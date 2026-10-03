\# CALI-INI — Database \& Seeder Architecture Specification



\## Status



\*\*Status:\*\* Database architecture specification  

\*\*Target database:\*\* PostgreSQL  

\*\*Analytical engine:\*\* `intelligence\_engine.py` V11.x-compatible  

\*\*Frontend target:\*\* Vue  

\*\*Backend target:\*\* FastAPI / Python  

\*\*Initial data source:\*\* Existing Excel workbook  

\*\*Runtime source of truth:\*\* PostgreSQL



\---



\# 1. Tujuan



Dokumen ini menjadi \*\*source of truth untuk implementasi database, seeder, data-access layer, dan integrasi dengan `intelligence\_engine.py` pada CALI-INI\*\*.



Arsitektur database dirancang berdasarkan:



1\. struktur aktual spreadsheet;

2\. kebutuhan data `intelligence\_engine.py`;

3\. kebutuhan input data dari frontend;

4\. workflow Reliability / RCA;

5\. historical seeding dari spreadsheet;

6\. runtime telemetry dari input user atau integrasi;

7\. weekly measurement yang pada runtime diturunkan dari hourly measurement;

8\. penyimpanan hasil analytics;

9\. human-in-the-loop problem verification;

10\. kebutuhan administrasi user.



Prinsip utama implementasi:



> \*\*Preserve analytical behavior, replace storage.\*\*



Implementasi database \*\*bukan proyek rewrite analytical engine\*\*.



Perubahan terhadap `intelligence\_engine.py` harus seminimal mungkin dan difokuskan pada:



\- penggantian data access;

\- dependency injection;

\- persistence hasil analitik;

\- penggantian CSV workflow dengan PostgreSQL.



\---



\# 2. Arsitektur Target



```text

&#x20;                          Vue Frontend

&#x20;                               │

&#x20;                               │ REST / JSON

&#x20;                               ▼

&#x20;                           FastAPI

&#x20;                               │

&#x20;         ┌─────────────────────┼─────────────────────┐

&#x20;         │                     │                     │

&#x20;         ▼                     ▼                     ▼

&#x20;    Master Data            Telemetry             Reliability

&#x20;         │                     │                     │

&#x20;         └─────────────────────┼─────────────────────┘

&#x20;                               ▼

&#x20;                          PostgreSQL

&#x20;                               │

&#x20;                               ▼

&#x20;                   Intelligence Data Adapter

&#x20;                               │

&#x20;                               │ DataFrame contract

&#x20;                               ▼

&#x20;                   intelligence\_engine.py

&#x20;                               │

&#x20;            ┌──────────────────┼──────────────────┐

&#x20;            ▼                  ▼                  ▼

&#x20;        Condition           Forecast             RCA

&#x20;            │                  │                  │

&#x20;            └──────────────────┼──────────────────┘

&#x20;                               ▼

&#x20;                       Analytics Storage

&#x20;                               │

&#x20;                               ▼

&#x20;                           FastAPI

&#x20;                               │

&#x20;                               ▼

&#x20;                        Vue Dashboard

```



Excel digunakan untuk \*\*initial historical seeding\*\*.



```text

Excel

&#x20; │

&#x20; ▼

Seeder

&#x20; │

&#x20; ▼

PostgreSQL

&#x20; │

&#x20; ├──► Frontend / API

&#x20; │

&#x20; └──► Intelligence Adapter

&#x20;             │

&#x20;             ▼

&#x20;     intelligence\_engine.py

```



Production runtime tidak boleh bergantung pada workbook Excel.



\---



\# 3. Domain Database



Database dibagi menjadi enam logical domain:



```text

PostgreSQL

│

├── core

│   ├── assets

│   ├── asset\_metadata

│   ├── sensor\_tags

│   └── equipment\_limits

│

├── telemetry

│   ├── hourly\_measurements

│   └── weekly\_measurements

│

├── knowledge

│   ├── incidents

│   ├── rca\_headers

│   ├── rca\_priority\_matrix

│   ├── rca\_4p\_verifications

│   ├── rca\_4m\_verifications

│   └── rca\_capa\_actions

│

├── analytics

│   ├── analysis\_runs

│   ├── condition\_inferences

│   ├── parameter\_forecasts

│   └── rca\_matches

│

├── workflow

│   ├── problem\_tickets

│   ├── operator\_inputs

│   └── audit\_logs

│

├── iam

│   └── users

│

└── system

&#x20;   └── seed\_runs

```



Total rancangan utama:



```text

4 core tables

2 telemetry tables

6 knowledge tables

4 analytics tables

3 workflow tables

1 IAM table

1 system table



= 21 tables

```



\---



\# 4. Core Asset Domain



\## 4.1 `core.assets`



`core.assets` merupakan master equipment utama.



Data berasal dari sheet:



```text

<ASSET> Metadata

```



Struktur:



```sql

CREATE SCHEMA IF NOT EXISTS core;



CREATE TABLE core.assets (

&#x20;   asset\_id BIGSERIAL PRIMARY KEY,



&#x20;   tag\_number VARCHAR(50) NOT NULL UNIQUE,

&#x20;   asset\_name VARCHAR(255) NOT NULL,



&#x20;   plant\_unit VARCHAR(255),

&#x20;   plant\_code VARCHAR(50),



&#x20;   equipment\_type VARCHAR(255),

&#x20;   equipment\_class VARCHAR(50),

&#x20;   discipline VARCHAR(50),

&#x20;   criticality VARCHAR(30),



&#x20;   design\_life TEXT,

&#x20;   monitoring\_method TEXT,



&#x20;   core\_mode VARCHAR(20) NOT NULL DEFAULT 'hourly',

&#x20;   fla\_amp NUMERIC,



&#x20;   linked\_rca\_ar\_no VARCHAR(100),

&#x20;   failure\_date DATE,

&#x20;   dominant\_failure\_mode TEXT,



&#x20;   is\_active BOOLEAN NOT NULL DEFAULT TRUE,



&#x20;   created\_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

&#x20;   updated\_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),



&#x20;   CONSTRAINT chk\_assets\_core\_mode

&#x20;       CHECK (core\_mode IN ('hourly', 'weekly'))

);

```



Mapping metadata:



```text

Equipment Tag

&#x20;   -> tag\_number



Equipment Name

&#x20;   -> asset\_name



Equipment Type

&#x20;   -> equipment\_type



Equipment Class

&#x20;   -> equipment\_class



Plant / Unit

&#x20;   -> plant\_unit



Discipline

&#x20;   -> discipline



Criticality

&#x20;   -> criticality



Design Life

&#x20;   -> design\_life



Monitoring Method

&#x20;   -> monitoring\_method



Linked RCA / AR No.

&#x20;   -> linked\_rca\_ar\_no



Failure Date

&#x20;   -> failure\_date



Dominant Failure Mode

&#x20;   -> dominant\_failure\_mode

```



