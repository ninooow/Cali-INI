from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, func
from database import Base, is_sqlite, PKBigInteger

SCHEMA = None if is_sqlite else "iam"

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        {"schema": SCHEMA} if SCHEMA else {}
    )

    user_id = Column(PKBigInteger, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(255), nullable=False)
    email = Column(String(255))
    employee_id = Column(String(100))
    role = Column(String(100))
    discipline = Column(String(100))
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
