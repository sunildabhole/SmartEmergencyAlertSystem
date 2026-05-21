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


@app.get("/debug/geocode/raw")
def debug_geocode_raw(lat: float = 16.6646, lon: float = 74.2095):
    """
    Test raw HTTP connectivity to Nominatim.
    Hit: http://127.0.0.1:8000/debug/geocode/raw
    """
    import urllib.request
    import ssl
    import json as _json

    url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
    headers = {
        "User-Agent": "SmartEmergencyAlertSystem/1.0 (sunildabhole6@gmail.com)",
        "Accept-Language": "en",
        "Accept": "application/json",
    }

    debug_info = {
        "url": url,
        "headers": headers,
        "steps": [],
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        debug_info["steps"].append("✓ Request object created")

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        debug_info["steps"].append("✓ SSL context created (verify=False)")

        resp = urllib.request.urlopen(req, timeout=8, context=context)
        debug_info["steps"].append(f"✓ HTTP response received, status={resp.status}")

        raw = resp.read().decode("utf-8")
        debug_info["steps"].append(f"✓ Body read, length={len(raw)} bytes")
        debug_info["raw_response_preview"] = raw[:1000]

        data = _json.loads(raw)
        debug_info["steps"].append("✓ JSON parsed successfully")
        debug_info["parsed_address"] = data.get("address", {})
        debug_info["display_name"] = data.get("display_name", "N/A")

        if "error" in data:
            debug_info["nominatim_error"] = data["error"]

        resp.close()

    except urllib.error.HTTPError as e:
        debug_info["steps"].append(f"✗ HTTP Error: {e.code} {e.reason}")
        try:
            debug_info["error_body"] = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        debug_info["error"] = f"HTTPError {e.code}"

    except urllib.error.URLError as e:
        debug_info["steps"].append(f"✗ URLError: {e.reason}")
        debug_info["error"] = str(e.reason)

    except TimeoutError:
        debug_info["steps"].append("✗ Timeout after 8 seconds")
        debug_info["error"] = "Timeout"

    except Exception as e:
        debug_info["steps"].append(f"✗ {type(e).__name__}: {str(e)}")
        debug_info["error"] = str(e)

    return debug_info


@app.get("/debug/db")
def debug_db():
    """
    Check if the columns exist in the database for the alerts table.
    """
    import sqlalchemy
    from database import engine

    inspector = sqlalchemy.inspect(engine)
    columns_info = []
    try:
        columns = inspector.get_columns("alerts")
        columns_info = [{"name": c["name"], "type": str(c["type"]), "nullable": c["nullable"]} for c in columns]
        tables = inspector.get_table_names()
    except Exception as e:
        return {"error": str(e)}

    return {
        "tables": tables,
        "alerts_columns": columns_info
    }


@app.get("/debug/last_alert")
def debug_last_alert():
    """
    Inspect the last alert in the database.
    """
    from database import SessionLocal
    import models
    import schemas

    db = SessionLocal()
    try:
        alert = db.query(models.Alert).order_by(models.Alert.id.desc()).first()
        if not alert:
            return {"message": "No alerts found"}

        # Serialize using Pydantic response schema
        pydantic_res = None
        try:
            pydantic_res = schemas.AlertResponse.model_validate(alert).model_dump(mode="json")
        except Exception as ser_err:
            pydantic_res = {"error": f"Serialization failed: {str(ser_err)}"}

        return {
            "alert_id": alert.id,
            "raw_attributes": {
                "full_address": alert.full_address,
                "landmark": alert.landmark,
                "city": alert.city,
                "state": alert.state,
                "country": alert.country,
                "postal_code": alert.postal_code,
                "latitude": alert.latitude,
                "longitude": alert.longitude,
            },
            "serialized_pydantic": pydantic_res
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()
