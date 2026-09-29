# -*- coding: utf-8 -*-
"""Human-friendly Streamlit interface for the Intelligent Manufacturing engine.

Run with:
    python -m streamlit run app.py

The analytical logic remains in ``intelligence_engine.py``. This file only loads,
explains, filters, and visualizes the engine outputs.
"""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from intelligence_engine import run_intelligence_engine, save_operator_update

st.set_page_config(
    page_title="Intelligent Manufacturing Dashboard",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# Visual system
# -----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    :root {
        --navy:#0F2747; --blue:#1F5A94; --cyan:#2F80C9; --ink:#172033;
        --muted:#687386; --line:#E5EAF0; --soft:#F5F8FC; --card:#FFFFFF;
    }
    .block-container {padding-top:1.1rem; padding-bottom:2.5rem; max-width:1720px;}
    [data-testid="stSidebar"] {background:#F7F9FC; border-right:1px solid #E5EAF0;}
    .hero {
        padding:1.2rem 1.35rem; border-radius:16px; color:white;
        background:linear-gradient(120deg,#0F2747 0%,#1F5A94 55%,#2F80C9 100%);
        box-shadow:0 8px 24px rgba(15,39,71,.16); margin-bottom:1rem;
    }
    .hero h1 {font-size:1.85rem; margin:0 0 .25rem 0; letter-spacing:.01em;}
    .hero p {margin:.15rem 0; opacity:.92; font-size:.93rem;}
    .section-title {font-size:1.08rem; font-weight:750; color:#172033; margin:.5rem 0 .15rem 0;}
    .section-desc {font-size:.86rem; color:#687386; margin-bottom:.65rem;}
    .info-strip {background:#F5F8FC; border:1px solid #E5EAF0; border-left:4px solid #2F80C9;
        padding:.7rem .9rem; border-radius:10px; margin:.5rem 0 .85rem 0; font-size:.88rem; color:#374151;}
    .mini-card {background:white; border:1px solid #E5EAF0; border-radius:12px; padding:.75rem .9rem; min-height:84px;}
    .mini-label {font-size:.76rem; color:#687386; text-transform:uppercase; letter-spacing:.04em;}
    .mini-value {font-size:1.1rem; font-weight:750; color:#172033; margin-top:.2rem;}
    div[data-testid="stMetric"] {background:white; border:1px solid #E5EAF0; padding:12px 14px; border-radius:12px; box-shadow:0 2px 8px rgba(15,39,71,.05);}
    div[data-testid="stMetricLabel"] {font-weight:650;}
    .badge {display:inline-block; color:white; padding:3px 9px; border-radius:999px; font-size:.76rem; font-weight:750;}
    .definition {font-size:.82rem; color:#687386; line-height:1.45;}
    .stTabs [data-baseweb="tab-list"] {gap:.3rem;}
    .stTabs [data-baseweb="tab"] {border-radius:8px 8px 0 0; padding:.45rem .8rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

STATE_COLORS = {
    "NORMAL": "#2E7D32", "WATCH": "#C98A00", "ALARM": "#E46B20", "TRIP": "#B42318",
    "DATA_GAP": "#667085", "NOT_OBSERVABLE": "#667085",
}
PRIORITY_COLORS = {"P1": "#B42318", "P2": "#E46B20", "P3": "#C98A00", "P4": "#2E7D32"}

STATE_EXPLANATIONS = {
    "NORMAL": "Normal — current evidence is within the configured decision limits.",
    "WATCH": "Watch — an early deviation is present and should be reviewed.",
    "ALARM": "Alarm — an alarm-level threshold or persistent abnormal condition is active.",
    "TRIP": "Trip — a trip-level threshold is reached or exceeded.",
    "DATA_GAP": "Data gap — the current condition cannot be assessed reliably because required data are unavailable.",
    "NOT_OBSERVABLE": "Not observable — the available measurements do not directly observe this condition.",
}
PRIORITY_EXPLANATIONS = {
    "P1": "Priority 1 — immediate or urgent intervention.",
    "P2": "Priority 2 — high-priority planned intervention.",
    "P3": "Priority 3 — scheduled follow-up.",
    "P4": "Priority 4 — routine monitoring.",
}
QUALITY_EXPLANATIONS = {
    "BACKTESTED": "Backtested — the model has historical validation over a comparable horizon.",
    "BACKTESTED_FORECAST": "Backtested forecast — forecast horizon is covered by historical validation.",
    "EXTRAPOLATED": "Extrapolated — the estimate extends beyond the strongest validated range.",
    "PROVISIONAL": "Provisional — too few validation points are available for a strong conclusion.",
    "PROVISIONAL_FORECAST": "Provisional forecast — the future estimate has limited validation support.",
    "BEYOND_VALIDATED_HORIZON": "Beyond validated horizon — the forecast is farther ahead than the validated horizon.",
}


def fmt_num(value, digits=1, suffix=""):
    try:
        x = float(value)
        return "—" if not np.isfinite(x) else f"{x:.{digits}f}{suffix}"
    except Exception:
        return "—"


def fmt_time(value):
    x = pd.to_datetime(value, errors="coerce")
    return "—" if pd.isna(x) else x.strftime("%d %b %Y, %H:%M")


def clean_text(value):
    """Remove escaped line-break artifacts and make serialized content readable."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"
    if isinstance(value, (list, tuple, dict)):
        return structured_text(value)
    text = str(value)
    text = text.replace("\\r\\n", " ").replace("\\n", " ").replace("\r", " ").replace("\n", " ")
    text = text.replace("\\/", "/").replace("\\\"", '"')
    text = re.sub(r"\s+", " ", text).strip()
    return text or "—"


def structured_text(value):
    if value is None:
        return "—"
    if isinstance(value, str):
        raw = value.strip()
        if raw.startswith(("[", "{")):
            try:
                value = ast.literal_eval(raw)
            except Exception:
                return clean_text(raw)
        else:
            return clean_text(raw)
    if isinstance(value, dict):
        preferred = ["Plan", "Type", "Source", "RC", "Factor", "Evidence", "Description"]
        pieces = []
        for key in preferred:
            if key in value and value[key] not in (None, "", [], {}):
                pieces.append(f"{key}: {clean_text(value[key])}")
        if not pieces:
            pieces = [f"{k}: {clean_text(v)}" for k, v in value.items() if v not in (None, "", [], {})]
        return " · ".join(pieces) if pieces else "—"
    if isinstance(value, (list, tuple)):
        return " • ".join(structured_text(item) for item in value if item not in (None, "", [], {})) or "—"
    return clean_text(value)


def badge(text, kind="state"):
    raw = clean_text(text)
    palette = STATE_COLORS if kind == "state" else PRIORITY_COLORS
    color = palette.get(raw.upper(), "#667085")
    shown = raw if kind == "priority" else readable_label(raw)
    return f'<span class="badge" style="background:{color};">{shown}</span>'


def status_rank(series):
    vals = [str(v).upper() for v in series if pd.notna(v)]
    if "FAIL" in vals:
        return "FAIL"
    if "CHECK" in vals:
        return "CHECK"
    return "PASS" if vals else "CHECK"


def resolve_default_workbook():
    env = os.environ.get("IM_WORKBOOK")
    candidates = [env] if env else []
    here = Path(__file__).resolve().parent
    candidates += [
        here / "All_Case_Data.xlsx", here / "All_Raw_Data.xlsx",
        Path.cwd() / "All_Case_Data.xlsx", Path.cwd() / "All_Raw_Data.xlsx",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate).resolve())
    return ""


@st.cache_resource(show_spinner="Loading data and running the analytical engine…")
def load_engine(workbook_path: str, workbook_modified_ns: int):
    """Run the analytical engine only when the workbook version changes.

    Streamlit reruns the app script after normal UI interactions such as changing
    the selected asset, tab, parameter, or filter. Those interactions must reuse
    the cached analytical result rather than rerunning the full engine.

    Workflow updates are handled explicitly in the Save follow-up action: the
    workflow file is written, this cache is cleared, and Streamlit reruns once.
    Therefore workflow-file modification time must not be part of this cache key.
    """
    _ = workbook_modified_ns
    return run_intelligence_engine(
        file_path=workbook_path,
        export_artifacts=False,
        generate_audit_plots=False,
        run_historical_replay=False,
        verbose=False,
    )


def get_result(data, asset):
    for result in data.get("results", []):
        if result.get("tag_number") == asset:
            return result
    return None


def aggregate_cards(executive):
    if executive.empty:
        return {}

    def avg(col):
        x = pd.to_numeric(executive.get(col), errors="coerce")
        return float(x.mean()) if x.notna().any() else np.nan

    downtime = pd.to_numeric(executive.get("Downtime_30d_h"), errors="coerce")
    coverage = pd.to_numeric(executive.get("Observed_Coverage_30d_h"), errors="coerce")
    return {
        "health": avg("Asset_Health_Score"),
        "operating": avg("Operating_Performance_Index"),
        "load": avg("Load_Proxy_Index"),
        "downtime": float(downtime.sum(min_count=1)) if downtime.notna().any() else np.nan,
        "coverage": float(coverage.sum(min_count=1)) if coverage.notna().any() else 0.0,
        "reliability": avg("Reliability_Consequence_Index"),
    }


def parameter_figure(parameter_data, title, analysis_time):
    trace = parameter_data["trace"].copy()
    analysis_time = pd.Timestamp(analysis_time)
    trace = trace.loc[trace.index >= analysis_time - pd.Timedelta(days=30)]
    if trace.empty:
        return go.Figure()

    source = trace["Source"].astype(str).str.upper()
    actual_mask = source.eq("ACTUAL")
    reconstruction_mask = source.str.contains("RECON|INTERPOL|SMOOTH|CAUSAL", regex=True)
    forecast_mask = source.str.contains("FORECAST|ASOF_ESTIMATE|FORWARD_GAP", regex=True)
    reconstruction_mask = reconstruction_mask | ~(actual_mask | reconstruction_mask | forecast_mask)

    fig = go.Figure()
    band_mask = ~actual_mask
    fig.add_trace(go.Scatter(
        x=trace.index, y=trace["Upper"].where(band_mask), mode="lines",
        line=dict(width=0), hoverinfo="skip", showlegend=False, name="Upper uncertainty bound",
    ))
    fig.add_trace(go.Scatter(
        x=trace.index, y=trace["Lower"].where(band_mask), mode="lines",
        line=dict(width=0), fill="tonexty", fillcolor="rgba(47,128,201,0.12)",
        hoverinfo="skip", name="Model uncertainty range",
    ))

    for mask, name, dash in [
        (actual_mask, "Measured value", "solid"),
        (reconstruction_mask, "Reconstructed or causal estimate", "dot"),
        (forecast_mask, "Forward estimate or forecast", "dash"),
    ]:
        y = trace["Estimate"].where(mask)
        if y.notna().any():
            fig.add_trace(go.Scatter(x=trace.index, y=y, mode="lines", name=name, line=dict(dash=dash, width=2.2)))

    weekly = parameter_data.get("weekly")
    if isinstance(weekly, pd.DataFrame) and not weekly.empty and parameter_data["parameter"] in weekly.columns:
        weekly = weekly.copy()
        weekly["Date"] = pd.to_datetime(weekly["Date"], errors="coerce")
        weekly = weekly.loc[weekly["Date"] >= trace.index.min()]
        if not weekly.empty:
            fig.add_trace(go.Scatter(
                x=weekly["Date"], y=weekly[parameter_data["parameter"]], mode="markers",
                name="Measured weekly engineering value", marker=dict(size=8, symbol="circle-open"),
            ))

    limit = parameter_data["limit"]
    fig.add_hline(y=limit["alarm"], line_dash="dot", annotation_text="Alarm limit")
    fig.add_hline(y=limit["trip"], line_dash="dash", annotation_text="Trip limit")
    fig.add_vline(x=analysis_time.timestamp() * 1000, line_dash="dot", annotation_text="Analysis reference time")
    fig.update_layout(
        title=title, height=440, margin=dict(l=20, r=20, t=65, b=20),
        xaxis_title="Time", yaxis_title=limit.get("unit", ""), hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#EEF2F6")
    return fig


def humanize_quality(value):
    raw = str(value or "—").upper()
    return QUALITY_EXPLANATIONS.get(raw, clean_text(value))


def readable_label(value):
    """Convert internal codes into normal reader-facing labels without changing engine keys."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"
    raw = str(value).strip()
    if not raw:
        return "—"
    special = {
        "P1": "P1", "P2": "P2", "P3": "P3", "P4": "P4",
        "RCA": "RCA", "DCS": "DCS", "MAE": "MAE", "RMSE": "RMSE",
        "ASOF": "As-of", "TFIDF": "TF-IDF",
    }
    words = re.split(r"[_\s]+", raw)
    pretty = []
    for word in words:
        key = word.upper()
        if key in special:
            pretty.append(special[key])
        elif key in {"NORMAL", "WATCH", "ALARM", "TRIP", "OPEN", "CLOSED", "ACKNOWLEDGED"}:
            pretty.append(key.title())
        else:
            pretty.append(word.lower() if word.isupper() else word)
    text = " ".join(pretty)
    return text[:1].upper() + text[1:] if text else "—"


def readable_headers(frame):
    """Use natural table headers in the app while leaving engine DataFrames untouched."""
    acronyms = {"RCA", "SLA", "MAE", "RMSE", "DCS", "PIC", "ID"}
    mapping = {}
    for col in frame.columns:
        words = str(col).replace("_", " ").split()
        mapping[col] = " ".join(w.upper() if w.upper() in acronyms else w.capitalize() for w in words)
    return frame.rename(columns=mapping)


def source_family(value):
    """Human-readable provenance family for decision use."""
    raw = str(value or "").upper()
    if "FORECAST" in raw or "FORWARD" in raw:
        return "Forecast"
    if "INDIRECT" in raw or "SOFT" in raw or "VIRTUAL" in raw:
        return "Indirect estimate"
    if "RECON" in raw or "INTERPOL" in raw or "SMOOTH" in raw or "CAUSAL" in raw or "ASOF_ESTIMATE" in raw or "BASELINE_PRIOR" in raw:
        return "Reconstructed / model estimate"
    if "WEEKLY" in raw:
        return "Weekly engineering observation"
    if "ACTUAL" in raw or "MEASURED" in raw or "DCS" in raw:
        return "Workbook observation"
    return clean_text(value)


def friendly_table(frame, rename=None, text_columns=None):
    out = frame.copy()
    if text_columns:
        for col in text_columns:
            if col in out.columns:
                out[col] = out[col].map(clean_text)
    if rename:
        out = out.rename(columns=rename)
    return out


# -----------------------------------------------------------------------------
# Sidebar and engine loading
# -----------------------------------------------------------------------------
default_workbook = resolve_default_workbook()
st.sidebar.markdown("## Dashboard controls")
st.sidebar.caption("Choose the source workbook and narrow the dashboard to the information you need.")
workbook_path = st.sidebar.text_input(
    "Source workbook",
    value=default_workbook,
    help="Excel workbook containing the five asset datasets, equipment limits, incident history, and root-cause tables.",
)
if not workbook_path or not Path(workbook_path).exists():
    st.error("The source workbook was not found. Place All_Case_Data.xlsx in the project folder or provide its full path in the sidebar.")
    st.stop()

resolved_workbook = str(Path(workbook_path).resolve())
modified_ns = Path(resolved_workbook).stat().st_mtime_ns
if st.sidebar.button("Reload workbook and analysis", help="Use this after editing the Excel workbook or changing engine configuration."):
    load_engine.clear()
    st.rerun()

try:
    data = load_engine(resolved_workbook, modified_ns)
except Exception as exc:
    st.error("The analytical engine could not complete the dashboard calculation.")
    st.exception(exc)
    st.stop()

executive = data.get("executive", pd.DataFrame()).copy()
problems = data.get("problem_tank", pd.DataFrame()).copy()
rca = data.get("rca", pd.DataFrame()).copy()
parameter_asof = data.get("parameter_asof", pd.DataFrame()).copy()
forecast = data.get("forecast", pd.DataFrame()).copy()
validation = data.get("validation", pd.DataFrame()).copy()
lineage = data.get("lineage", pd.DataFrame()).copy()
action_history = data.get("action_history", pd.DataFrame()).copy()
audit = data.get("data_quality", pd.DataFrame()).copy()
trends = data.get("executive_trends", {})
assets = sorted(executive.get("Asset", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())

if st.session_state.pop("followup_saved", False):
    st.success("Follow-up update saved and the workflow state has been refreshed.")

last_actual_values = pd.to_datetime(executive.get("Last_Actual"), errors="coerce") if "Last_Actual" in executive else pd.Series(dtype="datetime64[ns]")
analysis_time = pd.Timestamp(data.get("analysis_time"))
if pd.isna(analysis_time):
    # Fallback only for malformed/legacy engine output; the revised engine always returns analysis_time.
    analysis_time = pd.to_datetime(last_actual_values, errors="coerce").min() if not last_actual_values.empty else pd.NaT
if pd.isna(analysis_time):
    st.error("The engine did not provide a valid analysis reference time.")
    st.stop()

asset_filter = st.sidebar.selectbox(
    "Asset scope", ["All assets"] + assets,
    help="Select one asset for focused metrics, or keep all assets for plant-wide monitoring.",
)
priority_filter = st.sidebar.selectbox(
    "Action priority", ["All priorities", "P1", "P2", "P3", "P4"],
    help="P1 is the most urgent action level; P4 is routine monitoring.",
)
ticket_state_col = "Ticket_State" if "Ticket_State" in problems.columns else "Status"
status_values = sorted(problems[ticket_state_col].dropna().astype(str).unique().tolist()) if ticket_state_col in problems else []
status_choices = ["All statuses"] + status_values
status_filter = st.sidebar.selectbox(
    "Ticket state", status_choices,
    format_func=lambda x: x if x == "All statuses" else readable_label(x),
)
problem_only = st.sidebar.checkbox("Show only items requiring attention", value=False)
show_forecast = st.sidebar.checkbox("Show forecast tables", value=True)

with st.sidebar.expander("Terminology used in this dashboard"):
    st.markdown(
        """
        **Root Cause Analysis (RCA):** structured investigation of plausible failure mechanisms.  
        **Corrective and Preventive Action (CAPA):** actions used to correct a problem and reduce recurrence.  
        **Distributed Control System (DCS):** plant control system providing hourly process measurements.  
        **Analysis reference time:** latest common timestamp used by the engine for the current snapshot.  
        **Forecast horizon:** how far ahead a prediction is made, for example 24, 72, or 168 hours.  
        **Equipment condition:** analytical state derived from data and models (Normal, Watch, Alarm, Trip).  
        **Ticket state:** engine-controlled lifecycle of the problem ticket.  
        **Action status:** operator-managed progress of the follow-up action.
        """
    )

# -----------------------------------------------------------------------------
# Header
# -----------------------------------------------------------------------------
quality = status_rank(audit["Status"] if "Status" in audit else [])
st.markdown(
    f"""
    <div class="hero">
      <h1>Intelligent Manufacturing Decision Dashboard</h1>
      <p>Plant-wide condition monitoring, forecast-based maintenance support, and root-cause decision assistance.</p>
      <p><b>Analysis reference time:</b> {analysis_time:%d %b %Y, %H:%M} &nbsp;·&nbsp; <b>Operating mode:</b> Historical snapshot &nbsp;·&nbsp; <b>Data-quality gate:</b> {quality}</p>
    </div>
    """,
    unsafe_allow_html=True,
)

exec_scope = executive if asset_filter == "All assets" else executive.loc[executive.Asset.eq(asset_filter)]
problem_scope = problems.copy()
if asset_filter != "All assets" and "Asset" in problem_scope:
    problem_scope = problem_scope.loc[problem_scope.Asset.eq(asset_filter)]
if priority_filter != "All priorities" and "Priority" in problem_scope:
    problem_scope = problem_scope.loc[problem_scope.Priority.eq(priority_filter)]
if status_filter != "All statuses" and ticket_state_col in problem_scope:
    problem_scope = problem_scope.loc[problem_scope[ticket_state_col].eq(status_filter)]
if problem_only and "Priority" in problem_scope:
    problem_scope = problem_scope.loc[~problem_scope.Priority.eq("P4")]

# -----------------------------------------------------------------------------
# Tabs
# -----------------------------------------------------------------------------
tab_exec, tab_problem, tab_asset, tab_forecast, tab_quality = st.tabs([
    "Executive overview",
    "Active problems",
    "Asset details",
    "Forecast and root-cause analysis",
    "Data and model quality",
])

with tab_exec:
    st.markdown('<div class="section-title">Plant-wide decision indicators</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-desc">These indicators summarize current condition, operating behavior, historical downtime, and reliability consequence. They are decision indices, not direct probabilities of failure.</div>', unsafe_allow_html=True)
    cards = aggregate_cards(exec_scope)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Asset health score", fmt_num(cards.get("health"), 1, " / 100"), help="Composite condition score. Higher values represent healthier current condition.")
    c2.metric("Operating performance index", fmt_num(cards.get("operating"), 1, " / 100"), help="Normalized operating-performance indicator relative to the asset's own healthy baseline.")
    c3.metric("Load proxy index", fmt_num(cards.get("load"), 1), help="Relative operating-load indicator. A baseline around 100 represents the reference load level.")
    c4.metric("Observed downtime in last 30 days", fmt_num(cards.get("downtime"), 1, " h") if cards.get("coverage", 0) > 0 else "—", help="Downtime calculated only from observed running-status data in the 30-day window.")
    c5.metric("Reliability and consequence index", fmt_num(cards.get("reliability"), 1, " / 100"), help="Decision index combining reliability context and historical consequence information.")
    st.caption(f"Observed operating-data coverage in the selected scope: {fmt_num(cards.get('coverage'), 0, ' hours')}.")

    with st.expander("How these indicators are calculated and where they come from"):
        basis_cols = [c for c in [
            "Asset", "Data_Basis", "Health_KPI_Basis", "Operating_KPI_Basis", "Load_Metric_Name",
            "Load_KPI_Basis", "Reliability_KPI_Basis", "Downtime_KPI_Basis", "Last_Actual", "Data_Age_h",
        ] if c in exec_scope.columns]
        basis = friendly_table(exec_scope[basis_cols], rename={
            "Data_Basis": "Primary data basis", "Health_KPI_Basis": "Health-score basis",
            "Operating_KPI_Basis": "Operating-index basis", "Load_Metric_Name": "Load metric",
            "Load_KPI_Basis": "Load-index basis", "Reliability_KPI_Basis": "Reliability-index basis",
            "Downtime_KPI_Basis": "Downtime basis", "Last_Actual": "Latest measured value",
            "Data_Age_h": "Data age (hours)",
        })
        st.dataframe(basis, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Asset condition overview</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-desc">One-row summary per asset showing the current measured condition, forecast risk, and maintenance action priority.</div>', unsafe_allow_html=True)
    overview_cols = ["Asset", "Asset_Health_Score", "Operating_Performance_Index", "Load_Proxy_Index", "Downtime_30d_h", "Observed_Coverage_30d_h", "Measured_Condition", "Forecast_Risk_168h", "Priority"]
    overview = exec_scope[[c for c in overview_cols if c in exec_scope.columns]].copy()
    overview = overview.rename(columns={
        "Asset_Health_Score": "Asset health score", "Operating_Performance_Index": "Operating performance index",
        "Load_Proxy_Index": "Load proxy index", "Downtime_30d_h": "Downtime, last 30 days (hours)",
        "Observed_Coverage_30d_h": "Observed coverage, last 30 days (hours)", "Measured_Condition": "Current measured condition",
        "Forecast_Risk_168h": "Condition forecast up to 168 hours", "Priority": "Action priority",
    })
    st.dataframe(overview, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Thirty-day decision-index trends</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-desc">Trend lines show how the selected decision index has changed over the previous 30 days. Reconstructed values can be present when raw observations are unavailable.</div>', unsafe_allow_html=True)
    trend_assets = assets if asset_filter == "All assets" else [asset_filter]
    metric_choice = st.radio(
        "Select the trend indicator",
        ["Asset Health Score", "Operating Performance Index", "Reliability & Consequence Index"],
        horizontal=True,
    )
    fig = go.Figure()
    for asset in trend_assets:
        if asset not in trends or metric_choice not in trends[asset]:
            continue
        daily = trends[asset][metric_choice].resample("D").mean()
        fig.add_trace(go.Scatter(x=daily.index, y=daily, mode="lines", name=asset, line=dict(width=2)))
    fig.update_layout(height=340, margin=dict(l=20, r=20, t=20, b=20), yaxis_title="Decision index, 0 to 100", hovermode="x unified", legend=dict(orientation="h"), plot_bgcolor="white", paper_bgcolor="white")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#EEF2F6")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-title">Active problem tank</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-desc">The problem tank is the live worklist of abnormal conditions that may require verification, engineering review, or maintenance action.</div>', unsafe_allow_html=True)
    if problem_scope.empty:
        st.success("No active problem matches the current filters.")
    else:
        pcols = ["Problem_ID", "Asset", "Trigger", "Severity", "Priority", "RCA_Indication", "Recommended_Action", "Owner", "SLA", "Ticket_State", "Action_Status"]
        ptable = friendly_table(problem_scope[[c for c in pcols if c in problem_scope.columns]], rename={
            "Problem_ID": "Problem identifier", "Trigger": "Why it was raised", "Severity": "Condition severity",
            "Priority": "Action priority", "RCA_Indication": "Root-cause indication", "Recommended_Action": "Recommended next action",
            "Owner": "Suggested responsible role", "SLA": "Target response time", "Ticket_State": "Ticket state", "Action_Status": "Action status",
        }, text_columns=["Trigger", "RCA_Indication", "Recommended_Action"])
        st.dataframe(ptable, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Data and model status</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-desc">This table shows whether each asset is based on recent measured data, reconstructed values, or forecasts, together with the corresponding quality classification.</div>', unsafe_allow_html=True)
    qcols = ["Asset", "Last_Actual", "Data_Age_h", "Data_Basis", "Forecast_Quality", "Downtime_Status", "Observed_Coverage_30d_h"]
    qtable = friendly_table(exec_scope[[c for c in qcols if c in exec_scope.columns]], rename={
        "Last_Actual": "Latest measured timestamp", "Data_Age_h": "Data age (hours)", "Data_Basis": "Current data basis",
        "Forecast_Quality": "Forecast quality", "Downtime_Status": "Downtime-data status",
        "Observed_Coverage_30d_h": "Observed coverage, last 30 days (hours)",
    })
    st.dataframe(qtable, use_container_width=True, hide_index=True)

with tab_problem:
    st.markdown('<div class="section-title">Active problem review</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-desc">Review why a problem was raised, the strength of the supporting evidence, the leading root-cause hypothesis, and the recommended verification or maintenance action.</div>', unsafe_allow_html=True)
    review_problems = problem_scope.copy()
    if review_problems.empty:
        st.info("No problems match the current filters.")
    else:
        labels = (review_problems["Asset"].astype(str) + " — " + review_problems["Priority"].astype(str) + " — " + review_problems["Problem_ID"].astype(str)).tolist()
        selected_label = st.selectbox("Select a problem to review", labels)
        row = review_problems.iloc[labels.index(selected_label)]

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.markdown(f'<div class="mini-card"><div class="mini-label">Asset</div><div class="mini-value">{clean_text(row.get("Asset"))}</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="mini-card"><div class="mini-label">Action priority</div><div class="mini-value">{badge(row.get("Priority"), "priority")}</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="mini-card"><div class="mini-label">Condition severity</div><div class="mini-value">{badge(row.get("Severity"))}</div></div>', unsafe_allow_html=True)
        c4.markdown(f'<div class="mini-card"><div class="mini-label">Ticket state</div><div class="mini-value">{readable_label(row.get("Ticket_State", row.get("Status")))}</div></div>', unsafe_allow_html=True)
        c5.markdown(f'<div class="mini-card"><div class="mini-label">Action status</div><div class="mini-value">{readable_label(row.get("Action_Status", "NOT_STARTED"))}</div></div>', unsafe_allow_html=True)

        st.markdown("#### Why was this problem raised?")
        st.write(clean_text(row.get("Trigger")))

        st.markdown("#### Root-cause analysis indication")
        st.caption("This is a ranked engineering hypothesis based on current evidence and similar historical incidents. It is not a confirmed physical cause until verified.")
        st.write(clean_text(row.get("RCA_Indication")))

        evidence_label = clean_text(row.get("Evidence_Score"))
        st.markdown("#### Evidence strength")
        st.write(evidence_label)
        st.caption("Evidence strength summarizes consistency between current observations and the historical analogue. It is not a probability of failure.")

        with st.expander("Why this root-cause hypothesis?"):
            st.markdown("**Current trigger / supporting evidence**")
            st.write(clean_text(row.get("Current_Evidence")))
            matched = clean_text(row.get("Matched_Incident"))
            similarity = row.get("Case_Similarity")
            st.markdown("**Historical analogue**")
            st.write(matched)
            if pd.notna(similarity):
                try:
                    st.write(f"Case similarity: {float(similarity) * 100:.1f}%")
                except Exception:
                    st.write(f"Case similarity: {clean_text(similarity)}")
            st.markdown("**Historically verified evidence**")
            st.write(clean_text(row.get("Historical_Evidence")))
            st.caption("The historical analogue is used to rank hypotheses and verification steps; it does not automatically confirm the same failure mechanism in the current asset.")

        st.markdown("#### Recommended next action")
        st.write(structured_text(row.get("Recommended_Action")))

        a1, a2, a3 = st.columns(3)
        a1.markdown("**Suggested responsible role**")
        a1.write(clean_text(row.get("Owner")))
        a2.markdown("**Target response time**")
        a2.write(clean_text(row.get("SLA")))
        a3.markdown("**Asset criticality**")
        a3.write(clean_text(row.get("Asset_Criticality")))
        a3.caption("Criticality is a business-rule input when it is not explicitly provided by the source data.")

        st.markdown("#### Follow-up action tracking")
        st.caption("Equipment condition, ticket lifecycle, and action progress are intentionally separated. Saving a follow-up update writes the operator queue immediately, clears the analytical cache, reruns the app, and refreshes the persistent ticket context.")

        current_ticket_state = str(row.get("Ticket_State", row.get("Status", "OPEN"))).upper()
        current_action_status = str(row.get("Action_Status", "NOT_STARTED")).upper()
        w1, w2 = st.columns(2)
        w1.info(f"Ticket state: {readable_label(current_ticket_state)}")
        w2.info(f"Current action status: {readable_label(current_action_status)}")

        owner_default = clean_text(row.get("Owner"))
        owner_options = [
            "Reliability / Rotating Equipment", "Electrical / Reliability",
            "Process / Static Equipment", "Instrumentation / Reliability",
        ]
        if owner_default not in owner_options and owner_default != "—":
            owner_options.insert(0, owner_default)
        owner_index = owner_options.index(owner_default) if owner_default in owner_options else 0

        action_status_options = ["NOT_STARTED", "ACKNOWLEDGED", "IN_PROGRESS", "PENDING_VERIFICATION", "COMPLETED"]
        action_index = action_status_options.index(current_action_status) if current_action_status in action_status_options else 0
        decision_options = ["", "ACKNOWLEDGE", "CONFIRM_RCA", "REJECT_RCA", "REQUEST_REVIEW", "CLOSE_TICKET"]
        decision_labels = {
            "": "No decision change", "ACKNOWLEDGE": "Acknowledge",
            "CONFIRM_RCA": "Confirm RCA hypothesis", "REJECT_RCA": "Reject RCA hypothesis",
            "REQUEST_REVIEW": "Request engineering review", "CLOSE_TICKET": "Request ticket closure",
        }
        with st.form(f"operator_update_{clean_text(row.get('Asset'))}"):
            f1, f2 = st.columns(2)
            operator_name = f1.text_input("Operator / reviewer", value="")
            owner_choice = f2.selectbox("Responsible role", owner_options, index=owner_index)
            f3, f4 = st.columns(2)
            decision_choice = f3.selectbox("Operator decision", decision_options, index=0, format_func=lambda x: decision_labels.get(x, readable_label(x)))
            action_status = f4.selectbox("Action status", action_status_options, index=action_index, format_func=readable_label)
            field_observation = st.text_area("Field observation / verification finding", value="")
            operator_comment = st.text_area("Operator comment", value="")
            submitted = st.form_submit_button("Save follow-up update")
        if submitted:
            try:
                save_operator_update(
                    asset=row.get("Asset"), decision=decision_choice, operator=operator_name,
                    comment=operator_comment, owner_role=owner_choice, action_status=action_status,
                    field_observation=field_observation,
                )
                load_engine.clear()
                st.session_state["followup_saved"] = True
                st.rerun()
            except Exception as exc:
                st.error(f"The follow-up update could not be saved: {exc}")

        with st.expander("Follow-up history"):
            ticket_id = str(row.get("Problem_ID", ""))
            ah = action_history.copy()
            if not ah.empty:
                if "Ticket ID" in ah.columns and ticket_id and not ticket_id.startswith("MONITOR-"):
                    ah = ah.loc[ah["Ticket ID"].astype(str).eq(ticket_id)]
                elif "Asset" in ah.columns:
                    ah = ah.loc[ah["Asset"].astype(str).eq(str(row.get("Asset")))]
            if ah.empty:
                st.write("No follow-up history has been recorded for this problem yet.")
            else:
                show_cols = [c for c in [
                    "Event Time", "Update Source", "Event Type", "Previous Ticket State", "New Ticket State",
                    "Previous Action Status", "New Action Status", "Operator Decision", "Operator",
                    "Owner Role", "Field Observation", "Comment"
                ] if c in ah.columns]
                hist_view = friendly_table(ah[show_cols], rename={
                    "Event Time": "Time", "Update Source": "Updated by", "Event Type": "Event",
                    "Previous Ticket State": "Previous ticket state", "New Ticket State": "New ticket state",
                    "Previous Action Status": "Previous action status", "New Action Status": "New action status",
                    "Operator Decision": "Operator decision", "Owner Role": "Responsible role",
                    "Field Observation": "Field observation",
                }, text_columns=["Field Observation", "Comment"])
                st.dataframe(hist_view, use_container_width=True, hide_index=True)
                st.caption("This is an append-only workflow audit trail. It does not modify the analytical equipment condition or forecast values.")

        erca = rca.loc[rca.Asset.eq(row.get("Asset"))] if not rca.empty and "Asset" in rca else pd.DataFrame()
        with st.expander("Root-cause evidence from similar incidents"):
            st.caption("Shows the matched historical incident, similarity level, current supporting evidence, historical verification evidence, and the resulting evidence-strength label.")
            if erca.empty:
                st.write("No similar-incident evidence is available for this selection.")
            else:
                cols = [c for c in ["Matched_Incident", "Case_Similarity", "Current_Evidence", "Historical_Evidence", "Evidence_Strength"] if c in erca]
                etable = friendly_table(erca[cols], rename={
                    "Matched_Incident": "Matched historical incident", "Case_Similarity": "Case similarity",
                    "Current_Evidence": "Current supporting evidence", "Historical_Evidence": "Historically verified evidence",
                    "Evidence_Strength": "Evidence strength",
                }, text_columns=["Current_Evidence", "Historical_Evidence"])
                st.dataframe(etable, use_container_width=True, hide_index=True)

        with st.expander("Four-P verification: People, Process, Plant, and Procedure"):
            st.caption("Four-P verification organizes evidence around human factors, operating process, physical plant/equipment, and procedures.")
            st.write("\n\n".join(clean_text(x) for x in erca["Four_P"].dropna().astype(str).unique()) if not erca.empty and "Four_P" in erca else "No Four-P verification evidence is available.")

        with st.expander("Four-M verification: Man, Machine, Method, and Material"):
            st.caption("Four-M verification groups potential contributing factors into people, equipment, work method, and material or process-medium factors.")
            st.write("\n\n".join(clean_text(x) for x in erca["Four_M"].dropna().astype(str).unique()) if not erca.empty and "Four_M" in erca else "No Four-M verification evidence is available.")

        with st.expander("Corrective and Preventive Action references"):
            st.caption("These are historical corrective or preventive actions associated with similar incidents. They are references, not automatic instructions for the current asset.")
            st.write("\n\n".join(structured_text(x) for x in erca["CAPA"].dropna().astype(str).unique()) if not erca.empty and "CAPA" in erca else "No historical corrective or preventive action reference is available.")

with tab_asset:
    st.markdown('<div class="section-title">Asset and parameter details</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-desc">Inspect each engineering parameter, its current value, decision limits, data source, model quality, and recent measured or estimated trend.</div>', unsafe_allow_html=True)
    if not assets:
        st.warning("No assets are available in the current engine output.")
    else:
        default_index = assets.index(asset_filter) if asset_filter in assets else 0
        selected_asset = st.selectbox("Select an asset", assets, index=default_index, key="asset_detail_select")
        pframe = parameter_asof.loc[parameter_asof.Asset.eq(selected_asset)].copy() if "Asset" in parameter_asof else pd.DataFrame()
        if pframe.empty:
            st.warning("No parameter data are available for the selected asset.")
        else:
            display_cols = ["Parameter", "Value", "Unit", "State", "Last_Actual", "Data_Age_h", "Source", "Quality", "Model", "Alarm_Limit", "Trip_Limit"]
            pframe["Source_Basis"] = pframe.get("Source", pd.Series(index=pframe.index, dtype=object)).map(source_family)
            display_cols = ["Parameter", "Value", "Unit", "State", "Last_Actual", "Data_Age_h", "Source_Basis", "Source", "Quality", "Model", "Alarm_Limit", "Trip_Limit"]
            dtable = friendly_table(pframe[[c for c in display_cols if c in pframe.columns]], rename={
                "Value": "Current value", "State": "Current condition", "Last_Actual": "Latest observed timestamp",
                "Data_Age_h": "Data age (hours)", "Source_Basis": "Decision provenance", "Source": "Technical source label", "Quality": "Model or estimate quality",
                "Model": "Selected model", "Alarm_Limit": "Alarm limit", "Trip_Limit": "Trip limit",
            })
            for col in ["Current condition", "Technical source label", "Model or estimate quality"]:
                if col in dtable.columns:
                    dtable[col] = dtable[col].map(readable_label)
            st.dataframe(dtable, use_container_width=True, hide_index=True)

            selected_parameter = st.selectbox("Select an engineering parameter", pframe["Parameter"].astype(str).tolist())
            result = get_result(data, selected_asset)
            parameter_data = result["projection"]["parameters"].get(selected_parameter) if result else None
            if parameter_data:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Current value at the analysis reference time", f"{fmt_num(parameter_data['value'], 2)} {parameter_data['limit'].get('unit', '')}")
                m2.markdown("**Current condition**")
                m2.markdown(badge(parameter_data.get("state")), unsafe_allow_html=True)
                m2.caption(STATE_EXPLANATIONS.get(str(parameter_data.get("state", "")).upper(), "Condition is determined from the configured engineering and statistical rules."))
                m3.metric("Age of the latest measured value", fmt_num(parameter_data.get("data_age_h", parameter_data.get("age_h")), 1, " hours"))
                m4.markdown("**Value source and model quality**")
                m4.write(source_family(parameter_data.get("source")))
                m4.caption(f"Technical label: {readable_label(parameter_data.get('source'))}. {humanize_quality(parameter_data.get('quality'))}")
                st.plotly_chart(parameter_figure(parameter_data, f"{selected_asset} — {selected_parameter}", analysis_time), use_container_width=True)

with tab_forecast:
    st.markdown('<div class="section-title">Forecast and root-cause analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-desc">Forecasts estimate how each engineering parameter may evolve after the analysis reference time. Root-cause analysis ranks plausible historical mechanisms that are consistent with the current evidence.</div>', unsafe_allow_html=True)
    if not assets:
        st.warning("No assets are available in the current engine output.")
    else:
        default_index = assets.index(asset_filter) if asset_filter in assets else 0
        selected_asset_f = st.selectbox("Select an asset", assets, index=default_index, key="forecast_asset")
        asset_forecast = forecast.loc[forecast.Asset.eq(selected_asset_f)].copy() if "Asset" in forecast else pd.DataFrame()

        if not show_forecast:
            st.info("Forecast tables are hidden by the sidebar setting.")
        elif asset_forecast.empty:
            st.info("No forecast summary is available for this asset.")
        else:
            hourly = asset_forecast.loc[asset_forecast.Horizon.isin(["H+24", "H+72", "H+168"])].copy() if "Horizon" in asset_forecast else pd.DataFrame()
            if not hourly.empty:
                st.markdown("#### Operational forecast at 24, 72, and 168 hours")
                st.caption("24 hours = next day, 72 hours = next three days, and 168 hours = next seven days after the analysis reference time.")
                table = hourly.pivot_table(index="Parameter", columns="Horizon", values="Estimate", aggfunc="first")
                for col in ["H+24", "H+72", "H+168"]:
                    if col not in table:
                        table[col] = np.nan
                table = table[["H+24", "H+72", "H+168"]].rename(columns={"H+24": "24-hour estimate", "H+72": "72-hour estimate", "H+168": "168-hour estimate"})
                st.dataframe(table, use_container_width=True)

            weekly_f = asset_forecast.loc[asset_forecast.Horizon.astype(str).str.startswith("Week+")] if "Horizon" in asset_forecast else pd.DataFrame()
            if not weekly_f.empty:
                with st.expander("Weekly forecast for the next four weeks"):
                    st.caption("Weekly forecasts are intended for parameters whose engineering measurements are available or meaningful at weekly resolution.")
                    cols = [c for c in ["Parameter", "Horizon", "Target_Time", "Estimate", "Lower", "Upper", "Quality", "Model"] if c in weekly_f]
                    wtable = friendly_table(weekly_f[cols], rename={
                        "Horizon": "Forecast week", "Target_Time": "Forecast target time", "Estimate": "Estimated value",
                        "Lower": "Lower uncertainty bound", "Upper": "Upper uncertainty bound", "Quality": "Forecast quality",
                        "Model": "Selected model",
                    })
                    st.dataframe(wtable, use_container_width=True, hide_index=True)

            models = asset_forecast[[c for c in ["Parameter", "Horizon", "Model", "Quality", "Source"] if c in asset_forecast]].drop_duplicates()
            with st.expander("Selected forecast model and quality classification"):
                st.caption("Model quality describes the strength of historical validation for the deployed model and forecast horizon.")
                st.dataframe(models.rename(columns={"Horizon": "Forecast horizon", "Model": "Selected model", "Quality": "Quality classification", "Source": "Forecast source"}), use_container_width=True, hide_index=True)

            asset_validation = validation.loc[validation.Asset.eq(selected_asset_f)] if not validation.empty and "Asset" in validation else pd.DataFrame()
            with st.expander("Model validation metrics"):
                st.caption("Validation uses temporally released observations/engineering labels as targets, not reconstructed or forecast values. MAE is the average absolute prediction error; RMSE gives more weight to large errors; Skill compares the deployed model with persistence. None of these metrics is a probability of failure.")
                vtable = asset_validation.rename(columns={
                    "MAE": "Mean absolute error", "RMSE": "Root mean square error", "Skill": "Skill versus persistence",
                    "N": "Number of validation cases", "Validation_N": "Number of validation cases",
                })
                for col in ["Validation method", "Validation target basis", "Overall deployment decision", "Deployed model"]:
                    if col in vtable.columns:
                        vtable[col] = vtable[col].map(readable_label)
                st.dataframe(vtable, use_container_width=True, hide_index=True)

        erca = rca.loc[rca.Asset.eq(selected_asset_f)] if not rca.empty and "Asset" in rca else pd.DataFrame()
        st.markdown("#### Similar historical incidents and root-cause indications")
        st.caption("Historical similarity helps prioritize hypotheses; it does not prove that the same physical cause is active now.")
        if erca.empty:
            st.info("No active similar-incident evidence is available for this asset.")
        else:
            rtable = friendly_table(erca, rename={
                "Matched_Incident": "Matched historical incident", "Case_Similarity": "Case similarity",
                "Current_Evidence": "Current supporting evidence", "Historical_Evidence": "Historically verified evidence",
                "Evidence_Strength": "Evidence strength", "Four_P": "Four-P verification", "Four_M": "Four-M verification",
                "CAPA": "Corrective and preventive action reference",
            }, text_columns=["Current_Evidence", "Historical_Evidence", "Four_P", "Four_M", "CAPA"])
            st.dataframe(rtable, use_container_width=True, hide_index=True)

with tab_quality:
    st.markdown('<div class="section-title">Data and model quality</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-desc">Use this page to understand data freshness, audit findings, parameter provenance, and model execution time. These checks explain how much confidence should be placed in each displayed result.</div>', unsafe_allow_html=True)

    qexec = executive.copy()
    cols = ["Asset", "Last_Actual", "Data_Age_h", "Data_Basis", "Forecast_Quality", "Measured_Condition", "Forecast_Condition", "Downtime_Status", "Observed_Coverage_30d_h", "Availability_30d_pct"]
    qexec = friendly_table(qexec[[c for c in cols if c in qexec]], rename={
        "Last_Actual": "Latest measured timestamp", "Data_Age_h": "Data age (hours)", "Data_Basis": "Current data basis",
        "Forecast_Quality": "Forecast quality", "Measured_Condition": "Measured condition", "Forecast_Condition": "Forecast condition",
        "Downtime_Status": "Downtime-data status", "Observed_Coverage_30d_h": "Observed coverage, last 30 days (hours)",
        "Availability_30d_pct": "Observed availability, last 30 days (%)",
    })
    st.markdown("#### Asset data freshness and model status")
    st.dataframe(qexec, use_container_width=True, hide_index=True)

    st.markdown("#### Input data-quality gate")
    st.caption("PASS means no blocking input issue was found. CHECK means the engine can run but one or more items should be reviewed. FAIL blocks the affected asset from the complete dashboard.")
    audit_view = readable_headers(audit.copy())
    st.dataframe(audit_view, use_container_width=True, hide_index=True)

    st.markdown("#### Parameter provenance and lineage")
    st.caption("Provenance records whether a value came from a workbook observation, reconstruction, indirect estimate, weekly engineering observation, or forecast model. In this competition prototype, 'observation' means a value supplied in the source workbook; it does not imply independent real-plant ground truth.")
    lineage_view = readable_headers(lineage.copy())
    for col in ["Quality", "Source"]:
        if col in lineage_view.columns:
            lineage_view[col] = lineage_view[col].map(readable_label)
    st.dataframe(lineage_view, use_container_width=True, hide_index=True)

    with st.expander("Engine execution time by phase"):
        st.caption("Execution time helps identify which analytical phases are computationally expensive. Changing a filter does not rerun the engine because results are cached.")
        timing_df = pd.DataFrame([{"Analytical phase": key, "Execution time (seconds)": value} for key, value in data.get("phase_timings", {}).items()])
        st.dataframe(timing_df, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption(
    "Intelligence engine: calculation and decision-support layer · Streamlit: interactive presentation layer · "
    "Excel and CSV outputs: audit and handover artifacts. Dashboard filtering reuses cached engine results and does not refit the analytical models."
)
