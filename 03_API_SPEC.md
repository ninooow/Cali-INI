\# CALI-INI — Backend API Specification



\## 1. Tujuan



Dokumen ini mendefinisikan kontrak REST API antara:



```text

Vue Frontend

&#x20;    │

&#x20;    │ HTTP / JSON

&#x20;    ▼

FastAPI Backend

&#x20;    │

&#x20;    ├── Service Layer

&#x20;    ├── Repository Layer

&#x20;    ├── PostgreSQL

&#x20;    └── Intelligence Service

```



API menjadi satu-satunya application interface yang digunakan Vue.



Frontend tidak boleh:



\- mengakses PostgreSQL secara langsung;

\- membaca spreadsheet;

\- membaca workflow CSV;

\- menjalankan `intelligence\_engine.py`;

\- menghitung analytical condition;

\- menghitung forecast;

\- melakukan RCA matching.



\---



\# 2. Base URL



Seluruh endpoint menggunakan prefix:



```text

/api/v1

```



Contoh:



```text

GET /api/v1/assets

GET /api/v1/problems

GET /api/v1/analytics/dashboard

```



\---



\# 3. API Domain



Endpoint dibagi menjadi:



```text

/api/v1/

│

├── assets/

├── telemetry/

├── reliability/

├── problems/

├── analytics/

└── users/

```



Hubungan konseptual:



```text

Assets

&#x20;  │

&#x20;  ├── configuration

&#x20;  ├── tags

&#x20;  └── limits



Telemetry

&#x20;  │

&#x20;  ├── hourly input

&#x20;  └── weekly derived data



Reliability

&#x20;  │

&#x20;  ├── incidents

&#x20;  ├── RCA

&#x20;  ├── 4P

&#x20;  ├── 4M

&#x20;  ├── priority matrix

&#x20;  └── CAPA



Problems

&#x20;  │

&#x20;  ├── engine-generated problem context

&#x20;  ├── operator verification

&#x20;  └── workflow history



Analytics

&#x20;  │

&#x20;  ├── analysis run

&#x20;  ├── dashboard result

&#x20;  ├── condition

&#x20;  ├── forecast

&#x20;  └── current RCA match



Users

&#x20;  │

&#x20;  └── user administration

```



\---



\# 4. General Response Convention



Successful single-resource response:



```json

{

&#x20; "data": {}

}

```



Collection:



```json

{

&#x20; "data": \[],

&#x20; "meta": {

&#x20;   "page": 1,

&#x20;   "page\_size": 25,

&#x20;   "total": 100

&#x20; }

}

```



Error:



```json

{

&#x20; "error": {

&#x20;   "code": "VALIDATION\_ERROR",

&#x20;   "message": "Request validation failed.",

&#x20;   "details": \[]

&#x20; }

}

```



\---



\# 5. General HTTP Status



Gunakan:



```text

200 OK

201 Created

202 Accepted

204 No Content



400 Bad Request

401 Unauthorized

403 Forbidden

404 Not Found

409 Conflict

422 Unprocessable Entity

500 Internal Server Error

```



Analytical engine failure tidak boleh dikembalikan seolah-olah validation error.



\---



\# 6. Pagination



Endpoint collection mendukung:



```text

?page=1

\&page\_size=25

```



Default:



```text

page = 1

page\_size = 25

```



Backend menetapkan maximum page size yang wajar.



Frontend tidak mengambil seluruh historical telemetry sekaligus tanpa kebutuhan.



\---



\# 7. Sorting



Collection yang membutuhkan sorting menggunakan:



```text

?sort=measured\_at

\&order=desc

```



Allowed sorting fields harus didefinisikan oleh endpoint.



Jangan meneruskan nama column arbitrary langsung menjadi SQL.



\---



\# 8. Assets API



\## 8.1 List Assets



```text

GET /api/v1/assets

```



Optional filters:



```text

?search=KO

?plant=ZCU

?equipment\_type=Centrifugal Compressor

?criticality=High

?is\_active=true

```



Response minimal:



```json

{

&#x20; "data": \[

&#x20;   {

&#x20;     "asset\_id": "KO-3201",

&#x20;     "tag\_number": "KO-3201",

&#x20;     "asset\_name": "Cracked Gas Compressor KO-3201",

&#x20;     "equipment\_type": "Centrifugal Compressor",

&#x20;     "equipment\_class": "A",

&#x20;     "plant": "ZCU",

&#x20;     "discipline": "ROT",

&#x20;     "criticality": "High",

&#x20;     "is\_active": true

&#x20;   }

&#x20; ]

}

```



