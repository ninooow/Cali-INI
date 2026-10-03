from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from database import SessionLocal
from adapters.engine_adapter import EngineDataAdapter
from intelligence_engine import run_intelligence_engine
from models.analytics import AnalysisRun, ConditionInference, ParameterForecast, RcaMatch

class IntelligenceService:
    """Service to execute the analytical engine using data loaded from database and persist results."""

    @classmethod
    def run_analysis(cls, db: Optional[Session] = None) -> Dict[str, Any]:
        should_close = False
        if db is None:
            db = SessionLocal()
            should_close = True

        try:
            started_at = datetime.now()

            # 1. Load data from PostgreSQL via Adapter
            workbook_data = EngineDataAdapter.load_engine_input_data(db)
            op_inputs_df = EngineDataAdapter.load_operator_inputs_df(db)
            ticket_history_df = EngineDataAdapter.load_problem_tickets_df(db)

            table_overrides = {
                "operator_inputs": op_inputs_df,
                "ticket_history": ticket_history_df
            }

            # 2. Run the intelligence engine in-memory
            engine_result = run_intelligence_engine(
                workbook_data=workbook_data,
                global_tables_override=table_overrides,
                export_artifacts=False,
                generate_audit_plots=False,
                run_historical_replay=False,
                verbose=False
            )

            # 3. Persist AnalysisRun and results back to DB
            run = EngineDataAdapter.persist_analysis_results(
                db=db,
                engine_result=engine_result,
                started_at=started_at
            )

            return {
                "run_id": run.run_id,
                "status": run.status,
                "started_at": run.started_at,
                "completed_at": run.completed_at,
                "engine_result": engine_result
            }

        finally:
            if should_close:
                db.close()

    @classmethod
    def get_latest_run(cls, db: Session) -> Optional[AnalysisRun]:
        return db.query(AnalysisRun).filter(AnalysisRun.status == "COMPLETED").order_by(AnalysisRun.run_id.desc()).first()