`plant\_code` dapat diturunkan dari `Plant / Unit` atau data Reliability, tetapi nilai `plant\_unit` asli tidak boleh dibuang.



\---



\# 5. Lossless Asset Metadata



\## 5.1 `core.asset\_metadata`



Walaupun beberapa field Metadata dipromosikan ke `core.assets`, seluruh pasangan asli:



```text

Parameter | Value

```



tetap disimpan.



```sql

CREATE TABLE core.asset\_metadata (

&#x20;   metadata\_id BIGSERIAL PRIMARY KEY,



&#x20;   asset\_id BIGINT NOT NULL

&#x20;       REFERENCES core.assets(asset\_id)

&#x20;       ON DELETE CASCADE,



&#x20;   parameter VARCHAR(255) NOT NULL,

&#x20;   value\_text TEXT,



&#x20;   source\_sheet VARCHAR(255) NOT NULL,



&#x20;   created\_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),



&#x20;   UNIQUE (asset\_id, parameter)

);

```



Tujuannya adalah menjaga proses initial seeding tetap \*\*lossless\*\*.



Seeder melakukan exact deduplication untuk metadata identik.



Conflicting duplicate:



```text

asset sama

parameter sama

value berbeda

```



harus menghasilkan validation error.



\---



\# 6. Sensor / Tag Dictionary



\## 6.1 `core.sensor\_tags`



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



Schema:



```sql

CREATE TABLE core.sensor\_tags (

&#x20;   tag\_id BIGSERIAL PRIMARY KEY,



&#x20;   asset\_id BIGINT NOT NULL

&#x20;       REFERENCES core.assets(asset\_id)

&#x20;       ON DELETE CASCADE,



&#x20;   pi\_tag VARCHAR(255) NOT NULL,

&#x20;   canonical\_param VARCHAR(50),



&#x20;   name VARCHAR(255),

&#x20;   description TEXT,



&#x20;   digital\_set TEXT,

&#x20;   engineering\_unit VARCHAR(100),



&#x20;   span NUMERIC,

&#x20;   typical\_value NUMERIC,

&#x20;   zero\_value NUMERIC,



&#x20;   instrument\_tag VARCHAR(255),



&#x20;   is\_active BOOLEAN NOT NULL DEFAULT TRUE,



&#x20;   source\_sheet VARCHAR(255),



&#x20;   created\_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),



&#x20;   UNIQUE (asset\_id, pi\_tag)

);

```



Canonical parameter mapping:



```text

\*\_FEED -> FEED

\*\_DISP -> DISP

\*\_VIB  -> VIB

\*\_TEMP -> TEMP

\*\_AMP  -> AMP

```



Tag yang tidak cocok tidak boleh dibuang.



Gunakan:



```text

canonical\_param = NULL

```



\---



\# 7. Equipment Limits



\## 7.1 `core.equipment\_limits`



Source:



```text

<ASSET> Equipment Limits

```



Source contract:



```text

Parameter

Unit

Alarm Limit

Trip Limit

```



Schema:



```sql

CREATE TABLE core.equipment\_limits (

&#x20;   limit\_id BIGSERIAL PRIMARY KEY,



&#x20;   asset\_id BIGINT NOT NULL

&#x20;       REFERENCES core.assets(asset\_id)

&#x20;       ON DELETE CASCADE,



&#x20;   parameter VARCHAR(255) NOT NULL,

&#x20;   unit VARCHAR(100),



&#x20;   alarm\_limit NUMERIC NOT NULL,

&#x20;   trip\_limit NUMERIC NOT NULL,



&#x20;   effective\_from TIMESTAMPTZ,

&#x20;   effective\_to TIMESTAMPTZ,



&#x20;   source\_sheet VARCHAR(255),



&#x20;   created\_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),



&#x20;   UNIQUE (asset\_id, parameter, effective\_from),



&#x20;   CHECK (alarm\_limit <> trip\_limit)

);

```



Direction tidak perlu menjadi mandatory source field.



Engine dapat menentukan:



```text

trip\_limit > alarm\_limit

&#x20;   -> HIGH LIMIT



trip\_limit < alarm\_limit

&#x20;   -> LOW LIMIT

```



\---



\# 8. Hourly Telemetry



\## 8.1 `telemetry.hourly\_measurements`



Hourly measurement merupakan \*\*primary operational measurement source\*\*.



Initial historical data berasal dari:



```text

<ASSET> Production Data Hourly

```



Pada runtime, data dapat berasal dari:



```text

Frontend manual input

API integration

DCS / PI integration

Batch import

```



Schema menggunakan wide canonical format agar kompatibilitas dengan engine tetap tinggi.



```sql

CREATE SCHEMA IF NOT EXISTS telemetry;



CREATE TABLE telemetry.hourly\_measurements (

&#x20;   asset\_id BIGINT NOT NULL

&#x20;       REFERENCES core.assets(asset\_id),



&#x20;   measured\_at TIMESTAMPTZ NOT NULL,



&#x20;   feed NUMERIC,

&#x20;   disp NUMERIC,

&#x20;   vib NUMERIC,

&#x20;   temp NUMERIC,

&#x20;   amp NUMERIC,



&#x20;   plant\_rate NUMERIC,



&#x20;   run\_status VARCHAR(20),



&#x20;   source\_type VARCHAR(50) NOT NULL DEFAULT 'MANUAL',



&#x20;   source\_sheet VARCHAR(255),



&#x20;   created\_by BIGINT,



&#x20;   imported\_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),



&#x20;   PRIMARY KEY (asset\_id, measured\_at),



&#x20;   CHECK (

&#x20;       run\_status IS NULL

&#x20;       OR run\_status IN ('ON', 'OFF', 'UNKNOWN')

&#x20;   )

);



CREATE INDEX idx\_hourly\_asset\_time

ON telemetry.hourly\_measurements (

&#x20;   asset\_id,

&#x20;   measured\_at DESC

);

```



Recommended `source\_type`:



```text

LEGACY\_SEED

MANUAL

API

DCS

BATCH\_IMPORT

```



\---



\# 9. Weekly Measurement



\## 9.1 Prinsip



Weekly measurement \*\*bukan primary manual input pada runtime\*\*.



Historical weekly data dari Excel tetap di-seed karena diperlukan untuk:



\- historical compatibility;

\- engine parity;

\- historical model validation;

\- baseline comparison.



Pada operational runtime:



> Weekly measurement dihasilkan dari hourly measurement melalui proses derivation/aggregation yang ditentukan backend.



Flow:



