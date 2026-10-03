from sqlalchemy import Column, BigInteger, String, DateTime, Integer, JSON, func
from database import Base, is_sqlite, PKBigInteger

SCHEMA = None if is_sqlite else "system"

class SeedRun(Base):
    __tablename__ = "seed_runs"
    __table_args__ = (
        {"schema": SCHEMA} if SCHEMA else {}
    )

    seed_run_id = Column(PKBigInteger, primary_key=True, autoincrement=True)
    source_filename = Column(String(255), nullable=False)
    source_checksum = Column(String(128), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True))
    status = Column(String(50), nullable=False)
    assets_count = Column(Integer)
    metadata_count = Column(Integer)
    sensor_tags_count = Column(Integer)
    equipment_limits_count = Column(Integer)
    hourly_count = Column(Integer)
    weekly_source_rows = Column(Integer)
    weekly_measurements_count = Column(Integer)
    incidents_count = Column(Integer)
    rca_headers_count = Column(Integer)
    rca_priority_count = Column(Integer)
    rca_4p_count = Column(Integer)
    rca_4m_count = Column(Integer)
    rca_capa_count = Column(Integer)
    warnings = Column(JSON)
    errors = Column(JSON)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
