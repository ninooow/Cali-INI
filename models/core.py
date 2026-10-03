from sqlalchemy import Column, BigInteger, String, Text, Boolean, Numeric, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, func, Date
from sqlalchemy.orm import relationship
from database import Base, is_sqlite, PKBigInteger

SCHEMA = None if is_sqlite else "core"

class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint("core_mode IN ('hourly', 'weekly')", name="chk_assets_core_mode"),
        {"schema": SCHEMA} if SCHEMA else {}
    )

    asset_id = Column(PKBigInteger, primary_key=True, autoincrement=True)
    tag_number = Column(String(50), nullable=False, unique=True)
    asset_name = Column(String(255), nullable=False)
    plant_unit = Column(String(255))
    plant_code = Column(String(50))
    equipment_type = Column(String(255))
    equipment_class = Column(String(50))
    discipline = Column(String(50))
    criticality = Column(String(30))
    design_life = Column(Text)
    monitoring_method = Column(Text)
    core_mode = Column(String(20), nullable=False, default="hourly")
    fla_amp = Column(Numeric)
    linked_rca_ar_no = Column(String(100))
    failure_date = Column(Date)
    dominant_failure_mode = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    metadata_items = relationship("AssetMetadata", back_populates="asset", cascade="all, delete-orphan")
    sensor_tags = relationship("SensorTag", back_populates="asset", cascade="all, delete-orphan")
    equipment_limits = relationship("EquipmentLimit", back_populates="asset", cascade="all, delete-orphan")


class AssetMetadata(Base):
    __tablename__ = "asset_metadata"
    __table_args__ = (
        UniqueConstraint("asset_id", "parameter", name="uq_asset_metadata_param"),
        {"schema": SCHEMA} if SCHEMA else {}
    )

    metadata_id = Column(PKBigInteger, primary_key=True, autoincrement=True)
    asset_id = Column(BigInteger, ForeignKey(f"{'core.' if SCHEMA else ''}assets.asset_id", ondelete="CASCADE"), nullable=False)
    parameter = Column(String(255), nullable=False)
    value_text = Column(Text)
    source_sheet = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    asset = relationship("Asset", back_populates="metadata_items")


class SensorTag(Base):
    __tablename__ = "sensor_tags"
    __table_args__ = (
        UniqueConstraint("asset_id", "pi_tag", name="uq_sensor_tags_asset_pi_tag"),
        {"schema": SCHEMA} if SCHEMA else {}
    )

    tag_id = Column(PKBigInteger, primary_key=True, autoincrement=True)
    asset_id = Column(BigInteger, ForeignKey(f"{'core.' if SCHEMA else ''}assets.asset_id", ondelete="CASCADE"), nullable=False)
    pi_tag = Column(String(255), nullable=False)
    canonical_param = Column(String(50))
    name = Column(String(255))
    description = Column(Text)
    digital_set = Column(Text)
    engineering_unit = Column(String(100))
    span = Column(Numeric)
    typical_value = Column(Numeric)
    zero_value = Column(Numeric)
    instrument_tag = Column(String(255))
    is_active = Column(Boolean, nullable=False, default=True)
    source_sheet = Column(String(255))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    asset = relationship("Asset", back_populates="sensor_tags")


class EquipmentLimit(Base):
    __tablename__ = "equipment_limits"
    __table_args__ = (
        UniqueConstraint("asset_id", "parameter", "effective_from", name="uq_equipment_limits_asset_param_from"),
        CheckConstraint("alarm_limit != trip_limit", name="chk_equipment_limits_alarm_trip_diff"),
        {"schema": SCHEMA} if SCHEMA else {}
    )

    limit_id = Column(PKBigInteger, primary_key=True, autoincrement=True)
    asset_id = Column(BigInteger, ForeignKey(f"{'core.' if SCHEMA else ''}assets.asset_id", ondelete="CASCADE"), nullable=False)
    parameter = Column(String(255), nullable=False)
    unit = Column(String(100))
    alarm_limit = Column(Numeric, nullable=False)
    trip_limit = Column(Numeric, nullable=False)
    effective_from = Column(DateTime(timezone=True))
    effective_to = Column(DateTime(timezone=True))
    source_sheet = Column(String(255))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    asset = relationship("Asset", back_populates="equipment_limits")
