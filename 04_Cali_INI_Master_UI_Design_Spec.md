# Cali-INI — Master UI Design Specification
## Existing UI Redesign + Visual Design System + Logo Guide

> **Single source of truth for the current UI redesign.**
>
> This document consolidates the visual design system, Chandra Asri logo guidance, revised information architecture, page-by-page UI specification, user flow, progressive disclosure rules, and Streamlit implementation guidance for the **existing Cali-INI application**.
>
> **Critical constraint:** this phase is **UI-only**. Keep the analytical engine, existing data structures, analytical outputs, problem/RCA/priority/ticket/action/forecast/quality logic unchanged. **Hourly data input is intentionally out of scope for this version.**

---

# 0. MASTER DESIGN SUMMARY

## 0.1 The design problem

The current Cali-INI application already contains the required analytical information, but it presents information from different abstraction levels next to one another:

- plant-level indicators
- asset-level condition
- problem/ticket workflow
- RCA evidence
- forecast output
- model validation
- data provenance

The redesign therefore does **not** aim to remove information. It aims to put information at the level where the user actually needs it.

## 0.2 Core design principle

> **Dashboard tells the user WHAT matters.**
>
> **Problems / Assets explain WHY.**
>
> **Technical Details show HOW.**

## 0.3 User mental model

```text
SEE
  ↓
UNDERSTAND
  ↓
DECIDE
  ↓
ACT
  ↓
VERIFY
```

## 0.4 The four main areas

| Main area | Primary question |
|---|---|
| **Dashboard** | What is happening overall, and what needs attention? |
| **Problems** | What is wrong, why was it raised, and what should be done? |
| **Assets** | What is happening to this asset now, and what does the forecast show? |
| **Technical Details** | Where did the result come from, and how strong is the supporting data/model? |

## 0.5 Current → revised information architecture

```text
CURRENT
├── Executive Overview
├── Active Problems
├── Asset Details
├── Forecast & Root-Cause Analysis
└── Data & Model Quality

REVISED
├── Dashboard
├── Problems
├── Assets
└── Technical Details
```

### What moves where?

```text
Forecast
  Executive Overview / Forecast tab
        ↓
  Assets → Trend & Forecast

RCA
  Active Problems / Forecast & RCA
        ↓
  Problems → Likely Cause → Supporting Evidence

Data & Model Quality
        ↓
  Technical Details
  + small inline quality cues where relevant
```

## 0.6 Information hierarchy

### Tier 1 — Decision-first

Always visible when relevant:

- Asset
- Current condition
- Priority
- Current value
- Active problem
- Recommended action
- Forecast

### Tier 2 — Investigation

Visible when the user drills down:

- RCA indication
- Evidence strength
- Ticket status
- Action status
- Responsible role
- SLA
- Data freshness

### Tier 3 — Technical / audit

Available when explicitly requested:

- Source
- Provenance / lineage
- Model
- MAE
- RMSE
- Four-P
- Four-M
- CAPA
- Validation details
- Engine execution diagnostics

## 0.7 Main user flow

```text
OPEN CALI-INI
      ↓
CHECK CURRENT SNAPSHOT
      ↓
DASHBOARD
      ↓
┌──────────────┬──────────────────┬───────────────────┐
│              │                  │                   │
NO ATTENTION   ATTENTION          INVESTIGATE ASSET  │
│              │                  │                   │
DONE           PROBLEM            ASSET DETAIL       │
               ↓                  ↓                   │
            PROBLEMS           PARAMETERS             │
               ↓                  ↓                   │
              RCA          TREND + FORECAST           │
               ↓                                     │
        RECOMMENDED ACTION                            │
               ↓                                     │
           FOLLOW-UP                                 │
               ↓                                     │
            HISTORY                                  │
```

## 0.8 What must feel different after redesign

The user should no longer feel:

> “I need to understand the analytical model before I know what to click.”

The user should instead feel:

> “I can immediately see what matters, investigate it if necessary, and only open technical details when I need them.”

---

# PART I — VISUAL DESIGN SYSTEM & LOGO

> **Purpose:** visual reference for redesigning the existing Cali-INI interface without changing the analytical logic.
>
> **Source references:** the provided Selection Process visual and Chandra Asri logo.

---

## 1. Design Direction

Cali-INI should feel like an **industrial monitoring and decision-support application**: professional, calm, technical, trustworthy, and easy to scan.

The visual language should combine:

- **Deep corporate blue** for structure, headings, navigation, and trust.
- **Medium blue** for interactive elements and analytical emphasis.
- **Turquoise/cyan** for active states, positive emphasis, and visual continuity.
- **Very light blue-gray** for the application background.
- **White** for cards and content surfaces.

The interface should avoid looking like a generic SaaS dashboard. It should feel closer to an **industrial control / engineering decision-support interface**, while remaining clean and approachable.

---

# 2. Brand / Logo Reference

The supplied logo is the **Chandra Asri** logo.

The logo consists of:

1. A spherical icon made from layered curved bands.
2. The Chandra Asri wordmark.
3. A three-color blue/cyan visual identity.

### Logo colors observed

| Color | Hex | RGB | Recommended role |
|---|---|---|---|
| Deep Blue | `#243F7A` | 36, 63, 122 | Primary brand / logo |
| Medium Blue | `#2477B9` | 36, 119, 185 | Secondary brand |
| Cyan | `#4BC0D5` | 75, 192, 213 | Accent / highlight |

### Logo usage

**Preferred:**
- Use the full Chandra Asri logo in the application header or login/landing area.
- Keep sufficient whitespace around the logo.
- Preserve the original proportions.
- Use the supplied logo asset rather than redrawing it.

**Avoid:**
- Stretching horizontally or vertically.
- Recoloring the logo.
- Placing it over visually noisy backgrounds.
- Using very small sizes where the sphere details become unreadable.

### Recommended placement

For the main application:

```text
┌──────────────────────────────────────────────────────┐
│ [Chandra Asri logo]        Cali-INI                  │
│                           Intelligent Manufacturing   │
│                           Decision Support            │
└──────────────────────────────────────────────────────┘
```

The Chandra Asri logo should communicate the corporate context; **Cali-INI** should remain the product/application name.

---

# 3. Primary UI Color Palette

The supplied Selection Process visual provides the strongest reference for the UI palette.

## Primary colors

| Token | Hex | Usage |
|---|---|---|
| `--primary-dark` | `#0C2F7A` | Main headings, major navigation, primary text emphasis |
| `--primary-blue` | `#1A5CC8` | Buttons, links, selected states, active navigation |
| `--primary-navy` | `#1A3A6E` | Secondary headings, supporting dark text |
| `--accent-turquoise` | `#4DD4C8` | Accent, selected step, positive/active visual cue |
| `--brand-blue` | `#2477B9` | Secondary brand treatment |
| `--brand-cyan` | `#4BC0D5` | Brand accent / decorative highlight |

## Neutral colors

| Token | Hex | Usage |
|---|---|---|
| `--background` | `#F0F4F9` | Main application background |
| `--surface` | `#FFFFFF` | Cards, panels, tables |
| `--border` | `#D9E1EA` | Card borders, separators |
| `--text-primary` | `#17345F` | Main body text |
| `--text-secondary` | `#5F6F85` | Supporting text |
| `--text-muted` | `#8A94A3` | Metadata, timestamps, helper text |

### General rule

Use the palette with this approximate hierarchy:

```text
60%  Light background / white surfaces
25%  Deep + medium blues
10%  Secondary blue
5%   Turquoise accent
```

Do not turn the interface into a rainbow dashboard. Status colors should be reserved for operational meaning.

---

# 4. Status Colors

Status colors are **semantic**, not decorative.

The existing Cali-INI logic distinguishes equipment condition from ticket state and action status. The visual system should preserve this distinction.

## Equipment condition

| Condition | Visual treatment | Meaning |
|---|---|---|
| NORMAL | Green semantic status | Condition is within normal range |
| WATCH | Amber semantic status | Early deviation / needs monitoring |
| ALARM | Red semantic status | Abnormal condition requiring attention |
| TRIP | Dark red / critical semantic status | Trip-level condition |
| DATA GAP | Gray / neutral | Condition cannot be reliably assessed from available data |
| NOT OBSERVABLE | Gray / neutral | Required condition cannot be directly observed |

### Important

Do **not** use the primary brand turquoise as the only meaning for “normal”. Turquoise is a brand accent; operational status should remain semantically recognizable.

---

# 5. Priority Colors

Priority and condition should be visually distinct.

| Priority | Recommended treatment |
|---|---|
| P1 | Strong red emphasis |
| P2 | Orange/amber emphasis |
| P3 | Blue emphasis |
| P4 | Gray/neutral emphasis |

The exact shades may be tuned during implementation, but the visual hierarchy must clearly communicate that **P1 is more urgent than P4** without making the entire dashboard visually aggressive.

---

# 6. Typography

The supplied visual uses a bold modern sans-serif style.

Recommended typography:

### Headings
- Bold / semibold sans-serif
- Strong visual hierarchy
- Dark blue rather than pure black

### Body
- Regular sans-serif
- Comfortable line height
- Dark navy/blue-gray rather than black

### KPI values
- Large
- Semibold
- Minimal decoration

### Suggested scale

| Element | Suggested size |
|---|---:|
| App title | 24–30 px |
| Page title | 24–28 px |
| Section heading | 18–21 px |
| Card title | 14–16 px |
| Body text | 14–16 px |
| Helper text | 12–13 px |
| KPI number | 28–40 px |

---

# 7. UI Component Language

## Cards

Use:
- White surface
- Thin light border
- Small corner radius
- Very subtle shadow
- Generous internal padding

Avoid:
- Heavy shadows
- Excessive gradients
- Highly rounded “marketing SaaS” cards
- Bright colored backgrounds for every KPI

### Example

```text
┌──────────────────────────────┐
│ Asset Health Score       ⓘ   │
│                              │
│ 82.4 / 100                   │
│ Current asset condition      │
└──────────────────────────────┘
```

---

# 8. Dashboard KPI Hierarchy

Do not make every metric look equally important.

