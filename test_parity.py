import sys
import numpy as np
import pandas as pd
from time import perf_counter

from intelligence_engine import run_intelligence_engine
from services.intelligence_service import IntelligenceService
from database import SessionLocal

print("=" * 60, flush=True)
print("1. RUNNING WORKBOOK-BACKED ENGINE", flush=True)
print("=" * 60, flush=True)
t0 = perf_counter()
wb_res = run_intelligence_engine(verbose=False)
print(f"Workbook engine completed in {perf_counter() - t0:.2f}s", flush=True)

print("\n" + "=" * 60, flush=True)
print("2. RUNNING DB-BACKED ENGINE VIA IntelligenceService", flush=True)
print("=" * 60, flush=True)
t1 = perf_counter()
db = SessionLocal()
db_res_wrapper = IntelligenceService.run_analysis(db)
db_res = db_res_wrapper["engine_result"]
print(f"DB-backed engine completed in {perf_counter() - t1:.2f}s", flush=True)

print("\n" + "=" * 60, flush=True)
print("3. COMPARING ASSET RESULTS (PARITY CHECK)", flush=True)
print("=" * 60, flush=True)
mismatches = []
wb_assets = {r["tag_number"]: r for r in wb_res["results"]}
db_assets = {r["tag_number"]: r for r in db_res["results"]}

for tag in wb_assets:
    if tag not in db_assets:
        mismatches.append(f"Missing asset in DB: {tag}")
        continue
    w_a = wb_assets[tag]
    d_a = db_assets[tag]
    
    # Condition
    w_c = w_a.get("condition", {})
    d_c = d_a.get("condition", {})
    for k in ["overall_state", "consequence_class", "priority", "dominant_symptom"]:
        w_v = w_c.get(k) if k in w_c else w_a.get(k)
        d_v = d_c.get(k) if k in d_c else d_a.get(k)
        if w_v != d_v:
            mismatches.append(f"[{tag}] Condition mismatch for {k}: WB={w_v} vs DB={d_v}")
            
    # Health Index & PCA score (numerical)
    w_hi = w_c.get("health_index")
    d_hi = d_c.get("health_index")
    if w_hi is not None and d_hi is not None:
        if abs(float(w_hi) - float(d_hi)) > 1e-4:
            mismatches.append(f"[{tag}] Health index mismatch: WB={w_hi} vs DB={d_hi}")
            
    # RCA Evidence
    w_e = w_a.get("evidence", {})
    d_e = d_a.get("evidence", {})
    if w_e.get("matched_ar") != d_e.get("matched_ar"):
        mismatches.append(f"[{tag}] RCA Matched AR mismatch: WB={w_e.get('matched_ar')} vs DB={d_e.get('matched_ar')}")
    if w_e.get("evidence_strength") != d_e.get("evidence_strength"):
        mismatches.append(f"[{tag}] RCA Evidence strength mismatch: WB={w_e.get('evidence_strength')} vs DB={d_e.get('evidence_strength')}")

    # Ticket
    w_t = w_a.get("ticket", {})
    d_t = d_a.get("ticket", {})
    for tk in ["ticket_required", "ticket_id", "priority", "ticket_state", "action_status"]:
        if w_t.get(tk) != d_t.get(tk):
            mismatches.append(f"[{tag}] Ticket {tk} mismatch: WB={w_t.get(tk)} vs DB={d_t.get(tk)}")

print(f"Total mismatches found: {len(mismatches)}", flush=True)
for m in mismatches:
    print(f"  - {m}", flush=True)

if not mismatches:
    print("\nPARITY RESULT: 100% PERFECT MATCH!", flush=True)
