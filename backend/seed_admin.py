"""
Secure Admin Seeder Script for Smart Emergency Alert System (SEAS)
==================================================================
This CLI script securely seeds the default administrator account in the MySQL database.
It reads the admin email configuration from settings.ADMIN_EMAIL.

How to Run:
-----------
Windows/Powershell:
    python backend/seed_admin.py
"""
import sys
import os
import secrets
from sqlalchemy.orm import Session

# Add the backend directory to python path if not already there
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import database
import models
from config import settings
from utils import security

def seed_admin():
    print("═══ SEAS Administrator Account Seeder ═══")
    
    admin_email = settings.ADMIN_EMAIL.strip()
    if not admin_email or admin_email == "admin@example.com":
        print(f"[WARNING] You are using the default or empty ADMIN_EMAIL: '{admin_email}'.")
        print("Please configure a valid email in your '.env' file first!")
        
    db: Session = database.SessionLocal()
    try:
        # Check if the user already exists in the database
        user = db.query(models.User).filter(models.User.email == admin_email).first()
        
        if user:
            print(f"[INFO] User with email '{admin_email}' already exists in the database.")
            print(f"       Current Role: '{user.role}', Verified: {user.is_verified}")
            
            # Upgrade role to admin and set verified
            user.role = "admin"
            user.is_verified = True
            db.commit()
            
            print(f"[SUCCESS] Upgraded '{admin_email}' to 'admin' role and marked as verified!")
            print("[NOTE] Since the account already existed, the password was NOT changed.")
        else:
            # Create a new administrator account
            print(f"[INFO] Seeding a brand new admin account: '{admin_email}'")
            
            # Generate a secure 16-character random password since admin only logs in via OTP,
            # but standard user/admin DB schema requires a hashed password field.
            raw_password = secrets.token_urlsafe(12)
            hashed_pwd = security.get_password_hash(raw_password)
            
            new_admin = models.User(
                name="System Administrator",
                email=admin_email,
                phone=None,
                hashed_password=hashed_pwd,
                role="admin",
                is_verified=True
            )
            db.add(new_admin)
            db.commit()
            db.refresh(new_admin)
            
            print("[SUCCESS] Administrator account seeded successfully!")
            print(f"          Email: {admin_email}")
            print(f"          Role:  {new_admin.role}")
            print(f"          Status: Verified")
            print(f"          [CRITICAL] Dummy Password: {raw_password}")
            print("          (Note: Admin MUST log in using the email OTP flow. Traditional password login for admins is blocked.)")
            
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Seeding failed: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    seed_admin()