```text

Initial historical data:



Excel Performance Weekly

&#x20;       │

&#x20;       ▼

weekly\_measurements

&#x20;       │

&#x20;       ▼

intelligence\_engine





Operational runtime:



User / DCS / API

&#x20;       │

&#x20;       ▼

hourly\_measurements

&#x20;       │

&#x20;       ▼

Weekly Derivation Service

&#x20;       │

&#x20;       ▼

weekly\_measurements

&#x20;       │

&#x20;       ▼

intelligence\_engine

```



\## 9.2 `telemetry.weekly\_measurements`



Gunakan long-form karena engineering parameter berbeda antar asset.



```sql

CREATE TABLE telemetry.weekly\_measurements (

&#x20;   weekly\_measurement\_id BIGSERIAL PRIMARY KEY,



&#x20;   asset\_id BIGINT NOT NULL

&#x20;       REFERENCES core.assets(asset\_id),



&#x20;   week\_no INTEGER,

&#x20;   record\_date DATE NOT NULL,



&#x20;   parameter VARCHAR(255) NOT NULL,

&#x20;   measured\_value NUMERIC,



&#x20;   unit VARCHAR(100),



&#x20;   health\_status VARCHAR(100),

&#x20;   remark TEXT,



&#x20;   source\_type VARCHAR(50) NOT NULL,



&#x20;   derivation\_method VARCHAR(100),

&#x20;   derivation\_version VARCHAR(50),



&#x20;   period\_start TIMESTAMPTZ,

&#x20;   period\_end TIMESTAMPTZ,



&#x20;   source\_column VARCHAR(255),

&#x20;   source\_sheet VARCHAR(255),



&#x20;   generated\_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),



&#x20;   UNIQUE (

&#x20;       asset\_id,

&#x20;       record\_date,

&#x20;       parameter,

&#x20;       source\_type

&#x20;   )

);

```



Recommended source:



```text

LEGACY\_SEED

DERIVED

```



\## 9.3 Runtime Rule



Frontend \*\*tidak perlu menyediakan form Create Weekly Measurement\*\*.



Frontend hanya menyediakan fungsi yang relevan seperti:



```text

view weekly result

view derivation information

view historical weekly data

trigger recomputation jika memang diberikan permission

```



Primary telemetry input tetap hourly.



\---



\# 10. Reliability Domain



Reliability menggunakan konsep:



```text

Incident

&#x20;   │

&#x20;   ▼

RCA

&#x20;   │

&#x20;   ├── Priority Matrix

&#x20;   ├── 4P Verification

&#x20;   ├── 4M Verification

&#x20;   └── CAPA

```



Satu incident menjadi pusat workspace Reliability.



\---



\# 11. Incident Record



\## 11.1 `knowledge.incidents`



Semua kolom Incident Record harus disimpan.



```sql

CREATE SCHEMA IF NOT EXISTS knowledge;



CREATE TABLE knowledge.incidents (

&#x20;   incident\_id BIGSERIAL PRIMARY KEY,



&#x20;   serial\_no INTEGER,



&#x20;   mto\_no VARCHAR(100),



&#x20;   ar\_no VARCHAR(100) NOT NULL,



&#x20;   plant VARCHAR(100),

&#x20;   tag\_number VARCHAR(100),



&#x20;   equipment\_class VARCHAR(100),



&#x20;   date\_of\_occurrence DATE,



&#x20;   risk\_case\_title TEXT,



&#x20;   highest\_impact VARCHAR(255),



&#x20;   pre\_risk VARCHAR(100),

&#x20;   risk\_score NUMERIC,



&#x20;   pic\_rca VARCHAR(100),



&#x20;   overall\_status VARCHAR(255),



&#x20;   discipline VARCHAR(100),



&#x20;   equipment\_type VARCHAR(100),



&#x20;   component VARCHAR(255),



&#x20;   failure\_mechanism VARCHAR(255),



&#x20;   downtime\_hours NUMERIC,



&#x20;   actual\_loss\_kusd NUMERIC,

&#x20;   potential\_loss\_kusd NUMERIC,

&#x20;   total\_loss\_kusd NUMERIC,



&#x20;   rca\_due\_date DATE,



&#x20;   month\_year VARCHAR(50),



&#x20;   source\_type VARCHAR(50)

&#x20;       NOT NULL DEFAULT 'MANUAL',



&#x20;   source\_sheet VARCHAR(255),



&#x20;   created\_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

&#x20;   updated\_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);

```



Jika initial workbook validation membuktikan `AR No` unique, tambahkan:



```sql

ALTER TABLE knowledge.incidents

ADD CONSTRAINT uq\_incidents\_ar\_no

UNIQUE (ar\_no);

```



`AR No` kemudian menjadi business identifier utama untuk Reliability Workspace.



\---



\# 12. RCA Header



\## 12.1 `knowledge.rca\_headers`



Source:



```text

AR No

Tag Number

Plant

Date Occurrence

Pre Risk

Risk Score

PIC RCA

Procedure No

Problem Statement

Root Cause Statement

```



Schema:



```sql

CREATE TABLE knowledge.rca\_headers (

&#x20;   rca\_header\_id BIGSERIAL PRIMARY KEY,



&#x20;   ar\_no VARCHAR(100) NOT NULL UNIQUE,



&#x20;   tag\_number VARCHAR(100),

&#x20;   plant VARCHAR(100),



&#x20;   date\_occurrence DATE,



&#x20;   pre\_risk VARCHAR(100),

&#x20;   risk\_score NUMERIC,



&#x20;   pic\_rca VARCHAR(100),



&#x20;   procedure\_no VARCHAR(100),



&#x20;   problem\_statement TEXT,

&#x20;   root\_cause\_statement TEXT,



&#x20;   source\_type VARCHAR(50)

&#x20;       NOT NULL DEFAULT 'MANUAL',



&#x20;   source\_sheet VARCHAR(255),



&#x20;   created\_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

&#x20;   updated\_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),



&#x20;   CONSTRAINT fk\_rca\_incident

&#x20;       FOREIGN KEY (ar\_no)

&#x20;       REFERENCES knowledge.incidents(ar\_no)

);

```



\---



\# 13. RCA Priority Matrix



```sql

CREATE TABLE knowledge.rca\_priority\_matrix (

&#x20;   priority\_matrix\_id BIGSERIAL PRIMARY KEY,



&#x20;   ar\_no VARCHAR(100) NOT NULL

&#x20;       REFERENCES knowledge.rca\_headers(ar\_no)

&#x20;       ON DELETE CASCADE,



&#x20;   root\_cause\_id VARCHAR(100) NOT NULL,



&#x20;   impact\_level VARCHAR(100),

&#x20;   control\_level VARCHAR(100),



&#x20;   priority\_rank INTEGER,



&#x20;   description\_short TEXT,



&#x20;   created\_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),



&#x20;   UNIQUE (ar\_no, root\_cause\_id)

);

```



