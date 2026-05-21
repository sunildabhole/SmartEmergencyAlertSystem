"""
Alert routes – enhanced with live location update endpoint.

New endpoint
────────────
PUT /alerts/{alert_id}/location
  • Called every ~10 s by the frontend while the user has an active (Pending /
    In Progress) alert.
  • Updates last_latitude, last_longitude, last_location_update on the alert.
  • Admins see this in real time via their 5-second polling loop.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List
import schemas, models, database, auth
import math
from utils.geocoding import reverse_geocode

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees) in meters.
    """
    if None in (lat1, lon1, lat2, lon2):
        return 0.0
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    r = 6371000.0 # Radius of earth in meters
    return c * r

router = APIRouter(prefix="/alerts", tags=["Alerts"])


# ──────────────────────────────────────────────────────────────────────────────
# CREATE ALERT
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/", response_model=schemas.AlertResponse, status_code=status.HTTP_201_CREATED)
def create_alert(
    alert: schemas.AlertCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    # Prevent duplicate active alerts
    active_alert = db.query(models.Alert).filter(
        models.Alert.user_id == current_user.id,
        models.Alert.status.in_([models.AlertStatus.PENDING, models.AlertStatus.IN_PROGRESS])
    ).first()
    if active_alert:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an active emergency alert."
        )

    try:
        # Perform initial reverse geocoding (isolated so it never blocks alert creation)
        try:
            geo_info = reverse_geocode(alert.latitude, alert.longitude)
            print(f"[CREATE_ALERT] Geocoding result: city={geo_info.get('city')}, "
                  f"state={geo_info.get('state')}, landmark={geo_info.get('landmark')}, "
                  f"postal_code={geo_info.get('postal_code')}, "
                  f"full_address={geo_info.get('full_address', '')[:80]}")
        except Exception as geo_err:
            print(f"[CREATE_ALERT] Geocoding completely failed: {geo_err}")
            geo_info = {
                "full_address": "Address unavailable",
                "landmark": None, "city": None, "state": None,
                "country": None, "postal_code": None
            }
        
        new_alert = models.Alert(
            user_id=current_user.id,
            emergency_type=alert.emergency_type,
            latitude=alert.latitude,
            longitude=alert.longitude,
            accuracy=alert.accuracy,
            last_latitude=alert.latitude,
            last_longitude=alert.longitude,
            last_accuracy=alert.accuracy,
            last_location_update=datetime.now(timezone.utc),
            is_moving=False,
            status=models.AlertStatus.PENDING
        )

        # Explicitly save ALL address fields into Alert model
        new_alert.full_address = geo_info.get("full_address")
        new_alert.landmark = geo_info.get("landmark")
        new_alert.city = geo_info.get("city")
        new_alert.state = geo_info.get("state")
        new_alert.country = geo_info.get("country")
        new_alert.postal_code = geo_info.get("postal_code")

        print(f"[DB SAVE] Saving alert:\nfull_address={new_alert.full_address}\nlandmark={new_alert.landmark}\ncity={new_alert.city}\nstate={new_alert.state}\npostal_code={new_alert.postal_code}")

        db.add(new_alert)
        db.commit()

        # Immediately query back from DB to prove persistence
        db.refresh(new_alert)
        print(f"[DB VERIFY]\ncity={new_alert.city}\nstate={new_alert.state}\npostal_code={new_alert.postal_code}\nlandmark={new_alert.landmark}\nfull_address={new_alert.full_address}")

        return new_alert
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create alert: {str(e)}")


# ──────────────────────────────────────────────────────────────────────────────
# LIVE LOCATION UPDATE (PUT and PATCH support)
# ──────────────────────────────────────────────────────────────────────────────

