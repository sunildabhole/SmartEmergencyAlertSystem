from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import models
import database
from routers import auth_routes, alert_routes, admin_routes

# Create DB tables if they don't exist
models.Base.metadata.create_all(bind=database.engine)

from sqlalchemy import inspect, text
try:
    inspector = inspect(database.engine)
    columns = [col["name"] for col in inspector.get_columns("alerts")]
    if "updated_at" not in columns:
        with database.engine.connect() as conn:
            conn.execute(text("ALTER TABLE alerts ADD COLUMN updated_at DATETIME DEFAULT NULL;"))
            conn.commit()
            print("[MIGRATION] Added updated_at column successfully.")
except Exception as e:
    print(f"[MIGRATION] Error performing database schema inspection/migration: {e}")


app = FastAPI(
    title="Smart Emergency Alert System API",
    description="Backend API for managing emergency SOS alerts",
    version="1.0.0"
)

from config import settings

# CORS Middleware Setup
origins = [origin.strip() for origin in settings.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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