\---



\## 8.2 Asset Detail



```text

GET /api/v1/assets/{asset\_id}

```



Mengembalikan master asset dan metadata.



\---



\## 8.3 Create Asset



```text

POST /api/v1/assets

```



Digunakan oleh Asset Management.



Request mengikuti database asset master dan metadata specification.



\---



\## 8.4 Update Asset



```text

PATCH /api/v1/assets/{asset\_id}

```



Tidak boleh mengubah historical analytical result.



\---



\# 9. Asset Metadata API



```text

GET /api/v1/assets/{asset\_id}/metadata

PUT /api/v1/assets/{asset\_id}/metadata

```



Metadata mendukung data seperti:



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



Field yang sudah menjadi typed column pada asset master tidak perlu diduplikasi secara fisik hanya demi response API.



Service/serializer dapat membentuk representation frontend.



\---



\# 10. Sensor Tag API



\## List



```text

GET /api/v1/assets/{asset\_id}/tags

```



\## Create



```text

POST /api/v1/assets/{asset\_id}/tags

```



\## Update



```text

PATCH /api/v1/assets/{asset\_id}/tags/{tag\_id}

```



\## Delete



```text

DELETE /api/v1/assets/{asset\_id}/tags/{tag\_id}

```



Data mencakup source Tag Dictionary:



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



\---



\# 11. Equipment Limits API



\## List



```text

GET /api/v1/assets/{asset\_id}/limits

```



\## Create



```text

POST /api/v1/assets/{asset\_id}/limits

```



\## Update



```text

PATCH /api/v1/assets/{asset\_id}/limits/{limit\_id}

```



Data:



```text

Parameter

Unit

Alarm Limit

Trip Limit

```



Perubahan limit merupakan perubahan analytical configuration dan harus memiliki `updated\_at`.



Perubahan limit tidak otomatis mengubah historical analysis result.



Analysis baru diperlukan untuk memperoleh result berdasarkan configuration baru.



\---



\# 12. Hourly Telemetry API



\## 12.1 List Hourly Measurements



```text

GET /api/v1/telemetry/hourly

```



Filters:



```text

?asset\_id=KO-3201

\&from=2026-10-01T00:00:00

\&to=2026-10-03T23:59:59

\&run\_status=ON

\&page=1

\&page\_size=100

```



Response:



```json

{

&#x20; "data": \[

&#x20;   {

&#x20;     "asset\_id": "KO-3201",

&#x20;     "measured\_at": "2026-10-03T14:00:00",

&#x20;     "feed": 123.4,

&#x20;     "disp": 15.2,

&#x20;     "vib": 32.1,

&#x20;     "temp": 72.4,

&#x20;     "amp": 110.5,

&#x20;     "plant\_rate": 94.2,

&#x20;     "run\_status": "ON",

&#x20;     "source\_type": "MANUAL"

&#x20;   }

&#x20; ]

}

```



\---



\# 13. Single Hourly Measurement Input



```text

POST /api/v1/telemetry/hourly

```



Request:



```json

{

&#x20; "asset\_id": "KO-3201",

&#x20; "measured\_at": "2026-10-03T14:00:00",

&#x20; "feed": 123.4,

&#x20; "disp": 15.2,

&#x20; "vib": 32.1,

&#x20; "temp": 72.4,

&#x20; "amp": 110.5,

&#x20; "plant\_rate": 94.2,

&#x20; "run\_status": "ON"

}

```



Backend mengisi provenance:



```text

source\_type = MANUAL

```



apabila request berasal dari standard frontend manual input.



Endpoint ini:



```text

VALIDATE

&#x20;  ↓

SAVE

&#x20;  ↓

RETURN

```



Endpoint ini \*\*tidak menjalankan intelligence engine\*\*.



\---



\# 14. Bulk Hourly Measurement Input



Sediakan:



```text

POST /api/v1/telemetry/hourly/bulk

```



Request:



