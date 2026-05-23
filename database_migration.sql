-- SEAS Enhancement Migration
-- Run this if you already have the existing DB schema

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS phone VARCHAR(20) UNIQUE DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS is_verified TINYINT(1) NOT NULL DEFAULT 0;

ALTER TABLE alerts
  ADD COLUMN IF NOT EXISTS last_latitude DOUBLE DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS last_longitude DOUBLE DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS last_location_update DATETIME DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS updated_at DATETIME DEFAULT NULL;

CREATE TABLE IF NOT EXISTS otp_records (
  id           INT PRIMARY KEY AUTO_INCREMENT,
  user_id      INT NOT NULL,
  otp_code     VARCHAR(6) NOT NULL,
  purpose      VARCHAR(20) NOT NULL,
  is_used      TINYINT(1) NOT NULL DEFAULT 0,
  expires_at   DATETIME NOT NULL,
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_user_purpose (user_id, purpose),
  INDEX idx_expires (expires_at)
);

-- Mark all existing users as verified so they can still log in
UPDATE users SET is_verified = 1 WHERE is_verified = 0;
