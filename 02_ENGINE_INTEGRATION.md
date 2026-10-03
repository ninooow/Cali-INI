## Engine Execution Strategy

CALI-INI menggunakan **snapshot-based analytical execution**.

`intelligence_engine.py` tidak dijalankan pada setiap dashboard request atau setiap perubahan UI.

Analytical engine dijalankan sebagai satu analysis run terhadap source data yang tersedia sampai suatu analysis reference time.

```text
Source Data
    │
    ▼
PostgreSQL
    │
    ▼
Analysis Trigger
    │
    ▼
IntelligenceService
    │
    ▼
Engine Data Adapter
    │
    ▼
intelligence_engine.py
    │
    ▼
Analysis Snapshot
    │
    ▼
PostgreSQL
    │
    ▼
FastAPI
    │
    ▼
Vue Dashboard
```

### Development / Initial Deployment

Pada fase development dan initial deployment, analysis dijalankan menggunakan explicit/manual trigger.

Contoh API:

```text
POST /api/v1/analytics/runs
```

API hanya bertanggung jawab memulai analysis.

Execution dilakukan melalui:

```text
IntelligenceService.run_analysis()
```

### Production Evolution

`IntelligenceService.run_analysis()` tidak boleh bergantung pada HTTP request sehingga pada tahap berikutnya dapat dipanggil oleh:

```text
Manual Trigger
Scheduled Job
Background Worker
Telemetry Batch Completion
```

tanpa mengubah analytical engine.

### Dashboard Read Rule

Dashboard tidak menjalankan intelligence engine.

Dashboard membaca latest successful persisted analysis.

```text
Vue
 ↓
FastAPI
 ↓
Latest Successful Analysis
 ↓
PostgreSQL
```

### Input Write Rule

Input data seperti hourly telemetry tidak otomatis menjalankan seluruh engine untuk setiap row yang ditambahkan.

```text
User Input
    ↓
Validation
    ↓
PostgreSQL
```

Analysis dilakukan setelah data yang dibutuhkan untuk snapshot tersedia dan analysis trigger dijalankan.

### Runtime Mode

Initial database-backed implementation mempertahankan:

```text
RUNTIME_MODE = SNAPSHOT
```

Mode `LIVE` tidak digunakan sampai terdapat requirement dan integration yang jelas untuk automatic/live telemetry ingestion.

### Important Constraint

Jangan menjalankan `intelligence_engine.py` pada:

```text
GET dashboard
GET asset detail
GET forecast
GET problems
filter changes
pagination
sorting
operator comment update
```

Endpoint tersebut membaca persisted state/result.

Analytical engine hanya dijalankan melalui analytical execution workflow.