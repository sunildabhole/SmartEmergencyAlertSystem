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
    try:
        new_alert = models.Alert(
            user_id=current_user.id,
            emergency_type=alert.emergency_type,
            latitude=alert.latitude,
            longitude=alert.longitude,
            last_latitude=alert.latitude,
            last_longitude=alert.longitude,
            last_location_update=datetime.now(timezone.utc),
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
# LIVE LOCATION UPDATE  ← NEW
# ──────────────────────────────────────────────────────────────────────────────

@router.put("/{alert_id}/location", response_model=schemas.AlertResponse)
def update_alert_location(
    alert_id: int,
    location: schemas.AlertLocationUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Receive a live location ping from the user and persist it on the alert.
    Only allowed while the alert is Pending or In Progress.
    """
    alert = db.query(models.Alert).filter(
        models.Alert.id == alert_id,
        models.Alert.user_id == current_user.id,
    ).first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    active_statuses = {models.AlertStatus.PENDING.value, models.AlertStatus.IN_PROGRESS.value}
    if alert.status not in active_statuses:
        raise HTTPException(
            status_code=400,
            detail="Location updates only accepted for Pending or In-Progress alerts",
        )

    try:
        alert.last_latitude = location.latitude
        alert.last_longitude = location.longitude
        alert.last_location_update = datetime.now(timezone.utc)
        db.commit()
        db.refresh(alert)
        return alert
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update location: {str(e)}")


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
