import sqlalchemy
from database import engine

alter_statements = [
    "ALTER TABLE users ADD COLUMN phone VARCHAR(20) UNIQUE NULL;",
    "ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE alerts ADD COLUMN last_latitude FLOAT NULL;",
    "ALTER TABLE alerts ADD COLUMN last_longitude FLOAT NULL;",
    "ALTER TABLE alerts ADD COLUMN last_location_update DATETIME NULL;"
]

with engine.connect() as conn:
    for stmt in alter_statements:
        try:
            conn.execute(sqlalchemy.text(stmt))
            print(f"Executed: {stmt}")
        except sqlalchemy.exc.OperationalError as e:
            if 'Duplicate column name' in str(e):
                print(f"Skipped (already exists): {stmt}")
            else:
                print(f"Error executing {stmt}: {e}")
    conn.commit()

print("Database schema update completed.")
