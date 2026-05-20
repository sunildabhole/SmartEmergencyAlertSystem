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
            status=models.AlertStatus.PENDING,
        )
        db.add(new_alert)
        db.commit()
        db.refresh(new_alert)
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
        # Determine if moving (e.g. coordinates shifted by > ~5 meters)
        is_moving = False
        if alert.last_latitude is not None and alert.last_longitude is not None:
            lat_diff = abs(alert.last_latitude - location.latitude)
            lng_diff = abs(alert.last_longitude - location.longitude)
            if lat_diff > 0.00005 or lng_diff > 0.00005:
                is_moving = True

        alert.last_latitude = location.latitude
        alert.last_longitude = location.longitude
        alert.last_accuracy = location.accuracy
        alert.last_location_update = datetime.now(timezone.utc)
        alert.is_moving = is_moving
        db.commit()
        db.refresh(alert)
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
        return (
            db.query(models.Alert)
            .filter(models.Alert.user_id == current_user.id)
            .order_by(models.Alert.created_at.desc())
            .all()
        )
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