## Tier 1 — Core condition / decision indicators

- Asset Health Score
- Operating Performance
- Reliability & Consequence

These can use the strongest card treatment.

## Tier 2 — Operational context

- Load Index
- Production Index
- Downtime
- Emission Intensity Proxy

These should be visually lighter and more compact.

### Principle

```text
CORE CONDITION
        ↓
OPERATIONAL CONTEXT
```

This distinction prevents the user from interpreting every index as another version of “equipment health”.

---

# 9. Dashboard Layout Direction

Recommended top-to-bottom hierarchy:

```text
HEADER
│
├── Scope + Analysis Reference Time + Data Status
│
├── ATTENTION REQUIRED
│
├── CURRENT PLANT CONDITION
│
├── OPERATIONAL CONTEXT
│
├── ASSET STATUS
│
└── TREND ANALYSIS
```

The most important information should appear before supporting technical details.

---

# 10. Sidebar Style

The sidebar should feel like a **control panel**, not a second dashboard.

Recommended groups:

```text
VIEW
  Asset scope

PROBLEM FILTERS
  Priority
  Ticket status
  Show only items requiring attention

──────────────

ADVANCED
  Source workbook
  Refresh analysis

HELP
  Terminology
```

### Visual rules

- Keep section labels small and uppercase/semibold.
- Use the primary blue for selected controls.
- Do not use multiple accent colors inside the sidebar.
- Hide technical configuration under Advanced when possible.

---

# 11. Problem UI

The Problem page is an operational worklist.

Prioritize:

1. What happened?
2. Where?
3. How severe?
4. What is the likely cause?
5. What should be done?
6. Who is responsible?
7. What is the current action status?

### Recommended visual order

```text
PROBLEM
  ↓
CONDITION + PRIORITY
  ↓
WHY WAS IT RAISED?
  ↓
LIKELY CAUSE
  ↓
EVIDENCE STRENGTH
  ↓
RECOMMENDED ACTION
  ↓
OWNER + SLA
  ↓
FOLLOW-UP
  ↓
HISTORY
```

Detailed RCA evidence such as historical cases, Four-P, Four-M, CAPA, and provenance should use collapsible/secondary sections.

---

# 12. Asset UI

The Asset page is for investigation.

Recommended hierarchy:

```text
ASSET SUMMARY
│
├── Current condition
├── Health score
├── Priority
└── Latest data
│
PARAMETERS
│
├── Current value
├── Condition
└── Unit
│
TREND & FORECAST
│
├── Historical values
├── Current point
├── Forecast
├── Uncertainty range
└── Alarm / Trip limits
│
4-WEEK OUTLOOK
```

Full technical provenance, model details, validation metrics, and lineage should be available but visually secondary.

---

# 13. Chart Style

Charts should be clean and analytical.

### Historical trend

- Solid line for measured values.
- Clearly marked current/reference point.
- Reconstructed values, when present, should use a differentiated line pattern.
- Forecast should use a visually different line pattern.
- Forecast uncertainty should use a translucent range/band.
- Alarm and trip limits should be clearly distinguishable.

### Avoid

- 3D charts
- decorative gradients
- excessive markers
- unnecessary legends
- too many simultaneous series

---

# 14. Icons

Recommended style:

- Simple outline icons
- Consistent stroke width
- Blue/gray base
- Semantic colors only for status

Examples:

| Function | Icon concept |
|---|---|
| Dashboard | Grid / dashboard |
| Problems | Alert triangle / notification |
| Assets | Gear / equipment |
| Forecast | Line chart / trend |
| Settings | Gear |
| Help | Circle with question mark |
| Technical details | Sliders / database |

Do not mix filled and outlined icon families randomly.

---

# 15. Buttons

### Primary action

Use `--primary-blue`.

Examples:
- View problem
- View asset
- Save update

### Secondary action

White background + blue border.

Examples:
- View evidence
- View technical details
- View history

### Destructive / critical action

Use semantic red only when the action itself is consequential.

Do not use red just because the page contains an alarm.

---

# 16. Labels & Language

Prefer user-oriented wording.

| Current wording | Recommended |
|---|---|
| Plant-wide decision indicators | Current Plant Condition |
| Thirty-day decision-index trends | Trend Analysis |
| Active Problem Tank | Attention Required |
| Asset Condition Overview | Asset Status |
| Energy-related Load Outlook | Forecast / Operational Outlook |
| Root-cause analysis indication | Likely Cause |
| How these indicators are calculated... | Methodology / How this is calculated |
| Data and Model Quality | Technical Details / Data Quality |

The terminology should tell the user **what they can learn or do**, rather than how the backend is structured.

---

# 17. Tooltip Rules

Use tooltips for terms that need precision but do not deserve a permanent paragraph.

Good tooltip examples:

### Asset Health Score
> Composite indicator derived from current equipment condition. Higher values indicate healthier current condition.

### Production Index
> Current production relative to the measured healthy-running baseline. 100 represents the baseline.

### Emission Intensity Proxy
> Relative electricity-related emission indicator derived from available data. This is not a direct emissions measurement.

### Ticket State
> Lifecycle status of the problem ticket.

### Action Status
> Progress of the follow-up action.

Keep tooltips to **1–2 concise sentences**.

---

# 18. Data / Technical Details

Technical information should use progressive disclosure.

### Default view

```text
Forecast quality: ✓ Backtested
Data source: Measured
Data age: 1 h
```

### Expand for details

```text
Model
MAE
RMSE
Validation method
Provenance
Source
Data-quality findings
```

This preserves transparency without overwhelming the primary workflow.

---

# 19. Recommended Visual Personality

The overall personality should be:

**Professional**
- structured
- precise
- restrained

**Industrial**
- strong hierarchy
- operational states clearly visible
- engineering information easy to scan

**Modern**
- clean cards
- generous whitespace
- simple charts
- minimal visual noise

**Trustworthy**
- clear source/quality cues
- no fake precision
- explicit “proxy” labels where appropriate
- clear distinction between measured, estimated, reconstructed, and forecast values

---

# 20. Logo + Product Naming

Use:

### Primary
**Cali-INI**

### Descriptor
**Intelligent Manufacturing Decision Support**

### Corporate context
**Chandra Asri**

Suggested header arrangement:

```text
[ Chandra Asri logo ]

Cali-INI
Intelligent Manufacturing Decision Support
```

The application name should remain visually dominant on the product interface while the corporate logo establishes organizational context.

---

# 21. Design Tokens — Copy/Paste Reference

```css
:root {
  /* Brand / primary */
  --primary-dark: #0C2F7A;
  --primary-blue: #1A5CC8;
  --primary-navy: #1A3A6E;

  /* Brand secondary */
  --brand-blue: #2477B9;
  --brand-cyan: #4BC0D5;
  --accent-turquoise: #4DD4C8;

  /* Surfaces */
  --background: #F0F4F9;
  --surface: #FFFFFF;
  --border: #D9E1EA;

  /* Typography */
  --text-primary: #17345F;
  --text-secondary: #5F6F85;
  --text-muted: #8A94A3;
}
```

---

# 22. Visual Assets

The provided source images are preserved alongside this specification:

- `Cali_INI_logo_reference.png` — supplied Chandra Asri logo.
- `Cali_INI_visual_reference.png` — supplied Selection Process visual used as the main UI color/style reference.

Use these assets as visual references during implementation.

---

# 23. Final Design Principle

Cali-INI should follow:

> **Dashboard tells the user WHAT matters.**
>
> **Problem / Asset pages explain WHY.**
>
> **Technical details show HOW.**

The interface should always prioritize the user's operational question over the underlying data structure.



---

# PART II — DETAILED UI REDESIGN SPECIFICATION

## Purpose

This document defines a revised Streamlit interface for the **existing Cali-INI analytical engine**.

The redesign is intentionally **UI-only**:

- Keep `intelligence_engine.py` unchanged.
- Keep the existing data structures and analytical outputs unchanged.
- Keep the existing problem, RCA, priority, ticket-state, action-status, forecast, and quality logic unchanged.
- Change only information hierarchy, navigation, labeling, density, and visualization.
- Do **not** add hourly data input in this version.

The current `app.py` already separates UI/loading/filtering from the analytical engine, so this redesign mainly reorganizes the presentation layer.

---

# 1. Revised information architecture

## Main navigation

Use four top-level areas:

1. **Dashboard**
2. **Problems**
3. **Assets**
4. **Technical Details**

### Why these four?

- **Dashboard** answers: *What is happening overall?*
- **Problems** answers: *What is wrong, why, and what should be done?*
- **Assets** answers: *What is happening to this asset, including trend and forecast?*
- **Technical Details** answers: *Where did the data/model result come from and how strong is it?*

The existing **Forecast and Root-cause analysis** tab is removed as a top-level tab because:

- Forecast belongs naturally inside **Assets**.
- RCA belongs naturally inside **Problems**.

The existing **Data and model quality** tab becomes **Technical Details** rather than a user-facing operational menu.

---

# 2. Sidebar specification

The sidebar should contain only controls that change what the user sees.

```text
CALI-INI

VIEW
Asset scope
[ All assets ▼ ]

PROBLEM FILTERS
Priority
[ All priorities ▼ ]

Ticket status
[ All statuses ▼ ]

☐ Show only items requiring attention

────────────────────────

⚙ Technical / Advanced
    Source workbook
    Refresh analysis

ⓘ Help
    Terminology
```

## Sidebar rules

### Keep visible

- Asset scope
- Priority filter
- Ticket status filter
- Attention-only filter

### Move out of the main control area

- Source workbook → Technical / Advanced
- Reload workbook and analysis → Technical / Advanced
- Terminology → Help

### Remove

- `Show forecast tables`

Reason: forecast is no longer a table-first top-level page. Forecast lives in the Asset detail flow, with the chart as the primary view and the table as supporting information.

---

# 3. Header / snapshot bar

Replace the current verbose hero content with a concise operational snapshot.

```text
Cali-INI
Intelligent Manufacturing Decision Support

Scope: All assets     As of: 03 Oct 2026, 12:00     Data status: PASS
```