Source:



```text

AR No

Root Cause ID

Impact Level

Control Level

Priority Rank

Description (Short)

```



\---



\# 14. RCA 4P Verification



```sql

CREATE TABLE knowledge.rca\_4p\_verifications (

&#x20;   verification\_id BIGSERIAL PRIMARY KEY,



&#x20;   ar\_no VARCHAR(100) NOT NULL

&#x20;       REFERENCES knowledge.rca\_headers(ar\_no)

&#x20;       ON DELETE CASCADE,



&#x20;   parameter\_id VARCHAR(100) NOT NULL,



&#x20;   problem\_phenomenon\_parameter TEXT,



&#x20;   result VARCHAR(50),



&#x20;   evidence\_finding TEXT,



&#x20;   created\_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),



&#x20;   UNIQUE (ar\_no, parameter\_id)

);

```



Source:



```text

AR No

Parameter ID

Problem Phenomenon Parameter

Result

Evidence Finding

```



Nilai `G` dan `NG` tidak boleh diterjemahkan atau diubah oleh seeder.



\---



\# 15. RCA 4M Verification



```sql

CREATE TABLE knowledge.rca\_4m\_verifications (

&#x20;   verification\_id BIGSERIAL PRIMARY KEY,



&#x20;   ar\_no VARCHAR(100) NOT NULL

&#x20;       REFERENCES knowledge.rca\_headers(ar\_no)

&#x20;       ON DELETE CASCADE,



&#x20;   factor\_id VARCHAR(100) NOT NULL,



&#x20;   factor\_category TEXT,



&#x20;   result VARCHAR(50),



&#x20;   evidence\_finding TEXT,



&#x20;   created\_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),



&#x20;   UNIQUE (ar\_no, factor\_id)

);

```



Source:



```text

AR No

Factor ID

Factor Category

Result

Evidence Finding

```



\---



\# 16. RCA CAPA Actions



CAPA harus mendukung source workbook dengan struktur:



```text

AR No

RC

Action Type

Action Plan

Target Date

PIC

Status

```



`RC` dan `Action Type` harus nullable untuk mengakomodasi source yang tidak mempunyai kolom tersebut.



```sql

CREATE TABLE knowledge.rca\_capa\_actions (

&#x20;   capa\_id BIGSERIAL PRIMARY KEY,



&#x20;   ar\_no VARCHAR(100) NOT NULL

&#x20;       REFERENCES knowledge.rca\_headers(ar\_no)

&#x20;       ON DELETE CASCADE,



&#x20;   rc VARCHAR(100),



&#x20;   action\_type VARCHAR(100),



&#x20;   action\_plan TEXT NOT NULL,



&#x20;   target\_date DATE,



&#x20;   pic VARCHAR(100),



&#x20;   status VARCHAR(100),



&#x20;   fingerprint VARCHAR(64) NOT NULL UNIQUE,



&#x20;   created\_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

&#x20;   updated\_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);

```



Fingerprint deterministic:



```text

SHA256(

&#x20;   ar\_no

&#x20;   | rc

&#x20;   | action\_type

&#x20;   | normalized\_action\_plan

&#x20;   | target\_date

)

```



Seeder harus mendeteksi actual workbook columns.



Jangan mengarang `RC` atau `Action Type` apabila source tidak menyediakan nilainya.



\---



\# 17. Analytics Domain



Analytics tidak di-seed dari spreadsheet.



Data dihasilkan oleh `intelligence\_engine.py`.



```text

analytics

├── analysis\_runs

├── condition\_inferences

├── parameter\_forecasts

└── rca\_matches

```



\---



\# 18. Analysis Runs



```sql

CREATE SCHEMA IF NOT EXISTS analytics;



CREATE TABLE analytics.analysis\_runs (

&#x20;   run\_id BIGSERIAL PRIMARY KEY,



&#x20;   started\_at TIMESTAMPTZ NOT NULL,

&#x20;   completed\_at TIMESTAMPTZ,



&#x20;   reference\_time TIMESTAMPTZ,



&#x20;   engine\_version VARCHAR(100),



&#x20;   runtime\_mode VARCHAR(50),



&#x20;   status VARCHAR(50) NOT NULL,



&#x20;   error\_message TEXT,



&#x20;   created\_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);

```



Setiap engine execution harus mempunyai satu `run\_id`.



\---



\# 19. Condition Inference



```sql

CREATE TABLE analytics.condition\_inferences (

&#x20;   inference\_id BIGSERIAL PRIMARY KEY,



&#x20;   run\_id BIGINT NOT NULL

&#x20;       REFERENCES analytics.analysis\_runs(run\_id)

&#x20;       ON DELETE CASCADE,



&#x20;   asset\_id BIGINT NOT NULL

&#x20;       REFERENCES core.assets(asset\_id),



&#x20;   as\_of\_time TIMESTAMPTZ NOT NULL,



&#x20;   overall\_state VARCHAR(50),



&#x20;   consequence\_class VARCHAR(50),



&#x20;   priority VARCHAR(20),



&#x20;   dominant\_symptom TEXT,



&#x20;   health\_index NUMERIC,



&#x20;   pca\_anomaly\_score NUMERIC,



&#x20;   max\_zscore NUMERIC,



&#x20;   statistical\_available BOOLEAN,



&#x20;   created\_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),



&#x20;   UNIQUE (run\_id, asset\_id)

);

```



Condition state dapat berupa:



```text

NORMAL

WATCH

ALARM

TRIP

DATA\_GAP

NOT\_OBSERVABLE

```



Condition state tidak boleh disamakan dengan ticket state.



\---



\# 20. Parameter Forecasts



```sql

CREATE TABLE analytics.parameter\_forecasts (

&#x20;   forecast\_id BIGSERIAL PRIMARY KEY,



&#x20;   run\_id BIGINT NOT NULL

&#x20;       REFERENCES analytics.analysis\_runs(run\_id)

&#x20;       ON DELETE CASCADE,



&#x20;   asset\_id BIGINT NOT NULL

&#x20;       REFERENCES core.assets(asset\_id),



&#x20;   canonical\_param VARCHAR(255) NOT NULL,



&#x20;   anchor\_time TIMESTAMPTZ,



&#x20;   target\_time TIMESTAMPTZ NOT NULL,



&#x20;   estimate NUMERIC,



&#x20;   lower\_bound NUMERIC,

&#x20;   upper\_bound NUMERIC,



&#x20;   source VARCHAR(100),



&#x20;   model\_family VARCHAR(100),

&#x20;   model\_type VARCHAR(100),

&#x20;   model\_quality VARCHAR(100),



&#x20;   mae NUMERIC,

&#x20;   rmse NUMERIC,



&#x20;   created\_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),



&#x20;   UNIQUE (

&#x20;       run\_id,

&#x20;       asset\_id,

&#x20;       canonical\_param,

&#x20;       target\_time

&#x20;   )

);

```



