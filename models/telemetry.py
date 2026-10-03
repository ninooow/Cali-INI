from sqlalchemy import Column, BigInteger, String, Text, Numeric, DateTime, Date, Integer, ForeignKey, UniqueConstraint, CheckConstraint, func, Index
from sqlalchemy.orm import relationship
from database import Base, is_sqlite, PKBigInteger

SCHEMA = None if is_sqlite else "telemetry"

class HourlyMeasurement(Base):
    __tablename__ = "hourly_measurements"
    __table_args__ = (
        CheckConstraint("run_status IS NULL OR run_status IN ('ON', 'OFF', 'UNKNOWN')", name="chk_hourly_run_status"),
        Index("idx_hourly_asset_time", "asset_id", "measured_at"),
        {"schema": SCHEMA} if SCHEMA else {}
    )

    asset_id = Column(BigInteger, ForeignKey(f"{'core.' if not is_sqlite else ''}assets.asset_id"), primary_key=True)
    measured_at = Column(DateTime(timezone=True), primary_key=True)
    feed = Column(Numeric)
    disp = Column(Numeric)
    vib = Column(Numeric)
    temp = Column(Numeric)
    amp = Column(Numeric)
    plant_rate = Column(Numeric)
    run_status = Column(String(20))
    source_type = Column(String(50), nullable=False, default="MANUAL")
    source_sheet = Column(String(255))
    created_by = Column(BigInteger)
    imported_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class WeeklyMeasurement(Base):
    __tablename__ = "weekly_measurements"
    __table_args__ = (
        UniqueConstraint("asset_id", "record_date", "parameter", "source_type", name="uq_weekly_asset_date_param_source"),
        Index("idx_weekly_asset_date", "asset_id", "record_date"),
        {"schema": SCHEMA} if SCHEMA else {}
    )

    weekly_measurement_id = Column(PKBigInteger, primary_key=True, autoincrement=True)
    asset_id = Column(BigInteger, ForeignKey(f"{'core.' if not is_sqlite else ''}assets.asset_id"), nullable=False)
    week_no = Column(Integer)
    record_date = Column(Date, nullable=False)
    parameter = Column(String(255), nullable=False)
    measured_value = Column(Numeric)
    unit = Column(String(100))
    health_status = Column(String(100))
    remark = Column(Text)
    source_type = Column(String(50), nullable=False, default="LEGACY_SEED")
    derivation_method = Column(String(100))
    derivation_version = Column(String(50))
    period_start = Column(DateTime(timezone=True))
    period_end = Column(DateTime(timezone=True))
    source_column = Column(String(255))
    source_sheet = Column(String(255))
    generated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
