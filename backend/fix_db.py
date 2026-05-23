import sqlalchemy
from database import engine

alter_statements = [
    # Users table columns
    "ALTER TABLE users ADD COLUMN phone VARCHAR(20) UNIQUE NULL;",
    "ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT FALSE;",
    
    # Alerts table columns
    "ALTER TABLE alerts ADD COLUMN last_latitude DOUBLE DEFAULT NULL;",
    "ALTER TABLE alerts ADD COLUMN last_longitude DOUBLE DEFAULT NULL;",
    "ALTER TABLE alerts ADD COLUMN last_location_update DATETIME DEFAULT NULL;",
    "ALTER TABLE alerts ADD COLUMN updated_at DATETIME DEFAULT NULL;",
    "ALTER TABLE alerts ADD COLUMN accuracy DOUBLE DEFAULT NULL;",
    "ALTER TABLE alerts ADD COLUMN last_accuracy DOUBLE DEFAULT NULL;",
    "ALTER TABLE alerts ADD COLUMN is_moving BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE alerts ADD COLUMN full_address TEXT DEFAULT NULL;",
    "ALTER TABLE alerts ADD COLUMN landmark VARCHAR(255) DEFAULT NULL;",
    "ALTER TABLE alerts ADD COLUMN city VARCHAR(100) DEFAULT NULL;",
    "ALTER TABLE alerts ADD COLUMN state VARCHAR(100) DEFAULT NULL;",
    "ALTER TABLE alerts ADD COLUMN country VARCHAR(100) DEFAULT NULL;",
    "ALTER TABLE alerts ADD COLUMN postal_code VARCHAR(20) DEFAULT NULL;"
]

# Create otp_records table if not exists
create_otp_table = """
CREATE TABLE IF NOT EXISTS otp_records (
  id           INT PRIMARY KEY AUTO_INCREMENT,
  user_id      INT NOT NULL,
  otp_code     VARCHAR(6) NOT NULL,
  purpose      VARCHAR(20) NOT NULL,
  is_used      TINYINT(1) NOT NULL DEFAULT 0,
  expires_at   DATETIME NOT NULL,
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_user_purpose (user_id, purpose),
  INDEX idx_expires (expires_at)
);
"""

print("Connecting to the database to perform schema updates...")
with engine.connect() as conn:
    # 1. Create otp_records if missing
    try:
        conn.execute(sqlalchemy.text(create_otp_table))
        print("Ensured otp_records table exists.")
    except Exception as e:
        print(f"Error checking/creating otp_records: {e}")

    # 2. Add columns to users and alerts tables
    for stmt in alter_statements:
        try:
            conn.execute(sqlalchemy.text(stmt))
            print(f"Executed successfully: {stmt}")
        except sqlalchemy.exc.OperationalError as e:
            # Catch 1060 (Duplicate column name) safely
            if '1060' in str(e) or 'Duplicate column' in str(e):
                print(f"Column already exists, skipped: {stmt}")
            else:
                print(f"Error executing statement: {stmt}\nDetails: {e}")
        except Exception as e:
            print(f"Unhandled error for: {stmt}\nDetails: {e}")

    # 3. Mark all existing users as verified
    try:
        conn.execute(sqlalchemy.text("UPDATE users SET is_verified = 1 WHERE is_verified = 0;"))
        print("Marked existing users as verified.")
    except Exception as e:
        print(f"Error updating is_verified: {e}")

    conn.commit()

print("\nDatabase schema migration completed successfully!")
