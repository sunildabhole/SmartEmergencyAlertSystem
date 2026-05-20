from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import models
import database
from routers import auth_routes, alert_routes, admin_routes

# Create DB tables if they don't exist
models.Base.metadata.create_all(bind=database.engine)



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
