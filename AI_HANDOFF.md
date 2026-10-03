# CALI-INI Backend — AI Handoff

> Dokumen ini adalah checkpoint ringkas untuk coding agent.
> Gunakan file ini untuk melanjutkan pekerjaan tanpa membaca ulang seluruh chat atau seluruh dokumentasi project.

---

## 1. Current Goal

Migrasi backend CALI-INI dari runtime berbasis spreadsheet/CSV menuju database-backed backend dengan perubahan seminimal mungkin terhadap analytical logic di `intelligence_engine.py`.

Target arsitektur:

```text
Vue Frontend
     ↓
FastAPI
     ↓
Service Layer
     ↓
Database
     ↕
Engine Adapter
     ↓
intelligence_engine.py
```

Spreadsheet tetap digunakan sebagai initial seed/reference untuk validasi migrasi.

---

# 2. Source Documents

Dokumen project yang tersedia:

```text
01_DATABASE_AND_SEEDER.md
02_ENGINE_INTEGRATION.md
03_API_SPEC.md
```

Source utama existing:

```text
All_Case_Data.xlsx
intelligence_engine.py
requirements.txt
```

Jangan membaca seluruh dokumen/file besar secara otomatis.

Gunakan `AI_HANDOFF.md` sebagai entry point.

Buka specification hanya ketika informasi yang diperlukan tidak tersedia di file ini.

Untuk `intelligence_engine.py`, search symbol/function terlebih dahulu dan baca hanya bagian yang relevan.

---

# 3. CONFIRMED — Work Already Performed

Berdasarkan execution log terakhir, pekerjaan berikut sudah dilakukan.

## 3.1 Backend dependencies

Command berikut telah dijalankan:

```text
pip install sqlalchemy fastapi uvicorn pydantic psycopg2-binary
```

Status instalasi akhir setiap package tidak dicatat secara lengkap dalam handoff ini.

Periksa hanya jika dependency error muncul.

---

## 3.2 Database foundation

File berikut telah dibuat:

```text
config.py
database.py
```

Database initialization pernah berhasil dijalankan menggunakan:

```text
from database import init_db
init_db()
```

dengan output:

```text
DB Initialized successfully!
```

---

## 3.3 Database models

File/model berikut telah dibuat:

```text
core.py
telemetry.py
knowledge.py
analytics.py
workflow.py
iam.py
system.py
__init__.py
```

Beberapa file tersebut kemudian diedit selama proses debugging/seeding.

Jangan membuat ulang model tanpa terlebih dahulu menginspeksi implementasi existing.

---

# 4. Seeder Status

File berikut telah dibuat:

```text
seeder.py
```

Seeder telah dijalankan beberapa kali.

Development database `calini.db` juga pernah dihapus dan dibangun ulang sebelum proses seeding.

## Confirmed investigation

Agent telah memeriksa `Incident Record`, termasuk:

```text
Total rows
Unique AR
Duplicated AR
```

Agent juga membandingkan AR dari:

```text
Incident Record
RCA Header
```

dan melakukan investigasi terhadap duplicate AR.

Setelah investigasi tersebut, perubahan dilakukan pada:

```text
knowledge.py
seeder.py
```

Log terakhir menyebut:

```text
Running parity test with full 380 incidents seeded...
```

Ini menunjukkan seeder telah diubah untuk memasukkan 380 incident records pada test terakhir.

## Important

Jangan menyimpulkan bahwa seluruh spreadsheet → database mapping sudah 100% tervalidasi hanya dari informasi di atas.

Belum tersedia final validation report yang membuktikan seluruh domain memiliki row/value parity.

Status:

```text
SEEDER IMPLEMENTED: YES
SEEDER EXECUTED: YES
380 INCIDENT SEED ATTEMPT: YES
FULL SEED PARITY CONFIRMED: NO FINAL REPORT AVAILABLE
```

---

# 5. Engine Integration Status

File berikut telah dibuat:

```text
engine_adapter.py
```

Agent telah membaca dan mengubah bagian tertentu dari:

```text
intelligence_engine.py
```

Tujuan perubahan adalah memungkinkan engine menggunakan data dari database melalui adapter dengan perubahan seminimal mungkin terhadap analytical core.

File berikut juga telah dibuat:

```text
intelligence_service.py
```

atau berada pada service path yang digunakan melalui import:

```python
from services.intelligence_service import IntelligenceService
```

Agent pernah menjalankan:

```python
IntelligenceService.run_analysis()
```

dan kemudian menjalankan versi dengan database session:

```python
db = SessionLocal()
IntelligenceService.run_analysis(db)
```

Namun tidak terdapat final output pada log yang diberikan yang cukup untuk menyatakan DB-backed engine run sudah tervalidasi sepenuhnya.

Status:

```text
ENGINE ADAPTER CREATED: YES
INTELLIGENCE SERVICE CREATED: YES
INTELLIGENCE ENGINE MODIFIED: YES
DB-BACKED EXECUTION ATTEMPTED: YES
DB-BACKED EXECUTION FINAL PASS: NOT CONFIRMED
```