```json

{

&#x20; "measurements": \[

&#x20;   {

&#x20;     "asset\_id": "PU-2101B",

&#x20;     "measured\_at": "2026-10-03T14:00:00",

&#x20;     "feed": 10.4,

&#x20;     "disp": 7.2,

&#x20;     "vib": 2.1,

&#x20;     "temp": 64.0,

&#x20;     "amp": 88.0,

&#x20;     "plant\_rate": 94.2,

&#x20;     "run\_status": "ON"

&#x20;   },

&#x20;   {

&#x20;     "asset\_id": "KO-3201",

&#x20;     "measured\_at": "2026-10-03T14:00:00",

&#x20;     "feed": 123.4,

&#x20;     "disp": 15.2,

&#x20;     "vib": 32.1,

&#x20;     "temp": 72.4,

&#x20;     "amp": 110.5,

&#x20;     "plant\_rate": 94.2,

&#x20;     "run\_status": "ON"

&#x20;   }

&#x20; ]

}

```



Tujuan endpoint bulk adalah agar frontend nantinya dapat menyediakan UX seperti:



```text

Timestamp: 03 Oct 2026 14:00



Asset       FEED   DISP   VIB   TEMP   AMP   RATE   STATUS

\-----------------------------------------------------------

PU-2101B    \[...]

KO-3201     \[...]

...

&#x20;                                   \[ Save Measurements ]

```



Dengan demikian keputusan UI antara single-asset form dan multi-asset entry tidak mengharuskan perubahan API fundamental.



\---



\# 15. Telemetry Duplicate Handling



Kombinasi:



```text

asset\_id + measured\_at

```



harus unik untuk hourly measurement.



Jika data sudah tersedia, backend tidak boleh silently overwrite.



Response:



```text

409 Conflict

```



Frontend kemudian dapat menawarkan explicit edit/update action.



\---



\# 16. Update Hourly Measurement



```text

PATCH /api/v1/telemetry/hourly/{measurement\_id}

```



atau identifier database yang sesuai dengan final schema.



Perubahan measurement tidak mengubah historical analysis snapshot.



UI dapat menunjukkan bahwa:



```text

New/updated source data exists after latest analysis.

```



\---



\# 17. Weekly Measurements API



Weekly measurement merupakan derived data.



\## List



```text

GET /api/v1/telemetry/weekly

```



Filters:



```text

?asset\_id=KO-3201

\&from=2026-01-01

\&to=2026-10-03

```



Response konseptual:



```json

{

&#x20; "data": \[

&#x20;   {

&#x20;     "asset\_id": "KO-3201",

&#x20;     "record\_date": "2026-10-03",

&#x20;     "parameter": "DE Radial Vibration",

&#x20;     "measured\_value": 32.1,

&#x20;     "unit": "micron",

&#x20;     "health\_status": "WATCH",

&#x20;     "remark": null,

&#x20;     "source\_type": "DERIVED"

&#x20;   }

&#x20; ]

}

```



\---



\# 18. Weekly Write Rule



Tidak disediakan general manual CRUD untuk derived weekly measurement pada initial implementation.



Weekly runtime data dihasilkan melalui:



```text

Hourly Measurements

&#x20;       ↓

WeeklyDerivationService

&#x20;       ↓

Weekly Measurements

```



Historical weekly seeder tetap dapat memiliki:



```text

source\_type = LEGACY\_SEED

```



\## OPEN DECISION



Formula derivasi parameter weekly dari hourly belum ditentukan.



Jangan implementasikan formula engineering berdasarkan asumsi.



\---



\# 19. Reliability — Incident API



\## List Incidents



```text

GET /api/v1/reliability/incidents

```



Filters dapat mencakup:



```text

?asset\_id=KO-3201

?plant=ZCU

?status=CA/PA%20EXECUTION

?discipline=ROT

?from=2026-01-01

?to=2026-12-31

?search=bearing

```



\---



\# 20. Incident Detail



```text

GET /api/v1/reliability/incidents/{ar\_no}

```



Response mempertahankan seluruh information domain dari Incident Record:



```text

Serial No

MTO No.

AR No.

Plant

Tag Number

Eq. Class

Date of Occur.

Risk Case Title

Highest Impact

Pre-Risk

Risk Score

PIC (RCA)

Overall Status

Discipline

Eq. Type

Component

F Mechanism

Downtime (hrs)

Act. Loss (k US$)

Pot. Loss (k US$)

Total Loss (k US$)

RCA Due Date

Month - Year

```



