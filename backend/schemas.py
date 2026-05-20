from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime
from models import AlertStatus


# ─── User Schemas ──────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    name: str
    email: EmailStr


class UserCreate(UserBase):
    password: str
    phone: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    role: str
    phone: Optional[str] = None
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─── OTP Schemas ───────────────────────────────────────────────────────────────

class OTPRequest(BaseModel):
    """Client asks server to generate & send OTP."""
    email: EmailStr
    purpose: str = "login"          # 'login' | 'register'


class OTPVerify(BaseModel):
    """Client submits OTP code to verify."""
    email: EmailStr
    otp_code: str
    purpose: str = "login"


class OTPLoginComplete(BaseModel):
    """After OTP is verified, client may optionally provide password for full login."""
    email: EmailStr
    otp_code: str


# ─── Alert Schemas ─────────────────────────────────────────────────────────────

class AlertBase(BaseModel):
    emergency_type: str
    latitude: float
    longitude: float
    accuracy: Optional[float] = None

    @field_validator('latitude')
    @classmethod
    def validate_latitude(cls, v):
        if not (-90.0 <= v <= 90.0) or v == 0.0:
            raise ValueError('Latitude must be a non-zero value between -90 and 90.')
        return v

    @field_validator('longitude')
    @classmethod
    def validate_longitude(cls, v):
        if not (-180.0 <= v <= 180.0) or v == 0.0:
            raise ValueError('Longitude must be a non-zero value between -180 and 180.')
        return v


class AlertCreate(AlertBase):
    pass


class AlertLocationUpdate(BaseModel):
    """Payload for periodic live-location ping from active user."""
    latitude: float
    longitude: float
    accuracy: Optional[float] = None

    @field_validator('latitude')
    @classmethod
    def validate_latitude(cls, v):
        if not (-90.0 <= v <= 90.0) or v == 0.0:
            raise ValueError('Latitude must be a non-zero value between -90 and 90.')
        return v

    @field_validator('longitude')
    @classmethod
    def validate_longitude(cls, v):
        if not (-180.0 <= v <= 180.0) or v == 0.0:
            raise ValueError('Longitude must be a non-zero value between -180 and 180.')
        return v


class AlertUpdate(BaseModel):
    status: AlertStatus


class AlertResponse(AlertBase):
    id: int
    user_id: int
    status: AlertStatus
    last_latitude: Optional[float] = None
    last_longitude: Optional[float] = None
    last_location_update: Optional[datetime] = None
    last_accuracy: Optional[float] = None
    is_moving: Optional[bool] = False
    created_at: datetime

    class Config:
        from_attributes = True


class AlertWithUserResponse(AlertResponse):
    user: UserResponse

    class Config:
        from_attributes = True


# ─── Token Schemas ─────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str


class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    user_id: Optional[int] = None


class MessageResponse(BaseModel):
    message: str
