\# CALI-INI — Frontend Menu, Form, and Data View Specification



\## 1. Tujuan



Dokumen ini menjadi panduan implementasi frontend CALI-INI untuk menu di luar Dashboard.



Target arsitektur:



```text

Vue Frontend

&#x20;     ↓

FastAPI Backend

&#x20;     ↓

PostgreSQL

&#x20;     ↓

Data Adapter

&#x20;     ↓

intelligence\_engine.py

```



Prinsip utama:



1\. Frontend tidak mengikuti struktur tabel database secara mentah.

2\. UI mengikuti workflow pengguna.

3\. Data source spreadsheet lama harus tetap dapat direpresentasikan.

4\. Data yang dapat diturunkan otomatis tidak perlu diminta ulang dari user.

5\. Analytical output dari `intelligence\_engine.py` tidak boleh diinput manual.

6\. Historical Incident/RCA merupakan knowledge base.

7\. Problem Verification merupakan human verification terhadap analytical/RCA hypothesis dari engine.

8\. Weekly measurement bukan input manual; weekly data merupakan hasil derivasi dari hourly measurement.

9\. Detail algoritma derivasi hourly → weekly harus mengikuti backend/engine dan tidak diimplementasikan di Vue.

10\. Audit/history ditampilkan secara kontekstual dan tidak perlu menjadi menu utama.



\---



\# 2. Struktur Menu Final



```text

CALI-INI

│

├── Dashboard

│

├── Operations

│   ├── Data Input

│   └── Problem Verification

│

├── Reliability

│   ├── Incident Register

│   └── CAPA Tracking              \[optional]

│

├── Asset Management

│   ├── Assets

│   ├── Sensor \& Parameters

│   └── Equipment Limits

│

└── Administration

&#x20;   └── Users

```



`CAPA Tracking` hanya diperlukan apabila user membutuhkan monitoring CAPA lintas incident.



CAPA tetap dibuat dari dalam Incident Workspace.



\---



\# 3. Operations — Data Input



\## 3.1 Tujuan



Halaman ini digunakan untuk memasukkan data operasional hourly yang menjadi salah satu input utama analytical engine.



Source spreadsheet sebelumnya:



```text

<ASSET> Production Data Hourly

```



Contoh struktur source:



| Timestamp | KO3201\_FEED | KO3201\_DISP | KO3201\_VIB | KO3201\_TEMP | KO3201\_AMP | PLANT\_RATE | RUN\_STATUS |

|---|---|---|---|---|---|---|---|



Weekly measurement tidak mempunyai form manual.



Flow:



```text

User / Integration

&#x20;      ↓

Hourly Measurement

&#x20;      ↓

PostgreSQL

&#x20;      ↓

Weekly Derivation / Engineering Processing

&#x20;      ↓

Weekly Measurement

&#x20;      ↓

intelligence\_engine.py

```



\---



\## 3.2 Main Table View



Tampilkan:



| Column | Description |

|---|---|

| Timestamp | Waktu measurement |

| Asset | Equipment tag |

| FEED | Feed value |

| DISP | Discharge-related value |

| VIB | Vibration |

| TEMP | Temperature |

| AMP | Motor current |

| Plant Rate | Plant operating rate |

| Run Status | ON/OFF/etc. |

| Source | Manual / Upload / Integration |



Filter:



```text

Asset

Date From

Date To

Run Status

Source

```



Primary action:



```text

\[ + Input Data ]

```



Secondary action:



```text

\[ Upload Data ]

```



Upload bukan menu tersendiri.



\---



\# 4. Operational Data Form



Form:



```text

Asset \*

Timestamp \*



Operating Parameters

────────────────────────────

FEED

DISP

VIB

TEMP

AMP

Plant Rate



Run Status \*

```



Contoh:



```text

Asset                   \[ KO-3201 ▼ ]

Timestamp               \[ 2026-10-03 14:00 ]



FEED                     \[          ]

DISP                     \[          ]

VIB                      \[          ]

TEMP                     \[          ]

AMP                      \[          ]

Plant Rate               \[          ]



Run Status               \[ ON ▼ ]



\[ Cancel ]                         \[ Save Data ]

```



