"""
OTP utilities for SEAS.

In production, replace _send_email_otp() with a real email/SMS gateway
(e.g. Twilio, SendGrid, AWS SES).  For demo purposes the OTP is printed
to the server console and also returned in the API response so it can be
copied from the terminal or the JSON body.
"""

import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
import models
from config import settings
from fastapi import HTTPException, status

def _generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def _send_email_otp(email: str, otp: str, purpose: str) -> None:
    """
    Sends the OTP using Gmail SMTP with a beautiful, responsive HTML email.
    """
    if settings.SMTP_PASSWORD == "console":
        print(f"\n[OTP SERVICE] [LOCAL DEV MODE] Secure OTP for {email}: {otp}\n")
        return

    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD or "your_16_digit" in settings.SMTP_PASSWORD:
        raise ValueError("SMTP credentials are not configured or are placeholder on the server.")

    msg = MIMEMultipart()
    msg['From'] = settings.SMTP_USERNAME
    msg['To'] = email
    msg['Subject'] = f"[{purpose.upper()}] Your OTP Code for SMART EMERGENCY ALERT SYSTEM"

    html = f"""
    <!DOCTYPE html>
    <html>
      <body style="font-family: 'Outfit', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 40px 20px; background-color: #f8fafc;">
        <div style="background: white; border-radius: 16px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1); padding: 40px; border-top: 4px solid #e11d48;">
          <h2 style="color: #e11d48; text-align: center; font-size: 24px; font-weight: 800; margin-top: 0; margin-bottom: 8px; letter-spacing: 0.5px;">
            SMART EMERGENCY ALERT SYSTEM
          </h2>
          <p style="text-align: center; color: #64748b; font-size: 14px; margin-bottom: 30px;">Secure Emergency Action Portal</p>
          
          <div style="border-bottom: 1px solid #e2e8f0; margin-bottom: 30px;"></div>
          
          <p style="font-size: 16px; line-height: 1.6; margin-bottom: 24px;">Hello,</p>
          <p style="font-size: 16px; line-height: 1.6; margin-bottom: 24px;">You have requested a One-Time Password (OTP) for your <strong>{purpose}</strong> request.</p>
          
          <div style="text-align: center; margin: 35px 0;">
            <div style="display: inline-block; font-size: 36px; font-weight: 800; background-color: #fff1f2; border: 2px dashed #f43f5e; padding: 16px 36px; border-radius: 12px; letter-spacing: 6px; color: #e11d48; font-family: Courier, monospace;">
              {otp}
            </div>
          </div>
          
          <p style="font-size: 15px; line-height: 1.6; color: #475569; text-align: center; margin-bottom: 30px;">
            This OTP is valid for <strong style="color: #0f172a;">{settings.OTP_EXPIRE_MINUTES} minutes</strong>.
          </p>
          
          <div style="background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 16px; border-radius: 8px; margin-bottom: 30px;">
            <p style="margin: 0; font-size: 14px; color: #991b1b; line-height: 1.5;">
              <strong>WARNING:</strong> Do not share this OTP with anyone, including SEAS support. If you did not request this OTP, please ignore this email.
            </p>
          </div>
          
          <div style="border-bottom: 1px solid #e2e8f0; margin-bottom: 20px;"></div>
          
          <p style="font-size: 12px; color: #94a3b8; text-align: center; margin: 0;">
            This is an automated message from the Smart Emergency Alert System (SEAS). Please do not reply directly to this email.
          </p>
        </div>
      </body>
    </html>
    """
    msg.attach(MIMEText(html, 'html'))

    try:
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"[OTP SERVICE] Real email sent to {email}")
    except Exception as e:
        print(f"[OTP SERVICE] Failed to send email via SMTP: {str(e)}")
        raise ValueError(f"SMTP Server Error: {str(e)}")


def create_and_send_otp(db: Session, user: models.User, purpose: str) -> str:
    """
    Invalidate any previous OTPs for this user+purpose, create a new one,
    persist it, and dispatch it. Returns the OTP code.
    """
    # Invalidate old OTPs
    db.query(models.OTPRecord).filter(
        models.OTPRecord.user_id == user.id,
        models.OTPRecord.purpose == purpose,
        models.OTPRecord.is_used == False,
    ).update({"is_used": True})

    otp_code = _generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)

    record = models.OTPRecord(
        user_id=user.id,
        otp_code=otp_code,
        purpose=purpose,
        is_used=False,
        expires_at=expires_at,
    )
    db.add(record)
    db.commit()

    _send_email_otp(user.email, otp_code, purpose)
    return otp_code


def verify_otp(db: Session, user: models.User, otp_code: str, purpose: str) -> bool:
    """
    Strictest OTP validation:
    1. Retrieve latest OTP matching user, purpose, and code.
    2. Check if already used.
    3. Check expiry.
    4. Set is_used = True to prevent reuse.
    """
    now = datetime.now(timezone.utc)
    
    # Query latest record matching user, purpose, and OTP code
    record = (
        db.query(models.OTPRecord)
        .filter(
            models.OTPRecord.user_id == user.id,
            models.OTPRecord.purpose == purpose,
            models.OTPRecord.otp_code == otp_code,
        )
        .order_by(models.OTPRecord.created_at.desc())
        .first()
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP code."
        )

    if record.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has already been used. Please request a new OTP."
        )

    # Convert expiry time to UTC-aware if naive
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now > expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP expired. Please request a new OTP."
        )

    # Valid: immediately invalidate to prevent reuse
    record.is_used = True
    db.commit()
    return True