Keep the following existing information:

- analysis reference time
- historical snapshot / operating mode
- data-quality gate

Do not remove the data-quality gate; just make it compact.

---

# 4. Dashboard

## Dashboard order

```text
1. Attention Required
2. Current Plant Condition
3. Operational Context
4. Asset Status
5. Trend Analysis
```

The Dashboard should answer questions in this order:

1. Is there anything I need to pay attention to?
2. How is the selected scope doing now?
3. What is the operational context?
4. Which assets explain the current picture?
5. How have the indicators changed recently?

---

## 4.1 Attention Required

Move the current **Active Problem Tank** to the top of Dashboard.

Do not show the full current problem table here.

Show a compact exception summary:

```text
ATTENTION REQUIRED
3 items require attention

P1  1     P2  1     P3  1
```

Then show up to three compact problem cards.

Each card should contain only:

- priority
- asset
- problem / trigger
- condition severity
- ticket state
- recommended next action
- View problem button

Do not show RCA evidence, owner, SLA, historical cases, Four-P, Four-M, or CAPA on the Dashboard.

Those details belong in Problems.

If there are no matching problems:

> No active problem matches the current filters.

### Normal assets

Do **not** put NORMAL assets into Attention Required.

NORMAL assets belong in Asset Status.

---

## 4.2 Current Plant Condition

Replace **Plant-wide decision indicators** with:

> **Current Plant Condition**

Always show the current scope:

- `Scope: All assets`
- or `Scope: PU-2101B`

Show the three core indicators as primary cards:

### Asset Health Score

Current metric, no `DSS` label in the UI.

Tooltip:

> Composite condition score derived from current equipment condition. Higher values represent healthier current condition.

### Operating Performance

Tooltip:

> Normalized operating-performance indicator relative to the asset's healthy baseline.

### Reliability & Consequence

Tooltip:

> Decision indicator combining current reliability context and historical consequence information.

The analytical logic is unchanged.

Do not add language such as `decision index`, `DSS`, or `probability of failure` to the main label.

---

## 4.3 Operational Context

Move supporting operational indicators into a smaller section.

```text
OPERATIONAL CONTEXT

Load Index           118.9
Production Index      98.9
Downtime, 30 days      8.0 h
Emission Proxy        120.2
```

### Production Index tooltip

> Current production relative to the measured healthy-running baseline. A value near 100 represents the reference production level.

### Emission Intensity Proxy tooltip

> Relative electricity-related emission indicator derived from available data. This is a proxy, not a direct emissions measurement.

Do not present the emission proxy as actual CEMS / kg CO2e data.

---

## 4.4 Asset Status

Keep **Asset Condition Overview**, but simplify it.

Title:

> **Asset Status**

Purpose:

> Quickly compare the current state of each asset.

Recommended columns:

| Asset | Condition | Health | Priority | Forecast |
|---|---|---:|---|---|
| PU-2101B | Alarm | 16 | P1 | Attention |
| KO-3201 | Watch | 54 | P2 | Attention |
| PM-4405B | Normal | 87 | P4 | — |

Do not put these in the primary table:

- load proxy
- downtime
- observed coverage
- source
- model
- provenance

Those belong in Asset Details / Technical Details.

Clicking or selecting an asset should take the user conceptually to **Assets**.

---

## 4.5 Trend Analysis

Rename:

> `Thirty-day decision-index trends`

to:

> **Trend Analysis**

Add two groups of metrics.

### Condition & Reliability

- Asset Health Score
- Operating Performance Index
- Reliability & Consequence Index

### Operations

- Load Proxy Index
- Production Index
- Relative Energy Intensity

Downtime should be a separate chart because its unit is hours rather than an index.

Do not place all metrics on one axis.

### Trend scope

Allow:

- All assets / plant comparison
- One selected asset

If all assets are selected, plotting multiple asset lines is acceptable, but the user should be able to focus on one asset.

---

# 5. Problems

Rename the existing **Active problem review** tab to:

> **Problems**

The Problems page should follow:

```text
Problem List
    ↓
Problem Detail
    ↓
Why was it raised?
    ↓
Likely cause
    ↓
Evidence
    ↓
Recommended action
    ↓
Ownership + SLA
    ↓
Follow-up
    ↓
History
```

---

## 5.1 Problem List

Current dropdown selection can remain, but present it after a compact list/table.

Recommended columns:

| Priority | Asset | Problem | Condition | Ticket | Action |
|---|---|---|---|---|---|
| P1 | PU-2101B | High discharge pressure | Alarm | Open | In Progress |

The list is for finding a problem, not understanding all of its evidence.

---

## 5.2 Problem Detail

At the top:

```text
PU-2101B
High discharge pressure deviation

[ ALARM ]   [ P1 ]   Ticket: OPEN   Action: IN PROGRESS
```

### Hierarchy

Large / prominent:

- Condition severity
- Priority

Smaller / secondary:

- Ticket state
- Action status

Reason:

- Condition = current equipment condition
- Ticket = lifecycle of the problem case
- Action = progress of the human follow-up

Do not visually treat all three as the same concept.

---

## 5.3 Why was this problem raised?

Use:

> **Why is this a problem?**

Show the trigger explanation directly.

Example:

> Discharge pressure exceeded the configured engineering limit.

Keep this short and human-readable.

---

## 5.4 Root-cause indication

Use:

> **Likely Cause**

Show:

- RCA indication
- evidence strength
- one short explanation

Example structure:

```text
LIKELY CAUSE
Control valve degradation

Evidence strength
Moderate

Why?
Current pressure behavior resembles historical incidents.

[ View supporting evidence ]
```

Do not state a root cause as confirmed physical truth.

The existing engine already treats RCA as a ranked engineering hypothesis.

---

## 5.5 Supporting evidence

Keep the existing content, but use progressive disclosure:

```text
▼ Why this RCA?
▼ Historical incident evidence
▼ Four-P verification
▼ Four-M verification
▼ CAPA references
```

The underlying data remains unchanged.

Only the default visibility changes.

---

## 5.6 Recommended Action

This should be more prominent than supporting evidence.

Use:

> **Recommended Action**

Show:

- recommended action
- responsible role
- target response time / SLA
- asset criticality when available

Example:

```text
RECOMMENDED ACTION
Verify control response.

Responsible role
Reliability / Rotating Equipment

Target response
Within 24 hours
```

---

## 5.7 Follow-up Action

Keep the existing form and logic.

Do not create a separate top-level Follow-up page.

Use a section named:

> **Follow-up Action**

Current fields remain:

- Operator / reviewer
- Responsible role
- Operator decision
- Action status
- Field observation / verification finding
- Operator comment
- Save follow-up update

The workflow logic in `save_operator_update()` must remain unchanged.

Do not change ticket-state transitions in this UI redesign.

---

## 5.8 Action status presentation

Keep the existing engine values:

- NOT_STARTED
- ACKNOWLEDGED
- IN_PROGRESS
- PENDING_VERIFICATION
- COMPLETED

For display, format them as readable labels.

Use a visual progress stepper **for display**, but keep the existing underlying selectbox/update logic unless workflow logic is intentionally changed later.

Example:

```text
✓ Acknowledged
✓ In Progress
○ Pending Verification
○ Completed
```

Important: the UI must not invent new transition rules in this redesign.

---

## 5.9 Follow-up history

Keep the existing append-only history, but collapse it by default:

> `View follow-up history`

Show detailed columns only after expansion.

The current historical fields can remain:

- Event Time
- Event Type
- Previous Ticket State
- New Ticket State
- Previous Action Status
- New Action Status
- Operator Decision
- Operator
- Owner Role
- Field Observation
- Comment

---

# 6. Assets

Rename:

> `Asset details`

to:

> **Assets**

Purpose:

> Investigate a selected asset in depth.

---

## 6.1 Asset Summary

At the top:

```text
PU-2101B

Condition: Alarm
Health: 16.4 / 100
Priority: P1
Latest data: 03 Oct 2026, 12:00
```

This is a concise summary, not a technical table.

---

## 6.2 Current Parameters

Replace the full technical parameter table with:

| Parameter | Current | Condition |
|---|---:|---|
| Discharge Pressure | 82 bar | Alarm |
| Bearing Temperature | 68 °C | Normal |
| Overall Vibration | 8.2 mm/s | Watch |

Do not show these by default:

- technical source label
- selected model
- full provenance
- detailed quality classification
- alarm/trip implementation fields

These remain accessible under:

> `View technical details`

---

## 6.3 Parameter detail

After selecting one engineering parameter:

```text
Discharge Pressure

Current value: 82 bar
Condition: Alarm
Latest measured: 12:00
Data age: 1.0 hours
Source: Workbook observation
Quality: Good
```

Then show:

> **Trend & Forecast**

---

## 6.4 Trend & Forecast

Use the existing `parameter_figure()` as the primary visualization.

The chart should show:

- measured value
- reconstructed / causal estimate, when present
- current analysis reference time
- forecast / forward estimate
- model uncertainty range
- alarm limit
- trip limit

The current implementation already generates these components.

Do not create a second, redundant chart if the existing parameter graph already contains the same forecast information.

---

## 6.5 Forecast horizon selector

Use a compact selector:

```text
Forecast horizon
[ 24 h ] [ 72 h ] [ 7 days ]
```

The selected horizon controls the supporting forecast table / view.

Do not use a large table with Horizon as a repeated column if a selector can communicate the same information more clearly.

---

## 6.6 Supporting forecast table

The table is secondary to the chart.

Recommended columns:

| Parameter | Current | +24 h | +72 h | +168 h |
|---|---:|---:|---:|---:|
| Discharge Pressure | 82 | 85 | 91 | 103 |

For uncertainty detail, show an expandable version containing:

- Estimate
- Lower bound
- Upper bound
- Quality
- Model
- Target time

---

## 6.7 Four-week outlook

Keep the current weekly forecast data, but make a line chart with an uncertainty band the primary visualization.

Use the table only as supporting detail.

Recommended label:

> **4-Week Outlook**

Supporting detail can contain:

- Estimate
- Lower bound
- Upper bound
- Forecast quality
- Selected model

