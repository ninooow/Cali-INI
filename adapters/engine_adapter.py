import pandas as pd
import numpy as np
from datetime import datetime
from sqlalchemy.orm import Session
from typing import Dict, Any, List

from database import SessionLocal
from models.core import Asset, AssetMetadata, SensorTag, EquipmentLimit
from models.telemetry import HourlyMeasurement, WeeklyMeasurement
from models.knowledge import (
    Incident, RcaHeader, RcaPriorityMatrix,
    Rca4pVerification, Rca4mVerification, RcaCapaAction
)
from models.analytics import AnalysisRun, ConditionInference, ParameterForecast, RcaMatch
from models.workflow import ProblemTicket, OperatorInput, AuditLog

class EngineDataAdapter:
    """Adapter bridging PostgreSQL tables with the DataFrame contract expected by intelligence_engine.py."""

    @staticmethod
    def load_engine_input_data(db: Session) -> Dict[str, pd.DataFrame]:
        """Reconstruct workbook_data dictionary from database tables for intelligence_engine."""
        workbook_data: Dict[str, pd.DataFrame] = {}

        assets = db.query(Asset).filter(Asset.is_active == True).all()

        for asset in assets:
            tag = asset.tag_number

            # 1. Metadata
            meta_rows = db.query(AssetMetadata).filter(AssetMetadata.asset_id == asset.asset_id).all()
            if meta_rows:
                df_meta = pd.DataFrame([{"Parameter": m.parameter, "Value": m.value_text} for m in meta_rows])
            else:
                # Fallback to asset columns if raw metadata was empty
                df_meta = pd.DataFrame([
                    {"Parameter": "Equipment Tag", "Value": asset.tag_number},
                    {"Parameter": "Equipment Name", "Value": asset.asset_name},
                    {"Parameter": "Plant / Unit", "Value": asset.plant_unit},
                    {"Parameter": "Equipment Type", "Value": asset.equipment_type},
                    {"Parameter": "Equipment Class", "Value": asset.equipment_class},
                    {"Parameter": "Discipline", "Value": asset.discipline},
                    {"Parameter": "Criticality", "Value": asset.criticality},
                    {"Parameter": "Design Life", "Value": asset.design_life},
                    {"Parameter": "Monitoring Method", "Value": asset.monitoring_method},
                    {"Parameter": "Full Load Current (FLA)", "Value": str(asset.fla_amp or 150.0)},
                    {"Parameter": "Linked RCA / AR No.", "Value": asset.linked_rca_ar_no},
                    {"Parameter": "Failure Date", "Value": str(asset.failure_date) if asset.failure_date else ""},
                    {"Parameter": "Dominant Failure Mode", "Value": asset.dominant_failure_mode},
                ])
            workbook_data[f"{tag} Metadata"] = df_meta

            # 2. Tag Dictionary
            tag_rows = db.query(SensorTag).filter(SensorTag.asset_id == asset.asset_id).all()
            if tag_rows:
                df_tags = pd.DataFrame([{
                    "PI Tag": t.pi_tag,
                    "Name": t.name,
                    "Description": t.description,
                    "digitalset": t.digital_set,
                    "engunits": t.engineering_unit,
                    "span": float(t.span) if t.span is not None else np.nan,
                    "typicalvalue": float(t.typical_value) if t.typical_value is not None else np.nan,
                    "zero": float(t.zero_value) if t.zero_value is not None else np.nan,
                    "instrumenttag": t.instrument_tag
                } for t in tag_rows])
                workbook_data[f"{tag} Tag Dictionary"] = df_tags
            else:
                workbook_data[f"{tag} Tag Dictionary"] = pd.DataFrame(columns=["PI Tag", "Name", "Description", "digitalset", "engunits", "span", "typicalvalue", "zero", "instrumenttag"])

            # 3. Equipment Limits
            lim_rows = db.query(EquipmentLimit).filter(EquipmentLimit.asset_id == asset.asset_id).all()
            if lim_rows:
                df_lim = pd.DataFrame([{
                    "Parameter": l.parameter,
                    "Unit": l.unit,
                    "Alarm Limit": float(l.alarm_limit) if l.alarm_limit is not None else np.nan,
                    "Trip Limit": float(l.trip_limit) if l.trip_limit is not None else np.nan
                } for l in lim_rows])
                workbook_data[f"{tag} Equipment Limits"] = df_lim
            else:
                workbook_data[f"{tag} Equipment Limits"] = pd.DataFrame(columns=["Parameter", "Unit", "Alarm Limit", "Trip Limit"])

            # 4. Hourly Production Data
            hourly_rows = db.query(HourlyMeasurement).filter(
                HourlyMeasurement.asset_id == asset.asset_id
            ).order_by(HourlyMeasurement.measured_at.asc()).all()
            
            clean_tag = tag.replace("-", "")
            if hourly_rows:
                h_data = []
                for h in hourly_rows:
                    h_data.append({
                        "Timestamp": pd.to_datetime(h.measured_at).tz_localize(None) if hasattr(h.measured_at, 'tzinfo') and h.measured_at.tzinfo else pd.to_datetime(h.measured_at),
                        f"{clean_tag}_FEED": float(h.feed) if h.feed is not None else np.nan,
                        f"{clean_tag}_DISP": float(h.disp) if h.disp is not None else np.nan,
                        f"{clean_tag}_VIB": float(h.vib) if h.vib is not None else np.nan,
                        f"{clean_tag}_TEMP": float(h.temp) if h.temp is not None else np.nan,
                        f"{clean_tag}_AMP": float(h.amp) if h.amp is not None else np.nan,
                        "PLANT_RATE": float(h.plant_rate) if h.plant_rate is not None else np.nan,
                        "Plant Rate": float(h.plant_rate) if h.plant_rate is not None else np.nan,
                        "RUN_STATUS": h.run_status or "ON"
                    })
                workbook_data[f"{tag} Production Data Hourly"] = pd.DataFrame(h_data)
            else:
                workbook_data[f"{tag} Production Data Hourly"] = pd.DataFrame(columns=[
                    "Timestamp", f"{clean_tag}_FEED", f"{clean_tag}_DISP", f"{clean_tag}_VIB", f"{clean_tag}_TEMP", f"{clean_tag}_AMP", "PLANT_RATE", "RUN_STATUS"
                ])

            # 5. Weekly Performance Data (Pivoting long-form back to wide DataFrame)
            weekly_rows = db.query(WeeklyMeasurement).filter(
                WeeklyMeasurement.asset_id == asset.asset_id
            ).order_by(WeeklyMeasurement.record_date.asc()).all()

            if weekly_rows:
                # Group by record_date / week_no
                records_by_date = {}
                for w in weekly_rows:
                    d_key = (w.record_date, w.week_no)
                    if d_key not in records_by_date:
                        records_by_date[d_key] = {
                            "Week": w.week_no,
                            "Date": pd.to_datetime(w.record_date),
                            "Health Status": w.health_status or "NORMAL",
                            "Remark": w.remark or ""
                        }
                    col_name = w.source_column or (f"{w.parameter} ({w.unit})" if w.unit else w.parameter)
                    records_by_date[d_key][col_name] = float(w.measured_value) if w.measured_value is not None else np.nan

                df_weekly = pd.DataFrame(list(records_by_date.values()))
                workbook_data[f"{tag} Performance Weekly"] = df_weekly
            else:
                workbook_data[f"{tag} Performance Weekly"] = pd.DataFrame(columns=["Week", "Date", "Health Status", "Remark"])

        # 6. Global Knowledge / RCA Sheets
        # Incidents
        inc_rows = db.query(Incident).all()
        if inc_rows:
            workbook_data["Incident Record"] = pd.DataFrame([{
                "Serial No": i.serial_no,
                "MTO No.": i.mto_no,
                "AR No.": i.ar_no,
                "Plant": i.plant,
                "Tag Number": i.tag_number,
                "Eq. Class": i.equipment_class,
                "Date of Occur.": pd.to_datetime(i.date_of_occurrence) if i.date_of_occurrence else pd.NaT,
                "Risk Case Title": i.risk_case_title,
                "Highest Impact": i.highest_impact,
                "Pre-Risk": i.pre_risk,
                "Risk Score": float(i.risk_score) if i.risk_score is not None else np.nan,
                "PIC (RCA)": i.pic_rca,
                "Overall Status": i.overall_status,
                "Discipline": i.discipline,
                "Eq. Type": i.equipment_type,
                "Component": i.component,
                "F Mechanism": i.failure_mechanism,
                "Downtime (hrs)": float(i.downtime_hours) if i.downtime_hours is not None else np.nan,
                "Act. Loss (k US$)": float(i.actual_loss_kusd) if i.actual_loss_kusd is not None else np.nan,
                "Pot. Loss (k US$)": float(i.potential_loss_kusd) if i.potential_loss_kusd is not None else np.nan,
                "Total Loss (k US$)": float(i.total_loss_kusd) if i.total_loss_kusd is not None else np.nan,
                "RCA Due Date": pd.to_datetime(i.rca_due_date) if i.rca_due_date else pd.NaT,
                "Month - Year": i.month_year
            } for i in inc_rows])
        else:
            workbook_data["Incident Record"] = pd.DataFrame()

        # RCA Header
        rca_rows = db.query(RcaHeader).all()
        if rca_rows:
            workbook_data["RCA Header"] = pd.DataFrame([{
                "AR No": r.ar_no,
                "Tag Number": r.tag_number,
                "Plant": r.plant,
                "Date Occurrence": pd.to_datetime(r.date_occurrence) if r.date_occurrence else pd.NaT,
                "Pre Risk": r.pre_risk,
                "Risk Score": float(r.risk_score) if r.risk_score is not None else np.nan,
                "PIC RCA": r.pic_rca,
                "Procedure No": r.procedure_no,
                "Problem Statement": r.problem_statement,
                "Root Cause Statement": r.root_cause_statement
            } for r in rca_rows])
        else:
            workbook_data["RCA Header"] = pd.DataFrame()

        # RCA Priority Matrix
        pm_rows = db.query(RcaPriorityMatrix).all()
        if pm_rows:
            workbook_data["RCA Priority Matrix"] = pd.DataFrame([{
                "AR No": p.ar_no,
                "Root Cause ID": p.root_cause_id,
                "Impact Level": p.impact_level,
                "Control Level": p.control_level,
                "Priority Rank": p.priority_rank,
                "Description (Short)": p.description_short
            } for p in pm_rows])
        else:
            workbook_data["RCA Priority Matrix"] = pd.DataFrame()

        # RCA 4P Verification
        p4_rows = db.query(Rca4pVerification).all()
        if p4_rows:
            workbook_data["RCA 4P Verification"] = pd.DataFrame([{
                "AR No": p.ar_no,
                "Parameter ID": p.parameter_id,
                "Problem Phenomenon Parameter": p.problem_phenomenon_parameter,
                "Result": p.result,
                "Evidence Finding": p.evidence_finding
            } for p in p4_rows])
        else:
            workbook_data["RCA 4P Verification"] = pd.DataFrame()

        # RCA 4M Verification
        m4_rows = db.query(Rca4mVerification).all()
        if m4_rows:
            workbook_data["RCA 4M Verification"] = pd.DataFrame([{
                "AR No": m.ar_no,
                "Factor ID": m.factor_id,
                "Factor Category": m.factor_category,
                "Result": m.result,
                "Evidence Finding": m.evidence_finding
            } for m in m4_rows])
        else:
            workbook_data["RCA 4M Verification"] = pd.DataFrame()

        # RCA CAPA Actions
        capa_rows = db.query(RcaCapaAction).all()
        if capa_rows:
            workbook_data["RCA CAPA Actions"] = pd.DataFrame([{
                "AR No": c.ar_no,
                "RC": c.rc,
                "Action Type": c.action_type,
                "Action Plan": c.action_plan,
                "Target Date": pd.to_datetime(c.target_date) if c.target_date else pd.NaT,
                "PIC": c.pic,
                "Status": c.status
            } for c in capa_rows])
        else:
            workbook_data["RCA CAPA Actions"] = pd.DataFrame()

        return workbook_data

    @staticmethod
    def load_operator_inputs_df(db: Session) -> pd.DataFrame:
        """Load latest operator inputs per asset formatted for intelligence_engine."""
        cols = [
            "Asset", "Decision", "Operator", "Visible Leakage", "Abnormal Noise",
            "Abnormal Vibration", "Local Temperature Confirmed", "Field Observation",
            "Comment", "Updated At", "Owner Role", "Action Status"
        ]
        assets = db.query(Asset).all()
        asset_id_to_tag = {a.asset_id: a.tag_number for a in assets}

        # Query latest input per asset
        inputs = db.query(OperatorInput).order_by(OperatorInput.submitted_at.desc()).all()
        seen_assets = set()
        rows = []
        for inp in inputs:
            tag = asset_id_to_tag.get(inp.asset_id)
            if not tag or tag in seen_assets:
                continue
            seen_assets.add(tag)
            rows.append({
                "Asset": tag,
                "Decision": inp.decision or "",
                "Operator": inp.operator_name or "",
                "Visible Leakage": inp.visible_leakage or "",
                "Abnormal Noise": inp.abnormal_noise or "",
                "Abnormal Vibration": inp.abnormal_vibration or "",
                "Local Temperature Confirmed": inp.local_temperature_confirmed or "",
                "Field Observation": inp.field_observation or "",
                "Comment": inp.comment or "",
                "Updated At": inp.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if inp.submitted_at else "",
                "Owner Role": inp.owner_role or "",
                "Action Status": inp.action_status or "NOT_STARTED"
            })
        df = pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)
        for c in cols:
            df[c] = df[c].astype(object)
        return df

    @staticmethod
    def load_problem_tickets_df(db: Session) -> pd.DataFrame:
        """Load problem tickets from database formatted for intelligence_engine."""
        cols = [
            "Ticket ID", "Asset", "Opened At", "Last Seen", "Condition State", "Priority",
            "Owner Role", "Ticket State", "Action Status", "Normal Streak", "Matched RCA",
            "Evidence Strength", "Operator Decision", "Operator", "Operator Comment",
            "Field Observation", "Update Source", "Last Observation"
        ]
        assets = db.query(Asset).all()
        asset_id_to_tag = {a.asset_id: a.tag_number for a in assets}

        tickets = db.query(ProblemTicket).all()
        rows = []
        for t in tickets:
            tag = asset_id_to_tag.get(t.asset_id, "")
            rows.append({
                "Ticket ID": t.ticket_id,
                "Asset": tag,
                "Opened At": t.opened_at.strftime("%Y-%m-%d %H:%M:%S") if t.opened_at else "",
                "Last Seen": t.last_seen.strftime("%Y-%m-%d %H:%M:%S") if t.last_seen else "",
                "Condition State": t.condition_state or "",
                "Priority": t.priority or "",
                "Owner Role": t.owner_role or "",
                "Ticket State": t.ticket_state or "OPEN",
                "Action Status": t.action_status or "NOT_STARTED",
                "Normal Streak": int(t.normal_streak or 0),
                "Matched RCA": t.matched_rca_ar or "",
                "Evidence Strength": t.evidence_strength or "",
                "Operator Decision": t.operator_decision or "",
                "Operator": t.last_operator_name or "",
                "Operator Comment": t.operator_comment or "",
                "Field Observation": t.field_observation or "",
                "Update Source": t.update_source or "ENGINE",
                "Last Observation": t.last_observation_time.strftime("%Y-%m-%d %H:%M:%S") if t.last_observation_time else ""
            })
        df = pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)
        for c in cols:
            if c != "Normal Streak":
                df[c] = df[c].astype(object)
            else:
                df[c] = df[c].astype(int)
        return df

    @staticmethod
    def persist_analysis_results(db: Session, engine_result: Dict[str, Any], started_at: datetime, reference_time: datetime = None) -> AnalysisRun:
        """Persist analysis run and detailed inference results to database."""
        completed_at = datetime.now()
        assets = db.query(Asset).all()
        tag_to_asset = {a.tag_number: a for a in assets}

        run = AnalysisRun(
            started_at=started_at,
            completed_at=completed_at,
            reference_time=reference_time or datetime.now(),
            engine_version="V11.x",
            runtime_mode="SNAPSHOT",
            status="COMPLETED"
        )
        db.add(run)
        db.flush()

        for asset_res in engine_result.get("results", []):
            tag = asset_res.get("tag_number")
            asset_obj = tag_to_asset.get(tag)
            if not asset_obj:
                continue

            cond = asset_res.get("condition", {})
            inf = ConditionInference(
                run_id=run.run_id,
                asset_id=asset_obj.asset_id,
                as_of_time=cond.get("decision_time", cond.get("current_time", datetime.now())),
                overall_state=cond.get("overall_state"),
                consequence_class=asset_res.get("consequence_class"),
                priority=asset_res.get("priority"),
                dominant_symptom=cond.get("dominant_symptom"),
                health_index=cond.get("health_index"),
                pca_anomaly_score=cond.get("pca_anomaly_score"),
                max_zscore=cond.get("max_zscore"),
                statistical_available=cond.get("statistical_available", True)
            )
            db.add(inf)

            # Persist RCA Matches
            evidence = asset_res.get("rca_evidence", {})
            for rank, cand in enumerate(evidence.get("candidates", []), 1):
                rca_match = RcaMatch(
                    run_id=run.run_id,
                    asset_id=asset_obj.asset_id,
                    matched_ar_no=cand.get("AR No"),
                    similarity_score=cand.get("Case Similarity"),
                    evidence_strength=cand.get("Evidence Strength"),
                    rank_no=rank,
                    current_supporting_evidence=str(cand.get("Current Evidence", "")),
                    historical_verified_evidence=str(cand.get("Historical Verified Evidence", ""))
                )
                db.add(rca_match)

            # Persist Forecasts
            forecast_objects = []
            proj = asset_res.get("projection", {})

            for param_name, param_info in proj.get("parameters", {}).items():
                trace = param_info.get("trace")

                if not isinstance(trace, pd.DataFrame) or trace.empty:
                    continue

                model_info = param_info.get("model", {})
                model_name = (
                    model_info.get("fit", {}).get("name", "")
                    if isinstance(model_info, dict)
                    else str(model_info)
                )

                for t_idx, row in trace.iterrows():
                    val = row.get("Estimate", np.nan)
                    if pd.isna(val):
                        continue

                    low_val = row.get("Lower", np.nan)
                    up_val = row.get("Upper", np.nan)

                    forecast_objects.append(ParameterForecast(
                        run_id=run.run_id,
                        asset_id=asset_obj.asset_id,
                        canonical_param=param_name,
                        anchor_time=reference_time or datetime.now(),
                        target_time=pd.to_datetime(t_idx),
                        estimate=float(val),
                        lower_bound=float(low_val) if pd.notna(low_val) else None,
                        upper_bound=float(up_val) if pd.notna(up_val) else None,
                        model_family=str(model_name)
                    ))
            if forecast_objects:
                db.bulk_save_objects(forecast_objects)

            # Sync Problem Tickets
            ticket_data = asset_res.get("ticket", {})
            if ticket_data and ticket_data.get("ticket_id"):
                tid = ticket_data.get("ticket_id")
                pt = db.query(ProblemTicket).filter(ProblemTicket.ticket_id == tid).first()
                if not pt:
                    pt = ProblemTicket(
                        ticket_id=tid,
                        asset_id=asset_obj.asset_id,
                        opened_at=datetime.now(),
                        last_seen=datetime.now(),
                        condition_state=cond.get("overall_state"),
                        priority=ticket_data.get("priority"),
                        owner_role=ticket_data.get("owner"),
                        ticket_state=ticket_data.get("ticket_state", "OPEN"),
                        action_status=ticket_data.get("action_status", "NOT_STARTED"),
                        normal_streak=0,
                        matched_rca_ar=evidence.get("matched_ar"),
                        evidence_strength=evidence.get("evidence_strength"),
                        operator_decision=ticket_data.get("operator_decision", "")
                    )
                    db.add(pt)
                else:
                    pt.last_seen = datetime.now()
                    pt.ticket_state = ticket_data.get("ticket_state", pt.ticket_state)
                    pt.action_status = ticket_data.get("action_status", pt.action_status)

        db.commit()
        return run