`Month - Year` dapat dihitung dari occurrence date jika database specification menetapkannya sebagai derived field.



\---



\# 21. Create Incident



```text

POST /api/v1/reliability/incidents

```



Incident merupakan reliability record.



Pembuatan incident tidak otomatis berarti engine-generated problem ticket.



\---



\# 22. Update Incident



```text

PATCH /api/v1/reliability/incidents/{ar\_no}

```



`AR No.` diperlakukan sebagai domain identifier.



Perubahan identifier harus dibatasi karena menjadi referensi RCA.



\---



\# 23. RCA Workspace API



RCA menggunakan incident `AR No.` sebagai context utama.



```text

/reliability/incidents/{ar\_no}/rca

```



\---



\# 24. RCA Header



```text

GET /api/v1/reliability/incidents/{ar\_no}/rca/header



PUT /api/v1/reliability/incidents/{ar\_no}/rca/header

```



Data:



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



Beberapa informasi yang sudah berasal dari incident dapat ditampilkan read-only di frontend.



Jangan meminta user mengetik informasi yang sama berulang kali apabila dapat diperoleh melalui relation.



\---



\# 25. RCA Priority Matrix



```text

GET  /api/v1/reliability/incidents/{ar\_no}/rca/priority-matrix



POST /api/v1/reliability/incidents/{ar\_no}/rca/priority-matrix



PATCH /api/v1/reliability/incidents/{ar\_no}/rca/priority-matrix/{item\_id}



DELETE /api/v1/reliability/incidents/{ar\_no}/rca/priority-matrix/{item\_id}

```



Fields:



```text

Root Cause ID

Impact Level

Control Level

Priority Rank

Description

```



\---



\# 26. RCA 4P Verification



```text

GET  /api/v1/reliability/incidents/{ar\_no}/rca/4p



POST /api/v1/reliability/incidents/{ar\_no}/rca/4p



PATCH /api/v1/reliability/incidents/{ar\_no}/rca/4p/{verification\_id}



DELETE /api/v1/reliability/incidents/{ar\_no}/rca/4p/{verification\_id}

```



Fields:



```text

Parameter ID

Problem Phenomenon Parameter

Result

Evidence Finding

```



\---



\# 27. RCA 4M Verification



```text

GET  /api/v1/reliability/incidents/{ar\_no}/rca/4m



POST /api/v1/reliability/incidents/{ar\_no}/rca/4m



PATCH /api/v1/reliability/incidents/{ar\_no}/rca/4m/{factor\_id}



DELETE /api/v1/reliability/incidents/{ar\_no}/rca/4m/{factor\_id}

```



Fields mengikuti source data:



```text

Factor ID

Factor Category

Result

Evidence Finding

```



\---



\# 28. CAPA API



```text

GET  /api/v1/reliability/incidents/{ar\_no}/rca/capa



POST /api/v1/reliability/incidents/{ar\_no}/rca/capa



PATCH /api/v1/reliability/incidents/{ar\_no}/rca/capa/{capa\_id}



DELETE /api/v1/reliability/incidents/{ar\_no}/rca/capa/{capa\_id}

```



Fields:



```text

Action Plan

Target Date

PIC

Status

```



CAPA adalah historical/reliability knowledge dan dapat digunakan engine sebagai reference pada RCA matching.



\---



\# 29. Reliability Aggregate Detail



Untuk mengurangi jumlah request frontend pada RCA Workspace, backend dapat menyediakan:



```text

GET /api/v1/reliability/incidents/{ar\_no}/rca

```



Response:



```json

{

&#x20; "data": {

&#x20;   "incident": {},

&#x20;   "header": {},

&#x20;   "priority\_matrix": \[],

&#x20;   "verification\_4p": \[],

&#x20;   "verification\_4m": \[],

&#x20;   "capa": \[]

&#x20; }

}

```



Endpoint aggregate terutama digunakan untuk \*\*read/detail view\*\*.



Write operation tetap menggunakan resource endpoint masing-masing.



\---



\# 30. Problems API



Problems merupakan operational workflow berdasarkan analytical problem context.



Historical reliability incident dan current problem ticket bukan entity yang sama.



```text

Historical Incident

&#x20;     ≠

Current Problem Ticket

```



\---



\# 31. List Problems