Unit parameter harus diperoleh dari Sensor \& Parameter configuration jika tersedia.



Jangan hard-code unit di Vue.



\---



\# 5. Operational Bulk Upload



Bulk upload hanya merupakan metode lain untuk memasukkan operational measurement.



Flow:



```text

Upload File

&#x20;   ↓

Detect Columns

&#x20;   ↓

Column Mapping

&#x20;   ↓

Validation

&#x20;   ↓

Preview

&#x20;   ↓

Confirm

&#x20;   ↓

Insert

```



UI harus menampilkan:



```text

Rows detected

Valid rows

Warning rows

Invalid rows

```



Invalid row tidak boleh dimasukkan diam-diam.



Scope bulk upload awal cukup untuk operational/hourly data.



Jangan membuat generic Excel importer untuk seluruh database pada tahap awal.



\---



\# 6. Weekly Measurement



Source lama:



```text

<ASSET> Performance Weekly

```



Contoh:



| Week | Date | DE Radial Vibration (micron) | Lube Oil Water Content (ppm) | Lube Oil Supply Press (barg) | Bearing Metal Temp (°C) | Health Status | Remark |

|---|---|---|---|---|---|---|---|



Pada arsitektur baru:



> Weekly measurement merupakan derived/system-generated data dari hourly measurement dan proses backend.



Karena itu:



```text

NO manual Weekly Input menu

NO user Weekly Measurement form

```



Weekly data tetap dapat ditampilkan sebagai analytical/engineering information apabila dibutuhkan.



Vue tidak boleh menghitung weekly engineering measurement sendiri.



\---



\# 7. Operations — Problem Verification



\## 7.1 Konsep



Problem Verification adalah human-in-the-loop workflow.



Flow:



```text

Hourly / Derived Data

&#x20;       ↓

intelligence\_engine.py

&#x20;       ↓

Condition Analysis

&#x20;       ↓

WATCH / ALARM / TRIP

&#x20;       ↓

Historical RCA Matching

&#x20;       ↓

RCA Hypothesis

&#x20;       ↓

Problem Ticket

&#x20;       ↓

Problem Verification

&#x20;       ↓

Human Field Verification

```



User tidak membuat analytical problem secara manual.



User melakukan verifikasi terhadap hasil engine.



\---



\# 8. Problem Verification — Table View



Columns:



| Column |

|---|

| Problem ID |

| Asset |

| Condition |

| Priority |

| RCA Indication |

| Evidence Strength |

| Ticket State |

| Action Status |

| Responsible Role |

| Last Seen |



Filters:



```text

Asset

Condition

Priority

Ticket State

Action Status



\[ ] Requires Attention Only

```



Klik row membuka Problem Workspace.



\---



\# 9. Problem Workspace



Structure:



```text

Problem Workspace



\[ Verification ]

\[ Evidence \& RCA ]

\[ History ]

```



Header:



```text

Problem ID

Asset

Condition

Priority

Ticket State

Action Status

```



\---



\# 10. Problem — Verification



Engine information bersifat read-only:



```text

Current Condition

Problem Trigger

Priority

Probable RCA

Evidence Strength

Recommended Action

Suggested Responsible Role

Target Response

```



Human input:



```text

Operator / Reviewer



Visible Leakage

Abnormal Noise

Abnormal Vibration

Local Temperature Confirmed



Field Observation



Operator Decision

Responsible Role

Action Status



Comment

```



Verification options:



```text

YES

NO

N/A

```



Operator Decision:



```text

NO\_DECISION\_CHANGE

ACKNOWLEDGE

CONFIRM\_RCA\_HYPOTHESIS

REJECT\_RCA\_HYPOTHESIS

REQUEST\_ENGINEERING\_REVIEW

REQUEST\_TICKET\_CLOSURE

```



Action Status:



