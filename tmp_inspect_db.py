import os
from sqlalchemy import create_engine, inspect
from config import settings
engine = create_engine(settings.DATABASE_URL)
ins = inspect(engine)
schemas = ins.get_schema_names()
print('SCHEMAS:', schemas)
for schema in schemas:
    if schema.startswith('pg_') or schema == 'information_schema':
        continue
    tables = ins.get_table_names(schema=schema)
    print(f'Schema {schema} tables: {tables}')