---

## 6.8 Model details

Do not show MAE/RMSE/model fields by default.

Use:

> **Forecast quality: Backtested**

Then:

> `View model details`

Expanded content can contain:

- Selected model
- MAE
- RMSE
- Skill versus persistence
- Validation cases
- Validation method
- Deployment decision

---

# 7. Technical Details

Rename the current:

> `Data and model quality`

to:

> **Technical Details**

This remains available, but should not interrupt the primary operational flow.

Keep the existing content:

## Data freshness

- latest measured timestamp
- data age
- data basis
- forecast quality
- measured condition
- forecast condition
- downtime status
- coverage
- availability

## Data-quality gate

- PASS
- CHECK
- FAIL

## Parameter provenance / lineage

- workbook observation
- reconstructed / model estimate
- indirect estimate
- weekly engineering observation
- forecast model

## Model validation

- MAE
- RMSE
- skill
- validation method
- validation target basis
- deployment decision

## Engine diagnostics

- analytical phase
- execution time

No analytical calculation should be changed here.

---

# 8. Progressive disclosure rule

The UI should use three information levels.

## Tier 1 — always visible

User needs this to make an operational decision quickly:

- condition
- priority
- current value
- problem
- recommended action
- forecast
- asset

## Tier 2 — visible on investigation

- RCA indication
- evidence strength
- ticket state
- action status
- data freshness
- responsible role
- SLA

## Tier 3 — technical details

- data source
- provenance
- model
- MAE
- RMSE
- Four-P
- Four-M
- CAPA
- validation

---

# 9. User flow after redesign

## Normal monitoring

```text
OPEN
  ↓
Dashboard
  ↓
Check Attention Required
  ↓
No problem
  ↓
Check current condition / asset status if needed
  ↓
DONE
```

## Problem workflow

```text
Dashboard
  ↓
Attention Required
  ↓
Open problem
  ↓
Problems
  ↓
Why was it raised?
  ↓
Likely Cause
  ↓
Evidence
  ↓
Recommended Action
  ↓
Responsible role + SLA
  ↓
Follow-up Action
  ↓
History
```

## Asset investigation workflow

```text
Dashboard
  ↓
Asset Status
  ↓
Assets
  ↓
Select asset
  ↓
Current Parameters
  ↓
Select parameter
  ↓
Current value + condition
  ↓
Historical trend
  ↓
Current point
  ↓
Forecast
  ↓
4-Week Outlook
```

## Technical verification workflow

```text
Dashboard / Problems / Assets
  ↓
View Technical Details
  ↓
Data freshness / provenance / model / validation
```

---

# 10. Streamlit implementation approach

The easiest implementation is to keep all existing data-loading code intact and replace only the presentation layer after these objects have already been created:

```python
executive
problems
rca
parameter_asof
forecast
case2_kpis
case2_coverage
energy_proxy_forecast
validation
lineage
action_history
audit
trends
assets
analysis_time
exec_scope
problem_scope
```

The current app already creates these objects before rendering the tabs.

---

# 11. Sidebar replacement code

Replace the current post-engine sidebar controls with the following grouping.

```python
# -----------------------------------------------------------------------------
# Revised sidebar controls
# -----------------------------------------------------------------------------
st.sidebar.markdown("## Cali-INI")
st.sidebar.caption("Condition monitoring and maintenance decision support")

st.sidebar.markdown("### View")
asset_filter = st.sidebar.selectbox(
    "Asset scope",
    ["All assets"] + assets,
    help="Select one asset for focused monitoring, or keep All assets for plant-wide monitoring.",
)

st.sidebar.markdown("### Problem filters")
priority_filter = st.sidebar.selectbox(
    "Priority",
    ["All priorities", "P1", "P2", "P3", "P4"],
    help="Filter problem items by action priority.",
)

status_filter = st.sidebar.selectbox(
    "Ticket status",
    status_choices,
    format_func=lambda x: x if x == "All statuses" else readable_label(x),
)

problem_only = st.sidebar.checkbox(
    "Show only items requiring attention",
    value=False,
    help="Hide routine P4 monitoring items from the problem list.",
)

st.sidebar.divider()
with st.sidebar.expander("⚙ Technical / Advanced"):
    st.caption("These controls affect the source or technical presentation of the dashboard.")
    st.code(resolved_workbook, language="text")
    if st.button("Refresh analysis", use_container_width=True):
        load_engine.clear()
        st.rerun()

with st.sidebar.expander("ⓘ Terminology"):
    st.markdown(
        """
        **RCA:** Root Cause Analysis.

        **CAPA:** Corrective and Preventive Action.

        **DCS:** Distributed Control System.

        **Analysis reference time:** latest common timestamp used for the current snapshot.

        **Forecast horizon:** how far ahead a forecast is made, such as 24, 72, or 168 hours.

        **Equipment condition:** analytical condition state such as Normal, Watch, Alarm, or Trip.

        **Ticket state:** lifecycle state of the problem ticket.

        **Action status:** progress of the follow-up action.
        """
    )
```

Note: keep the existing workbook validation and engine-loading block above this section unchanged.

---

# 12. Revised scope filtering code

Keep the existing filtering logic.

```python
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
```

Do not modify the analytical engine based on this filtering change.

---

# 13. Recommended navigation implementation

Instead of five `st.tabs`, use a top navigation selector so buttons can move the user between areas more naturally.

```python
# -----------------------------------------------------------------------------
# Main navigation
# -----------------------------------------------------------------------------
if "nav" not in st.session_state:
    st.session_state["nav"] = "Dashboard"

nav = st.radio(
    "",
    ["Dashboard", "Problems", "Assets", "Technical Details"],
    horizontal=True,
    key="main_navigation",
)
st.session_state["nav"] = nav
```

If the project prefers to retain `st.tabs`, the same page structure can be implemented inside tabs; however, `st.radio` is preferred here because it allows buttons on the Dashboard to set the destination page through session state.

---

# 14. Header code

```python
# -----------------------------------------------------------------------------
# Header
# -----------------------------------------------------------------------------
quality = status_rank(audit["Status"] if "Status" in audit else [])
scope_label = "All assets" if asset_filter == "All assets" else asset_filter

st.markdown(
    f"""
    <div class="hero">
      <h1>Cali-INI</h1>
      <p>Intelligent Manufacturing Decision Support</p>
      <p>
        <b>Scope:</b> {clean_text(scope_label)}
        &nbsp;·&nbsp;
        <b>As of:</b> {analysis_time:%d %b %Y, %H:%M}
        &nbsp;·&nbsp;
        <b>Data status:</b> {quality}
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)
```

---

# 15. Dashboard implementation code

```python
if st.session_state["nav"] == "Dashboard":
    st.markdown("## Dashboard")
    st.caption("Start here to understand what needs attention and how the selected scope is performing.")

    # -------------------------------------------------------------------------
    # 1. Attention Required
    # -------------------------------------------------------------------------
    attention = problem_scope.copy()
    if "Priority" in attention.columns:
        attention = attention.loc[attention["Priority"].astype(str).isin(["P1", "P2", "P3"])]

    st.markdown("### Attention Required")
    if attention.empty:
        st.success("No active problem matches the current filters.")
    else:
        counts = attention["Priority"].value_counts().to_dict()
        s1, s2, s3 = st.columns(3)
        s1.metric("P1", int(counts.get("P1", 0)))
        s2.metric("P2", int(counts.get("P2", 0)))
        s3.metric("P3", int(counts.get("P3", 0)))

        show_n = min(3, len(attention))
        for _, prow in attention.head(show_n).iterrows():
            p1, p2, p3 = st.columns([0.9, 2.5, 1.2])
            p1.markdown(
                f"**{readable_label(prow.get('Priority'))}**\n\n{clean_text(prow.get('Asset'))}")
            p2.markdown(
                f"**{clean_text(prow.get('Trigger'))}**\n\n"
                f"Condition: {readable_label(prow.get('Severity'))}  ·  "
                f"Ticket: {readable_label(prow.get('Ticket_State', prow.get('Status')))}")
            p3.markdown(
                f"**Next action**\n\n{structured_text(prow.get('Recommended_Action'))}")
            st.divider()

        st.info("Open the Problems page to investigate a selected issue, review evidence, and record follow-up.")

    # -------------------------------------------------------------------------
    # 2. Current Plant Condition
    # -------------------------------------------------------------------------
    st.markdown("### Current Plant Condition")
    st.caption(f"Scope: **{scope_label}**")

    cards = aggregate_cards(exec_scope)
    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Asset Health Score",
        fmt_num(cards.get("health"), 1, " / 100"),
        help="Composite condition score derived from current equipment condition. Higher values represent healthier current condition.",
    )
    c2.metric(
        "Operating Performance",
        fmt_num(cards.get("operating"), 1, " / 100"),
        help="Normalized operating-performance indicator relative to the asset's healthy baseline.",
    )
    c3.metric(
        "Reliability & Consequence",
        fmt_num(cards.get("reliability"), 1, " / 100"),
        help="Decision indicator combining current reliability context and historical consequence information.",
    )

    # -------------------------------------------------------------------------
    # 3. Operational Context
    # -------------------------------------------------------------------------
    st.markdown("### Operational Context")
    ck = case2_kpis.copy()
    if asset_filter != "All assets" and not ck.empty and "Asset" in ck:
        ck = ck.loc[ck["Asset"].eq(asset_filter)]

    prod = pd.to_numeric(ck.get("Production_Index"), errors="coerce").mean() if not ck.empty else np.nan
    emis = pd.to_numeric(ck.get("Emission_Intensity_Proxy"), errors="coerce").mean() if not ck.empty else np.nan

    o1, o2, o3, o4 = st.columns(4)
    o1.metric(
        "Load Index",
        fmt_num(cards.get("load"), 1),
        help="Relative operating-load indicator. A value near 100 represents the reference load level.",
    )
    o2.metric(
        "Production Index",
        fmt_num(prod, 1),
        help="Current production relative to the measured healthy-running baseline. A value near 100 represents the reference production level.",
    )
    o3.metric(
        "Downtime — Last 30 Days",
        fmt_num(cards.get("downtime"), 1, " h") if cards.get("coverage", 0) > 0 else "—",
        help="Downtime calculated from observed running-status data in the 30-day window.",
    )
    o4.metric(
        "Emission Intensity Proxy",
        fmt_num(emis, 1) if pd.notna(emis) else "—",
        help="Relative electricity-related emission-intensity proxy. This is not a direct emissions measurement.",
    )

    # -------------------------------------------------------------------------
    # 4. Asset Status
    # -------------------------------------------------------------------------
    st.markdown("### Asset Status")
    st.caption("Quick comparison of current condition, health, priority, and forecast risk by asset.")

    overview_cols = [
        "Asset", "Measured_Condition", "Asset_Health_Score", "Priority", "Forecast_Risk_168h"
    ]
    overview = exec_scope[[c for c in overview_cols if c in exec_scope.columns]].copy()
    overview = overview.rename(columns={
        "Measured_Condition": "Condition",
        "Asset_Health_Score": "Health",
        "Priority": "Priority",
        "Forecast_Risk_168h": "Forecast",
    })
    if "Condition" in overview.columns:
        overview["Condition"] = overview["Condition"].map(readable_label)
    if "Forecast" in overview.columns:
        overview["Forecast"] = overview["Forecast"].map(readable_label)
    st.dataframe(overview, use_container_width=True, hide_index=True)

    # -------------------------------------------------------------------------
    # 5. Trend Analysis
    # -------------------------------------------------------------------------
    st.markdown("### Trend Analysis")
    trend_group = st.radio(
        "Trend group",
        ["Condition & Reliability", "Operations"],
        horizontal=True,
    )

    if trend_group == "Condition & Reliability":
        metric_options = [
            "Asset Health Score",
            "Operating Performance Index",
            "Reliability & Consequence Index",
        ]
        y_title = "Index (0–100)"
    else:
        metric_options = [
            "Load Proxy Index",
            "Production Index",
            "Relative Energy Intensity",
        ]
        y_title = "Relative index"

    metric_choice = st.selectbox("Indicator", metric_options)

    trend_assets = assets if asset_filter == "All assets" else [asset_filter]
    fig = go.Figure()
    for asset in trend_assets:
        if asset not in trends:
            continue
        if metric_choice not in trends[asset]:
            continue
        daily = trends[asset][metric_choice].resample("D").mean()
        fig.add_trace(
            go.Scatter(
                x=daily.index,
                y=daily,
                mode="lines",
                name=asset,
                line=dict(width=2),
            )
        )

    fig.update_layout(
        height=360,
        margin=dict(l=20, r=20, t=20, b=20),
        yaxis_title=y_title,
        hovermode="x unified",
        legend=dict(orientation="h"),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#EEF2F6")
    st.plotly_chart(fig, use_container_width=True)
```

