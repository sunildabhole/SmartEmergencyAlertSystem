from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum


class AlertStatus(enum.Enum):
    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    RESOLVED = "Resolved"
    CANCELLED = "Cancelled"
    FALSE_ALARM = "False Alarm"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    phone = Column(String(20), unique=True, nullable=True)          # NEW: for OTP
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="user")                       # 'user' or 'admin'
    is_verified = Column(Boolean, default=False)                    # NEW: OTP-verified flag
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")
    otp_records = relationship("OTPRecord", back_populates="user", cascade="all, delete-orphan")


class OTPRecord(Base):
    """Stores temporary OTP codes for phone/email verification."""
    __tablename__ = "otp_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    otp_code = Column(String(6), nullable=False)
    purpose = Column(String(20), nullable=False)        # 'login' | 'register'
    is_used = Column(Boolean, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="otp_records")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    emergency_type = Column(String(50), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy = Column(Float, nullable=True)                        # NEW: accuracy of original SOS GPS in meters
    # NEW: live location tracking – updated periodically while alert is active
    last_latitude = Column(Float, nullable=True)
    last_longitude = Column(Float, nullable=True)
    last_accuracy = Column(Float, nullable=True)                   # NEW: accuracy of latest live update in meters
    last_location_update = Column(DateTime(timezone=True), nullable=True)
    is_moving = Column(Boolean, default=False)                     # NEW: whether citizen is currently moving
    # NEW: human-readable reverse geocoded address fields
    full_address = Column(Text, nullable=True)
    landmark = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=True)

    status = Column(
        Enum(
            AlertStatus,
            values_callable=lambda obj: [e.value for e in obj]
        ),
        default=AlertStatus.PENDING.value
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="alerts")