```text

GET /api/v1/problems

```



Filters:



```text

?asset\_id=KO-3201

?priority=P1

?ticket\_state=OPEN

?action\_status=NOT\_STARTED

?requires\_attention=true

```



Response minimal:



```json

{

&#x20; "data": \[

&#x20;   {

&#x20;     "ticket\_id": "PT-20261003-KO3201-001",

&#x20;     "asset\_id": "KO-3201",

&#x20;     "condition\_state": "ALARM",

&#x20;     "priority": "P1",

&#x20;     "ticket\_state": "OPEN",

&#x20;     "action\_status": "NOT\_STARTED",

&#x20;     "why\_raised": "...",

&#x20;     "rca\_indication": "...",

&#x20;     "evidence\_strength": "HIGH",

&#x20;     "recommended\_action": "...",

&#x20;     "owner\_role": "Reliability / Rotating Equipment"

&#x20;   }

&#x20; ]

}

```



\---



\# 32. Problem Detail



```text

GET /api/v1/problems/{ticket\_id}

```



Detail dapat menggabungkan:



```text

Ticket

Current analytical condition

Why raised

Current evidence

Current RCA match

Historical analogue

Evidence strength

Recommended action

Operator state

```



Problem Detail merupakan read model untuk frontend.



Tidak semua field harus berasal dari satu database table.



\---



\# 33. Problem Verification



```text

POST /api/v1/problems/{ticket\_id}/verification

```



Request:



```json

{

&#x20; "operator\_decision": "ACKNOWLEDGE",

&#x20; "operator\_name": "Operator A",

&#x20; "owner\_role": "Reliability / Rotating Equipment",

&#x20; "action\_status": "ACKNOWLEDGED",



&#x20; "visible\_leakage": "NO",

&#x20; "abnormal\_noise": "YES",

&#x20; "abnormal\_vibration": "YES",

&#x20; "local\_temp\_confirmed": "NO",



&#x20; "field\_observation": "Abnormal noise observed near DE bearing.",

&#x20; "comment": "Request reliability inspection."

}

```



Service melakukan satu transaction:



```text

BEGIN

&#x20;  ↓

Save Operator Input

&#x20;  ↓

Update Ticket Workflow State

&#x20;  ↓

Append Audit Log

COMMIT

```



Operator verification tidak mengubah historical engine output.



\---



\# 34. Problem History



```text

GET /api/v1/problems/{ticket\_id}/history

```



Response append-only audit events.



Contoh fields:



```text

event\_time

event\_type

update\_source



previous\_ticket\_state

new\_ticket\_state



previous\_action\_status

new\_action\_status



operator\_decision

operator\_name

owner\_role



field\_observation

comment

```



\---



\# 35. Analytics Runs API



\## Create Analysis Run



```text

POST /api/v1/analytics/runs

```



Request initial implementation dapat sederhana:



```json

{}

```



Backend:



```text

API

&#x20;↓

IntelligenceService.run\_analysis()

&#x20;↓

Engine Adapter

&#x20;↓

intelligence\_engine.py

&#x20;↓

Persist Result

```



Response dapat berupa:



```json

{

&#x20; "data": {

&#x20;   "run\_id": 153,

&#x20;   "status": "RUNNING"

&#x20; }

}

```



Gunakan `202 Accepted` jika execution dilakukan asynchronous/background.



Jika initial local implementation berjalan synchronous, implementation dapat menyesuaikan tanpa mengubah domain contract.



\---



\# 36. List Analysis Runs



```text

GET /api/v1/analytics/runs

```



Response:



```json

{

&#x20; "data": \[

&#x20;   {

&#x20;     "run\_id": 153,

&#x20;     "status": "COMPLETED",

&#x20;     "started\_at": "2026-10-03T14:05:00Z",

&#x20;     "completed\_at": "2026-10-03T14:05:32Z",

&#x20;     "analysis\_reference\_time": "2026-10-03T14:00:00",

&#x20;     "trigger\_type": "MANUAL"

&#x20;   }

&#x20; ]

}

```



\---



\# 37. Analysis Run Detail



```text

GET /api/v1/analytics/runs/{run\_id}

```



Digunakan untuk mengetahui:



```text

RUNNING

COMPLETED

FAILED

```



Jika gagal, response dapat menyertakan safe error information untuk administrator/developer.