```text

NOT\_STARTED

ACKNOWLEDGED

IN\_PROGRESS

PENDING\_VERIFICATION

COMPLETED

```



User tidak boleh mengedit:



```text

Condition

Priority hasil engine

Similarity score

Evidence-strength calculation

Forecast

Health score

```



\---



\# 11. Problem — Evidence \& RCA



Tampilkan read-only:



```text

Root Cause Hypothesis

Evidence Strength



Current Supporting Evidence



Historical Analogue

AR No.

Historical Incident Title

Case Similarity



Historically Verified Evidence



4P Evidence

4M Evidence

Historical CAPA Reference

```



Jika historical analogue mempunyai AR No., sediakan:



```text

\[ View Historical Incident \& RCA ]

```



Action tersebut membuka Incident Workspace.



Dengan demikian:



```text

Current Problem

&#x20;     ↓

Historical Analogue

&#x20;     ↓

Incident Register

&#x20;     ↓

Historical RCA

```



\---



\# 12. Problem — History



Gunakan timeline.



Contoh:



```text

03 Oct 2026 14:42

Operator REL-05

RCA hypothesis confirmed

Action status → IN\_PROGRESS



03 Oct 2026 13:20

SYSTEM

Problem detected

Condition → ALARM

Priority → P1

```



History read-only.



\---



\# 13. Reliability — Incident Register



\## 13.1 Tujuan



Incident Register merupakan historical reliability knowledge base.



Source:



```text

Incident Record

```



Source memiliki field:



```text

Serial No

MTO No.

AR No.

Plant

Tag Number

Eq. Class

Date of Occurrence

Risk Case Title

Highest Impact

Pre-Risk

Risk Score

PIC RCA

Overall Status

Discipline

Eq. Type

Component

Failure Mechanism

Downtime Hours

Actual Loss

Potential Loss

Total Loss

RCA Due Date

Month-Year

```



\---



\# 14. Incident Register — Table View



Jangan tampilkan seluruh field sebagai column.



Gunakan:



| Column |

|---|

| AR No. |

| Occurrence Date |

| Plant |

| Asset / Tag |

| Risk Case Title |

| Highest Impact |

| Risk Score |

| Overall Status |

| PIC RCA |

| RCA Due Date |



Search:



```text

AR No

MTO No

Tag Number

Risk Case Title

```



Filters:



```text

Plant

Asset

Equipment Class

Discipline

Equipment Type

Highest Impact

Pre-Risk

Overall Status

PIC RCA

Occurrence Date From / To

RCA Due Status

```



Primary action:



```text

\[ + New Incident ]

```



\---



\# 15. New Incident Form



Jangan membuat 23 field flat.



Gunakan section.



\## 15.1 Case Identification



Fields:



```text

Serial No

MTO No.

AR No.

Plant

Asset / Tag

Date of Occurrence

```



Recommended behavior:



`Serial No`:



```text

auto-generated / read-only

```



`Asset / Tag`:



```text

dropdown dari Asset Master

```



Setelah asset dipilih:



```text

Plant

Equipment Class

Equipment Type

Discipline

```



di-autofill dari Asset Master jika tersedia.



Namun nilai tersebut harus dapat disimpan sebagai historical incident snapshot apabila schema backend mendukungnya.



\---



\# 16. Incident Classification



Fields:



```text

Risk Case Title

Equipment Class

Discipline

Equipment Type

Component

Failure Mechanism

```



Equipment Class, Discipline, dan Equipment Type dapat berasal dari Asset Master.



Example:



```text

Asset                KO-3201



Equipment Class      A

Discipline           ROT

Equipment Type       CO



Component            \[ Journal Bearing ]

Failure Mechanism    \[ High ]

```



\---



\# 17. Risk Assessment



Fields:



```text

Highest Impact

Pre-Risk

Risk Score

```



Example:



```text

Highest Impact       \[ Class A Eq. Breakdown ▼ ]

Pre-Risk             \[ II ▼ ]

Risk Score           \[ 4000 ]

```



