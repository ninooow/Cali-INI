import sys
sys.path.append(r"d:/KULIAH/SEMESTER 7/Lomba/Cali-INI/calini")

from datetime import datetime
from database import SessionLocal
from services.intelligence_service import IntelligenceService
from models.analytics import AnalysisRun, ConditionInference, ParameterForecast, RcaMatch
from sqlalchemy import func

db = SessionLocal()
try:
    # BEFORE counts
    before = {
        'runs': db.query(func.count(AnalysisRun.run_id)).scalar(),
        'condition_inferences': db.query(func.count(ConditionInference.inference_id)).scalar(),
        'parameter_forecasts': db.query(func.count(ParameterForecast.forecast_id)).scalar(),
        'rca_matches': db.query(func.count(RcaMatch.rca_match_id)).scalar(),
    }
    start = datetime.now()
    result = IntelligenceService.run_analysis(db=db)
    end = datetime.now()
    # AFTER counts
    after = {
        'runs': db.query(func.count(AnalysisRun.run_id)).scalar(),
        'condition_inferences': db.query(func.count(ConditionInference.inference_id)).scalar(),
        'parameter_forecasts': db.query(func.count(ParameterForecast.forecast_id)).scalar(),
        'rca_matches': db.query(func.count(RcaMatch.rca_match_id)).scalar(),
    }
    diffs = {k: after[k] - before[k] for k in before}
    assets_processed = len(result.get('engine_result', {}).get('results', []))
    duration = (end - start).total_seconds()
    print('RUN ID:', result.get('run_id'))
    print('DURATION:', duration)
    print('ASSETS PROCESSED:', assets_processed)
    print('BEFORE -> AFTER:')
    for k in before:
        print(f"{k}: {before[k]} -> {after[k]} (Δ {diffs[k]})")
finally:
    db.close()