Tidak perlu membuat tabel terpisah untuk:



```text

AutoReg

OLS

Persistence

Kalman

PCA

EWMA

```



Model tersebut merupakan implementation detail analytical engine.



\---



\# 21. RCA Analytical Matches



\## 21.1 `analytics.rca\_matches`



Tabel ini menyimpan output historical similarity / RCA matching dari analytical engine.



```sql

CREATE TABLE analytics.rca\_matches (

&#x20;   rca\_match\_id BIGSERIAL PRIMARY KEY,



&#x20;   run\_id BIGINT NOT NULL

&#x20;       REFERENCES analytics.analysis\_runs(run\_id)

&#x20;       ON DELETE CASCADE,



&#x20;   asset\_id BIGINT NOT NULL

&#x20;       REFERENCES core.assets(asset\_id),



&#x20;   matched\_ar\_no VARCHAR(100),



&#x20;   similarity\_score NUMERIC,



&#x20;   evidence\_strength VARCHAR(100),



&#x20;   rank\_no INTEGER,



&#x20;   current\_supporting\_evidence TEXT,



&#x20;   historical\_verified\_evidence TEXT,



&#x20;   created\_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),



&#x20;   UNIQUE (

&#x20;       run\_id,

&#x20;       asset\_id,

&#x20;       matched\_ar\_no

&#x20;   )

);

```



Tabel ini menyimpan \*\*hasil engine\*\*, bukan source RCA historical.



Perbedaannya:



```text

knowledge.\*

&#x20;   = historical RCA knowledge



analytics.rca\_matches

&#x20;   = hasil engine mencocokkan kondisi sekarang

&#x20;     dengan historical RCA

```



Pemisahan ini diperlukan untuk auditability.



\---



\# 22. Problem Workflow



Problem workflow harus dipisahkan dari analytical condition.



Flow:



```text

Intelligence Engine

&#x20;       │

&#x20;       ▼

Condition Detection

&#x20;       │

&#x20;       ▼

Problem Ticket

&#x20;       │

&#x20;       ▼

RCA Hypothesis

&#x20;       │

&#x20;       ▼

Operator Verification

&#x20;       │

&#x20;       ▼

Follow-up Action

&#x20;       │

&#x20;       ▼

Audit Log

```



Operator tidak mengubah hasil model secara langsung.



Operator memberikan \*\*verification / operational decision\*\* terhadap hasil analytical engine.



\---



\# 23. Problem Tickets



```sql

CREATE SCHEMA IF NOT EXISTS workflow;



CREATE TABLE workflow.problem\_tickets (

&#x20;   ticket\_id VARCHAR(100) PRIMARY KEY,



&#x20;   asset\_id BIGINT NOT NULL

&#x20;       REFERENCES core.assets(asset\_id),



&#x20;   opened\_at TIMESTAMPTZ NOT NULL,



&#x20;   last\_seen TIMESTAMPTZ,



&#x20;   condition\_state VARCHAR(50),



&#x20;   priority VARCHAR(20),



&#x20;   owner\_role VARCHAR(255),



&#x20;   ticket\_state VARCHAR(100),



&#x20;   action\_status VARCHAR(100),



&#x20;   normal\_streak INTEGER NOT NULL DEFAULT 0,



&#x20;   matched\_rca\_ar VARCHAR(100),



&#x20;   evidence\_strength VARCHAR(100),



&#x20;   operator\_decision VARCHAR(100),



&#x20;   last\_operator\_name VARCHAR(255),



&#x20;   operator\_comment TEXT,



&#x20;   field\_observation TEXT,



&#x20;   update\_source VARCHAR(50),



&#x20;   last\_observation\_time TIMESTAMPTZ,



&#x20;   updated\_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);

```



`problem\_tickets` menyimpan \*\*current ticket snapshot\*\*.



Historical perubahan tidak disimpan dengan menambah kolom baru pada ticket.



Historical event disimpan pada `audit\_logs`.



\---



\# 24. Operator Verification Input



```sql

CREATE TABLE workflow.operator\_inputs (

&#x20;   operator\_input\_id BIGSERIAL PRIMARY KEY,



&#x20;   asset\_id BIGINT NOT NULL

&#x20;       REFERENCES core.assets(asset\_id),



&#x20;   ticket\_id VARCHAR(100)

&#x20;       REFERENCES workflow.problem\_tickets(ticket\_id),



&#x20;   decision VARCHAR(100),



&#x20;   operator\_name VARCHAR(255),



&#x20;   visible\_leakage VARCHAR(50),



&#x20;   abnormal\_noise VARCHAR(50),



&#x20;   abnormal\_vibration VARCHAR(50),



&#x20;   local\_temperature\_confirmed VARCHAR(50),



&#x20;   field\_observation TEXT,



&#x20;   comment TEXT,



&#x20;   owner\_role VARCHAR(255),



&#x20;   action\_status VARCHAR(100),



&#x20;   submitted\_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);



CREATE INDEX idx\_operator\_inputs\_ticket\_time

ON workflow.operator\_inputs (

&#x20;   ticket\_id,

&#x20;   submitted\_at DESC

);

```



Setiap submission operator menjadi row baru.



Jangan overwrite historical verification.



Repository tetap dapat menyediakan:



```python

get\_latest\_operator\_input(asset)

```



untuk compatibility dengan engine.



\---



\# 25. Workflow Audit Log



```sql

CREATE TABLE workflow.audit\_logs (

&#x20;   audit\_id BIGSERIAL PRIMARY KEY,



&#x20;   event\_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),



&#x20;   ticket\_id VARCHAR(100)

&#x20;       REFERENCES workflow.problem\_tickets(ticket\_id),



&#x20;   asset\_id BIGINT

&#x20;       REFERENCES core.assets(asset\_id),



&#x20;   update\_source VARCHAR(50),



&#x20;   event\_type VARCHAR(100),



&#x20;   previous\_ticket\_state VARCHAR(100),

&#x20;   new\_ticket\_state VARCHAR(100),



&#x20;   previous\_action\_status VARCHAR(100),

&#x20;   new\_action\_status VARCHAR(100),



&#x20;   operator\_decision VARCHAR(100),



&#x20;   operator\_name VARCHAR(255),



&#x20;   owner\_role VARCHAR(255),



&#x20;   field\_observation TEXT,



&#x20;   comment TEXT

);

```



