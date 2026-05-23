from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import models
import database
from routers import auth_routes, alert_routes, admin_routes

# Create DB tables if they don't exist
models.Base.metadata.create_all(bind=database.engine)

from sqlalchemy import text
with database.engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE alerts ADD COLUMN updated_at DATETIME DEFAULT NULL;"))
        conn.commit()
        print("[MIGRATION] Added updated_at column successfully.")
    except Exception as e:
        if "Duplicate column" in str(e) or "1060" in str(e):
            pass
        else:
            print(f"[MIGRATION] Error migrating DB: {e}")


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


# ── Diagnostic endpoints (remove in production) ────────────────────────────
@app.get("/debug/geocode")
def debug_geocode(lat: float = 16.6646, lon: float = 74.2095):
    """
    Test reverse geocoding directly from browser.
    Hit: http://127.0.0.1:8000/debug/geocode?lat=16.6646&lon=74.2095
    """
    import sys
    import io
    from utils.geocoding import reverse_geocode

    # Capture all print output
    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    try:
        result = reverse_geocode(lat, lon)
    except Exception as e:
        result = {"error": str(e)}

    logs = buffer.getvalue()
    sys.stdout = old_stdout

    # Also print to terminal
    print(logs, end="")

    return {
        "input": {"lat": lat, "lon": lon},
        "result": result,
        "logs": logs.split("\n"),
    }

