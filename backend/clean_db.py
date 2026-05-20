import sqlalchemy
from database import engine

def clean_database():
    print("Connecting to the database...")
    tables = ["otp_records", "alerts", "users"]
    
    with engine.connect() as conn:
        print("Disabling foreign key checks...")
        conn.execute(sqlalchemy.text("SET FOREIGN_KEY_CHECKS = 0;"))
        
        for table in tables:
            try:
                print(f"Truncating table: {table}...")
                conn.execute(sqlalchemy.text(f"TRUNCATE TABLE {table};"))
                print(f"Successfully truncated: {table}")
            except Exception as e:
                print(f"Truncate failed for {table}, attempting DELETE FROM instead. Error: {e}")
                try:
                    conn.execute(sqlalchemy.text(f"DELETE FROM {table};"))
                    print(f"Successfully deleted all records from: {table}")
                except Exception as ex:
                    print(f"Failed to clean table {table}: {ex}")
                    
        print("Enabling foreign key checks...")
        conn.execute(sqlalchemy.text("SET FOREIGN_KEY_CHECKS = 1;"))
        conn.commit()
        
    print("\nDatabase cleanup complete! All registered users, alerts, and emails have been deleted.")

if __name__ == "__main__":
    clean_database()
