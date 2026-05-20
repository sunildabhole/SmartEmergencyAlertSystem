from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import models
import database
from routers import auth_routes, alert_routes, admin_routes

# Create DB tables if they don't exist
models.Base.metadata.create_all(bind=database.engine)

# Auto-migrate table columns for MySQL/SQLite if they do not exist
from sqlalchemy import text
try:
    with database.engine.begin() as conn:
        for col_name, col_type in [("accuracy", "DOUBLE"), ("last_accuracy", "DOUBLE"), ("is_moving", "TINYINT(1)")]:
            try:
                conn.execute(text(f"ALTER TABLE alerts ADD COLUMN {col_name} {col_type} DEFAULT NULL;"))
                print(f"[MIGRATION] Added column {col_name} to alerts table.")
            except Exception:
                # Column already exists or another transient DB error, skip safely
                pass
except Exception as e:
    print(f"[MIGRATION] Database auto-migration skipped or failed: {e}")

app = FastAPI(
    title="Smart Emergency Alert System API",
    description="Backend API for managing emergency SOS alerts",
    version="1.0.0"
)

# CORS Middleware Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_routes.router)
app.include_router(alert_routes.router)
app.include_router(admin_routes.router)

@app.get("/")
def root():
    return {"message": "Welcome to Smart Emergency Alert System API"}