Allowed values jangan diasumsikan oleh frontend.



Ambil dari backend/configuration atau existing source values.



\---



\# 18. Business Impact



Fields:



```text

Downtime Hours

Actual Loss (k US$)

Potential Loss (k US$)

Total Loss (k US$)

```



Contoh:



```text

Downtime             \[ 32      ] hrs

Actual Loss          \[ 1584    ] k US$

Potential Loss       \[ 475.20  ] k US$

Total Loss           \[ 2059.20 ] k US$

```



Current source menunjukkan:



```text

Total Loss = Actual Loss + Potential Loss

```



Namun backend business rule harus menjadi source of truth.



Frontend boleh menampilkan calculated suggestion tetapi jangan mengunci formula tanpa business-rule confirmation.



\---



\# 19. RCA Administration



Fields:



```text

PIC RCA

Overall Status

RCA Due Date

```



`Month-Year` tidak perlu menjadi input user.



Derive dari:



```text

Date of Occurrence

```



Contoh:



```text

2026-03-12

&#x20;  ↓

Mar-2026

```



Jika hanya digunakan untuk reporting, tidak perlu disimpan sebagai independent editable field.



\---



\# 20. Incident Workspace



Setelah incident dibuat:



```text

AR-2026-ZCU-0142



Cracked Gas Compressor KO-3201

High Radial Vibration Trip



\[ Incident ]

\[ RCA Investigation ]

\[ CAPA ]

\[ History ]

```



\---



\# 21. Incident Tab



Default read-only.



Display groups:



```text

CASE IDENTIFICATION



Serial No

MTO No.

AR No.

Plant

Asset

Occurrence Date

```



```text

CLASSIFICATION



Risk Case Title

Equipment Class

Discipline

Equipment Type

Component

Failure Mechanism

```



```text

RISK



Highest Impact

Pre-Risk

Risk Score

```



```text

BUSINESS IMPACT



Downtime

Actual Loss

Potential Loss

Total Loss

```



```text

RCA MANAGEMENT



PIC RCA

Overall Status

RCA Due Date

```



Action:



```text

\[ Edit Incident ]

```



\---



\# 22. RCA Investigation



Source data:



```text

RCA Header

RCA Priority Matrix

RCA 4P Verification

RCA 4M Verification

```



UI:



```text

RCA Investigation



\[ Overview ]

\[ Root Causes ]

\[ Verification ]

```



Jangan membuat empat sidebar menu.



\---



\# 23. RCA Investigation — Overview



Source: `RCA Header`.



Source fields:



```text

AR No.

Tag Number

Plant

Date Occurrence

Pre Risk

Risk Score

PIC RCA

Procedure No.

Problem Statement

Root Cause Statement

```



Fields berikut sudah tersedia dari Incident dan ditampilkan read-only:



```text

AR No.

Tag Number

Plant

Date Occurrence

Pre Risk

Risk Score

```



Editable RCA fields:



```text

PIC RCA

Procedure No.

Problem Statement

Root Cause Statement

```



Example:



```text

Procedure No.

\[ RCA-P-0050-03 ]



Problem Statement

\[...........................................]



Root Cause Statement

\[...........................................]



\[ Save RCA ]

```



Jangan meminta user menginput ulang incident context.



\---



\# 24. RCA Investigation — Root Causes



Source:



```text

RCA Priority Matrix

```



Source columns:



```text

AR No.

Root Cause ID

Impact Level

Control Level

Priority Rank

Description (Short)

```



Table:



| Root Cause ID | Description | Impact Level | Control Level | Priority Rank | Action |

|---|---|---|---|---|---|



Example:



```text

P2

Suction pressure below NPSH margin

Impact: High

Control: High

Priority: 1

```



Actions:



```text

\[ + Add Root Cause ]

\[ Edit ]

\[ Delete ]

```



Create/Edit form:



```text

Root Cause ID

Description

Impact Level

Control Level

Priority Rank

```