Audit log bersifat:



> \*\*append-only\*\*



Normal application flow tidak boleh melakukan:



```text

UPDATE old audit event

DELETE old audit event

```



\---



\# 26. User Administration



Administration pada tahap implementasi awal hanya berfokus pada user.



```sql

CREATE SCHEMA IF NOT EXISTS iam;



CREATE TABLE iam.users (

&#x20;   user\_id BIGSERIAL PRIMARY KEY,



&#x20;   username VARCHAR(100) NOT NULL UNIQUE,



&#x20;   display\_name VARCHAR(255) NOT NULL,



&#x20;   email VARCHAR(255),



&#x20;   employee\_id VARCHAR(100),



&#x20;   role VARCHAR(100),



&#x20;   discipline VARCHAR(100),



&#x20;   is\_active BOOLEAN NOT NULL DEFAULT TRUE,



&#x20;   created\_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),



&#x20;   updated\_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);

```



Authentication mechanism \*\*belum ditentukan pada specification ini\*\*.



Jangan otomatis menambahkan:



```text

password\_hash

OAuth provider

SSO provider

JWT configuration

LDAP mapping

```



sampai keputusan authentication dibuat.



\---



\# 27. Seeder Run Tracking



Tambahkan tracking untuk setiap proses seeding/import workbook.



```sql

CREATE SCHEMA IF NOT EXISTS system;



CREATE TABLE system.seed\_runs (

&#x20;   seed\_run\_id BIGSERIAL PRIMARY KEY,



&#x20;   source\_filename VARCHAR(255) NOT NULL,



&#x20;   source\_checksum VARCHAR(128) NOT NULL,



&#x20;   started\_at TIMESTAMPTZ NOT NULL,



&#x20;   completed\_at TIMESTAMPTZ,



&#x20;   status VARCHAR(50) NOT NULL,



&#x20;   assets\_count INTEGER,



&#x20;   metadata\_count INTEGER,



&#x20;   sensor\_tags\_count INTEGER,



&#x20;   equipment\_limits\_count INTEGER,



&#x20;   hourly\_count INTEGER,



&#x20;   weekly\_source\_rows INTEGER,



&#x20;   weekly\_measurements\_count INTEGER,



&#x20;   incidents\_count INTEGER,



&#x20;   rca\_headers\_count INTEGER,



&#x20;   rca\_priority\_count INTEGER,



&#x20;   rca\_4p\_count INTEGER,



&#x20;   rca\_4m\_count INTEGER,



&#x20;   rca\_capa\_count INTEGER,



&#x20;   warnings JSONB,



&#x20;   errors JSONB,



&#x20;   created\_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);

```



Checksum digunakan untuk mengetahui apakah workbook yang sama pernah di-import.



Seeder tetap harus idempotent walaupun checksum sama.



\---



\# 28. Seeder Flow



```text

All\_Case\_Data.xlsx

&#x20;       │

&#x20;       ▼

Workbook Validation

&#x20;       │

&#x20;       ▼

Create Seed Run

&#x20;       │

&#x20;       ▼

Core Asset Seed

&#x20;       │

&#x20;       ├── Assets

&#x20;       ├── Metadata

&#x20;       ├── Tags

&#x20;       └── Limits

&#x20;       │

&#x20;       ▼

Telemetry Seed

&#x20;       │

&#x20;       ├── Hourly

&#x20;       └── Historical Weekly

&#x20;       │

&#x20;       ▼

Reliability Seed

&#x20;       │

&#x20;       ├── Incidents

&#x20;       ├── RCA Header

&#x20;       ├── Priority Matrix

&#x20;       ├── 4P

&#x20;       ├── 4M

&#x20;       └── CAPA

&#x20;       │

&#x20;       ▼

Cross-table Validation

&#x20;       │

&#x20;       ▼

Commit

&#x20;       │

&#x20;       ▼

Seed Report

```



Seeder tidak mengisi:



```text

analytics.\*

workflow.\*

iam.users

```



kecuali terdapat source data tambahan yang secara eksplisit diberikan.



\---



\# 29. Sheet → Database Mapping



| Spreadsheet Source | Database Target |

|---|---|

| `<ASSET> Metadata` | `core.assets`, `core.asset\_metadata` |

| `<ASSET> Tag Dictionary` | `core.sensor\_tags` |

| `<ASSET> Equipment Limits` | `core.equipment\_limits` |

| `<ASSET> Production Data Hourly` | `telemetry.hourly\_measurements` |

| `<ASSET> Performance Weekly` | `telemetry.weekly\_measurements` sebagai `LEGACY\_SEED` |

| `Incident Record` | `knowledge.incidents` |

| `RCA Header` | `knowledge.rca\_headers` |

| `RCA Priority Matrix` | `knowledge.rca\_priority\_matrix` |

| `RCA 4P Verification` | `knowledge.rca\_4p\_verifications` |

| `RCA 4M Verification` | `knowledge.rca\_4m\_verifications` |

| `RCA CAPA Actions` | `knowledge.rca\_capa\_actions` |



Runtime generated:



| Runtime Source | Database Target |

|---|---|

| Hourly aggregation / derivation | `telemetry.weekly\_measurements` |

| Intelligence engine execution | `analytics.analysis\_runs` |

| Condition analysis | `analytics.condition\_inferences` |

| Forecast | `analytics.parameter\_forecasts` |

| Historical RCA similarity | `analytics.rca\_matches` |

| Problem generation | `workflow.problem\_tickets` |

| Operator verification | `workflow.operator\_inputs` |

| Workflow event | `workflow.audit\_logs` |

| Administration | `iam.users` |



\---



\# 30. Intelligence Engine Compatibility



Database design tidak boleh memaksa `intelligence\_engine.py` mengetahui struktur PostgreSQL.



Gunakan:



```text

PostgreSQL

&#x20;   │

&#x20;   ▼

Repository

&#x20;   │

&#x20;   ▼

Intelligence Data Adapter

&#x20;   │

&#x20;   ▼

Source-compatible DataFrame

&#x20;   │

&#x20;   ▼

intelligence\_engine.py

```



Adapter bertanggung jawab melakukan:



```text

SQL naming

&#x20;   ↓

engine naming



long-form weekly

&#x20;   ↓

wide DataFrame



database relation

&#x20;   ↓

engine-compatible object/dataframe contract

```



Contoh hourly:



Database:



```text

measured\_at

feed

disp

vib

temp

amp

plant\_rate

run\_status

```



Engine-facing:



```text

Timestamp

FEED

DISP

VIB

TEMP

AMP

PLANT\_RATE

RUN\_STATUS

```



\---



\# 31. Weekly Adapter



Database menyimpan weekly dalam long form:



```text

asset

date

parameter

value

```



