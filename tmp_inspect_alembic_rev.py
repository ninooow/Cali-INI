from sqlalchemy import create_engine, text
from config import settings
engine = create_engine(settings.DATABASE_URL)
with engine.connect() as conn:
    result = conn.execute(text('SELECT version_num FROM alembic_version'))
    rows = result.fetchall()
    print('DB REVISION:', rows)
