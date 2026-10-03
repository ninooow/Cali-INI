from sqlalchemy import Column, BigInteger, String, Text, Numeric, DateTime, Boolean, Integer, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from database import Base, is_sqlite, PKBigInteger

SCHEMA = None if is_sqlite else "analytics"

class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        {"schema": SCHEMA} if SCHEMA else {}
    )

    run_id = Column(PKBigInteger, primary_key=True, autoincrement=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True))
    reference_time = Column(DateTime(timezone=True))
    engine_version = Column(String(100))
    runtime_mode = Column(String(50))
    status = Column(String(50), nullable=False)  # 'RUNNING', 'COMPLETED', 'FAILED'
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    condition_inferences = relationship("ConditionInference", back_populates="run", cascade="all, delete-orphan")
    parameter_forecasts = relationship("ParameterForecast", back_populates="run", cascade="all, delete-orphan")
    rca_matches = relationship("RcaMatch", back_populates="run", cascade="all, delete-orphan")


class ConditionInference(Base):
    __tablename__ = "condition_inferences"
    __table_args__ = (
        UniqueConstraint("run_id", "asset_id", name="uq_condition_inferences_run_asset"),
        {"schema": SCHEMA} if SCHEMA else {}
    )

    inference_id = Column(PKBigInteger, primary_key=True, autoincrement=True)
    run_id = Column(BigInteger, ForeignKey(f"{'analytics.' if not is_sqlite else ''}analysis_runs.run_id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(BigInteger, ForeignKey(f"{'core.' if not is_sqlite else ''}assets.asset_id"), nullable=False)
    as_of_time = Column(DateTime(timezone=True), nullable=False)
    overall_state = Column(String(50))
    consequence_class = Column(String(50))
    priority = Column(String(20))
    dominant_symptom = Column(Text)
    health_index = Column(Numeric)
    pca_anomaly_score = Column(Numeric)
    max_zscore = Column(Numeric)
    statistical_available = Column(Boolean)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    run = relationship("AnalysisRun", back_populates="condition_inferences")


class ParameterForecast(Base):
    __tablename__ = "parameter_forecasts"
    __table_args__ = (
        UniqueConstraint("run_id", "asset_id", "canonical_param", "target_time", name="uq_param_forecast_run_asset_param_time"),
        {"schema": SCHEMA} if SCHEMA else {}
    )

    forecast_id = Column(PKBigInteger, primary_key=True, autoincrement=True)
    run_id = Column(BigInteger, ForeignKey(f"{'analytics.' if not is_sqlite else ''}analysis_runs.run_id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(BigInteger, ForeignKey(f"{'core.' if not is_sqlite else ''}assets.asset_id"), nullable=False)
    canonical_param = Column(String(255), nullable=False)
    anchor_time = Column(DateTime(timezone=True))
    target_time = Column(DateTime(timezone=True), nullable=False)
    estimate = Column(Numeric)
    lower_bound = Column(Numeric)
    upper_bound = Column(Numeric)
    source = Column(String(100))
    model_family = Column(String(100))
    model_type = Column(String(100))
    model_quality = Column(String(100))
    mae = Column(Numeric)
    rmse = Column(Numeric)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    run = relationship("AnalysisRun", back_populates="parameter_forecasts")


class RcaMatch(Base):
    __tablename__ = "rca_matches"
    __table_args__ = (
        UniqueConstraint("run_id", "asset_id", "matched_ar_no", name="uq_rca_matches_run_asset_ar"),
        {"schema": SCHEMA} if SCHEMA else {}
    )

    rca_match_id = Column(PKBigInteger, primary_key=True, autoincrement=True)
    run_id = Column(BigInteger, ForeignKey(f"{'analytics.' if not is_sqlite else ''}analysis_runs.run_id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(BigInteger, ForeignKey(f"{'core.' if not is_sqlite else ''}assets.asset_id"), nullable=False)
    matched_ar_no = Column(String(100))
    similarity_score = Column(Numeric)
    evidence_strength = Column(String(100))
    rank_no = Column(Integer)
    current_supporting_evidence = Column(Text)
    historical_verified_evidence = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    run = relationship("AnalysisRun", back_populates="rca_matches")