AR No. otomatis berasal dari current Incident Workspace.



\---



\# 25. RCA Investigation — Verification



Gabungkan 4P dan 4M dalam satu screen.



Structure:



```text

VERIFICATION



4P Verification

────────────────────────



4M Verification

────────────────────────

```



\---



\# 26. 4P Verification



Source:



```text

RCA 4P Verification

```



Source fields:



```text

AR No.

Parameter ID

Problem Phenomenon Parameter

Result

Evidence Finding

```



Table:



| Parameter ID | Problem / Phenomenon | Result | Evidence Finding | Action |

|---|---|---|---|---|



Form:



```text

Parameter ID

Problem / Phenomenon Parameter

Result

Evidence Finding

```



Example:



```text

Parameter ID

P2



Problem / Phenomenon

Suction pressure below NPSH margin



Result

NG



Evidence

Suction pressure dropped during feed swing...

```



Do not reinterpret `G` / `NG` without backend/domain definition.



Preserve source-compatible values.



\---



\# 27. 4M Verification



Source:



```text

RCA 4M Verification

```



Source fields:



```text

AR No.

Factor ID

Factor Category

Result

Evidence Finding

```



Table:



| Factor ID | Factor Category | Result | Evidence Finding | Action |

|---|---|---|---|---|



Important:



Current source examples show `Factor Category` values such as:



```text

No low-NPSH / flush-flow interlock in DCS

Feed-swing SOP allows fast rate ramp

```



Therefore frontend \*\*must not assume\*\* that the source column `Factor Category` only contains:



```text

MAN

MACHINE

METHOD

MATERIAL

```



until source semantics/schema are clarified.



Preserve the actual source data.



Form baseline:



```text

Factor ID

Factor Category

Result

Evidence Finding

```



\---



\# 28. CAPA



Source:



```text

RCA CAPA Actions

```



Current source fields:



```text

Action Plan

Target Date

PIC

Status

```



CAPA belongs to the current Incident/RCA Workspace.



Table:



| Action Plan | Target Date | PIC | Status | Action |

|---|---|---|---|---|



Example:



```text

Install seal-flush flow switch with DCS alarm on PU-2101B

Target: 24 Apr 2026

PIC: REL-05

Status: In Progress

```



Form:



```text

Action Plan \*

Target Date

PIC

Status

```



Do not require fields that do not exist in the current source, such as `Action Type` or `Root Cause ID`, unless database/business requirements explicitly add them.



This is important for source-data parity.



\---



\# 29. CAPA Tracking — Optional



Jika diperlukan, sediakan cross-incident view:



| AR No | Asset | Action Plan | PIC | Target Date | Status |

|---|---|---|---|---|---|



Filters:



```text

Asset

Plant

PIC

Status

Target Date



\[ ] Overdue Only

```



CAPA creation tetap dilakukan dari Incident Workspace.



\---



\# 30. Asset Management — Assets



Source:



```text

<ASSET> Metadata

```



Current source fields:



```text

Equipment Tag

Equipment Name

Equipment Type

Equipment Class

Plant / Unit

Discipline

Criticality

Design Life

Monitoring Method

Linked RCA / AR No.

Failure Date

Dominant Failure Mode

```



\---



\# 31. Assets — Table View



Columns:



| Column |

|---|

| Equipment Tag |

| Equipment Name |

| Plant / Unit |

| Equipment Type |

| Equipment Class |

| Discipline |

| Criticality |

| Monitoring Method |

| Status |



Filters:



```text

Search

Plant / Unit

Equipment Type

Equipment Class

Discipline

Criticality

Status

```



Primary action:



```text

\[ + Add Asset ]

```



\---



\# 32. Asset Workspace



Use:



```text

Asset Workspace



\[ General ]

\[ Reliability Context ]

```



Metadata tidak perlu menjadi sidebar menu terpisah.



\---



\# 33. Asset — General



Form/display:



```text

Equipment Tag \*

Equipment Name \*

Equipment Type \*

Equipment Class

Plant / Unit \*

Discipline

Criticality

Design Life

Monitoring Method

```