Jangan mengirim internal stack trace kepada normal frontend user.



\---



\# 38. Latest Analysis Status



```text

GET /api/v1/analytics/latest

```



Response contoh:



```json

{

&#x20; "data": {

&#x20;   "run\_id": 153,

&#x20;   "status": "COMPLETED",

&#x20;   "analysis\_reference\_time": "2026-10-03T14:00:00",

&#x20;   "completed\_at": "2026-10-03T14:05:32Z",

&#x20;   "latest\_source\_data\_time": "2026-10-03T15:00:00",

&#x20;   "new\_data\_available": true

&#x20; }

}

```



Endpoint ini berguna untuk frontend menampilkan:



```text

Latest Data       15:00

Latest Analysis   14:00



New data available.



\[ Run Analysis ]

```



\---



\# 39. Dashboard Analytics



Sediakan aggregate read endpoint:



```text

GET /api/v1/analytics/dashboard

```



Optional filter:



```text

?asset\_id=KO-3201

```



Response berasal dari \*\*latest successful persisted analysis\*\*.



Dapat berisi:



```json

{

&#x20; "data": {

&#x20;   "analysis": {},

&#x20;   "kpis": {},

&#x20;   "asset\_overview": \[],

&#x20;   "production\_emissions": \[],

&#x20;   "energy\_outlook": \[],

&#x20;   "trends": \[],

&#x20;   "active\_problems": \[],

&#x20;   "data\_model\_status": \[]

&#x20; }

}

```



Endpoint ini menggantikan kebutuhan frontend untuk mengambil banyak endpoint kecil saat membuka Executive Dashboard.



\---



\# 40. Asset Condition Analytics



```text

GET /api/v1/analytics/assets/{asset\_id}/condition

```



Mengembalikan latest persisted condition:



```text

Current condition

Health score

Operating performance

Load proxy

Reliability / consequence context

Analysis reference time

Data provenance

```



\---



\# 41. Asset Parameter Analytics



```text

GET /api/v1/analytics/assets/{asset\_id}/parameters

```



Mengembalikan:



```text

Parameter

Current value

Unit

Current condition

Latest observed timestamp

Data age

Decision provenance

Technical source

Model quality

Selected model

Alarm limit

Trip limit

```



\---



\# 42. Parameter Trend



```text

GET /api/v1/analytics/assets/{asset\_id}/parameters/{parameter}/trend

```



Query:



```text

?days=30

```



Response dapat mencakup:



```text

Measured values

Reconstructed values

Forward estimates

Lower bound

Upper bound

Weekly engineering observations

Alarm limit

Trip limit

Analysis reference time

```



\---



\# 43. Forecast API



```text

GET /api/v1/analytics/assets/{asset\_id}/forecast

```



Response mencakup persisted forecast untuk:



```text

H+24

H+72

H+168

```



serta weekly forecast jika tersedia.



\---



\# 44. Forecast Validation API



```text

GET /api/v1/analytics/assets/{asset\_id}/validation

```



Response dapat mencakup:



```text

Parameter

Horizon

Selected Model

Quality Classification

MAE

RMSE

Skill vs Persistence

Validation Cases

Validation Method

Deployment Decision

```



\---



\# 45. Current RCA Match API



```text

GET /api/v1/analytics/assets/{asset\_id}/rca

```



Response berasal dari current analysis:



```text

Current trigger

Matched historical incident

Case similarity

Current supporting evidence

Historically verified evidence

Evidence strength

Four-P reference

Four-M reference

CAPA reference

```



Ini berbeda dari:



```text

/reliability/incidents/{ar\_no}/rca

```



Perbedaannya:



```text

/reliability/...

&#x20;   = historical knowledge



/analytics/.../rca

&#x20;   = current engine inference/match

```



\---



\# 46. Data Quality API



```text

GET /api/v1/analytics/data-quality

```



Response dapat mencakup:



```text

Asset

Latest measured timestamp

Data age

Current data basis

Forecast quality

Measured condition

Forecast condition

Downtime-data status

Observed coverage

Observed availability

Input quality gate

```



\---



\# 47. Users API



Administration initial scope hanya menangani user data.



```text

GET   /api/v1/users

POST  /api/v1/users

GET   /api/v1/users/{user\_id}

PATCH /api/v1/users/{user\_id}

```