---

# 6. Current Parity Validation

File berikut telah dibuat:

```text
test_parity.py
```

Tujuan test:

```text
Workbook
   ↓
intelligence_engine
   ↓
Workbook Result
          \
           → Compare
          /
Database
   ↓
EngineDataAdapter / IntelligenceService
   ↓
intelligence_engine
   ↓
Database Result
```

Parity script yang terlihat pada log membandingkan beberapa output per asset.

## Condition

```text
overall_state
consequence_class
priority
dominant_symptom
```

## Numerical

```text
health_index
```

dengan tolerance:

```text
1e-4
```

## RCA

```text
matched_ar
evidence_strength
```

Script juga memeriksa asset yang hilang dari DB-backed result.

---

# 7. Parity Tasks Already Started

Parity execution telah dilakukan lebih dari sekali.

## First known run

```text
python test_parity.py
```

Associated task:

```text
task-373
```

Agent melakukan polling berulang terhadap task ini.

Agent kemudian membaca:

```text
task-373.log
```

Tidak ada final PASS/FAIL dari task-373 pada log yang tersedia.

---

## Second known run

`test_parity.py` kemudian dibuat/diubah kembali dan dijalankan menggunakan:

```text
python -u test_parity.py
```

Associated task:

```text
task-466
```

Log terakhir:

```text
DB-backed engine execution in progress, waiting for parity comparison...
Waiting for parity comparison result...
```

Tidak ada final output task-466 pada context yang tersedia.

Therefore:

```text
PARITY STATUS: IN PROGRESS / UNKNOWN FINAL RESULT
```

Jangan mengklaim:

```text
PARITY PASS
```

atau:

```text
PARITY FAIL
```

sebelum membaca existing task/log/output.

---

# 8. Files Known to Have Been Changed

Berdasarkan execution log:

```text
config.py
database.py

core.py
telemetry.py
knowledge.py
analytics.py
workflow.py
iam.py
system.py
__init__.py

seeder.py
engine_adapter.py
intelligence_engine.py
intelligence_service.py / services/intelligence_service.py
test_parity.py
```

Daftar ini berasal dari log.

Gunakan `git status` / `git diff` untuk menentukan actual repository state.

---

# 9. DO NOT ASSUME

Belum ada bukti final pada context ini bahwa:

- full spreadsheet/database parity sudah PASS;
- DB-backed intelligence engine sudah final PASS;
- workbook-vs-database analytical parity sudah PASS;
- analytical result persistence sudah selesai;
- FastAPI application sudah dibuat;
- REST API endpoint sudah dibuat;
- authentication sudah dibuat;
- Vue integration sudah dibuat;
- workflow API sudah dibuat;
- PostgreSQL production runtime sudah diuji;
- hourly → weekly derivation sudah diimplementasikan.

Jangan menandai item tersebut selesai tanpa memeriksa repository/test result.

---

# 10. Current Stop Point

Pekerjaan terakhir berada pada:

```text
Database
   ↓
Engine Adapter
   ↓
IntelligenceService
   ↓
intelligence_engine.py
   ↓
Parity Validation
```

Bukan pada FastAPI development.

Current blocking question:

```text
Apakah database-backed analytical execution menghasilkan output yang equivalent dengan workbook-backed execution?
```

Final answer belum tersedia dari log terakhir.

---

# 11. NEXT ACTION — TOKEN-EFFICIENT RECOVERY

Agent berikutnya JANGAN langsung menjalankan engine.

Lakukan hanya:

```text
1. Read AI_HANDOFF.md.
2. Inspect git status/diff.
3. Check existing task-373/task-466 logs/results if accessible.
4. Determine whether parity execution completed.
5. Report existing result.
```

Do NOT:

```text
- rerun test_parity.py;
- rerun intelligence_engine;
- rerun seeder;
- rebuild database;
- start FastAPI;
- reread all specification documents.
```

Jika task/log sudah memiliki final result, gunakan hasil tersebut.

---

# 12. If Existing Parity Result Is Missing

Jika task-373/task-466 tidak menghasilkan final result, jangan menjalankan dual-engine parity dengan pola lama.

Gunakan strategi terpisah:

```text
STEP A

Workbook
   ↓
Engine
   ↓
saved workbook baseline
   ↓
STOP
```

Kemudian pada execution terpisah:

```text
STEP B

Database
   ↓
Adapter
   ↓
Engine
   ↓
saved database result
   ↓
STOP
```

Kemudian:

```text
STEP C

saved workbook baseline
          +
saved database result
          ↓
      parity compare
          ↓
    PASS / MISMATCH
```

Tujuan:

- engine berat tidak perlu dijalankan dua kali dalam satu agent task;
- agent tidak perlu polling terus;
- result dapat digunakan kembali;
- failure dapat dilanjutkan dari checkpoint;
- penggunaan token lebih rendah.

