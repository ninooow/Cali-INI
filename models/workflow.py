from sqlalchemy import Column, BigInteger, String, Text, Numeric, DateTime, Integer, ForeignKey, Index, func
from sqlalchemy.orm import relationship
from database import Base, is_sqlite, PKBigInteger

SCHEMA = None if is_sqlite else "workflow"

class ProblemTicket(Base):
    __tablename__ = "problem_tickets"
    __table_args__ = (
        {"schema": SCHEMA} if SCHEMA else {}
    )

    ticket_id = Column(String(100), primary_key=True)
    asset_id = Column(BigInteger, ForeignKey(f"{'core.' if not is_sqlite else ''}assets.asset_id"), nullable=False)
    opened_at = Column(DateTime(timezone=True), nullable=False)
    last_seen = Column(DateTime(timezone=True))
    condition_state = Column(String(50))
    priority = Column(String(20))
    owner_role = Column(String(255))
    ticket_state = Column(String(100), default="OPEN")
    action_status = Column(String(100), default="NOT_STARTED")
    normal_streak = Column(Integer, nullable=False, default=0)
    matched_rca_ar = Column(String(100))
    evidence_strength = Column(String(100))
    operator_decision = Column(String(100))
    last_operator_name = Column(String(255))
    operator_comment = Column(Text)
    field_observation = Column(Text)
    update_source = Column(String(50), default="ENGINE")
    last_observation_time = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    operator_inputs = relationship("OperatorInput", back_populates="ticket", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="ticket")


class OperatorInput(Base):
    __tablename__ = "operator_inputs"
    __table_args__ = (
        Index("idx_operator_inputs_ticket_time", "ticket_id", "submitted_at"),
        {"schema": SCHEMA} if SCHEMA else {}
    )

    operator_input_id = Column(PKBigInteger, primary_key=True, autoincrement=True)
    asset_id = Column(BigInteger, ForeignKey(f"{'core.' if not is_sqlite else ''}assets.asset_id"), nullable=False)
    ticket_id = Column(String(100), ForeignKey(f"{'workflow.' if not is_sqlite else ''}problem_tickets.ticket_id"))
    decision = Column(String(100))
    operator_name = Column(String(255))
    visible_leakage = Column(String(50))
    abnormal_noise = Column(String(50))
    abnormal_vibration = Column(String(50))
    local_temperature_confirmed = Column(String(50))
    field_observation = Column(Text)
    comment = Column(Text)
    owner_role = Column(String(255))
    action_status = Column(String(100))
    submitted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    ticket = relationship("ProblemTicket", back_populates="operator_inputs")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_ticket_time", "ticket_id", "event_time"),
        {"schema": SCHEMA} if SCHEMA else {}
    )

    audit_id = Column(PKBigInteger, primary_key=True, autoincrement=True)
    event_time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ticket_id = Column(String(100), ForeignKey(f"{'workflow.' if not is_sqlite else ''}problem_tickets.ticket_id"))
    asset_id = Column(BigInteger, ForeignKey(f"{'core.' if not is_sqlite else ''}assets.asset_id"))
    update_source = Column(String(50))
    event_type = Column(String(100))
    previous_ticket_state = Column(String(100))
    new_ticket_state = Column(String(100))
    previous_action_status = Column(String(100))
    new_action_status = Column(String(100))
    operator_decision = Column(String(100))
    operator_name = Column(String(255))
    owner_role = Column(String(255))
    field_observation = Column(Text)
    comment = Column(Text)

    ticket = relationship("ProblemTicket", back_populates="audit_logs")