Password/authentication implementation mengikuti authentication decision yang ditentukan kemudian.



Jangan menyimpan plaintext password.



\---



\# 48. Source Data vs Analytical Data



API harus mempertahankan separation berikut:



```text

SOURCE DATA



/assets

/telemetry

/reliability





WORKFLOW DATA



/problems





ANALYTICAL DATA



/analytics

```



Contoh:



```text

GET /telemetry/hourly

```



berarti:



> Apa measurement yang tersimpan?



Sedangkan:



```text

GET /analytics/assets/KO-3201/condition

```



berarti:



> Apa interpretation engine terhadap measurement tersebut?



Jangan mencampur dua konsep tersebut.



\---



\# 49. Read vs Compute Rule



Normal GET endpoint:



```text

GET /analytics/dashboard

GET /analytics/assets/{id}/condition

GET /analytics/assets/{id}/forecast

GET /problems

GET /reliability/incidents

```



hanya membaca persisted state.



Satu-satunya analytical execution flow:



```text

POST /analytics/runs

```



atau trigger internal yang nantinya memanggil service yang sama.



\---



\# 50. Source Data Freshness



Backend harus dapat membandingkan:



```text

latest source data timestamp



vs



latest successful analysis reference time

```



Sehingga frontend dapat mengetahui:



```text

Analysis is current

```



atau:



```text

New data available — analysis may be outdated

```



Jangan diam-diam menampilkan analytical result lama sebagai hasil dari measurement terbaru.



\---



\# 51. Provenance



API response yang relevan harus mempertahankan provenance.



Contoh values:



```text

LEGACY\_SEED

MANUAL

API

DCS

DERIVED

ENGINE

OPERATOR

SYSTEM

```



Analytical provenance dapat lebih spesifik mengikuti output `intelligence\_engine.py`.



\---



\# 52. Validation Responsibility



Gunakan pembagian:



```text

Pydantic

&#x20;   ↓

API structural validation



Service

&#x20;   ↓

business/domain validation



Database

&#x20;   ↓

integrity constraints



intelligence\_engine

&#x20;   ↓

analytical/data-quality validation

```



Jangan memindahkan seluruh data-quality logic engine ke Pydantic.



\---



\# 53. Example End-to-End Flow — Input Telemetry



```text

Vue

&#x20;│

&#x20;│ POST /telemetry/hourly

&#x20;▼

FastAPI

&#x20;│

&#x20;▼

TelemetryService

&#x20;│

&#x20;▼

TelemetryRepository

&#x20;│

&#x20;▼

PostgreSQL

&#x20;│

&#x20;▼

201 Created

```



Engine tidak dijalankan.



\---



\# 54. Example End-to-End Flow — Run Analysis



```text

Vue

&#x20;│

&#x20;│ POST /analytics/runs

&#x20;▼

FastAPI

&#x20;│

&#x20;▼

IntelligenceService

&#x20;│

&#x20;├── Repository

&#x20;│       ↓

&#x20;│   PostgreSQL

&#x20;│

&#x20;├── Engine Data Adapter

&#x20;│

&#x20;├── intelligence\_engine.py

&#x20;│

&#x20;├── Engine Output Adapter

&#x20;│

&#x20;└── AnalyticsRepository

&#x20;        ↓

&#x20;    PostgreSQL

```



\---



\# 55. Example End-to-End Flow — Dashboard



```text

Vue

&#x20;│

&#x20;│ GET /analytics/dashboard

&#x20;▼

FastAPI

&#x20;│

&#x20;▼

AnalyticsService

&#x20;│

&#x20;▼

AnalyticsRepository

&#x20;│

&#x20;▼

Latest Successful Analysis

&#x20;│

&#x20;▼

JSON

```



Tidak ada engine execution.



\---



\# 56. Example End-to-End Flow — Reliability RCA



```text

User creates Incident

&#x20;       │

&#x20;       ▼

Incident Record

&#x20;       │

&#x20;       ▼

RCA Workspace

&#x20;       │

&#x20;       ├── Header

&#x20;       ├── Priority Matrix

&#x20;       ├── 4P

&#x20;       ├── 4M

&#x20;       └── CAPA

&#x20;       │

&#x20;       ▼

Historical RCA Knowledge

&#x20;       │

&#x20;       ▼

Available to future engine runs

```



\---