Example:



```text

Equipment Tag

KO-3201



Equipment Name

Cracked Gas Compressor KO-3201



Equipment Type

Centrifugal Compressor



Equipment Class

A



Plant / Unit

Cracker Unit (ZCU)



Discipline

ROT



Criticality

High



Design Life

5 years (bearing) / 24 months (seal element)



Monitoring Method

Online DCS + monthly vibration/thermography route

```



Do not drop `Design Life` or `Monitoring Method`.



\---



\# 34. Asset — Reliability Context



Source metadata contains:



```text

Linked RCA / AR No.

Failure Date

Dominant Failure Mode

```



Display:



```text

Linked Historical RCA

AR-2026-ZCU-0142



Failure Date

29 Apr 2026



Dominant Failure Mode

High Radial Vibration Trip (Bearing Distress)

```



If Linked RCA exists:



```text

\[ View Incident \& RCA ]

```



Recommended design:



Historical incident/RCA database should eventually become source of truth for this information.



Until migration/business rules are finalized, preserve the source metadata fields so no source information is lost.



\---



\# 35. Asset Management — Sensor \& Parameters



Source:



```text

<ASSET> Tag Dictionary

```



Source columns:



```text

PI Tag

Name

Description

digitalset

engunits

span

typicalvalue

zero

instrumenttag

```



Table:



| PI Tag | Name | Unit | Span | Typical Value | Instrument Tag | Action |

|---|---|---|---|---|---|---|



Asset is selected/filter context.



Form must preserve:



```text

PI Tag \*

Name

Description

Digital Set

Engineering Units

Span

Typical Value

Zero

Instrument Tag

```



If backend adds canonical parameter mapping such as:



```text

FEED

DISP

VIB

TEMP

AMP

```



display it as an additional system mapping field.



Do not replace/drop original source fields.



\---



\# 36. Asset Management — Equipment Limits



Source:



```text

<ASSET> Equipment Limits

```



Source columns:



```text

Parameter

Unit

Alarm Limit

Trip Limit

```



UI should use editable matrix.



Example:



```text

Asset: KO-3201



Parameter                    Unit      Alarm       Trip

──────────────────────────────────────────────────────

DE Radial Vibration         micron    \[ ... ]     \[ ... ]

Bearing Metal Temperature   °C        \[ ... ]     \[ ... ]



\[ + Add Limit ]                         \[ Save Changes ]

```



Fields:



```text

Parameter \*

Unit

Alarm Limit

Trip Limit

```



Changing limits may influence future analytical condition evaluation.



Require confirmation before save.



\---



\# 37. Administration — Users



Administration initial scope only contains:



```text

Users

```



Table:



| Name | Username / Email | Role | Status | Last Login |

|---|---|---|---|---|



Filters:



```text

Search

Role

Status

```



Form:



```text

Full Name \*

Username / Email \*

Role \*

Status \*

```



Authentication/password mechanism must not be invented by frontend implementation.



Wait for authentication architecture decision.



\---



\# 38. Source-to-Frontend Mapping



| Source Sheet | Frontend |

|---|---|

| `<ASSET> Metadata` | Asset Management → Assets |

| `<ASSET> Production Data Hourly` | Operations → Data Input |

| `<ASSET> Performance Weekly` | System-derived; no manual input |

| `<ASSET> Tag Dictionary` | Asset Management → Sensor \& Parameters |

| `<ASSET> Equipment Limits` | Asset Management → Equipment Limits |

| `Incident Record` | Reliability → Incident Register |

| `RCA Header` | Incident Workspace → RCA Investigation → Overview |

| `RCA Priority Matrix` | Incident Workspace → RCA Investigation → Root Causes |

| `RCA 4P Verification` | Incident Workspace → RCA Investigation → Verification |

| `RCA 4M Verification` | Incident Workspace → RCA Investigation → Verification |

| `RCA CAPA Actions` | Incident Workspace → CAPA |



