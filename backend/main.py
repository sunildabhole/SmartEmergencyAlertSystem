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


@app.get("/debug/create_test_alert")
def debug_create_test_alert():
    """
    Diagnostic endpoint to create a temporary test alert and verify geocoding & DB persistence.
    """
    from database import SessionLocal
    import models
    from utils.geocoding import reverse_geocode
    from datetime import datetime, timezone
    
    db = SessionLocal()
    try:
        lat = 16.6646
        lon = 74.2095
        print(f"[DEBUG_TEST_ALERT] Geocoding coordinates: lat={lat}, lon={lon}")
        geo_info = reverse_geocode(lat, lon)
        print(f"[DEBUG_TEST_ALERT] Geocoding success: {geo_info}")
        
        # Find the first user in the DB.
        user = db.query(models.User).first()
        if not user:
            # Create a mock user if none exists
            user = models.User(
                name="Test User",
                email="testuser@example.com",
                hashed_password="fakehashedpassword",
                role="user",
                is_verified=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"[DEBUG_TEST_ALERT] Created temporary user with id={user.id}")

        test_alert = models.Alert(
            user_id=user.id,
            emergency_type="TEST",
            latitude=lat,
            longitude=lon,
            accuracy=10.0,
            last_latitude=lat,
            last_longitude=lon,
            last_location_update=datetime.now(timezone.utc),
            is_moving=False,
            status=models.AlertStatus.PENDING.value
        )
        test_alert.full_address = geo_info.get("full_address")
        test_alert.landmark = geo_info.get("landmark")
        test_alert.city = geo_info.get("city")
        test_alert.state = geo_info.get("state")
        test_alert.country = geo_info.get("country")
        test_alert.postal_code = geo_info.get("postal_code")
        
        db.add(test_alert)
        db.commit()
        db.refresh(test_alert)
        
        print(f"[DEBUG_TEST_ALERT] Saved and verified from DB:\n"
              f"id={test_alert.id}\n"
              f"city={test_alert.city}\n"
              f"state={test_alert.state}\n"
              f"postal_code={test_alert.postal_code}\n"
              f"full_address={test_alert.full_address}")
        
        result = {
            "status": "success",
            "alert_id": test_alert.id,
            "city": test_alert.city,
            "state": test_alert.state,
            "postal_code": test_alert.postal_code,
            "full_address": test_alert.full_address,
            "landmark": test_alert.landmark,
            "country": test_alert.country
        }
        
        # Clean up the test alert so we don't bloat the DB
        db.delete(test_alert)
        db.commit()
        print("[DEBUG_TEST_ALERT] Temporary test alert deleted from DB.")
        
        return result
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        print(f"[DEBUG_TEST_ALERT] Error: {err_msg}")
        return {"error": str(e), "traceback": err_msg.split("\n")}
    finally:
        db.close()


@app.get("/debug/resolve_all")
def debug_resolve_all():
    """
    Diagnostic endpoint to resolve all active (Pending/In Progress) alerts in the database.
    This immediately unlocks the citizen dashboard SOS button.
    """
    from database import SessionLocal
    import models
    
    db = SessionLocal()
    try:
        active_alerts = db.query(models.Alert).filter(
            models.Alert.status.in_([models.AlertStatus.PENDING.value, models.AlertStatus.IN_PROGRESS.value])
        ).all()
        
        count = len(active_alerts)
        for alert in active_alerts:
            alert.status = models.AlertStatus.RESOLVED.value
            
        db.commit()
        print(f"[DEBUG_RESOLVE_ALL] Successfully resolved {count} active alerts.")
        return {"status": "success", "resolved_count": count}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()