\# 57. Example End-to-End Flow — Problem Verification



```text

Engine Analysis

&#x20;     │

&#x20;     ▼

Problem Context

&#x20;     │

&#x20;     ▼

Problem Ticket

&#x20;     │

&#x20;     ▼

Vue Problem Detail

&#x20;     │

&#x20;     ▼

Operator Verification

&#x20;     │

&#x20;     ▼

POST /problems/{ticket}/verification

&#x20;     │

&#x20;     ▼

Transaction

&#x20;     │

&#x20;     ├── Operator Input

&#x20;     ├── Ticket Update

&#x20;     └── Audit Log

```



\---



\# 58. Initial Backend Implementation Priority



Implement API secara bertahap.



\## Phase 1 — Foundation



```text

GET /assets

GET /assets/{id}



GET /telemetry/hourly

POST /telemetry/hourly

POST /telemetry/hourly/bulk



GET /telemetry/weekly

```



Tujuan:



> memastikan PostgreSQL + Repository + FastAPI bekerja.



\---



\## Phase 2 — Intelligence Integration



```text

POST /analytics/runs

GET  /analytics/runs/{id}

GET  /analytics/latest



GET /analytics/dashboard

GET /analytics/assets/{id}/condition

GET /analytics/assets/{id}/parameters

GET /analytics/assets/{id}/forecast

GET /analytics/assets/{id}/rca

```



Tujuan:



> memastikan database → adapter → engine → database → API bekerja.



\---



\## Phase 3 — Reliability



```text

/reliability/incidents

/reliability/incidents/{ar\_no}/rca/\*

```



Tujuan:



> mengganti historical RCA spreadsheet dengan database-backed knowledge management.



\---



\## Phase 4 — Problems



```text

/problems

/problems/{ticket\_id}

/problems/{ticket\_id}/verification

/problems/{ticket\_id}/history

```



Tujuan:



> mengganti workflow CSV dengan transactional database workflow.



\---



\## Phase 5 — Administration



```text

/users

```



Authentication dan authorization mengikuti requirement terpisah.



\---



\# 59. AI Implementation Rules



Implementation AI harus:



```text

Use FastAPI routers.



Use Pydantic request/response schemas.



Keep API routes thin.



Put workflow logic in services.



Put SQL/database access in repositories.



Use transactions for workflow writes.



Use engine adapter for intelligence\_engine input.



Read persisted analytical results for dashboard GET requests.



Keep historical RCA separate from current RCA inference.



Keep source telemetry separate from analytical interpretation.

```



Implementation AI tidak boleh:



```text

Run intelligence\_engine from ordinary GET requests.



Put SQL queries directly throughout route handlers.



Move intelligence algorithms into FastAPI routes.



Let Vue access PostgreSQL.



Silently overwrite duplicate telemetry.



Treat operator verification as measured sensor data.



Treat RCA similarity as confirmed physical root cause.



Assume weekly derivation formulas.



Rewrite intelligence\_engine to fit the API.

```



\---



\# 60. Open Decisions



Hal berikut tetap tidak boleh ditentukan sendiri oleh implementation AI.



\## OPEN-001 — Weekly Derivation Formula



Formula engineering untuk membentuk weekly measurements dari hourly measurements.



\## OPEN-002 — Authentication



Authentication mechanism.



\## OPEN-003 — Authorization



User role dan permission matrix.



\## OPEN-004 — Production Analysis Trigger



Initial implementation menggunakan manual analysis trigger.



Production dapat menggunakan scheduler/background execution, tetapi trigger final belum ditentukan.



\## OPEN-005 — External Telemetry Source



Integrasi DCS/PI/API belum ditentukan.



\---



\# 61. Core API Principle



API harus mempertahankan flow:



```text

SOURCE INPUT

&#x20;    ↓

PostgreSQL

&#x20;    ↓

Intelligence Engine

&#x20;    ↓

PERSISTED ANALYSIS

&#x20;    ↓

FastAPI

&#x20;    ↓

Vue

```



dan bukan:



```text

Vue

&#x20;↓

intelligence\_engine.py

&#x20;↓

temporary result

```



Tujuan backend adalah membuat `intelligence\_engine.py` menjadi analytical core yang dapat digunakan oleh application architecture baru tanpa melakukan rewrite besar terhadap algoritma existing.

