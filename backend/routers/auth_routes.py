"""
Authentication routes – now with OTP-based verification.

Flow
────
Register:
  1. POST /auth/register           → creates user (is_verified=False), sends OTP to email
  2. POST /auth/verify-register    → verifies OTP, sets is_verified=True

Login:
  Option A – OTP login (recommended):
    1. POST /auth/request-otp      → user must exist, sends OTP
    2. POST /auth/verify-otp-login → verifies OTP, returns JWT

  Option B – password login (legacy, kept for admin convenience):
    1. POST /auth/login            → password + email → JWT
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import schemas, models, database, auth
from utils import security
from utils.otp import create_and_send_otp, verify_otp
from config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ──────────────────────────────────────────────────────────────────────────────
# REGISTER
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=schemas.MessageResponse, status_code=status.HTTP_201_CREATED)
def register(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    """Create account. Sends OTP to email; user must verify before logging in."""

    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user:
        if existing_user.is_verified:
            raise HTTPException(status_code=400, detail="Email already registered")
        else:
            # Re-registering unverified user: update their details
            if user.phone:
                existing_phone = db.query(models.User).filter(
                    models.User.phone == user.phone,
                    models.User.email != user.email
                ).first()
                if existing_phone:
                    raise HTTPException(status_code=400, detail="Phone number already registered by another user")

            existing_user.name = user.name
            existing_user.phone = user.phone
            existing_user.hashed_password = security.get_password_hash(user.password)
            db.commit()
            db.refresh(existing_user)

            try:
                create_and_send_otp(db, existing_user, "register")
            except ValueError as e:
                # Catch configuration/placeholder SMTP errors and return them cleanly
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=str(e)
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to send registration OTP email: {str(e)}"
                )

            return {
                "message": "Account details updated. A new OTP has been sent to your email."
            }

    if user.phone:
        if db.query(models.User).filter(models.User.phone == user.phone).first():
            raise HTTPException(status_code=400, detail="Phone number already registered")

    hashed_password = security.get_password_hash(user.password)
    role = "admin" if user.email.lower() == settings.ADMIN_EMAIL.lower() else "user"

    new_user = models.User(
        name=user.name,
        email=user.email,
        phone=user.phone,
        hashed_password=hashed_password,
        role=role,
        is_verified=False,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    try:
        create_and_send_otp(db, new_user, "register")
    except ValueError as e:
        # Catch configuration/placeholder SMTP errors and return them cleanly
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send registration OTP email: {str(e)}"
        )

    return {
        "message": "Registration successful. Check your email for the OTP."
    }


@router.post("/verify-register", response_model=schemas.Token)
def verify_register(payload: schemas.OTPVerify, db: Session = Depends(database.get_db)):
    """Verify the registration OTP and return a JWT so the user is logged in."""

    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # verify_otp raises explicit HTTPExceptions for expired or invalid OTPs
    verify_otp(db, user, payload.otp_code, "register")

    user.is_verified = True
    db.commit()

    token = security.create_access_token(
        data={"user_id": user.id, "email": user.email, "role": user.role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": token, "token_type": "bearer", "role": user.role}


# ──────────────────────────────────────────────────────────────────────────────
# OTP LOGIN (primary flow)
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/request-otp", response_model=schemas.MessageResponse)
def request_otp(payload: schemas.OTPRequest, db: Session = Depends(database.get_db)):
    """Send a registration or login OTP to the user's registered email."""

    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="No account found with this email")

    if payload.purpose == "login":
        if not user.is_verified:
            raise HTTPException(status_code=403, detail="Account not verified. Complete registration first.")
    elif payload.purpose == "register":
        if user.is_verified:
            raise HTTPException(status_code=400, detail="Account is already verified. Please login.")
    else:
        raise HTTPException(status_code=400, detail="Invalid purpose specified.")

    # Prevent resend spam abuse: check if an OTP was recently sent (within settings.OTP_RESEND_COOLDOWN_SECONDS)
    last_record = db.query(models.OTPRecord).filter(
        models.OTPRecord.user_id == user.id,
        models.OTPRecord.purpose == payload.purpose
    ).order_by(models.OTPRecord.created_at.desc()).first()

    if last_record:
        from datetime import timezone
        created_at = last_record.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
            
        now = datetime.now(timezone.utc)
        cooldown = timedelta(seconds=settings.OTP_RESEND_COOLDOWN_SECONDS)
        if now - created_at < cooldown:
            raise HTTPException(
                status_code=429,
                detail="Please wait before requesting another OTP."
            )

    try:
        create_and_send_otp(db, user, payload.purpose)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send OTP: {str(e)}")

    return {
        "message": f"OTP sent successfully to your email. Valid for {settings.OTP_EXPIRE_MINUTES} minutes."
    }


@router.post("/verify-otp-login", response_model=schemas.Token)
def verify_otp_login(payload: schemas.OTPLoginComplete, db: Session = Depends(database.get_db)):
    """Exchange a valid login OTP for a JWT."""

    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # verify_otp raises explicit HTTPExceptions for expired or invalid OTPs
    verify_otp(db, user, payload.otp_code, "login")

    token = security.create_access_token(
        data={"user_id": user.id, "email": user.email, "role": user.role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": token, "token_type": "bearer", "role": user.role}


# ──────────────────────────────────────────────────────────────────────────────
# PASSWORD LOGIN (legacy / admin convenience)
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=schemas.Token)
def login(user_credentials: schemas.UserLogin, db: Session = Depends(database.get_db)):
    """Traditional password login. Admin password login is strictly blocked."""

    user = db.query(models.User).filter(models.User.email == user_credentials.email).first()

    # Enforce OTP-only admin login - check BEFORE verifying password
    if user and user.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin must login using OTP."
        )

    if not user or not security.verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Credentials")

    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Account not verified. Please verify via OTP.")

    token = security.create_access_token(
        data={"user_id": user.id, "email": user.email, "role": user.role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": token, "token_type": "bearer", "role": user.role}


# ──────────────────────────────────────────────────────────────────────────────
# PROFILE
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=schemas.UserResponse)
def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user

@router.get("/config")
def get_config():
    """Return public configuration required by the frontend."""
    return {"admin_email": settings.ADMIN_EMAIL}