Adapter melakukan pivot menjadi struktur yang dibutuhkan engine, misalnya:



```text

Date

DE Radial Vibration (micron)

Lube Oil Water Content (ppm)

Lube Oil Supply Press (barg)

Bearing Metal Temp (°C)

Health Status

Remark

```



Dengan demikian engine tetap menerima struktur yang kompatibel dengan data source yang dibutuhkan.



\---



\# 32. Frontend Data Ownership



Frontend tidak boleh diperlakukan sebagai editor langsung seluruh tabel database.



Pembagian ownership:



```text

USER EDITABLE

│

├── Asset Master

├── Sensor / Tag Configuration

├── Equipment Limits

├── Hourly Measurement

├── Incident

├── RCA

├── RCA Verification

├── CAPA

├── Problem Verification

└── Users





SYSTEM GENERATED

│

├── Weekly Derived Measurement

├── Analysis Run

├── Condition Inference

├── Forecast

├── RCA Match

├── Problem Detection

└── Audit Events

```



System-generated data tidak boleh mempunyai generic CRUD form.



\---



\# 33. Input Navigation



Untuk mempercepat user workflow, menu input tidak perlu mengikuti jumlah tabel database.



Navigation:



```text

Dashboard



Operations

├── Hourly Measurements

└── Weekly Results



Reliability

├── Incidents

├── RCA Workspace

└── CAPA Tracking



Problems

├── Active Problems

├── Problem Verification

└── Follow-up History



Asset Management

├── Assets

├── Sensor / Tag Dictionary

└── Equipment Limits



Administration

└── Users

```



Database normalization tidak harus tercermin langsung sebagai jumlah menu frontend.



\---



\# 34. Reliability UX



Reliability menggunakan konsep \*\*Incident Workspace\*\*, bukan form terpisah untuk setiap tabel.



Flow:



```text

Incident List

&#x20;     │

&#x20;     ▼

Open Incident

&#x20;     │

&#x20;     ▼

┌────────────────────────────────────────────┐

│ Incident Header                            │

├────────────────────────────────────────────┤

│ Overview                                   │

│ RCA                                        │

│ Priority Matrix                            │

│ 4P Verification                            │

│ 4M Verification                            │

│ CAPA                                       │

└────────────────────────────────────────────┘

```



User tidak perlu berpindah menu hanya untuk memasukkan data yang masih terkait dengan `AR No` yang sama.



`AR No` menjadi context identifier utama.



\---



\# 35. Problem Verification UX



Menu Problems berbeda dengan Reliability historical RCA.



```text

Historical Reliability Knowledge

&#x20;         │

&#x20;         ▼

&#x20;intelligence\_engine.py

&#x20;         │

&#x20;         ▼

&#x20;Current RCA Hypothesis

&#x20;         │

&#x20;         ▼

&#x20;    Problem Ticket

&#x20;         │

&#x20;         ▼

&#x20;Operator Verification

```



Problem Verification adalah tempat user memverifikasi \*\*hasil analitik kondisi sekarang\*\*.



Contoh input:



```text

Decision

Operator

Responsible Role



Visible Leakage

Abnormal Noise

Abnormal Vibration

Local Temperature Confirmation



Field Observation

Comment



Action Status

```



Input tersebut bukan RCA historical baru.



Jika investigasi berkembang menjadi formal RCA/incident, proses dapat diarahkan ke Reliability Workspace.



\---



\# 36. Separation of Concepts



Empat konsep berikut tidak boleh digabung:



```text

Equipment Condition

&#x20;       ≠

Ticket State

&#x20;       ≠

Action Status

&#x20;       ≠

Operator Decision

```



Contoh:



```text

Equipment Condition = ALARM



Ticket State = OPEN



Action Status = IN\_PROGRESS



Operator Decision = REQUEST\_ENGINEERING\_REVIEW

```



Perubahan `Action Status` tidak boleh otomatis mengubah `Equipment Condition`.



\---



\# 37. Source Observation vs Derived Data



Database harus membedakan:



```text

SOURCE OBSERVATION

│

├── hourly measurement

├── historical incident

├── historical RCA

└── user verification





DERIVED / ANALYTICAL

│

├── weekly derivation

├── reconstructed signal

├── condition inference

├── forecast

├── RCA similarity

└── KPI

```



Jangan overwrite source observation dengan hasil model.



\---



\# 38. Seeder Rules



Seeder boleh melakukan:



```text

trim whitespace

normalize empty string -> NULL

normalize dates

exact deduplication

column mapping

weekly wide -> long transformation

```



Seeder tidak boleh melakukan:



```text

interpolation

Hampel cleaning

Kalman reconstruction

forecasting

condition classification

RCA inference

automatic engineering correction

```



Semua preprocessing analytical tetap menjadi tanggung jawab engine.



\---



\# 39. Required Validation



Sebelum commit, seeder harus memvalidasi:



```text

Required sheets exist

Required columns exist

Assets identifiable

Hourly timestamps valid

Weekly dates valid

Equipment limits numeric

AR No valid

RCA relations valid

No conflicting metadata duplicate

No orphan asset telemetry

No orphan RCA children

```



Unknown extra column:



```text

DO NOT silently discard

```



Masukkan ke seed report.



\---



\# 40. Historical Seed vs Runtime Data



Gunakan provenance yang jelas.



Initial historical seed:



```text

source\_type = LEGACY\_SEED

```



Manual frontend:



```text

source\_type = MANUAL

```



External integration:



```text

source\_type = API

```



DCS:



```text

source\_type = DCS

```



Derived weekly:



```text

source\_type = DERIVED

```



Dengan ini developer dapat mengetahui asal setiap record.



\---



\# 41. Backend Structure



```text

backend/

│

├── intelligence\_engine.py

│

├── app/

│   ├── api/

│   ├── services/

│   ├── schemas/

│   └── dependencies/

│

├── database/

│   ├── connection.py

│   │

│   ├── models/

│   │   ├── core.py

│   │   ├── telemetry.py

│   │   ├── knowledge.py

│   │   ├── analytics.py

│   │   ├── workflow.py

│   │   ├── iam.py

│   │   └── system.py

│   │

│   ├── repositories/

│   │   ├── asset\_repository.py

│   │   ├── telemetry\_repository.py

│   │   ├── reliability\_repository.py

│   │   ├── analytics\_repository.py

│   │   ├── workflow\_repository.py

│   │   └── user\_repository.py

│   │

│   └── migrations/

│

├── adapters/

│   ├── intelligence\_data\_adapter.py

│   └── excel\_seed\_adapter.py

│

├── services/

│   ├── weekly\_derivation\_service.py

│   ├── intelligence\_service.py

│   ├── problem\_service.py

│   └── reliability\_service.py

│

├── seeders/

│   ├── seed\_from\_excel.py

│   ├── workbook\_reader.py

│   ├── transformers.py

│   ├── validators.py

│   ├── mappings.py

│   └── seed\_report.py

│

└── tests/

&#x20;   ├── test\_seed\_integrity.py

&#x20;   ├── test\_seed\_idempotency.py

&#x20;   ├── test\_excel\_db\_parity.py

&#x20;   ├── test\_engine\_adapter.py

&#x20;   ├── test\_weekly\_derivation.py

&#x20;   ├── test\_rca\_relationship.py

&#x20;   └── test\_workflow\_repository.py

```



