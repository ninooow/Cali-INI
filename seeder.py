import os
import hashlib
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text

from config import settings
from database import SessionLocal, init_db
from models.core import Asset, AssetMetadata, SensorTag, EquipmentLimit
from models.telemetry import HourlyMeasurement, WeeklyMeasurement
from models.knowledge import (
    Incident, RcaHeader, RcaPriorityMatrix,
    Rca4pVerification, Rca4mVerification, RcaCapaAction
)
from models.workflow import ProblemTicket, OperatorInput, AuditLog
from models.system import SeedRun

ASSET_TAGS = ["PU-2101B", "KO-3201", "PM-4405B", "HE-3301", "BL-5702"]

def safe_str(val):
    if pd.isna(val) or val is None:
        return None
    s = str(val).strip()
    return s if s else None

def safe_num(val):
    if pd.isna(val) or val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def safe_int(val):
    if pd.isna(val) or val is None:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None

def safe_date(val):
    if pd.isna(val) or val is None:
        return None
    try:
        dt = pd.to_datetime(val)
        return dt.date()
    except Exception:
        return None

def safe_datetime(val):
    if pd.isna(val) or val is None:
        return None
    try:
        return pd.to_datetime(val).to_pydatetime()
    except Exception:
        return None

def compute_checksum(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def seed_database(workbook_path: str = None, force: bool = False):
    init_db()
    db: Session = SessionLocal()
    workbook_path = workbook_path or settings.WORKBOOK_PATH
    
    if not os.path.exists(workbook_path):
        raise FileNotFoundError(f"Workbook not found at {workbook_path}")

    filename = os.path.basename(workbook_path)
    checksum = compute_checksum(workbook_path)
    start_time = datetime.now()

    # Create SeedRun record
    seed_run = SeedRun(
        source_filename=filename,
        source_checksum=checksum,
        started_at=start_time,
        status="RUNNING",
        warnings=[],
        errors=[]
    )
    db.add(seed_run)
    db.commit()
    db.refresh(seed_run)

    warnings = []
    errors = []

    try:
        wb = pd.ExcelFile(workbook_path)
        sheet_names = wb.sheet_names

        # 1. CORE ASSETS & METADATA
        assets_seeded = 0
        metadata_seeded = 0
        sensor_tags_seeded = 0
        limits_seeded = 0

        asset_map = {}  # tag_number -> Asset instance or asset_id

        for tag in ASSET_TAGS:
            meta_sheet = f"{tag} Metadata"
            if meta_sheet in sheet_names:
                df_meta = pd.read_excel(wb, sheet_name=meta_sheet)
                meta_dict = {}
                for _, row in df_meta.iterrows():
                    p = safe_str(row.get("Parameter"))
                    v = safe_str(row.get("Value"))
                    if p:
                        meta_dict[p] = v

                # Determine core mode
                core_mode = "weekly" if tag == "HE-3301" else "hourly"
                
                # Fla amp
                fla = 150.0
                if "Full Load Current (FLA)" in meta_dict:
                    fla = safe_num(meta_dict["Full Load Current (FLA)"]) or 150.0
                elif "FLA" in meta_dict:
                    fla = safe_num(meta_dict["FLA"]) or 150.0

                asset = db.query(Asset).filter(Asset.tag_number == tag).first()
                if not asset:
                    asset = Asset(
                        tag_number=tag,
                        asset_name=meta_dict.get("Equipment Name") or tag,
                        plant_unit=meta_dict.get("Plant / Unit"),
                        plant_code=safe_str(meta_dict.get("Plant / Unit")),
                        equipment_type=meta_dict.get("Equipment Type"),
                        equipment_class=meta_dict.get("Equipment Class"),
                        discipline=meta_dict.get("Discipline"),
                        criticality=meta_dict.get("Criticality", "MEDIUM"),
                        design_life=meta_dict.get("Design Life"),
                        monitoring_method=meta_dict.get("Monitoring Method"),
                        core_mode=core_mode,
                        fla_amp=fla,
                        linked_rca_ar_no=meta_dict.get("Linked RCA / AR No."),
                        failure_date=safe_date(meta_dict.get("Failure Date")),
                        dominant_failure_mode=meta_dict.get("Dominant Failure Mode")
                    )
                    db.add(asset)
                    db.flush()
                else:
                    asset.asset_name = meta_dict.get("Equipment Name") or tag
                    asset.plant_unit = meta_dict.get("Plant / Unit")
                    asset.equipment_type = meta_dict.get("Equipment Type")
                    asset.equipment_class = meta_dict.get("Equipment Class")
                    asset.discipline = meta_dict.get("Discipline")
                    asset.criticality = meta_dict.get("Criticality", "MEDIUM")
                    asset.design_life = meta_dict.get("Design Life")
                    asset.monitoring_method = meta_dict.get("Monitoring Method")
                    asset.core_mode = core_mode
                    asset.fla_amp = fla
                    asset.linked_rca_ar_no = meta_dict.get("Linked RCA / AR No.")
                    asset.failure_date = safe_date(meta_dict.get("Failure Date"))
                    asset.dominant_failure_mode = meta_dict.get("Dominant Failure Mode")
                    db.flush()

                asset_map[tag] = asset
                assets_seeded += 1

                # Seed raw metadata lossless
                for p, v in meta_dict.items():
                    existing_meta = db.query(AssetMetadata).filter(
                        AssetMetadata.asset_id == asset.asset_id,
                        AssetMetadata.parameter == p
                    ).first()
                    if not existing_meta:
                        db.add(AssetMetadata(
                            asset_id=asset.asset_id,
                            parameter=p,
                            value_text=v,
                            source_sheet=meta_sheet
                        ))
                        metadata_seeded += 1
                    else:
                        existing_meta.value_text = v

            # 2. TAG DICTIONARY
            tag_sheet = f"{tag} Tag Dictionary"
            if tag_sheet in sheet_names and tag in asset_map:
                df_tags = pd.read_excel(wb, sheet_name=tag_sheet)
                asset_obj = asset_map[tag]
                for _, row in df_tags.iterrows():
                    pi_tag = safe_str(row.get("PI Tag"))
                    if not pi_tag:
                        continue
                    
                    # Deduce canonical parameter
                    canon = None
                    u_pi = pi_tag.upper()
                    if u_pi.endswith("_FEED"): canon = "FEED"
                    elif u_pi.endswith("_DISP"): canon = "DISP"
                    elif u_pi.endswith("_VIB"): canon = "VIB"
                    elif u_pi.endswith("_TEMP"): canon = "TEMP"
                    elif u_pi.endswith("_AMP"): canon = "AMP"

                    existing_tag = db.query(SensorTag).filter(
                        SensorTag.asset_id == asset_obj.asset_id,
                        SensorTag.pi_tag == pi_tag
                    ).first()
                    if not existing_tag:
                        db.add(SensorTag(
                            asset_id=asset_obj.asset_id,
                            pi_tag=pi_tag,
                            canonical_param=canon,
                            name=safe_str(row.get("Name")),
                            description=safe_str(row.get("Description")),
                            digital_set=safe_str(row.get("digitalset")),
                            engineering_unit=safe_str(row.get("engunits")),
                            span=safe_num(row.get("span")),
                            typical_value=safe_num(row.get("typicalvalue")),
                            zero_value=safe_num(row.get("zero")),
                            instrument_tag=safe_str(row.get("instrumenttag")),
                            source_sheet=tag_sheet
                        ))
                        sensor_tags_seeded += 1

            # 3. EQUIPMENT LIMITS
            limits_sheet = f"{tag} Equipment Limits"
            if limits_sheet in sheet_names and tag in asset_map:
                df_lim = pd.read_excel(wb, sheet_name=limits_sheet)
                asset_obj = asset_map[tag]
                for _, row in df_lim.iterrows():
                    param = safe_str(row.get("Parameter"))
                    if not param:
                        continue
                    alarm = safe_num(row.get("Alarm Limit"))
                    trip = safe_num(row.get("Trip Limit"))
                    if alarm is None or trip is None:
                        continue

                    existing_lim = db.query(EquipmentLimit).filter(
                        EquipmentLimit.asset_id == asset_obj.asset_id,
                        EquipmentLimit.parameter == param
                    ).first()
                    if not existing_lim:
                        db.add(EquipmentLimit(
                            asset_id=asset_obj.asset_id,
                            parameter=param,
                            unit=safe_str(row.get("Unit")),
                            alarm_limit=alarm,
                            trip_limit=trip,
                            source_sheet=limits_sheet
                        ))
                        limits_seeded += 1
                    else:
                        existing_lim.alarm_limit = alarm
                        existing_lim.trip_limit = trip
                        existing_lim.unit = safe_str(row.get("Unit"))

        db.commit()

        # 4. TELEMETRY: HOURLY
        hourly_seeded = 0
        for tag in ASSET_TAGS:
            hourly_sheet = f"{tag} Production Data Hourly"
            if hourly_sheet in sheet_names and tag in asset_map:
                asset_obj = asset_map[tag]
                df_hourly = pd.read_excel(wb, sheet_name=hourly_sheet)
                
                # Identify columns
                cols = {c.upper(): c for c in df_hourly.columns}
                ts_col = cols.get("TIMESTAMP", "Timestamp")
                feed_col = next((cols[k] for k in cols if k.endswith("_FEED")), None)
                disp_col = next((cols[k] for k in cols if k.endswith("_DISP")), None)
                vib_col = next((cols[k] for k in cols if k.endswith("_VIB")), None)
                temp_col = next((cols[k] for k in cols if k.endswith("_TEMP")), None)
                amp_col = next((cols[k] for k in cols if k.endswith("_AMP")), None)
                plant_col = next((cols[k] for k in cols if "PLANT" in k), None)
                run_col = cols.get("RUN_STATUS", "RUN_STATUS")

                hourly_objects = []
                for _, row in df_hourly.iterrows():
                    ts = safe_datetime(row.get(ts_col))
                    if not ts:
                        continue
                    
                    r_status = safe_str(row.get(run_col))
                    if r_status and r_status.upper() in ["ON", "OFF", "UNKNOWN"]:
                        r_status = r_status.upper()
                    else:
                        r_status = "UNKNOWN" if r_status else None

                    hourly_objects.append(HourlyMeasurement(
                        asset_id=asset_obj.asset_id,
                        measured_at=ts,
                        feed=safe_num(row.get(feed_col)) if feed_col else None,
                        disp=safe_num(row.get(disp_col)) if disp_col else None,
                        vib=safe_num(row.get(vib_col)) if vib_col else None,
                        temp=safe_num(row.get(temp_col)) if temp_col else None,
                        amp=safe_num(row.get(amp_col)) if amp_col else None,
                        plant_rate=safe_num(row.get(plant_col)) if plant_col else None,
                        run_status=r_status,
                        source_type="LEGACY_SEED",
                        source_sheet=hourly_sheet
                    ))
                
                # Bulk insert / merge
                if hourly_objects:
                    # Delete existing legacy seed for this asset if force or fresh
                    db.query(HourlyMeasurement).filter(
                        HourlyMeasurement.asset_id == asset_obj.asset_id,
                        HourlyMeasurement.source_type == "LEGACY_SEED"
                    ).delete()
                    db.bulk_save_objects(hourly_objects)
                    db.commit()
                    hourly_seeded += len(hourly_objects)

        # 5. TELEMETRY: WEEKLY (Long form)
        weekly_source_rows = 0
        weekly_seeded = 0
        for tag in ASSET_TAGS:
            weekly_sheet = f"{tag} Performance Weekly"
            if weekly_sheet in sheet_names and tag in asset_map:
                asset_obj = asset_map[tag]
                df_weekly = pd.read_excel(wb, sheet_name=weekly_sheet)
                weekly_source_rows += len(df_weekly)

                meta_cols = {"WEEK", "DATE", "HEALTH STATUS", "REMARK"}
                param_cols = [c for c in df_weekly.columns if c.upper().strip() not in meta_cols]

                # Clear previous seed
                db.query(WeeklyMeasurement).filter(
                    WeeklyMeasurement.asset_id == asset_obj.asset_id,
                    WeeklyMeasurement.source_type == "LEGACY_SEED"
                ).delete()

                weekly_objects = []
                for _, row in df_weekly.iterrows():
                    rec_date = safe_date(row.get("Date"))
                    if not rec_date:
                        continue
                    week_no = safe_int(row.get("Week"))
                    health = safe_str(row.get("Health Status"))
                    remark = safe_str(row.get("Remark"))

                    for pcol in param_cols:
                        val = safe_num(row.get(pcol))
                        # extract clean param name and unit if present
                        p_name = pcol.replace("\n", " ").strip()
                        unit = None
                        if "(" in p_name and p_name.endswith(")"):
                            parts = p_name.rsplit("(", 1)
                            p_clean = parts[0].strip()
                            unit = parts[1].rstrip(")").strip()
                        else:
                            p_clean = p_name

                        weekly_objects.append(WeeklyMeasurement(
                            asset_id=asset_obj.asset_id,
                            week_no=week_no,
                            record_date=rec_date,
                            parameter=p_clean,
                            measured_value=val,
                            unit=unit,
                            health_status=health,
                            remark=remark,
                            source_type="LEGACY_SEED",
                            source_column=pcol,
                            source_sheet=weekly_sheet
                        ))
                
                if weekly_objects:
                    db.bulk_save_objects(weekly_objects)
                    db.commit()
                    weekly_seeded += len(weekly_objects)

        # 6. RELIABILITY: INCIDENTS
        incidents_seeded = 0
        if "Incident Record" in sheet_names:
            df_inc = pd.read_excel(wb, sheet_name="Incident Record")
            db.query(Incident).filter(Incident.source_type == "LEGACY_SEED").delete()
            incident_objects = []
            for _, row in df_inc.iterrows():
                incident_objects.append(Incident(
                    serial_no=safe_int(row.get("Serial No")),
                    mto_no=safe_str(row.get("MTO No.")),
                    ar_no=safe_str(row.get("AR No.")),
                    plant=safe_str(row.get("Plant")),
                    tag_number=safe_str(row.get("Tag Number")),
                    equipment_class=safe_str(row.get("Eq. Class")),
                    date_of_occurrence=safe_date(row.get("Date of Occur.")),
                    risk_case_title=safe_str(row.get("Risk Case Title")),
                    highest_impact=safe_str(row.get("Highest Impact")),
                    pre_risk=safe_str(row.get("Pre-Risk")),
                    risk_score=safe_num(row.get("Risk Score")),
                    pic_rca=safe_str(row.get("PIC (RCA)")),
                    overall_status=safe_str(row.get("Overall Status")),
                    discipline=safe_str(row.get("Discipline")),
                    equipment_type=safe_str(row.get("Eq. Type")),
                    component=safe_str(row.get("Component")),
                    failure_mechanism=safe_str(row.get("F Mechanism")),
                    downtime_hours=safe_num(row.get("Downtime (hrs)")),
                    actual_loss_kusd=safe_num(row.get("Act. Loss (k US$)")),
                    potential_loss_kusd=safe_num(row.get("Pot. Loss (k US$)")),
                    total_loss_kusd=safe_num(row.get("Total Loss (k US$)")),
                    rca_due_date=safe_date(row.get("RCA Due Date")),
                    month_year=safe_str(row.get("Month - Year")),
                    source_type="LEGACY_SEED",
                    source_sheet="Incident Record"
                ))
            if incident_objects:
                db.bulk_save_objects(incident_objects)
                db.commit()
                incidents_seeded = len(incident_objects)

        # 7. RELIABILITY: RCA HEADER
        rca_headers_seeded = 0
        if "RCA Header" in sheet_names:
            df_rca = pd.read_excel(wb, sheet_name="RCA Header")
            for _, row in df_rca.iterrows():
                ar = safe_str(row.get("AR No"))
                if not ar:
                    continue
                rca = db.query(RcaHeader).filter(RcaHeader.ar_no == ar).first()
                if not rca:
                    rca = RcaHeader(
                        ar_no=ar,
                        tag_number=safe_str(row.get("Tag Number")),
                        plant=safe_str(row.get("Plant")),
                        date_occurrence=safe_date(row.get("Date Occurrence")),
                        pre_risk=safe_str(row.get("Pre Risk")),
                        risk_score=safe_num(row.get("Risk Score")),
                        pic_rca=safe_str(row.get("PIC RCA")),
                        procedure_no=safe_str(row.get("Procedure No")),
                        problem_statement=safe_str(row.get("Problem Statement")),
                        root_cause_statement=safe_str(row.get("Root Cause Statement")),
                        source_type="LEGACY_SEED",
                        source_sheet="RCA Header"
                    )
                    db.add(rca)
                    rca_headers_seeded += 1
                else:
                    rca.problem_statement = safe_str(row.get("Problem Statement"))
                    rca.root_cause_statement = safe_str(row.get("Root Cause Statement"))
            db.commit()

        # 8. RCA PRIORITY MATRIX
        rca_priority_seeded = 0
        if "RCA Priority Matrix" in sheet_names:
            df_rpm = pd.read_excel(wb, sheet_name="RCA Priority Matrix")
            for _, row in df_rpm.iterrows():
                ar = safe_str(row.get("AR No"))
                rc_id = safe_str(row.get("Root Cause ID"))
                if not ar or not rc_id:
                    continue
                
                # Check header exists
                if not db.query(RcaHeader).filter(RcaHeader.ar_no == ar).first():
                    continue

                existing = db.query(RcaPriorityMatrix).filter(
                    RcaPriorityMatrix.ar_no == ar,
                    RcaPriorityMatrix.root_cause_id == rc_id
                ).first()
                if not existing:
                    db.add(RcaPriorityMatrix(
                        ar_no=ar,
                        root_cause_id=rc_id,
                        impact_level=safe_str(row.get("Impact Level")),
                        control_level=safe_str(row.get("Control Level")),
                        priority_rank=safe_int(row.get("Priority Rank")),
                        description_short=safe_str(row.get("Description (Short)"))
                    ))
                    rca_priority_seeded += 1
            db.commit()

        # 9. RCA 4P VERIFICATION
        rca_4p_seeded = 0
        if "RCA 4P Verification" in sheet_names:
            df_4p = pd.read_excel(wb, sheet_name="RCA 4P Verification")
            for _, row in df_4p.iterrows():
                ar = safe_str(row.get("AR No"))
                pid = safe_str(row.get("Parameter ID"))
                if not ar or not pid:
                    continue
                if not db.query(RcaHeader).filter(RcaHeader.ar_no == ar).first():
                    continue

                existing = db.query(Rca4pVerification).filter(
                    Rca4pVerification.ar_no == ar,
                    Rca4pVerification.parameter_id == pid
                ).first()
                if not existing:
                    db.add(Rca4pVerification(
                        ar_no=ar,
                        parameter_id=pid,
                        problem_phenomenon_parameter=safe_str(row.get("Problem Phenomenon Parameter")),
                        result=safe_str(row.get("Result")),
                        evidence_finding=safe_str(row.get("Evidence Finding"))
                    ))
                    rca_4p_seeded += 1
            db.commit()

        # 10. RCA 4M VERIFICATION
        rca_4m_seeded = 0
        if "RCA 4M Verification" in sheet_names:
            df_4m = pd.read_excel(wb, sheet_name="RCA 4M Verification")
            for _, row in df_4m.iterrows():
                ar = safe_str(row.get("AR No"))
                fid = safe_str(row.get("Factor ID"))
                if not ar or not fid:
                    continue
                if not db.query(RcaHeader).filter(RcaHeader.ar_no == ar).first():
                    continue

                existing = db.query(Rca4mVerification).filter(
                    Rca4mVerification.ar_no == ar,
                    Rca4mVerification.factor_id == fid
                ).first()
                if not existing:
                    db.add(Rca4mVerification(
                        ar_no=ar,
                        factor_id=fid,
                        factor_category=safe_str(row.get("Factor Category")),
                        result=safe_str(row.get("Result")),
                        evidence_finding=safe_str(row.get("Evidence Finding"))
                    ))
                    rca_4m_seeded += 1
            db.commit()

        # 11. RCA CAPA ACTIONS
        rca_capa_seeded = 0
        if "RCA CAPA Actions" in sheet_names:
            df_capa = pd.read_excel(wb, sheet_name="RCA CAPA Actions")
            for _, row in df_capa.iterrows():
                ar = safe_str(row.get("AR No"))
                action_plan = safe_str(row.get("Action Plan"))
                if not ar or not action_plan:
                    continue
                if not db.query(RcaHeader).filter(RcaHeader.ar_no == ar).first():
                    continue

                rc = safe_str(row.get("RC"))
                act_type = safe_str(row.get("Action Type"))
                tgt_date = safe_date(row.get("Target Date"))
                
                # Deterministic fingerprint
                fp_str = f"{ar}|{rc or ''}|{act_type or ''}|{action_plan.strip().lower()}|{str(tgt_date or '')}"
                fingerprint = hashlib.sha256(fp_str.encode("utf-8")).hexdigest()

                existing = db.query(RcaCapaAction).filter(RcaCapaAction.fingerprint == fingerprint).first()
                if not existing:
                    db.add(RcaCapaAction(
                        ar_no=ar,
                        rc=rc,
                        action_type=act_type,
                        action_plan=action_plan,
                        target_date=tgt_date,
                        pic=safe_str(row.get("PIC")),
                        status=safe_str(row.get("Status")),
                        fingerprint=fingerprint
                    ))
                    rca_capa_seeded += 1
            db.commit()

        # 12. MIGRATE CSV WORKFLOW STATE IF PRESENT
        out_dir = settings.OUTPUT_DIR
        pt_csv = os.path.join(out_dir, "problem_tank_history.csv")
        if os.path.exists(pt_csv):
            try:
                df_pt = pd.read_csv(pt_csv, dtype=str).fillna("")
                for _, r in df_pt.iterrows():
                    tid = safe_str(r.get("Ticket ID"))
                    asset_tag = safe_str(r.get("Asset"))
                    if not tid or not asset_tag or asset_tag not in asset_map:
                        continue
                    
                    asset_obj = asset_map[asset_tag]
                    ticket = db.query(ProblemTicket).filter(ProblemTicket.ticket_id == tid).first()
                    if not ticket:
                        ticket = ProblemTicket(
                            ticket_id=tid,
                            asset_id=asset_obj.asset_id,
                            opened_at=safe_datetime(r.get("Opened At")) or datetime.now(),
                            last_seen=safe_datetime(r.get("Last Seen")) or datetime.now(),
                            condition_state=safe_str(r.get("Condition State")),
                            priority=safe_str(r.get("Priority")),
                            owner_role=safe_str(r.get("Owner Role")),
                            ticket_state=safe_str(r.get("Ticket State")) or "OPEN",
                            action_status=safe_str(r.get("Action Status")) or "NOT_STARTED",
                            normal_streak=safe_int(r.get("Normal Streak")) or 0,
                            matched_rca_ar=safe_str(r.get("Matched RCA")),
                            evidence_strength=safe_str(r.get("Evidence Strength")),
                            operator_decision=safe_str(r.get("Operator Decision")),
                            last_operator_name=safe_str(r.get("Operator")),
                            operator_comment=safe_str(r.get("Operator Comment")),
                            field_observation=safe_str(r.get("Field Observation")),
                            update_source=safe_str(r.get("Update Source")) or "ENGINE",
                            last_observation_time=safe_datetime(r.get("Last Observation"))
                        )
                        db.add(ticket)
                    else:
                        ticket.last_seen = safe_datetime(r.get("Last Seen")) or datetime.now()
                        ticket.ticket_state = safe_str(r.get("Ticket State")) or ticket.ticket_state
                        ticket.action_status = safe_str(r.get("Action Status")) or ticket.action_status
                        ticket.normal_streak = safe_int(r.get("Normal Streak")) or ticket.normal_streak
                db.commit()
            except Exception as e:
                warnings.append(f"CSV problem_tank_history import notice: {str(e)}")

        # Complete SeedRun
        seed_run.completed_at = datetime.now()
        seed_run.status = "COMPLETED"
        seed_run.assets_count = assets_seeded
        seed_run.metadata_count = metadata_seeded
        seed_run.sensor_tags_count = sensor_tags_seeded
        seed_run.equipment_limits_count = limits_seeded
        seed_run.hourly_count = hourly_seeded
        seed_run.weekly_source_rows = weekly_source_rows
        seed_run.weekly_measurements_count = weekly_seeded
        seed_run.incidents_count = incidents_seeded
        seed_run.rca_headers_count = rca_headers_seeded
        seed_run.rca_priority_count = rca_priority_seeded
        seed_run.rca_4p_count = rca_4p_seeded
        seed_run.rca_4m_count = rca_4m_seeded
        seed_run.rca_capa_count = rca_capa_seeded
        seed_run.warnings = warnings
        seed_run.errors = errors
        db.commit()

        print("=" * 60)
        print("SEEDING COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print(f"Assets:               {assets_seeded}")
        print(f"Metadata rows:        {metadata_seeded}")
        print(f"Sensor tags:          {sensor_tags_seeded}")
        print(f"Equipment limits:     {limits_seeded}")
        print(f"Hourly measurements:  {hourly_seeded}")
        print(f"Weekly measurements:  {weekly_seeded}")
        print(f"Incidents:            {incidents_seeded}")
        print(f"RCA Headers:          {rca_headers_seeded}")
        print(f"RCA Priority Matrix:  {rca_priority_seeded}")
        print(f"RCA 4P Verifications: {rca_4p_seeded}")
        print(f"RCA 4M Verifications: {rca_4m_seeded}")
        print(f"RCA CAPA Actions:     {rca_capa_seeded}")
        print("=" * 60)

        return seed_run

    except Exception as e:
        db.rollback()
        seed_run.completed_at = datetime.now()
        seed_run.status = "FAILED"
        seed_run.errors = [str(e)]
        db.commit()
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