---

# 16. Problems implementation code

Use the current problem workflow and `save_operator_update()` logic, but reorganize its presentation.

```python
if st.session_state["nav"] == "Problems":
    st.markdown("## Problems")
    st.caption("Investigate active issues, understand the likely cause, and track follow-up actions.")

    review_problems = problem_scope.copy()

    if review_problems.empty:
        st.success("No problems match the current filters.")
    else:
        list_cols = [
            "Priority", "Asset", "Trigger", "Severity",
            "Ticket_State", "Action_Status",
        ]
        problem_list = friendly_table(
            review_problems[[c for c in list_cols if c in review_problems.columns]],
            rename={
                "Priority": "Priority",
                "Asset": "Asset",
                "Trigger": "Problem",
                "Severity": "Condition",
                "Ticket_State": "Ticket",
                "Action_Status": "Action",
            },
            text_columns=["Trigger"],
        )
        for col in ["Condition", "Ticket", "Action"]:
            if col in problem_list.columns:
                problem_list[col] = problem_list[col].map(readable_label)

        st.dataframe(problem_list, use_container_width=True, hide_index=True)

        labels = (
            review_problems["Asset"].astype(str)
            + " — "
            + review_problems["Priority"].astype(str)
            + " — "
            + review_problems["Problem_ID"].astype(str)
        ).tolist()
        selected_label = st.selectbox("Select a problem", labels)
        row = review_problems.iloc[labels.index(selected_label)]

        st.markdown("---")
        st.markdown(f"## {clean_text(row.get('Asset'))}")
        st.markdown(f"### {clean_text(row.get('Trigger'))}")

        c1, c2, c3, c4 = st.columns(4)
        c1.markdown("**Condition**")
        c1.markdown(badge(row.get("Severity")), unsafe_allow_html=True)
        c2.markdown("**Priority**")
        c2.markdown(badge(row.get("Priority"), "priority"), unsafe_allow_html=True)
        c3.markdown("**Ticket**")
        c3.write(readable_label(row.get("Ticket_State", row.get("Status"))))
        c4.markdown("**Action**")
        c4.write(readable_label(row.get("Action_Status", "NOT_STARTED")))

        st.markdown("### Why is this a problem?")
        st.write(clean_text(row.get("Trigger")))

        st.markdown("### Likely Cause")
        st.caption("This is a ranked engineering hypothesis based on current evidence and similar historical incidents. It is not a confirmed physical cause until verified.")
        st.write(clean_text(row.get("RCA_Indication")))

        st.markdown("### Evidence Strength")
        st.write(clean_text(row.get("Evidence_Score")))
        st.caption("Evidence strength is not a probability of failure.")

        with st.expander("Why this RCA?"):
            st.markdown("**Current supporting evidence**")
            st.write(clean_text(row.get("Current_Evidence")))

            st.markdown("**Historical analogue**")
            st.write(clean_text(row.get("Matched_Incident")))

            similarity = row.get("Case_Similarity")
            if pd.notna(similarity):
                try:
                    st.write(f"Case similarity: {float(similarity) * 100:.1f}%")
                except Exception:
                    st.write(f"Case similarity: {clean_text(similarity)}")

            st.markdown("**Historically verified evidence**")
            st.write(clean_text(row.get("Historical_Evidence")))

        st.markdown("### Recommended Action")
        st.write(structured_text(row.get("Recommended_Action")))

        a1, a2, a3 = st.columns(3)
        a1.markdown("**Responsible role**")
        a1.write(clean_text(row.get("Owner")))
        a2.markdown("**Target response**")
        a2.write(clean_text(row.get("SLA")))
        a3.markdown("**Asset criticality**")
        a3.write(clean_text(row.get("Asset_Criticality")))

        st.markdown("### Follow-up Action")
        current_ticket_state = str(row.get("Ticket_State", row.get("Status", "OPEN"))).upper()
        current_action_status = str(row.get("Action_Status", "NOT_STARTED")).upper()

        st.info(
            f"Ticket: {readable_label(current_ticket_state)}  ·  "
            f"Action: {readable_label(current_action_status)}"
        )

        owner_default = clean_text(row.get("Owner"))
        owner_options = [
            "Reliability / Rotating Equipment",
            "Electrical / Reliability",
            "Process / Static Equipment",
            "Instrumentation / Reliability",
        ]
        if owner_default not in owner_options and owner_default != "—":
            owner_options.insert(0, owner_default)
        owner_index = owner_options.index(owner_default) if owner_default in owner_options else 0

        action_status_options = [
            "NOT_STARTED",
            "ACKNOWLEDGED",
            "IN_PROGRESS",
            "PENDING_VERIFICATION",
            "COMPLETED",
        ]
        action_index = action_status_options.index(current_action_status) if current_action_status in action_status_options else 0

        decision_options = [
            "",
            "ACKNOWLEDGE",
            "CONFIRM_RCA",
            "REJECT_RCA",
            "REQUEST_REVIEW",
            "CLOSE_TICKET",
        ]
        decision_labels = {
            "": "No decision change",
            "ACKNOWLEDGE": "Acknowledge",
            "CONFIRM_RCA": "Confirm RCA hypothesis",
            "REJECT_RCA": "Reject RCA hypothesis",
            "REQUEST_REVIEW": "Request engineering review",
            "CLOSE_TICKET": "Request ticket closure",
        }

        with st.form(f"operator_update_{clean_text(row.get('Asset'))}"):
            f1, f2 = st.columns(2)
            operator_name = f1.text_input("Operator / reviewer")
            owner_choice = f2.selectbox("Responsible role", owner_options, index=owner_index)

            f3, f4 = st.columns(2)
            decision_choice = f3.selectbox(
                "Operator decision",
                decision_options,
                index=0,
                format_func=lambda x: decision_labels.get(x, readable_label(x)),
            )
            action_status = f4.selectbox(
                "Action status",
                action_status_options,
                index=action_index,
                format_func=readable_label,
            )

            field_observation = st.text_area("Field observation / verification finding")
            operator_comment = st.text_area("Operator comment")
            submitted = st.form_submit_button("Save follow-up update")

        if submitted:
            try:
                save_operator_update(
                    asset=row.get("Asset"),
                    decision=decision_choice,
                    operator=operator_name,
                    comment=operator_comment,
                    owner_role=owner_choice,
                    action_status=action_status,
                    field_observation=field_observation,
                )
                load_engine.clear()
                st.session_state["followup_saved"] = True
                st.rerun()
            except Exception as exc:
                st.error(f"The follow-up update could not be saved: {exc}")

        with st.expander("View follow-up history"):
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
                hist_view = friendly_table(
                    ah[show_cols],
                    rename={
                        "Event Time": "Time",
                        "Update Source": "Updated by",
                        "Event Type": "Event",
                        "Previous Ticket State": "Previous ticket state",
                        "New Ticket State": "New ticket state",
                        "Previous Action Status": "Previous action status",
                        "New Action Status": "New action status",
                        "Operator Decision": "Operator decision",
                        "Owner Role": "Responsible role",
                        "Field Observation": "Field observation",
                    },
                    text_columns=["Field Observation", "Comment"],
                )
                st.dataframe(hist_view, use_container_width=True, hide_index=True)

        erca = rca.loc[rca.Asset.eq(row.get("Asset"))] if not rca.empty and "Asset" in rca else pd.DataFrame()
        with st.expander("Historical incident evidence"):
            if erca.empty:
                st.write("No similar-incident evidence is available for this selection.")
            else:
                cols = [c for c in ["Matched_Incident", "Case_Similarity", "Current_Evidence", "Historical_Evidence", "Evidence_Strength"] if c in erca]
                etable = friendly_table(
                    erca[cols],
                    rename={
                        "Matched_Incident": "Matched historical incident",
                        "Case_Similarity": "Case similarity",
                        "Current_Evidence": "Current supporting evidence",
                        "Historical_Evidence": "Historically verified evidence",
                        "Evidence_Strength": "Evidence strength",
                    },
                    text_columns=["Current_Evidence", "Historical_Evidence"],
                )
                st.dataframe(etable, use_container_width=True, hide_index=True)

        with st.expander("Four-P verification"):
            st.write(
                "\n\n".join(clean_text(x) for x in erca["Four_P"].dropna().astype(str).unique())
                if not erca.empty and "Four_P" in erca
                else "No Four-P verification evidence is available."
            )

        with st.expander("Four-M verification"):
            st.write(
                "\n\n".join(clean_text(x) for x in erca["Four_M"].dropna().astype(str).unique())
                if not erca.empty and "Four_M" in erca
                else "No Four-M verification evidence is available."
            )

        with st.expander("CAPA references"):
            st.write(
                "\n\n".join(structured_text(x) for x in erca["CAPA"].dropna().astype(str).unique())
                if not erca.empty and "CAPA" in erca
                else "No historical CAPA reference is available."
            )
```