\---



\# 42. Implementation Order



Implementasi dilakukan bertahap.



\## Phase 1 — Database Foundation



```text

PostgreSQL

SQLAlchemy

Alembic

Core tables

Telemetry tables

Knowledge tables

```



\## Phase 2 — Seeder



```text

Workbook validation

Core seed

Telemetry seed

Reliability seed

Cross-table validation

Seed report

Idempotency test

```



\## Phase 3 — Intelligence Adapter



```text

PostgreSQL

&#x20;   ↓

Repository

&#x20;   ↓

DataFrame Adapter

&#x20;   ↓

intelligence\_engine.py

```



\## Phase 4 — Engine Parity



Validasi dilakukan dengan membandingkan:



```text

Excel Data

&#x20;    │

&#x20;    ▼

Engine

&#x20;    │

&#x20;    ▼

Result A

```



dengan:



```text

PostgreSQL Data

&#x20;    │

&#x20;    ▼

Adapter

&#x20;    │

&#x20;    ▼

Engine

&#x20;    │

&#x20;    ▼

Result B

```



Target:



```text

Result A ≈ Result B

```



Tujuannya memastikan perpindahan storage tidak mengubah perilaku analytical engine.



\## Phase 5 — Runtime Input



Tambahkan:



```text

Hourly input

Asset management

Reliability input

Problem verification

```



\## Phase 6 — Derived Weekly



Implement:



```text

hourly

&#x20;  ↓

weekly derivation

&#x20;  ↓

weekly\_measurements

```



\## Phase 7 — Analytics Persistence



Persist:



```text

analysis run

condition inference

forecast

RCA matches

```



\## Phase 8 — Vue Integration



Expose REST API untuk frontend Vue.



\---



\# 43. Open Decisions



AI / developer \*\*tidak boleh menentukan sendiri\*\* keputusan berikut.



\## Authentication



Belum diputuskan apakah menggunakan:



```text

internal username/password

OAuth

SSO

LDAP

external auth provider

```



\## Weekly Derivation Formula



Belum ditentukan secara final bagaimana setiap engineering weekly parameter dihitung dari hourly telemetry.



Jangan mengarang aggregation formula.



\## Real-time DCS Integration



Belum diputuskan apakah data masuk melalui:



```text

manual frontend

batch

REST API

PI System

DCS connector

message broker

```



Schema harus mendukung perkembangan tersebut tanpa mengunci implementasi terlalu dini.



\## User Role / Permission Matrix



Role final belum ditentukan.



Jangan membuat permission matrix kompleks sebelum requirement tersedia.



\---



\# 44. Architecture Principle



Implementasi CALI-INI harus mengikuti urutan ownership berikut:



```text

SOURCE DATA

&#x20;   │

&#x20;   ▼

PostgreSQL

&#x20;   │

&#x20;   ▼

Data Adapter

&#x20;   │

&#x20;   ▼

Intelligence Engine

&#x20;   │

&#x20;   ▼

Analytical Results

&#x20;   │

&#x20;   ├── Condition

&#x20;   ├── Forecast

&#x20;   ├── RCA Match

&#x20;   └── KPI

&#x20;   │

&#x20;   ▼

Workflow

&#x20;   │

&#x20;   ▼

Human Verification

&#x20;   │

&#x20;   ▼

Audit Trail

```



Database berfungsi sebagai:



```text

Operational Source of Truth

Historical Knowledge Store

Analytics Result Store

Human Workflow Store

```



`intelligence\_engine.py` berfungsi sebagai:



```text

Analytical Decision Engine

```



Frontend Vue berfungsi sebagai:



```text

Operational Interaction Layer

```



FastAPI berfungsi sebagai:



```text

Application/API Layer

```



\---



\# 45. Instruction for Implementation AI



Dokumen ini harus diperlakukan sebagai \*\*implementation context dan architectural source of truth\*\*.



Ketika mengimplementasikan specification ini:



1\. Jangan rewrite `intelligence\_engine.py`.

2\. Jangan mengubah algoritma analytical yang sudah ada tanpa requirement eksplisit.

3\. PostgreSQL menjadi runtime source of truth.

4\. Excel hanya menjadi historical initial seed.

5\. Pertahankan source data secara lossless.

6\. Gunakan Data Adapter untuk menjaga compatibility dengan engine.

7\. Hourly measurement adalah primary runtime telemetry input.

8\. Historical weekly Excel tetap di-seed untuk compatibility dan parity validation.

9\. Runtime weekly harus berasal dari derivation hourly, bukan manual entry.

10\. Reliability menggunakan Incident / AR No sebagai workspace context.

11\. Problem Verification merupakan human verification terhadap current analytical result.

12\. Historical RCA dan current RCA match harus dipisahkan.

13\. Source observations dan analytical results harus dipisahkan.

14\. Equipment condition, ticket state, action status, dan operator decision harus tetap merupakan konsep berbeda.

15\. Seluruh workflow event penting harus dapat diaudit.

16\. Seeder harus idempotent.

17\. Seeder harus menghasilkan validation/seed report.

18\. Jangan membuang unknown source data secara diam-diam.

19\. Jangan membuat generic CRUD untuk system-generated analytical tables.

20\. Jika terdapat keputusan domain yang belum ditentukan, tandai sebagai \*\*OPEN DECISION\*\* dan jangan mengarang business rule.



Prioritas implementasi:



```text

1\. Data Fidelity

2\. Engine Compatibility

3\. Referential Integrity

4\. Seeder Reliability

5\. Historical / Runtime Provenance

6\. Workflow Auditability

7\. API Usability

8\. Frontend UX

9\. Performance Optimization

10\. Future AI Enhancement

```



Jika terdapat konflik antara desain database yang secara teoritis lebih ideal dan compatibility terhadap `intelligence\_engine.py`:



> \*\*Pertahankan engine compatibility dan isolasi kompromi pada repository / Data Adapter terlebih dahulu.\*\*



Optimasi analytical architecture dilakukan sebagai pekerjaan terpisah setelah database implementation dan engine parity test dinyatakan stabil.

