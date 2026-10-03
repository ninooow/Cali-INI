from sqlalchemy import Column, BigInteger, String, Text, Numeric, DateTime, Date, Integer, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from database import Base, is_sqlite, PKBigInteger

SCHEMA = None if is_sqlite else "knowledge"

class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        {"schema": SCHEMA} if SCHEMA else {}
    )

    incident_id = Column(PKBigInteger, primary_key=True, autoincrement=True)
    serial_no = Column(Integer)
    mto_no = Column(String(100))
    ar_no = Column(String(100))
    plant = Column(String(100))
    tag_number = Column(String(100))
    equipment_class = Column(String(100))
    date_of_occurrence = Column(Date)
    risk_case_title = Column(Text)
    highest_impact = Column(String(255))
    pre_risk = Column(String(100))
    risk_score = Column(Numeric)
    pic_rca = Column(String(100))
    overall_status = Column(String(255))
    discipline = Column(String(100))
    equipment_type = Column(String(100))
    component = Column(String(255))
    failure_mechanism = Column(String(255))
    downtime_hours = Column(Numeric)
    actual_loss_kusd = Column(Numeric)
    potential_loss_kusd = Column(Numeric)
    total_loss_kusd = Column(Numeric)
    rca_due_date = Column(Date)
    month_year = Column(String(50))
    source_type = Column(String(50), nullable=False, default="MANUAL")
    source_sheet = Column(String(255))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class RcaHeader(Base):
    __tablename__ = "rca_headers"
    __table_args__ = (
        UniqueConstraint("ar_no", name="uq_rca_headers_ar_no"),
        {"schema": SCHEMA} if SCHEMA else {}
    )

    rca_header_id = Column(PKBigInteger, primary_key=True, autoincrement=True)
    ar_no = Column(String(100), nullable=False, unique=True)
    tag_number = Column(String(100))
    plant = Column(String(100))
    date_occurrence = Column(Date)
    pre_risk = Column(String(100))
    risk_score = Column(Numeric)
    pic_rca = Column(String(100))
    procedure_no = Column(String(100))
    problem_statement = Column(Text)
    root_cause_statement = Column(Text)
    source_type = Column(String(50), nullable=False, default="MANUAL")
    source_sheet = Column(String(255))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    priority_matrix = relationship("RcaPriorityMatrix", back_populates="rca_header", cascade="all, delete-orphan")
    verifications_4p = relationship("Rca4pVerification", back_populates="rca_header", cascade="all, delete-orphan")
    verifications_4m = relationship("Rca4mVerification", back_populates="rca_header", cascade="all, delete-orphan")
    capa_actions = relationship("RcaCapaAction", back_populates="rca_header", cascade="all, delete-orphan")


class RcaPriorityMatrix(Base):
    __tablename__ = "rca_priority_matrix"
    __table_args__ = (
        UniqueConstraint("ar_no", "root_cause_id", name="uq_rca_priority_ar_root_cause"),
        {"schema": SCHEMA} if SCHEMA else {}
    )

    priority_matrix_id = Column(PKBigInteger, primary_key=True, autoincrement=True)
    ar_no = Column(String(100), ForeignKey(f"{'knowledge.' if not is_sqlite else ''}rca_headers.ar_no", ondelete="CASCADE"), nullable=False)
    root_cause_id = Column(String(100), nullable=False)
    impact_level = Column(String(100))
    control_level = Column(String(100))
    priority_rank = Column(Integer)
    description_short = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    rca_header = relationship("RcaHeader", back_populates="priority_matrix")


class Rca4pVerification(Base):
    __tablename__ = "rca_4p_verifications"
    __table_args__ = (
        UniqueConstraint("ar_no", "parameter_id", name="uq_rca_4p_ar_param"),
        {"schema": SCHEMA} if SCHEMA else {}
    )

    verification_id = Column(PKBigInteger, primary_key=True, autoincrement=True)
    ar_no = Column(String(100), ForeignKey(f"{'knowledge.' if not is_sqlite else ''}rca_headers.ar_no", ondelete="CASCADE"), nullable=False)
    parameter_id = Column(String(100), nullable=False)
    problem_phenomenon_parameter = Column(Text)
    result = Column(String(50))
    evidence_finding = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    rca_header = relationship("RcaHeader", back_populates="verifications_4p")


class Rca4mVerification(Base):
    __tablename__ = "rca_4m_verifications"
    __table_args__ = (
        UniqueConstraint("ar_no", "factor_id", name="uq_rca_4m_ar_factor"),
        {"schema": SCHEMA} if SCHEMA else {}
    )

    verification_id = Column(PKBigInteger, primary_key=True, autoincrement=True)
    ar_no = Column(String(100), ForeignKey(f"{'knowledge.' if not is_sqlite else ''}rca_headers.ar_no", ondelete="CASCADE"), nullable=False)
    factor_id = Column(String(100), nullable=False)
    factor_category = Column(Text)
    result = Column(String(50))
    evidence_finding = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    rca_header = relationship("RcaHeader", back_populates="verifications_4m")


class RcaCapaAction(Base):
    __tablename__ = "rca_capa_actions"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_rca_capa_fingerprint"),
        {"schema": SCHEMA} if SCHEMA else {}
    )

    capa_id = Column(PKBigInteger, primary_key=True, autoincrement=True)
    ar_no = Column(String(100), ForeignKey(f"{'knowledge.' if not is_sqlite else ''}rca_headers.ar_no", ondelete="CASCADE"), nullable=False)
    rc = Column(String(100))
    action_type = Column(String(100))
    action_plan = Column(Text, nullable=False)
    target_date = Column(Date)
    pic = Column(String(100))
    status = Column(String(100))
    fingerprint = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    rca_header = relationship("RcaHeader", back_populates="capa_actions")