---

# 17. Assets implementation code

This combines the existing Asset Details and Forecast pages.

```python
if st.session_state["nav"] == "Assets":
    st.markdown("## Assets")
    st.caption("Inspect current asset condition, engineering parameters, recent trend, and forecast outlook.")

    if not assets:
        st.warning("No assets are available in the current engine output.")
    else:
        default_index = assets.index(asset_filter) if asset_filter in assets else 0
        selected_asset = st.selectbox(
            "Select an asset",
            assets,
            index=default_index,
            key="asset_detail_select",
        )

        asset_exec = executive.loc[executive.Asset.eq(selected_asset)].copy()
        result = get_result(data, selected_asset)
        pframe = parameter_asof.loc[parameter_asof.Asset.eq(selected_asset)].copy() if "Asset" in parameter_asof else pd.DataFrame()

        # ---------------------------------------------------------------------
        # Asset summary
        # ---------------------------------------------------------------------
        st.markdown("### Asset Summary")
        if not asset_exec.empty:
            asset_row = asset_exec.iloc[0]
            a1, a2, a3, a4 = st.columns(4)
            a1.metric("Condition", readable_label(asset_row.get("Measured_Condition")))
            a2.metric("Health", fmt_num(asset_row.get("Asset_Health_Score"), 1, " / 100"))
            a3.metric("Priority", readable_label(asset_row.get("Priority")))
            a4.metric("Latest data", fmt_time(asset_row.get("Last_Actual")))

        if pframe.empty:
            st.warning("No parameter data are available for the selected asset.")
        else:
            # -----------------------------------------------------------------
            # Current Parameters
            # -----------------------------------------------------------------
            st.markdown("### Current Parameters")
            pview = pframe[[c for c in ["Parameter", "Value", "Unit", "State"] if c in pframe.columns]].copy()
            if "Value" in pview.columns and "Unit" in pview.columns:
                pview["Current"] = pview.apply(
                    lambda r: f"{fmt_num(r.get('Value'), 2)} {clean_text(r.get('Unit'))}", axis=1
                )
                pview = pview.drop(columns=[c for c in ["Value", "Unit"] if c in pview.columns])
            pview = pview.rename(columns={"State": "Condition"})
            if "Condition" in pview.columns:
                pview["Condition"] = pview["Condition"].map(readable_label)
            st.dataframe(pview, use_container_width=True, hide_index=True)

            # -----------------------------------------------------------------
            # Parameter selection
            # -----------------------------------------------------------------
            selected_parameter = st.selectbox(
                "Select an engineering parameter",
                pframe["Parameter"].astype(str).tolist(),
            )
            parameter_data = result["projection"]["parameters"].get(selected_parameter) if result else None

            if parameter_data:
                st.markdown(f"### {selected_parameter}")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric(
                    "Current value",
                    f"{fmt_num(parameter_data['value'], 2)} {parameter_data['limit'].get('unit', '')}",
                )
                m2.markdown("**Condition**")
                m2.markdown(badge(parameter_data.get("state")), unsafe_allow_html=True)
                m2.caption(
                    STATE_EXPLANATIONS.get(
                        str(parameter_data.get("state", "")).upper(),
                        "Condition is determined from configured engineering and statistical rules.",
                    )
                )
                m3.metric(
                    "Data age",
                    fmt_num(parameter_data.get("data_age_h", parameter_data.get("age_h")), 1, " h"),
                )
                m4.markdown("**Data source / quality**")
                m4.write(source_family(parameter_data.get("source")))
                m4.caption(humanize_quality(parameter_data.get("quality")))

                st.markdown("### Trend & Forecast")
                st.plotly_chart(
                    parameter_figure(
                        parameter_data,
                        f"{selected_asset} — {selected_parameter}",
                        analysis_time,
                    ),
                    use_container_width=True,
                )

                # -----------------------------------------------------------------
                # Forecast horizon summary
                # -----------------------------------------------------------------
                st.markdown("### Forecast")
                forecast_horizon = st.radio(
                    "Forecast horizon",
                    ["24 h", "72 h", "7 days"],
                    horizontal=True,
                )
                horizon_map = {
                    "24 h": "H+24",
                    "72 h": "H+72",
                    "7 days": "H+168",
                }
                selected_horizon = horizon_map[forecast_horizon]

                asset_forecast = forecast.loc[forecast.Asset.eq(selected_asset)].copy() if "Asset" in forecast else pd.DataFrame()
                selected_f = asset_forecast.loc[
                    (asset_forecast["Parameter"].astype(str).eq(selected_parameter))
                    & (asset_forecast["Horizon"].astype(str).eq(selected_horizon))
                ].copy() if not asset_forecast.empty and "Parameter" in asset_forecast and "Horizon" in asset_forecast else pd.DataFrame()

                if selected_f.empty:
                    st.info("No forecast is available for the selected parameter and horizon.")
                else:
                    fcols = [c for c in ["Parameter", "Horizon", "Target_Time", "Estimate", "Lower", "Upper", "Quality", "Model"] if c in selected_f.columns]
                    fview = friendly_table(
                        selected_f[fcols],
                        rename={
                            "Horizon": "Horizon",
                            "Target_Time": "Target time",
                            "Estimate": "Estimate",
                            "Lower": "Lower bound",
                            "Upper": "Upper bound",
                            "Quality": "Forecast quality",
                            "Model": "Model",
                        },
                    )
                    st.dataframe(fview, use_container_width=True, hide_index=True)

                # -----------------------------------------------------------------
                # Four-week outlook
                # -----------------------------------------------------------------
                weekly_f = asset_forecast.loc[
                    asset_forecast["Horizon"].astype(str).str.startswith("Week+")
                ].copy() if not asset_forecast.empty and "Horizon" in asset_forecast else pd.DataFrame()

                if not weekly_f.empty:
                    st.markdown("### 4-Week Outlook")
                    weekly_param = weekly_f.loc[
                        weekly_f["Parameter"].astype(str).eq(selected_parameter)
                    ].copy() if "Parameter" in weekly_f else pd.DataFrame()

                    if not weekly_param.empty and "Estimate" in weekly_param:
                        weekly_param["Date"] = pd.to_datetime(weekly_param.get("Target_Time"), errors="coerce")
                        fig_w = go.Figure()
                        fig_w.add_trace(
                            go.Scatter(
                                x=weekly_param["Date"],
                                y=weekly_param["Upper"],
                                mode="lines",
                                line=dict(width=0),
                                hoverinfo="skip",
                                showlegend=False,
                            )
                        )
                        fig_w.add_trace(
                            go.Scatter(
                                x=weekly_param["Date"],
                                y=weekly_param["Lower"],
                                mode="lines",
                                fill="tonexty",
                                line=dict(width=0),
                                name="Uncertainty range",
                            )
                        )
                        fig_w.add_trace(
                            go.Scatter(
                                x=weekly_param["Date"],
                                y=weekly_param["Estimate"],
                                mode="lines+markers",
                                name="Forecast",
                            )
                        )
                        fig_w.update_layout(
                            height=340,
                            margin=dict(l=20, r=20, t=20, b=20),
                            hovermode="x unified",
                            plot_bgcolor="white",
                            paper_bgcolor="white",
                        )
                        fig_w.update_xaxes(showgrid=False)
                        fig_w.update_yaxes(gridcolor="#EEF2F6")
                        st.plotly_chart(fig_w, use_container_width=True)

                    with st.expander("Forecast details"):
                        cols = [c for c in ["Parameter", "Horizon", "Target_Time", "Estimate", "Lower", "Upper", "Quality", "Model"] if c in weekly_param]
                        if cols:
                            st.dataframe(
                                friendly_table(
                                    weekly_param[cols],
                                    rename={
                                        "Horizon": "Forecast week",
                                        "Target_Time": "Forecast target time",
                                        "Estimate": "Estimated value",
                                        "Lower": "Lower uncertainty bound",
                                        "Upper": "Upper uncertainty bound",
                                        "Quality": "Forecast quality",
                                        "Model": "Selected model",
                                    },
                                ),
                                use_container_width=True,
                                hide_index=True,
                            )

                # -----------------------------------------------------------------
                # Technical detail for the selected parameter
                # -----------------------------------------------------------------
                with st.expander("Technical details for this parameter"):
                    technical_row = pframe.loc[pframe["Parameter"].astype(str).eq(selected_parameter)].copy()
                    if not technical_row.empty:
                        st.dataframe(
                            readable_headers(technical_row),
                            use_container_width=True,
                            hide_index=True,
                        )
```

