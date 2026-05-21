from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import schemas, models, database, auth

router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)

@router.get("/alerts", response_model=List[schemas.AlertWithUserResponse])
def get_all_alerts(
    db: Session = Depends(database.get_db),
    current_admin: models.User = Depends(auth.get_current_admin)
):
    try:
        alerts = db.query(models.Alert).order_by(models.Alert.created_at.desc()).all()
        if alerts:
            first = alerts[0]
            print(f"[API RESPONSE /admin/alerts] First alert id={first.id}: city={first.city}, state={first.state}, postal_code={first.postal_code}, landmark={first.landmark}, full_address={first.full_address}")
        else:
            print("[API RESPONSE /admin/alerts] No alerts in system")
        return alerts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch alerts: {str(e)}")

@router.put("/alerts/{alert_id}", response_model=schemas.AlertResponse)
def update_alert_status(
    alert_id: int,
    alert_update: schemas.AlertUpdate,
    db: Session = Depends(database.get_db),
    current_admin: models.User = Depends(auth.get_current_admin)
):
    try:
        alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
            
        alert.status = alert_update.status
        db.commit()
        db.refresh(alert)
        return alert
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update alert: {str(e)}")