def process_location_update(
    alert_id: int,
    location: schemas.AlertLocationUpdate,
    db: Session,
    current_user: models.User,
) -> models.Alert:
    alert = db.query(models.Alert).filter(
        models.Alert.id == alert_id,
        models.Alert.user_id == current_user.id,
    ).first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    active_statuses = {models.AlertStatus.PENDING, models.AlertStatus.IN_PROGRESS}
    if alert.status not in active_statuses:
        raise HTTPException(
            status_code=400,
            detail="Location updates only accepted for Pending or In-Progress alerts",
        )

    try:
        # Determine if moving (e.g. coordinates shifted by > 5 meters)
        # And determine if we need to update geocoding address (shifted by > 30 meters or address is currently missing)
        is_moving = False
        should_geocode = False

        if alert.last_latitude is not None and alert.last_longitude is not None:
            distance_moved = haversine_distance(
                alert.last_latitude, alert.last_longitude,
                location.latitude, location.longitude
            )
            
            # Determine if citizen is moving (shifted by > ~5 meters)
            if distance_moved > 5.0:
                is_moving = True
            
            # Determine if we should trigger Nominatim reverse geocode update (> 30 meters)
            if distance_moved > 30.0:
                should_geocode = True
        else:
            should_geocode = True

        # If the address is currently missing or set to "Address unavailable", attempt to fetch/refetch it
        if not alert.full_address or alert.full_address == "Address unavailable":
            should_geocode = True
            print(f"[LOCATION_UPDATE] Alert #{alert_id}: address missing/unavailable, will re-geocode")

        if should_geocode:
            print(f"[LOCATION_UPDATE] Alert #{alert_id}: triggering geocode for ({location.latitude}, {location.longitude})")
            try:
                geo_info = reverse_geocode(location.latitude, location.longitude)
                alert.full_address = geo_info.get("full_address")
                alert.landmark = geo_info.get("landmark")
                alert.city = geo_info.get("city")
                alert.state = geo_info.get("state")
                alert.country = geo_info.get("country")
                alert.postal_code = geo_info.get("postal_code")
                print(f"[DB SAVE] Saving updated location alert #{alert_id}:\nfull_address={alert.full_address}\nlandmark={alert.landmark}\ncity={alert.city}\nstate={alert.state}\npostal_code={alert.postal_code}")
            except Exception as geo_err:
                print(f"[LOCATION_UPDATE] Geocoding failed (non-fatal): {geo_err}")

        alert.last_latitude = location.latitude
        alert.last_longitude = location.longitude
        alert.last_accuracy = location.accuracy
        alert.last_location_update = datetime.now(timezone.utc)
        alert.is_moving = is_moving
        
        db.commit()
        db.refresh(alert)
        print(f"[DB VERIFY] Updated location:\ncity={alert.city}\nstate={alert.state}\npostal_code={alert.postal_code}\nlandmark={alert.landmark}\nfull_address={alert.full_address}")
        return alert
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update location: {str(e)}")


@router.put("/{alert_id}/location", response_model=schemas.AlertResponse)
def update_alert_location(
    alert_id: int,
    location: schemas.AlertLocationUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Receive periodic live location ping and persist it."""
    return process_location_update(alert_id, location, db, current_user)


@router.patch("/location/{alert_id}", response_model=schemas.AlertResponse)
def patch_alert_location(
    alert_id: int,
    location: schemas.AlertLocationUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """WhatsApp-style PATCH endpoint to update the alert's live location."""
    return process_location_update(alert_id, location, db, current_user)



# ──────────────────────────────────────────────────────────────────────────────
# MY ALERTS
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/my-alerts", response_model=List[schemas.AlertResponse])
def get_my_alerts(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    try:
        alerts = (
            db.query(models.Alert)
            .filter(models.Alert.user_id == current_user.id)
            .order_by(models.Alert.created_at.desc())
            .all()
        )
        if alerts:
            first = alerts[0]
            print(f"[API RESPONSE /my-alerts] First alert id={first.id}: city={first.city}, state={first.state}, postal_code={first.postal_code}, landmark={first.landmark}, full_address={first.full_address}")
        else:
            print("[API RESPONSE /my-alerts] No alerts returned for current user")
        return alerts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch alerts: {str(e)}")


# ──────────────────────────────────────────────────────────────────────────────
# CANCEL ALERT
# ──────────────────────────────────────────────────────────────────────────────

@router.put("/cancel/{alert_id}", response_model=schemas.AlertResponse)
def cancel_alert(
    alert_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    try:
        alert = db.query(models.Alert).filter(
            models.Alert.id == alert_id,
            models.Alert.user_id == current_user.id,
        ).first()

        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        if alert.status != models.AlertStatus.PENDING.value:
            raise HTTPException(status_code=400, detail="Only Pending alerts can be cancelled")

        alert.status = models.AlertStatus.CANCELLED
        db.commit()
        db.refresh(alert)
        return alert
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to cancel alert: {str(e)}")