---

# 18. Technical Details implementation code

Move the existing quality page here without changing its data.

```python
if st.session_state["nav"] == "Technical Details":
    st.markdown("## Technical Details")
    st.caption("Supporting information about data freshness, provenance, forecast quality, and model validation.")

    qexec = executive.copy()
    cols = [
        "Asset", "Last_Actual", "Data_Age_h", "Data_Basis",
        "Forecast_Quality", "Measured_Condition", "Forecast_Condition",
        "Downtime_Status", "Observed_Coverage_30d_h", "Availability_30d_pct",
    ]
    qexec = friendly_table(
        qexec[[c for c in cols if c in qexec]],
        rename={
            "Last_Actual": "Latest measured timestamp",
            "Data_Age_h": "Data age (hours)",
            "Data_Basis": "Current data basis",
            "Forecast_Quality": "Forecast quality",
            "Measured_Condition": "Measured condition",
            "Forecast_Condition": "Forecast condition",
            "Downtime_Status": "Downtime-data status",
            "Observed_Coverage_30d_h": "Observed coverage, last 30 days (hours)",
            "Availability_30d_pct": "Observed availability, last 30 days (%)",
        },
    )

    st.markdown("### Asset Data Freshness & Model Status")
    st.dataframe(qexec, use_container_width=True, hide_index=True)

    st.markdown("### Input Data-quality Gate")
    st.caption(
        "PASS means no blocking input issue was found. CHECK means the engine can run but one or more items should be reviewed. FAIL blocks the affected asset from the complete dashboard."
    )
    st.dataframe(readable_headers(audit.copy()), use_container_width=True, hide_index=True)

    st.markdown("### Parameter Provenance & Lineage")
    lineage_view = readable_headers(lineage.copy())
    for col in ["Quality", "Source"]:
        if col in lineage_view.columns:
            lineage_view[col] = lineage_view[col].map(readable_label)
    st.dataframe(lineage_view, use_container_width=True, hide_index=True)

    st.markdown("### Forecast Validation")
    st.caption(
        "Validation metrics evaluate the forecast model against released historical targets. MAE, RMSE, and skill are model-validation measures and are not probabilities of failure."
    )
    st.dataframe(
        readable_headers(validation.copy()),
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Engine execution time by phase"):
        timing_df = pd.DataFrame(
            [
                {"Analytical phase": key, "Execution time (seconds)": value}
                for key, value in data.get("phase_timings", {}).items()
            ]
        )
        st.dataframe(timing_df, use_container_width=True, hide_index=True)
```

---

# 19. Optional CSS additions

Add the following styles to the existing visual system. These do not affect the analytical engine.

```python
st.markdown(
    """
    <style>
    .attention-card {
        background: #FFFFFF;
        border: 1px solid #E5EAF0;
        border-left: 4px solid #E46B20;
        border-radius: 12px;
        padding: 0.85rem 1rem;
        margin-bottom: 0.65rem;
    }

    .subtle-label {
        color: #687386;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        font-weight: 700;
    }

    .page-note {
        background: #F5F8FC;
        border: 1px solid #E5EAF0;
        border-radius: 10px;
        padding: 0.65rem 0.85rem;
        color: #374151;
        font-size: 0.86rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
```

---

# 20. What must NOT be changed

The redesign must not alter these engine concepts:

- condition state logic
- Asset Health Score calculation
- Operating Performance Index calculation
- Load Proxy Index calculation
- Reliability & Consequence Index calculation
- Production Index baseline logic
- Energy/load forecast logic
- H+24 / H+72 / H+168 forecast generation
- weekly forecast generation
- RCA historical similarity logic
- evidence strength logic
- P1–P4 prioritization logic
- ticket lifecycle logic
- action status values
- `save_operator_update()` behavior
- follow-up history persistence
- data-quality rules
- model validation logic

Only the UI placement, labeling, grouping, visibility, and visualization should change.

---

# 21. Existing → Revised mapping

| Existing | Revised |
|---|---|
| Dashboard controls | Sidebar: View + Problem Filters + Technical + Help |
| Source workbook | Technical / Advanced |
| Reload workbook and analysis | Technical / Advanced |
| Asset scope | Sidebar → View |
| Action priority | Sidebar → Problem Filters |
| Ticket state | Sidebar → Problem Filters |
| Show only items requiring attention | Sidebar → Problem Filters |
| Show forecast tables | Remove |
| Terminology | Sidebar → Help |
| Executive overview | Dashboard |
| Plant-wide decision indicators | Current Plant Condition |
| Production and emissions context | Operational Context |
| Energy-related load outlook | Assets → Forecast |
| How indicators are calculated | Technical Details / tooltip |
| Asset condition overview | Asset Status |
| Thirty-day decision-index trends | Trend Analysis |
| Active problem tank | Dashboard → Attention Required |
| Active problem review | Problems |
| Root-cause indication | Problems → Likely Cause |
| Root-cause evidence | Problems → Supporting Evidence |
| Recommended next action | Problems → Recommended Action |
| Follow-up action tracking | Problems → Follow-up Action |
| Follow-up history | Problems → expandable history |
| Asset details | Assets |
| Full parameter table | Assets → simplified Current Parameters + technical expander |
| Forecast and root-cause analysis | Remove as top-level tab |
| Operational forecast | Assets → Trend & Forecast |
| Weekly forecast | Assets → 4-Week Outlook |
| Forecast model | Assets → Technical Details |
| Model validation metrics | Technical Details |
| Data and model quality | Technical Details |

---

# 22. Final user mental model

The interface should feel like this:

```text
DASHBOARD
"What needs my attention?"
        ↓
PROBLEMS
"What is wrong, why, and what should I do?"
        ↓
ASSETS
"What is happening to this asset now and next?"
        ↓
TECHNICAL DETAILS
"How was this result produced and how strong is it?"
```

The system therefore becomes:

```text
SEE
 ↓
UNDERSTAND
 ↓
DECIDE
 ↓
ACT
 ↓
VERIFY
```

without changing the existing analytical engine.

---

# 23. Important implementation note

This document is intentionally a **presentation-layer redesign**. Some code blocks above assume the existing helper functions and engine result objects remain available, including:

```python
aggregate_cards()
parameter_figure()
friendly_table()
readable_headers()
readable_label()
source_family()
humanize_quality()
get_result()
badge()
fmt_num()
fmt_time()
clean_text()
structured_text()
save_operator_update()
load_engine()
```

The existing `intelligence_engine.py` should not be edited for this UI-only phase.

Before replacing the full `app.py`, integrate the sidebar block and navigation block carefully with the existing engine-loading section.

---

# 24. Source reference

Current repository:

- `app.py`: Streamlit loading, filtering, visualization, and workflow UI.
- `intelligence_engine.py`: analytical engine, condition logic, forecasting, RCA, prioritization, and workflow persistence.

Repository:
`https://github.com/ninooow/Cali-INI`


---

# PART III — UNIFIED IMPLEMENTATION RULES

# 73. One-source-of-truth rule

This file is the consolidated reference for implementation.

When the visual system and the UI specification seem to overlap:

- Use the **visual system** for how something should look.
- Use the **UI specification** for where it should appear and what it should do.
- Use the **analytical engine** as the source of truth for calculations and state transitions.

Do not invent new analytical semantics merely to make the UI easier to design.

---

# 74. Do not confuse these concepts

| Concept | User-facing question | UI treatment |
|---|---|---|
| **Equipment Condition** | How is the equipment now? | Strong semantic badge |
| **Priority** | How urgently does this need attention? | Distinct P1–P4 badge |
| **Ticket Status** | Where is this problem case in its lifecycle? | Neutral/secondary status |
| **Action Progress** | How far has the follow-up progressed? | Progress/stepper |
| **RCA Indication** | What is the leading engineering hypothesis? | Investigation section |
| **Evidence Strength** | How strongly does evidence support the hypothesis? | Secondary evidence indicator |
| **Forecast** | What is projected ahead? | Chart + supporting table |
| **Data Quality** | Can I rely on the supporting data/model? | Compact quality cue + technical detail |

These are different dimensions and must not be visually merged into one generic “status”.

---

# 75. What should be above the fold on Dashboard

The first screen should answer, in order:

```text
1. What needs attention?
2. What is the current condition?
3. What is the operating context?
```

The user should not need to scroll through methodology or data lineage before seeing these.

---

# 76. Dashboard ideal above-the-fold wireframe

```text
┌─────────────────────────────────────────────────────────────┐
│ [Chandra Asri logo]    Cali-INI                             │
│                        Intelligent Manufacturing             │
│                        Decision Support                      │
│ Scope: All assets · As of 03 Oct 2026, 12:00 · Data: PASS  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ ⚠ ATTENTION REQUIRED                         3 items        │
│ P1 1    P2 1    P3 1                                      │
│                                                             │
│ P1 · PU-2101B                                               │
│ High discharge pressure deviation                           │
│ ALARM · OPEN                                                │
│ Next action: Verify control response                        │
│ [ View problem ]                                            │
└─────────────────────────────────────────────────────────────┘

CURRENT PLANT CONDITION
┌────────────────┐ ┌────────────────┐ ┌────────────────────┐
│ Health         │ │ Operating      │ │ Reliability &      │
│ 16.4 / 100     │ │ 67.8 / 100     │ │ Consequence 24.8  │
└────────────────┘ └────────────────┘ └────────────────────┘

OPERATIONAL CONTEXT
Load 118.9 · Production 98.9 · Downtime 8.0 h · Emission proxy 120.2
```

This is intentionally not the same as a technical report layout.

---

# 77. Dashboard lower-page wireframe

```text
ASSET STATUS

┌──────────┬───────────┬────────┬──────────┬──────────┐
│ Asset    │ Condition │ Health │ Priority │ Forecast │
├──────────┼───────────┼────────┼──────────┼──────────┤
│ PU-2101B │ Alarm     │ 16     │ P1       │ Attention│
│ KO-3201  │ Watch     │ 54     │ P2       │ Attention│
│ PM-4405B │ Normal    │ 87     │ P4       │ —        │
└──────────┴───────────┴────────┴──────────┴──────────┘


TREND ANALYSIS

[ Condition & Reliability ] [ Operations ]

Indicator:
[ Health Score ▼ ]

                 30-day trend
             ─────────────────────
             clean analytical chart
```