Workflow generated by engine:



| Engine / Workflow Data | Frontend |

|---|---|

| Problem Tickets | Operations → Problem Verification |

| Operator Confirmation | Problem Workspace → Verification |

| Problem/Action History | Problem Workspace → History |

| Historical RCA Match | Problem Workspace → Evidence \& RCA |



\---



\# 39. Final UX Structure



```text

Dashboard



Operations

│

├── Data Input

│   ├── Measurement Table

│   ├── Manual Input

│   └── Bulk Upload

│

└── Problem Verification

&#x20;   ├── Problem List

&#x20;   └── Problem Workspace

&#x20;       ├── Verification

&#x20;       ├── Evidence \& RCA

&#x20;       └── History



Reliability

│

├── Incident Register

│   ├── Incident List

│   ├── New Incident

│   └── Incident Workspace

│       ├── Incident

│       ├── RCA Investigation

│       │   ├── Overview

│       │   ├── Root Causes

│       │   └── Verification

│       │       ├── 4P

│       │       └── 4M

│       ├── CAPA

│       └── History

│

└── CAPA Tracking \[optional]



Asset Management

│

├── Assets

│   └── Asset Workspace

│       ├── General

│       └── Reliability Context

│

├── Sensor \& Parameters

└── Equipment Limits



Administration

└── Users

```



\---



\# 40. Important Frontend Rules



\## Do not expose database architecture directly



Bad:



```text

RCA Header

RCA 4P Table

RCA 4M Table

Asset Metadata Table

```



as sidebar items.



Good:



```text

Incident Workspace

RCA Investigation

Asset Workspace

```



\---



\## Do not ask for duplicate data



If Asset is selected, reuse:



```text

Plant

Equipment Type

Equipment Class

Discipline

Criticality

```



where appropriate.



For historical Incident records, backend may save these as snapshots.



\---



\## Do not ask users to input derived values



Examples:



```text

Month-Year

Weekly derived measurement

Analysis reference time

Forecast result

Health score

RCA similarity

Evidence strength

```



\---



\## Preserve source data



Fields from the spreadsheet must not silently disappear merely because the new normalized model has a cleaner structure.



If a source field is being deprecated or derived, explicitly map it to:



```text

master data

derived field

historical snapshot

system-generated field

or legacy-preserved field

```



\---



\# 41. Key Relationship Between Reliability and Problem Verification



Do not confuse these two workflows.



\## Reliability



Represents historical/formal engineering knowledge:



```text

Incident

&#x20;  ↓

Formal RCA

&#x20;  ↓

Root Cause Verification

&#x20;  ↓

CAPA

&#x20;  ↓

Historical Knowledge Base

```



\## Problem Verification



Represents current operational decision support:



```text

Current Measurements

&#x20;      ↓

intelligence\_engine.py

&#x20;      ↓

Condition Detection

&#x20;      ↓

Historical Similarity

&#x20;      ↓

RCA Hypothesis

&#x20;      ↓

Operator Verification

```



Connection:



```text

CURRENT PROBLEM

&#x20;     │

&#x20;     │ matched with

&#x20;     ▼

HISTORICAL INCIDENT / RCA

&#x20;     │

&#x20;     ▼

RCA HYPOTHESIS

&#x20;     │

&#x20;     ▼

FIELD VERIFICATION

```



Historical Incident/RCA therefore supplies knowledge to the analytical engine, while Problem Verification captures human response to the engine's current analytical conclusion.



\---



\# 42. Implementation Principle



Use this principle throughout frontend development:



> Users input observations, configuration, incident facts, engineering findings, and human decisions. The analytical engine produces analytical conclusions.



Vue is responsible for presentation and user interaction.



FastAPI is responsible for validation, authorization, orchestration, and data contracts.



PostgreSQL is the system of record.



`intelligence\_engine.py` remains responsible for analytical logic.



If frontend data shape and engine data shape differ, resolve the difference in backend service/data-adapter layers rather than duplicating analytical logic in Vue.