---

# 13. Parity Validation Scope

Current parity script hanya diketahui membandingkan:

```text
asset presence
overall_state
consequence_class
priority
dominant_symptom
health_index
matched RCA AR
RCA evidence strength
```

Jika test tersebut PASS, tuliskan sebagai:

```text
CORE PARITY: PASS
```

Jangan menyebut:

```text
FULL ENGINE PARITY: PASS
```

kecuali output lain juga benar-benar sudah dibandingkan.

Extended parity dapat dilakukan kemudian terhadap output penting seperti forecast/model/validation/data-quality jika memang dibutuhkan.

Jangan menjalankan extended parity sebelum core parity selesai.

---

# 14. Backend Work Remaining

Item berikut belum boleh dianggap selesai berdasarkan context yang tersedia.

## Gate A — Database / Engine Validation

```text
[ ] Confirm final seeder validation
[ ] Confirm DB-backed engine execution
[ ] Confirm core parity
```

Gate ini harus diselesaikan sebelum architectural work berikutnya.

---

## Gate B — Analysis Result Persistence

Setelah Gate A selesai, implementasikan persistence untuk analytical run/result sesuai project specification.

Jangan mulai sebelum diminta.

---

## Gate C — FastAPI

Setelah persistence/service integration stabil:

```text
FastAPI foundation
REST endpoints
source-data endpoints
analytics endpoints
reliability endpoints
problem/workflow endpoints
```

Ikuti `03_API_SPEC.md`.

Jangan implement seluruh API dalam satu agent session.

---

## Gate D — Backend Integration

Setelah API tersedia:

```text
API
 ↓
Service
 ↓
Repository / Database
 ↓
Engine when explicitly triggered
```

Kemudian lakukan backend integration tests.

---

## Gate E — Vue Contract

Tahap akhir backend:

```text
Vue
 ↓
FastAPI
 ↓
Backend
```

Frontend tidak boleh mengakses database atau `intelligence_engine.py` secara langsung.

---

# 15. Token-Efficiency Rules

Semua coding agent berikutnya harus mengikuti aturan ini.

## Rule 1 — Read this file first

Mulai dari:

```text
AI_HANDOFF.md
```

Jangan otomatis membaca seluruh:

```text
01_DATABASE_AND_SEEDER.md
02_ENGINE_INTEGRATION.md
03_API_SPEC.md
intelligence_engine.py
```

---

## Rule 2 — Search before reading

Untuk file besar seperti:

```text
intelligence_engine.py
```

search function/symbol terlebih dahulu.

Baca hanya relevant line range.

---

## Rule 3 — One milestone per session

Contoh:

```text
GOOD:
"Confirm parity."

BAD:
"Confirm parity, implement persistence, FastAPI, authentication and API."
```

---

## Rule 4 — No aggressive polling

Untuk command yang lama:

```text
run command
↓
allow execution
↓
inspect final output
```

Jangan melakukan loop:

```text
wait
poll
wait
poll
view unrelated file
poll
wait
poll
```

---

## Rule 5 — Separate expensive computation

Jangan menjalankan workbook engine + DB engine berulang kali dalam satu development loop.

Persist test artifacts/baselines bila memungkinkan.

---

## Rule 6 — Update handoff before expensive work

Sebelum long-running command, update:

```text
Current task
Command
Expected output
Next action
```

di `AI_HANDOFF.md`.

Dengan demikian jika agent terkena limit, agent berikutnya mengetahui state terakhir.

---

## Rule 7 — Update handoff after milestone

Setelah milestone selesai, update hanya:

```text
Status
Result
Files changed
Next task
Blockers
```

Jangan menulis laporan panjang.

---

# 16. Required Agent Reporting Format

Setelah task selesai, jangan membuat penjelasan panjang.

Gunakan:

```text
STATUS:
PASS / FAIL / BLOCKED

DONE:
- ...

VALIDATION:
- ...

CHANGED:
- ...

BLOCKER:
- none / ...

NEXT:
- ...
```

Maksimal beberapa bullet kecuali user meminta detail.

---

# 17. Recommended Prompt for Next Agent

Gunakan prompt pendek berikut:

```text
Read AI_HANDOFF.md and inspect current git status/diff.

Recover the existing parity-test status only.
Check existing task/log output before running anything.

Do not rerun the engine, seeder, or parity test.
Do not start FastAPI.

If a final parity result exists, report it.
If not, report exactly where execution stopped and recommend the smallest next action.

Keep the response short.
```

---

# 18. Project Principle

Prinsip utama migrasi:

```text
Change the data source and backend architecture,
not the analytical meaning of intelligence_engine.py.
```

Prioritas:

```text
Database correctness
        ↓
Engine compatibility
        ↓
Parity validation
        ↓
Result persistence
        ↓
FastAPI
        ↓
Vue integration
```

Do not skip validation gates merely to progress faster.