---

# 78. Problems page ideal wireframe

```text
PROBLEMS
Investigate active issues, understand the likely cause,
and track follow-up actions.

PROBLEM LIST
┌──────┬──────────┬─────────────────────────┬────────┬────────┐
│ P1   │ PU-2101B │ High discharge pressure  │ Alarm  │ Open   │
└──────┴──────────┴─────────────────────────┴────────┴────────┘

────────────────────────────────────────────────────────────────

PU-2101B
High discharge pressure deviation

[ ALARM ] [ P1 ]      Ticket: OPEN      Action: IN PROGRESS

WHY IS THIS A PROBLEM?
Discharge pressure exceeded the configured engineering limit.

LIKELY CAUSE
Control valve degradation

Evidence strength: Moderate

[ View supporting evidence ]

RECOMMENDED ACTION
Verify control response.

Responsible role: Reliability / Rotating Equipment
Target response: Within 24 hours

FOLLOW-UP ACTION
[ Operator ] [ Responsible role ]
[ Decision ] [ Action progress ]
[ Field observation.....................]
[ Comment...............................]
[ Save follow-up update ]

▼ View follow-up history
```

---

# 79. Assets page ideal wireframe

```text
ASSETS

Asset
[ PU-2101B ▼ ]

PU-2101B
Condition: ALARM    Health: 16.4    Priority: P1
Latest data: 03 Oct 2026, 12:00

CURRENT PARAMETERS
┌──────────────────────┬───────────┬───────────┐
│ Parameter            │ Current   │ Condition │
├──────────────────────┼───────────┼───────────┤
│ Discharge Pressure   │ 82 bar    │ ALARM     │
│ Bearing Temperature  │ 68 °C     │ NORMAL    │
│ Overall Vibration    │ 8.2 mm/s  │ WATCH     │
└──────────────────────┴───────────┴───────────┘

Selected parameter:
[ Discharge Pressure ▼ ]

Current value: 82 bar
Condition: ALARM
Latest measured: 12:00
Data age: 1 h

TREND & FORECAST
[ 24 h ] [ 72 h ] [ 7 days ]

   historical    CURRENT       forecast
───────────────●──────────────────────────
                │       ╱╲
                │      ╱  ╲
             alarm limit
             trip limit

4-WEEK OUTLOOK
                 📈 analytical trend

▼ Forecast details
▼ Technical details
```

---

# 80. Interaction philosophy

Every interaction should answer one of these:

### Navigation

> “Where can I go next?”

### Selection

> “Which asset/problem/parameter am I investigating?”

### Tooltip

> “What does this term mean?”

### Expand

> “Why does the system say this?”

### Action button

> “What happens if I click this?”

Avoid interactions that require users to know backend terminology.

---

# 81. Exception-first principle

Use this visual priority:

```text
ABNORMAL
  ↓
VISIBLE
  ↓
ACTIONABLE

NORMAL
  ↓
VISIBLE
  ↓
QUIET
```

Normal assets are still represented, but should not overpower abnormal items.

---

# 82. Scope visibility rule

Any value that can change when `Asset scope` changes must make that scope visible.

Examples:

```text
Current Plant Condition
Scope: All assets
```

or:

```text
Current Asset Condition
Scope: PU-2101B
```

This prevents misreading an aggregate as an individual asset value.

---

# 83. Data freshness rule

Data quality should be visible close to the number it affects.

Preferred:

```text
Current value
82 bar

Measured 1 h ago · Good
```

rather than forcing the user to visit a separate quality page.

Detailed provenance still belongs in Technical Details.

---

# 84. Forecast interpretation rule

Always visually distinguish:

```text
MEASURED
CURRENT
FORECAST
UNCERTAINTY
LIMIT
```

The graph should make it obvious where historical measurement ends and forecast begins.

The current analysis/reference timestamp should be marked clearly.

Do not let forecast look like measured history.

---

# 85. Metric explanation rule

Every derived metric that can reasonably be misunderstood should have:

1. Plain-language title.
2. One-sentence tooltip.
3. Baseline/reference statement when applicable.
4. “Proxy” terminology where the data is not a direct measurement.

Examples:

```text
Production Index
≈ 100 = healthy-running reference
```

```text
Emission Intensity Proxy
Relative electricity-related proxy, not direct emissions measurement
```

---

# 86. Methodology placement rule

The current calculation-basis information is useful but should not dominate the dashboard.

Preferred hierarchy:

```text
Metric
  ↓
Tooltip
  ↓
Methodology expander
  ↓
Technical Details
```

Never put a large calculation table between the user and the problem/condition they are trying to understand.

---

# 87. RCA wording rule

Never display a hypothesis as an unquestionable diagnosis.

Preferred:

> **Likely Cause**

or:

> **Root-cause indication**

Then:

> “This is a ranked engineering hypothesis based on current evidence and similar historical incidents.”

Avoid:

> “Root cause: X”

unless X has actually been verified by the operational workflow.

---

# 88. Action workflow rule

Action status should look like a process:

```text
Acknowledged
     ↓
In Progress
     ↓
Pending Verification
     ↓
Completed
```

But in this UI-only redesign, these visual states must continue to reflect the **existing engine state**. Do not add or silently change transition rules.

---

# 89. Ticket lifecycle rule

Ticket status is not the same as action progress.

Example:

```text
Equipment condition:
ALARM

Ticket:
OPEN

Action:
IN PROGRESS
```

This combination is valid and should not be collapsed into a single “status”.

---

# 90. Technical disclosure rule

Technical details should be available, not absent.

Recommended pattern:

```text
Visible summary
       ↓
[ View evidence ]
       ↓
Supporting technical detail
```

Examples:

- View supporting evidence
- View follow-up history
- View technical details
- View model details

---

# 91. Final quality checklist

Before implementation is considered complete:

## Information architecture

- [ ] Four main areas are clear: Dashboard / Problems / Assets / Technical Details.
- [ ] Forecast no longer requires a separate top-level workflow.
- [ ] RCA no longer requires a separate top-level workflow.
- [ ] Technical quality content is available without interrupting the operational flow.

## Dashboard

- [ ] Attention Required appears before technical analytics.
- [ ] Current scope is visible.
- [ ] Core Condition KPIs are visually stronger than operational context.
- [ ] Asset Status is concise.
- [ ] Trend Analysis is grouped logically.
- [ ] Normal assets do not crowd out abnormal issues.
- [ ] Calculation/source details are not first-glance content.

## Problems

- [ ] Problem list is easy to scan.
- [ ] Condition and priority are prominent.
- [ ] Ticket and action status remain distinct.
- [ ] Trigger explanation is concise.
- [ ] RCA is explicitly a hypothesis.
- [ ] Evidence is collapsible.
- [ ] Recommended action is prominent.
- [ ] Ownership and SLA are easy to find.
- [ ] Follow-up remains on the problem page.
- [ ] History is available but collapsed.

## Assets

- [ ] Current asset summary is immediate.
- [ ] Parameter list is concise.
- [ ] Current parameter value and condition are clear.
- [ ] Historical and forecast values are visually distinguishable.
- [ ] Current point is clearly marked.
- [ ] Alarm/trip limits are visible where relevant.
- [ ] Forecast horizon is easy to change.
- [ ] Weekly outlook is visual.
- [ ] Model metrics are secondary.

## Visual design

- [ ] Chandra Asri logo is not distorted.
- [ ] Corporate blue/cyan palette is coherent.
- [ ] Status colors are semantic.
- [ ] Cards are clean and restrained.
- [ ] Charts are analytical rather than decorative.
- [ ] Typography has clear hierarchy.
- [ ] Technical UI does not look like a generic marketing SaaS dashboard.

## Engine safety

- [ ] No analytical formula changes.
- [ ] No condition-state logic changes.
- [ ] No priority-matrix changes.
- [ ] No RCA logic changes.
- [ ] No forecast logic changes.
- [ ] No ticket-transition changes.
- [ ] No action-history persistence changes.
- [ ] No data-quality validation logic changes.

---

# 92. Final one-page design philosophy

```text
                    CALI-INI
                       │
                CURRENT SNAPSHOT
              Scope + Time + Status
                       │
                       ▼
              ⚠ WHAT NEEDS ATTENTION?
                       │
                       ▼
              HOW IS THE PLANT NOW?
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
      CONDITION                OPERATIONS
          │                         │
          └────────────┬────────────┘
                       ▼
                WHICH ASSET?
                       │
             ┌─────────┴──────────┐
             ▼                    ▼
          NO ISSUE              ISSUE
             │                    │
             ▼                    ▼
          ASSET                PROBLEM
          DETAIL               DETAIL
             │                    │
             ▼                    ▼
     PARAMETER → FORECAST     RCA → ACTION
                                  ↓
                              FOLLOW-UP
                                  ↓
                                HISTORY
```

> **The best UI is not the one that shows the most information. It is the one that reveals the right information at the right moment while keeping the complete technical evidence available when needed.**

---

# 93. Visual asset references

Place these files beside the master specification during implementation:

- `Cali_INI_logo_reference.png` — supplied Chandra Asri logo.
- `Cali_INI_visual_reference.png` — supplied Selection Process visual used as the main visual/color reference.

Recommended project arrangement:

```text
project/
├── app.py
├── intelligence_engine.py
├── Cali_INI_Master_UI_Design_Spec.md
├── Cali_INI_logo_reference.png
└── Cali_INI_visual_reference.png
```

---

# 94. End state

The intended result is a Cali-INI interface that is:

**Clear**
→ users understand the purpose of each section.

**Attractive**
→ corporate blue/cyan visual language, clean white surfaces, restrained semantic status colors.

**Operational**
→ abnormal conditions and actions are easy to identify.

**Traceable**
→ RCA evidence, provenance, quality, and model details remain available.

**Faithful**
→ existing analytical logic and outputs are preserved.

