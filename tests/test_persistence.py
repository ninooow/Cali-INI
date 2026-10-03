import pytest
from services.intelligence_service import IntelligenceService
from database import SessionLocal
from models.analytics import ConditionInference, ParameterForecast, RcaMatch

def test_persistence_rows():
    db = SessionLocal()
    try:
        result = IntelligenceService.run_analysis(db=db)
        run_id = result["run_id"]
        # Ensure rows were created
        cond_cnt = db.query(ConditionInference).filter(ConditionInference.run_id == run_id).count()
        forecast_cnt = db.query(ParameterForecast).filter(ParameterForecast.run_id == run_id).count()
        rca_cnt = db.query(RcaMatch).filter(RcaMatch.run_id == run_id).count()
        assert cond_cnt > 0, "No condition_inferences rows persisted"
        assert forecast_cnt > 0, "No parameter_forecasts rows persisted"
        assert rca_cnt > 0, "No rca_matches rows persisted"
    finally:
        db.close()
