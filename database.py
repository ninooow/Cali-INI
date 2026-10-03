import os
from sqlalchemy import create_engine, text, event, BigInteger, Integer
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings

DATABASE_URL = settings.DATABASE_URL
is_sqlite = DATABASE_URL.startswith("sqlite")

connect_args = {"check_same_thread": False} if is_sqlite else {}

PKBigInteger = BigInteger().with_variant(Integer, "sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Ensure tables exist when the module is imported (useful for direct SessionLocal usage in tests)
# init_db()  # disabled for import safety

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    # Drop all tables to ensure a clean slate (useful for test isolation)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.drop_all(bind=engine)
    if not is_sqlite:
        schemas = ["core", "telemetry", "knowledge", "analytics", "workflow", "iam", "system"]
        with engine.begin() as conn:
            for s in schemas:
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {s};"))
    # Import all models to ensure they are registered with Base.metadata
    import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
