# -*- coding: utf-8 -*-
"""
==============================================================================
 Intelligent Manufacturing V11.6 — Case-2 executive domains, governed proxies, and closed-loop actions
==============================================================================
Reference time is resolved from the latest timestamp commonly available to all five assets at each engine run.

Revision goals implemented in V10.10:
- one operational forecasting engine and one definition for every canonical PF/plot function;
- raw observations remain untouched while analytical Estimate/Lower/Upper are complete;
- short-gap interpolation is provenance-labeled; long gaps use state-space reconstruction;
- weekly-only parameters use latent-state Kalman/RTS estimation, not hourly pseudo-actuals;
- hybrid hourly + weekly parameters treat weekly results as state corrections;
- validated indirect hourly soft sensors (DCS covariates -> weekly engineering targets) feed the same canonical trace;
- rolling-origin model selection uses common origins/horizons and conservative 30-day horizon;
- harmonic candidates are available only when cadence/cycle support exists and backtest wins;
- plots, AS-OF status, RCA events, CSV and Excel reuse the same canonical trace;
- executive KPIs are normalized to each asset's own healthy baseline and never re-fit models;
- hard completeness validation blocks plotting when canonical numeric output is invalid.

Environment overrides:
  IM_WORKBOOK   input workbook
  IM_OUTPUT_DIR output directory
==============================================================================
"""

import os
from pathlib import Path
import re
import math
import warnings
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
import hashlib

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
try:
    from statsmodels.tsa.ar_model import AutoReg
except ImportError:
    AutoReg = None  # Explicitly reported; Persistence and OLS remain available.

# Warnings remain visible; numeric/data failures must not be silently hidden.
pd.set_option("mode.chained_assignment", None)

# ==============================================================================
# KONFIGURASI GLOBAL
# ==============================================================================
# Can be overridden in Spyder or through IM_WORKBOOK environment variable.
SCRIPT_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
FILE_PATH = os.environ.get("IM_WORKBOOK", str(SCRIPT_DIR / "All_Case_Data.xlsx"))
if not Path(FILE_PATH).exists() and "IM_WORKBOOK" not in os.environ:
    for folder in (SCRIPT_DIR, Path.cwd()):
        for name in ("All_Case_Data.xlsx", "All_Case_Data(1).xlsx", "All_Case_Data(2).xlsx", "All_Raw_Data.xlsx", "All_Raw_Data(1).xlsx", "All_Raw_Data(2).xlsx"):
            candidate = folder / name
            if candidate.exists():
                FILE_PATH = str(candidate)
                break
        if Path(FILE_PATH).exists():
            break
RUNTIME_MODE = "SNAPSHOT"  # Explicit: SNAPSHOT / LIVE; never auto-revert stale LIVE to historical.
MIN_RCA_SIMILARITY = 0.25
MIN_HEALTHY_WEEKLY_ROWS = 12
REPLAY_LOOKBACK_HOURS = 48
REPLAY_GRID_HOURS = 1
REPLAY_NORMAL_CHECKS = 12  # Descriptive sampled alert rate, not validated specificity.
MIN_FORECAST_HOURLY_ROWS = 48
OUTPUT_DIR = os.environ.get("IM_OUTPUT_DIR", str(SCRIPT_DIR / "dashboard_output_v10_10"))
SAVE_PLOTS = True
SHOW_PLOTS = False  # Production: save figures without repeated GUI rendering
RUN_HISTORICAL_REPLAY = False  # Normal run; enable for chronological causal replay audit
AUDIT_MODE = False  # False = compact operational export; True = full traces/backtest audit
VERBOSE_CONSOLE = False  # True to print detailed information for each phase/calculation

# Operator / live-use controls
INTERACTIVE_OPERATOR_MODE = False  # True: request confirmation via console; False: use the CSV queue
AUTO_LIVE_MODE_MAX_LAG_DAYS = 7    # dataset dekat wall-clock dianggap live
LIVE_FRESHNESS_HOURS = 2.0         # latest hourly data older than this threshold -> STALE
LIVE_WEEKLY_FRESHNESS_DAYS = 8.0     # weekly core data older than this threshold -> STALE_WEEKLY
HOURLY_PERSISTENCE_WINDOW = 4
HOURLY_PERSISTENCE_MIN_COUNT = 3
WEEKLY_PERSISTENCE_WINDOW = 3
WEEKLY_PERSISTENCE_MIN_COUNT = 2
TICKET_NORMAL_STREAK_FOR_CLOSE = 3
OPERATOR_INPUT_FILE = os.path.join(OUTPUT_DIR, "operator_confirmation_queue.csv")
PROBLEM_TANK_HISTORY_FILE = os.path.join(OUTPUT_DIR, "problem_tank_history.csv")
ACTION_HISTORY_FILE = os.path.join(OUTPUT_DIR, "action_history.csv")

# Current owner is expressed as a role, not copied blindly from historical PIC.
OWNER_ROLE_MAP = {
    "ROT": "Reliability / Rotating Equipment",
    "ELE": "Electrical / Reliability",
    "STA": "Process / Static Equipment",
    "INS": "Instrumentation / Reliability",
}

# Baseline / evaluation
BASELINE_DAYS = 30
EVAL_HOURS = 24
INCIDENT_EXCLUSION_HOURS = 24
MIN_BASELINE_ROWS_HOURLY = 72
MIN_BASELINE_ROWS_WEEKLY = 8

# Data quality
SHORT_GAP_INTERPOLATION_LIMIT = 2   # max 2 consecutive samples
HAMPEL_WINDOW = 7
HAMPEL_N_SIGMA = 3.0

# PCA-MSPC
PCA_EXPLAINED_VARIANCE_TARGET = 0.90
MSPC_WATCH_QUANTILE = 0.95
MSPC_ALARM_QUANTILE = 0.99
EPS = 1e-12

# EWMA
EWMA_LAMBDA = 0.20
EWMA_L_WATCH = 2.5
EWMA_L_ALARM = 3.0

# Forecast
HOURLY_FORECAST_HOURS = 72       # plot = 3 hari
HOURLY_TTT_HORIZON_HOURS = 168   # decision horizon = 7 hari
WEEKLY_FORECAST_WEEKS = 4
HOURLY_VALIDATION_HOLDOUT = 24
WEEKLY_VALIDATION_HOLDOUT = 4

# Similar incident / CBR
TOP_K_SIMILAR = 5
TOP_K_RCA_DISPLAY = 3

# Visualization
HOURLY_PLOT_DAYS = 7
WEEKLY_PLOT_MONTHS = 6
SINGLE_PANE_LINE_DAYS = 30

# Generic hourly channels available in workbook
HOURLY_SUFFIXES = ["FEED", "DISP", "VIB", "TEMP", "AMP"]
DEFAULT_PIC = "REL-05"

# Severity order for deterministic prioritization
STATE_RANK = {"NORMAL": 0, "WATCH": 1, "ALARM": 2, "TRIP": 3}
NON_OBSERVABLE_STATES = {"DATA_GAP", "NOT_OBSERVABLE"}
PRIORITY_RANK = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}

# Business-rule criticality, reviewable by the plant owner. It does not represent a failure probability.
ASSET_CRITICALITY = {
    "PU-2101B": "HIGH",
    "KO-3201": "HIGH",
    "PM-4405B": "MEDIUM",
    "HE-3301": "HIGH",
    "BL-5702": "MEDIUM",
}
CRITICALITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

# Proposed decision matrix (NOT a probability model)
ACTION_PRIORITY_MATRIX = {
    "NORMAL": {"C1": "P4", "C2": "P4", "C3": "P4", "C4": "P4"},
    "WATCH":  {"C1": "P4", "C2": "P3", "C3": "P2", "C4": "P2"},
    "ALARM":  {"C1": "P3", "C2": "P2", "C3": "P1", "C4": "P1"},
    "TRIP":   {"C1": "P1", "C2": "P1", "C3": "P1", "C4": "P1"},
}

# Explicit mapping only for variables that the case data defines as equivalent
# to Equipment Limits parameters. Parameters unavailable in hourly data use
# weekly-aligned context for plotting and are never treated as actual hourly measurements.
ASSET_CONFIGS = [
    {
        "tag_number": "PU-2101B",
        "core_mode": "hourly",
        "hourly_param_map": {
            "Overall Vibration": "VIB",
            "Discharge Pressure": "DISP",
            "Bearing Temp": "TEMP",
        },
    },
    {
        "tag_number": "KO-3201",
        "core_mode": "hourly",
        "hourly_param_map": {
            # The case dataset shows a VIB scale of approximately 25-75, consistent with
            # the Equipment Limits DE Radial Vibration scale in micrometres, although the
            # Tag Dictionary labels it as MM/S. This override is explicit rather than silent.
            "DE Radial Vibration": "VIB",
            "Bearing Metal Temp": "TEMP",
        },
        "unit_override_note": {
            "DE Radial Vibration": (
                "The hourly VIB label in the Tag Dictionary is MM/S, but the case values "
                "follow the micrometre scale used by Equipment Limits; this is treated "
                "sebagai case-specific unit-label inconsistency."
            )
        },
    },
    {
        "tag_number": "PM-4405B",
        "core_mode": "hourly",
        "hourly_param_map": {
            "Motor DE Bearing Temp": "TEMP",
            "Motor Vibration": "VIB",
            "Motor Ampere": "AMP",
        },
    },
    {
        "tag_number": "HE-3301",
        "core_mode": "weekly",
        "hourly_param_map": {},
        "known_data_issue": (
            "HE-3301 generic hourly FEED/DISP/TEMP/VIB/AMP are preserved as DCS covariates. "
            "They are never relabeled as Tube-side dP/Heat Duty/Cold Outlet Temp directly; "
            "validated indirect models convert them to engineering-parameter estimates, while physics models still require verified stream/tap identities."
        ),
    },
    {
        "tag_number": "BL-5702",
        "core_mode": "hourly",
        "hourly_param_map": {
            "Overall Vibration": "VIB",
            "Bearing Temp": "TEMP",
        },
    },
]


# ==============================================================================
# UTILITIES
# ==============================================================================
def log(msg=""):
    print(msg)


def detail_log(msg=""):
    """Print technical details only when VERBOSE_CONSOLE=True."""
    if VERBOSE_CONSOLE:
        print(msg)


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def workbook_sheet(source, sheet_name):
    """Return a defensive copy from an in-memory workbook dict or an open ExcelFile."""
    if isinstance(source, dict):
        if sheet_name not in source:
            raise KeyError(sheet_name)
        return source[sheet_name].copy(deep=True)
    return pd.read_excel(source, sheet_name=sheet_name)


def workbook_sheet_names(source):
    return set(source.keys()) if isinstance(source, dict) else set(source.sheet_names if isinstance(source, pd.ExcelFile) else pd.ExcelFile(source).sheet_names)


def safe_float(x, default=np.nan):
    try:
        return float(x)
    except Exception:
        return default


def normalize_text(value):
    s = "" if pd.isna(value) else str(value)
    s = s.replace("\n", " ").replace("\r", " ")
    s = s.lower()
    s = re.sub(r"[^a-z0-9%]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def extract_plant_code(value):
    s = "" if pd.isna(value) else str(value)
    m = re.search(r"\(([A-Za-z0-9_-]+)\)", s)
    if m:
        return m.group(1).upper()
    return s.strip().upper()


def metadata_to_dict(df_meta):
    out = {}
    if df_meta is None or df_meta.empty:
        return out
    for _, row in df_meta.iterrows():
        k = str(row.get("Parameter", "")).strip()
        if k and k not in out:
            out[k] = row.get("Value", np.nan)
    return out


def get_fla(df_tags):
    if df_tags is None or df_tags.empty or "PI Tag" not in df_tags.columns:
        return 150.0
    mask = df_tags["PI Tag"].astype(str).str.upper().str.endswith("_AMP")
    row = df_tags[mask]
    if row.empty:
        return 150.0
    v = pd.to_numeric(row["typicalvalue"], errors="coerce").dropna()
    return float(v.iloc[0]) if not v.empty else 150.0


def state_max(*states):
    """Return the most severe observable state; never silently convert a pure data gap to NORMAL."""
    raw = [str(s) for s in states if s is not None]
    ranked = [s for s in raw if s in STATE_RANK]
    if ranked:
        return max(ranked, key=lambda s: STATE_RANK[s])
    if any(s == "DATA_GAP" for s in raw):
        return "DATA_GAP"
    if any(s == "NOT_OBSERVABLE" for s in raw):
        return "NOT_OBSERVABLE"
    return "DATA_GAP"


def condition_state_color(state):
    return {
        "NORMAL": "tab:green",
        "WATCH": "goldenrod",
        "ALARM": "tab:orange",
        "TRIP": "tab:red",
    }.get(state, "tab:gray")


def priority_text(priority):
    return {
        "P1": "Immediate / urgent intervention",
        "P2": "High-priority planned intervention",
        "P3": "Scheduled follow-up",
        "P4": "Routine monitoring",
    }.get(priority, "Routine monitoring")


def structured_list_to_text(items, preferred_keys=None):
    """Safely serialize strings/dicts/lists for CSV, Excel and Streamlit tables.

    RCA evidence objects are intentionally structured dictionaries.  Export code must
    never assume these collections contain only strings.  ``preferred_keys`` keeps the
    human-readable field first while preserving unexpected structured content for audit.
    """
    if items is None:
        return ""
    if not isinstance(items, (list, tuple)):
        items = [items]
    preferred_keys = tuple(preferred_keys or ())
    out = []
    for item in items:
        if item in (None, ""):
            continue
        if isinstance(item, dict):
            primary = None
            for key in preferred_keys:
                value = item.get(key)
                if value not in (None, ""):
                    primary = str(value)
                    break
            if primary is not None:
                # Preserve useful qualifiers without dumping raw Python dict syntax.
                qualifiers = []
                for key in ("State", "Parameter", "Evidence", "Status", "Source", "PIC", "Owner", "SLA"):
                    value = item.get(key)
                    if value not in (None, "") and str(value) != primary:
                        qualifiers.append(f"{key}={value}")
                out.append(primary + (f" [{', '.join(qualifiers)}]" if qualifiers else ""))
            else:
                parts = [f"{k}={v}" for k, v in item.items() if v not in (None, "", [], {}) and not str(k).startswith('_')]
                if parts:
                    out.append(" | ".join(parts))
        elif isinstance(item, (list, tuple)):
            nested = structured_list_to_text(item, preferred_keys=preferred_keys)
            if nested:
                out.append(nested)
        else:
            out.append(str(item))
    return "; ".join(out)


def action_list_to_text(actions):
    """Serialize Problem-Tank actions safely while keeping the action plan readable."""
    return structured_list_to_text(actions, preferred_keys=("Plan", "Action", "Recommendation"))


def clip01(x):
    return float(np.clip(x, 0.0, 1.0))



# ==============================================================================
# OPERATOR-RCA UTILITIES
# ==============================================================================
def consecutive_true_count(mask):
    """Count consecutive True values ending at the latest observation."""
    count = 0
    for v in list(pd.Series(mask).fillna(False).astype(bool))[::-1]:
        if not v:
            break
        count += 1
    return count


def persistent_state(raw_states, window, min_count):
    """Persistence gate for statistical signals; engineering TRIP states do not use this gate."""
    seq = [s for s in list(raw_states)[-window:] if s in STATE_RANK]
    if not seq:
        return "NORMAL"
    current = seq[-1]
    if current == "NORMAL":
        return "NORMAL"
    alarm_like = sum(STATE_RANK.get(x, 0) >= STATE_RANK["ALARM"] for x in seq)
    watch_like = sum(STATE_RANK.get(x, 0) >= STATE_RANK["WATCH"] for x in seq)
    if current in {"ALARM", "TRIP"} and alarm_like >= min_count:
        return "ALARM"
    if watch_like >= min_count:
        return "WATCH"
    return "NORMAL"


def alarm_deviation(value, lim):
    if pd.isna(value):
        return np.nan
    return value - lim["alarm"] if lim["direction"] == "high" else lim["alarm"] - value


def latest_episode_start(times, mask):
    times = pd.Series(times).reset_index(drop=True)
    mask = pd.Series(mask).fillna(False).astype(bool).reset_index(drop=True)
    if mask.empty or not mask.iloc[-1]:
        return pd.NaT
    i = len(mask) - 1
    while i > 0 and mask.iloc[i - 1]:
        i -= 1
    return pd.Timestamp(times.iloc[i])


def detect_runtime_mode(assets):
    latest = [a["df_hourly"]["Timestamp"].max() for a in assets if not a["df_hourly"].empty]
    ref = max(latest) if latest else pd.NaT
    mode = RUNTIME_MODE.upper()
    if mode not in {"LIVE", "SNAPSHOT"}:
        raise ValueError("RUNTIME_MODE must be LIVE or SNAPSHOT")
    return {"mode": mode, "reference_time": ref,
            "wall_clock_lag_hours": (pd.Timestamp.now()-ref).total_seconds()/3600 if pd.notna(ref) else np.nan}


def operating_context(asset, runtime_mode):
    df = asset.get("df_hourly", pd.DataFrame())
    if df.empty:
        return {"status": "NO_DATA", "latest_time": pd.NaT, "age_hours": np.nan, "diagnosis_allowed": False, "reason": "No hourly data"}
    row = df.iloc[-1]
    ts = pd.Timestamp(row["Timestamp"])
    if asset.get("cfg", {}).get("core_mode") == "weekly":
        weekly = asset.get("df_weekly", pd.DataFrame())
        params = asset["df_limits"]["Parameter"].astype(str).tolist()
        missing = weekly.empty or any(p not in weekly or pd.isna(weekly.iloc[-1].get(p)) for p in params)
        if missing:
            return {"status":"DATA_GAP", "latest_time":ts, "age_hours":np.nan,
                    "diagnosis_allowed":False, "reason":"Latest weekly engineering measurements incomplete"}
    run_status = str(row.get("RUN_STATUS", "UNKNOWN")).strip().upper()
    amp = safe_float(row.get("AMP"), np.nan)
    age_h = (pd.Timestamp.now() - ts).total_seconds() / 3600.0

    if runtime_mode.get("mode") == "LIVE" and age_h > LIVE_FRESHNESS_HOURS:
        return {"status": "STALE", "latest_time": ts, "age_hours": age_h, "diagnosis_allowed": False,
                "reason": f"Latest hourly data is {age_h:.1f} h old"}
    if runtime_mode.get("mode") == "LIVE" and asset.get("cfg", {}).get("core_mode") == "weekly":
        w = asset.get("df_weekly", pd.DataFrame())
        wtime = pd.to_datetime(w.get("Date"), errors="coerce").max() if not w.empty else pd.NaT
        if pd.isna(wtime):
            return {"status": "STALE_WEEKLY", "latest_time": ts, "age_hours": age_h, "diagnosis_allowed": False,
                    "reason": "Weekly core-condition data unavailable"}
        age_d = (pd.Timestamp.now().normalize() - pd.Timestamp(wtime).normalize()).days
        if age_d > LIVE_WEEKLY_FRESHNESS_DAYS:
            return {"status": "STALE_WEEKLY", "latest_time": ts, "age_hours": age_h, "diagnosis_allowed": False,
                    "reason": f"Latest weekly core-condition data is {age_d} days old"}
    if run_status != "ON":
        return {"status": "OFF", "latest_time": ts, "age_hours": age_h, "diagnosis_allowed": False,
                "reason": f"RUN_STATUS={run_status}"}
    mapped_suffixes = set(asset.get("cfg", {}).get("hourly_param_map", {}).values())
    use_amp_running_gate = ("AMP" in mapped_suffixes) and ("AMP" in df.columns)
    if use_amp_running_gate and pd.isna(amp):
        return {"status": "DATA_GAP", "latest_time": ts, "age_hours": age_h, "diagnosis_allowed": False,
                "reason": "Validated motor-current channel is missing"}
    if use_amp_running_gate and amp <= 0.10 * asset.get("fla", 150.0):
        return {"status": "NOT_RUNNING", "latest_time": ts, "age_hours": age_h, "diagnosis_allowed": False,
                "reason": "RUN_STATUS is ON but validated motor current is below 10% FLA"}

    # Latest critical mapped channels may not be silently imputed for operator diagnosis.
    missing_critical = []
    for _, suffix in asset.get("cfg", {}).get("hourly_param_map", {}).items():
        if suffix in df.columns and pd.isna(row.get(suffix)):
            missing_critical.append(suffix)
    if missing_critical:
        return {"status": "DATA_GAP", "latest_time": ts, "age_hours": age_h, "diagnosis_allowed": False,
                "reason": "Missing latest critical channels: " + ", ".join(missing_critical)}
    return {"status": "RUNNING", "latest_time": ts, "age_hours": age_h, "diagnosis_allowed": True, "reason": ""}


def load_operator_inputs():
    """Load the latest human follow-up input for each asset.

    This file is a current-input queue, not the complete workflow audit trail.
    Historical workflow events are stored separately in ``action_history.csv``.
    """
    cols = [
        "Asset", "Decision", "Operator", "Visible Leakage", "Abnormal Noise",
        "Abnormal Vibration", "Local Temperature Confirmed", "Field Observation",
        "Comment", "Updated At", "Owner Role", "Action Status"
    ]
    if os.path.exists(OPERATOR_INPUT_FILE):
        try:
            df = pd.read_csv(OPERATOR_INPUT_FILE, dtype=str)
            for c in cols:
                if c not in df.columns:
                    df[c] = ""
            df = df.fillna("")
            for c in cols:
                df[c] = df[c].astype(object)
            return df[cols].copy()
        except Exception:
            pass
    df = pd.DataFrame(columns=cols)
    for c in cols:
        df[c] = df[c].astype(object)
    return df


def get_operator_input(operator_df, tag):
    if operator_df is None or operator_df.empty:
        return {}
    x = operator_df[operator_df["Asset"].astype(str) == str(tag)]
    if x.empty:
        return {}
    row = x.iloc[-1]
    return {c: ("" if pd.isna(row.get(c, "")) else row.get(c, "")) for c in operator_df.columns}


def load_action_history():
    """Load the append-only follow-up audit trail."""
    cols = [
        "Event Time", "Ticket ID", "Asset", "Update Source", "Event Type",
        "Previous Ticket State", "New Ticket State", "Previous Action Status",
        "New Action Status", "Operator Decision", "Operator", "Owner Role",
        "Field Observation", "Comment"
    ]
    if os.path.exists(ACTION_HISTORY_FILE):
        try:
            df = pd.read_csv(ACTION_HISTORY_FILE, dtype=str)
            for c in cols:
                if c not in df.columns:
                    df[c] = ""
            df = df.fillna("")
            for c in cols:
                df[c] = df[c].astype(object)
            return df[cols].copy()
        except Exception:
            pass
    df = pd.DataFrame(columns=cols)
    for c in cols:
        df[c] = df[c].astype(object)
    return df


def append_action_history(ticket_id, asset, update_source, event_type,
                          previous_ticket_state="", new_ticket_state="",
                          previous_action_status="", new_action_status="",
                          operator_decision="", operator="", owner_role="",
                          field_observation="", comment=""):
    """Append one immutable workflow event to ``action_history.csv``."""
    ensure_output_dir()
    df = load_action_history()
    row = {
        "Event Time": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Ticket ID": str(ticket_id or ""), "Asset": str(asset or ""),
        "Update Source": str(update_source or "SYSTEM").upper(),
        "Event Type": str(event_type or "UPDATE").upper(),
        "Previous Ticket State": str(previous_ticket_state or ""),
        "New Ticket State": str(new_ticket_state or ""),
        "Previous Action Status": str(previous_action_status or ""),
        "New Action Status": str(new_action_status or ""),
        "Operator Decision": str(operator_decision or ""),
        "Operator": str(operator or ""), "Owner Role": str(owner_role or ""),
        "Field Observation": str(field_observation or ""), "Comment": str(comment or ""),
    }
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(ACTION_HISTORY_FILE, index=False)
    return row


def get_workflow_storage_version():
    """Return a deterministic revision key for Streamlit cache invalidation."""
    vals = []
    for path in (OPERATOR_INPUT_FILE, PROBLEM_TANK_HISTORY_FILE, ACTION_HISTORY_FILE):
        try:
            vals.append(Path(path).stat().st_mtime_ns)
        except Exception:
            vals.append(0)
    return int(max(vals) if vals else 0)


def save_operator_update(asset, decision="", operator="", comment="", owner_role="", action_status="",
                         field_observation="", visible_leakage="", abnormal_noise="", abnormal_vibration="",
                         local_temperature_confirmed=""):
    """Save the latest operator follow-up and append an immutable audit event.

    ``Action Status`` describes progress of the human follow-up task. It is deliberately
    separate from the engine-controlled ``Ticket State`` and from the analytical
    equipment condition (Normal/Watch/Alarm/Trip).
    """
    allowed_decisions = {"", "ACKNOWLEDGE", "CONFIRM_RCA", "REJECT_RCA", "REQUEST_REVIEW", "CLOSE_TICKET"}
    allowed_action_status = {"", "NOT_STARTED", "ACKNOWLEDGED", "IN_PROGRESS", "PENDING_VERIFICATION", "COMPLETED"}
    decision = str(decision or "").strip().upper()
    action_status = str(action_status or "").strip().upper()
    if decision not in allowed_decisions:
        raise ValueError(f"Unsupported operator decision: {decision}")
    if action_status not in allowed_action_status:
        raise ValueError(f"Unsupported action status: {action_status}")

    # Capture the current ticket/workflow state before the update for the audit trail.
    hist = load_problem_tank_history()
    active = _active_ticket_row(hist, asset) if '_active_ticket_row' in globals() else None
    ticket_id = active.get("Ticket ID", "") if active is not None else ""
    previous_ticket_state = active.get("Ticket State", active.get("Status", "")) if active is not None else ""
    previous_action_status = active.get("Action Status", "") if active is not None else ""

    df = load_operator_inputs()
    row = {
        "Asset": str(asset), "Decision": decision, "Operator": str(operator or "").strip(),
        "Visible Leakage": str(visible_leakage or "").strip(), "Abnormal Noise": str(abnormal_noise or "").strip(),
        "Abnormal Vibration": str(abnormal_vibration or "").strip(),
        "Local Temperature Confirmed": str(local_temperature_confirmed or "").strip(),
        "Field Observation": str(field_observation or "").strip(), "Comment": str(comment or "").strip(),
        "Updated At": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Owner Role": str(owner_role or "").strip(), "Action Status": action_status,
    }
    if df.empty or not df["Asset"].astype(str).eq(str(asset)).any():
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    else:
        idx = df.index[df["Asset"].astype(str).eq(str(asset))][-1]
        for k, v in row.items():
            df.loc[idx, k] = v
    ensure_output_dir()
    df.to_csv(OPERATOR_INPUT_FILE, index=False)

    append_action_history(
        ticket_id=ticket_id, asset=asset, update_source="OPERATOR", event_type="FOLLOW_UP_UPDATE",
        previous_ticket_state=previous_ticket_state, new_ticket_state=previous_ticket_state,
        previous_action_status=previous_action_status, new_action_status=action_status or previous_action_status,
        operator_decision=decision, operator=operator, owner_role=owner_role,
        field_observation=field_observation, comment=comment,
    )
    return row

def field_observation_text(operator_input):
    if not operator_input:
        return ""
    parts = []
    for key, label in [
        ("Visible Leakage", "visible leakage"),
        ("Abnormal Noise", "abnormal noise"),
        ("Abnormal Vibration", "operator-observed abnormal vibration"),
        ("Local Temperature Confirmed", "local temperature confirmation"),
    ]:
        v = str(operator_input.get(key, "")).strip().upper()
        if v in {"Y", "YES", "TRUE", "1"}:
            parts.append(label)
    note = str(operator_input.get("Field Observation", "")).strip()
    if note:
        parts.append(note)
    return " ".join(parts)


def suggested_owner_role(asset):
    disc = str(asset.get("meta", {}).get("Discipline", "")).strip().upper()
    return OWNER_ROLE_MAP.get(disc, "Reliability / Maintenance")


def priority_sla(priority):
    return {"P1": "Immediate / <2 h", "P2": "<24 h", "P3": "<7 d", "P4": "Routine monitoring"}.get(priority, "Review")


def blank_rca_evidence():
    return {
        "matched_ar": None,
        "root_cause": None,
        "problem_statement": None,
        "priority_causes": [],
        "verification_4p": [],
        "verification_4m": [],
        "capa": [],
        "candidates": [],
        "current_measured_evidence": [],
        "current_statistical_evidence": [],
        "historical_verified_evidence": [],
        "systemic_hypotheses": [],
        "evidence_strength": "NOT_TRIGGERED",
    }


def build_trigger_explanation(condition_result):
    triggers = []
    for p, d in condition_result.get("engineering", {}).items():
        if d.get("state") in {"ALARM", "TRIP"}:
            triggers.append({
                "type": "ENGINEERING_LIMIT",
                "parameter": p,
                "value": d.get("value"),
                "unit": d.get("unit", ""),
                "state": d.get("state"),
                "alarm": d.get("alarm"),
                "trip": d.get("trip"),
                "direction": d.get("direction"),
                "deviation_from_alarm": d.get("deviation_from_alarm"),
                "first_breach": d.get("first_alarm_breach"),
                "consecutive": d.get("alarm_consecutive", 0),
            })
        elif d.get("ewma_state") in {"WATCH", "ALARM"}:
            triggers.append({
                "type": "EWMA_DRIFT",
                "parameter": p,
                "value": d.get("value"),
                "unit": d.get("unit", ""),
                "state": d.get("ewma_state"),
                "alarm": d.get("alarm"),
                "trip": d.get("trip"),
                "direction": d.get("direction"),
                "consecutive": d.get("ewma_abnormal_count", 0),
            })
    if condition_result.get("stat_state") in {"WATCH", "ALARM"}:
        triggers.append({
            "type": "MULTIVARIATE_ANOMALY",
            "parameter": None,
            "state": condition_result.get("stat_state"),
            "condition_index": condition_result.get("condition_index"),
            "contributors": condition_result.get("contributors", []),
            "consecutive": condition_result.get("stat_abnormal_count", 0),
        })
    if condition_result.get("virtual_decision_eligible") and HS_ALLOW_ESTIMATED_WATCH:
        seen = set()
        for target, entry in condition_result.get("virtual_sensors", {}).get("entries", {}).items():
            if target not in condition_result.get("virtual_sensors", {}).get("watch_names", []) or entry["name"] in seen:
                continue
            seen.add(entry["name"])
            triggers.append({"type":"VIRTUAL_ADVISORY", "parameter":entry["name"], "state":"WATCH",
                             "value":entry["value"], "unit":entry["unit"], "source_kind":entry["kind"],
                             "reason":entry["reason"], "target":target})
    order = {"ENGINEERING_LIMIT": 0, "EWMA_DRIFT": 1, "MULTIVARIATE_ANOMALY": 2, "VIRTUAL_ADVISORY": 3}
    return sorted(triggers, key=lambda x: (order.get(x["type"], 9), -STATE_RANK.get(x.get("state"), 0)))


def trigger_short_text(trigger_list):
    if not trigger_list:
        return "No active trigger"
    t = trigger_list[0]
    if t["type"] == "ENGINEERING_LIMIT":
        return f"{t['parameter']} {t['state']}"
    if t["type"] == "EWMA_DRIFT":
        return f"{t['parameter']} {t['state']} drift"
    if t["type"] == "VIRTUAL_ADVISORY":
        return "Virtual/proxy WATCH"
    return f"MSPC {t.get('state', 'WATCH')}"


def measurement_groups(condition_result):
    """Group observable measurements to match current evidence against 4P/Priority Matrix factors."""
    alias = {
        "pressure": ["pressure", "npsh", "suction", "discharge", "differential", "dp"],
        "flow": ["flow", "flush", "feed rate", "rate"],
        "vibration": ["vibration", "radial", "harmonic", "2x"],
        "temperature": ["temperature", "temp", "overheat", "overheating", "bearing temp", "winding"],
        "current": ["ampere", "current", "motor amp", "amps"],
        "oil": ["oil", "water content", "lubrication", "grease"],
        "coupling": ["coupling", "alignment", "offset", "misalignment", "soft foot"],
        "heat": ["heat duty", "duty", "outlet temp"],
        "composition": ["heavy ends", "heavy-ends", "composition"],
    }
    out = {}
    for p, d in condition_result.get("engineering", {}).items():
        txt = normalize_text(p)
        state = state_max(d.get("state", "NORMAL"), d.get("ewma_state", "NORMAL"))
        for g, kws in alias.items():
            if any(normalize_text(k) in txt for k in kws):
                old = out.get(g, "NORMAL")
                out[g] = state_max(old, state)
    # Generic PCA channels are observable, but cannot prove an engineering limit breach.
    suffix_map = {"VIB": "vibration", "TEMP": "temperature", "DISP": "pressure", "FEED": "flow", "AMP": "current"}
    for c, z in condition_result.get("contributors", []):
        g = suffix_map.get(str(c).upper())
        if g and g not in out:
            out[g] = "WATCH" if abs(z) >= 1.0 else "NORMAL"
    return out, alias


def match_factor_to_current(factor_text, condition_result):
    txt = normalize_text(factor_text)
    # Systemic/process-management failures cannot be proven by a sensor group.
    if any(x in txt for x in ["no ", "not monitored", "not trended", "absence", "dashboard", "trigger", "procedure"]):
        return "NOT_OBSERVABLE", []
    aliases = {
        "tube side dp": ["tube side dp", "tube side d p"],
        "heat duty": ["heat duty", "duty"],
        "feed heavy ends": ["heavy ends"],
        "cold outlet temp": ["cold outlet", "outlet temperature"],
        "seal flush flow": ["seal flush", "flush flow"],
        "lube oil water content": ["water content", "water in oil", "oil water"],
        "coupling offset": ["coupling offset", "misalignment", "alignment"],
    }
    matched = []
    for p, d in condition_result.get("engineering", {}).items():
        pn = normalize_text(p)
        keys = aliases.get(pn, [pn])
        if "vibration" in pn: keys = ["vibration", "radial"]
        if "bearing" in pn and "temp" in pn: keys = ["bearing temp", "bearing metal temp", "overheat"]
        if "ampere" in pn: keys = ["ampere", "motor current", "overcurrent"]
        if any(k in txt for k in keys):
            matched.append((p,d))
    if not matched:
        return "NOT_OBSERVABLE", []
    expected = "low" if any(x in txt for x in ["below", "low ", "loss of", "fell", "drop"]) else "high" if any(x in txt for x in ["above", "high", "overheat", "exceed"]) else None
    for p,d in matched:
        abnormal = state_max(d.get("state","NORMAL"),d.get("ewma_state","NORMAL")) != "NORMAL"
        if abnormal and expected is not None and expected == d.get("direction"):
            return "CONSISTENT", [p]
    return "NOT_SUPPORTED_CURRENTLY", [p for p,d in matched]


def evidence_strength_label(case_similarity, consistent_n, observable_n, candidate_gap=np.nan):
    if consistent_n == 0:
        return "UNSUPPORTED_CURRENTLY" if observable_n else "UNVERIFIED"
    support = consistent_n / max(observable_n, 1)
    if case_similarity >= 0.55 and support >= 0.5 and (pd.isna(candidate_gap) or candidate_gap >= 0.05):
        return "HIGH"
    if case_similarity >= 0.35 and support >= 0.5:
        return "MEDIUM"
    return "LOW"


def rca_hypothesis_label(evidence_strength):
    """Return cautious language that reflects the evidentiary strength of an RCA match."""
    strength = str(evidence_strength or "UNVERIFIED").upper()
    if strength == "HIGH":
        return "Leading RCA hypothesis"
    if strength == "MEDIUM":
        return "Plausible RCA hypothesis"
    if strength == "LOW":
        return "Historically similar failure mechanism"
    if strength == "UNSUPPORTED_CURRENTLY":
        return "Historical mechanism not currently supported by available evidence"
    if strength == "UNVERIFIED":
        return "Historical mechanism requiring independent verification"
    return "RCA hypothesis"


def historical_capa_is_actionable(evidence_strength):
    """Historical CAPA may become a current reference action only with MEDIUM/HIGH evidence."""
    return str(evidence_strength or "").upper() in {"MEDIUM", "HIGH"}


def build_discriminating_checks(asset, condition_result, rca_evidence):
    """Return asset-specific checks that can distinguish the leading hypothesis from alternatives.

    These are verification checks, not diagnoses. They are intentionally limited to signals or
    inspections that are meaningful for the configured asset and common competing mechanisms.
    """
    tag = asset.get("tag_number", "")
    checks = {
        "PU-2101B": [
            "verify seal-flush flow and pressure against the applicable operating minimum",
            "check suction pressure / NPSH margin and recent feed swings for cavitation evidence",
            "inspect for seal leakage, cavitation noise, and abnormal vibration locally",
        ],
        "KO-3201": [
            "verify lube-oil water content and oil-supply pressure from an independent or laboratory measurement",
            "check lube-oil temperature, cooler condition, and evidence of water ingress",
            "review vibration trend/spectrum and bearing condition for oil-film or mechanical distress",
        ],
        "PM-4405B": [
            "verify motor load/current and, where available, phase-current imbalance",
            "check bearing lubrication condition and local bearing temperature",
            "review vibration spectrum/alignment to distinguish lubrication, imbalance, misalignment, and electrical causes",
        ],
        "HE-3301": [
            "confirm tube-side differential pressure with verified pressure taps",
            "confirm inlet/outlet temperatures and flow used for heat-duty assessment",
            "check fouling indicators and feed composition before attributing performance loss to a specific mechanism",
        ],
        "BL-5702": [
            "verify overall vibration locally and review the 2X component if available",
            "check coupling alignment/offset and bearing temperature",
            "inspect for imbalance, looseness, or misalignment before assigning a mechanical cause",
        ],
    }.get(tag, [])
    return checks


# ==============================================================================
# PHASE -1: DATA SOURCE MAPPING & QUALITY GATE
# ==============================================================================
def required_sheets_for_asset(tag):
    return [
        f"{tag} Metadata",
        f"{tag} Performance Weekly",
        f"{tag} Production Data Hourly",
        f"{tag} Tag Dictionary",
        f"{tag} Equipment Limits",
    ]


def audit_workbook(workbook):
    """Hard gate using the already-open ExcelFile; FAIL blocks asset diagnosis."""
    detail_log("=" * 110)
    detail_log("[PHASE -1] DATA SOURCE MAPPING & DATA-QUALITY GATE")
    detail_log("=" * 110)
    available = workbook_sheet_names(workbook)
    rows = []
    required_global = ["Incident Record", "RCA Header", "RCA Priority Matrix", "RCA 4P Verification", "RCA 4M Verification", "RCA CAPA Actions"]
    missing_global = [x for x in required_global if x not in available]
    if missing_global:
        detail_log(f"Global RCA tables missing: {missing_global}")

    for cfg in ASSET_CONFIGS:
        tag = cfg["tag_number"]
        missing_sheets = [x for x in required_sheets_for_asset(tag) if x not in available]
        if missing_sheets:
            rows.append({"Asset": tag, "Status": "FAIL", "Issue": f"Missing sheets: {missing_sheets}"})
            continue
        df_h = workbook_sheet(workbook, f"{tag} Production Data Hourly")
        required_cols = ["Timestamp", "RUN_STATUS"]
        missing_cols = [c for c in required_cols if c not in df_h.columns]
        source_upper = {str(c).upper() for c in df_h.columns}
        missing_mapped = []
        for param, suffix in cfg.get("hourly_param_map", {}).items():
            expected = f"{tag.replace('-', '')}_{suffix}".upper()
            if expected not in source_upper and not any(str(c).upper().endswith("_" + suffix) for c in df_h.columns):
                missing_mapped.append(f"{param}->{suffix}")
        ts = pd.to_datetime(df_h.get("Timestamp"), errors="coerce") if "Timestamp" in df_h.columns else pd.Series(dtype="datetime64[ns]")
        n_bad_ts = int(ts.isna().sum()) if len(ts) else len(df_h)
        n_dup = int(ts.duplicated().sum()) if len(ts) else 0
        miss = int(df_h.isna().sum().sum())
        prefix_expected = tag.replace("-", "").upper()
        sensor_cols = [c for c in df_h.columns if "_" in str(c)]
        prefixes = sorted({str(c).upper().split("_")[0] for c in sensor_cols if str(c).upper().endswith(tuple("_" + x for x in HOURLY_SUFFIXES))})
        prefix_ok = (not prefixes) or (prefix_expected in prefixes)

        weekly = workbook_sheet(workbook, f"{tag} Performance Weekly")
        limits_frame = workbook_sheet(workbook, f"{tag} Equipment Limits")
        semantic_issues = []; weekly_hard_fail = False
        if "Date" not in weekly:
            weekly_hard_fail = True; semantic_issues.append("Weekly Date column missing")
        else:
            wt = pd.to_datetime(weekly["Date"], errors="coerce")
            if wt.isna().any() or wt.duplicated().any():
                weekly_hard_fail = True; semantic_issues.append("Invalid/duplicate weekly dates")
            gaps = wt.sort_values().diff().dropna()
            if not gaps.eq(pd.Timedelta(days=7)).all(): semantic_issues.append("Weekly cadence has gaps")
        required_limits = {"Parameter", "Unit", "Alarm Limit", "Trip Limit"}
        if not required_limits.issubset(limits_frame.columns):
            weekly_hard_fail = True; semantic_issues.append("Missing Equipment Limits columns")
        else:
            av = pd.to_numeric(limits_frame["Alarm Limit"], errors="coerce")
            tv = pd.to_numeric(limits_frame["Trip Limit"], errors="coerce")
            if av.isna().any() or tv.isna().any() or av.eq(tv).any():
                weekly_hard_fail = True; semantic_issues.append("Invalid or equal alarm/trip limits")
            if "Date" in weekly:
                cleaned = clean_weekly_frame(weekly, limits_frame)
                missing_params = [p for p in limits_frame["Parameter"] if p not in cleaned or cleaned[p].isna().any()]
                if missing_params: semantic_issues.append(f"Missing weekly parameter observations: {missing_params}")
        if cfg.get("unit_override_note"):
            semantic_issues.append("KO vibration unit override UNVERIFIED; confirm micrometre vs mm/s with data owner")
        if cfg.get("known_data_issue"): semantic_issues.append(cfg["known_data_issue"])
        if len(ts) > 1 and not ts.sort_values().diff().dropna().eq(pd.Timedelta(hours=1)).all(): semantic_issues.append("Hourly calendar cadence has gaps")
        numeric_columns = [c for c in df_h if any(str(c).upper().endswith("_"+v) for v in HOURLY_SUFFIXES)]
        if any(pd.to_numeric(df_h[c].astype(str).str.replace(",","."), errors="coerce").isna().any() for c in numeric_columns):
            semantic_issues.append("Non-numeric/missing sensor values")
        if "RUN_STATUS" in df_h and not df_h["RUN_STATUS"].astype(str).str.upper().isin(["ON","OFF"]).all(): semantic_issues.append("Invalid RUN_STATUS values")
        hard_fail = bool(missing_cols or missing_mapped or n_bad_ts or n_dup or weekly_hard_fail)
        status = "FAIL" if hard_fail else ("CHECK" if (miss or not prefix_ok or missing_global or semantic_issues) else "PASS")
        issues = list(semantic_issues)
        if missing_cols: issues.append(f"missing required columns={missing_cols}")
        if missing_mapped: issues.append(f"missing mapped channels={missing_mapped}")
        if n_bad_ts: issues.append(f"invalid timestamp={n_bad_ts}")
        if n_dup: issues.append(f"duplicate timestamp={n_dup}")
        if miss: issues.append(f"missing cells={miss}")
        if not prefix_ok: issues.append(f"prefix={prefixes}, expected={prefix_expected}")
        if missing_global: issues.append(f"RCA tables missing={missing_global}")
        rows.append({"Asset":tag,"Status":status,"Invalid Timestamp":n_bad_ts,"Duplicate Timestamp":n_dup,"Missing Cells":miss,"Prefix OK":prefix_ok,"Issue":"; ".join(issues)})

    if "Incident Record" in available:
        inc_audit = workbook_sheet(workbook, "Incident Record")
        raw_mech = inc_audit.get("F Mechanism", pd.Series(dtype=object)).map(normalize_text)
        coarse = int(raw_mech.isin(["high","motor","mechanical",""]).sum())
        if coarse:
            for row in rows:
                if row["Status"] == "PASS": row["Status"] = "CHECK"
                row["Issue"] = (row["Issue"] + f"; global mechanism taxonomy: {coarse} coarse labels; derived mapping exported for review").lstrip("; ")
    df_audit = pd.DataFrame(rows)
    ensure_output_dir(); df_audit.to_csv(os.path.join(OUTPUT_DIR,"data_quality_audit.csv"),index=False)
    return df_audit


# ==============================================================================
# DATA LOADING / CLEANING
# ==============================================================================
def detect_and_rename_hourly_columns(df_hourly, tag_number):
    df = df_hourly.copy()
    rename = {}
    prefix_seen = set()

    for suf in HOURLY_SUFFIXES:
        exact_expected = f"{tag_number.replace('-', '')}_{suf}".upper()
        matches = [c for c in df.columns if str(c).upper() == exact_expected]
        if not matches:
            matches = [c for c in df.columns if str(c).upper().endswith("_" + suf)]
        if matches:
            rename[matches[0]] = suf
            prefix_seen.add(str(matches[0]).upper().rsplit("_" + suf, 1)[0])

    df = df.rename(columns=rename)

    rate_cols = [c for c in df.columns if "RATE" in str(c).upper() and str(c).upper() != "RUN_STATUS"]
    if "PLANT_RATE" not in df.columns and rate_cols:
        # Prefer explicit plant rate if available; otherwise first rate column
        preferred = [c for c in rate_cols if "PLANT" in str(c).upper()]
        src = preferred[0] if preferred else rate_cols[0]
        df = df.rename(columns={src: "PLANT_RATE"})

    run_cols = [c for c in df.columns if str(c).upper().replace(" ", "_") == "RUN_STATUS"]
    if run_cols and run_cols[0] != "RUN_STATUS":
        df = df.rename(columns={run_cols[0]: "RUN_STATUS"})

    expected_prefix = tag_number.replace("-", "").upper()
    mismatch = bool(prefix_seen and expected_prefix not in {p.upper() for p in prefix_seen})
    return df, mismatch, prefix_seen


def hampel_flags(series, window=HAMPEL_WINDOW, n_sigma=HAMPEL_N_SIGMA):
    """Offline data-quality flag. Values are NOT automatically replaced."""
    s = pd.to_numeric(series, errors="coerce")
    med = s.rolling(window=window, center=True, min_periods=max(3, window // 2)).median()
    abs_dev = (s - med).abs()
    mad = abs_dev.rolling(window=window, center=True, min_periods=max(3, window // 2)).median()
    robust_sigma = 1.4826 * mad
    flags = (abs_dev > n_sigma * robust_sigma) & (robust_sigma > 0)
    return flags.fillna(False)


def short_gap_interpolate(df, cols, limit=SHORT_GAP_INTERPOLATION_LIMIT):
    out = df.copy()
    for c in cols:
        out[c] = pd.to_numeric(out[c], errors="coerce")
        out[c] = out[c].interpolate(
            method="linear",
            limit=limit,
            limit_direction="both",
            limit_area="inside",
        )
    return out


def clean_weekly_frame(df_weekly_raw, df_limits):
    df = df_weekly_raw.copy()
    if "Date" not in df.columns:
        raise ValueError("Performance Weekly does not contain a Date column.")
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    param_names = df_limits["Parameter"].astype(str).tolist()
    rename = {}
    for param in param_names:
        np_ = normalize_text(param)
        candidates = []
        for c in df.columns:
            if c in ["Week", "Date", "Health Status", "Remark"]:
                continue
            nc = normalize_text(c)
            if nc.startswith(np_) or np_ in nc:
                candidates.append(c)
        if candidates:
            rename[candidates[0]] = param

    df = df.rename(columns=rename)
    for p in param_names:
        if p in df.columns:
            df[p] = pd.to_numeric(df[p], errors="coerce")
    return df


def load_asset_data(workbook, cfg):
    """Load one asset from an already-open workbook. Raw observations are preserved separately."""
    tag = cfg["tag_number"]
    detail_log("\n" + "=" * 110); detail_log(f"[PHASE 0] DATA INGESTION & ROBUST PRE-PROCESSING — {tag}"); detail_log("=" * 110)
    df_limits = workbook_sheet(workbook, f"{tag} Equipment Limits")
    df_tags = workbook_sheet(workbook, f"{tag} Tag Dictionary")
    df_meta = workbook_sheet(workbook, f"{tag} Metadata")
    df_weekly_raw = workbook_sheet(workbook, f"{tag} Performance Weekly")
    df_hourly_raw = workbook_sheet(workbook, f"{tag} Production Data Hourly")
    df_hourly, mismatch, prefix_seen = detect_and_rename_hourly_columns(df_hourly_raw, tag)
    if mismatch: detail_log(f"Prefix mismatch detected: {sorted(prefix_seen)} vs expected {tag.replace('-', '')}")
    df_hourly["Timestamp"] = pd.to_datetime(df_hourly["Timestamp"], errors="coerce")
    df_hourly = df_hourly.dropna(subset=["Timestamp"]).sort_values("Timestamp").drop_duplicates("Timestamp").reset_index(drop=True)
    numeric_cols = [c for c in HOURLY_SUFFIXES + ["PLANT_RATE"] if c in df_hourly.columns]
    for c in numeric_cols: df_hourly[c] = pd.to_numeric(df_hourly[c].astype(str).str.replace(",","."), errors="coerce")
    df_hourly_observed = df_hourly.copy(deep=True)
    for c in [x for x in HOURLY_SUFFIXES if x in df_hourly.columns]: df_hourly[f"{c}_HampelFlag"] = hampel_flags(df_hourly[c])
    df_hourly = short_gap_interpolate(df_hourly, numeric_cols)
    df_hourly["RUN_STATUS"] = df_hourly["RUN_STATUS"].ffill() if "RUN_STATUS" in df_hourly.columns else "UNKNOWN"
    fla = get_fla(df_tags)
    mapped_suffixes = set(cfg.get("hourly_param_map", {}).values())
    use_amp_running_gate = ("AMP" in mapped_suffixes) and ("AMP" in df_hourly.columns)
    run_on = df_hourly["RUN_STATUS"].astype(str).str.strip().str.upper().eq("ON")
    if use_amp_running_gate:
        amp_running = pd.to_numeric(df_hourly["AMP"], errors="coerce").gt(0.10 * fla)
        df_hourly["Is_Running"] = (run_on & amp_running).astype(int)
    else:
        # Generic AMP may remain a covariate, but it is not allowed to redefine
        # equipment running state unless AMP is a validated direct mapping.
        df_hourly["Is_Running"] = run_on.astype(int)
    df_on = df_hourly[df_hourly["Is_Running"]==1].copy().reset_index(drop=True)
    observed_availability = 100.0*df_hourly["Is_Running"].mean() if len(df_hourly) else np.nan
    df_weekly = clean_weekly_frame(df_weekly_raw, df_limits)
    meta = metadata_to_dict(df_meta)
    return {"tag_number":tag,"cfg":cfg,"df_limits":df_limits,"df_tags":df_tags,"df_meta":df_meta,"meta":meta,
            "df_weekly":df_weekly,"df_hourly":df_hourly,"df_hourly_observed":df_hourly_observed,"df_on":df_on,
            "fla":fla,"observed_availability":observed_availability,"_weekly_covariates":{},"_dcs_model_cache":{},"_dcs_trace_cache":{}}


def load_global_tables(workbook):
    df_incident = workbook_sheet(workbook, "Incident Record")
    df_incident = df_incident.rename(columns={"AR No.":"AR No","Pre-Risk":"Pre Risk"})
    for c in ["Downtime (hrs)","Act. Loss (k US$)","Pot. Loss (k US$)","Total Loss (k US$)","Risk Score"]:
        if c in df_incident.columns: df_incident[c] = pd.to_numeric(df_incident[c], errors="coerce")
    if "Date of Occur." in df_incident.columns: df_incident["Date of Occur."] = pd.to_datetime(df_incident["Date of Occur."], errors="coerce")
    df_incident["F Mechanism Raw"] = df_incident["F Mechanism"]
    df_incident["F Mechanism"] = df_incident.apply(canonical_mechanism, axis=1)
    df_incident["Mechanism Normalization"] = np.where(df_incident["F Mechanism"].eq(df_incident["F Mechanism Raw"].map(normalize_text)),
                                                       "normalized source label","rule-derived from incident title; review required")
    df_incident["Incident Key"] = df_incident["AR No"].fillna(df_incident.get("MTO No.")).fillna(df_incident.index.to_series().map(lambda x:f"ROW-{x}"))
    tables={"incident":df_incident}
    for sheet,key in [("RCA Header","rca_header"),("RCA Priority Matrix","rca_priority"),("RCA 4P Verification","rca_4p"),("RCA 4M Verification","rca_4m"),("RCA CAPA Actions","rca_capa")]:
        try: tables[key]=workbook_sheet(workbook,sheet)
        except Exception: tables[key]=pd.DataFrame()
    return tables



# ==============================================================================
# LIMITS / BASELINE / ROBUST SCALING
# ==============================================================================
def build_limit_dict(df_limits):
    out = {}
    for _, r in df_limits.iterrows():
        p = str(r["Parameter"]).strip()
        alarm = safe_float(r["Alarm Limit"])
        trip = safe_float(r["Trip Limit"])
        direction = "high" if trip > alarm else "low"
        out[p] = {
            "parameter": p,
            "unit": r.get("Unit", ""),
            "alarm": alarm,
            "trip": trip,
            "direction": direction,
        }
    return out


def exclude_incident_windows(df, time_col, df_incident, tag, end_time=None, half_window_hours=INCIDENT_EXCLUSION_HOURS):
    out = df.copy()
    incidents = df_incident[df_incident["Tag Number"].astype(str) == tag].copy()
    if end_time is not None:
        incidents = incidents[incidents["Date of Occur."] < pd.Timestamp(end_time)]
    for dt in incidents["Date of Occur."].dropna():
        lo = pd.Timestamp(dt) - pd.Timedelta(hours=half_window_hours)
        hi = pd.Timestamp(dt) + pd.Timedelta(hours=half_window_hours)
        out = out[~out[time_col].between(lo, hi)]
    return out


def select_hourly_baseline(df_on, eval_time, df_incident, tag, eval_hours=EVAL_HOURS):
    eval_time = pd.Timestamp(eval_time)
    baseline_end = eval_time - pd.Timedelta(hours=eval_hours)
    baseline_start = baseline_end - pd.Timedelta(days=BASELINE_DAYS)
    base = df_on[df_on["Timestamp"].between(baseline_start, baseline_end, inclusive="left")].copy()
    base = exclude_incident_windows(base, "Timestamp", df_incident, tag, end_time=baseline_end)

    if len(base) < MIN_BASELINE_ROWS_HOURLY:
        base = df_on[df_on["Timestamp"] < baseline_end].tail(BASELINE_DAYS * 24).copy()
        base = exclude_incident_windows(base, "Timestamp", df_incident, tag, end_time=baseline_end)
    return base, baseline_start, baseline_end


def select_weekly_baseline(df_weekly, eval_date, df_incident, tag,
                           holdout_weeks=WEEKLY_FORECAST_WEEKS, limits=None):
    eval_date = pd.Timestamp(eval_date)
    baseline_end = eval_date - pd.Timedelta(weeks=holdout_weeks)
    known = df_weekly[df_weekly["Date"] <= eval_date].copy()
    regime_start = pd.NaT
    if "Remark" in known:
        repaired = known["Remark"].fillna("").str.contains(
            r"post[- ]repair|baseline restored|post[- ]maintenance", case=False, regex=True)
        if repaired.any():
            regime_start = known.loc[repaired, "Date"].max()
            known = known[known["Date"] >= regime_start]
    base = known[known["Date"] < baseline_end].copy()
    if "Health Status" in base:
        base = base[base["Health Status"].astype(str).str.upper().str.strip() == "NORMAL"]
    base = healthy_rows(base, limits or {}, {p: p for p in (limits or {})})
    incidents = df_incident[df_incident["Tag Number"].astype(str) == tag]
    for dt in incidents["Date of Occur."].dropna():
        if dt < baseline_end:
            base = base[~base["Date"].between(dt-pd.Timedelta(days=7), dt+pd.Timedelta(days=7))]
    base.attrs["regime_start"] = regime_start
    base.attrs["baseline_note"] = "Healthy-only; current maintenance regime; no fallback to degraded data"
    return base, baseline_end


@dataclass
class RobustScalerModel:
    median: pd.Series
    scale: pd.Series
    columns: list

    def transform(self, df):
        x = df[self.columns].astype(float)
        return (x - self.median) / self.scale


def fit_robust_scaler(df, cols):
    x = df[cols].astype(float)
    med = x.median()
    mad = (x - med).abs().median()
    scale = 1.4826 * mad
    std = x.std(ddof=1)
    scale = scale.where(scale > EPS, std)
    scale = scale.where(scale > EPS, 1.0)
    return RobustScalerModel(median=med, scale=scale, columns=cols)


# ==============================================================================
# PCA-MSPC + EWMA
# ==============================================================================
def _pca_statistics(z_df, pca):
    z = np.asarray(z_df, dtype=float)
    scores = pca.transform(z_df)
    eig = np.maximum(pca.explained_variance_, EPS)
    t2 = np.sum((scores ** 2) / eig, axis=1)
    recon = pca.inverse_transform(scores)
    residual = z - recon
    spe = np.sum(residual ** 2, axis=1)
    return t2, spe, residual


def fit_mspc_model(df_baseline, cols):
    clean = df_baseline.dropna(subset=cols).copy()
    if len(clean) < max(10, len(cols) * 3):
        raise ValueError(f"Baseline is too small for PCA-MSPC: {len(clean)} rows, {len(cols)} variables")

    scaler = fit_robust_scaler(clean, cols)
    z = scaler.transform(clean)

    pca_full = PCA().fit(z)
    cum = np.cumsum(pca_full.explained_variance_ratio_)
    n_comp = int(np.searchsorted(cum, PCA_EXPLAINED_VARIANCE_TARGET) + 1)
    # Preserve one residual dimension for SPE when p > 1.
    if len(cols) > 1:
        n_comp = min(n_comp, len(cols) - 1)
    n_comp = max(1, min(n_comp, len(cols), len(clean) - 1))

    pca = PCA(n_components=n_comp).fit(z)
    t2, spe, _ = _pca_statistics(z, pca)

    limits = {
        "t2_watch": float(np.quantile(t2, MSPC_WATCH_QUANTILE)),
        "t2_alarm": float(np.quantile(t2, MSPC_ALARM_QUANTILE)),
        "spe_watch": float(np.quantile(spe, MSPC_WATCH_QUANTILE)),
        "spe_alarm": float(np.quantile(spe, MSPC_ALARM_QUANTILE)),
    }
    for k in limits:
        limits[k] = max(limits[k], EPS)

    return {
        "scaler": scaler,
        "pca": pca,
        "cols": cols,
        "limits": limits,
        "n_components": n_comp,
        "explained_variance": float(np.sum(pca.explained_variance_ratio_)),
    }


def transform_mspc(df, model, time_col):
    x = df.dropna(subset=model["cols"]).copy()
    if x.empty:
        return pd.DataFrame(columns=[time_col, "T2", "SPE", "AnomalyIndex"]), np.empty((0, len(model["cols"])))
    z = model["scaler"].transform(x)
    t2, spe, residual = _pca_statistics(z, model["pca"])
    lim = model["limits"]
    out = pd.DataFrame({
        time_col: x[time_col].values,
        "T2": t2,
        "SPE": spe,
        "T2_Ratio": t2 / lim["t2_alarm"],
        "SPE_Ratio": spe / lim["spe_alarm"],
    })
    out["AnomalyIndex"] = np.maximum(out["T2_Ratio"], out["SPE_Ratio"])
    return out, residual


def mspc_state(t2, spe, limits):
    if t2 >= limits["t2_alarm"] or spe >= limits["spe_alarm"]:
        return "ALARM"
    if t2 >= limits["t2_watch"] or spe >= limits["spe_watch"]:
        return "WATCH"
    return "NORMAL"


def directional_engineering_state(value, lim):
    # Missing measurement is not evidence of a normal condition.
    if pd.isna(value) or not np.isfinite(safe_float(value, np.nan)):
        return "DATA_GAP"
    if lim["direction"] == "high":
        if value >= lim["trip"]:
            return "TRIP"
        if value >= lim["alarm"]:
            return "ALARM"
    else:
        if value <= lim["trip"]:
            return "TRIP"
        if value <= lim["alarm"]:
            return "ALARM"
    return "NORMAL"


def engineering_margin_score(value, reference, lim):
    """Display-oriented engineering margin, not a probability/health model."""
    if any(pd.isna(v) for v in [value, reference, lim["trip"]]):
        return np.nan
    if lim["direction"] == "high":
        denom = lim["trip"] - reference
        if abs(denom) < EPS:
            return 100.0
        score = 100.0 * (lim["trip"] - value) / denom
    else:
        denom = reference - lim["trip"]
        if abs(denom) < EPS:
            return 100.0
        score = 100.0 * (value - lim["trip"]) / denom
    return float(np.clip(score, 0, 100))


def ewma_risk_series(series, baseline_mean, baseline_std, direction):
    s = pd.to_numeric(series, errors="coerce")
    sigma_inf = math.sqrt(EWMA_LAMBDA / (2.0 - EWMA_LAMBDA))
    watch, alarm = EWMA_L_WATCH*sigma_inf, EWMA_L_ALARM*sigma_inf
    if not np.isfinite(baseline_mean) or not np.isfinite(baseline_std) or baseline_std <= EPS:
        return pd.Series(np.nan, index=s.index), watch, alarm
    z = (s-baseline_mean)/baseline_std
    return (z if direction == "high" else -z).ewm(alpha=EWMA_LAMBDA, adjust=False).mean(), watch, alarm


def _top_statistical_contributors(current_row, model, top_n=3):
    vals = current_row[model["cols"]].astype(float).to_frame().T
    z = model["scaler"].transform(vals).iloc[0]
    ranked = z.abs().sort_values(ascending=False).head(top_n)
    return [(idx, float(z[idx])) for idx in ranked.index]


# ==============================================================================
# PHASE 1-2: HOURLY CONDITION MODEL
# ==============================================================================
def evaluate_hourly_condition(asset, global_tables, eval_time=None, eval_hours=EVAL_HOURS):
    tag = asset["tag_number"]
    cfg = asset["cfg"]
    df_on = asset["df_on"].copy()
    df_incident = global_tables["incident"]
    limit_dict = build_limit_dict(asset["df_limits"])

    if df_on.empty:
        raise ValueError(f"{tag}: no running data are available")

    if eval_time is None:
        eval_time = df_on["Timestamp"].max()
    eval_time = pd.Timestamp(eval_time)
    df_to_eval = df_on[df_on["Timestamp"] <= eval_time].copy()
    if df_to_eval.empty:
        raise ValueError(f"{tag}: no data are available up to {eval_time}")

    current_row = df_to_eval.iloc[-1]
    current_time = current_row["Timestamp"]
    base, baseline_start, baseline_end = select_hourly_baseline(
        df_to_eval, current_time, df_incident, tag, eval_hours=eval_hours
    )

    base = healthy_rows(base, limit_dict, cfg.get("hourly_param_map", {}))
    model_cols = [c for c in HOURLY_SUFFIXES if c in df_to_eval.columns and base[c].notna().sum() >= MIN_BASELINE_ROWS_HOURLY]
    if len(model_cols) < 2:
        raise ValueError(f"{tag}: insufficient hourly variables for MSPC")

    mspc = fit_mspc_model_cached(asset["tag_number"], base, model_cols)
    eval_window = df_to_eval[df_to_eval["Timestamp"] > baseline_end].copy()
    # Persistence must not bridge a shutdown or an unobserved clock-hour.
    if len(eval_window) > 1:
        discontinuity = eval_window["Timestamp"].diff().gt(pd.Timedelta(hours=1))
        if discontinuity.any():
            eval_window = eval_window.loc[discontinuity[discontinuity].index[-1]:].copy()
    if eval_window.empty:
        eval_window = df_to_eval.tail(eval_hours).copy()

    stat_hist, _ = transform_mspc(eval_window, mspc, "Timestamp")
    if stat_hist.empty:
        raise ValueError(f"{tag}: no evaluable MSPC rows")

    lims = mspc["limits"]
    stat_hist["RawState"] = [mspc_state(t2, q, lims) for t2, q in zip(stat_hist["T2"], stat_hist["SPE"])]
    stat_state_raw = stat_hist["RawState"].iloc[-1]
    stat_state = persistent_state(stat_hist["RawState"], HOURLY_PERSISTENCE_WINDOW, HOURLY_PERSISTENCE_MIN_COUNT)
    stat_abnormal_count = sum(STATE_RANK.get(x, 0) >= STATE_RANK["WATCH"] for x in stat_hist["RawState"].tail(HOURLY_PERSISTENCE_WINDOW))

    t2 = float(stat_hist["T2"].iloc[-1])
    spe = float(stat_hist["SPE"].iloc[-1])

    engineering = {}
    ewma_states = []
    margins = []
    for param, suffix in cfg.get("hourly_param_map", {}).items():
        if param not in limit_dict or suffix not in df_to_eval.columns:
            continue
        lim = limit_dict[param]
        value = safe_float(current_row[suffix])
        state = directional_engineering_state(value, lim)

        b = base[suffix].dropna()
        bmean = float(b.mean()) if not b.empty else np.nan
        bstd = float(b.std(ddof=1)) if len(b) > 1 else np.nan
        ref = float(b.median()) if not b.empty else np.nan

        ewma, ew_watch, ew_alarm = ewma_risk_series(eval_window[suffix], bmean, bstd, lim["direction"])
        ew_raw_states = pd.Series(np.where(ewma >= ew_alarm, "ALARM", np.where(ewma >= ew_watch, "WATCH", "NORMAL")), index=ewma.index)
        ew_state_raw = ew_raw_states.iloc[-1] if len(ew_raw_states) else "NORMAL"
        ew_state = persistent_state(ew_raw_states, HOURLY_PERSISTENCE_WINDOW, HOURLY_PERSISTENCE_MIN_COUNT)
        ew_abnormal_count = sum(STATE_RANK.get(x, 0) >= STATE_RANK["WATCH"] for x in ew_raw_states.tail(HOURLY_PERSISTENCE_WINDOW))
        ewma_states.append(ew_state)
        margin = engineering_margin_score(value, ref, lim)
        margins.append(margin)

        vals = pd.to_numeric(eval_window[suffix], errors="coerce")
        if lim["direction"] == "high":
            alarm_mask = vals >= lim["alarm"]
            trip_mask = vals >= lim["trip"]
        else:
            alarm_mask = vals <= lim["alarm"]
            trip_mask = vals <= lim["trip"]

        engineering[param] = {
            "suffix": suffix,
            "value": value,
            "unit": lim["unit"],
            "state": state,
            "direction": lim["direction"],
            "alarm": lim["alarm"],
            "trip": lim["trip"],
            "deviation_from_alarm": alarm_deviation(value, lim),
            "first_alarm_breach": latest_episode_start(eval_window["Timestamp"], alarm_mask),
            "first_trip_breach": latest_episode_start(eval_window["Timestamp"], trip_mask),
            "alarm_consecutive": consecutive_true_count(alarm_mask),
            "trip_consecutive": consecutive_true_count(trip_mask),
            "baseline_mean": bmean,
            "baseline_std": bstd,
            "baseline_reference": ref,
            "ewma": float(ewma.iloc[-1]) if len(ewma) and pd.notna(ewma.iloc[-1]) else np.nan,
            "ewma_watch": ew_watch,
            "ewma_alarm": ew_alarm,
            "ewma_state_raw": ew_state_raw,
            "ewma_state": ew_state,
            "ewma_abnormal_count": ew_abnormal_count,
            "engineering_margin": margin,
        }

    eng_state = state_max(*[d["state"] for d in engineering.values()]) if engineering else "NORMAL"
    ewma_state = state_max(*ewma_states) if ewma_states else "NORMAL"
    # Hourly PCA-MSPC remains part of the primary multivariate condition decision.
    overall_state = state_max(eng_state, stat_state, ewma_state)

    t2_ratio = t2 / lims["t2_alarm"]
    spe_ratio = spe / lims["spe_alarm"]
    ewma_ratio = 0.0
    for d in engineering.values():
        if pd.notna(d["ewma"]) and d["ewma_alarm"] > EPS:
            ewma_ratio = max(ewma_ratio, d["ewma"] / d["ewma_alarm"])
    condition_index = float(max(t2_ratio, spe_ratio, ewma_ratio))
    eng_margin = float(np.nanmin(margins)) if margins and np.isfinite(margins).any() else np.nan
    contributors = _top_statistical_contributors(current_row, mspc, top_n=3)

    return {
        "mode": "hourly",
        "current_time": current_time,
        "baseline": base,
        "baseline_start": baseline_start,
        "baseline_end": baseline_end,
        "mspc": mspc,
        "stat_history": stat_hist,
        "stat_state_raw": stat_state_raw,
        "stat_state": stat_state,
        "stat_abnormal_count": stat_abnormal_count,
        "engineering": engineering,
        "engineering_state": eng_state,
        "ewma_state": ewma_state,
        "overall_state": overall_state,
        "condition_index": condition_index,
        "engineering_margin": eng_margin,
        "contributors": contributors,
        "model_cols": model_cols,
        "current_row": current_row,
    }

# ==============================================================================
# PHASE 1-2: WEEKLY CONDITION MODEL
# ==============================================================================
def evaluate_weekly_condition(asset, global_tables, eval_date=None):
    tag = asset["tag_number"]
    df = asset["df_weekly"].copy()
    df_incident = global_tables["incident"]
    limits = build_limit_dict(asset["df_limits"])
    params = [p for p in limits if p in df.columns]
    if len(params) < 2:
        raise ValueError(f"{tag}: insufficient weekly parameters")

    if eval_date is None:
        eval_date = df["Date"].max()
    eval_date = pd.Timestamp(eval_date)
    df_eval = df[df["Date"] <= eval_date].copy()
    current = df_eval.iloc[-1]
    current_date = current["Date"]

    base, baseline_end = select_weekly_baseline(df_eval, current_date, df_incident, tag, limits=limits)
    clean_params = [p for p in params if base[p].notna().sum() >= MIN_BASELINE_ROWS_WEEKLY]
    statistical_available = len(base) >= MIN_HEALTHY_WEEKLY_ROWS and len(clean_params) >= 2
    mspc = fit_mspc_model_cached(asset["tag_number"], base, clean_params) if statistical_available else None

    if mspc is None:
        recent_dates = df_eval.loc[df_eval["Date"] >= baseline_end, "Date"]
        stat_hist = pd.DataFrame({"Date": recent_dates.values, "T2": np.nan, "SPE": np.nan,
                                  "T2_Ratio": np.nan, "SPE_Ratio": np.nan, "AnomalyIndex": np.nan})
    else:
        stat_hist, _ = transform_mspc(df_eval[df_eval["Date"] >= baseline_end], mspc, "Date")
    if stat_hist.empty:
        stat_hist, _ = transform_mspc(df_eval.tail(WEEKLY_FORECAST_WEEKS + 1), mspc, "Date")

    lims = mspc["limits"] if mspc else dict(t2_watch=np.inf, t2_alarm=np.inf, spe_watch=np.inf, spe_alarm=np.inf)
    stat_hist["RawState"] = [mspc_state(t2, q, lims) for t2, q in zip(stat_hist["T2"], stat_hist["SPE"])]
    raw_last = stat_hist["RawState"].iloc[-1]
    # Small-sample guard remains: PCA weekly cannot alone escalate to ALARM when baseline <20.
    guarded = stat_hist["RawState"].replace("ALARM", "WATCH") if len(base) < 20 else stat_hist["RawState"]
    stat_state = persistent_state(guarded, WEEKLY_PERSISTENCE_WINDOW, WEEKLY_PERSISTENCE_MIN_COUNT)
    stat_abnormal_count = sum(STATE_RANK.get(x, 0) >= STATE_RANK["WATCH"] for x in guarded.tail(WEEKLY_PERSISTENCE_WINDOW))

    t2 = float(stat_hist["T2"].iloc[-1])
    spe = float(stat_hist["SPE"].iloc[-1])

    engineering = {}
    margins = []
    ewma_states = []
    recent = df_eval[df_eval["Date"] >= baseline_end].copy()
    for p in params:
        lim = limits[p]
        value = safe_float(current[p])
        state = directional_engineering_state(value, lim)
        b = base[p].dropna()
        bmean = float(b.mean()) if statistical_available and not b.empty else np.nan
        bstd = float(b.std(ddof=1)) if statistical_available and len(b) > 1 else np.nan
        ref = float(b.median()) if not b.empty else np.nan

        tail = recent[p]
        ewma, ew_watch, ew_alarm = ewma_risk_series(tail, bmean, bstd, lim["direction"])
        ew_raw_states = pd.Series(np.where(ewma >= ew_alarm, "ALARM", np.where(ewma >= ew_watch, "WATCH", "NORMAL")), index=ewma.index)
        ew_state = persistent_state(ew_raw_states, WEEKLY_PERSISTENCE_WINDOW, WEEKLY_PERSISTENCE_MIN_COUNT)
        ew_abnormal_count = sum(STATE_RANK.get(x, 0) >= STATE_RANK["WATCH"] for x in ew_raw_states.tail(WEEKLY_PERSISTENCE_WINDOW))
        ewma_states.append(ew_state)
        margin = engineering_margin_score(value, ref, lim)
        margins.append(margin)

        vals = pd.to_numeric(recent[p], errors="coerce")
        if lim["direction"] == "high":
            alarm_mask = vals >= lim["alarm"]
            trip_mask = vals >= lim["trip"]
        else:
            alarm_mask = vals <= lim["alarm"]
            trip_mask = vals <= lim["trip"]

        engineering[p] = {
            "value": value,
            "unit": lim["unit"],
            "state": state,
            "direction": lim["direction"],
            "alarm": lim["alarm"],
            "trip": lim["trip"],
            "deviation_from_alarm": alarm_deviation(value, lim),
            "first_alarm_breach": latest_episode_start(recent["Date"], alarm_mask),
            "first_trip_breach": latest_episode_start(recent["Date"], trip_mask),
            "alarm_consecutive": consecutive_true_count(alarm_mask),
            "trip_consecutive": consecutive_true_count(trip_mask),
            "baseline_mean": bmean,
            "baseline_std": bstd,
            "baseline_reference": ref,
            "ewma": float(ewma.iloc[-1]) if len(ewma) and pd.notna(ewma.iloc[-1]) else np.nan,
            "ewma_watch": ew_watch,
            "ewma_alarm": ew_alarm,
            "ewma_state": ew_state,
            "ewma_abnormal_count": ew_abnormal_count,
            "engineering_margin": margin,
        }

    eng_state = state_max(*[d["state"] for d in engineering.values()])
    ewma_state = state_max(*ewma_states)
    # Weekly PCA-MSPC remains a diagnostic signal only. Primary weekly state is
    # Engineering Limits + robust EWMA/trend/persistence logic.
    overall_state = state_max(eng_state, ewma_state)

    t2_ratio = t2 / lims["t2_alarm"]
    spe_ratio = spe / lims["spe_alarm"]
    ewma_ratio = max([d["ewma"] / d["ewma_alarm"] for d in engineering.values() if pd.notna(d["ewma"]) and d["ewma_alarm"] > EPS] + [0.0])
    condition_index = float(max(t2_ratio, spe_ratio, ewma_ratio)) if statistical_available else np.nan
    eng_margin = float(np.nanmin(margins)) if margins and np.isfinite(margins).any() else np.nan
    contributors = _top_statistical_contributors(current[clean_params], mspc, top_n=3) if mspc else []

    return {
        "mode": "weekly",
        "statistical_available": statistical_available,
        "model_note": "Engineering limits + EWMA/trend are primary; weekly PCA-MSPC is diagnostic only" if statistical_available else f"INSUFFICIENT HEALTHY BASELINE ({len(base)}/{MIN_HEALTHY_WEEKLY_ROWS}); engineering limits + trend only",
        "current_time": current_date,
        "baseline": base,
        "baseline_end": baseline_end,
        "mspc": mspc,
        "stat_history": stat_hist,
        "stat_state_raw": raw_last,
        "stat_state": stat_state,
        "stat_abnormal_count": stat_abnormal_count,
        "engineering": engineering,
        "engineering_state": eng_state,
        "ewma_state": ewma_state,
        "overall_state": overall_state,
        "condition_index": condition_index,
        "engineering_margin": eng_margin,
        "contributors": contributors,
        "model_cols": clean_params,
        "current_row": current,
    }

# ==============================================================================
# PHASE 3: VALIDATED FORECAST + PROJECTED TIME-TO-THRESHOLD (PTT)
# ==============================================================================
def _ols_forecast(values, horizon, fit_window=None):
    y = np.asarray(values, dtype=float)
    if fit_window is not None and len(y) > fit_window:
        y = y[-fit_window:]
    if len(y) < 2:
        return np.repeat(y[-1] if len(y) else np.nan, horizon)
    x = np.arange(len(y), dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    xf = np.arange(len(y), len(y) + horizon, dtype=float)
    return intercept + slope * xf


def _autoreg_forecast(values, horizon, lag):
    y = np.asarray(values, dtype=float)
    if len(y) <= lag + 5:
        raise ValueError("insufficient rows for AutoReg")
    if AutoReg is None:
        raise RuntimeError("statsmodels unavailable: AutoReg candidate disabled")
    model = AutoReg(y, lags=lag, trend="ct", old_names=False).fit()
    return np.asarray(model.predict(start=len(y), end=len(y) + horizon - 1, dynamic=False), dtype=float)


def validated_forecast(series, horizon, cadence="hourly"):
    s = pd.to_numeric(pd.Series(series), errors="coerce").dropna()
    if len(s) < 8:
        pred = np.repeat(s.iloc[-1] if len(s) else np.nan, horizon)
        return {"model": "Persistence", "forecast": pred, "mae": np.nan}

    holdout = HOURLY_VALIDATION_HOLDOUT if cadence == "hourly" else WEEKLY_VALIDATION_HOLDOUT
    holdout = min(holdout, max(2, len(s) // 5))
    train = s.iloc[:-holdout]
    test = s.iloc[-holdout:]

    candidates = []

    # 1. Persistence baseline
    p = np.repeat(train.iloc[-1], holdout)
    candidates.append(("Persistence", float(np.mean(np.abs(test.values - p))), None))

    # 2. OLS trend on recent window
    fit_window = min(len(train), 7 * 24) if cadence == "hourly" else len(train)
    p = _ols_forecast(train.values, holdout, fit_window=fit_window)
    candidates.append(("OLS", float(np.mean(np.abs(test.values - p))), None))

    # 3. AutoReg candidates
    lag_grid = ([1, 3, 6, 12, 24] if cadence == "hourly" else [1, 2, 3, 4]) if AutoReg is not None else []
    for lag in lag_grid:
        if len(train) <= lag + 8:
            continue
        try:
            p = _autoreg_forecast(train.values, holdout, lag)
            mae = float(np.mean(np.abs(test.values - p)))
            if np.isfinite(mae):
                candidates.append((f"AutoReg({lag})", mae, lag))
        except Exception:
            pass

    candidates = [c for c in candidates if np.isfinite(c[1])]
    best_name, best_mae, best_lag = min(candidates, key=lambda x: x[1]) if candidates else ("Persistence", np.nan, None)

    full = s.values
    try:
        if best_name == "Persistence":
            future = np.repeat(full[-1], horizon)
        elif best_name == "OLS":
            fit_window = min(len(full), 7 * 24) if cadence == "hourly" else len(full)
            future = _ols_forecast(full, horizon, fit_window=fit_window)
        else:
            future = _autoreg_forecast(full, horizon, best_lag)
    except Exception:
        best_name = "OLS-fallback"
        future = _ols_forecast(full, horizon, fit_window=min(len(full), 7 * 24) if cadence == "hourly" else len(full))

    return {"model": best_name, "forecast": np.asarray(future, dtype=float), "mae": best_mae}


def first_threshold_crossing(pred, lim, direction, threshold="trip"):
    boundary = lim[threshold]
    arr = np.asarray(pred, dtype=float)
    if direction == "high":
        idx = np.where(arr >= boundary)[0]
    else:
        idx = np.where(arr <= boundary)[0]
    return int(idx[0] + 1) if len(idx) else None




# ==============================================================================
# PHASE 4A: CASE-BASED SIMILAR INCIDENT RETRIEVAL
# ==============================================================================
def _token_jaccard(a, b):
    sa = set(normalize_text(a).split())
    sb = set(normalize_text(b).split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def build_symptom_query(asset, condition_result, operator_input=None):
    meta = asset["meta"]
    parts = [
        f"equipment {meta.get('Equipment Type', '')}",
        f"class {meta.get('Equipment Class', '')}",
        f"discipline {meta.get('Discipline', '')}",
    ]

    for t in build_trigger_explanation(condition_result):
        if t["type"] == "ENGINEERING_LIMIT":
            direction = "high" if t.get("direction") == "high" else "low"
            parts.append(f"{t['parameter']} {t['state']} deviation {direction}")
        elif t["type"] == "EWMA_DRIFT":
            direction = "high" if t.get("direction") == "high" else "low"
            parts.append(f"{t['parameter']} persistent drift {direction}")
        elif t["type"] == "VIRTUAL_ADVISORY":
            parts.append(f"hourly nonspecific {t['parameter']} deviation requires verification")
        elif t["type"] == "MULTIVARIATE_ANOMALY":
            for c, z in t.get("contributors", []):
                parts.append(f"{c} deviation {'high' if z > 0 else 'low'}")

    obs = field_observation_text(operator_input or {})
    if obs:
        parts.append(f"operator field observation {obs}")
    return " ".join(parts)

def prepare_incident_text(df_incident, global_tables):
    """Build retrieval corpus from Incident + RCA Header + Priority + verified 4P/4M evidence."""
    inc = df_incident.copy()
    rca = global_tables.get("rca_header", pd.DataFrame())
    if not rca.empty and "AR No" in rca.columns:
        rca_small = rca[[c for c in ["AR No", "Problem Statement", "Root Cause Statement"] if c in rca.columns]].copy()
        inc = inc.merge(rca_small, on="AR No", how="left")
    else:
        inc["Problem Statement"] = ""
        inc["Root Cause Statement"] = ""

    def aggregate_text(df, ar_col, text_cols, filter_ng=False):
        if df is None or df.empty or ar_col not in df.columns:
            return {}
        x = df.copy()
        if filter_ng and "Result" in x.columns:
            x = x[x["Result"].astype(str).str.upper() == "NG"]
        out = {}
        for ar, g in x.groupby(ar_col):
            parts = []
            for c in text_cols:
                if c in g.columns:
                    parts.extend(g[c].dropna().astype(str).tolist())
            out[str(ar)] = " ".join(parts)
        return out

    pri_map = aggregate_text(global_tables.get("rca_priority", pd.DataFrame()), "AR No", ["Description (Short)"])
    p4_map = aggregate_text(global_tables.get("rca_4p", pd.DataFrame()), "AR No", ["Problem Phenomenon Parameter", "Evidence Finding"], filter_ng=True)
    m4_map = aggregate_text(global_tables.get("rca_4m", pd.DataFrame()), "AR No", ["Factor Category", "Evidence Finding"], filter_ng=True)

    inc["RCA Priority Text"] = inc["AR No"].astype(str).map(pri_map).fillna("")
    inc["RCA 4P Text"] = inc["AR No"].astype(str).map(p4_map).fillna("")
    inc["RCA 4M Text"] = inc["AR No"].astype(str).map(m4_map).fillna("")

    text_cols = [
        "Risk Case Title", "Eq. Type", "Component", "F Mechanism",
        "Problem Statement", "Root Cause Statement", "RCA Priority Text", "RCA 4P Text", "RCA 4M Text"
    ]
    for c in text_cols:
        if c not in inc.columns:
            inc[c] = ""
    inc["Retrieval Text"] = inc[text_cols].fillna("").astype(str).agg(" ".join, axis=1)
    return inc

def retrieve_similar_incidents(asset, condition_result, global_tables, exclude_ar=None, top_k=TOP_K_SIMILAR, only_rca=False):
    cutoff=pd.Timestamp(condition_result['current_time'])
    knowledge,base_inc,vectorizer,tfidf_matrix=get_rca_tfidf_index(global_tables,cutoff,only_rca)
    inc=base_inc.copy()
    if exclude_ar is not None: inc=inc[inc['AR No'].astype(str)!=str(exclude_ar)].copy()
    if only_rca and not inc.empty:
        disc=str(asset['meta'].get('Discipline','')).upper()
        inc=inc[inc['Discipline'].astype(str).str.upper().eq(disc)].copy()
        family=asset['tag_number'].split('-')[0]
        compatible={"PU":{"PU"},"KO":{"CO"},"PM":{"EM"},"HE":{"HB","HE"},"BL":{"BL"}}.get(family)
        if compatible: inc=inc[inc['Eq. Type'].astype(str).str.upper().isin(compatible)].copy()
    inc=inc.reset_index(drop=True)
    query=build_symptom_query(asset,condition_result,get_operator_input(global_tables.get('operator_inputs',pd.DataFrame()),asset['tag_number']))
    if inc.empty or vectorizer is None: return query,pd.DataFrame()
    qvec=vectorizer.transform([query]); sim_all=cosine_similarity(qvec,tfidf_matrix).ravel()
    meta=asset['meta']; tag=asset['tag_number']; asset_class=str(meta.get('Equipment Class','')).strip().upper(); discipline=str(meta.get('Discipline','')).strip().upper(); plant=extract_plant_code(meta.get('Plant / Unit','')); eq_name=normalize_text(meta.get('Equipment Type',''))
    if 'heat exchanger' in eq_name: eq_code='HB'
    elif 'compressor' in eq_name: eq_code='CO'
    elif 'blower' in eq_name: eq_code='BL'
    elif 'motor' in eq_name and 'pump' in eq_name: eq_code='EM'
    elif 'pump' in eq_name: eq_code='PU'
    else: eq_code=''
    rowid=inc['_RCA_ROW_ID'].to_numpy(int); text_sim=sim_all[rowid]
    sim_tag=inc.get('Tag Number',pd.Series('',index=inc.index)).astype(str).str.strip().str.upper().eq(tag.upper()).astype(float).to_numpy()
    sim_class=(inc.get('Eq. Class',pd.Series('',index=inc.index)).astype(str).str.strip().str.upper().eq(asset_class)&bool(asset_class)).astype(float).to_numpy()
    sim_disc=(inc.get('Discipline',pd.Series('',index=inc.index)).astype(str).str.strip().str.upper().eq(discipline)&bool(discipline)).astype(float).to_numpy()
    sim_plant=(inc.get('Plant',pd.Series('',index=inc.index)).astype(str).str.strip().str.upper().eq(plant)&bool(plant)).astype(float).to_numpy()
    sim_type=(inc.get('Eq. Type',pd.Series('',index=inc.index)).astype(str).str.strip().str.upper().eq(eq_code)&bool(eq_code)).astype(float).to_numpy()
    score=.60*text_sim+.05*sim_tag+.10*sim_class+.10*sim_disc+.10*sim_plant+.05*sim_type
    out=pd.DataFrame({
        'AR No':inc.get('AR No'),'Incident Key':inc.get('Incident Key'),'Tag Number':inc.get('Tag Number'),'Date':inc.get('Date of Occur.'),
        'Risk Case Title':inc.get('Risk Case Title'),'Eq. Class':inc.get('Eq. Class'),'Discipline':inc.get('Discipline'),'Plant':inc.get('Plant'),'Eq. Type':inc.get('Eq. Type'),
        'Component':inc.get('Component'),'F Mechanism':inc.get('F Mechanism'),'Pre Risk':inc.get('Pre Risk'),'Risk Score':inc.get('Risk Score'),
        'Downtime (hrs)':inc.get('Downtime (hrs)'),'Act. Loss (k US$)':inc.get('Act. Loss (k US$)'),'CBR Similarity':score,
        'Text Similarity':text_sim,'Tag Similarity':sim_tag,'Class Similarity':sim_class,'Discipline Similarity':sim_disc,'Plant Similarity':sim_plant,'Type Similarity':sim_type})
    out=out.sort_values(['CBR Similarity','Date'],ascending=[False,False]).reset_index(drop=True)
    out=out[out['CBR Similarity']>=MIN_RCA_SIMILARITY].head(top_k).reset_index(drop=True)
    return query,out


def similarity_weighted_impact(similar_df, df_incident):
    """Similarity-weighted historical consequence with schema-tolerant column mapping.

    The source workbook is not required to contain a literal ``Total Loss (k US$)``
    column.  We first look for a documented total-loss field; when it is absent we
    use the available actual-loss field as the *consequence basis* rather than
    inventing a value.  The selected basis is returned for auditability.
    """
    if similar_df is None or similar_df.empty:
        return {
            "downtime": np.nan, "loss": np.nan, "total_loss": np.nan,
            "consequence_class": "C1", "loss_basis": "NO_SIMILAR_INCIDENT"
        }

    def _resolve_col(df, aliases):
        if df is None or df.empty:
            return None
        # Exact match first, then normalized match to tolerate punctuation/case changes.
        for c in aliases:
            if c in df.columns:
                return c
        normalized = {normalize_text(c): c for c in df.columns}
        for c in aliases:
            hit = normalized.get(normalize_text(c))
            if hit is not None:
                return hit
        return None

    w = pd.to_numeric(similar_df.get("CBR Similarity", pd.Series(1.0, index=similar_df.index)),
                      errors="coerce").fillna(0).to_numpy(float)
    if np.sum(w) <= EPS:
        w = np.ones(len(similar_df), dtype=float)

    def wavg_resolved(aliases):
        col = _resolve_col(similar_df, aliases)
        if col is None:
            return np.nan, None
        y = pd.to_numeric(similar_df[col], errors="coerce").to_numpy(float)
        mask = np.isfinite(y) & np.isfinite(w)
        if not mask.any():
            return np.nan, col
        ww = w[mask]
        value = (float(np.sum(ww * y[mask]) / np.sum(ww))
                 if np.sum(ww) > EPS else float(np.nanmean(y[mask])))
        return value, col

    downtime, _ = wavg_resolved([
        "Downtime (hrs)", "Downtime (hr)", "Downtime Hours", "Downtime"
    ])
    loss, loss_col = wavg_resolved([
        "Act. Loss (k US$)", "Actual Loss (k US$)", "Actual Loss (kUSD)",
        "Act Loss (k US$)", "Business Loss (k US$)"
    ])
    total_loss, total_col = wavg_resolved([
        "Total Loss (k US$)", "Total Loss (kUSD)", "Total Loss k US$",
        "Total Business Loss (k US$)"
    ])

    # If the workbook has no separate total-loss field, use the available actual-loss
    # metric as the consequence basis.  This is a transparent fallback, not invented data.
    if total_col is None or not np.isfinite(total_loss):
        total_loss = loss
        consequence_aliases = [
            "Act. Loss (k US$)", "Actual Loss (k US$)", "Actual Loss (kUSD)",
            "Act Loss (k US$)", "Business Loss (k US$)"
        ]
        loss_basis = f"ACTUAL_LOSS_FALLBACK:{loss_col}" if loss_col else "NO_LOSS_COLUMN"
    else:
        consequence_aliases = [total_col]
        loss_basis = f"TOTAL_LOSS:{total_col}"

    hist_col = _resolve_col(df_incident, consequence_aliases)
    hist = (pd.to_numeric(df_incident[hist_col], errors="coerce").dropna()
            if hist_col is not None else pd.Series(dtype=float))

    if hist.empty or not np.isfinite(total_loss):
        # No evidence to rank historical economic consequence. Keep the least-severe
        # class but expose the missing basis in loss_basis instead of raising KeyError.
        cclass = "C1"
    else:
        q50, q75, q90 = hist.quantile([0.50, 0.75, 0.90]).to_numpy(float)
        if total_loss <= q50:
            cclass = "C1"
        elif total_loss <= q75:
            cclass = "C2"
        elif total_loss <= q90:
            cclass = "C3"
        else:
            cclass = "C4"

    return {
        "downtime": downtime,
        "loss": loss,
        "total_loss": total_loss,
        "consequence_class": cclass,
        "loss_basis": loss_basis,
    }


# ==============================================================================
# PHASE 4B: TRACEABLE RCA EVIDENCE
# ==============================================================================
def retrieve_rca_evidence(similar_df, global_tables, condition_result=None, top_n=TOP_K_RCA_DISPLAY):
    """Build Top-N probable RCA candidates with explicit current-vs-historical evidence separation."""
    evidence = blank_rca_evidence()
    if similar_df is None or similar_df.empty or condition_result is None:
        return evidence

    rca_header = global_tables.get("rca_header", pd.DataFrame())
    if rca_header.empty:
        return evidence

    triggers = build_trigger_explanation(condition_result)
    evidence["current_measured_evidence"] = [t for t in triggers if t["type"] in {"ENGINEERING_LIMIT", "EWMA_DRIFT"}]
    evidence["current_statistical_evidence"] = [t for t in triggers if t["type"] == "MULTIVARIATE_ANOMALY"]

    pr = global_tables.get("rca_priority", pd.DataFrame())
    p4 = global_tables.get("rca_4p", pd.DataFrame())
    m4 = global_tables.get("rca_4m", pd.DataFrame())
    capa = global_tables.get("rca_capa", pd.DataFrame())

    candidates = []
    used_ar = set()
    for _, simrow in similar_df.iterrows():
        ar = simrow.get("AR No")
        if pd.isna(ar) or str(ar) in used_ar:
            continue
        hdr = rca_header[rca_header["AR No"].astype(str) == str(ar)]
        if hdr.empty:
            continue
        used_ar.add(str(ar))
        h = hdr.iloc[0]
        case_similarity = safe_float(simrow.get("CBR Similarity"), 0.0)

        cause_rows = []
        if not pr.empty:
            x = pr[pr["AR No"].astype(str) == str(ar)].sort_values(["Priority Rank", "Root Cause ID"])
            for _, r in x.iterrows():
                factor_text = f"{r.get('Description (Short)', '')}"
                status, groups = match_factor_to_current(factor_text, condition_result)
                cause_rows.append({
                    "ID": r.get("Root Cause ID"),
                    "Priority": r.get("Priority Rank"),
                    "Description": r.get("Description (Short)"),
                    "CurrentEvidenceStatus": status,
                    "ObservableGroups": groups,
                })

        verification_4p = []
        if not p4.empty:
            x = p4[(p4["AR No"].astype(str) == str(ar)) & (p4["Result"].astype(str).str.upper() == "NG")]
            for _, r in x.iterrows():
                txt = f"{r.get('Problem Phenomenon Parameter', '')} {r.get('Evidence Finding', '')}"
                status, groups = match_factor_to_current(txt, condition_result)
                verification_4p.append({
                    "ID": r.get("Parameter ID"),
                    "Factor": r.get("Problem Phenomenon Parameter"),
                    "Evidence": r.get("Evidence Finding"),
                    "CurrentEvidenceStatus": status,
                    "ObservableGroups": groups,
                })

        verification_4m = []
        if not m4.empty:
            x = m4[(m4["AR No"].astype(str) == str(ar)) & (m4["Result"].astype(str).str.upper() == "NG")]
            for _, r in x.iterrows():
                verification_4m.append({
                    "ID": r.get("Factor ID"),
                    "Factor": r.get("Factor Category"),
                    "Evidence": r.get("Evidence Finding"),
                    "CurrentEvidenceStatus": "SYSTEMIC_HYPOTHESIS_REQUIRES_VERIFICATION",
                })

        # Merge evidence by factor ID to avoid double counting Priority Matrix + 4P.
        factor_status = {}
        for item in cause_rows + verification_4p:
            fid = str(item.get("ID", ""))
            st = item.get("CurrentEvidenceStatus", "NOT_OBSERVABLE")
            if not fid:
                continue
            old = factor_status.get(fid)
            order = {"CONSISTENT": 3, "NOT_SUPPORTED_CURRENTLY": 2, "NOT_OBSERVABLE": 1}
            if old is None or order.get(st, 0) > order.get(old, 0):
                factor_status[fid] = st
        observable = [st for st in factor_status.values() if st != "NOT_OBSERVABLE"]
        consistent = [st for st in observable if st == "CONSISTENT"]
        support_ratio = len(consistent) / len(observable) if observable else 0.0

        # Candidate ranking: similarity dominates; current evidence refines ranking.
        candidate_score = 0.75 * case_similarity + 0.25 * support_ratio
        consistent_ids = [fid for fid, st in factor_status.items() if st == "CONSISTENT"]

        capa_rows = []
        if not capa.empty:
            cx = capa[capa["AR No"].astype(str) == str(ar)].copy()
            type_rank = {"Corrective": 0, "Preventive": 1, "Pro-Active": 2}
            for _, r in cx.iterrows():
                rc = str(r.get("RC", "")).strip()
                related = bool(consistent_ids) and (rc in consistent_ids)
                capa_rows.append({
                    "RC": rc,
                    "Type": r.get("Action Type"),
                    "Plan": r.get("Action Plan"),
                    "HistoricalPIC": r.get("PIC"),
                    "HistoricalTarget": pd.to_datetime(r.get("Target Date"), errors="coerce"),
                    "HistoricalStatus": str(r.get("Status", "")).strip(),
                    "RelatedToCurrentCandidate": bool(related),
                    "_rank": type_rank.get(str(r.get("Action Type")), 9),
                })
            capa_rows = sorted(capa_rows, key=lambda x: (not x["RelatedToCurrentCandidate"], x["_rank"]))
            for x in capa_rows:
                x.pop("_rank", None)

        candidates.append({
            "AR No": ar,
            "Case Similarity": case_similarity,
            "Candidate Score": candidate_score,
            "Root Cause": h.get("Root Cause Statement"),
            "Problem Statement": h.get("Problem Statement"),
            "Priority Causes": cause_rows,
            "Verification 4P": verification_4p,
            "Verification 4M": verification_4m,
            "CAPA": capa_rows,
            "Consistent RC IDs": consistent_ids,
            "Evidence Support Ratio": support_ratio,
            "Observable Evidence Count": len(observable),
            "Consistent Evidence Count": len(consistent),
        })
        if len(candidates) >= max(top_n * 2, top_n):
            break

    if not candidates:
        return evidence

    candidates.sort(key=lambda x: x["Candidate Score"], reverse=True)
    candidates = candidates[:top_n]
    for i, c in enumerate(candidates):
        next_score = candidates[i + 1]["Candidate Score"] if i + 1 < len(candidates) else np.nan
        gap = c["Candidate Score"] - next_score if pd.notna(next_score) else np.nan
        c["Evidence Strength"] = evidence_strength_label(
            c["Case Similarity"], c["Consistent Evidence Count"], c["Observable Evidence Count"], gap
        )

    primary = candidates[0]
    strength = primary["Evidence Strength"]
    evidence.update({
        "matched_ar": primary["AR No"],
        # Kept for backward compatibility. This text is a historical-case mechanism, not a confirmed current root cause.
        "root_cause": primary["Root Cause"],
        "leading_hypothesis": primary["Root Cause"],
        "hypothesis_label": rca_hypothesis_label(strength),
        "problem_statement": primary["Problem Statement"],
        "priority_causes": primary["Priority Causes"],
        "verification_4p": primary["Verification 4P"],
        "verification_4m": primary["Verification 4M"],
        "capa": primary["CAPA"],
        "candidates": candidates,
        "historical_verified_evidence": primary["Verification 4P"],
        "systemic_hypotheses": primary["Verification 4M"],
        "evidence_strength": strength,
        "historical_capa_actionable": historical_capa_is_actionable(strength),
    })
    return evidence


# ==============================================================================
# OPERATOR ACTION GUIDANCE + PERSISTENT PROBLEM TANK
# ==============================================================================
def build_current_actions(asset, condition_result, rca_evidence, priority):
    """Create proposed current actions without treating a historical RCA match as a confirmed diagnosis."""
    actions = []
    owner_role = suggested_owner_role(asset)
    sla = priority_sla(priority)
    triggers = build_trigger_explanation(condition_result)
    strength = str(rca_evidence.get("evidence_strength", "UNVERIFIED")).upper()

    # 1) Always verify the live trigger first.
    if triggers:
        t = triggers[0]
        if t["type"] == "ENGINEERING_LIMIT":
            plan = f"Verify {t['parameter']} locally and in DCS, then inspect the associated equipment condition before intervention."
        elif t["type"] == "EWMA_DRIFT":
            plan = f"Verify the persistent drift in {t['parameter']} and compare it with local indication and recent operating changes."
        elif t["type"] == "VIRTUAL_ADVISORY":
            plan = f"Verify {t['parameter']} with an independent measurement and operating context before using the estimate for diagnosis. {t['reason']}."
        else:
            contrib = ", ".join(str(x[0]) for x in t.get("contributors", [])[:3]) or "the top contributing sensors"
            plan = f"Verify the multivariate anomaly using {contrib} and check for common-cause operating changes."
        actions.append({
            "Type": "Verification",
            "Plan": plan,
            "SuggestedOwner": owner_role,
            "CurrentStatus": "PROPOSED",
            "SLA": sla,
            "Source": "CURRENT_TRIGGER",
            "RC": None,
        })

    # 2) Add discriminating checks so engineers can test the hypothesis against realistic alternatives.
    checks = build_discriminating_checks(asset, condition_result, rca_evidence)
    if checks:
        actions.append({
            "Type": "Diagnostic Verification",
            "Plan": "; ".join(checks),
            "SuggestedOwner": owner_role,
            "CurrentStatus": "PROPOSED",
            "SLA": sla,
            "Source": "HYPOTHESIS_DISCRIMINATION",
            "RC": None,
        })

    # 3) Historical CAPA is only a reference action when current evidence is MEDIUM/HIGH.
    # LOW / UNSUPPORTED_CURRENTLY / UNVERIFIED cases remain verification-only.
    if historical_capa_is_actionable(strength):
        for a in rca_evidence.get("capa", []):
            if not a.get("RelatedToCurrentCandidate", False):
                continue
            actions.append({
                "Type": a.get("Type"),
                "Plan": a.get("Plan"),
                "SuggestedOwner": owner_role,
                "CurrentStatus": "PROPOSED_REFERENCE",
                "SLA": sla,
                "Source": "HISTORICAL_CAPA_REFERENCE",
                "RC": a.get("RC"),
                "HistoricalStatus": a.get("HistoricalStatus"),
                "HistoricalPIC": a.get("HistoricalPIC"),
                "HistoricalTarget": a.get("HistoricalTarget"),
            })
            if len(actions) >= 4:
                break
    return actions


def load_problem_tank_history():
    """Load the persistent ticket register.

    One row represents the latest state of one ticket. Chronological transitions are
    stored separately in ``action_history.csv``.
    """
    cols = [
        "Ticket ID", "Asset", "Opened At", "Last Seen", "Condition State", "Priority",
        "Owner Role", "Ticket State", "Action Status", "Normal Streak", "Matched RCA",
        "Evidence Strength", "Operator Decision", "Operator", "Operator Comment",
        "Field Observation", "Update Source", "Last Observation"
    ]
    if os.path.exists(PROBLEM_TANK_HISTORY_FILE):
        try:
            df = pd.read_csv(PROBLEM_TANK_HISTORY_FILE, dtype=str)
            # Backward compatibility with earlier files where Ticket State was named Status.
            if "Ticket State" not in df.columns:
                df["Ticket State"] = df["Status"] if "Status" in df.columns else "OPEN"
            if "Action Status" not in df.columns:
                # Do not copy engine lifecycle states into human action progress.
                df["Action Status"] = "NOT_STARTED"
            for c in cols:
                if c not in df.columns:
                    df[c] = 0 if c == "Normal Streak" else ""
            df = df.fillna("")
            df["Normal Streak"] = pd.to_numeric(df["Normal Streak"], errors="coerce").fillna(0).astype(int)
            df["Action Status"] = df["Action Status"].replace("", "NOT_STARTED").fillna("NOT_STARTED")
            for c in cols:
                if c != "Normal Streak":
                    df[c] = df[c].astype(object)
            return df[cols].copy()
        except Exception:
            pass
    df = pd.DataFrame(columns=cols)
    for c in cols:
        if c != "Normal Streak":
            df[c] = df[c].astype(object)
        else:
            df[c] = df[c].astype(int)
    return df


def save_problem_tank_history(df):
    ensure_output_dir()
    df.to_csv(PROBLEM_TANK_HISTORY_FILE, index=False)


def _active_ticket_row(history, tag):
    if history is None or history.empty:
        return None
    state_col = "Ticket State" if "Ticket State" in history.columns else "Status"
    x = history[(history["Asset"].astype(str) == str(tag)) &
                (~history[state_col].astype(str).str.upper().isin(["CLOSED"]))]
    if x.empty:
        return None
    return x.iloc[-1]


def _new_ticket_id(history, tag):
    n = 1
    if history is not None and not history.empty:
        n = int((history["Asset"].astype(str) == str(tag)).sum()) + 1
    return f"PT-{pd.Timestamp.now().strftime('%Y%m%d')}-{tag.replace('-', '')}-{n:03d}"


def update_persistent_ticket(history, asset, operator_context, condition_result, priority, rca_evidence, operator_input, current_actions):
    """Update ticket lifecycle without mixing it with action progress or equipment state."""
    tag = asset["tag_number"]
    history = history.copy() if history is not None else load_problem_tank_history()
    # Normalize older in-memory history if needed.
    if "Ticket State" not in history.columns:
        history["Ticket State"] = history["Status"] if "Status" in history.columns else "OPEN"
    if "Action Status" not in history.columns:
        history["Action Status"] = "NOT_STARTED"
    for c in ["Field Observation", "Update Source", "Last Observation"]:
        if c not in history.columns:
            history[c] = ""
    for c in history.columns:
        if c != "Normal Streak" and history[c].dtype != "object":
            history[c] = history[c].fillna("").astype(object)

    active = _active_ticket_row(history, tag)
    observation = pd.Timestamp(condition_result.get("decision_time", condition_result["current_time"]))
    previous_observation = pd.to_datetime(active.get("Last Observation"), errors="coerce") if active is not None else pd.NaT
    new_observation = pd.isna(previous_observation) or observation > previous_observation
    abnormal = operator_context.get("status") == "RUNNING" and condition_result.get("overall_state") != "NORMAL"
    ticket_required = abnormal and priority in {"P1", "P2", "P3"}

    decision = str(operator_input.get("Decision", "")).strip().upper() if operator_input else ""
    operator = str(operator_input.get("Operator", "")).strip() if operator_input else ""
    comment = str(operator_input.get("Comment", "")).strip() if operator_input else ""
    field_observation = str(operator_input.get("Field Observation", "")).strip() if operator_input else ""
    requested_owner = str(operator_input.get("Owner Role", "")).strip() if operator_input else ""
    requested_action_status = str(operator_input.get("Action Status", "")).strip().upper() if operator_input else ""
    operator_update_present = any([decision, operator, comment, field_observation, requested_owner, requested_action_status])
    update_source = "OPERATOR" if operator_update_present else "ENGINE"
    allowed_action = {"", "NOT_STARTED", "ACKNOWLEDGED", "IN_PROGRESS", "PENDING_VERIFICATION", "COMPLETED"}
    if requested_action_status not in allowed_action:
        requested_action_status = ""
    now_txt = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    owner_role = requested_owner or (str(active.get("Owner Role", "")).strip() if active is not None else "") or suggested_owner_role(asset)

    previous_ticket_state = str(active.get("Ticket State", "")) if active is not None else ""
    previous_action_status = str(active.get("Action Status", "NOT_STARTED")) if active is not None else "NOT_STARTED"

    if ticket_required:
        if active is None:
            ticket_id = _new_ticket_id(history, tag)
            ticket_state = "OPEN"
            action_status = requested_action_status or ("ACKNOWLEDGED" if decision == "ACKNOWLEDGE" else "NOT_STARTED")
            row = {
                "Ticket ID": ticket_id, "Asset": tag, "Opened At": now_txt, "Last Seen": now_txt,
                "Condition State": condition_result.get("overall_state"), "Priority": priority,
                "Owner Role": owner_role, "Ticket State": ticket_state, "Action Status": action_status,
                "Normal Streak": 0, "Matched RCA": rca_evidence.get("matched_ar"),
                "Evidence Strength": rca_evidence.get("evidence_strength"),
                "Operator Decision": decision, "Operator": operator, "Operator Comment": comment,
                "Field Observation": field_observation, "Update Source": update_source,
                "Last Observation": str(observation),
            }
            history = pd.concat([history, pd.DataFrame([row])], ignore_index=True)
            idx = history.index[-1]
            append_action_history(ticket_id, tag, "ENGINE", "TICKET_CREATED",
                                  "", ticket_state, "", action_status,
                                  decision, operator, owner_role, field_observation, comment)
        else:
            ticket_id = active["Ticket ID"]
            idx = history.index[history["Ticket ID"].astype(str) == str(ticket_id)][-1]
            ticket_state = str(history.loc[idx, "Ticket State"] or "OPEN")
            action_status = str(history.loc[idx, "Action Status"] or "NOT_STARTED")
            if requested_action_status:
                action_status = requested_action_status
            elif decision == "ACKNOWLEDGE" and action_status == "NOT_STARTED":
                action_status = "ACKNOWLEDGED"
            history.loc[idx, ["Last Seen", "Condition State", "Priority", "Owner Role", "Matched RCA", "Evidence Strength", "Normal Streak"]] = [
                now_txt, condition_result.get("overall_state"), priority, owner_role,
                rca_evidence.get("matched_ar"), rca_evidence.get("evidence_strength"), 0
            ]
            history.loc[idx, "Action Status"] = action_status

        history.loc[idx, ["Operator Decision", "Operator", "Operator Comment", "Field Observation", "Owner Role", "Last Observation", "Update Source"]] = [
            decision, operator, comment, field_observation, owner_role, str(observation), update_source
        ]
        # RCA confirmation/rejection remains a decision, not a ticket lifecycle state.
        current_ticket_state = str(history.loc[idx, "Ticket State"])
        current_action_status = str(history.loc[idx, "Action Status"])
        if current_ticket_state != previous_ticket_state and previous_ticket_state:
            append_action_history(ticket_id, tag, "ENGINE", "TICKET_STATE_CHANGED",
                                  previous_ticket_state, current_ticket_state,
                                  previous_action_status, current_action_status,
                                  decision, operator, owner_role, field_observation, comment)
        return history, {
            "ticket_required": True, "ticket_id": ticket_id, "priority": priority,
            "owner": owner_role, "ticket_state": current_ticket_state,
            "action_status": current_action_status, "status": current_ticket_state,
            "actions": current_actions, "operator_decision": decision,
        }

    # Existing ticket remains persistent through recovery/off/data-gap periods.
    if active is not None:
        ticket_id = active["Ticket ID"]
        idx = history.index[history["Ticket ID"].astype(str) == str(ticket_id)][-1]
        streak = int(safe_float(history.loc[idx, "Normal Streak"], 0) or 0)
        ticket_state = str(history.loc[idx, "Ticket State"] or "OPEN")
        action_status = str(history.loc[idx, "Action Status"] or "NOT_STARTED")

        if operator_context.get("status") == "RUNNING" and condition_result.get("overall_state") == "NORMAL" and condition_result.get("statistical_available", True):
            if new_observation:
                streak += 1
            ticket_state = "READY_FOR_CLOSURE" if streak >= TICKET_NORMAL_STREAK_FOR_CLOSE else "RECOVERY_MONITORING"
            if decision == "CLOSE_TICKET" and streak >= TICKET_NORMAL_STREAK_FOR_CLOSE:
                ticket_state = "CLOSED"
                if not requested_action_status:
                    action_status = "COMPLETED"
        elif operator_context.get("status") in {"STALE_WEEKLY", "STALE", "OFF", "NOT_RUNNING", "DATA_GAP"}:
            ticket_state = f"PAUSED_{operator_context.get('status')}"
            streak = 0
        else:
            streak = 0
            if not condition_result.get("statistical_available", True):
                ticket_state = "REVIEW_DATA_COVERAGE"

        if requested_action_status:
            action_status = requested_action_status
        elif decision == "ACKNOWLEDGE" and action_status == "NOT_STARTED":
            action_status = "ACKNOWLEDGED"

        history.loc[idx, ["Last Seen", "Condition State", "Priority", "Ticket State", "Action Status", "Normal Streak",
                          "Operator Decision", "Operator", "Operator Comment", "Field Observation", "Owner Role", "Update Source", "Last Observation"]] = [
            now_txt, condition_result.get("overall_state"), priority, ticket_state, action_status, streak,
            decision, operator, comment, field_observation, owner_role, update_source, str(observation)
        ]

        if ticket_state != previous_ticket_state:
            append_action_history(ticket_id, tag, "ENGINE", "TICKET_STATE_CHANGED",
                                  previous_ticket_state, ticket_state,
                                  previous_action_status, action_status,
                                  decision, operator, owner_role, field_observation, comment)

        return history, {
            "ticket_required": False, "ticket_id": ticket_id, "priority": priority,
            "owner": owner_role, "ticket_state": ticket_state, "action_status": action_status,
            "status": ticket_state, "actions": [], "operator_decision": decision,
        }

    return history, {
        "ticket_required": False, "ticket_id": None, "priority": priority,
        "owner": None, "ticket_state": "MONITOR", "action_status": "NOT_STARTED",
        "status": "MONITOR", "actions": [], "operator_decision": decision,
    }


# ==============================================================================
# PHASE 5-6: ACTION PRIORITIZATION + PROBLEM TANK
# ==============================================================================
def prioritize_action(condition_state, consequence_class, asset_criticality='MEDIUM'):
    """Transparent business-rule engine: severity + consequence + asset criticality."""
    base = ACTION_PRIORITY_MATRIX.get(condition_state, ACTION_PRIORITY_MATRIX["NORMAL"]).get(consequence_class, "P4")
    rank=PRIORITY_RANK.get(base,4)
    crit=CRITICALITY_RANK.get(str(asset_criticality).upper(),1)
    # Escalate one level for HIGH/CRITICAL criticality when condition is WATCH+; never infer probability.
    if STATE_RANK.get(condition_state,0)>=STATE_RANK['WATCH'] and crit>=2:
        rank=max(1,rank-1)
    priority={1:'P1',2:'P2',3:'P3',4:'P4'}[rank]
    return priority, priority_text(priority)

def make_problem_tank_ticket(asset, operator_context, condition_result, impact, priority, rca_evidence, similar_df, global_tables, operator_input):
    current_actions = build_current_actions(asset, condition_result, rca_evidence, priority)
    history = global_tables.get("ticket_history", load_problem_tank_history())
    history, ticket = update_persistent_ticket(
        history, asset, operator_context, condition_result, priority, rca_evidence, operator_input, current_actions
    )
    global_tables["ticket_history"] = history
    return ticket

def log_retrieval_and_action(tag, query, similar_df, impact, condition_result, priority, urgency, evidence, ticket):
    if not VERBOSE_CONSOLE:
        return
    detail_log("\n" + "=" * 110)
    detail_log(f"RCA DECISION SUPPORT — {tag}")
    detail_log("=" * 110)
    detail_log(f"Query: {query}")
    detail_log(f"Condition: {condition_result['overall_state']} | Priority: {priority} | {urgency}")
    for i, c in enumerate(evidence.get("candidates", []), 1):
        detail_log(
            f"Candidate {i}: {c['AR No']} | similarity={c['Case Similarity']*100:.1f}% | "
            f"evidence={c['Evidence Strength']} | root cause={str(c['Root Cause'])[:150]}"
        )
    if ticket.get("ticket_id"):
        detail_log(f"Problem Tank: {ticket['ticket_id']} | {ticket['status']} | owner={ticket['owner']}")

# ==============================================================================
# AUXILIARY HOURLY STATISTICAL CONTEXT FOR EXECUTIVE TREND
# ==============================================================================
def build_aux_hourly_stat_context(asset, global_tables):
    """For HE-3301 this is statistical context only, not engineering-limit diagnosis."""
    try:
        df_on = asset["df_on"].copy()
        if df_on.empty:
            return pd.DataFrame()
        eval_time = df_on["Timestamp"].max()
        base, _, baseline_end = select_hourly_baseline(
            df_on, eval_time, global_tables["incident"], asset["tag_number"], eval_hours=EVAL_HOURS
        )
        cols = [c for c in HOURLY_SUFFIXES if c in df_on.columns and base[c].notna().sum() >= MIN_BASELINE_ROWS_HOURLY]
        if len(cols) < 2:
            return pd.DataFrame()
        model = fit_mspc_model_cached(asset["tag_number"], base, cols)
        full = df_on[df_on["Timestamp"] >= base["Timestamp"].min()].copy()
        hist, _ = transform_mspc(full, model, "Timestamp")
        return hist
    except Exception:
        return pd.DataFrame()


# ==============================================================================
# PIPELINE PER ASSET
# ==============================================================================
def run_asset_pipeline(asset, global_tables):
    tag = asset["tag_number"]
    runtime_mode = global_tables.get("runtime_mode", {"mode": "SNAPSHOT"})
    op_context = operating_context(asset, runtime_mode)
    operator_input = get_operator_input(global_tables.get("operator_inputs", pd.DataFrame()), tag)

    condition = evaluate_asset_condition(asset, global_tables)
    # Legacy build_forecasts() intentionally removed from the operational path.
    # All final forecasts are generated once by the canonical PF layer after asset ingestion/RCA context.
    forecasts = {}
    triggers = build_trigger_explanation(condition)

    # Full incident base for consequence estimation.
    query = build_symptom_query(asset, condition, operator_input=operator_input)
    _, similar = retrieve_similar_incidents(asset, condition, global_tables, top_k=TOP_K_SIMILAR)
    impact = similarity_weighted_impact(similar, global_tables["incident"])

    rca_active = op_context.get("diagnosis_allowed", False) and condition["overall_state"] != "NORMAL"
    if rca_active:
        # Separate detailed-RCA library: search only incidents that have RCA Header/4P/4M/CAPA records.
        _, rca_pool = retrieve_similar_incidents(
            asset, condition, global_tables, top_k=max(TOP_K_RCA_DISPLAY * 2, 5), only_rca=True
        )
        obs = field_observation_text(operator_input)
        if obs and not rca_pool.empty:
            obs_norm = normalize_text(obs)
            rca_pool = rca_pool.copy()
            rca_pool["Field Observation Similarity"] = rca_pool["Risk Case Title"].fillna("").map(lambda x: _token_jaccard(obs_norm, x))
            rca_pool["CBR Similarity"] = 0.90 * rca_pool["CBR Similarity"] + 0.10 * rca_pool["Field Observation Similarity"]
            rca_pool = rca_pool.sort_values("CBR Similarity", ascending=False).reset_index(drop=True)
        evidence = retrieve_rca_evidence(rca_pool, global_tables, condition_result=condition)
    else:
        evidence = blank_rca_evidence()

    active_state_for_priority = condition["overall_state"] if op_context.get("diagnosis_allowed", False) else "NORMAL"
    priority, urgency = prioritize_action(active_state_for_priority, impact["consequence_class"], ASSET_CRITICALITY.get(tag,"MEDIUM"))
    ticket = make_problem_tank_ticket(asset, op_context, condition, impact, priority, evidence, similar, global_tables, operator_input)

    log_retrieval_and_action(tag, query, similar, impact, condition, priority, urgency, evidence, ticket)
    aux_stat = pd.DataFrame()  # Legacy executive statistical context is not recomputed; canonical executive layer reads cached traces
    operator_state = condition["overall_state"] if op_context.get("diagnosis_allowed", False) else op_context.get("status", "DATA_GAP")
    return {
        "tag_number": tag, "asset": asset, "condition": condition, "forecasts": forecasts,
        "similar_incidents": similar, "impact": impact, "rca_evidence": evidence,
        "priority": priority, "urgency": urgency, "ticket": ticket,
        "operator_input": operator_input, "operating_context": op_context, "operator_state": operator_state,
        "triggers": triggers, "observed_availability": asset["observed_availability"],
        "engineering_margin": condition["engineering_margin"], "condition_index": condition["condition_index"],
        "overall_state": condition["overall_state"], "aux_hourly_stat": aux_stat,
    }

# ==============================================================================
# PHASE 8: CROSS-ASSET SUMMARY
# ==============================================================================
def _nearest_trip_ptt_text(result):
    """Return the nearest trip PTT across all parameters for the console summary."""
    candidates = []
    has_hourly = False
    has_weekly = False
    invalid = False
    for f in result.get("forecasts", {}).values():
        if not f.get("ptt_valid", True) and f.get("time_to_trip") != 0:
            invalid = True
            continue
        cadence = f.get("cadence")
        t = f.get("time_to_trip")
        if cadence == "hourly":
            has_hourly = True
            if t is not None:
                candidates.append((float(t), f"{int(t)} h"))
        elif cadence == "weekly":
            has_weekly = True
            if t is not None:
                # Convert only for comparison; display remains weekly.
                candidates.append((float(t) * 168.0, f"{int(t)} wk"))
    if candidates:
        return min(candidates, key=lambda x: x[0])[1]
    if invalid:
        return "MODEL_NOT_ESTIMABLE"
    if has_hourly:
        return f">{HOURLY_TTT_HORIZON_HOURS} h"
    if has_weekly:
        return f">{WEEKLY_FORECAST_WEEKS} wk"
    return "-"


def cross_asset_summary(results):
    """Operator summary: what needs attention, not every internal calculation."""
    display_rank = {"TRIP": 6, "ALARM": 5, "WATCH": 4, "DATA_GAP": 4, "STALE_WEEKLY": 3, "STALE": 2, "OFF": 1, "NOT_RUNNING": 1, "NORMAL": 0}
    ordered = sorted(
        results,
        key=lambda r: (
            -display_rank.get(r.get("operator_state"), 0),
            PRIORITY_RANK.get(r["priority"], 9),
            -safe_float(r["condition_index"], 0),
        ),
    )

    log("\n" + "=" * 104)
    log("PLANT-WIDE OPERATOR STATUS")
    log("=" * 104)
    log(f"{'Rank':<5}{'Asset':<12}{'Op.Status':<13}{'State':<11}{'Priority':<10}{'PTT Trip':<12}{'Trigger':<28}{'Ticket':<18}")
    log("-" * 104)
    for i, r in enumerate(ordered, 1):
        op = r.get("operating_context", {})
        op_status = op.get("status", "-")
        state = r.get("operator_state", r.get("overall_state", "-"))
        ptt = _nearest_trip_ptt_text(r) if op_status == "RUNNING" else "-"
        trigger = trigger_short_text(r.get("triggers", [])) if op_status == "RUNNING" else op.get("reason", "")
        ticket = r["ticket"].get("ticket_id") or "-"
        log(f"{i:<5}{r['tag_number']:<12}{op_status:<13}{state:<11}{r['priority']:<10}{ptt:<12}{trigger[:27]:<28}{ticket:<18}")

    log("\nDATA AS OF (independent historical snapshots; not simultaneous plant status)")
    for r in ordered:
        c = r["condition"]
        log(f"{r['tag_number']}: condition={c['current_time']} [{c['mode']}] | operating={r['operating_context'].get('latest_time')} | {c.get('model_note', 'Hourly engineering + MSPC/EWMA')}")
    log("PTT > horizon = no modeled crossing; MODEL_NOT_ESTIMABLE is an audit status, not a numeric prediction.")
    ensure_output_dir()
    pd.DataFrame([
        {
            "Asset": r["tag_number"],
            "Operating Data As Of": r.get("operating_context", {}).get("latest_time"),
            "Virtual Hourly As Of": r["condition"].get("virtual_sensors",{}).get("as_of"),
            "Measured Condition State": r["condition"].get("measured_overall_state",r["overall_state"]),
            "Virtual Advisory": "; ".join(r["condition"].get("virtual_sensors",{}).get("watch_names",[])),
            "Data As Of": r["condition"]["current_time"],
            "Condition Cadence": r["condition"]["mode"],
            "Model Note": r["condition"].get("model_note", ""),
            "Operating Status": r.get("operating_context", {}).get("status"),
            "State": r.get("operator_state"),
            "Priority": r["priority"],
            "Trigger": trigger_short_text(r.get("triggers", [])),
            "Condition Index": r["condition_index"],
            "Engineering Margin (%)": r["engineering_margin"],
            "Observed Availability (%)": r["observed_availability"],
            "Nearest PTT Trip": _nearest_trip_ptt_text(r),
            "Similarity-weighted Downtime (h)": r["impact"]["downtime"],
            "Similarity-weighted Loss (kUS$)": r["impact"]["loss"],
            "Consequence Class": r["impact"]["consequence_class"],
            "Probable RCA": r["rca_evidence"].get("matched_ar") if r.get("operator_state") in {"WATCH", "ALARM", "TRIP"} else None,
            "Evidence Strength": r["rca_evidence"].get("evidence_strength") if r.get("operator_state") in {"WATCH", "ALARM", "TRIP"} else None,
            "Ticket": r["ticket"].get("ticket_id"),
            "Ticket State": r["ticket"].get("ticket_state", r["ticket"].get("status")),
            "Action Status": r["ticket"].get("action_status", "NOT_STARTED"),
        }
        for r in ordered
    ]).to_csv(os.path.join(OUTPUT_DIR, "cross_asset_summary.csv"), index=False)
    return ordered


def print_attention_details(results):
    attention = [r for r in results if r.get("operator_state") in {"WATCH", "ALARM", "TRIP", "DATA_GAP", "STALE_WEEKLY", "STALE", "OFF", "NOT_RUNNING"}]
    if not attention:
        log("\nNo active condition trigger on available measurements. Review data/model coverage notes above.")
        return

    log("\n" + "=" * 104)
    log("ATTENTION DETAILS")
    log("=" * 104)
    for r in attention:
        tag = r["tag_number"]
        op = r.get("operating_context", {})
        log(f"\n{tag} | {r.get('operator_state')} | Priority {r.get('priority')}")
        log("-" * 104)

        if op.get("status") != "RUNNING":
            log(f"Diagnosis suspended: {op.get('reason', 'operating status not suitable for RCA')}")
            if pd.notna(op.get("latest_time")):
                log(f"Latest hourly timestamp: {pd.Timestamp(op['latest_time'])}")
            continue

        triggers = r.get("triggers", [])
        if triggers:
            log("Current trigger:")
            for t in triggers[:4]:
                if t["type"] == "ENGINEERING_LIMIT":
                    dev = t.get("deviation_from_alarm")
                    dev_txt = f" | deviation from alarm={dev:+.3g} {t.get('unit','')}" if pd.notna(dev) else ""
                    log(
                        f"  - {t['parameter']}: {t.get('value'):.3g} {t.get('unit','')} | {t.get('state')} | "
                        f"alarm/trip={t.get('alarm'):.3g}/{t.get('trip'):.3g}{dev_txt} | consecutive={t.get('consecutive',0)}"
                    )
                elif t["type"] == "EWMA_DRIFT":
                    log(f"  - {t['parameter']}: persistent {t.get('state')} drift | current={t.get('value'):.3g} {t.get('unit','')}")
                elif t["type"] == "VIRTUAL_ADVISORY":
                    log(f"  - {t['source_kind']} {t['parameter']}: {t['value']:.4g} {t['unit']} | WATCH | verification required")
                else:
                    contrib = ", ".join(f"{c} {'HIGH' if z > 0 else 'LOW'}" for c, z in t.get("contributors", [])[:3])
                    log(f"  - Multivariate anomaly: {t.get('state')} | CI={safe_float(t.get('condition_index')):.2f} | contributors={contrib}")
        else:
            log("Current trigger: no active trigger")

        ev = r.get("rca_evidence", {})
        candidates = ev.get("candidates", [])
        if candidates:
            log("Probable RCA candidates (AI decision support; operator/engineer verification required):")
            for i, c in enumerate(candidates, 1):
                log(f"  {i}. {c['AR No']} | evidence={c['Evidence Strength']} | case similarity={c['Case Similarity']*100:.1f}%")
                log(f"     {str(c['Root Cause'])[:180]}")
                consistent = [x for x in c.get("Priority Causes", []) if x.get("CurrentEvidenceStatus") == "CONSISTENT"]
                if consistent:
                    log("     Current evidence consistent with: " + "; ".join(f"{x.get('ID')} {x.get('Description')}" for x in consistent[:3]))
                notobs = [x for x in c.get("Verification 4P", []) if x.get("CurrentEvidenceStatus") == "NOT_OBSERVABLE"]
                if notobs:
                    log("     Historical-only evidence requiring field/other data: " + "; ".join(f"{x.get('ID')} {x.get('Factor')}" for x in notobs[:2]))
            systemic = ev.get("systemic_hypotheses", [])
            if systemic:
                log("Systemic hypotheses from historical 4M (not confirmed by sensors):")
                for x in systemic[:3]:
                    log(f"  - {x.get('ID')}: {x.get('Factor')} — {str(x.get('Evidence'))[:130]}")
        else:
            log("Probable RCA: no active RCA candidate generated.")

        actions = r.get("ticket", {}).get("actions", [])
        if actions:
            log("Recommended current follow-up:")
            for i, a in enumerate(actions, 1):
                log(f"  {i}. [{a.get('Type')}] {a.get('Plan')}")
                log(f"     Owner role={a.get('SuggestedOwner')} | SLA={a.get('SLA')} | status={a.get('CurrentStatus')}")
        ticket = r.get("ticket", {})
        if ticket.get("ticket_id"):
            log(f"Problem Tank: {ticket.get('ticket_id')} | {ticket.get('status')} | owner={ticket.get('owner')}")
            if not ticket.get("operator_decision"):
                log("Operator confirmation: pending (ACKNOWLEDGE / CONFIRM_RCA / REJECT_RCA / REQUEST_REVIEW).")


# ==============================================================================
# WEEKLY -> HOURLY CONTEXT ALIGNMENT (VISUALIZATION ONLY)
# ==============================================================================
def interpolate_weekly_to_hourly_context(df_weekly, params, hourly_timestamps):
    """
    Context-only interpolation. This does not create a new measurement.
    Within the observed range: time interpolation. Outside the range: nearest-edge hold.
    """
    hourly_index = pd.DatetimeIndex(pd.to_datetime(hourly_timestamps)).sort_values()
    out = pd.DataFrame({"Timestamp": hourly_index})
    if len(hourly_index) == 0:
        return out

    for p in params:
        if p not in df_weekly.columns:
            out[p] = np.nan
            continue
        s2 = df_weekly[["Date", p]].dropna().drop_duplicates("Date").set_index("Date")[p].sort_index()
        if s2.empty:
            out[p] = np.nan
            continue
        union = s2.index.union(hourly_index).sort_values()
        interp = s2.reindex(union).interpolate(method="time").ffill().bfill()
        out[p] = interp.reindex(hourly_index).values
    return out


# ==============================================================================
# PLOT HELPERS
# ==============================================================================
def _format_time_axis(ax, weekly=False):
    if weekly:
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    else:
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%b"))
    ax.tick_params(axis="x", rotation=30)


def _annotate_state(ax, state, source_label, model_label=None):
    txt = f"State: {state}\nSource: {source_label}"
    if model_label:
        txt += f"\nForecast: {model_label}"
    ax.text(
        0.985, 0.96, txt,
        transform=ax.transAxes,
        ha="right", va="top", fontsize=8,
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=condition_state_color(state), alpha=0.85),
    )

def _plot_parameter_series(ax, hist_t, hist_y, fut_t, fut_y, param, lim, state, source_label, model_label, unit):
    ax.plot(hist_t, hist_y, linewidth=1.5, label="History")
    if len(fut_t) and len(fut_y):
        ax.plot(fut_t, fut_y, linestyle="--", linewidth=1.6, label="Forecast")
    if lim is not None:
        ax.axhline(lim["alarm"], linestyle="--", linewidth=1.0, label="Alarm")
        ax.axhline(lim["trip"], linestyle=":", linewidth=1.2, label="Trip")
    ax.set_title(param, fontsize=10, fontweight="bold")
    ax.set_ylabel(str(unit))
    ax.grid(False)
    ax.legend(fontsize=7, loc="best")
    _annotate_state(ax, state, source_label, model_label)


# ==============================================================================
# PLOT 1: 5 FIGURE HOURLY x 4 PARAMETER
# ==============================================================================
def plot_all_assets_hourly_legacy(results):
    detail_log("\n" + "=" * 110)
    detail_log("📊 [PLOT 1] HOURLY CONDITION MONITORING — 5 ASSETS × 4 PARAMETERS")
    detail_log("   History: 7 hari | Forecast visual: 3 hari")
    detail_log("=" * 110)

    for r in results:
        asset = r["asset"]
        tag = r["tag_number"]
        df_h = asset["df_hourly"].copy()
        df_w = asset["df_weekly"].copy()
        limits = build_limit_dict(asset["df_limits"])
        params = list(limits.keys())[:4]

        last_time = df_h["Timestamp"].max()
        hist_start = last_time - pd.Timedelta(days=HOURLY_PLOT_DAYS)
        hts = pd.date_range(hist_start, last_time, freq="1h")
        weekly_context = interpolate_weekly_to_hourly_context(df_w, params, hts)

        fig, axes = plt.subplots(2, 2, figsize=(15, 9), squeeze=False)
        axes = axes.ravel()
        fig.suptitle(
            f"{tag} — HOURLY CONDITION MONITORING\n"
            "Actual hourly where semantically mapped; Weekly-aligned context otherwise",
            fontsize=14, fontweight="bold",
        )

        for ax, p in zip(axes, params):
            lim = limits[p]
            suffix = asset["cfg"].get("hourly_param_map", {}).get(p)
            direct_ok = suffix in df_h.columns if suffix else False

            if direct_ok:
                hist = df_h[df_h["Timestamp"].between(hist_start, last_time)][["Timestamp", suffix]].dropna()
                source = f"Actual Hourly ({suffix})"
                fmodel = r["forecasts"].get(p)
                if fmodel is None:
                    series = calendar_forecast_series(asset, suffix, last_time, "hourly")
                    fmodel = validated_forecast(series, HOURLY_TTT_HORIZON_HOURS, cadence="hourly")
                fut_t = pd.date_range(last_time + pd.Timedelta(hours=1), periods=HOURLY_FORECAST_HOURS, freq="1h")
                fut_y = fmodel["forecast"][:HOURLY_FORECAST_HOURS]
                current_state = directional_engineering_state(hist[suffix].iloc[-1], lim) if not hist.empty else "NORMAL"
                model_label = f"{fmodel['model']} | MAE={fmodel['mae']:.3g}" if pd.notna(fmodel["mae"]) else fmodel["model"]
                hist_t, hist_y = hist["Timestamp"], hist[suffix]
            else:
                # Weekly-aligned context only.
                context_end = df_w["Date"].max()
                context_times = pd.date_range(context_end-pd.Timedelta(days=HOURLY_PLOT_DAYS), context_end, freq="1h")
                context = interpolate_weekly_to_hourly_context(df_w, [p], context_times)
                hist = context[["Timestamp", p]].dropna()
                source = "Weekly→Hourly aligned context"
                wf = r["forecasts"].get(p) if r["condition"]["mode"] == "weekly" else None
                if wf is None:
                    wf = validated_forecast(calendar_forecast_series(asset, p, df_w["Date"].max(), "weekly"), WEEKLY_FORECAST_WEEKS, cadence="weekly")
                # Convert weekly predictions to hourly line across 3-day visual horizon.
                weekly_future_dates = pd.date_range(df_w["Date"].max() + pd.Timedelta(weeks=1), periods=WEEKLY_FORECAST_WEEKS, freq="7D")
                s = pd.Series(wf["forecast"], index=weekly_future_dates)
                fut_t = pd.date_range(context_end + pd.Timedelta(hours=1), periods=HOURLY_FORECAST_HOURS, freq="1h")
                s = pd.concat([pd.Series([df_w[p].iloc[-1]], index=[context_end]), s])
                union = s.index.union(pd.DatetimeIndex(fut_t)).sort_values()
                interp = s.reindex(union).interpolate(method="time").ffill().bfill()
                fut_y = interp.reindex(fut_t).values
                current_state = directional_engineering_state(hist[p].iloc[-1], lim) if not hist.empty else "NORMAL"
                model_label = f"Weekly {wf['model']} | MAE={wf['mae']:.3g}" if pd.notna(wf["mae"]) else f"Weekly {wf['model']}"
                hist_t, hist_y = hist["Timestamp"], hist[p]

            _plot_parameter_series(
                ax, hist_t, hist_y, fut_t, fut_y, p, lim, current_state,
                source, model_label, lim["unit"]
            )
            _format_time_axis(ax, weekly=False)

        plt.tight_layout(rect=[0, 0.02, 1, 0.94])
        if SAVE_PLOTS:
            ensure_output_dir()
            fig.savefig(os.path.join(OUTPUT_DIR, f"PLOT1_HOURLY_{tag}.png"), dpi=160, bbox_inches="tight")
        if SHOW_PLOTS: plt.show()
        plt.close(fig)
        detail_log(f"  ✅ {tag}: 4 subplot Hourly/context plotted.")


# ==============================================================================
# PLOT 2: 5 FIGURE WEEKLY x 4 PARAMETER
# ==============================================================================


# ==============================================================================
# PLOT 3: EXECUTIVE SINGLE PANE (5 BAR + 3 LINE)
# ==============================================================================
def _bar_snapshot(ax, values, labels, title, ylabel, fmt):
    values = np.asarray(values, dtype=float)
    bars = ax.bar(labels, values)
    ax.set_title(title, fontweight="bold", fontsize=10)
    ax.set_ylabel(ylabel)
    for i,v in enumerate(values):
        if not np.isfinite(v):
            ax.text(i, 0, "DATA_GAP", ha="center", va="bottom", fontsize=8)
    ax.grid(False)
    ax.tick_params(axis="x", rotation=25)
    finite = values[np.isfinite(values)]
    if len(finite):
        span = np.nanmax(finite) - np.nanmin(finite)
        pad = max(abs(np.nanmax(finite)) * 0.05, span * 0.08, 0.01)
        ax.set_ylim(top=max(ax.get_ylim()[1], np.nanmax(finite)+3*pad))
        for b, v in zip(bars, values):
            if np.isfinite(v):
                ax.text(b.get_x() + b.get_width()/2, v + pad*0.15, fmt(v), ha="center", va="bottom", fontsize=8)


def build_single_pane_line_data(results):
    out = {}
    for r in results:
        asset = r["asset"]
        df = asset["df_hourly"].copy()
        last = df["Timestamp"].max()
        start = last - pd.Timedelta(days=SINGLE_PANE_LINE_DAYS)
        df = df[df["Timestamp"] >= start].copy()

        df["Production Rate"] = pd.to_numeric(df["PLANT_RATE"], errors="coerce") if "PLANT_RATE" in df.columns else np.nan
        if "AMP" in df.columns and asset["fla"] > 0:
            df["Electrical Load Index"] = 100.0 * pd.to_numeric(df["AMP"], errors="coerce") / asset["fla"]
        else:
            df["Electrical Load Index"] = np.nan

        stat = r.get("aux_hourly_stat", pd.DataFrame())
        if stat is not None and not stat.empty:
            df = df.merge(stat[["Timestamp", "AnomalyIndex"]], on="Timestamp", how="left")
        else:
            df["AnomalyIndex"] = np.nan

        out[r["tag_number"]] = df
    return out


def _plot_single_pane_line(ax, data_by_asset, metric, title, ylabel):
    plotted = 0
    for tag, df in data_by_asset.items():
        if metric not in df.columns:
            continue
        series = df[["Timestamp", metric]].copy()
        series[metric] = pd.to_numeric(series[metric], errors="coerce")
        series = series.dropna()
        if series.empty:
            continue
        daily = series.set_index("Timestamp")[metric].resample("1D").mean().dropna()
        if daily.empty:
            continue
        ax.plot(daily.index, daily.values, linewidth=1.6, marker="o", markersize=2.6, label=tag)
        plotted += 1
    ax.set_title(title, fontweight="bold", fontsize=10)
    ax.set_ylabel(ylabel)
    ax.grid(False)
    if plotted:
        ax.legend(fontsize=7, ncol=2)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=6))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%b"))
    ax.tick_params(axis="x", rotation=30)




# ==============================================================================
# PHASE 9: HISTORICAL INCIDENT REPLAY (TIME-AWARE VALIDATION)
# ==============================================================================
def _replay_hourly_asset(asset, global_tables, incident_row):
    return replay_one_event(asset,global_tables,incident_row)

def _replay_weekly_asset(asset, global_tables, incident_row):
    return replay_one_event(asset,global_tables,incident_row)

def historical_replay_validation(assets, global_tables):
    rows, normal_rows = [], []
    inc = global_tables["incident"]
    log("\nHISTORICAL REPLAY — chronological, pre-event alerts, strict historical knowledge")
    for asset in assets:
        events = inc[inc["Tag Number"].astype(str)==asset["tag_number"]].sort_values("Date of Occur.")
        for _,event in events.iterrows():
            row = replay_one_event(asset,global_tables,event)
            rows.append(row)
            log(f"{row['Asset']}: early={row['Detected']} | first={row['First Pre-event Alert']} | event-day={row['Detected State']} | eligible={row['Eligible Mechanism Candidates']}")
        # Sample presumed normal periods, excluding event neighborhoods; labels are not ground truth.
        weekly = asset["cfg"]["core_mode"] == "weekly"
        df = asset["df_weekly"].copy() if weekly else asset["df_hourly"].copy()
        tc = "Date" if weekly else "Timestamp"
        for dt in events["Date of Occur."].dropna():
            df = df[~df[tc].between(dt-pd.Timedelta(days=7),dt+pd.Timedelta(days=7))]
        if weekly and "Health Status" in df:
            df=df[df["Health Status"].astype(str).str.upper().eq("NORMAL")]
        if not weekly:
            df=df[df["Is_Running"].eq(1)]
        sample = df.iloc[np.unique(np.linspace(0,len(df)-1,min(REPLAY_NORMAL_CHECKS,len(df))).astype(int))] if len(df) else df
        for t in sample[tc]:
            try:
                tables=time_scoped_knowledge({**global_tables,"strict_replay":True},t)
                c=evaluate_asset_condition(asset,tables,eval_time=t)
                normal_rows.append({"Asset":asset["tag_number"],"Time":t,"State":c["overall_state"],
                                    "Statistical Available":c.get("statistical_available",True)})
            except Exception:
                normal_rows.append({"Asset":asset["tag_number"],"Time":t,"State":"DATA_GAP","Statistical Available":False})
    out=pd.DataFrame(rows)
    ensure_output_dir()
    out.to_csv(os.path.join(OUTPUT_DIR,"historical_replay_validation.csv"),index=False)
    pd.DataFrame(normal_rows).to_csv(os.path.join(OUTPUT_DIR,"presumed_normal_sample_validation.csv"),index=False)
    inc[["Incident Key","F Mechanism Raw","F Mechanism","Mechanism Normalization"]].to_csv(os.path.join(OUTPUT_DIR,"mechanism_label_audit.csv"),index=False)
    if not out.empty:
        n=int(out["Evaluable Pre-event Samples"].gt(0).sum())
        eligible=out["Mechanism Hit@1"].notna()
        log(f"Early detection: {int(out['Detected'].sum())}/{n} evaluable incidents (total={len(out)})")
        log(f"Normalized-label retrieval Hit@1: {int(out.loc[eligible,'Mechanism Hit@1'].sum())}/{int(eligible.sum())}; Hit@3: {int(out.loc[eligible,'Mechanism Hit@3'].sum())}/{int(eligible.sum())}; ineligible excluded")
    valid=[r for r in normal_rows if r['State'] in STATE_RANK]
    alerts=sum(r['State']!='NORMAL' for r in valid)
    log(f"Sampled presumed-normal alerts: {alerts}/{len(valid)}; descriptive only, not validated false-positive rate.")
    return out

# ==============================================================================
# PROBLEM TANK SNAPSHOT EXPORT
# ==============================================================================
def export_problem_tank(results):
    rows = []
    for r in results:
        t = r["ticket"]
        rows.append({
            "Asset": r["tag_number"],
            "Operating Data As Of": r.get("operating_context", {}).get("latest_time"),
            "Virtual Hourly As Of": r["condition"].get("virtual_sensors",{}).get("as_of"),
            "Measured Condition State": r["condition"].get("measured_overall_state",r["overall_state"]),
            "Virtual Advisory": "; ".join(r["condition"].get("virtual_sensors",{}).get("watch_names",[])),
            "Data As Of": r["condition"]["current_time"],
            "Condition Cadence": r["condition"]["mode"],
            "Model Note": r["condition"].get("model_note", ""),
            "Operating Status": r.get("operating_context", {}).get("status"),
            "Condition State": r.get("operator_state"),
            "Condition Index": r["condition_index"],
            "Consequence Class": r["impact"]["consequence_class"],
            "Priority": r["priority"],
            "Ticket Required": t["ticket_required"],
            "Ticket ID": t["ticket_id"],
            "Owner Role": t["owner"],
            "Ticket State": t.get("ticket_state", t.get("status")),
            "Action Status": t.get("action_status", "NOT_STARTED"),
            "Probable RCA": r["rca_evidence"].get("matched_ar"),
            "Evidence Strength": r["rca_evidence"].get("evidence_strength"),
            "Historical Analog Downtime (h)": r["impact"]["downtime"],
            "Historical Analog Loss (kUS$)": r["impact"]["loss"],
            "Operator Decision": t.get("operator_decision"),
        })
    ensure_output_dir()
    pd.DataFrame(rows).to_csv(os.path.join(OUTPUT_DIR, "problem_tank_snapshot.csv"), index=False)


def export_operator_confirmation_queue(results, existing_df=None):
    """Human-in-the-loop queue. Existing operator entries are preserved by Asset."""
    existing_df = existing_df if existing_df is not None else pd.DataFrame()
    existing_map = {}
    if not existing_df.empty and "Asset" in existing_df.columns:
        existing_map = {str(r["Asset"]): r for _, r in existing_df.iterrows()}

    rows = []
    for r in results:
        if r.get("operator_state") not in {"WATCH", "ALARM", "TRIP"} and not r.get("ticket", {}).get("ticket_id"):
            continue
        tag = r["tag_number"]
        old = existing_map.get(tag, {})
        ev = r.get("rca_evidence", {})
        rows.append({
            "Asset": tag,
            "Ticket ID": r.get("ticket", {}).get("ticket_id"),
            "Current State": r.get("operator_state"),
            "Probable RCA": ev.get("matched_ar"),
            "Evidence Strength": ev.get("evidence_strength"),
            "Decision": old.get("Decision", ""),
            "Operator": old.get("Operator", ""),
            "Visible Leakage": old.get("Visible Leakage", ""),
            "Abnormal Noise": old.get("Abnormal Noise", ""),
            "Abnormal Vibration": old.get("Abnormal Vibration", ""),
            "Local Temperature Confirmed": old.get("Local Temperature Confirmed", ""),
            "Field Observation": old.get("Field Observation", ""),
            "Comment": old.get("Comment", ""),
            "Updated At": old.get("Updated At", ""),
            "Owner Role": old.get("Owner Role", r.get("ticket", {}).get("owner", "")),
            "Action Status": old.get("Action Status", r.get("ticket", {}).get("action_status", "NOT_STARTED")),
            "Allowed Decisions": "ACKNOWLEDGE | CONFIRM_RCA | REJECT_RCA | REQUEST_REVIEW | CLOSE_TICKET",
        })
    ensure_output_dir()
    pd.DataFrame(rows).to_csv(OPERATOR_INPUT_FILE, index=False)


def interactive_operator_confirmation(results):
    if not INTERACTIVE_OPERATOR_MODE:
        return
    for r in results:
        if r.get("operator_state") not in {"WATCH", "ALARM", "TRIP"}:
            continue
        log(f"\nOperator confirmation for {r['tag_number']} ({r['operator_state']}):")
        log("Options: ACKNOWLEDGE / CONFIRM_RCA / REJECT_RCA / REQUEST_REVIEW")
        decision = input("Decision: ").strip().upper()
        if decision:
            log(f"Decision recorded for this run: {decision}. Re-run after saving to operator queue for persistent update.")


# ==============================================================================
# MAIN
# ==============================================================================
def healthy_rows(frame, limits, parameter_map):
    """Keep finite observations inside engineering alarm limits; no outcome labels inferred."""
    valid = pd.Series(True, index=frame.index)
    for p, col in parameter_map.items():
        if p not in limits or col not in frame:
            continue
        values = pd.to_numeric(frame[col], errors="coerce")
        lim = limits[p]
        valid &= values.notna() & (values.lt(lim["alarm"]) if lim["direction"] == "high" else values.gt(lim["alarm"]))
    return frame.loc[valid].copy()

def canonical_mechanism(row):
    """Conservative derived evaluation label; original label remains in the export.

    These rules harmonize symptoms, not verified causal mechanisms. They must not
    be interpreted as a new confirmed RCA or used as input to the sensor model.
    """
    raw = normalize_text(row.get("F Mechanism", ""))
    if raw and raw not in {"high", "mechanical", "motor", "nan"}:
        return raw
    title = normalize_text(row.get("Risk Case Title", ""))
    for tokens, label in [(("fouling",), "fouling"),
                          (("vibration",), "high vibration"),
                          (("overheat",), "overheat"),
                          (("leak",), "leakage")]:
        if any(token in title for token in tokens):
            return label
    return "unclassified"

def time_scoped_knowledge(tables, cutoff):
    """Incident dates are day-level: conservatively available from the next day.

    Strict replay never consumes undated RCA findings. For the ordinary historical
    snapshot, supplied RCA is an undated advisory reference, not a validated as-of
    knowledge base. Add 'RCA Available At' to RCA Header to enable strict access.
    """
    out = dict(tables)
    cutoff = pd.Timestamp(cutoff)
    inc = tables["incident"].copy()
    available = pd.to_datetime(inc["Date of Occur."], errors="coerce").dt.normalize()+pd.Timedelta(days=1)
    out["incident"] = inc.loc[available <= cutoff].copy()
    ars = set(out["incident"]["AR No"].dropna().astype(str))
    hdr = tables.get("rca_header", pd.DataFrame()).copy()
    if not hdr.empty:
        hdr = hdr[hdr["AR No"].astype(str).isin(ars)]
        if "RCA Available At" in hdr:
            hdr = hdr[pd.to_datetime(hdr["RCA Available At"], errors="coerce") <= cutoff]
        elif tables.get("strict_replay", False):
            hdr = hdr.iloc[:0]
    out["rca_header"] = hdr
    valid = set(hdr.get("AR No", pd.Series(dtype=object)).astype(str))
    for key in ("rca_priority", "rca_4p", "rca_4m", "rca_capa"):
        df = tables.get(key, pd.DataFrame())
        out[key] = df[df["AR No"].astype(str).isin(valid)].copy() if not df.empty else df.copy()
    return out

def calendar_forecast_series(asset, parameter, cutoff, cadence):
    """A model step is a real hour/week. Never collapse shutdowns or missing weeks.

    Use the latest contiguous observed operating segment; restart after repair.
    Limited data retain a display-only persistence forecast, with PTT marked MODEL_NOT_ESTIMABLE.
    """
    if cadence == "hourly":
        df = asset["df_hourly_observed"]
        df = df[df["Timestamp"] <= cutoff].copy()
        if df.empty:
            return pd.Series(dtype=float)
        idx = pd.date_range(df["Timestamp"].min(), df["Timestamp"].max(), freq="1h")
        x = df.set_index("Timestamp").reindex(idx)
        running = x["RUN_STATUS"].astype(str).str.upper().eq("ON")
        if "AMP" in x:
            running &= x["AMP"].gt(0.1*asset["fla"])
        series = pd.to_numeric(x[parameter], errors="coerce").where(running)
        max_rows = BASELINE_DAYS*24
    else:
        df = asset["df_weekly"]
        df = df[df["Date"] <= cutoff].copy()
        if df.empty:
            return pd.Series(dtype=float)
        repair = df.get("Remark", pd.Series("", index=df.index)).fillna("").str.contains(
            r"post[- ]repair|baseline restored|post[- ]maintenance", case=False, regex=True)
        if repair.any():
            df = df[df["Date"] >= df.loc[repair, "Date"].max()]
        series = df.set_index("Date")[parameter].reindex(pd.date_range(df["Date"].min(), df["Date"].max(), freq="7D"))
        max_rows = len(series)
    gaps = np.flatnonzero(series.isna().to_numpy())
    if len(gaps):
        series = series.iloc[gaps[-1]+1:]
    return series.tail(max_rows).astype(float)

def replay_one_event(asset, global_tables, incident_row):
    """Sequential condition evaluations, using exactly the production persistence rule.

    Only pre-event-day samples establish early detection because event time is unknown.
    Event-day results are reported separately and cannot inflate early-detection recall.
    """
    weekly = asset["cfg"]["core_mode"] == "weekly"
    frame = asset["df_weekly"] if weekly else asset["df_hourly"]
    tc = "Date" if weekly else "Timestamp"
    event = pd.Timestamp(incident_row["Date of Occur."]).normalize()
    lo = event - (pd.Timedelta(weeks=4) if weekly else pd.Timedelta(hours=REPLAY_LOOKBACK_HOURS))
    times = frame.loc[frame[tc].between(lo, event+pd.Timedelta(days=1), inclusive="left"),tc].drop_duplicates().sort_values()
    if not weekly:
        times = times.iloc[::REPLAY_GRID_HOURS]
    records, conditions = [], {}
    for t in times:
        tables = time_scoped_knowledge({**global_tables,"strict_replay":True},t)
        try:
            if not weekly:
                row = frame.loc[frame[tc]==t].iloc[-1]
                if row.get("Is_Running",0) != 1:
                    records.append({"Timestamp":t,"State":"OFF","Error":""})
                    continue
            cond = evaluate_asset_condition(asset,tables,eval_time=t)
            if pd.Timestamp(cond["current_time"]) != t:
                continue
            conditions[t] = cond
            records.append({"Timestamp":t,"State":cond["overall_state"],"Error":""})
        except Exception as e:
            records.append({"Timestamp":t,"State":"DATA_GAP","Error":str(e)})
    records_df = pd.DataFrame(records,columns=["Timestamp","State","Error"])
    pre = records_df[records_df["Timestamp"] < event]
    alarms = pre[pre["State"].isin(["WATCH","ALARM","TRIP"])]
    first = alarms["Timestamp"].min() if not alarms.empty else pd.NaT
    day = records_df[records_df["Timestamp"] >= event]
    day_states = day.loc[day["State"].isin(STATE_RANK),"State"].tolist()
    pre_valid = pre[pre["State"].isin(STATE_RANK)]
    retrieval_t = first if pd.notna(first) else (pre_valid["Timestamp"].max() if not pre_valid.empty else pd.NaT)
    hit1 = hit3 = np.nan
    eligible = 0
    topkey = None
    if pd.notna(retrieval_t):
        cond = conditions[retrieval_t]
        tables = time_scoped_knowledge({**global_tables,"strict_replay":True},retrieval_t)
        # Date-scoped corpus, no current incident, no future/undated RCA fields.
        _,sim = retrieve_similar_incidents(asset,cond,tables,exclude_ar=incident_row["AR No"],top_k=TOP_K_SIMILAR)
        target = normalize_text(incident_row["F Mechanism"])
        pool = tables["incident"]
        pool = pool[pool["AR No"].astype(str) != str(incident_row["AR No"])]
        eligible = int(pool["F Mechanism"].map(normalize_text).eq(target).sum()) if target != "unclassified" else 0
        if not sim.empty:
            topkey = sim.iloc[0].get("Incident Key")
        if eligible:
            mech = sim.get("F Mechanism",pd.Series(dtype=object)).map(normalize_text)
            hit1 = bool(len(mech) and mech.iloc[0]==target)
            hit3 = bool(mech.head(3).eq(target).any())
    ensure_output_dir()
    records_df.to_csv(os.path.join(OUTPUT_DIR,f"replay_trace_{asset['tag_number']}.csv"),index=False)
    return {"Asset":asset["tag_number"],"Incident AR":incident_row["AR No"],"Incident Date":event,
            "Replay Eval Time":retrieval_t,"Detected State":state_max(*day_states) if day_states else "DATA_GAP",
            "First Alert in 48h Window":first,"First Pre-event Alert":first,
            "Detected":bool(pd.notna(first)),"Detected On Event Day":any(x != "NORMAL" for x in day_states),
            "Lead Time Lower Bound (h)":(event-first).total_seconds()/3600 if pd.notna(first) else np.nan,
            "Evaluable Pre-event Samples":len(pre_valid),"Unavailable Samples":int(records_df["State"].eq("DATA_GAP").sum()),
            "Eligible Mechanism Candidates":eligible,"Mechanism Hit@1":hit1,"Mechanism Hit@3":hit3,
            "Top Retrieval AR":topkey,"Mechanism Label":incident_row["F Mechanism"],
            "Note":"Day-level incident timestamp; early = strictly before event day; label-normalized retrieval is not RCA accuracy."}

# ==============================================================================
# V10.4 HYBRID HOURLY ESTIMATION — all outputs retain their target's native unit
# ==============================================================================
from scipy.optimize import brentq, nnls
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.svm import SVR

ENABLE_VIRTUAL_SENSORS = True  # Indirect hourly estimator is active and is reused by the canonical PF layer; no separate decision pipeline
HS_WEEKLY_RELEASE_DELAY_HOURS = 24  # Date-only lab data: explicit conservative assumption.
HS_WEEKLY_AVAILABLE_COLUMN = 'Available At'  # Optional per-row actual result-release timestamp.
HS_MAX_LABEL_AGE_HOURS = 14 * 24
HS_MIN_VALIDATION_POINTS = 3
HS_VALIDATION_WINDOW = 8
HS_REQUIRED_IMPROVEMENT = 0.05
HS_MIN_REGRESSION_ROWS = 8
HS_PAIR_WINDOW_HOURS = 1  # Use contemporaneous/backward hourly input, never future input.
HS_EMA_ALPHA = 0.3
HS_MEASUREMENT_REL_SD = 0.02  # Assumed instrument/lab noise until a measured SD is supplied.
HS_MEASUREMENT_SD = {}  # Optional {(asset, target): actual laboratory/instrument SD}.
HS_ALLOW_ESTIMATED_WATCH = False  # Estimated limit state is printed separately by default.
HS_CHEMISTRY_TARGETS = {'Lube Oil Water Content', 'Feed Heavy-ends', 'Coupling Offset'}

# Defaults deliberately do not assign physical identities/coefficients to generic tags.
# FEED is mass flow (t/h); never substitute it for suction/seal pressure.
HS_PHYSICS = {
    'PU-2101B': dict(verified=False, valid_from=None, seal_chamber_pressure_column=None,
                    seal_chamber_pressure_barg=None, flow_coefficient_L_min_sqrt_bar=None),
    'HE-3301': dict(verified=False, valid_from=None, cold_mass_flow_column='FEED',
                    mass_flow_unit='t/h', cp_cold_kJ_kg_K=None, design_duty_kW=None,
                    cold_inlet_temperature_column=None, cold_inlet_temperature_C=None,
                    hot_inlet_temperature_column=None, hot_inlet_temperature_C=None,
                    hot_outlet_temperature_column=None, hot_outlet_temperature_C=None,
                    UA_kW_K=None, density_kg_m3=None),
}
HS_WEEKLY_INPUTS = {
    'PU-2101B': {'DISP': 'Discharge Pressure', 'VIB': 'Overall Vibration', 'TEMP': 'Bearing Temp'},
    'KO-3201': {'TEMP': 'Bearing Metal Temp', 'VIB': 'DE Radial Vibration'},
    'PM-4405B': {'TEMP': 'Motor DE Bearing Temp', 'AMP': 'Motor Ampere', 'VIB': 'Motor Vibration'},
    'HE-3301': {},  # Cold Outlet Temp is NOT the generic HE TEMP channel.
    'BL-5702': {'TEMP': 'Bearing Temp', 'VIB': 'Overall Vibration'},
}
HS_STAT_FEATURES = {
    'Seal Flush Flow': ['DISP', 'VIB', 'TEMP'],
    'Lube Oil Supply Press': ['TEMP', 'VIB'],
    'Winding Temp': ['TEMP', 'AMP', 'AMP_SQ'],
    'Tube-side dP': ['FEED', 'DISP', 'TEMP'],
    'Heat Duty': ['FEED', 'DISP', 'TEMP'],
    'Cold Outlet Temp': ['FEED', 'DISP', 'TEMP'],
    '2X Harmonic': ['VIB', 'TEMP'],
}


def hs_observed_hours(asset):
    h = asset['df_hourly_observed'].copy().set_index('Timestamp').sort_index()
    h = h.loc[~h.index.duplicated(keep='last')]
    h = h.reindex(pd.date_range(h.index.min(), h.index.max(), freq='1h'))
    for c in h.columns:
        if c != 'RUN_STATUS': h[c] = pd.to_numeric(h[c], errors='coerce')
    h.index.name = 'Timestamp'
    return h


def hs_weekly(asset, target, cutoff):
    w = asset['df_weekly'].copy()
    if target not in w: return pd.DataFrame()
    w['Date'] = pd.to_datetime(w['Date'], errors='coerce')
    w['Available At'] = (pd.to_datetime(w[HS_WEEKLY_AVAILABLE_COLUMN], errors='coerce')
                         if HS_WEEKLY_AVAILABLE_COLUMN in w else
                         w['Date'] + pd.Timedelta(hours=HS_WEEKLY_RELEASE_DELAY_HOURS))
    # Reject a release before measurement; unknown release timestamps stay unavailable.
    w = w[w['Date'].notna() & w['Available At'].notna() &
          (w['Available At'] >= w['Date']) & (w['Available At'] <= cutoff)].copy()
    w[target] = pd.to_numeric(w[target], errors='coerce')
    w = w.dropna(subset=[target]).sort_values('Date').drop_duplicates('Date', keep='last')
    w['Repair'] = w.get('Remark', pd.Series('', index=w.index)).fillna('').str.contains(
        r'post[- ]repair|baseline restored|post[- ]maintenance', case=False, regex=True)
    # Late older samples need an out-of-sequence filter; they are not silently backdated.
    w = w.sort_values('Available At')
    keep = []; latest = pd.Timestamp.min
    for i, row in w.iterrows():
        if row['Date'] > latest: keep.append(i); latest = row['Date']
    return w.loc[keep].reset_index(drop=True)


def hs_covariates(asset, rows, h):
    """Precompute/cached weekly covariates; no repeated hourly-window aggregation."""
    if rows is None or rows.empty: return pd.DataFrame()
    dates = pd.to_datetime(rows['Date'], errors='coerce')
    releases = pd.to_datetime(rows.get('Available At', rows['Date']), errors='coerce')
    key=(tuple(dates.astype('int64').tolist()), tuple(releases.astype('int64').tolist()),
         pd.Timestamp(h.index.min()).value if len(h) else None, pd.Timestamp(h.index.max()).value if len(h) else None)
    cache=asset.setdefault('_weekly_covariates',{})
    if key in cache: return cache[key].copy()
    mapping=HS_WEEKLY_INPUTS[asset['tag_number']]
    out=[]
    # Weekly rows are few; the expensive hourly means are computed once and cached.
    for _,row in rows.iterrows():
        t=pd.Timestamp(row['Date'])
        sample=h.loc[(h.index>t-pd.Timedelta(hours=HS_PAIR_WINDOW_HOURS)) & (h.index<=t)]
        running=sample['RUN_STATUS'].astype(str).str.upper().eq('ON') if 'RUN_STATUS' in sample else pd.Series(True,index=sample.index)
        vals=sample.loc[running].select_dtypes(include=[np.number]).mean().to_dict()
        for name,column in mapping.items():
            if pd.notna(row.get(column)): vals[name]=float(row[column])
        vals['AMP_SQ']=vals.get('AMP',np.nan)**2; vals['Timestamp']=t; out.append(vals)
    result=pd.DataFrame(out).set_index('Timestamp') if out else pd.DataFrame()
    cache[key]=result.copy()
    return result



def hs_channel(query, cfg, key):
    column = cfg.get(key+'_column')
    if column in query: return pd.to_numeric(query[column], errors='coerce').to_numpy(float)
    value = safe_float(cfg.get(key+'_C', cfg.get(key+'_barg')))
    return np.full(len(query), value)


def hs_lmtd(a, b):
    if not np.isfinite(a+b) or min(a, b) <= 0: return np.nan
    if abs(a-b) < 1e-7 * max(a, b): return (a+b)/2
    return (a-b)/np.log(a/b)


def hs_heat_solution(mass_t_h, tc_in, th_in, th_out, cp, ua, unit):
    """Countercurrent exchanger, F=1. cp in kJ/(kg K), UA in kW/K, Q in kW."""
    flow = mass_t_h*1000/3600 if unit == 't/h' else mass_t_h if unit == 'kg/s' else np.nan
    if not np.isfinite(flow+tc_in+th_in+th_out+cp+ua) or min(flow, cp, ua) <= 0 or th_out <= tc_in or th_in <= tc_in:
        return np.nan, np.nan
    def residual(tout):
        return flow*cp*(tout-tc_in) - ua*hs_lmtd(th_in-tout, th_out-tc_in)
    try:
        tout = brentq(residual, tc_in, th_in-1e-7)
    except ValueError:
        return np.nan, np.nan
    return tout, flow*cp*(tout-tc_in)


def hs_fit_kalman(known, target, measurement_sd):
    """Causal local linear state [value, value/hour]. No smoother or random draws.

    Lab observations update the filter at measurement time; predictions are only
    published after release time. The chosen noise model is an assumption, not a
    certified confidence level. Innovation-driven Q only uses earlier innovations.
    """
    y = known[target].to_numpy(float); times = known['Date'].tolist()
    r = measurement_sd**2
    x = np.array([y[0], 0.]); p = np.diag([r, r/168**2])
    q = r/168**3
    for i in range(1, len(y)):
        dt = (times[i]-times[i-1]).total_seconds()/3600
        if dt <= 0: continue
        f = np.array([[1., dt], [0., 1.]])
        process = q*np.array([[dt**3/3, dt**2/2], [dt**2/2, dt]])
        x = f@x; p = f@p@f.T + process
        innovation = y[i]-x[0]
        gain = p[:, 0]/(p[0, 0]+r)
        x += gain*innovation
        a = np.eye(2)-np.outer(gain, [1., 0.])
        p = a@p@a.T + np.outer(gain, gain)*r
        q = .8*q + .2*max(innovation**2-r, r*.05)/max(dt**3, 1.)
    # Respect the latest actual anchor exactly, while retaining the estimated drift.
    x[0] = y[-1]
    return dict(x=x, covariance=p, q=q, anchor=times[-1], noise_sd=measurement_sd)


def hs_domain(x, train):
    lo = train.min(axis=0); hi = train.max(axis=0)
    margin = np.maximum(.1*(hi-lo), .03*np.maximum(np.abs(lo), np.abs(hi))) + 1e-9
    return np.isfinite(x).all(axis=1) & ((x >= lo-margin) & (x <= hi+margin)).all(axis=1)


def hs_fit_models(asset, known, target, h):
    """Fit mathematical, statistical and naive candidates using released labels only."""
    last = known.iloc[-1]; y = known[target].to_numpy(float)
    sd = float(HS_MEASUREMENT_SD.get((asset['tag_number'], target),
               max(abs(float(np.median(y)))*HS_MEASUREMENT_REL_SD, 1e-6)))
    base = dict(anchor=last['Date'], anchor_value=float(y[-1]), noise_sd=sd,
                release=last['Available At'], n=len(y), domain='weekly temporal validation')
    models = {'BASELINE_HOLD': dict(base, kind='hold', family='BASELINE')}
    times = pd.DatetimeIndex(known['Date'])
    slopes = np.diff(y)/np.diff(times.asi8)*3.6e12 if len(y)>1 else np.array([0.])
    drift = float(np.median(slopes[-4:]))
    models['MATH_WEEKLY_DRIFT'] = dict(base, kind='drift', family='MATHEMATICAL', drift=drift)
    models['STAT_KALMAN'] = dict(base, kind='kalman', family='STATISTICAL', **hs_fit_kalman(known, target, sd))
    x = hs_covariates(asset, known, h)
    names = HS_STAT_FEATURES.get(target)
    if names and set(names).issubset(x.columns):
        good = x[names].notna().all(axis=1).to_numpy()
        xx = x.loc[good, names].to_numpy(float); yy = y[good]
        if len(xx) >= max(HS_MIN_REGRESSION_ROWS, 2*len(names)+2):
            estimator = (make_pipeline(StandardScaler(), SVR(C=max(np.std(yy)*3, .01), epsilon=max(np.std(yy)*.05, .001)))
                         if target=='2X Harmonic' else make_pipeline(StandardScaler(), Ridge(alpha=2.)))
            estimator.fit(xx, yy)
            models['STAT_SVR' if target=='2X Harmonic' else 'STAT_RIDGE'] = dict(
                base, kind='regression', family='STATISTICAL', estimator=estimator,
                features=names, train=xx, n=len(xx), domain='conditional weekly holdout; hourly transfer unvalidated')
    if target == 'Winding Temp' and {'TEMP', 'AMP'}.issubset(x):
        good = x[['TEMP','AMP']].notna().all(axis=1).to_numpy()
        xx = x.loc[good, ['TEMP','AMP']].to_numpy(float); yy=y[good]
        if len(xx)>=2:
            a=xx[:,1]**2*(xx[:,0]+235.)/(75.+235.)
            k=float(np.dot(a, yy-xx[:,0])/max(np.dot(a,a),1e-12))
            if k>=0:
                models['MATH_COPPER_LOSS'] = dict(base, kind='copper', family='MATHEMATICAL', coefficient=k,
                    features=['TEMP','AMP'], train=xx, n=len(xx), domain='simplified thermal correlation; weekly holdout; not IEEE certification')
    if target == 'Lube Oil Supply Press' and 'TEMP' in x:
        good=x['TEMP'].notna().to_numpy(); xx=x.loc[good,['TEMP']].to_numpy(float); yy=y[good]
        if len(xx)>=4:
            best=None
            for c in [.005,.01,.02,.05]:
                design=np.column_stack([np.ones(len(xx)),-np.exp(-c*(xx[:,0]-75.))])
                beta=np.linalg.lstsq(design,yy,rcond=None)[0]
                if beta[1]<0: continue  # Supplied positive-viscosity-coefficient hypothesis must fit its sign.
                mse=float(np.mean((design@beta-yy)**2))
                if best is None or mse<best[0]: best=(mse,c,beta)
            if best:
                models['MATH_EXP_TEMP'] = dict(base, kind='exp_temperature', family='MATHEMATICAL',
                    c=best[1], beta=best[2], features=['TEMP'], train=xx, n=len(xx),
                    domain='empirical bearing-temperature correlation; not Poiseuille oil pressure')
    if target == '2X Harmonic' and 'TEMP' in x:
        good=x['TEMP'].notna().to_numpy(); xx=x.loc[good,['TEMP']].to_numpy(float); yy=y[good]
        if len(xx)>=3:
            center=float(xx[:,0].mean()); a=np.column_stack([np.ones(len(xx)),xx[:,0]-center])
            beta=np.linalg.lstsq(a,yy,rcond=None)[0]
            if beta[1]>=0:
                models['MATH_THERMAL_2X'] = dict(base, kind='thermal_2x', family='MATHEMATICAL', center=center,
                    beta=beta, features=['TEMP'], train=xx, n=len(xx),
                    domain='empirical thermal-growth correlation; torque term unavailable')
    if target == 'Tube-side dP' and 'FEED' in x:
        good=(x['FEED'].notna() & x['FEED'].gt(0)).to_numpy()
        xx=x.loc[good,['FEED']].to_numpy(float); yy=y[good]
        if len(xx):
            ks=yy/xx[:,0]**2
            # EMA updates only when a new measured dP/flow pair is released.
            kval=float(pd.Series(ks).ewm(alpha=HS_EMA_ALPHA,adjust=False).mean().iloc[-1])
            models['MATH_FLOW_SQUARED'] = dict(base, kind='flow_squared', family='MATHEMATICAL',
                coefficient=kval, features=['FEED'], train=xx, n=len(xx),
                domain='calibrated constant-density flow-squared correlation; not measured differential pressure')
    if target == 'Coupling Offset' and {'VIB','AMP'}.issubset(h.columns):
        # Identifiable empirical rate law dx/dt = -lambda*x + gamma*stress.
        # Integrate each interval ONCE; no repeated integral from t0 at each step.
        # AMP/FLA is a dimensionless load index; gamma absorbs stress units.
        features=[];rates=[]
        for j in range(1,len(known)):
            earlier=known.iloc[j-1];later=known.iloc[j]
            dt=(later['Date']-earlier['Date']).total_seconds()/3600
            segment=h.loc[(h.index>=earlier['Date'])&(h.index<later['Date'])]
            if dt<=0 or len(segment)!=int(dt) or segment[['VIB','AMP']].isna().any().any():continue
            stress=segment['VIB']*segment['AMP']/asset['fla']
            stress=stress.where(segment['RUN_STATUS'].astype(str).str.upper().eq('ON'),0.)
            features.append([-float(earlier[target]),float(stress.mean())])
            rates.append((float(later[target])-float(earlier[target]))/dt)
        if len(rates)>=4:
            design=np.array(features);scale=np.maximum(np.linalg.norm(design,axis=0),1e-12)
            if np.linalg.matrix_rank(design)==2 and np.linalg.cond(design/scale)<1e8:
                coefficients=nnls(design/scale,np.array(rates))[0]/scale
                models['MATH_STRESS_STATE']=dict(base,kind='stress',family='MATHEMATICAL',
                    relaxation=coefficients[0],stress_gain=coefficients[1],hourly=h[['VIB','AMP','RUN_STATUS']].copy(),
                    fla=asset['fla'],n=len(rates),domain='calibrated empirical relaxation/stress rate; geometry anchored by inspection')
    # Full physical candidates only with independently verified meanings and units.
    cfg=HS_PHYSICS.get(asset['tag_number'],{})
    valid=pd.to_datetime(cfg.get('valid_from'),errors='coerce')
    if cfg.get('verified') and pd.notna(valid) and valid<=last['Available At']:
        if target=='Seal Flush Flow':
            coefficient=safe_float(cfg.get('flow_coefficient_L_min_sqrt_bar'))
            if not np.isfinite(coefficient) and 'DISP' in x:
                dp=x['DISP'].to_numpy(float)-hs_channel(x,cfg,'seal_chamber_pressure')
                a=np.sqrt(np.where(dp>=0,dp,np.nan)); good=np.isfinite(a)&(a>0)&(known['Date'].to_numpy()>=valid.to_datetime64())
                if good.any(): coefficient=float(np.dot(a[good],y[good])/np.dot(a[good],a[good]))
            if np.isfinite(coefficient) and coefficient>0:
                models['PHYSICS_ORIFICE'] = dict(base, kind='orifice', family='MATHEMATICAL', cfg=cfg,
                    coefficient=coefficient, domain='verified discharge-to-seal-chamber pressure difference', valid_from=valid)
        if target in {'Heat Duty','Cold Outlet Temp'}:
            ua=safe_float(cfg.get('UA_kW_K')); design=safe_float(cfg.get('design_duty_kW'))
            cp=safe_float(cfg.get('cp_cold_kJ_kg_K'))
            # Each simultaneous weekly Q/Tout pair can update effective UA by EMA.
            ua_samples=[]
            for i,row in known.iterrows():
                j=known.index.get_loc(i)
                if row['Date']<valid: continue
                if pd.notna(row.get('Heat Duty')) and pd.notna(row.get('Cold Outlet Temp')) and design>0:
                    query=x.iloc[[j]]
                    tc=hs_channel(query,cfg,'cold_inlet_temperature')[0]
                    thi=hs_channel(query,cfg,'hot_inlet_temperature')[0]
                    tho=hs_channel(query,cfg,'hot_outlet_temperature')[0]
                    lm=hs_lmtd(thi-float(row['Cold Outlet Temp']),tho-tc)
                    if np.isfinite(lm) and lm>0: ua_samples.append(float(row['Heat Duty'])/100*design/lm)
            if ua_samples: ua=float(pd.Series(ua_samples).ewm(alpha=HS_EMA_ALPHA,adjust=False).mean().iloc[-1])
            if ua>0 and cp>0 and design>0:
                models['PHYSICS_LMTD'] = dict(base, kind='lmtd', family='MATHEMATICAL', cfg=cfg, ua=ua,
                    domain='verified countercurrent energy balance and effective UA; F=1', valid_from=valid)
    return models


def hs_predict(model, query, target):
    n=len(query); out=np.full(n,np.nan); age=(query.index-model['anchor']).total_seconds().to_numpy()/3600
    kind=model['kind']; value=model['anchor_value']
    if kind=='hold': out[:]=value
    elif kind=='drift': out=value+model['drift']*age
    elif kind=='kalman': out=model['x'][0]+model['x'][1]*age
    elif kind=='blend':
        out=sum(weight*hs_predict(m,query,target) for weight,m in zip(model['weights'],model['components']))
    elif kind in {'regression','copper','exp_temperature','thermal_2x','flow_squared'}:
        q=query.copy()
        if 'AMP' in q: q['AMP_SQ']=q['AMP']**2
        names=model['features']
        if not set(names).issubset(q): return out
        x=q[names].to_numpy(float); good=hs_domain(x,model['train'])
        if good.any():
            z=x[good]
            if kind=='regression': out[good]=model['estimator'].predict(z)
            elif kind=='copper': out[good]=z[:,0]+model['coefficient']*z[:,1]**2*(z[:,0]+235)/(75+235)
            elif kind=='exp_temperature': out[good]=model['beta'][0]-model['beta'][1]*np.exp(-model['c']*(z[:,0]-75))
            elif kind=='thermal_2x': out[good]=model['beta'][0]+model['beta'][1]*(z[:,0]-model['center'])
            else: out[good]=model['coefficient']*z[:,0]**2
    elif kind=='stress':
        # Use observed inputs only up to the query time. Future plotting supplies
        # explicitly held-constant inputs; missing historical hours are not filled.
        if {'VIB','AMP','RUN_STATUS'}.issubset(query.columns):
            timeline=pd.concat([model['hourly'],query[['VIB','AMP','RUN_STATUS']]])
            timeline=timeline.loc[~timeline.index.duplicated(keep='last')].sort_index()
            grid=pd.date_range(model['anchor'],query.index.max(),freq='1h')
            timeline=timeline.reindex(grid);values={};state=value
            decay=np.exp(-model['relaxation'])
            factor=(1-decay)/model['relaxation'] if model['relaxation']>1e-12 else 1.
            for j,timestamp in enumerate(grid):
                if j:
                    inputs=timeline.iloc[j-1]
                    if pd.isna(inputs['VIB']) or pd.isna(inputs['AMP']):state=np.nan
                    else:
                        stress=float(inputs['VIB'])*float(inputs['AMP'])/model['fla'] if str(inputs['RUN_STATUS']).upper()=='ON' else 0.
                        state=decay*state+model['stress_gain']*stress*factor
                values[timestamp]=state
            out=np.array([values.get(t,np.nan) for t in query.index])
    elif kind=='orifice':
        if 'DISP' in query:
            dp=query['DISP'].to_numpy(float)-hs_channel(query,model['cfg'],'seal_chamber_pressure')
            out=model['coefficient']*np.sqrt(np.where(dp>=0,dp,np.nan))
    elif kind=='lmtd':
        cfg=model['cfg']; col=cfg.get('cold_mass_flow_column')
        if col in query:
            tc=hs_channel(query,cfg,'cold_inlet_temperature'); thi=hs_channel(query,cfg,'hot_inlet_temperature')
            tho=hs_channel(query,cfg,'hot_outlet_temperature')
            for i,flow in enumerate(query[col]):
                tout,duty=hs_heat_solution(flow,tc[i],thi[i],tho[i],cfg['cp_cold_kJ_kg_K'],model['ua'],cfg['mass_flow_unit'])
                out[i]=tout if target=='Cold Outlet Temp' else 100*duty/cfg['design_duty_kW']
    out=np.asarray(out,float)
    out[(age<0)|(age>HS_MAX_LABEL_AGE_HOURS)]=np.nan
    if 'valid_from' in model: out[query.index<model['valid_from']]=np.nan
    if target not in {'Winding Temp','Cold Outlet Temp'}: out[out<0]=np.nan
    else: out[out < -273.15]=np.nan
    # Same-unit RMS check: retain only physically possible modeled 2X values.
    if target=='2X Harmonic' and 'VIB' in query:
        vib=query['VIB'].to_numpy(float)
        out[np.isfinite(vib)&((out>vib)|(out<0))]=np.nan
    return out


def hs_scores(records):
    """Compare each model with persistence on the SAME held-out dates."""
    scores={}
    if not records: return scores
    frame=pd.DataFrame(records)
    for model, group in frame.groupby('Model'):
        g=group.tail(HS_VALIDATION_WINDOW)
        mae=float(g['Abs Error'].mean()); b=float(g['Baseline Abs Error'].mean())
        ratio=mae/max(b,1e-12)
        scores[model]=dict(n=len(g),mae=mae,rmse=float(np.sqrt(np.mean(g['Error']**2))),
                           baseline_mae=b,skill=1-ratio,score=ratio)
    return scores


def hs_blend(models, records):
    """Weights use past errors; the new blend is evaluated only on future labels."""
    scores=hs_scores(records)
    math_names=[k for k,m in models.items() if m['family']=='MATHEMATICAL' and scores.get(k,{}).get('n',0)>=HS_MIN_VALIDATION_POINTS]
    stat_names=[k for k,m in models.items() if m['family']=='STATISTICAL' and scores.get(k,{}).get('n',0)>=HS_MIN_VALIDATION_POINTS]
    if not math_names or not stat_names: return
    a=min(math_names,key=lambda k:scores[k]['score']); b=min(stat_names,key=lambda k:scores[k]['score'])
    ar={r['Date']:r for r in records if r['Model']==a}; br={r['Date']:r for r in records if r['Model']==b}
    dates=sorted(set(ar)&set(br))[-HS_VALIDATION_WINDOW:]
    if len(dates)<HS_MIN_VALIDATION_POINTS:return
    mse=np.array([np.mean([source[t]['Error']**2 for t in dates]) for source in [ar,br]])
    inv=1/np.maximum(mse,1e-12); weights=inv/inv.sum()
    models['HYBRID_MATH_STAT']=dict(models['BASELINE_HOLD'],kind='blend',family='HYBRID',
                                   components=[models[a],models[b]],weights=weights,component_names=[a,b],
                                   domain='past-error-weighted mathematical/statistical fusion')


def hs_rank(models, records):
    scores=hs_scores(records)
    accepted=[k for k in models if scores.get(k,{}).get('n',0)>=HS_MIN_VALIDATION_POINTS
              and scores[k]['skill']>=HS_REQUIRED_IMPROVEMENT]
    accepted.sort(key=lambda k:scores[k]['score'])
    # With little post-repair evidence, show a provisional state estimate, not an invented fit.
    provisional=[k for k in ['PHYSICS_ORIFICE','PHYSICS_LMTD','MATH_COPPER_LOSS','STAT_KALMAN','BASELINE_HOLD','MATH_WEEKLY_DRIFT'] if k in models]
    if not accepted and scores.get('BASELINE_HOLD',{}).get('n',0)>=HS_MIN_VALIDATION_POINTS:
        provisional=['BASELINE_HOLD']+provisional
    return list(dict.fromkeys(accepted+provisional+list(models))),scores


def hs_predict_ranked(models, ranking, query, target):
    out=np.full(len(query),np.nan); names=np.full(len(query),'DATA_GAP',dtype=object)
    for name in ranking:
        pred=hs_predict(models[name],query,target); use=~np.isfinite(out)&np.isfinite(pred)
        out[use]=pred[use];names[use]=name
    return out,names


def hs_build_target(asset, target, h):
    """Walk releases chronologically. No future weekly points train earlier models."""
    w=hs_weekly(asset,target,h.index.max())
    series=pd.Series(np.nan,index=h.index); lower=series.copy();upper=series.copy()
    names=pd.Series('DATA_GAP',index=h.index,dtype=object)
    families=names.copy(); quality=names.copy(); anchors=pd.Series(pd.NaT,index=h.index)
    validation=[];records=[];snapshots=[];known=pd.DataFrame();previous=None
    for i,row in w.iterrows():
        release=row['Available At']; t=row['Date']; actual=float(row[target])
        if previous is not None and previous['release']<=t:
            query=hs_covariates(asset,w.iloc[[i]],h)
            baseline=hs_predict(previous['models']['BASELINE_HOLD'],query,target)[0]
            if np.isfinite(baseline):
                baseline_error=abs(baseline-actual)
                policy,policy_names=hs_predict_ranked(previous['models'],previous['ranking'],query,target)
                for name,model in previous['models'].items():
                    pred=hs_predict(model,query,target)[0]
                    if not np.isfinite(pred):continue
                    rec={'Asset':asset['tag_number'],'Target':target,'Date':t,'Available At':release,
                         'Model':name,'Family':model['family'],'Prediction':pred,'Actual':actual,
                         'Error':pred-actual,'Abs Error':abs(pred-actual),'Baseline Abs Error':baseline_error,
                         'Training Label Date':model['anchor'],'Training Available At':model['release'],'Repair Observation':bool(row['Repair']),
                         'Domain':model['domain']}
                    records.append(rec);validation.append(rec)
                if np.isfinite(policy[0]):
                    validation.append(dict(rec,Model='SELECTED_POLICY',Family='POLICY',Prediction=policy[0],
                                           Error=policy[0]-actual,**{'Abs Error':abs(policy[0]-actual),
                                           'Selected Component':policy_names[0]}))
        if row['Repair']:
            known=w.iloc[[i]].copy();records=[]  # New regime; never carry old degradation drift through repair.
        else:
            known=pd.concat([known,w.iloc[[i]]],ignore_index=True)
        models=hs_fit_models(asset,known,target,h)
        hs_blend(models,records);ranking,scores=hs_rank(models,records)
        snapshot=dict(release=release,models=models,ranking=ranking,scores=scores,
                      known_rows=len(known),anchor=t,records=list(records))
        snapshots.append(snapshot);previous=snapshot
        end=w.iloc[i+1]['Available At'] if i+1<len(w) else h.index.max()+pd.Timedelta(hours=1)
        query=h.loc[(h.index>=release)&(h.index<end)]
        if query.empty:continue
        values,chosen=hs_predict_ranked(models,ranking,query,target)
        if target not in HS_CHEMISTRY_TARGETS:
            off=~query['RUN_STATUS'].astype(str).str.upper().eq('ON').to_numpy()
            values[off]=np.nan;chosen[off]='DATA_GAP'
        series.loc[query.index]=values;names.loc[query.index]=chosen;anchors.loc[query.index]=t
        for name in set(chosen)-{'DATA_GAP'}:
            mask=chosen==name;times=query.index[mask];model=models[name];score=scores.get(name,{})
            age=(times-t).total_seconds().to_numpy()/3600
            sd=max(model['noise_sd'],score.get('rmse',0.))*np.sqrt(1+age/168)
            if model['kind']=='kalman':
                p=model['covariance'];var=p[0,0]+2*age*p[0,1]+age**2*p[1,1]+model['q']*age**3/3
                sd=np.maximum(sd,np.sqrt(np.maximum(var,0)))
            lower.loc[times]=values[mask]-2*sd;upper.loc[times]=values[mask]+2*sd
            families.loc[times]=model['family']
            quality.loc[times]='WEEKLY_BACKTESTED' if score.get('n',0)>=HS_MIN_VALIDATION_POINTS else 'PROVISIONAL'
    if target not in {'Winding Temp','Cold Outlet Temp'}:lower=lower.clip(lower=0)
    return dict(series=series,lower=lower,upper=upper,model=names,family=families,quality=quality,
                anchor=anchors,snapshots=snapshots,validation=validation,weekly=w)


def hs_reason(target):
    return {
        'Seal Flush Flow':'FEED is t/h, not pressure. Plan 11 needs seal-chamber pressure and a calibrated orifice coefficient.',
        'Lube Oil Supply Press':'Bearing TEMP is not verified oil temperature; exponential model is empirical and sign-checked.',
        'Lube Oil Water Content':'ppm state is anchored to released lab results. No dew point/oil-temperature condensation model is available.',
        'Winding Temp':'Copper-loss equation is a calibrated steady-state approximation; weekly-to-hourly transfer remains to be validated.',
        'Heat Duty':'Physical LMTD branch needs verified stream temperatures, flow, Cp, design duty and UA; otherwise use weekly state prediction.',
        'Cold Outlet Temp':'Generic TEMP is not relabeled as cold outlet. Physical branch needs stream definitions; otherwise weekly state prediction.',
        'Tube-side dP':'Flow-squared candidate assumes constant density. DISP alone is not dP; coefficient updated from released weekly dP.',
        'Feed Heavy-ends':'Percent estimate is driven by lab history; no verified composition correlation is claimed.',
        '2X Harmonic':'Thermal/SVR candidates use measured weekly 2X targets; overall RMS alone cannot recover a spectrum.',
        'Coupling Offset':'mm state is anchored to alignment readings. Stress/relaxation rate needs >=4 complete weekly hourly-input intervals; otherwise drift/Kalman. No uncalibrated wear coefficient.'
    }.get(target,'')


def generate_virtual_sensors(asset, global_tables, as_of=None, include_history=False):
    as_of=pd.Timestamp(as_of if as_of is not None else asset['df_hourly_observed']['Timestamp'].max())
    h=hs_observed_hours(asset)
    # Each cached historical point was calculated with its own information set.
    # Cache is local to one loaded asset/run; clear it after modifying data/config in a notebook.
    if '_hybrid_cache' not in asset:
        missing=[p for p in build_limit_dict(asset['df_limits']) if p not in asset['cfg'].get('hourly_param_map',{})]
        asset['_hybrid_cache']={p:hs_build_target(asset,p,h) for p in missing}
    result=dict(as_of=min(as_of,h.index.max()),entries={},watch_names=[])
    for target,data in asset['_hybrid_cache'].items():
        visible=data['series'].loc[:as_of]; t=visible.index.max() if len(visible) else pd.NaT
        if pd.isna(t):continue
        snaps=[s for s in data['snapshots'] if s['release']<=as_of]
        snap=snaps[-1] if snaps else None
        name=data['model'].loc[t];model=snap['models'].get(name) if snap else None
        score=snap['scores'].get(name,{}) if snap else {}
        value=visible.iloc[-1];lim=build_limit_dict(asset['df_limits'])[target]
        age=(t-data['anchor'].loc[t]).total_seconds()/3600 if pd.notna(data['anchor'].loc[t]) else np.nan
        state=directional_engineering_state(value,lim) if np.isfinite(value) else 'DATA_GAP'
        forecast=pd.Series(dtype=float)
        if include_history and snap and t==h.index.max() and (target in HS_CHEMISTRY_TARGETS or str(h.iloc[-1]['RUN_STATUS']).upper()=='ON'):
            future=pd.date_range(t+pd.Timedelta(hours=1),periods=HOURLY_FORECAST_HOURS,freq='1h')
            # Conditional forecast: external DCS inputs held at last observed operating point.
            q=pd.DataFrame(np.repeat(h.iloc[[-1]].to_numpy(),len(future),axis=0),index=future,columns=h.columns)
            for c in q:
                if c!='RUN_STATUS':q[c]=pd.to_numeric(q[c],errors='coerce')
            pred,_=hs_predict_ranked(snap['models'],snap['ranking'],q,target)
            forecast=pd.Series(pred,index=future)
        quality=data['quality'].loc[t] if np.isfinite(value) else 'DATA_GAP'
        entry=dict(target=target,name=target,kind='ESTIMATE' if np.isfinite(value) else 'DATA_GAP',
             unit=lim['unit'],series=visible,value=value,lower=data['lower'].loc[:as_of],upper=data['upper'].loc[:as_of],
             selected_model=name,model_history=data['model'].loc[:as_of],family_history=data['family'].loc[:as_of],
             quality_history=data['quality'].loc[:as_of],family=model['family'] if model else 'DATA_GAP',
             method=name,reason=hs_reason(target),assessment_status=quality,state=state,
             alert_eligible=False,validation_mae=score.get('mae',np.nan),validation_skill=score.get('skill',np.nan),
             validation_rows=score.get('n',0),paired_rows=model['n'] if model else 0,
             last_weekly_date=data['anchor'].loc[t],label_age_h=age,forecast=forecast,
             uncertainty_note='Assumed/model error envelope; not a calibrated 95% interval',
             candidate_scores=snap['scores'] if snap else {},candidate_names=list(snap['models']) if snap else [],
             model_domain=model['domain'] if model else '',
             validation=[v for v in data['validation'] if v['Available At']<=as_of])
        if model and model['kind']=='blend':entry['fusion_weights']=dict(zip(model['component_names'],model['weights'].tolist()))
        result['entries'][target]=entry
        if (HS_ALLOW_ESTIMATED_WATCH and quality=='WEEKLY_BACKTESTED' and score.get('skill',0)>HS_REQUIRED_IMPROVEMENT
                and state in {'ALARM','TRIP'}):result['watch_names'].append(target)
    return result


def evaluate_asset_condition(asset,global_tables,eval_time=None):
    weekly=asset['cfg'].get('core_mode')=='weekly'
    condition=evaluate_weekly_condition(asset,global_tables,eval_date=eval_time) if weekly else evaluate_hourly_condition(asset,global_tables,eval_time=eval_time)
    condition['measured_overall_state']=condition['overall_state']
    if not ENABLE_VIRTUAL_SENSORS:return condition
    as_of=eval_time if eval_time is not None else asset['df_hourly_observed']['Timestamp'].max()
    virtual=generate_virtual_sensors(asset,global_tables,as_of,include_history=eval_time is None)
    condition['virtual_sensors']=virtual
    eligible=pd.notna(virtual['as_of']) and virtual['as_of']>=condition['current_time']
    condition['virtual_decision_eligible']=bool(eligible)
    condition['decision_time']=max(condition['current_time'],virtual['as_of']) if eligible else condition['current_time']
    if eligible and HS_ALLOW_ESTIMATED_WATCH and virtual['watch_names']:
        condition['overall_state']=state_max(condition['overall_state'],'WATCH')
    return condition


def print_virtual_sensor_summary(results):
    log('\n'+'='*104);log('HYBRID HOURLY ESTIMATES — mathematical/statistical candidates; native target units');log('='*104)
    log(f'Weekly release: Available At column, or Date + {HS_WEEKLY_RELEASE_DELAY_HOURS} h assumption. No future interpolation.')
    for r in results:
        v=r['condition'].get('virtual_sensors',{})
        log(f"{r['tag_number']} | hourly as-of={v.get('as_of')}")
        for p,e in v.get('entries',{}).items():
            log(f"  {p}: {e['value']:.4g} {e['unit']} ESTIMATE | {e['selected_model']} | {e['assessment_status']}")
            log(f"    Weekly anchor={e['last_weekly_date']} | age={e['label_age_h']:.1f} h | estimated limit state={e['state']}")
            log(f"    Released-label validation n={e['validation_rows']}, MAE={e['validation_mae']:.4g}, skill={e['validation_skill']:.3g}; candidates={', '.join(e['candidate_names'])}")
            if 'fusion_weights' in e:log(f"    Past-error fusion weights={e['fusion_weights']}")
    log('Estimates are provisional between lab/inspection updates; error envelopes have no validated confidence coverage.')
    log('Validated indirect estimates are consumed by the canonical PF trace; non-validated virtual estimates remain advisory/fallback only.')


def export_virtual_sensors(results):
    ensure_output_dir();audit=[];validation=[];scores=[]
    for r in results:
        v=r['condition'].get('virtual_sensors',{});wide=pd.DataFrame()
        for p,e in v.get('entries',{}).items():
            stem=p+' ['+e['unit']+']'
            wide[stem+' ESTIMATE']=e['series'];wide[stem+' Lower']=e['lower'];wide[stem+' Upper']=e['upper']
            wide[p+' Model']=e['model_history'];wide[p+' Quality']=e['quality_history']
            audit.append({'Asset':r['tag_number'],'Target':p,'Unit':e['unit'],'Value':e['value'],'As Of':v['as_of'],
                'Selected Model':e['selected_model'],'Family':e['family'],'Quality':e['assessment_status'],
                'Estimated Limit State':e['state'],'Latest Weekly Measurement':e['last_weekly_date'],'Label Age h':e['label_age_h'],
                'Validation n':e['validation_rows'],'Validation MAE':e['validation_mae'],'Skill vs hold':e['validation_skill'],
                'Training n':e['paired_rows'],'Domain':e['model_domain'],'Reason':e['reason'],'Uncertainty':e['uncertainty_note'],
                'Candidates':'; '.join(e['candidate_names']),'Fusion Weights':str(e.get('fusion_weights',{}))})
            for name,score in e['candidate_scores'].items():scores.append({'Asset':r['tag_number'],'Target':p,'Model':name,**score})
            validation.extend(e['validation'])
        wide.index.name='Timestamp';wide.to_csv(os.path.join(OUTPUT_DIR,f"virtual_sensors_hourly_{r['tag_number']}.csv"))
    pd.DataFrame(audit).to_csv(os.path.join(OUTPUT_DIR,'virtual_sensor_model_audit.csv'),index=False)
    pd.DataFrame(scores).to_csv(os.path.join(OUTPUT_DIR,'hybrid_model_comparison.csv'),index=False)
    pd.DataFrame(validation).to_csv(os.path.join(OUTPUT_DIR,'hybrid_prequential_validation.csv'),index=False)


# ============================================================================== 
# V10.10 SHARED COMPUTATION CACHE / PROFILING
# ============================================================================== 
MSPC_MODEL_CACHE = {}
RCA_TFIDF_CACHE = {}
PF_BACKTEST_FIT_CACHE = {}
PHASE_TIMINGS = {}


def _frame_time_bounds(df):
    if df is None or len(df)==0: return (None,None,0)
    for c in ('Timestamp','Date','Available At'):
        if c in df:
            t=pd.to_datetime(df[c],errors='coerce').dropna()
            if len(t): return (int(t.min().value),int(t.max().value),len(df))
    return (None,None,len(df))


def fit_mspc_model_cached(asset_tag, df_baseline, cols):
    key=(str(asset_tag),tuple(cols),_frame_time_bounds(df_baseline))
    if key not in MSPC_MODEL_CACHE: MSPC_MODEL_CACHE[key]=fit_mspc_model(df_baseline,cols)
    return MSPC_MODEL_CACHE[key]


def pf_series_fingerprint(series):
    s=pf_clean(series)
    if s.empty: return 'EMPTY'
    h=pd.util.hash_pandas_object(s,index=True).values.tobytes()
    return hashlib.sha1(h).hexdigest()


def pf_config_hash():
    payload=repr((AS_OF,PF_END,PF_HORIZONS_H,PF_WEEKLY_HORIZONS_H,PF_BASE_MODELS,PF_MIN_VALIDATION_N,PF_IMPROVEMENT_THRESHOLD,
                  SHORT_GAP_INTERPOLATION_LIMIT,PF_STATE_CONFIGS)).encode()
    return hashlib.sha1(payload).hexdigest()[:16]


def _time_phase(name, start):
    PHASE_TIMINGS[name]=PHASE_TIMINGS.get(name,0.0)+(perf_counter()-start)


def print_phase_timings():
    if not PHASE_TIMINGS: return
    print('\nPHASE TIMING')
    print('-'*48)
    subtotal=0.0
    for name,value in PHASE_TIMINGS.items():
        print(f'{name:<28}: {value:8.3f} s')
        if name != 'Total wall-clock': subtotal += value
    print('-'*48); print(f'{"PHASE SUBTOTAL":<28}: {subtotal:8.3f} s')


def _rca_corpus_key(global_tables, cutoff, only_rca):
    inc=global_tables.get('incident',pd.DataFrame())
    dates=pd.to_datetime(inc.get('Date of Occur.',pd.Series(dtype='datetime64[ns]')),errors='coerce')
    max_date=int(dates.max().value) if len(dates.dropna()) else 0
    return (int(pd.Timestamp(cutoff).value),bool(only_rca),len(inc),max_date)


def get_rca_tfidf_index(global_tables, cutoff, only_rca=False):
    key=_rca_corpus_key(global_tables,cutoff,only_rca)
    if key in RCA_TFIDF_CACHE: return RCA_TFIDF_CACHE[key]
    knowledge=time_scoped_knowledge(global_tables,pd.Timestamp(cutoff))
    inc=prepare_incident_text(knowledge['incident'],knowledge).reset_index(drop=True)
    if only_rca:
        hdr=knowledge.get('rca_header',pd.DataFrame())
        valid_ar=set(hdr.get('AR No',pd.Series(dtype=object)).astype(str)) if not hdr.empty else set()
        inc=inc[inc['AR No'].astype(str).isin(valid_ar)].copy().reset_index(drop=True)
    inc['_RCA_ROW_ID']=np.arange(len(inc),dtype=int)
    if inc.empty:
        result=(knowledge,inc,None,None)
    else:
        vec=TfidfVectorizer(stop_words='english',ngram_range=(1,2),min_df=1)
        matrix=vec.fit_transform(inc['Retrieval Text'].fillna('').astype(str).tolist())
        result=(knowledge,inc,vec,matrix)
    RCA_TFIDF_CACHE[key]=result
    return result

# ==============================================================================
# V10.10 — SINGLE CANONICAL COMPLETE-TRACE FORECASTING / EXECUTIVE PIPELINE
# ==============================================================================
# Design rules:
#   1) Raw/observed data are never overwritten merely to make a dashboard complete.
#   2) Estimate/Lower/Upper in the canonical analytical trace must be finite.
#   3) All plots, CSV, Excel, AS-OF status and event/RCA context read the same trace.
#   4) Weekly-only parameters are latent-state estimates; they are never relabeled as hourly actuals.
#   5) Historical reconstruction may smooth with observations on both sides; future forecast is causal.

def get_latest_common_asof(source):
    """Return the latest hourly timestamp already available for every configured asset.

    ``source`` may be a workbook path, an open ``ExcelFile``, or the in-memory
    workbook dictionary used by ``run_intelligence_engine``.  Resolving AS_OF from
    the actual workbook on every run prevents stale module-import timestamps after
    users edit or replace the Excel file.
    """
    latest_times = []
    names = workbook_sheet_names(source)
    for cfg in ASSET_CONFIGS:
        tag = cfg["tag_number"]
        sheet = f"{tag} Production Data Hourly"
        if sheet not in names:
            raise ValueError(f"{tag}: required hourly sheet '{sheet}' is missing; AS_OF cannot be resolved.")
        if isinstance(source, dict):
            df = source[sheet]
            if "Timestamp" not in df.columns:
                raise ValueError(f"{tag}: hourly sheet has no Timestamp column; AS_OF cannot be resolved.")
            ts = pd.to_datetime(df["Timestamp"], errors="coerce").dropna()
        else:
            xl = source if isinstance(source, pd.ExcelFile) else pd.ExcelFile(source)
            df = pd.read_excel(xl, sheet_name=sheet, usecols=["Timestamp"])
            ts = pd.to_datetime(df["Timestamp"], errors="coerce").dropna()
        if ts.empty:
            raise ValueError(f"{tag}: no valid hourly Timestamp is available to determine AS_OF.")
        latest_times.append(pd.Timestamp(ts.max()))
    return min(latest_times)


def refresh_runtime_context(source):
    """Refresh all time anchors from the workbook currently being analysed."""
    global AS_OF, PF_END, PF_START, PF_HOURLY_START, PF_HOURLY_END
    AS_OF = pd.Timestamp(get_latest_common_asof(source)).floor("h")
    PF_END = AS_OF + pd.Timedelta(hours=720)
    PF_START = AS_OF - pd.DateOffset(months=6)
    PF_HOURLY_START = AS_OF - pd.Timedelta(days=HOURLY_PLOT_DAYS)
    PF_HOURLY_END = AS_OF + pd.Timedelta(hours=HOURLY_FORECAST_HOURS)
    return {
        "as_of": AS_OF, "pf_start": PF_START, "pf_end": PF_END,
        "hourly_start": PF_HOURLY_START, "hourly_end": PF_HOURLY_END,
    }


# Safe import-time defaults.  They are refreshed from the selected workbook at
# every engine run and must not be treated as authoritative by the UI.
AS_OF = get_latest_common_asof(FILE_PATH)
PF_END = AS_OF + pd.Timedelta(hours=720)
PF_START = AS_OF - pd.DateOffset(months=6)
PF_HOURLY_START = AS_OF - pd.Timedelta(days=HOURLY_PLOT_DAYS)
PF_HOURLY_END = AS_OF + pd.Timedelta(hours=HOURLY_FORECAST_HOURS)
PF_HORIZONS_H = (24, 72, 168)  # operational hourly horizons only
PF_WEEKLY_HORIZONS_H = (168, 336, 504, 672)  # Week+1 ... Week+4
PF_BASE_MODELS = ('Persistence', 'Damped OLS', 'Kalman Level', 'Kalman Trend')
PF_MIN_VALIDATION_N = 3
PF_IMPROVEMENT_THRESHOLD = 0.98
PF_VALIDATION_ORIGINS = 8
PF_STATE_VALIDATION_ORIGINS = 8
PF_STATE_CONFIGS = (
    (0.03,0.005,1.00,0.70,0.995),
    (0.08,0.010,1.00,0.70,0.995),
    (0.15,0.020,1.00,0.70,0.990),
    (0.08,0.010,0.75,0.50,0.995),
    (0.08,0.010,1.25,1.00,0.995),
    (0.03,0.005,1.00,1.00,1.000),
    (0.15,0.020,1.00,1.00,0.985),
)  # q_level, q_trend, R_primary, R_weekly, damping; selected by rolling validation
PF_EXPECTED_ENGINEERING_PARAMETERS = 20
PF_COLORS = dict(actual='#245A81', prediction='#168A87', band='#BFDCD8',
                 alarm='#C88B20', trip='#B6424C', now='#374151')
PF_MODEL_CACHE = {}
PF_TRACE_CACHE = {}
PF_EXECUTIVE_CACHE = None
PF_STATE_CACHE = {}


def pf_reset_cache(force=False):
    """Dependency-aware caches persist within the Python session; force=True clears them."""
    global PF_EXECUTIVE_CACHE
    if force:
        PF_MODEL_CACHE.clear(); PF_TRACE_CACHE.clear(); PF_STATE_CACHE.clear(); PF_BACKTEST_FIT_CACHE.clear(); MSPC_MODEL_CACHE.clear(); RCA_TFIDF_CACHE.clear()
    PF_EXECUTIVE_CACHE=None


def asof_trim_asset(asset, asof=None):
    if asof is None:
        asof = AS_OF
    for key in ('df_hourly', 'df_hourly_observed', 'df_on'):
        asset[key] = asset[key].loc[asset[key].Timestamp.le(asof)].copy()
    w = asset['df_weekly'].copy()
    release = (pd.to_datetime(w[HS_WEEKLY_AVAILABLE_COLUMN], errors='coerce')
               if HS_WEEKLY_AVAILABLE_COLUMN in w else
               pd.to_datetime(w.Date) + pd.Timedelta(hours=HS_WEEKLY_RELEASE_DELAY_HOURS))
    asset['df_weekly'] = w.loc[release.le(asof) & release.ge(w.Date)].copy()
    for key in ('_hybrid_cache', '_asof_weekly_cache', '_pf_channels', '_dcs_model_cache', '_dcs_trace_cache'):
        asset.pop(key, None)
    return asset


def pf_clean(series):
    s = pd.to_numeric(series, errors='coerce').replace([np.inf, -np.inf], np.nan).dropna()
    if not isinstance(s.index, pd.DatetimeIndex):
        s.index = pd.to_datetime(s.index, errors='coerce')
        s = s.loc[~s.index.isna()]
    return s.loc[~s.index.duplicated(keep='last')].sort_index().astype(float)


def pf_robust_scale(series):
    s = pf_clean(series)
    if len(s) < 2:
        return max(abs(float(s.iloc[-1])) * 0.01 if len(s) else 1.0, 1e-4)
    dy = np.diff(s.to_numpy(float))
    med = float(np.median(dy))
    mad = float(np.median(np.abs(dy - med)) * 1.4826)
    std = float(np.std(dy))
    return max(mad, 0.25 * std, abs(float(s.iloc[-1])) * 0.002, 1e-5)


def pf_clip_physical(values, target=''):
    arr = np.asarray(values, dtype=float)
    low = -273.15 if ('temp' in str(target).lower()) else 0.0
    arr = np.maximum(arr, low)
    if normalize_text(target) in {'feed heavy ends', 'feed heavy ends percent'}:
        arr = np.minimum(arr, 100.0)
    return arr


def pf_harmonic_eligibility(series, period_h):
    s = pf_clean(series)
    if len(s) < 12:
        return False
    span_h = (s.index[-1] - s.index[0]).total_seconds() / 3600.0
    steps = np.diff(s.index.asi8) / 3.6e12
    if len(steps) == 0:
        return False
    median_step = float(np.median(steps))
    irregularity = float(np.median(np.abs(steps - median_step)) / max(median_step, 1e-9))
    return bool(span_h >= 3.0 * period_h and median_step <= period_h / 4.0 and irregularity <= 0.15)


def pf_candidate_names(series):
    names = list(PF_BASE_MODELS)
    if pf_harmonic_eligibility(series, 24.0):
        names.append('Harmonic 24h')
    if pf_harmonic_eligibility(series, 168.0):
        names.append('Harmonic 168h')
    return tuple(names)


def pf_fit(series, name):
    """One canonical model fitter. Point forecasts are deterministic conditional means."""
    s = pf_clean(series)
    if s.empty:
        raise ValueError('pf_fit requires at least one observed anchor')
    y = s.to_numpy(float)
    t = (s.index - s.index[0]).total_seconds().to_numpy() / 3600.0
    dt = max(float(np.median(np.diff(t))) if len(t) > 1 else 1.0, 1e-6)
    scale = pf_robust_scale(s)
    out = dict(name=name, time=s.index[-1], anchor=float(y[-1]), step=dt, noise=scale,
               slope=0.0, decay=0.95, variance=scale**2, eligible=True)

    if name.startswith('Harmonic'):
        period = 24.0 if '24h' in name else 168.0
        if not pf_harmonic_eligibility(s, period):
            out['eligible'] = False
            return out
        recent = s.loc[s.index >= s.index[-1] - pd.Timedelta(hours=6 * period)]
        th = (recent.index - recent.index[-1]).total_seconds().to_numpy() / 3600.0
        yy = recent.to_numpy(float)
        phase = 2 * np.pi * th / period
        X = np.column_stack([np.ones(len(th)), th, np.sin(phase), np.cos(phase)])
        coef = np.linalg.lstsq(X, yy, rcond=None)[0]
        fitted = X @ coef
        anchor = float(coef[0] + coef[3])  # phase=0 at last observation
        out.update(anchor=anchor, slope=float(coef[1] * dt), period=period,
                   harmonic=np.asarray([coef[2], coef[3]], float),
                   noise=max(scale, float(np.std(yy - fitted))))
        return out

    if len(y) < 3 or name == 'Persistence':
        return out

    if name == 'Damped OLS':
        window = min(len(y), max(5, int(round(168.0 / dt))))
        x = (t[-window:] - t[-1]) / dt
        z = y[-window:]
        slope = float(np.polyfit(x, z, 1)[0])
        fitted = np.polyval(np.polyfit(x, z, 1), x)
        out.update(slope=slope, noise=max(scale, float(np.std(z - fitted))))
        return out

    # Local-level / local-linear-trend filter. qratio is selected by innovation likelihood.
    trend = name == 'Kalman Trend'
    best = None
    for qratio in (0.001, 0.01, 0.1):
        state = np.array([y[0], 0.0], dtype=float)
        cov = np.eye(2) * scale**2
        r = max(scale**2, 1e-12)
        cost = 0.0
        for i in range(1, len(y)):
            delta_h = max(t[i] - t[i-1], 1e-6)
            d = delta_h / dt
            phi = 0.95**d if trend else 0.0
            gain = (1.0 - phi) / (1.0 - 0.95) if trend else 0.0
            F = np.array([[1.0, gain], [0.0, phi]])
            Q = np.diag([r * qratio * max(d, 1e-3), r * qratio * 0.01 * max(d, 1e-3) if trend else 0.0])
            state = F @ state
            cov = F @ cov @ F.T + Q
            innovation = y[i] - state[0]
            vv = max(cov[0,0] + r, 1e-12)
            K = cov[:,0] / vv
            state = state + K * innovation
            cov = cov - np.outer(K, cov[0,:])
            cost += np.log(vv) + innovation**2 / vv
        if best is None or cost < best[0]:
            best = (cost, state, cov, qratio)
    _, state, cov, qratio = best
    out.update(anchor=float(state[0]), slope=float(state[1]) if trend else 0.0,
               variance=max(float(cov[0,0]), scale**2), qratio=qratio)
    return out


def pf_predict(fit, dates):
    dates = pd.DatetimeIndex(dates)
    hours = np.maximum(0.0, (dates - fit['time']).total_seconds().to_numpy() / 3600.0)
    d = hours / max(float(fit['step']), 1e-6)
    phi = float(fit.get('decay', 0.95))
    gain = (1.0 - np.power(phi, d)) / max(1.0 - phi, 1e-9)
    pred = float(fit['anchor']) + float(fit.get('slope', 0.0)) * gain
    if 'harmonic' in fit:
        phase = 2 * np.pi * hours / float(fit['period'])
        a, b = fit['harmonic']
        pred = pred + a * np.sin(phase) + b * (np.cos(phase) - 1.0)
    return np.asarray(pred, dtype=float)


def pf_validation_summary(records, candidates):
    frame = pd.DataFrame(records)
    scores = {}
    if frame.empty:
        return scores
    for name in candidates:
        g = frame.loc[frame.Model.eq(name)]
        if g.empty:
            continue
        err = g.Error.to_numpy(float)
        base_err = g.Baseline_Error.to_numpy(float)
        mae = float(np.mean(np.abs(err)))
        rmse = float(np.sqrt(np.mean(err**2)))
        base_mae = float(np.mean(np.abs(base_err)))
        skill = 1.0 - mae / base_mae if base_mae > 1e-12 else (0.0 if mae <= 1e-12 else np.nan)
        scores[name] = dict(mae=mae, rmse=rmse, skill=skill, n=int(len(g)),
                            max_h=float(g.Horizon_H.max()), errors=err,
                            horizons=g.Horizon_H.to_numpy(float))
    return scores


def pf_temporal(series, gap_h, regime_start=None):
    """Select a deployed temporal model using causal rolling-origin validation.

    Operational claims are restricted to H+24/H+72/H+168. Speed comes from cached
    fits, not from removing history, origins, or candidate models. A non-persistence
    candidate is deployed only when it improves MAE by at least 2% vs persistence.
    """
    s=pf_clean(series)
    if regime_start is not None:
        s=s.loc[s.index>=pd.Timestamp(regime_start)]
    if s.empty:
        raise ValueError('Forecast needs at least one observed anchor')
    candidates=pf_candidate_names(s); records=[]; n=len(s)
    if n>=4:
        first=max(1,n//4); last=max(first,n-2)
        origins=np.unique(np.linspace(first,last,min(PF_VALIDATION_ORIGINS,last-first+1)).astype(int))
    else:
        origins=[]
    full_fp=pf_series_fingerprint(s)
    for i in origins:
        train=s.iloc[:i+1]; available=s.iloc[i+1:]
        if available.empty: continue
        horizons=(available.index-train.index[-1]).total_seconds().to_numpy()/3600.0
        target_ids=[]
        for hours in PF_HORIZONS_H:
            j=int(np.argmin(np.abs(horizons-hours)))
            if 0.70*hours<=horizons[j]<=1.40*hours:
                target_ids.append(j)
        if not target_ids:
            continue
        test=available.iloc[sorted(set(target_ids))]
        train_key=(full_fp,int(i),pd.Timestamp(train.index[-1]).value)
        for name in candidates:
            key=(train_key,name)
            fit=PF_BACKTEST_FIT_CACHE.get(key)
            if fit is None:
                fit=pf_fit(train,name); PF_BACKTEST_FIT_CACHE[key]=fit
            if not fit.get('eligible',True): continue
            pred=pf_predict(fit,test.index)
            for date,truth,guess in zip(test.index,test.to_numpy(float),pred):
                actual_h=(date-train.index[-1]).total_seconds()/3600.0
                relevant_h=min(PF_HORIZONS_H, key=lambda H: abs(actual_h-H))
                records.append(dict(Model=name,Origin=train.index[-1],Date=date,
                    Horizon_H=actual_h, Relevant_Horizon_H=float(relevant_h),
                    Error=float(guess-truth),Baseline_Error=float(train.iloc[-1]-truth)))
    scores=pf_validation_summary(records,candidates)
    valid=[name for name in candidates if name in scores and scores[name]['n']>=PF_MIN_VALIDATION_N]
    persistence=scores.get('Persistence')
    if valid:
        best=min(valid,key=lambda k:(scores[k]['mae'],candidates.index(k)))
        if best!='Persistence' and persistence is not None and scores[best]['mae'] < persistence['mae']*PF_IMPROVEMENT_THRESHOLD:
            chosen=best
        else:
            chosen='Persistence' if persistence is not None else best
    else:
        chosen='Persistence'
    fit=pf_fit(s,chosen)
    score=scores.get(chosen,dict(mae=np.nan,rmse=np.nan,skill=np.nan,n=0,max_h=0.0,errors=np.array([],dtype=float),horizons=np.array([],dtype=float)))
    return dict(fit=fit,score=score,records=records,scores=scores,series=s,model=chosen,
                persistence_mae=(persistence or {}).get('mae',np.nan),
                beats_persistence=bool(chosen!='Persistence'),
                validation_method='ROLLING_ORIGIN_CAUSAL_H24_H72_H168' if score['n'] else 'NO_RELEVANT_HORIZON_VALIDATION')

def pf_trace(model, dates, target='', anchor_override=None):
    dates = pd.DatetimeIndex(dates)
    fit = model['fit']
    score = model['score']
    mean = pf_predict(fit, dates)
    if anchor_override is not None:
        at_anchor = float(pf_predict(fit, pd.DatetimeIndex([AS_OF]))[0])
        mean = mean + (float(anchor_override) - at_anchor)
    h = np.maximum(0.0, (dates - AS_OF).total_seconds().to_numpy() / 3600.0)
    errors = np.abs(np.asarray(score.get('errors', []), dtype=float))
    horizons = np.asarray(score.get('horizons', []), dtype=float)
    ref = max(float(np.median(horizons)) if len(horizons) else float(fit['step']), 1.0)
    radius = max(float(np.quantile(errors, 0.90)) if len(errors) else 1.645 * float(fit['noise']),
                 float(fit['noise']))
    band = radius * np.sqrt(np.maximum(1.0, h / ref))
    mean = pf_clip_physical(mean, target)
    lower = pf_clip_physical(mean - band, target)
    upper = pf_clip_physical(mean + band, target)
    upper = np.maximum(upper, mean)
    lower = np.minimum(lower, mean)
    return pd.DataFrame({'Estimate':mean, 'Lower':lower, 'Upper':upper}, index=dates)



def pf_inv2(matrix):
    """Fast stable inverse for the 2x2 covariance matrices used by the RTS smoother."""
    a,b=float(matrix[0,0]),float(matrix[0,1]); c,d=float(matrix[1,0]),float(matrix[1,1])
    det=a*d-b*c
    if abs(det)<1e-18:
        jitter=max(abs(a)+abs(d),1.0)*1e-12
        a+=jitter; d+=jitter; det=a*d-b*c
    return np.array([[d,-b],[-c,a]],dtype=float)/det


def pf_state_config_dict(cfg):
    ql,qt,rp,rw,damp=cfg
    return {'q_level_ratio':float(ql),'q_trend_ratio':float(qt),'r_primary_ratio':float(rp),'r_weekly_ratio':float(rw),'damping':float(damp)}


def pf_state_filter_pass(primary_series, weekly_series, timeline, config, target=''):
    primary=pf_clean(primary_series); weekly=pf_clean(weekly_series); timeline=pd.DatetimeIndex(timeline).sort_values().unique()
    all_obs=pd.concat([primary.rename('value'),weekly.rename('value')]).sort_index()
    if all_obs.empty: raise ValueError('State-space filter requires an observed anchor')
    scale=pf_robust_scale(all_obs); cfg=pf_state_config_dict(config) if not isinstance(config,dict) else config
    pm=primary.to_dict(); wm=weekly.to_dict(); rp=max((cfg['r_primary_ratio']*scale)**2,1e-10); rw=max((cfg['r_weekly_ratio']*scale)**2,1e-10)
    ql=max((cfg['q_level_ratio']*scale)**2,1e-12); qt=max((cfg['q_trend_ratio']*scale)**2,1e-14); damp0=cfg['damping']
    early=all_obs.iloc[:min(5,len(all_obs))]
    if len(early)>=2:
        dh=(early.index-early.index[0]).total_seconds().to_numpy()/3600.0; valid=dh>0
        slope=float(np.median((early.to_numpy(float)[valid]-float(early.iloc[0]))/dh[valid])) if valid.any() else 0.0
    else: slope=0.0
    x=np.array([float(early.iloc[0]),slope],float); P=np.diag([max(scale**2,1e-8),max((scale/24.0)**2,1e-10)])
    xf=[];Pf=[];xp=[];Pp=[];Fs=[]; last_t=timeline[0]
    for i,t in enumerate(timeline):
        if i==0: F=np.eye(2); xpred=x.copy(); Ppred=P.copy()
        else:
            dt=max((t-last_t).total_seconds()/3600.0,1e-6); phi=damp0**dt
            gain=(1-phi)/max(1-damp0,1e-9) if damp0<0.999999 else dt
            F=np.array([[1.0,gain],[0.0,phi]]); Q=np.diag([ql*dt,qt*dt])
            xpred=F@x; Ppred=F@P@F.T+Q
        x=xpred.copy();P=Ppred.copy()
        for obs,r in ((pm,rp),(wm,rw)):
            if t in obs:
                innovation=float(obs[t])-x[0]; S=max(P[0,0]+r,1e-12); K=P[:,0]/S; x=x+K*innovation; P=P-np.outer(K,P[0,:])
        xp.append(xpred.copy());Pp.append(Ppred.copy());xf.append(x.copy());Pf.append(P.copy());Fs.append(F.copy());last_t=t
    return {'timeline':timeline,'xf':np.asarray(xf),'Pf':np.asarray(Pf),'xp':np.asarray(xp),'Pp':np.asarray(Pp),'F':np.asarray(Fs),'scale':scale,'config':cfg}


def pf_state_propagate(state,cov,hours,config,scale):
    h=max(float(hours),0.0); cfg=pf_state_config_dict(config) if not isinstance(config,dict) else config; damp=cfg['damping']; phi=damp**h
    gain=(1-phi)/max(1-damp,1e-9) if damp<0.999999 else h
    F=np.array([[1.0,gain],[0.0,phi]]); ql=max((cfg['q_level_ratio']*scale)**2,1e-12); qt=max((cfg['q_trend_ratio']*scale)**2,1e-14)
    Q=np.diag([ql*max(h,1e-6),qt*max(h,1e-6)]); x=F@np.asarray(state,float); P=F@np.asarray(cov,float)@F.T+Q
    return x,P


def pf_state_space_validation(primary_series,weekly_series,target=''):
    """Validate the FINAL fused candidate against persistence on decision-relevant horizons."""
    primary=pf_clean(primary_series); weekly=pf_clean(weekly_series)
    truth=pd.concat([primary.rename('Primary'),weekly.rename('Weekly')],axis=1).sort_index()
    truth['Truth']=truth['Weekly'].combine_first(truth['Primary']); truth=truth['Truth'].dropna()
    if truth.empty: raise ValueError('State-space validation requires an observed target')
    first=truth.index.min().floor('h'); timeline=pd.date_range(first,AS_OF,freq='h')
    timeline=pd.DatetimeIndex(sorted(set(timeline).union(set(primary.index[primary.index<=AS_OF])).union(set(weekly.index[weekly.index<=AS_OF]))))
    weekly_like=(primary.empty or (len(truth)>2 and float(np.median(np.diff(truth.index.asi8))/3.6e12)>=72.0))
    validation_horizons=PF_WEEKLY_HORIZONS_H if weekly_like else PF_HORIZONS_H
    n=len(truth); origins=np.unique(np.linspace(max(0,n//4),max(0,n-2),min(PF_STATE_VALIDATION_ORIGINS,max(1,n-1))).astype(int)) if n>=3 else np.array([],int)
    pairs=[]
    for i in origins:
        origin=truth.index[i]; available=truth.loc[truth.index>origin]
        if available.empty: continue
        hs=(available.index-origin).total_seconds().to_numpy()/3600.0
        for H in validation_horizons:
            j=int(np.argmin(np.abs(hs-H)))
            if .70*H<=hs[j]<=1.40*H:
                pairs.append((origin,available.index[j],float(available.iloc[j]),H))
    records=[]; config_scores={}; persistence_errors=[]; persistence_h=[]
    for origin,target_time,truth_value,H in pairs:
        prev=float(truth.loc[:origin].iloc[-1]); err=prev-truth_value
        persistence_errors.append(err); persistence_h.append((target_time-origin).total_seconds()/3600.0)
        records.append({'Model':'Persistence','Config':'Persistence','Origin':origin,'Date':target_time,
                        'Horizon_H':persistence_h[-1],'Relevant_Horizon_H':H,'Error':err,'Baseline_Error':err})
    base_mae=float(np.mean(np.abs(persistence_errors))) if persistence_errors else np.nan
    base_rmse=float(np.sqrt(np.mean(np.square(persistence_errors)))) if persistence_errors else np.nan
    persistence_score={'mae':base_mae,'rmse':base_rmse,'skill':0.0,'n':len(persistence_errors),
                       'max_h':max(persistence_h) if persistence_h else 0.0,
                       'errors':np.asarray(persistence_errors,float),'horizons':np.asarray(persistence_h,float)}
    for ci,cfg in enumerate(PF_STATE_CONFIGS):
        fp=pf_state_filter_pass(primary,weekly,timeline,cfg,target); pos={pd.Timestamp(t):i for i,t in enumerate(fp['timeline'])}; errs=[]; hs=[]
        for origin,target_time,truth_value,H in pairs:
            if origin not in pos: continue
            k=pos[origin]; horizon=(target_time-origin).total_seconds()/3600.0
            x,P=pf_state_propagate(fp['xf'][k],fp['Pf'][k],horizon,cfg,fp['scale']); err=float(x[0]-truth_value); errs.append(err);hs.append(horizon)
            records.append({'Model':'State-Space Fusion','Config':str(ci),'Origin':origin,'Date':target_time,
                            'Horizon_H':horizon,'Relevant_Horizon_H':H,'Error':err,
                            'Baseline_Error':float(truth.loc[:origin].iloc[-1]-truth_value)})
        if errs:
            mae=float(np.mean(np.abs(errs)));rmse=float(np.sqrt(np.mean(np.square(errs))));skill=1-mae/base_mae if np.isfinite(base_mae) and base_mae>1e-12 else np.nan
            config_scores[ci]={'mae':mae,'rmse':rmse,'skill':skill,'n':len(errs),'max_h':max(hs),'errors':np.asarray(errs,float),'horizons':np.asarray(hs,float),'config':pf_state_config_dict(cfg)}
    valid=[i for i,v in config_scores.items() if v['n']>=PF_MIN_VALIDATION_N]
    selected=min(valid,key=lambda i:config_scores[i]['mae']) if valid else (min(config_scores,key=lambda i:config_scores[i]['mae']) if config_scores else 1)
    state_score=config_scores.get(selected,{'mae':np.nan,'rmse':np.nan,'skill':np.nan,'n':0,'max_h':0.0,'errors':np.array([]),'horizons':np.array([]),'config':pf_state_config_dict(PF_STATE_CONFIGS[selected])})
    deploy_fusion=(state_score['n']>=PF_MIN_VALIDATION_N and persistence_score['n']>=PF_MIN_VALIDATION_N and np.isfinite(state_score['mae']) and np.isfinite(base_mae) and state_score['mae'] < base_mae*PF_IMPROVEMENT_THRESHOLD)
    if deploy_fusion:
        model='State-Space Fusion'; model_type='STATE_SPACE_FUSION'; score=state_score
    else:
        model='Persistence'; model_type='PERSISTENCE_FALLBACK'; score=persistence_score
    return {'model':model,'model_type':model_type,'config_index':selected,'config':PF_STATE_CONFIGS[selected],
            'score':score,'state_score':state_score,'persistence_score':persistence_score,'records':records,'scores':config_scores,
            'series':truth,'beats_persistence':deploy_fusion,'persistence_mae':base_mae,
            'validation_method':'ROLLING_ORIGIN_FINAL_FUSED_VS_PERSISTENCE_RELEVANT_HORIZONS' if score['n'] else 'PROVISIONAL_STATE_SPACE_CONFIG'}

def pf_state_model_cached(asset,key,primary,weekly,target=''):
    fp=(pf_series_fingerprint(primary),pf_series_fingerprint(weekly));ck=(asset['tag_number'],key,AS_OF.value,pf_config_hash(),fp)
    if ck not in PF_STATE_CACHE: PF_STATE_CACHE[ck]=pf_state_space_validation(primary,weekly,target)
    return PF_STATE_CACHE[ck]

def pf_state_space_reconstruct(primary_series, weekly_series, grid, target='', state_model=None):
    primary=pf_clean(primary_series);weekly=pf_clean(weekly_series);grid=pd.DatetimeIndex(grid);hist_grid=grid[grid<=AS_OF]
    all_obs=pd.concat([primary.rename('value'),weekly.rename('value')]).sort_index()
    if all_obs.empty: raise ValueError('State-space reconstruction requires at least one observed anchor')
    config=state_model['config'] if state_model is not None else PF_STATE_CONFIGS[1]
    first_obs=min(all_obs.index.min(),AS_OF)
    timeline=pd.DatetimeIndex(sorted(set(hist_grid[hist_grid>=first_obs]).union(set(primary.index[primary.index<=AS_OF])).union(set(weekly.index[weekly.index<=AS_OF]))))
    fp=pf_state_filter_pass(primary,weekly,timeline,config,target)
    xf,Pf,xp,Pp,Fs=fp['xf'],fp['Pf'],fp['xp'],fp['Pp'],fp['F'];xs=xf.copy();Ps=Pf.copy()
    for i in range(len(timeline)-2,-1,-1):
        C=Pf[i]@Fs[i+1].T@pf_inv2(Pp[i+1]);xs[i]=xf[i]+C@(xs[i+1]-xp[i+1]);Ps[i]=Pf[i]+C@(Ps[i+1]-Pp[i+1])@C.T
    state=pd.DataFrame({'Estimate':xs[:,0],'StateVariance':np.maximum(Ps[:,0,0],0.0)},index=timeline);hist=state.reindex(hist_grid)
    before=hist.index<first_obs
    if before.any():
        hours=(first_obs-hist.index[before]).total_seconds().to_numpy()/3600.0;hist.loc[before,'Estimate']=xs[0,0]-xs[0,1]*hours;hist.loc[before,'StateVariance']=max(float(Ps[0,0,0]),fp['scale']**2)*(1+hours/24.0)
    hist['Estimate']=pf_clip_physical(hist['Estimate'].to_numpy(float),target);hist['StateVariance']=pd.to_numeric(hist['StateVariance'],errors='coerce').fillna(fp['scale']**2).clip(lower=0.0)
    # causal filtered state at AS_OF drives future forecasts
    last_i=len(timeline)-1; causal={'state':xf[last_i].copy(),'cov':Pf[last_i].copy(),'time':timeline[last_i],'scale':fp['scale'],'config':config}
    return hist,fp['scale'],causal



def pf_short_gap_values(actual, max_gap=SHORT_GAP_INTERPOLATION_LIMIT):
    actual = pf_clean(actual)
    out = {}
    if len(actual) < 2:
        return out
    for (t0,v0),(t1,v1) in zip(actual.items(), list(actual.items())[1:]):
        gap_h = int(round((t1-t0).total_seconds()/3600.0)) - 1
        if 1 <= gap_h <= max_gap:
            for k in range(1, gap_h+1):
                t = t0 + pd.Timedelta(hours=k)
                frac = k/(gap_h+1)
                out[t] = float(v0 + frac*(v1-v0))
    return out


def pf_validation_band(model, dates, anchor_times, state_variance=None):
    """Empirical prediction-error envelope by operational horizon bucket plus state covariance."""
    score=model['score']; fit=model.get('fit',{'noise':pf_robust_scale(model.get('series',pd.Series([1.0],index=[AS_OF]))),'step':1.0})
    errors=np.abs(np.asarray(score.get('errors',[]),float)); horizons=np.asarray(score.get('horizons',[]),float)
    noise=float(fit.get('noise',pf_robust_scale(model.get('series',pd.Series([1.0],index=[AS_OF])))))
    dates=pd.DatetimeIndex(dates); anchors=pd.DatetimeIndex(anchor_times).sort_values()
    if len(anchors):
        pos=anchors.searchsorted(dates); left=np.clip(pos-1,0,len(anchors)-1); right=np.clip(pos,0,len(anchors)-1)
        dist=np.minimum(np.abs((dates-anchors[left]).total_seconds()/3600.0),np.abs((anchors[right]-dates).total_seconds()/3600.0))
    else: dist=np.ones(len(dates))*24.0
    fallback=max(float(np.quantile(errors,.90)) if len(errors) else 1.645*noise,noise)
    band=np.empty(len(dates),float)
    for i,h in enumerate(np.maximum(dist,0.0)):
        if h<=24: lo,hi=0,24
        elif h<=72: lo,hi=24,72
        else: lo,hi=72,168
        use=errors[(horizons>lo)&(horizons<=hi)] if len(errors)==len(horizons) else np.array([])
        band[i]=max(float(np.quantile(use,.90)) if len(use)>=2 else fallback,noise)
    if state_variance is not None:
        band=np.maximum(band,1.645*np.sqrt(np.maximum(np.asarray(state_variance,float),0.0)))
    return band

def pf_build_complete_trace(actual, weekly, model, grid, target='', weekly_only=False, state_model=None, use_state_future=False):
    actual=pf_clean(actual);weekly=pf_clean(weekly);grid=pd.DatetimeIndex(grid)
    hist,_,causal=pf_state_space_reconstruct(actual,weekly,grid,target,state_model=state_model)
    fusion_allowed=bool(use_state_future and state_model is not None and state_model.get('model_type')=='STATE_SPACE_FUSION')
    deployed=state_model if fusion_allowed else model
    trace=pd.DataFrame(index=grid,columns=['Estimate','Lower','Upper','Source','Quality','Model','Model_Type'],dtype=object)
    hist_idx=grid[grid<=AS_OF];trace.loc[hist_idx,'Estimate']=hist.loc[hist_idx,'Estimate'].to_numpy(float)
    anchors=actual.index.union(weekly.index);band=pf_validation_band(state_model or model,hist_idx,anchors,hist.loc[hist_idx,'StateVariance'].to_numpy(float));est=trace.loc[hist_idx,'Estimate'].astype(float).to_numpy()
    trace.loc[hist_idx,'Lower']=pf_clip_physical(est-band,target);trace.loc[hist_idx,'Upper']=np.maximum(pf_clip_physical(est+band,target),est)
    last_observed=max([x for x in [actual.index.max() if len(actual) else pd.NaT,weekly.index.max() if len(weekly) else pd.NaT] if pd.notna(x)])
    historical=hist_idx[hist_idx<AS_OF]
    trace.loc[historical,'Source']='HISTORICAL_RECONSTRUCTION_RTS';trace.loc[historical,'Quality']='RETROSPECTIVE_RECONSTRUCTION'
    gap_idx=historical[historical>last_observed]
    if len(gap_idx):
        trace.loc[gap_idx,'Source']='FORWARD_GAP_FORECAST';trace.loc[gap_idx,'Quality']='CAUSAL_GAP_ESTIMATE'
    if AS_OF in trace.index:
        trace.loc[AS_OF,'Source']='ASOF_ESTIMATE';trace.loc[AS_OF,'Quality']='MODEL_ESTIMATED'
    trace.loc[hist_idx,'Model']='Local Linear Trend State-Space reconstruction';trace.loc[hist_idx,'Model_Type']='STATE_SPACE_RECONSTRUCTION'
    for t,v in pf_short_gap_values(actual).items():
        if t in trace.index and t<AS_OF:
            trace.loc[t,['Estimate','Lower','Upper']]=[v,v,v];trace.loc[t,['Source','Quality','Model','Model_Type']]=['INTERPOLATED_SHORT_GAP','INTERPOLATED_SHORT_GAP','Linear interpolation <=2 h','INTERPOLATION']
    actual_idx=actual.index.intersection(trace.index[trace.index<=AS_OF])
    if len(actual_idx):
        av=actual.reindex(actual_idx).to_numpy(float);trace.loc[actual_idx,['Estimate','Lower','Upper']]=np.column_stack([av,av,av]);trace.loc[actual_idx,'Source']='ACTUAL';trace.loc[actual_idx,'Quality']='MEASURED';trace.loc[actual_idx,'Model']='Observed measurement';trace.loc[actual_idx,'Model_Type']='MEASUREMENT'
    weekly_idx=weekly.index.intersection(trace.index[trace.index<=AS_OF]).difference(actual_idx)
    if len(weekly_idx):
        trace.loc[weekly_idx,'Source']='WEEKLY_MEASUREMENT_UPDATE';trace.loc[weekly_idx,'Quality']='MEASURED_WEEKLY_UPDATE';trace.loc[weekly_idx,'Model']='State-space measurement update';trace.loc[weekly_idx,'Model_Type']='STATE_SPACE_FUSION'
    future=grid[grid>AS_OF]
    if len(future):
        if fusion_allowed:
            score=state_model['score'];errs=np.abs(np.asarray(score.get('errors',[]),float));hs=np.asarray(score.get('horizons',[]),float)
            means=[];lo=[];hi=[]
            for t in future:
                h=(t-AS_OF).total_seconds()/3600.0;x,P=pf_state_propagate(causal['state'],causal['cov'],h,state_model['config'],causal['scale']);m=float(pf_clip_physical([x[0]],target)[0])
                bucket=(errs[(hs>0)&(hs<=24)] if h<=24 else errs[(hs>24)&(hs<=72)] if h<=72 else errs[(hs>72)&(hs<=168)])
                empirical=float(np.quantile(np.abs(bucket),.90)) if len(bucket)>=2 else max(float(np.quantile(np.abs(errs),.90)) if len(errs) else causal['scale'],causal['scale'])
                rad=max(empirical,1.645*np.sqrt(max(float(P[0,0]),0.0)));means.append(m);lo.append(float(pf_clip_physical([m-rad],target)[0]));hi.append(max(float(pf_clip_physical([m+rad],target)[0]),m))
            trace.loc[future,['Estimate','Lower','Upper']]=np.column_stack([means,lo,hi]);deployed_name='State-Space Fusion';deployed_type='STATE_SPACE_FUSION'
        else:
            # Persistence must remain anchored to the latest observed/released value.
            # Never shift persistence to an RTS-smoothed/modelled AS-OF estimate.
            if model['model'] == 'Persistence':
                fut=pf_trace(model,future,target,anchor_override=None)
            else:
                anchor_value=float(trace.loc[AS_OF,'Estimate'])
                fut=pf_trace(model,future,target,anchor_override=anchor_value)
            trace.loc[future,['Estimate','Lower','Upper']]=fut[['Estimate','Lower','Upper']].to_numpy();deployed_name=model['model'];deployed_type='PERSISTENCE_FALLBACK' if model['model']=='Persistence' else 'TIME_SERIES_FORECAST'
        score=deployed['score'];max_h=float(score.get('max_h',0.0));n=int(score.get('n',0));h=(future-AS_OF).total_seconds().to_numpy()/3600.0
        trace.loc[future,'Source']='FORECASTED';trace.loc[future,'Quality']=np.where((n>=PF_MIN_VALIDATION_N)&(h<=max_h),'BACKTESTED_FORECAST',np.where(n>=PF_MIN_VALIDATION_N,'BEYOND_VALIDATED_HORIZON','PROVISIONAL_FORECAST'));trace.loc[future,'Model']=deployed_name;trace.loc[future,'Model_Type']=deployed_type
    score=deployed['score'];trace['Validation_N']=int(score.get('n',0));trace['Validation_MAE']=score.get('mae',np.nan);trace['Validation_RMSE']=score.get('rmse',np.nan);trace['Skill']=score.get('skill',np.nan);trace['Validation_Horizon_H']=score.get('max_h',0.0);trace['Validation_Method']=deployed.get('validation_method','ROLLING_ORIGIN');trace['Training_Start']=deployed['series'].index.min();trace['Training_End']=deployed['series'].index.max();trace['Last_Actual']=actual.index.max() if len(actual) else pd.NaT;trace['Last_Weekly']=weekly.index.max() if len(weekly) else pd.NaT
    for c in ('Estimate','Lower','Upper'):
        vals=pd.to_numeric(trace[c],errors='coerce')
        if vals.isna().any() or not np.isfinite(vals.to_numpy(float)).all(): raise ValueError(f'Canonical trace contains non-finite {c} for {target}')
        trace[c]=vals.astype(float)
    trace['Lower']=np.minimum(trace['Lower'],trace['Estimate']);trace['Upper']=np.maximum(trace['Upper'],trace['Estimate'])
    return trace

def pf_weekly_series(asset, parameter):
    w = hs_weekly(asset, parameter, AS_OF)
    if w.empty:
        return w, pd.Series(dtype=float), None
    s = pd.Series(w[parameter].to_numpy(float), index=pd.DatetimeIndex(w['Available At']))
    repairs = w.loc[w.Repair, 'Available At'] if 'Repair' in w else pd.Series(dtype='datetime64[ns]')
    regime = repairs.iloc[-1] if len(repairs) else None
    return w, pf_clean(s), regime


def pf_model_for_series(asset, key, series, gap_h, regime=None, force_fallback=False):
    """Fit/select one temporal model without allowing a regime filter to erase every anchor.

    A maintenance/reset regime is used only when at least one released observation exists
    on/after the regime start. If the regime boundary is newer than the latest usable
    observation, the function falls back to the documented pre-regime history and marks
    the model PROVISIONAL_REGIME_FALLBACK. This avoids both a crash and an invented anchor.
    """
    s = pf_clean(series)
    if s.empty:
        raise ValueError(
            f"{asset['tag_number']}/{key}: temporal model has no observed/documented anchor; "
            "caller must provide an identifiable baseline prior rather than arbitrary fill"
        )

    requested_regime = pd.Timestamp(regime) if regime is not None and pd.notna(regime) else None
    effective_regime = requested_regime
    regime_fallback = False
    if requested_regime is not None:
        post_regime = s.loc[s.index >= requested_regime]
        if post_regime.empty:
            # Do not silently discard all known history merely because the latest repair/reset
            # date is newer than the last released observation. No fake post-repair value is made.
            effective_regime = None
            regime_fallback = True

    cache_key = (
        asset['tag_number'], key, AS_OF.value, pf_config_hash(), pf_series_fingerprint(s),
        requested_regime.value if requested_regime is not None else None,
        effective_regime.value if effective_regime is not None else None,
        bool(force_fallback), bool(regime_fallback)
    )
    if cache_key in PF_MODEL_CACHE:
        return PF_MODEL_CACHE[cache_key]

    candidate = pf_temporal(s, gap_h, effective_regime)
    if force_fallback:
        # Forced fallback is explicitly the latest-observation Persistence benchmark; never an arbitrary value fill.
        name = 'Persistence'
        fit_series = candidate['series']
        fit = pf_fit(fit_series, name)
        score = candidate['scores'].get(name, candidate['score'])
        model = dict(
            fit=fit, score=score, records=candidate['records'], scores=candidate['scores'],
            series=fit_series, model=name,
            validation_method=(
                'PROVISIONAL_REGIME_FALLBACK|' + candidate['validation_method']
                if regime_fallback else candidate['validation_method']
            ),
            persistence_mae=candidate.get('persistence_mae', np.nan),
            beats_persistence=False,
            regime_requested=requested_regime,
            regime_effective=effective_regime,
            regime_fallback=regime_fallback,
        )
    else:
        model = candidate
        model['regime_requested'] = requested_regime
        model['regime_effective'] = effective_regime
        model['regime_fallback'] = regime_fallback
        if regime_fallback:
            model['validation_method'] = 'PROVISIONAL_REGIME_FALLBACK|' + model.get('validation_method', 'ROLLING_ORIGIN')

    PF_MODEL_CACHE[cache_key] = model
    return model



def pf_channels(asset, force_rebuild=False):
    """One selected DCS model and one complete trace per channel; reused by every downstream layer."""
    if '_pf_channels' in asset and not force_rebuild: return asset['_pf_channels']
    h=asset['df_hourly_observed'].set_index('Timestamp').sort_index();out={};grid=pd.date_range(PF_START.floor('h'),PF_END,freq='h')
    model_cache=asset.setdefault('_dcs_model_cache',{});trace_cache=asset.setdefault('_dcs_trace_cache',{})
    for c in h.columns:
        if c=='RUN_STATUS': continue
        s=pf_clean(h[c])
        if s.empty: continue
        fp=pf_series_fingerprint(s);ck=(str(c),AS_OF.value,pf_config_hash(),fp,bool(force_rebuild))
        if ck in model_cache: model=model_cache[ck]
        else:
            gap_h=max((AS_OF-s.index[-1]).total_seconds()/3600.0,1.0);model=pf_model_for_series(asset,'DCS:'+str(c),s,gap_h,force_fallback=force_rebuild);model_cache[ck]=model
        if ck in trace_cache: trace=trace_cache[ck]
        else:
            state_model=pf_state_model_cached(asset,'DCS_STATE:'+str(c),s,pd.Series(dtype=float),str(c))
            trace=pf_build_complete_trace(s,pd.Series(dtype=float),model,grid,str(c),weekly_only=False,state_model=state_model,use_state_future=False);trace_cache[ck]=trace
        out[c]=dict(model=model,trace=trace,actual=s,state_model=pf_state_model_cached(asset,'DCS_STATE:'+str(c),s,pd.Series(dtype=float),str(c)))
    asset['_pf_channels']=out;return out




def pf_real_baseline_prior(asset,parameter):
    """Return only a real documented typical/reference value; never derive a fake prior from alarm/trip midpoint."""
    tags=asset.get('df_tags',pd.DataFrame()).copy()
    if not tags.empty:
        text_cols=[c for c in tags.columns if normalize_text(c) in {'description','parameter','tag description','name'}]
        typical=[c for c in tags.columns if normalize_text(c) in {'typicalvalue','typical value','normal value','design value'}]
        if typical:
            mask=pd.Series(False,index=tags.index)
            for c in text_cols: mask=mask|tags[c].astype(str).map(normalize_text).str.contains(normalize_text(parameter),regex=False)
            vals=pd.to_numeric(tags.loc[mask,typical[0]],errors='coerce').dropna()
            if len(vals): return float(vals.iloc[-1]),'TAG_DICTIONARY_TYPICAL'
    return None,None


def native_weekly_grid(asset,parameter):
    w=hs_weekly(asset,parameter,AS_OF)
    if len(w):
        dates=pd.DatetimeIndex(pd.to_datetime(w['Date'])).sort_values(); delays=(pd.to_datetime(w['Available At'])-pd.to_datetime(w['Date'])).dt.total_seconds()/3600.0;delay_h=float(delays.median()) if len(delays.dropna()) else HS_WEEKLY_RELEASE_DELAY_HOURS
        rows=[{'Measurement_Date':pd.Timestamp(row.Date),'Available_At':pd.Timestamp(row['Available At']),'Forecast_Target_Date':pd.Timestamp(row.Date),'Weekly_Basis':'MEASURED_WEEKLY'} for _,row in w.iterrows() if pd.Timestamp(row.Date)>=PF_START]
        anchor=dates[-1]
    else:
        anchor=AS_OF.normalize();delay_h=HS_WEEKLY_RELEASE_DELAY_HOURS;rows=[]
    t=anchor+pd.Timedelta(days=7)
    while t<=PF_END:
        rows.append({'Measurement_Date':pd.NaT,'Available_At':t+pd.Timedelta(hours=delay_h),'Forecast_Target_Date':t,'Weekly_Basis':'FORECAST_TARGET'});t+=pd.Timedelta(days=7)
    return pd.DataFrame(rows)


def pf_indirect_candidate(asset, parameter, grid):
    """Return a validated indirect hourly engineering estimate for a non-direct parameter.

    The estimator reuses the causal `hs_*` soft-sensor engine:
      generic hourly DCS covariates -> released weekly engineering labels ->
      prequential model validation -> hourly engineering estimate.

    It is eligible for the canonical decision trace only when the currently selected
    indirect model has at least HS_MIN_VALIDATION_POINTS and improves over persistence
    by HS_REQUIRED_IMPROVEMENT.  Otherwise the canonical state-space/persistence path
    remains authoritative.  No generic DCS channel is ever semantically relabelled as
    the engineering target.
    """
    if asset.get('cfg', {}).get('hourly_param_map', {}).get(parameter):
        return None
    if parameter not in build_limit_dict(asset['df_limits']):
        return None
    h = hs_observed_hours(asset)
    if h.empty:
        return None
    if '_hybrid_cache' not in asset:
        missing = [p for p in build_limit_dict(asset['df_limits'])
                   if p not in asset.get('cfg', {}).get('hourly_param_map', {})]
        asset['_hybrid_cache'] = {p: hs_build_target(asset, p, h) for p in missing}
    data = asset['_hybrid_cache'].get(parameter)
    if not data:
        return None
    snaps = [x for x in data.get('snapshots', []) if pd.Timestamp(x['release']) <= AS_OF]
    if not snaps:
        return None
    snap = snaps[-1]

    visible_model = data['model'].loc[:min(AS_OF, h.index.max())]
    visible_series = pd.to_numeric(data['series'].loc[:min(AS_OF, h.index.max())], errors='coerce')
    good_idx = visible_series.index[visible_series.notna()]
    if not len(good_idx):
        return None
    latest_t = good_idx[-1]
    selected_name = str(visible_model.loc[latest_t])
    selected_model = snap['models'].get(selected_name)
    selected_score = snap['scores'].get(selected_name, {})
    if selected_model is None:
        return None

    # Only models whose estimate genuinely depends on hourly covariates qualify as
    # an indirect conversion. Pure hold/drift/Kalman models remain the temporal fallback.
    hourly_kinds = {'regression','copper','exp_temperature','thermal_2x','flow_squared',
                    'stress','orifice','lmtd','blend'}
    if selected_model.get('kind') not in hourly_kinds:
        return None
    if int(selected_score.get('n', 0)) < HS_MIN_VALIDATION_POINTS:
        return None
    if float(selected_score.get('skill', -np.inf)) < HS_REQUIRED_IMPROVEMENT:
        return None

    grid = pd.DatetimeIndex(grid)
    trace = pd.DataFrame(index=grid, columns=['Estimate','Lower','Upper','Source','Quality','Model','Model_Type'], dtype=object)

    # Historical/current indirect estimates are those generated causally after each
    # released weekly label. Earlier hours are intentionally left empty here and will
    # be filled by the canonical state-space reconstruction before this overlay.
    hist_idx = grid[(grid <= AS_OF) & grid.isin(data['series'].index)]
    hist_val = pd.to_numeric(data['series'].reindex(hist_idx), errors='coerce')
    valid_hist = hist_idx[hist_val.notna().to_numpy()]
    if len(valid_hist):
        vals = pd.to_numeric(data['series'].reindex(valid_hist), errors='coerce').to_numpy(float)
        los = pd.to_numeric(data['lower'].reindex(valid_hist), errors='coerce').to_numpy(float)
        his = pd.to_numeric(data['upper'].reindex(valid_hist), errors='coerce').to_numpy(float)
        # A few provisional rows may not have an uncertainty value; use the selected
        # model's measured/backtest error rather than inventing a constant percentage.
        base_sd = max(float(selected_model.get('noise_sd', 0.0)), float(selected_score.get('rmse', 0.0)), EPS)
        los = np.where(np.isfinite(los), los, vals - 2*base_sd)
        his = np.where(np.isfinite(his), his, vals + 2*base_sd)
        trace.loc[valid_hist, ['Estimate','Lower','Upper']] = np.column_stack([vals,los,his])
        trace.loc[valid_hist,'Source'] = 'INDIRECT_HOURLY_ESTIMATE'
        trace.loc[valid_hist,'Quality'] = data['quality'].reindex(valid_hist).astype(str).to_numpy()
        trace.loc[valid_hist,'Model'] = data['model'].reindex(valid_hist).astype(str).to_numpy()
        trace.loc[valid_hist,'Model_Type'] = ('INDIRECT_' + data['family'].reindex(valid_hist).astype(str)).to_numpy()

    # Future indirect forecast uses the already-canonical DCS channel forecasts as
    # covariates; this avoids fitting a second DCS forecasting pipeline.
    future = grid[grid > AS_OF]
    if len(future):
        dcs = pf_channels(asset)
        q = pd.DataFrame(index=future)
        for c in HOURLY_SUFFIXES:
            if c in dcs:
                q[c] = pd.to_numeric(dcs[c]['trace']['Estimate'].reindex(future), errors='coerce')
        q['RUN_STATUS'] = 'ON'
        if 'AMP' in q and q['AMP'].notna().any():
            q.loc[q['AMP'] <= 0.10*asset.get('fla',150.0), 'RUN_STATUS'] = 'OFF'
        pred, chosen = hs_predict_ranked(snap['models'], snap['ranking'], q, parameter)
        finite = np.isfinite(pred)
        if finite.any():
            ft = future[finite]
            pv = pred[finite]
            lo=[]; hi=[]; fam=[]; qual=[]; names=[]
            for t, val, name in zip(ft, pv, chosen[finite]):
                m = snap['models'].get(str(name), selected_model)
                sc = snap['scores'].get(str(name), selected_score)
                age = max((pd.Timestamp(t)-pd.Timestamp(m['anchor'])).total_seconds()/3600.0, 0.0)
                sd = max(float(m.get('noise_sd',0.0)), float(sc.get('rmse',0.0)), EPS)*np.sqrt(1.0+age/168.0)
                lo.append(float(val-2*sd)); hi.append(float(val+2*sd))
                fam.append('INDIRECT_'+str(m.get('family','MODEL')))
                names.append(str(name))
                qual.append('BACKTESTED_INDIRECT_FORECAST' if int(sc.get('n',0))>=HS_MIN_VALIDATION_POINTS else 'PROVISIONAL_INDIRECT_FORECAST')
            trace.loc[ft,['Estimate','Lower','Upper']] = np.column_stack([pv,lo,hi])
            trace.loc[ft,'Source']='INDIRECT_FORECAST'
            trace.loc[ft,'Quality']=qual
            trace.loc[ft,'Model']=names
            trace.loc[ft,'Model_Type']=fam

    records=[r for r in data.get('validation',[]) if str(r.get('Model'))==selected_name and pd.Timestamp(r.get('Available At'))<=AS_OF]
    errors=np.asarray([safe_float(r.get('Error')) for r in records],float)
    errors=errors[np.isfinite(errors)]
    horizons=np.asarray([(pd.Timestamp(r['Date'])-pd.Timestamp(r['Training Label Date'])).total_seconds()/3600.0
                         for r in records if pd.notna(r.get('Date')) and pd.notna(r.get('Training Label Date'))],float)
    max_h=float(np.nanmax(horizons)) if len(horizons) else 168.0
    score=dict(n=int(selected_score.get('n',0)), mae=selected_score.get('mae',np.nan),
               rmse=selected_score.get('rmse',np.nan), skill=selected_score.get('skill',np.nan),
               baseline_mae=selected_score.get('baseline_mae',np.nan), errors=errors,
               horizons=horizons, max_h=max_h)
    deployed=dict(model='INDIRECT:'+selected_name, score=score, records=records,
                  scores=snap.get('scores',{}), series=pf_clean(pd.Series(data['series'].loc[:AS_OF])),
                  validation_method='RELEASED_WEEKLY_PREQUENTIAL_INDIRECT_VS_PERSISTENCE',
                  persistence_mae=selected_score.get('baseline_mae',np.nan), beats_persistence=True,
                  indirect_model_name=selected_name, indirect_family=selected_model.get('family'),
                  indirect_features=list(selected_model.get('features',[])),
                  domain=selected_model.get('domain',''))
    return dict(trace=trace, deployed=deployed, data=data, selected_name=selected_name,
                selected_model=selected_model, latest_time=latest_t)


def pf_overlay_indirect(base_trace, indirect, weekly, parameter):
    """Overlay validated indirect estimates onto one canonical trace, preserving measured weekly updates."""
    if indirect is None:
        return base_trace
    tr = base_trace.copy()
    ind = indirect['trace']
    use = ind['Estimate'].notna()
    idx = ind.index[use]
    if len(idx):
        tr.loc[idx,['Estimate','Lower','Upper','Source','Quality','Model','Model_Type']] = \
            ind.loc[idx,['Estimate','Lower','Upper','Source','Quality','Model','Model_Type']].to_numpy()
    # Released weekly values are ground-truth engineering anchors and override any
    # indirect estimate at the same availability timestamp.
    weekly = pf_clean(weekly)
    weekly_idx = weekly.index.intersection(tr.index[tr.index<=AS_OF])
    if len(weekly_idx):
        vals=weekly.reindex(weekly_idx).to_numpy(float)
        tr.loc[weekly_idx,['Estimate','Lower','Upper']] = np.column_stack([vals,vals,vals])
        tr.loc[weekly_idx,'Source']='WEEKLY_MEASUREMENT_UPDATE'
        tr.loc[weekly_idx,'Quality']='MEASURED_WEEKLY_UPDATE'
        tr.loc[weekly_idx,'Model']='Released weekly engineering measurement'
        tr.loc[weekly_idx,'Model_Type']='MEASUREMENT_UPDATE'
    for c in ('Estimate','Lower','Upper'):
        tr[c]=pd.to_numeric(tr[c],errors='coerce')
        if tr[c].isna().any() or not np.isfinite(tr[c].to_numpy(float)).all():
            raise ValueError(f'Indirect overlay created non-finite {c} for {parameter}')
    tr['Lower']=np.minimum(tr['Lower'],tr['Estimate'])
    tr['Upper']=np.maximum(tr['Upper'],tr['Estimate'])
    return tr

def pf_parameter(asset, parameter, force_fallback=False):
    limits=build_limit_dict(asset['df_limits']);lim=limits[parameter]
    channels=pf_channels(asset,force_rebuild=force_fallback)
    suffix=asset['cfg'].get('hourly_param_map',{}).get(parameter)
    direct=channels.get(suffix)
    actual=direct['actual'] if direct else pd.Series(dtype=float)
    w,weekly,regime=pf_weekly_series(asset,parameter)
    prior_value=prior_source=None
    if actual.empty and weekly.empty:
        prior_value,prior_source=pf_real_baseline_prior(asset,parameter)
        if prior_value is None:
            raise ValueError(f'{asset["tag_number"]}/{parameter}: scientifically identifiable numeric prior is unavailable; refusing arbitrary fill')
        weekly=pd.Series([prior_value],index=pd.DatetimeIndex([PF_START.floor('h')]))

    fp=(pf_series_fingerprint(actual),pf_series_fingerprint(weekly),pf_config_hash())
    cache_key=(asset['tag_number'],parameter,AS_OF.value,fp,bool(force_fallback),'INDIRECT_CANONICAL_V1')
    if cache_key in PF_TRACE_CACHE:return PF_TRACE_CACHE[cache_key]
    grid=pd.date_range(PF_START.floor('h'),PF_END,freq='h')
    last_anchor=max([t for t in [actual.index.max() if len(actual) else pd.NaT,weekly.index.max() if len(weekly) else pd.NaT] if pd.notna(t)])
    gap_h=max((AS_OF-last_anchor).total_seconds()/3600.0,1.0)
    state_model=None

    # Build the ordinary direct/weekly canonical trace first. It guarantees a complete
    # numerically safe trace and remains the fallback when an indirect model has not
    # demonstrated out-of-sample improvement over persistence.
    if direct is not None and weekly.empty and prior_value is None and not force_fallback:
        model=direct['model'];trace=direct['trace'].copy();deployed=model;model_type='DCS_REUSED'
    else:
        state_model=pf_state_model_cached(asset,'PARAM_FUSION:'+parameter,actual,weekly,parameter)
        fallback_series=actual if len(actual)>=3 else weekly
        temporal=direct['model'] if direct is not None else pf_model_for_series(asset,'PARAM_FALLBACK:'+parameter,fallback_series,gap_h,regime,force_fallback)
        if state_model.get('model_type')=='STATE_SPACE_FUSION':
            deployed=state_model;use_state_future=True;model_type='STATE_SPACE_FUSION'
        else:
            temporal=pf_model_for_series(asset,'PARAM_PERSISTENCE:'+parameter,fallback_series,gap_h,regime,True)
            if temporal.get('model')!='Persistence':
                fit=pf_fit(fallback_series,'Persistence');ps=state_model.get('persistence_score',state_model.get('score',{}))
                temporal=dict(fit=fit,score=ps,records=state_model.get('records',[]),scores={'Persistence':ps},series=fallback_series,model='Persistence',validation_method='PERSISTENCE_FALLBACK_AFTER_FUSION_GATE')
            deployed=temporal;use_state_future=False;model_type='PERSISTENCE_FALLBACK'
        trace=pf_build_complete_trace(actual,weekly,temporal,grid,parameter,weekly_only=actual.empty,state_model=state_model,use_state_future=use_state_future)
        model=deployed

    # NEW canonical bridge: when there is no direct hourly engineering measurement,
    # a validated soft-sensor can replace the temporal estimate at hours for which the
    # indirect estimate is scientifically eligible. The same resulting trace is then
    # used by limit checks, RCA, plots and exports.
    indirect=None
    if direct is None and not force_fallback and prior_source is None:
        indirect=pf_indirect_candidate(asset,parameter,grid)
        if indirect is not None:
            trace=pf_overlay_indirect(trace,indirect,weekly,parameter)
            deployed=indirect['deployed'];model=deployed
            model_type='INDIRECT_CANONICAL'

    current=trace.loc[AS_OF]
    score=deployed['score'];n=int(score.get('n',0));max_h=float(score.get('max_h',0.0))
    if model_type=='INDIRECT_CANONICAL':
        quality=('BACKTESTED_INDIRECT' if n>=HS_MIN_VALIDATION_POINTS and safe_float(score.get('skill'),-np.inf)>=HS_REQUIRED_IMPROVEMENT else 'PROVISIONAL')
    else:
        quality=('BACKTESTED' if n>=PF_MIN_VALIDATION_N and gap_h<=max_h else 'EXTRAPOLATED' if n>=PF_MIN_VALIDATION_N else 'PROVISIONAL')
    if deployed.get('regime_fallback',False):
        quality='PROVISIONAL';trace.loc[:,'Quality']='PROVISIONAL_REGIME_FALLBACK'
    if prior_source:
        quality='PROVISIONAL';trace.loc[:AS_OF,'Source']='BASELINE_PRIOR';trace.loc[:AS_OF,'Quality']='PROVISIONAL';trace.loc[:AS_OF,'Model']=prior_source;trace.loc[:AS_OF,'Model_Type']='DOCUMENTED_PRIOR'

    state=directional_engineering_state(float(current.Estimate),lim)
    band_states=[directional_engineering_state(float(current[c]),lim) for c in ('Lower','Upper')]
    risk=state_max(state,*band_states)
    lab_date=pd.Timestamp(w.Date.iloc[-1]) if len(w) else pd.NaT
    last_actual=actual.index.max() if len(actual) else pd.NaT
    data_age_h=(AS_OF-last_actual).total_seconds()/3600.0 if pd.notna(last_actual) else gap_h
    indirect_source=(str(current.Source).startswith('INDIRECT_'))
    result=dict(parameter=parameter,limit=lim,suffix=suffix,source=str(current.Source),model=deployed,
        trace=trace,actual=actual,weekly=w,last_anchor=last_anchor,last_actual=last_actual,last_lab=lab_date,
        quality=quality,value=float(current.Estimate),lower=float(current.Lower),upper=float(current.Upper),state=state,
        risk=risk,age_h=gap_h,data_age_h=data_age_h,lab_age_h=(AS_OF-lab_date).total_seconds()/3600.0 if pd.notna(lab_date) else np.nan,
        mae=score.get('mae',np.nan),rmse=score.get('rmse',np.nan),skill=score.get('skill',np.nan),n=n,
        validation_h=max_h,validation_method=deployed.get('validation_method'),model_type=model_type,
        beats_persistence=bool(deployed.get('beats_persistence',deployed.get('model')!='Persistence')),
        persistence_mae=deployed.get('persistence_mae',state_model.get('persistence_mae',np.nan) if state_model is not None else np.nan),
        physics_candidate='AVAILABLE' if HS_PHYSICS.get(asset['tag_number'],{}).get('verified') else 'NOT_AVAILABLE_VERIFIED_MAPPING_REQUIRED',
        indirect_used=bool(indirect_source),indirect_candidate_available=bool(indirect is not None),
        indirect_features=deployed.get('indirect_features',[]) if model_type=='INDIRECT_CANONICAL' else [],
        indirect_family=deployed.get('indirect_family') if model_type=='INDIRECT_CANONICAL' else None)
    PF_TRACE_CACHE[cache_key]=result;return result

def pf_snapshot(results):
    for r in results:
        asset = r['asset']
        params = {p:pf_parameter(asset,p) for p in build_limit_dict(asset['df_limits'])}
        r['projection'] = dict(parameters=params,
            state=state_max(*[v['state'] for v in params.values()]),
            risk=state_max(*[v['risk'] for v in params.values()]),
            quality=('EXTRAPOLATED' if any(v['quality']=='EXTRAPOLATED' for v in params.values()) else
                     'PROVISIONAL' if any(v['quality']=='PROVISIONAL' for v in params.values()) else 'BACKTESTED'))
    return results


def pf_trace_issues(trace, target=''):
    issues=[]
    if trace.empty:
        return ['empty trace']
    expected = pd.date_range(trace.index.min(), trace.index.max(), freq='h')
    if not trace.index.equals(expected):
        issues.append('timestamps not continuous hourly')
    for c in ('Estimate','Lower','Upper'):
        x = pd.to_numeric(trace[c], errors='coerce').to_numpy(float)
        if not np.isfinite(x).all():
            issues.append(f'non-finite {c}')
    if (trace['Lower'].to_numpy(float) > trace['Estimate'].to_numpy(float)).any():
        issues.append('Lower > Estimate')
    if (trace['Estimate'].to_numpy(float) > trace['Upper'].to_numpy(float)).any():
        issues.append('Estimate > Upper')
    if (trace.loc[trace.index <= AS_OF,'Source'].eq('FORECASTED')).any():
        issues.append('future source appears at/before AS_OF')
    if (trace.loc[trace.index > AS_OF,'Source'].ne('FORECASTED')).any():
        issues.append('future is not uniformly FORECASTED')
    vals = trace['Estimate'].to_numpy(float)
    if 'temp' not in str(target).lower() and (vals < -1e-9).any():
        issues.append('impossible negative physical value')
    if normalize_text(target) == 'feed heavy ends' and ((vals < -1e-9) | (vals > 100+1e-9)).any():
        issues.append('composition outside 0-100')
    return issues


def validate_prediction_completeness(results):
    parameter_count=sum(len(r['projection']['parameters']) for r in results);failures=[];repaired=[]
    if parameter_count!=PF_EXPECTED_ENGINEERING_PARAMETERS: failures.append(f'engineering parameter count={parameter_count}, expected={PF_EXPECTED_ENGINEERING_PARAMETERS}')
    for r in results:
        asset=r['asset']
        for p,v in list(r['projection']['parameters'].items()):
            issues=pf_trace_issues(v['trace'],p)
            if issues:
                fallback=pf_parameter(asset,p,force_fallback=True);r['projection']['parameters'][p]=fallback;after=pf_trace_issues(fallback['trace'],p)
                if after: failures.append(f"{asset['tag_number']}/{p}: {', '.join(after)}")
                else: repaired.append(f"{asset['tag_number']}/{p}")
            vv=r['projection']['parameters'][p]
            if vv['model_type']=='STATE_SPACE_FUSION' and vv['validation_method'] not in {'ROLLING_ORIGIN_FINAL_FUSED_VS_PERSISTENCE_RELEVANT_HORIZONS','PROVISIONAL_STATE_SPACE_CONFIG'}: failures.append(f"{asset['tag_number']}/{p}: deployed fusion validation mismatch")
        for c,d in pf_channels(asset).items():
            issues=pf_trace_issues(d['trace'],str(c))
            if issues: failures.append(f"{asset['tag_number']}/DCS {c}: {', '.join(issues)}")
    for r in results:
        vals=list(r['projection']['parameters'].values());r['projection']['state']=state_max(*[v['state'] for v in vals]);r['projection']['risk']=state_max(*[v['risk'] for v in vals]);r['projection']['quality']=('EXTRAPOLATED' if any(v['quality']=='EXTRAPOLATED' for v in vals) else 'PROVISIONAL' if any(v['quality']=='PROVISIONAL' for v in vals) else 'BACKTESTED')
    report=pd.DataFrame([{'Check':'Engineering parameter count','Status':'PASS' if parameter_count==PF_EXPECTED_ENGINEERING_PARAMETERS else 'FAIL','Detail':str(parameter_count)},{'Check':'Finite Estimate/Lower/Upper + ordering + provenance','Status':'PASS' if not failures else 'FAIL','Detail':'; '.join(failures)},{'Check':'Fallback repairs','Status':'PASS','Detail':'; '.join(repaired) if repaired else 'none'}]);ensure_output_dir();report.to_csv(os.path.join(OUTPUT_DIR,'prediction_completeness_audit.csv'),index=False)
    if failures: raise ValueError('Prediction completeness gate failed: '+' | '.join(failures))
    return report



def pf_refresh_results_from_canonical(results, tables):
    """Refresh operator/RCA context from the canonical AS-OF trace without re-fitting forecasts."""
    for r in results:
        c = r['condition']
        c['current_time'] = AS_OF
        for p,v in r['projection']['parameters'].items():
            entry=c.setdefault('engineering',{}).setdefault(p,{})
            entry.update(value=v['value'], state=v['state'], direction=v['limit']['direction'],
                         unit=v['limit']['unit'], alarm=v['limit']['alarm'], trip=v['limit']['trip'],
                         deviation_from_alarm=alarm_deviation(v['value'],v['limit']),
                         source=v.get('source'), quality=v.get('quality'), model=v.get('model',{}).get('model'),
                         model_type=v.get('model_type'), indirect_used=v.get('indirect_used',False),
                         indirect_features=v.get('indirect_features',[]))
        c['overall_state']=r['projection']['state']
        r['overall_state']=r['projection']['state']
        r['operator_state']=r['projection']['state'] if r['operating_context'].get('diagnosis_allowed',False) else r['operating_context'].get('status','DATA_GAP')
        query=build_symptom_query(r['asset'],c,operator_input=r.get('operator_input',{}))
        _,similar=retrieve_similar_incidents(r['asset'],c,tables,top_k=TOP_K_SIMILAR)
        r['similar_incidents']=similar
        r['impact']=similarity_weighted_impact(similar,tables['incident'])
        r['priority'],r['urgency']=prioritize_action(r['projection']['state'],r['impact']['consequence_class'],ASSET_CRITICALITY.get(r['tag_number'],'MEDIUM'))
        r['triggers']=build_trigger_explanation(c)
        r['canonical_query']=query
    return results


def pf_events(results):
    events=[]
    for r in results:
        for p,v in r['projection']['parameters'].items():
            lim=v['limit']; tr=v['trace']; recent=AS_OF-pd.Timedelta(days=3); end=AS_OF+pd.Timedelta(days=7)
            measurements=[(t,float(x),'DCS',t) for t,x in v['actual'].loc[recent:AS_OF].items()]
            w=v['weekly']
            if len(w):
                for _,row in w.loc[w.Date.between(recent,AS_OF)].iterrows():
                    measurements.append((row.Date,float(row[p]),'LAB',row['Available At']))
            groups=[]
            bad=[x for x in measurements if directional_engineering_state(x[1],lim) in {'ALARM','TRIP'}]
            if bad:
                t,x,src,rel=max(bad,key=lambda z:STATE_RANK[directional_engineering_state(z[1],lim)])
                groups.append(dict(kind='RECENT_MEASURED',time=t,value=x,state=directional_engineering_state(x,lim),
                                   first_time=min(b[0] for b in bad),quality='MEASURED',source=src,available=rel))
            hist=tr.loc[recent:AS_OF]
            hist=hist.loc[~hist.Source.eq('ACTUAL')]
            states=hist.Estimate.map(lambda x:directional_engineering_state(x,lim))
            badhist=hist.loc[states.isin(['ALARM','TRIP'])]
            if len(badhist):
                most='TRIP' if (states=='TRIP').any() else 'ALARM'; t=states[states.eq(most)].index[0]
                groups.append(dict(kind='RECENT_ESTIMATED',time=t,first_time=badhist.index[0],value=float(hist.loc[t,'Estimate']),
                                   state=most,quality=str(hist.loc[t,'Quality']),source=str(hist.loc[t,'Model'])))
            fut=tr.loc[AS_OF+pd.Timedelta(hours=1):end]
            states=fut.Estimate.map(lambda x:directional_engineering_state(x,lim)); badf=fut.loc[states.isin(['ALARM','TRIP'])]
            if len(badf):
                most='TRIP' if (states=='TRIP').any() else 'ALARM'; t=states[states.eq(most)].index[0]
                groups.append(dict(kind='FUTURE_PREDICTED',time=t,first_time=badf.index[0],value=float(fut.loc[t,'Estimate']),
                                   state=most,quality=str(fut.loc[t,'Quality']),source=str(fut.loc[t,'Model'])))
            for e in groups:
                e.update(tag=r['tag_number'],parameter=p,unit=lim['unit'],mae=v['mae'],rmse=v['rmse'],skill=v['skill'],n=v['n'],
                         id=f"{r['tag_number']}-{re.sub('[^A-Za-z0-9]','',p)[:12]}-{e['kind']}")
                events.append(e)
    return sorted(events,key=lambda x:(x['first_time'],x['tag'],x['parameter']))


def pf_rca(event, results, tables):
    """Event-specific RCA hypothesis; canonical predictions never assert a physical event occurred."""
    import copy
    r=next(x for x in results if x['tag_number']==event['tag']); a=r['asset']
    c=copy.deepcopy(r['condition']); c['current_time']=AS_OF; c['overall_state']=event['state']
    for p,entry in c.get('engineering',{}).items():
        entry['state']='NORMAL'
        if p in r['projection']['parameters']:
            entry['value']=r['projection']['parameters'][p]['value']
    p=event['parameter']; lim=r['projection']['parameters'][p]['limit']
    c.setdefault('engineering',{}).setdefault(p,{}).update(state=event['state'],value=event['value'],
        alarm=lim['alarm'],trip=lim['trip'],direction=lim['direction'],unit=lim['unit'])
    _,similar=retrieve_similar_incidents(a,c,tables,only_rca=True,top_k=3)
    ev=retrieve_rca_evidence(similar,tables,c,top_n=1)
    reason=ev.get('leading_hypothesis') if ev.get('matched_ar') else None
    strength=str(ev.get('evidence_strength') or 'UNVERIFIED').upper()
    action=f'Verify {p} and the operating condition using the latest reading; inspect the sensor and recent load/process changes.'
    if event['kind']!='RECENT_MEASURED':
        action+=' This is a crossing in an estimate/forecast, so confirm the measurement before assigning a physical cause.'
    checks=build_discriminating_checks(a,c,ev)
    if checks:
        action+=' Discriminating checks: '+ '; '.join(checks)+'.'
    if reason and strength in {'MEDIUM','HIGH'}:
        action+=' The historical analogue may be used as a working hypothesis, but corrective action still requires current-condition verification.'
    elif reason:
        action+=' The historical analogue is not sufficiently supported to justify mechanism-specific corrective action.'
    event.update(rca_ar=ev.get('matched_ar'),rca=reason,evidence=strength,
                 rca_label=ev.get('hypothesis_label',rca_hypothesis_label(strength)),
                 recommendation=action,owner=suggested_owner_role(a))
    return event


def pf_time_text(value):
    return pd.Timestamp(value).strftime('%d-%b %H:%M') if pd.notna(value) else 'not released'


def pf_metric_text(value, digits=2):
    return f'{float(value):.{digits}f}' if np.isfinite(safe_float(value)) else 'provisional-no-backtest'


def pf_print(results, events, audit):
    import textwrap
    print('\n'+'='*116+f'\nIntelligent Manufacturing V11.4 | canonical estimation, KPI provenance, and horizon validation | {AS_OF.strftime("%d %b %Y %H:%M")}\n'+'='*116)
    print('Data quality: '+', '.join(f'{k}={v}' for k,v in audit.Status.value_counts().items()))
    print('Raw observations remain unchanged; model estimates/reconstructions are provenance-labeled in the canonical trace.')
    print(f"{'Asset':<11}{'State':<12}{'Quality':<16}{'DCS last':<18}{'Weekly last':<18}{'RCA events':>10}")
    for r in results:
        labs=[v['last_lab'] for v in r['projection']['parameters'].values() if pd.notna(v['last_lab'])]
        last_lab=max(labs) if labs else pd.NaT; count=sum(e['tag']==r['tag_number'] for e in events)
        print(f"{r['tag_number']:<11}{r['projection']['state']:<12}{r['projection']['quality']:<16}{pf_time_text(r['asset']['df_hourly_observed'].Timestamp.max()):<18}{pf_time_text(last_lab):<18}{count:>10}")
    for r in results:
        print('\n'+r['tag_number']+' | CANONICAL AS-OF PARAMETERS')
        print(f"{'Parameter':<25}{'Estimate [Lower, Upper]':<38}{'State':<9}{'Model':<22}{'Quality':<14}")
        for p,v in r['projection']['parameters'].items():
            interval=f"{v['value']:.3g} [{v['lower']:.3g}, {v['upper']:.3g}] {v['limit']['unit']}"
            print(f"{p:<25}{interval:<38}{v['state']:<9}{v['model']['model'][:21]:<22}{v['quality']:<14}")
            print(f"  Source={v['source']} | validation n={v['n']} | MAE={pf_metric_text(v['mae'])} | RMSE={pf_metric_text(v['rmse'])} | horizon={v['validation_h']:.0f} h")
    print('\nRCA EVENTS FROM CANONICAL TRACE')
    if not events:
        print('No measured/estimated/predicted ALARM/TRIP crossing in the configured event windows.')
    for e in events:
        print('\n'+e['id'])
        print(f"  {e['kind']} | first={e['first_time']:%d-%b %H:%M} | {e['state']} @ {e['time']:%d-%b %H:%M} | {e['value']:.3g} {e['unit']} | {e['quality']}")
        text=(f"{e.get('rca_label','RCA hypothesis')} {e['rca_ar']} ({e['evidence']}): {e['rca']}" if e.get('rca') else 'A specific RCA has not been established from the historical cases available at the reference time.')
        print(textwrap.fill(text,110,initial_indent='  ',subsequent_indent='  '))
        print(textwrap.fill('Recommendation: '+e['recommendation']+' Owner: '+e['owner'],110,initial_indent='  ',subsequent_indent='  '))


def pf_measured_parameter_series(v):
    """Observed/released engineering measurements only; canonical estimates are never baseline inputs."""
    pieces=[]
    actual=pf_clean(v.get('actual',pd.Series(dtype=float)))
    if len(actual): pieces.append(actual)
    w=v.get('weekly',pd.DataFrame())
    p=v.get('parameter')
    if w is not None and len(w) and p in w.columns:
        idx=pd.to_datetime(w['Available At'],errors='coerce') if 'Available At' in w.columns else pd.to_datetime(w['Date'],errors='coerce')
        ws=pd.Series(pd.to_numeric(w[p],errors='coerce').to_numpy(),index=idx)
        ws=pf_clean(ws.loc[ws.index<=AS_OF])
        if len(ws): pieces.append(ws)
    if not pieces: return pd.Series(dtype=float)
    out=pd.concat(pieces).sort_index()
    return out.loc[~out.index.duplicated(keep='last')]


def pf_asset_baselines(parameter_objects, limits):
    """Healthy baselines from ACTUAL/RELEASED measurements only, never canonical Estimate."""
    baselines={}; basis={}; measured={}
    for p,v in parameter_objects.items():
        s=pf_measured_parameter_series(v); measured[p]=s; lim=limits[p]
        healthy=s[s.map(lambda x: directional_engineering_state(float(x),lim)=='NORMAL')]
        if len(healthy):
            baselines[p]=float(healthy.median()); basis[p]='MEASURED_HEALTHY_HISTORY'
        elif len(s):
            # Still actual data, but no healthy subset is identifiable. Keep explicit low-confidence basis.
            baselines[p]=float(s.median()); basis[p]='MEASURED_HISTORY_NO_HEALTHY_SUBSET'
        else:
            baselines[p]=None; basis[p]='NOT_OBSERVABLE_NO_MEASURED_BASELINE'
    return baselines,basis,measured


def pf_self_stability_score(series, baseline, measured_history=None):
    s=pd.to_numeric(series,errors='coerce').astype(float)
    hist=pf_clean(measured_history) if measured_history is not None else pd.Series(dtype=float)
    if hist.empty: hist=s.loc[s.index<=AS_OF].dropna()
    mad=float(np.median(np.abs(hist-baseline))*1.4826) if len(hist) else 0.0
    scale=max(mad,abs(baseline)*0.02,1e-6)
    return (100.0/(1.0+np.abs(s-baseline)/scale)).clip(0,100)


def pf_consequence_resilience(result):
    """Return consequence resilience only when historical analogue evidence exists."""
    impact=result.get('impact',{}); similar=result.get('similar_incidents',pd.DataFrame())
    if similar is None or similar.empty:
        return None,'CONDITION_ONLY_NO_HISTORICAL_ANALOGUE'
    raw_d=safe_float(impact.get('downtime'),np.nan); raw_l=safe_float(impact.get('loss'),np.nan)
    cur_d=max(float(raw_d),0.0) if np.isfinite(raw_d) else np.nan
    cur_l=max(float(raw_l),0.0) if np.isfinite(raw_l) else np.nan
    d=pd.to_numeric(similar.get('Downtime (hrs)',pd.Series(dtype=float)),errors='coerce').dropna()
    loss_col='Total Loss (k US$)' if 'Total Loss (k US$)' in similar else ('Act. Loss (k US$)' if 'Act. Loss (k US$)' in similar else None)
    l=pd.to_numeric(similar.get(loss_col,pd.Series(dtype=float)),errors='coerce').dropna() if loss_col else pd.Series(dtype=float)
    if (not np.isfinite(cur_d) and not np.isfinite(cur_l)) or (d.empty and l.empty):
        return None,'CONDITION_ONLY_INSUFFICIENT_CONSEQUENCE_EVIDENCE'
    bd=float(d[d>0].median()) if (d>0).any() else np.nan
    bl=float(l[l>0].median()) if (l>0).any() else np.nan
    ratios=[]
    if np.isfinite(cur_d) and np.isfinite(bd) and bd>0: ratios.append(cur_d/bd)
    if np.isfinite(cur_l) and np.isfinite(bl) and bl>0: ratios.append(cur_l/bl)
    if not ratios: return None,'CONDITION_ONLY_INSUFFICIENT_CONSEQUENCE_EVIDENCE'
    ratio=max(float(np.sqrt(np.prod(np.maximum(ratios,1e-6)))) if len(ratios)>1 else float(ratios[0]),1e-6)
    return float(np.clip(100.0/max(ratio,1.0),0,100)),'HISTORICAL_ANALOGUE_CONSEQUENCE_CONTEXT'


def pf_duration_based_downtime(asset, window_hours=720.0):
    """Duration-weighted observed downtime; long timestamp gaps are not silently treated as observed hours."""
    obs=asset.get('df_hourly_observed',pd.DataFrame()).copy()
    start=AS_OF-pd.Timedelta(hours=float(window_hours))
    if obs.empty or 'Timestamp' not in obs or 'RUN_STATUS' not in obs:
        return dict(Downtime_h=0.0,Observed_Coverage_h=0.0,Availability_pct='NOT_OBSERVABLE',Status='NO_RECENT_OBSERVATION')
    obs['Timestamp']=pd.to_datetime(obs['Timestamp'],errors='coerce');obs=obs.dropna(subset=['Timestamp']).sort_values('Timestamp').drop_duplicates('Timestamp',keep='last')
    obs=obs.loc[obs.Timestamp.le(AS_OF)]
    if obs.empty:
        return dict(Downtime_h=0.0,Observed_Coverage_h=0.0,Availability_pct='NOT_OBSERVABLE',Status='NO_RECENT_OBSERVATION')
    diffs=obs.Timestamp.diff().dt.total_seconds().div(3600).dropna(); regular=diffs[(diffs>0)&(diffs<=6)]
    nominal=float(regular.median()) if len(regular) else 1.0; max_hold=max(1.5*nominal,nominal)
    prev=obs.loc[obs.Timestamp.lt(start)].tail(1);inside=obs.loc[obs.Timestamp.ge(start)]
    z=pd.concat([prev,inside],ignore_index=True).sort_values('Timestamp').drop_duplicates('Timestamp',keep='last').reset_index(drop=True)
    if z.empty or not z.Timestamp.ge(start).any():
        return dict(Downtime_h=0.0,Observed_Coverage_h=0.0,Availability_pct='NOT_OBSERVABLE',Status='NO_RECENT_OBSERVATION')
    times=z.Timestamp.to_list(); downtime=coverage=running_h=0.0
    for i,row in z.iterrows():
        t=pd.Timestamp(row.Timestamp); seg_start=max(t,start)
        next_t=(pd.Timestamp(z.iloc[i+1].Timestamp) if i+1<len(z) else AS_OF)
        seg_end=min(next_t,AS_OF,t+pd.Timedelta(hours=max_hold))
        dur=max((seg_end-seg_start).total_seconds()/3600.0,0.0)
        if dur<=0: continue
        rs=str(row.get('RUN_STATUS','')).strip().upper()
        if rs not in {'ON','OFF'}: continue
        valid=True; is_running=(rs=='ON')
        if 'AMP' in z.columns and pd.notna(row.get('AMP')):
            amp=safe_float(row.get('AMP'),np.nan)
            if np.isfinite(amp): is_running=is_running and amp>0.10*asset.get('fla',150.0)
        if valid:
            coverage+=dur
            if is_running: running_h+=dur
            else: downtime+=dur
    if coverage<=1e-9:
        return dict(Downtime_h=0.0,Observed_Coverage_h=0.0,Availability_pct='NOT_OBSERVABLE',Status='NO_RECENT_OBSERVATION')
    availability=100.0*running_h/coverage
    status='OBSERVED' if coverage>=0.95*window_hours else 'PARTIAL_OBSERVATION'
    return dict(Downtime_h=float(downtime),Observed_Coverage_h=float(coverage),Availability_pct=float(availability),Status=status)


def pf_actual_channel_baseline(asset, channel, params, require_running=True):
    """Measured healthy/running baseline for executive load/throughput ratios."""
    ch=pf_channels(asset).get(channel)
    if ch is None or ch.get('actual') is None or len(ch['actual'])==0: return None,'NOT_OBSERVABLE_NO_MEASURED_BASELINE'
    s=pf_clean(ch['actual']); keep=pd.Series(True,index=s.index)
    h=asset.get('df_hourly_observed',pd.DataFrame()).copy()
    if not h.empty:
        h=h.set_index('Timestamp').sort_index()
        if require_running and 'RUN_STATUS' in h:
            keep &= h['RUN_STATUS'].reindex(s.index).astype(str).str.upper().eq('ON').fillna(False)
        if require_running and 'AMP' in h:
            amps=pd.to_numeric(h['AMP'].reindex(s.index),errors='coerce')
            keep &= amps.gt(.10*asset.get('fla',150.0)).fillna(False)
    # Constrain baseline to measured-normal engineering observations when timestamps overlap.
    normal_votes=[]
    for p,v in params.items():
        av=pf_clean(v.get('actual',pd.Series(dtype=float)))
        if av.empty: continue
        lim=v['limit']; st=av.reindex(s.index).map(lambda x: directional_engineering_state(x,lim) if pd.notna(x) else 'DATA_GAP')
        observed=st.ne('DATA_GAP')
        if observed.any(): normal_votes.append((~observed)|st.eq('NORMAL'))
    if normal_votes:
        healthy=pd.concat(normal_votes,axis=1).all(axis=1); keep &= healthy
    selected=s.loc[keep]
    if len(selected): return float(selected.median()),'MEASURED_HEALTHY_RUNNING_BASELINE'
    return float(s.median()),'MEASURED_HISTORY_BASELINE_NO_HEALTHY_OVERLAP'


def pf_kpi_data_basis(params):
    sources={str(v.get('source','')) for v in params.values()}
    ages=[safe_float(v.get('data_age_h'),np.nan) for v in params.values()]
    max_age=max([x for x in ages if np.isfinite(x)],default=np.inf)
    if sources and sources.issubset({'ACTUAL','WEEKLY_MEASUREMENT_UPDATE'}): return 'MEASURED'
    if max_age>24*7: return 'STALE/OLD DATA + MODEL ESTIMATE'
    if any('FORECAST' in x or x=='ASOF_ESTIMATE' for x in sources): return 'ESTIMATED/FORECAST'
    return 'ESTIMATED'


def executive_asof_data(results):
    """Decision KPIs with measured baselines and explicit provenance; no model fitting occurs here."""
    global PF_EXECUTIVE_CACHE
    if PF_EXECUTIVE_CACHE is not None: return PF_EXECUTIVE_CACHE
    start=AS_OF-pd.Timedelta(days=SINGLE_PANE_LINE_DAYS);grid=pd.date_range(start,AS_OF,freq='h');metrics=[];trends={}
    for r in results:
        a=r['asset'];tag=r['tag_number'];params=r['projection']['parameters'];limits=build_limit_dict(a['df_limits'])
        pseries={p:v['trace'].Estimate.reindex(grid).astype(float) for p,v in params.items()}
        baselines,baseline_basis,measured_hist=pf_asset_baselines(params,limits)
        frame=pd.DataFrame(index=grid);frame.index.name='Timestamp';health_parts=[];stability_parts=[]
        for p,series in pseries.items():
            base=baselines.get(p)
            if base is None or not np.isfinite(base): continue
            lim=limits[p];health_parts.append(series.map(lambda x:engineering_margin_score(float(x),base,lim)).astype(float).rename(p));stability_parts.append(pf_self_stability_score(series,base,measured_hist.get(p)).rename(p))
        if health_parts:
            frame['Asset Health Score']=pd.concat(health_parts,axis=1).min(axis=1).clip(0,100)
            stability=pd.concat(stability_parts,axis=1).mean(axis=1).clip(0,100)
            health_basis='MEASURED_HEALTHY_BASELINE -> CANONICAL_CURRENT'
        else:
            # No fake NORMAL/index: this should be visible as a data-quality defect.
            raise ValueError(f'{tag}: executive health baseline has no measured engineering observations')
        channels=pf_channels(a)
        if 'PLANT_RATE' in channels:
            rate=channels['PLANT_RATE']['trace'].Estimate.reindex(grid).astype(float);base,rate_basis=pf_actual_channel_baseline(a,'PLANT_RATE',params)
            if base is not None and abs(base)>1e-9:
                throughput=(100.0*rate/base).clip(0,100);frame['Operating Performance Index']=(.60*throughput+.40*stability).clip(0,100);op_basis='MEASURED_HEALTHY_PLANT_RATE_BASELINE + PARAMETER_STABILITY'
            else:
                frame['Operating Performance Index']=(.55*frame['Asset Health Score']+.45*stability).clip(0,100);op_basis='CONDITION_ONLY_NO_MEASURED_RATE_BASELINE'
        else:
            frame['Operating Performance Index']=(.55*frame['Asset Health Score']+.45*stability).clip(0,100);op_basis='HEALTH + PARAMETER_STABILITY_PROXY'
        if 'AMP' in channels and tag!='HE-3301':
            load=channels['AMP']['trace'].Estimate.reindex(grid).astype(float);base,load_base_basis=pf_actual_channel_baseline(a,'AMP',params)
            load_name='Electrical Load Proxy';load_basis='AMP_LOAD_PROXY | '+load_base_basis
        elif 'Heat Duty' in pseries:
            load=pseries['Heat Duty'];base=baselines.get('Heat Duty');load_base_basis=baseline_basis.get('Heat Duty','NOT_OBSERVABLE');load_name='Thermal Duty Index';load_basis='HEAT_DUTY_PROXY | '+load_base_basis
        else:
            available=[(p,b) for p,b in baselines.items() if b is not None and np.isfinite(b) and abs(b)>1e-9]
            if not available: raise ValueError(f'{tag}: no measured baseline available for Operating Load Proxy')
            agg=pd.concat([pseries[p]/b for p,b in available],axis=1).abs().mean(axis=1);load=agg;base=1.0;load_name='Operating Load Proxy';load_base_basis='MEASURED_ENGINEERING_BASELINES';load_basis='NORMALIZED_OPERATING_LOAD_PROXY | '+load_base_basis
        frame['Load Proxy Index']=(100.0*load/max(float(base),1e-9)).clip(0,300) if load_name!='Operating Load Proxy' else (100.0*load).clip(0,300)
        consequence_score,consequence_basis=pf_consequence_resilience(r)
        if consequence_score is None:
            frame['Reliability & Consequence Index']=frame['Asset Health Score'];reliability_basis='CONDITION_ONLY | '+consequence_basis
        else:
            frame['Reliability & Consequence Index']=(.70*frame['Asset Health Score']+.30*float(consequence_score)).clip(0,100);reliability_basis='CONDITION + HISTORICAL CONSEQUENCE | '+consequence_basis
        dt30=pf_duration_based_downtime(a,720.0)
        last_actual=max([v['last_actual'] for v in params.values() if pd.notna(v.get('last_actual'))],default=pd.NaT);data_age_h=(AS_OF-last_actual).total_seconds()/3600.0 if pd.notna(last_actual) else max(v['age_h'] for v in params.values())
        data_basis=pf_kpi_data_basis(params)
        row=dict(Asset=tag,As_Of=AS_OF,Last_Actual=last_actual,Data_Age_h=data_age_h,Data_Basis=data_basis,
            Asset_Health_Score=float(frame['Asset Health Score'].iloc[-1]),Health_KPI_Basis=health_basis,Health_Data_Basis=data_basis,
            Operating_Performance_Index=float(frame['Operating Performance Index'].iloc[-1]),Operating_KPI_Basis=op_basis,Operating_Data_Basis=data_basis,
            Load_Proxy_Index=float(frame['Load Proxy Index'].iloc[-1]),Load_Metric_Name=load_name,Load_KPI_Basis=load_basis,Load_Data_Basis=data_basis,
            Reliability_Consequence_Index=float(frame['Reliability & Consequence Index'].iloc[-1]),Reliability_KPI_Basis=reliability_basis,Reliability_Data_Basis=data_basis,
            Downtime_30d_h=dt30['Downtime_h'],Observed_Coverage_30d_h=dt30['Observed_Coverage_h'],Availability_30d_pct=dt30['Availability_pct'],Downtime_Status=dt30['Status'],Downtime_KPI_Basis='MEASURED RUN_STATUS/AMP DURATION',
            Historical_Consequence_Benchmark_Downtime_h=(safe_float(r.get('impact',{}).get('downtime'),np.nan) if np.isfinite(safe_float(r.get('impact',{}).get('downtime'),np.nan)) else 'NOT_AVAILABLE'),Historical_Consequence_Benchmark_Loss_kUSD=(safe_float(r.get('impact',{}).get('loss'),np.nan) if np.isfinite(safe_float(r.get('impact',{}).get('loss'),np.nan)) else 'NOT_AVAILABLE'),
            Measured_Condition=r['condition'].get('measured_overall_state',r['condition'].get('overall_state','DATA_GAP')),Forecast_Condition=r['projection']['state'],Forecast_Risk_168h=r['projection']['risk'],Forecast_Quality=r['projection']['quality'],Asset_Criticality=ASSET_CRITICALITY.get(tag,'MEDIUM'),Asset_Criticality_Basis='BUSINESS_RULE_ASSUMPTION_REVIEW_WITH_PLANT_OWNER')
        metrics.append(row);trends[tag]=frame
    metrics_df=pd.DataFrame(metrics);numeric=['Asset_Health_Score','Operating_Performance_Index','Load_Proxy_Index','Reliability_Consequence_Index','Downtime_30d_h','Observed_Coverage_30d_h']
    if not np.isfinite(metrics_df[numeric].to_numpy(float)).all(): raise ValueError('Executive KPI transformation produced a non-finite decision value')
    PF_EXECUTIVE_CACHE=(metrics,trends);return PF_EXECUTIVE_CACHE


def case2_executive_domain_kpis(results, executive_df):
    """Build one governed KPI row per asset for the five executive domains in Case 2.

    Important governance rule:
    - Production and downtime use observed plant/work-status data when available.
    - Operational performance is a derived decision KPI.
    - Energy is a relative load proxy because the workbook has no kWh/MW/steam/fuel meter.
    - Emission is *not* reported as kg CO2e.  For electrically driven assets only, a
      relative Scope-2-like emission-intensity proxy is provided under the explicit
      assumption of a constant electricity emission factor.  This makes the Case-2
      domain visible without fabricating a physical emission measurement.
    """
    rows = []
    ex = executive_df.set_index('Asset') if not executive_df.empty and 'Asset' in executive_df else pd.DataFrame()

    for r in results:
        tag = r['tag_number']
        asset = r['asset']
        params = r['projection']['parameters']
        channels = pf_channels(asset)
        erow = ex.loc[tag] if (not ex.empty and tag in ex.index) else pd.Series(dtype=object)

        # Production: native Plant Rate retained, plus a normalized index against the
        # measured healthy/running baseline.  This is separate from OPI.
        production_value = np.nan
        production_index = np.nan
        production_unit = ''
        production_source = 'NOT_OBSERVABLE'
        production_basis = 'Plant Rate unavailable'
        if 'PLANT_RATE' in channels:
            tr = channels['PLANT_RATE']['trace']
            ts = AS_OF if AS_OF in tr.index else tr.index[tr.index <= AS_OF].max()
            if pd.notna(ts):
                z = tr.loc[ts]
                production_value = safe_float(z.Estimate, np.nan)
                production_source = str(z.Source)
                base, base_basis = pf_actual_channel_baseline(asset, 'PLANT_RATE', params)
                if base is not None and np.isfinite(safe_float(base, np.nan)) and abs(float(base)) > 1e-12:
                    production_index = float(np.clip(100.0 * production_value / float(base), 0.0, 300.0))
                    production_basis = 'Plant Rate / measured healthy-running Plant Rate baseline | ' + str(base_basis)
                # Recover the engineering unit from the tag dictionary when possible.
                tags = asset.get('df_tags', pd.DataFrame())
                if not tags.empty and 'PI Tag' in tags.columns:
                    rr = tags.loc[tags['PI Tag'].astype(str).str.upper().eq('PLANT_RATE')]
                    if not rr.empty:
                        production_unit = str(rr.iloc[0].get('engunits', '') or '')

        # Energy-related load proxy is already governed in the executive layer.
        energy_index = safe_float(erow.get('Load_Proxy_Index'), np.nan)
        energy_metric = str(erow.get('Load_Metric_Name', 'Not observable'))
        energy_basis = str(erow.get('Load_KPI_Basis', 'No validated load proxy'))
        energy_observability = 'INDIRECT / PROXY' if np.isfinite(energy_index) else 'NOT OBSERVABLE'

        # Relative energy intensity versus production.  100 = same relative load per
        # relative production as the healthy baseline.  It is dimensionless, not GJ/t.
        energy_intensity = np.nan
        if np.isfinite(energy_index) and np.isfinite(production_index) and production_index > 1e-12:
            energy_intensity = float(np.clip(100.0 * energy_index / production_index, 0.0, 500.0))

        # Relative emission-intensity proxy is only defensible for electrical-load
        # proxies under a constant grid emission factor.  Heat Duty is not automatically
        # an emission source, therefore HE-3301 remains not observable for emission.
        emission_proxy = np.nan
        emission_observability = 'NOT OBSERVABLE'
        emission_basis = 'Direct CEMS/fuel/emission-factor data unavailable'
        if np.isfinite(energy_intensity) and energy_metric.lower().startswith('electrical load proxy'):
            emission_proxy = energy_intensity
            emission_observability = 'INDIRECT PROXY — ELECTRICITY-RELATED'
            emission_basis = ('Relative electrical-load intensity × constant electricity emission-factor assumption; '
                              'dimensionless proxy only, not kg CO2e')

        rows.append(dict(
            Asset=tag,
            Production_Value=production_value,
            Production_Unit=production_unit,
            Production_Index=production_index,
            Production_Source=production_source,
            Production_Basis=production_basis,
            Energy_Load_Index=energy_index,
            Energy_Metric=energy_metric,
            Energy_Intensity_Index=energy_intensity,
            Energy_Observability=energy_observability,
            Energy_Basis=energy_basis,
            Emission_Intensity_Proxy=emission_proxy,
            Emission_Observability=emission_observability,
            Emission_Basis=emission_basis,
            Downtime_30d_h=safe_float(erow.get('Downtime_30d_h'), np.nan),
            Availability_30d_pct=safe_float(erow.get('Availability_30d_pct'), np.nan),
            Downtime_Observability='DIRECT / OBSERVED',
            Operational_Performance_Index=safe_float(erow.get('Operating_Performance_Index'), np.nan),
            Asset_Health_Score=safe_float(erow.get('Asset_Health_Score'), np.nan),
            Reliability_Consequence_Index=safe_float(erow.get('Reliability_Consequence_Index'), np.nan),
            Operational_Performance_Observability='DERIVED DECISION KPI',
        ))
    return pd.DataFrame(rows)


def case2_requirement_coverage(executive_df, case2_kpis=None):
    """Map implementation status to the five executive domains named in CALIBER Case 2."""
    case2_kpis = pd.DataFrame() if case2_kpis is None else case2_kpis
    has_rate = bool(not case2_kpis.empty and case2_kpis.get('Production_Index', pd.Series(dtype=float)).notna().any())
    has_downtime = bool('Downtime_30d_h' in executive_df.columns and executive_df['Downtime_30d_h'].notna().any())
    has_load = bool(not case2_kpis.empty and case2_kpis.get('Energy_Load_Index', pd.Series(dtype=float)).notna().any())
    has_emission_proxy = bool(not case2_kpis.empty and case2_kpis.get('Emission_Intensity_Proxy', pd.Series(dtype=float)).notna().any())
    has_health = bool('Asset_Health_Score' in executive_df.columns and executive_df['Asset_Health_Score'].notna().any())

    rows = [
        dict(
            Case2_Domain='Production', Coverage_Status='COVERED', Observability='DIRECT + DERIVED',
            Dashboard_Metric='Plant Rate + Production Index + Operating Performance Index',
            Data_Basis='Observed Plant Rate where available; normalized against measured healthy/running baseline',
            Interpretation='Shows native throughput and relative production performance without replacing the original production unit.',
            Limitation='Production Index is normalized; native Plant Rate remains the physical production measurement.' if has_rate else 'Production is not observable in the current runtime.'
        ),
        dict(
            Case2_Domain='Energy', Coverage_Status='PARTIAL — GOVERNED PROXY', Observability='INDIRECT / PROXY',
            Dashboard_Metric='Energy-related Load Index + Relative Energy Intensity + forward outlook',
            Data_Basis='Motor current (AMP) for electrically driven assets; Heat Duty for HE-3301',
            Interpretation='Tracks relative load and load-per-relative-production against measured healthy/running baselines.',
            Limitation='Not kWh, MW, steam, fuel, or GJ. Direct energy consumption requires validated power/utility metering.' if has_load else 'No energy-related load proxy is observable.'
        ),
        dict(
            Case2_Domain='Emission', Coverage_Status=('PARTIAL — GOVERNED PROXY' if has_emission_proxy else 'DATA SOURCE REQUIRED'),
            Observability=('INDIRECT PROXY — ELECTRICITY-RELATED' if has_emission_proxy else 'NOT OBSERVABLE'),
            Dashboard_Metric='Relative Electricity-related Emission Intensity Proxy',
            Data_Basis='Electrical-load intensity with constant electricity emission-factor assumption; HE-3301 thermal duty is not converted to emission',
            Interpretation='Makes direction of electricity-related indirect emission intensity visible without fabricating kg CO2e.',
            Limitation='Not a CEMS/stack measurement and not absolute CO2e. Direct emission KPI requires CEMS or governed energy × validated emission factor.'
        ),
        dict(
            Case2_Domain='Downtime', Coverage_Status='COVERED', Observability='DIRECT / OBSERVED',
            Dashboard_Metric='Downtime 30 d / Availability / Observed Coverage',
            Data_Basis='Duration-weighted RUN_STATUS with AMP running check',
            Interpretation='Quantifies observed lost operating time while reporting data coverage so missing data are not interpreted as zero downtime.',
            Limitation='Accuracy depends on RUN_STATUS/AMP coverage and timestamp integrity.' if has_downtime else 'Downtime is not observable in the current runtime.'
        ),
        dict(
            Case2_Domain='Operational Performance', Coverage_Status='COVERED', Observability='DERIVED DECISION KPI',
            Dashboard_Metric='Asset Health Score / Operating Performance Index / Reliability & Consequence Index',
            Data_Basis='Engineering margins, measured healthy baselines, production/load context, stability, and historical consequence',
            Interpretation='Converts heterogeneous equipment signals into decision-level condition and reliability indicators while retaining provenance.',
            Limitation='Decision indices are not physical measurements or failure probabilities.' if has_health else 'Operational performance is not observable in the current runtime.'
        ),
    ]
    return pd.DataFrame(rows)


def case2_energy_proxy_forecast(results, executive_df):
    """Forward outlook for production, energy proxy, relative intensity, and emission proxy.

    This reuses existing canonical traces and does not fit a second model.  All energy
    and emission outputs are dimensionless proxies unless direct meters/factors are
    later integrated.
    """
    rows = []
    executive_lookup = executive_df.set_index('Asset') if not executive_df.empty and 'Asset' in executive_df else pd.DataFrame()
    horizons = [('H+24', 24), ('H+72', 72), ('H+168', 168)]

    for r in results:
        tag = r['tag_number']
        asset = r['asset']
        params = r['projection']['parameters']
        channels = pf_channels(asset)

        # Resolve the energy-related load trace and baseline.
        load_name = None; load_basis = None; load_trace = None; load_base = None
        if 'AMP' in channels and tag != 'HE-3301':
            load_name = 'Electrical Load Proxy (motor current)'
            load_trace = channels['AMP']['trace']
            load_base, base_basis = pf_actual_channel_baseline(asset, 'AMP', params)
            load_basis = 'AMP / measured healthy-running AMP baseline | ' + str(base_basis)
        elif 'Heat Duty' in params:
            load_name = 'Thermal Load Proxy (heat duty)'
            load_trace = params['Heat Duty']['trace']
            baselines, baseline_basis, _ = pf_asset_baselines(params, build_limit_dict(asset['df_limits']))
            load_base = baselines.get('Heat Duty')
            load_basis = 'Heat Duty / measured healthy engineering baseline | ' + str(baseline_basis.get('Heat Duty', 'NOT_OBSERVABLE'))

        # Resolve Plant Rate so energy intensity can be forecast against relative production.
        production_trace = channels.get('PLANT_RATE', {}).get('trace') if 'PLANT_RATE' in channels else None
        production_base = None; production_basis = 'Plant Rate unavailable'
        if production_trace is not None:
            production_base, pbasis = pf_actual_channel_baseline(asset, 'PLANT_RATE', params)
            production_basis = 'Plant Rate / measured healthy-running baseline | ' + str(pbasis)

        valid_load = load_trace is not None and load_base is not None and np.isfinite(safe_float(load_base, np.nan)) and abs(float(load_base)) > 1e-12
        valid_prod = production_trace is not None and production_base is not None and np.isfinite(safe_float(production_base, np.nan)) and abs(float(production_base)) > 1e-12
        is_electrical = bool(load_name and load_name.lower().startswith('electrical load proxy'))

        current = safe_float(executive_lookup.loc[tag, 'Load_Proxy_Index'], np.nan) if tag in executive_lookup.index else np.nan
        rows.append(dict(
            Asset=tag, Horizon='AS-OF', Target_Time=AS_OF,
            Energy_Load_Index=current,
            Energy_Lower=np.nan, Energy_Upper=np.nan,
            Production_Index=np.nan, Energy_Intensity_Index=np.nan,
            Emission_Intensity_Proxy=np.nan,
            Proxy=load_name or 'Not observable', Source='EXECUTIVE_CURRENT' if np.isfinite(current) else 'NOT_OBSERVABLE',
            Quality='CURRENT' if np.isfinite(current) else 'NOT_OBSERVABLE',
            Energy_Basis=load_basis or 'No validated load-proxy baseline', Production_Basis=production_basis,
            Emission_Basis=('Constant electricity emission-factor assumption; dimensionless proxy only' if is_electrical else 'Not observable from current asset data'),
            Interpretation='Index 100 is the relevant measured healthy/running baseline; no physical kWh/MW/GJ or kg CO2e is claimed.'
        ))

        if not valid_load:
            continue

        for label, hours in horizons:
            t = AS_OF + pd.Timedelta(hours=hours)
            if t not in load_trace.index:
                continue
            z = load_trace.loc[t]
            eidx = 100.0 * safe_float(z.Estimate, np.nan) / float(load_base)
            elo = 100.0 * safe_float(z.Lower, np.nan) / float(load_base)
            ehi = 100.0 * safe_float(z.Upper, np.nan) / float(load_base)
            if elo > ehi: elo, ehi = ehi, elo

            pidx = np.nan
            if valid_prod and t in production_trace.index:
                pz = production_trace.loc[t]
                pidx = 100.0 * safe_float(pz.Estimate, np.nan) / float(production_base)

            intensity = np.nan
            if np.isfinite(eidx) and np.isfinite(pidx) and pidx > 1e-12:
                intensity = 100.0 * eidx / pidx
            emission_proxy = intensity if (is_electrical and np.isfinite(intensity)) else np.nan

            rows.append(dict(
                Asset=tag, Horizon=label, Target_Time=t,
                Energy_Load_Index=float(np.clip(eidx, 0.0, 300.0)) if np.isfinite(eidx) else np.nan,
                Energy_Lower=float(np.clip(elo, 0.0, 300.0)) if np.isfinite(elo) else np.nan,
                Energy_Upper=float(np.clip(ehi, 0.0, 300.0)) if np.isfinite(ehi) else np.nan,
                Production_Index=float(np.clip(pidx, 0.0, 300.0)) if np.isfinite(pidx) else np.nan,
                Energy_Intensity_Index=float(np.clip(intensity, 0.0, 500.0)) if np.isfinite(intensity) else np.nan,
                Emission_Intensity_Proxy=float(np.clip(emission_proxy, 0.0, 500.0)) if np.isfinite(emission_proxy) else np.nan,
                Proxy=load_name, Source=str(z.Source), Quality=str(z.Quality),
                Energy_Basis=load_basis, Production_Basis=production_basis,
                Emission_Basis=('Constant electricity emission-factor assumption; dimensionless proxy only' if is_electrical else 'Not observable from current asset data'),
                Interpretation='Forecast of relative load and intensity only; not a forecast of physical energy or absolute emissions.'
            ))
    return pd.DataFrame(rows)

def pf_native_weekly_export(results):
    rows=[]
    for r in results:
        asset=r['asset'];tag=r['tag_number']
        for p,v in r['projection']['parameters'].items():
            cal=native_weekly_grid(asset,p)
            measured={(pd.Timestamp(row.Date)):float(row[p]) for _,row in v['weekly'].iterrows()} if len(v['weekly']) else {}
            for _,row in cal.iterrows():
                target=pd.Timestamp(row['Forecast_Target_Date']); available=pd.Timestamp(row['Available_At']) if pd.notna(row['Available_At']) else pd.NaT
                # Released historical measurements are evaluated when they actually became available; future rows are evaluated at their native target date.
                eval_time=(available if row['Weekly_Basis']=='MEASURED_WEEKLY' and pd.notna(available) and available<=AS_OF else target).floor('h')
                ts=min(max(eval_time,v['trace'].index.min()),v['trace'].index.max()); tr=v['trace'].loc[ts]
                rows.append({'Asset':tag,'Parameter':p,'Measurement_Date':row['Measurement_Date'],'Available_At':available,'Forecast_Target_Date':target,'Canonical_Evaluation_Time':ts,'Weekly_Basis':row['Weekly_Basis'],'Actual_Weekly':measured.get(target,np.nan),'Estimate':float(tr.Estimate),'Lower':float(tr.Lower),'Upper':float(tr.Upper),'Unit':v['limit']['unit'],'Source':tr.Source,'Quality':tr.Quality,'Model':tr.Model,'Validation_N':tr.Validation_N,'Validation_MAE':tr.Validation_MAE,'Validation_RMSE':tr.Validation_RMSE})
    return pd.DataFrame(rows)

def pf_export(results, events, executive=None):
    """V11 compact operational workbook. Full traces are emitted only in AUDIT_MODE."""
    ensure_output_dir()
    if executive is None: executive=executive_asof_data(results)
    ex_metrics,_=executive; executive_df=pd.DataFrame(ex_metrics)
    parameter_rows=[]; forecast_rows=[]; validation_rows=[]; lineage=[]; full_traces=[]; full_dcs=[]; full_validation=[]
    for r in results:
        tag=r['tag_number'];a=r['asset']
        for p,v in r['projection']['parameters'].items():
            parameter_rows.append(dict(Asset=tag,Parameter=p,As_Of=AS_OF,Value=v['value'],Lower=v['lower'],Upper=v['upper'],Unit=v['limit']['unit'],State=v['state'],Source=v['source'],Quality=v['quality'],Model=v['model']['model'],Model_Type=v['model_type'],MAE=v['mae'],RMSE=v['rmse'],Skill=v['skill'],Last_Actual=v.get('last_actual'),Last_Weekly=v['last_lab'],Data_Age_h=v.get('data_age_h',v['age_h'])))
            tr=v['trace']
            for label,h in [('H+24',24),('H+72',72),('H+168',168)]:
                t=AS_OF+pd.Timedelta(hours=h)
                if t in tr.index:
                    z=tr.loc[t];forecast_rows.append(dict(Asset=tag,Parameter=p,Horizon=label,Target_Time=t,Estimate=z.Estimate,Lower=z.Lower,Upper=z.Upper,State=directional_engineering_state(float(z.Estimate),v['limit']),Source=z.Source,Quality=z.Quality,Model=z.Model))
            # Keep validation visible per deployed decision horizon, not only as a pooled MAE.
            records=pd.DataFrame(v['model'].get('records',[]))
            horizons=(PF_WEEKLY_HORIZONS_H if v.get('actual',pd.Series(dtype=float)).empty else PF_HORIZONS_H)
            deployed_name=v['model']['model']
            for H in horizons:
                if records.empty:
                    gm=pd.DataFrame(); gp=pd.DataFrame()
                else:
                    if 'Relevant_Horizon_H' in records.columns:
                        hmask=pd.to_numeric(records['Relevant_Horizon_H'],errors='coerce').eq(float(H))
                    else:
                        hh=pd.to_numeric(records.get('Horizon_H'),errors='coerce'); hmask=(hh-float(H)).abs().le(max(1.0,.40*float(H)))
                    gm=records.loc[hmask & records['Model'].astype(str).eq(str(deployed_name))]
                    if deployed_name=='State-Space Fusion' and 'Config' in records.columns and v['model'].get('config_index') is not None:
                        gm=gm.loc[gm['Config'].astype(str).eq(str(v['model']['config_index']))]
                    gp=records.loc[hmask & records['Model'].astype(str).eq('Persistence')]
                def _m(g):
                    if g.empty: return (np.nan,np.nan,0)
                    e=pd.to_numeric(g['Error'],errors='coerce').dropna().to_numpy(float)
                    return (float(np.mean(np.abs(e))) if len(e) else np.nan,float(np.sqrt(np.mean(e**2))) if len(e) else np.nan,int(len(e)))
                cmae,crmse,cn=_m(gm);pmae,prmse,pn=_m(gp)
                skill=(1-cmae/pmae) if np.isfinite(cmae) and np.isfinite(pmae) and pmae>1e-12 else np.nan
                beats=(deployed_name!='Persistence' and np.isfinite(cmae) and np.isfinite(pmae) and cmae < pmae*PF_IMPROVEMENT_THRESHOLD)
                label=(f'Week+{int(H/168)}' if v.get('actual',pd.Series(dtype=float)).empty else f'H+{int(H)}')
                validation_rows.append(dict(Asset=tag,Parameter=p,Relevant_Horizon=label,Horizon_H=float(H),Deployed_Model=deployed_name,Persistence_MAE=pmae,Persistence_RMSE=prmse,Model_MAE=cmae,Model_RMSE=crmse,Skill=skill,Validation_N=cn,Beats_Persistence_at_Horizon=beats,Overall_Deployment_Decision=('DEPLOY_MODEL' if v.get('beats_persistence') else 'PERSISTENCE/FALLBACK'),Validation_Method=v['validation_method']))
            lineage.append(dict(Asset=tag,Source='Engineering Parameter',Parameter=p,Last_Actual=v.get('last_actual'),Last_Weekly=v['last_lab'],Data_Age_h=v.get('data_age_h',v['age_h']),Channel_Mapping=v.get('suffix'),Unit=v['limit']['unit'],Quality=v['quality'],Physics_Candidate=v['physics_candidate']))
            if AUDIT_MODE:
                x=tr.copy();x['Asset']=tag;x['Parameter']=p;x.index.name='Timestamp';full_traces.append(x.reset_index());full_validation.extend(dict(rec,Asset=tag,Parameter=p) for rec in v['model'].get('records',[]))
        if AUDIT_MODE:
            for c,d in pf_channels(a).items():
                x=d['trace'].copy();x['Asset']=tag;x['Channel']=c;x.index.name='Timestamp';full_dcs.append(x.reset_index())
    # Native weekly Week+1..4 summary
    weekly_native=pf_native_weekly_export(results)
    future_week=weekly_native.loc[weekly_native['Weekly_Basis'].eq('FORECAST_TARGET')].copy()
    future_week['Week_Index']=future_week.groupby(['Asset','Parameter']).cumcount()+1
    for _,z in future_week.loc[future_week.Week_Index.le(4)].iterrows():
        forecast_rows.append(dict(Asset=z.Asset,Parameter=z.Parameter,Horizon=f"Week+{int(z.Week_Index)}",Target_Time=z.Forecast_Target_Date,Estimate=z.Estimate,Lower=z.Lower,Upper=z.Upper,State='',Source=z.Source,Quality=z.Quality,Model=z.Model))
    parameter_df=pd.DataFrame(parameter_rows);forecast_df=pd.DataFrame(forecast_rows);validation_df=pd.DataFrame(validation_rows);lineage_df=pd.DataFrame(lineage)
    # Problem Tank / RCA evidence are main decision outputs.
    problem_rows=[];rca_rows=[]
    for r in results:
        ticket=r.get('ticket',{});e=r.get('rca_evidence',{});trig=trigger_short_text(r.get('triggers',[]));rca_ind=e.get('leading_hypothesis') or e.get('root_cause') or (e.get('priority_causes',[None])[0] if e.get('priority_causes') else '')
        problem_rows.append(dict(Problem_ID=ticket.get('ticket_id') or f"MONITOR-{r['tag_number']}",Asset=r['tag_number'],Trigger=trig,Severity=r['projection']['state'],Priority=r['priority'],Asset_Criticality=ASSET_CRITICALITY.get(r['tag_number'],'MEDIUM'),Asset_Criticality_Basis='BUSINESS_RULE_ASSUMPTION_REVIEW_WITH_PLANT_OWNER',RCA_Indication=((e.get('hypothesis_label') or rca_hypothesis_label(e.get('evidence_strength'))) + ': ' + str(rca_ind)) if rca_ind else 'No active RCA hypothesis',Evidence_Score=e.get('evidence_strength','NOT_TRIGGERED'),Recommended_Action=action_list_to_text(ticket.get('actions', [])),Owner=ticket.get('owner') or suggested_owner_role(r['asset']),SLA=priority_sla(r['priority']),Ticket_State=ticket.get('ticket_state',ticket.get('status','MONITOR')),Action_Status=ticket.get('action_status','NOT_STARTED'),Status=ticket.get('ticket_state',ticket.get('status','MONITOR'))))
        for c in e.get('candidates',[])[:TOP_K_RCA_DISPLAY]:
            rca_rows.append(dict(Asset=r['tag_number'],Matched_Incident=c.get('AR No'),Case_Similarity=c.get('Case Similarity'),Current_Evidence=structured_list_to_text(e.get('current_measured_evidence',[]), preferred_keys=('Evidence','Parameter','type')),Historical_Evidence=structured_list_to_text(e.get('historical_verified_evidence',[]), preferred_keys=('Evidence','Factor','Finding','Description')),Four_P=structured_list_to_text(e.get('verification_4p',[]), preferred_keys=('Factor','Verification','Evidence','Description')),Four_M=structured_list_to_text(e.get('verification_4m',[]), preferred_keys=('Factor','Verification','Evidence','Description')),CAPA=structured_list_to_text(e.get('capa',[]), preferred_keys=('Action','CAPA','Plan','Recommendation')),Evidence_Strength=e.get('evidence_strength')))
    problem_df=pd.DataFrame(problem_rows);rca_df=pd.DataFrame(rca_rows)
    # Executive snapshot joins decision fields from Problem Tank.
    executive_snapshot=executive_df.merge(problem_df[['Asset','Priority','RCA_Indication','Recommended_Action','Owner','SLA','Ticket_State','Action_Status','Status']],on='Asset',how='left')
    xlsx=os.path.join(OUTPUT_DIR,'V11_3_operational_dashboard.xlsx')
    with pd.ExcelWriter(xlsx,engine='openpyxl') as writer:
        executive_snapshot.to_excel(writer,sheet_name='Executive Snapshot',index=False)
        problem_df.to_excel(writer,sheet_name='Problem Tank',index=False)
        rca_df.to_excel(writer,sheet_name='RCA Evidence',index=False)
        parameter_df.to_excel(writer,sheet_name='Parameter Snapshot',index=False)
        forecast_df.to_excel(writer,sheet_name='Forecast Summary',index=False)
        validation_df.to_excel(writer,sheet_name='Model Validation',index=False)
        lineage_df.to_excel(writer,sheet_name='Data Lineage',index=False)
    # Compact CSVs only in normal mode.
    executive_snapshot.to_csv(os.path.join(OUTPUT_DIR,'executive_snapshot.csv'),index=False);problem_df.to_csv(os.path.join(OUTPUT_DIR,'problem_tank.csv'),index=False);parameter_df.to_csv(os.path.join(OUTPUT_DIR,'parameter_asof.csv'),index=False);forecast_df.to_csv(os.path.join(OUTPUT_DIR,'forecast_summary.csv'),index=False);validation_df.to_csv(os.path.join(OUTPUT_DIR,'validation_summary.csv'),index=False)
    if AUDIT_MODE:
        if full_traces: pd.concat(full_traces,ignore_index=True).to_csv(os.path.join(OUTPUT_DIR,'complete_parameter_predictions_hourly.csv'),index=False)
        if full_dcs: pd.concat(full_dcs,ignore_index=True).to_csv(os.path.join(OUTPUT_DIR,'complete_DCS_predictions_hourly.csv'),index=False)
        pd.DataFrame(full_validation).to_csv(os.path.join(OUTPUT_DIR,'forecast_backtest_audit.csv'),index=False)
        weekly_native.to_csv(os.path.join(OUTPUT_DIR,'complete_parameter_predictions_weekly.csv'),index=False)
        pd.DataFrame(events).to_csv(os.path.join(OUTPUT_DIR,'asof_rca_events.csv'),index=False)

def pf_axis(ax, lim, start, end, weekly=False):
    ax.set_xlim(start,end); ax.grid(False); ax.axvline(AS_OF,color=PF_COLORS['now'],ls=':',lw=1.0)
    ax.axhline(lim['alarm'],color=PF_COLORS['alarm'],ls=':',lw=1.0); ax.axhline(lim['trip'],color=PF_COLORS['trip'],ls='-.',lw=1.0)
    ax.xaxis.set_major_locator(mdates.MonthLocator() if weekly else mdates.DayLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y' if weekly else '%d-%b'))
    ax.tick_params(axis='x',rotation=25,labelsize=8); ax.set_ylabel(lim['unit'],fontsize=9); ax.spines[['top','right']].set_visible(False)


def pf_panel(ax, v, start, end, weekly=False):
    tr=v['trace'].loc[start:end];lim=v['limit'];estimated=~tr.Source.eq('ACTUAL')
    ax.fill_between(tr.index,tr.Lower,tr.Upper,where=estimated,color=PF_COLORS['band'],alpha=.28,lw=0,label='Forecast uncertainty band')
    ax.plot(tr.index,tr.Estimate.where(estimated),color=PF_COLORS['prediction'],ls='--',lw=1.5,label='Estimate / forecast')
    actual=v['actual'].loc[start:min(end,AS_OF)]
    if len(actual): ax.plot(actual.index,actual,color=PF_COLORS['actual'],lw=1.1,label='Measured hourly')
    w=v['weekly'];w=w.loc[w.Date.between(start,min(end,AS_OF))] if len(w) else w
    if len(w): ax.scatter(w.Date,w[v['parameter']],s=24,color='black',zorder=5,label='Measured weekly')
    pf_axis(ax,lim,start,end,weekly);ax.set_title(v['parameter'],fontweight='bold',fontsize=10,pad=8)
    last_actual=v.get('last_actual');age_d=v.get('data_age_h',v['age_h'])/24.0
    label=(f"Forecast condition: {v['state']}\nAS-OF source: {v['source']}\nLast actual: {pf_time_text(last_actual)} | age: {age_d:.1f} d\n"
           f"Deployed: {v['model']['model']} | {v['quality']}\nValidation n={v['n']}, MAE={pf_metric_text(v['mae'])}, RMSE={pf_metric_text(v['rmse'])}")
    ax.text(.985,.97,label,transform=ax.transAxes,ha='right',va='top',fontsize=7.2,bbox=dict(facecolor='white',edgecolor='#D1D5DB',alpha=.96,pad=4))
    bottom,top=ax.get_ylim();ax.set_ylim(bottom,top+.32*(top-bottom));handles,labels=ax.get_legend_handles_labels()
    if handles:
        unique=dict(zip(labels,handles));ax.legend(unique.values(),unique.keys(),fontsize=7,loc='lower left',frameon=True)

def pf_plot_assets(results, weekly=False):
    start,end=(PF_START,PF_END) if weekly else (PF_HOURLY_START,PF_HOURLY_END)
    for r in results:
        fig,axes=plt.subplots(2,2,figsize=(16,9),squeeze=False);name='WEEKLY' if weekly else 'HOURLY';fig.suptitle(f"{r['tag_number']} | {name} CANONICAL TRACE | AS-OF 01 Aug 2026",fontsize=14,fontweight='bold')
        for ax,v in zip(axes.ravel(),r['projection']['parameters'].values()): pf_panel(ax,v,start,end,weekly)
        fig.text(.5,.018,'Solid = measured | dashed = reconstruction/gap forecast/future forecast | band = prediction error envelope | weekly markers retain native measurement dates',ha='center',fontsize=8);fig.tight_layout(rect=[0,.04,1,.94])
        if SAVE_PLOTS: fig.savefig(os.path.join(OUTPUT_DIR,f"PLOT{'2' if weekly else '1'}_{name}_{r['tag_number']}.png"),dpi=150,bbox_inches='tight')
        if SHOW_PLOTS: plt.show()
        plt.close(fig)



def plot_all_assets_hourly(results):
    pf_plot_assets(results,False)


def plot_all_assets_weekly(results):
    pf_plot_assets(results,True)


def generate_executive_dashboard(results, executive=None):
    if executive is None: executive=executive_asof_data(results)
    metrics,trends=executive;labels=[x['Asset'] for x in metrics];start=AS_OF-pd.Timedelta(days=SINGLE_PANE_LINE_DAYS);palette=['#285F87','#D29744','#458C7C','#A76885','#7875A6'];fig,axes=plt.subplots(2,4,figsize=(20,10.5));axes=axes.ravel();fig.suptitle(f'PLANT-WIDE EXECUTIVE SINGLE PANE OF GLASS\nDecision-level metrics with explicit provenance | AS-OF {AS_OF:%d %b %Y %H:%M}',fontsize=16,fontweight='bold')
    panels=[('Asset_Health_Score','Asset Health Score','0–100',1),('Operating_Performance_Index','Operating Performance Index','0–100',1),('Load_Proxy_Index','Operating / Energy-related Load Proxy','baseline = 100',1),('Downtime_30d_h','Actual Downtime – Last 30 Days','actual hours',1),('Reliability_Consequence_Index','Reliability & Consequence Index','0–100',1)]
    for ax,(key,title,unit,dig) in zip(axes,panels):
        values=np.asarray([x[key] for x in metrics],float);bars=ax.bar(labels,values,color=palette,width=.62);top=max(float(values.max()) if len(values) else 1.0,100.0 if key not in {'Downtime_30d_h'} else 1.0);ax.set_ylim(0,top*1.20);ax.set_title(title,fontweight='bold',fontsize=10);ax.set_ylabel(unit);ax.tick_params(axis='x',rotation=35,labelsize=8);ax.grid(False);ax.spines[['top','right']].set_visible(False)
        for i,(bar,value) in enumerate(zip(bars,values)):
            label=f'{value:.{dig}f}'
            if key=='Downtime_30d_h':
                m=metrics[i];label += f" h\n{m.get('Downtime_Status','')}\ncoverage {safe_float(m.get('Observed_Coverage_30d_h'),0.0):.0f} h"
            ax.text(bar.get_x()+bar.get_width()/2,value+top*.02,label,ha='center',va='bottom',fontsize=7 if key=='Downtime_30d_h' else 8)
        if key=='Load_Proxy_Index': ax.axhline(100,color=PF_COLORS['now'],ls=':',lw=1,label='Own healthy/load baseline')
        if key=='Load_Proxy_Index': ax.legend(fontsize=7,loc='upper right')
    specs=[('Asset Health Score','Asset Health Score – 30 Days','0–100'),('Operating Performance Index','Operating Performance – 30 Days','0–100'),('Reliability & Consequence Index','Reliability & Consequence – 30 Days','0–100')]
    for ax,(metric,title,unit) in zip(axes[5:],specs):
        for tag,color in zip(labels,palette): daily=trends[tag][metric].resample('D').mean();ax.plot(daily.index,daily,color=color,lw=1.4,label=tag)
        ax.set_xlim(start,AS_OF);ax.set_title(title,fontweight='bold',fontsize=10);ax.set_ylabel(unit);ax.xaxis.set_major_locator(mdates.DayLocator(interval=7));ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%b'));ax.tick_params(axis='x',rotation=30,labelsize=8);ax.grid(False);ax.spines[['top','right']].set_visible(False);ax.legend(fontsize=7,ncol=2,loc='best')
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(facecolor=c,label=t) for t,c in zip(labels,palette)],loc='upper center',bbox_to_anchor=(.5,.925),ncol=len(labels),fontsize=8,frameon=False,title='Assets')
    fig.text(.5,.030,'Load panel is explicitly a proxy unless direct power/fuel/steam metering is available; no CO2 pseudo-measurement is shown.',ha='center',fontsize=8)
    fig.text(.5,.014,'Downtime is duration-weighted from measured RUN_STATUS/AMP over the last 30 days; coverage/status prevent missing data from being read as zero downtime. Measured and forecast condition remain separate.',ha='center',fontsize=8)
    fig.tight_layout(rect=[0,.06,1,.89])
    if SAVE_PLOTS: fig.savefig(os.path.join(OUTPUT_DIR,'PLOT3_EXECUTIVE_SINGLE_PANE.png'),dpi=160,bbox_inches='tight')
    if SHOW_PLOTS: plt.show()
    plt.close(fig)

def build_decision_frames(results, events, executive=None, audit=None):
    """Build the compact decision tables in memory without exporting or refitting.

    This is the only adapter consumed by the Streamlit UI.  It reuses the already
    materialized canonical traces/results and never calls model fitting functions.
    """
    if executive is None:
        executive = executive_asof_data(results)
    ex_metrics, trends = executive
    executive_df = pd.DataFrame(ex_metrics)

    parameter_rows, forecast_rows, validation_rows, lineage_rows = [], [], [], []
    for r in results:
        tag = r['tag_number']
        a = r['asset']
        for p, v in r['projection']['parameters'].items():
            parameter_rows.append(dict(
                Asset=tag, Parameter=p, As_Of=AS_OF,
                Value=v['value'], Lower=v['lower'], Upper=v['upper'], Unit=v['limit']['unit'],
                State=v['state'], Source=v['source'], Quality=v['quality'],
                Model=v['model']['model'], Model_Type=v['model_type'],
                MAE=v['mae'], RMSE=v['rmse'], Skill=v['skill'],
                Last_Actual=v.get('last_actual'), Last_Weekly=v['last_lab'],
                Data_Age_h=v.get('data_age_h', v['age_h']),
                Alarm_Limit=v['limit']['alarm'], Trip_Limit=v['limit']['trip'],
                Direction=v['limit']['direction'],
            ))

            tr = v['trace']
            for label, h in [('H+24', 24), ('H+72', 72), ('H+168', 168)]:
                t = AS_OF + pd.Timedelta(hours=h)
                if t in tr.index:
                    z = tr.loc[t]
                    forecast_rows.append(dict(
                        Asset=tag, Parameter=p, Horizon=label, Target_Time=t,
                        Estimate=float(z.Estimate), Lower=float(z.Lower), Upper=float(z.Upper),
                        State=directional_engineering_state(float(z.Estimate), v['limit']),
                        Source=z.Source, Quality=z.Quality, Model=z.Model,
                    ))

            records = pd.DataFrame(v['model'].get('records', []))
            horizons = PF_WEEKLY_HORIZONS_H if v.get('actual', pd.Series(dtype=float)).empty else PF_HORIZONS_H
            deployed_name = v['model']['model']
            for H in horizons:
                if records.empty:
                    gm = pd.DataFrame(); gp = pd.DataFrame()
                else:
                    if 'Relevant_Horizon_H' in records.columns:
                        hmask = pd.to_numeric(records['Relevant_Horizon_H'], errors='coerce').eq(float(H))
                    else:
                        hh = pd.to_numeric(records.get('Horizon_H'), errors='coerce')
                        hmask = (hh - float(H)).abs().le(max(1.0, .40 * float(H)))
                    gm = records.loc[hmask & records['Model'].astype(str).eq(str(deployed_name))]
                    if deployed_name == 'State-Space Fusion' and 'Config' in records.columns and v['model'].get('config_index') is not None:
                        gm = gm.loc[gm['Config'].astype(str).eq(str(v['model']['config_index']))]
                    gp = records.loc[hmask & records['Model'].astype(str).eq('Persistence')]

                def _metrics(g):
                    if g.empty:
                        return np.nan, np.nan, 0
                    e = pd.to_numeric(g['Error'], errors='coerce').dropna().to_numpy(float)
                    if not len(e):
                        return np.nan, np.nan, 0
                    return float(np.mean(np.abs(e))), float(np.sqrt(np.mean(e ** 2))), int(len(e))

                cmae, crmse, cn = _metrics(gm)
                pmae, prmse, pn = _metrics(gp)
                skill = (1 - cmae / pmae) if np.isfinite(cmae) and np.isfinite(pmae) and pmae > 1e-12 else np.nan
                beats = (deployed_name != 'Persistence' and np.isfinite(cmae) and np.isfinite(pmae)
                         and cmae < pmae * PF_IMPROVEMENT_THRESHOLD)
                hlabel = f'Week+{int(H/168)}' if v.get('actual', pd.Series(dtype=float)).empty else f'H+{int(H)}'
                validation_rows.append(dict(
                    Asset=tag, Parameter=p, Relevant_Horizon=hlabel, Horizon_H=float(H),
                    Deployed_Model=deployed_name,
                    Persistence_MAE=pmae, Persistence_RMSE=prmse,
                    Model_MAE=cmae, Model_RMSE=crmse, Skill=skill,
                    Validation_N=cn, Beats_Persistence_at_Horizon=beats,
                    Overall_Deployment_Decision=('DEPLOY_MODEL' if v.get('beats_persistence') else 'PERSISTENCE/FALLBACK'),
                    Validation_Method=v['validation_method'],
                    Validation_Target_Basis=(
                        'RELEASED_WEEKLY_ENGINEERING_LABEL' if str(v.get('model_type','')).upper().startswith('INDIRECT')
                        else ('OBSERVED_WEEKLY_ENGINEERING' if v.get('actual', pd.Series(dtype=float)).empty else 'OBSERVED_DIRECT_SERIES')
                    ),
                    Validation_Target_Is_Model_Output=False,
                ))

            lineage_rows.append(dict(
                Asset=tag, Source='Engineering Parameter', Parameter=p,
                Last_Actual=v.get('last_actual'), Last_Weekly=v['last_lab'],
                Data_Age_h=v.get('data_age_h', v['age_h']), Channel_Mapping=v.get('suffix'),
                Unit=v['limit']['unit'], Quality=v['quality'], Physics_Candidate=v['physics_candidate'],
            ))

    weekly_native = pf_native_weekly_export(results)
    if not weekly_native.empty:
        future_week = weekly_native.loc[weekly_native['Weekly_Basis'].eq('FORECAST_TARGET')].copy()
        future_week['Week_Index'] = future_week.groupby(['Asset', 'Parameter']).cumcount() + 1
        for _, z in future_week.loc[future_week.Week_Index.le(4)].iterrows():
            forecast_rows.append(dict(
                Asset=z.Asset, Parameter=z.Parameter, Horizon=f'Week+{int(z.Week_Index)}',
                Target_Time=z.Forecast_Target_Date, Estimate=float(z.Estimate),
                Lower=float(z.Lower), Upper=float(z.Upper), State='',
                Source=z.Source, Quality=z.Quality, Model=z.Model,
            ))

    problem_rows, rca_rows = [], []
    for r in results:
        ticket = r.get('ticket', {})
        evidence = r.get('rca_evidence', {})
        trigger = trigger_short_text(r.get('triggers', []))
        rca_ind = evidence.get('leading_hypothesis') or evidence.get('root_cause') or (evidence.get('priority_causes', [None])[0] if evidence.get('priority_causes') else '')
        problem_rows.append(dict(
            Problem_ID=ticket.get('ticket_id') or f"MONITOR-{r['tag_number']}",
            Asset=r['tag_number'], Trigger=trigger, Severity=r['projection']['state'],
            Priority=r['priority'], Asset_Criticality=ASSET_CRITICALITY.get(r['tag_number'], 'MEDIUM'),
            Asset_Criticality_Basis='BUSINESS_RULE_ASSUMPTION_REVIEW_WITH_PLANT_OWNER',
            RCA_Indication=((evidence.get('hypothesis_label') or rca_hypothesis_label(evidence.get('evidence_strength'))) + ': ' + str(rca_ind)) if rca_ind else 'No active RCA hypothesis',
            Evidence_Score=evidence.get('evidence_strength', 'NOT_TRIGGERED'),
            Matched_Incident=evidence.get('matched_ar'),
            Case_Similarity=(evidence.get('candidates', [{}])[0].get('Case Similarity') if evidence.get('candidates') else np.nan),
            Current_Evidence=structured_list_to_text(evidence.get('current_measured_evidence', []), preferred_keys=('Evidence','Parameter','type')),
            Historical_Evidence=structured_list_to_text(evidence.get('historical_verified_evidence', []), preferred_keys=('Evidence','Factor','Finding','Description')),
            Recommended_Action=action_list_to_text(ticket.get('actions', [])),
            Owner=ticket.get('owner') or suggested_owner_role(r['asset']),
            SLA=priority_sla(r['priority']), Ticket_State=ticket.get('ticket_state', ticket.get('status', 'MONITOR')),
            Action_Status=ticket.get('action_status', 'NOT_STARTED'), Status=ticket.get('ticket_state', ticket.get('status', 'MONITOR')),
        ))
        for c in evidence.get('candidates', [])[:TOP_K_RCA_DISPLAY]:
            rca_rows.append(dict(
                Asset=r['tag_number'], Matched_Incident=c.get('AR No'),
                Case_Similarity=c.get('Case Similarity'),
                Current_Evidence=structured_list_to_text(evidence.get('current_measured_evidence', []), preferred_keys=('Evidence','Parameter','type')),
                Historical_Evidence=structured_list_to_text(evidence.get('historical_verified_evidence', []), preferred_keys=('Evidence','Factor','Finding','Description')),
                Four_P=structured_list_to_text(evidence.get('verification_4p', []), preferred_keys=('Factor','Verification','Evidence','Description')),
                Four_M=structured_list_to_text(evidence.get('verification_4m', []), preferred_keys=('Factor','Verification','Evidence','Description')),
                CAPA=structured_list_to_text(evidence.get('capa', []), preferred_keys=('Action','CAPA','Plan','Recommendation')),
                Evidence_Strength=evidence.get('evidence_strength'),
            ))

    parameter_df = pd.DataFrame(parameter_rows)
    forecast_df = pd.DataFrame(forecast_rows)
    validation_df = pd.DataFrame(validation_rows)
    lineage_df = pd.DataFrame(lineage_rows)
    problem_df = pd.DataFrame(problem_rows)
    rca_df = pd.DataFrame(rca_rows)

    if problem_df.empty:
        executive_snapshot = executive_df.copy()
    else:
        executive_snapshot = executive_df.merge(
            problem_df[['Asset', 'Priority', 'RCA_Indication', 'Recommended_Action', 'Owner', 'SLA', 'Ticket_State', 'Action_Status', 'Status']],
            on='Asset', how='left'
        )

    audit_df = pd.DataFrame() if audit is None else audit.copy()
    case2_kpis_df = case2_executive_domain_kpis(results, executive_df)
    case2_coverage_df = case2_requirement_coverage(executive_df, case2_kpis_df)
    energy_proxy_forecast_df = case2_energy_proxy_forecast(results, executive_df)
    return {
        'executive': executive_snapshot,
        'case2_kpis': case2_kpis_df,
        'case2_coverage': case2_coverage_df,
        'energy_proxy_forecast': energy_proxy_forecast_df,
        'executive_trends': trends,
        'problem_tank': problem_df,
        'rca': rca_df,
        'parameter_asof': parameter_df,
        'forecast': forecast_df,
        'validation': validation_df,
        'lineage': lineage_df,
        'action_history': load_action_history(),
        'data_quality': audit_df,
        'weekly_native': weekly_native,
    }


def run_intelligence_engine(file_path=None, export_artifacts=False, generate_audit_plots=False,
                            run_historical_replay=False, verbose=False):
    """Run the V11.3 indirect-canonical intelligence engine once and return structured in-memory results.

    Streamlit should cache this function. UI interactions only filter/render its return
    value; they must not rerun forecasting, RCA, validation, export, or Matplotlib plots.
    """
    global FILE_PATH, VERBOSE_CONSOLE, RUN_HISTORICAL_REPLAY
    if file_path:
        FILE_PATH = str(file_path)
    VERBOSE_CONSOLE = bool(verbose)
    RUN_HISTORICAL_REPLAY = bool(run_historical_replay)

    PHASE_TIMINGS.clear()
    ensure_output_dir()
    if not os.path.exists(FILE_PATH):
        raise FileNotFoundError('Set IM_WORKBOOK / file_path ke lokasi workbook All_Case_Data.xlsx.')

    total_start = perf_counter()
    t = perf_counter()
    workbook = pd.ExcelFile(FILE_PATH)
    workbook_data = pd.read_excel(workbook, sheet_name=None)
    runtime_context = refresh_runtime_context(workbook_data)
    # A fresh engine run may follow an edited workbook; analytical caches must never
    # survive across a changed AS_OF/source workbook. Streamlit provides the outer cache.
    pf_reset_cache(force=True)
    tables = load_global_tables(workbook_data)
    tables['operator_inputs'] = load_operator_inputs()
    tables['ticket_history'] = load_problem_tank_history()
    tables['runtime_mode'] = {'mode': 'SNAPSHOT', 'reference_time': AS_OF}
    _time_phase('Data loading', t)

    t = perf_counter()
    audit = audit_workbook(workbook_data)
    bad = set(audit.loc[audit.Status.eq('FAIL'), 'Asset'].astype(str))
    _time_phase('Data audit', t)

    t = perf_counter()
    assets = [asof_trim_asset(load_asset_data(workbook_data, c)) for c in ASSET_CONFIGS if c['tag_number'] not in bad]
    _time_phase('Asset ingestion', t)
    if len(assets) != 5:
        raise ValueError('All five assets must pass the input audit before the complete dashboard can be generated.')

    t = perf_counter()
    results = [run_asset_pipeline(a, tables) for a in assets]
    # Persist the current ticket register independently from the source workbook.
    # Updating Excel must not reset workflow state.
    save_problem_tank_history(tables.get('ticket_history', load_problem_tank_history()))
    _time_phase('Condition + RCA context', t)

    t = perf_counter(); [pf_channels(a) for a in assets]; _time_phase('DCS model + trace', t)
    t = perf_counter(); pf_snapshot(results); _time_phase('Engineering fusion/model', t)
    t = perf_counter(); validate_prediction_completeness(results); pf_refresh_results_from_canonical(results, tables); _time_phase('Validation + canonical gate', t)
    t = perf_counter(); events = [pf_rca(e, results, tables) for e in pf_events(results)]; _time_phase('RCA canonical events', t)
    t = perf_counter(); executive = executive_asof_data(results); _time_phase('Executive KPI', t)

    frames = build_decision_frames(results, events, executive, audit)

    replay = pd.DataFrame()
    if run_historical_replay:
        import contextlib, io
        t = perf_counter()
        with contextlib.redirect_stdout(io.StringIO()):
            replay = historical_replay_validation(assets, tables)
        _time_phase('Historical replay audit', t)

    if export_artifacts:
        t = perf_counter(); pf_export(results, events, executive); _time_phase('Export CSV/XLSX', t)
    if generate_audit_plots:
        t = perf_counter(); plot_all_assets_hourly(results); plot_all_assets_weekly(results); generate_executive_dashboard(results, executive); _time_phase('Plot', t)

    PHASE_TIMINGS['Total wall-clock'] = perf_counter() - total_start
    return {
        'results': results,
        'events': events,
        'assets': assets,
        'tables': tables,
        'audit': audit,
        'replay': replay,
        'phase_timings': dict(PHASE_TIMINGS),
        'analysis_time': AS_OF,
        'runtime_context': runtime_context,
        **frames,
    }


def main():
    PHASE_TIMINGS.clear();pf_reset_cache(force=False);ensure_output_dir()
    if not os.path.exists(FILE_PATH): raise FileNotFoundError('Set IM_WORKBOOK ke lokasi workbook Anda.')
    total_start=perf_counter()
    t=perf_counter();workbook=pd.ExcelFile(FILE_PATH);workbook_data=pd.read_excel(workbook,sheet_name=None);refresh_runtime_context(workbook_data);pf_reset_cache(force=True);tables=load_global_tables(workbook_data);tables['operator_inputs']=load_operator_inputs();tables['ticket_history']=load_problem_tank_history();tables['runtime_mode']={'mode':'SNAPSHOT','reference_time':AS_OF};_time_phase('Data loading',t)
    t=perf_counter();audit=audit_workbook(workbook_data);bad=set(audit.loc[audit.Status.eq('FAIL'),'Asset'].astype(str));_time_phase('Data audit',t)
    t=perf_counter();assets=[asof_trim_asset(load_asset_data(workbook_data,c)) for c in ASSET_CONFIGS if c['tag_number'] not in bad];_time_phase('Asset ingestion',t)
    if len(assets)!=5: raise ValueError('All five assets must pass the input audit before the complete dashboard can be generated.')
    t=perf_counter();results=[run_asset_pipeline(a,tables) for a in assets];save_problem_tank_history(tables.get('ticket_history',load_problem_tank_history()));_time_phase('Condition + RCA context',t)
    t=perf_counter();[pf_channels(a) for a in assets];_time_phase('DCS model + trace',t)
    t=perf_counter();pf_snapshot(results);_time_phase('Engineering fusion/model',t)
    t=perf_counter();validate_prediction_completeness(results);pf_refresh_results_from_canonical(results,tables);_time_phase('Validation + canonical gate',t)
    t=perf_counter();events=[pf_rca(e,results,tables) for e in pf_events(results)];_time_phase('RCA canonical events',t)
    t=perf_counter();executive=executive_asof_data(results);_time_phase('Executive KPI',t)
    pf_print(results,events,audit)
    t=perf_counter();pf_export(results,events,executive);_time_phase('Export CSV/XLSX',t)
    if RUN_HISTORICAL_REPLAY:
        import contextlib,io
        t=perf_counter()
        with contextlib.redirect_stdout(io.StringIO()): replay=historical_replay_validation(assets,tables)
        _time_phase('Historical replay audit',t);print(f'\nHistorical replay: {len(replay)} incidents; CSV exported.')
    t=perf_counter();print('\nGenerating plots: 5 hourly + 5 weekly + 1 executive...');plot_all_assets_hourly(results);plot_all_assets_weekly(results);generate_executive_dashboard(results,executive);_time_phase('Plot',t)
    PHASE_TIMINGS['Total wall-clock']=perf_counter()-total_start;print_phase_timings();print('Complete: 11 plots | compact export mode: '+str(not AUDIT_MODE)+' | predictions through '+PF_END.strftime('%Y-%m-%d %H:%M')+' | output: '+OUTPUT_DIR)



if __name__=='__main__':
    main()
