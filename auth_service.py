"""
AURA Security & Cryptographic Authentication Service
Provides:
1. HMAC-SHA256 Cryptographically Signed Tokens for Student Onboarding.
2. Single-Use Token (Nonce / JTI) tracking to prevent replay attacks.
3. In-memory Rate Limiting & Cooldown Protection for OTP dispatches.
"""

import os
import time
import json
import base64
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, Any

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

import database as db

# Server cryptographic secret key
SECRET_KEY = os.getenv("AURA_SECRET_KEY", "").strip()
if not SECRET_KEY:
    # Stable machine-tied fallback if not set in .env
    fallback_seed = f"aura_vault_{os.path.abspath(__file__)}_2026"
    SECRET_KEY = hashlib.sha256(fallback_seed.encode("utf-8")).hexdigest()

SECRET_BYTES = SECRET_KEY.encode("utf-8")

# In-memory Rate Limiting Tracker
# Structure: { email: { 'attempts': [timestamps], 'last_send': timestamp, 'failed_verifications': int, 'lock_until': float } }
_RATE_LIMITS: Dict[str, Dict[str, Any]] = {}

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def _b64url_decode(s: str) -> bytes:
    padding = "=" * (4 - (len(s) % 4)) if (len(s) % 4) else ""
    return base64.urlsafe_b64decode((s + padding).encode("utf-8"))

def check_otp_rate_limit(email: str, ip: str = "") -> Tuple[bool, str]:
    """
    Enforces rate limits on OTP generation:
    1. 60-second cooldown between consecutive OTP requests.
    2. Maximum 4 OTP requests per 15 minutes.
    3. Temporary lockout if locked.
    """
    email_key = email.strip().lower()
    now = time.time()

    record = _RATE_LIMITS.setdefault(email_key, {
        "attempts": [],
        "last_send": 0,
        "failed_verifications": 0,
        "lock_until": 0
    })

    if now < record["lock_until"]:
        remaining = int(record["lock_until"] - now)
        return False, f"Too many attempts. Account locked for {remaining} seconds. Please wait."

    # 60s cooldown check
    if now - record["last_send"] < 60:
        remaining = int(60 - (now - record["last_send"]))
        return False, f"Please wait {remaining} seconds before requesting another verification code."

    # Filter attempts within the last 15 minutes (900 seconds)
    record["attempts"] = [t for t in record["attempts"] if now - t < 900]
    if len(record["attempts"]) >= 4:
        record["lock_until"] = now + 900
        return False, "Rate limit exceeded (max 4 OTPs per 15 mins). Please try again in 15 minutes."

    record["attempts"].append(now)
    record["last_send"] = now
    return True, ""

def record_failed_otp_attempt(email: str) -> int:
    """Tracks failed OTP attempts. Locks for 15 minutes after 5 consecutive failures."""
    email_key = email.strip().lower()
    record = _RATE_LIMITS.setdefault(email_key, {
        "attempts": [],
        "last_send": 0,
        "failed_verifications": 0,
        "lock_until": 0
    })
    record["failed_verifications"] += 1
    if record["failed_verifications"] >= 5:
        record["lock_until"] = time.time() + 900
        record["failed_verifications"] = 0
        return 0
    return 5 - record["failed_verifications"]

def reset_failed_otp_attempts(email: str):
    """Resets failed verification counter upon successful verification."""
    email_key = email.strip().lower()
    if email_key in _RATE_LIMITS:
        _RATE_LIMITS[email_key]["failed_verifications"] = 0

def generate_onboarding_token(email: str, expiry_minutes: int = 25) -> str:
    """
    Creates a signed HMAC-SHA256 JWT for student onboarding.
    Stores the token nonce (JTI) in database to ensure single-use (anti-replay).
    """
    email_clean = email.strip().lower()
    token_id = secrets.token_hex(16) # 32-character unique nonce
    now = int(time.time())
    exp = now + (expiry_minutes * 60)

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": email_clean,
        "jti": token_id,
        "purpose": "student_onboarding",
        "iat": now,
        "exp": exp
    }

    header_enc = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_enc = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_enc}.{payload_enc}".encode("utf-8")

    signature = hmac.new(SECRET_BYTES, signing_input, hashlib.sha256).digest()
    sig_enc = _b64url_encode(signature)

    jwt_token = f"{header_enc}.{payload_enc}.{sig_enc}"

    # Record token nonce in SQLite for single-use enforcement
    expires_dt = datetime.fromtimestamp(exp)
    db.store_onboarding_token(token_id=token_id, email=email_clean, expires_at=expires_dt)

    return jwt_token

def verify_onboarding_token(token_str: str, expected_email: Optional[str] = None) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Verifies the cryptographic signature, expiration, email match, and non-consumed status.
    Returns: (is_valid, payload, error_message)
    """
    if not token_str or not isinstance(token_str, str):
        return False, None, "Missing authentication token. Please complete email verification."

    parts = token_str.strip().split(".")
    if len(parts) != 3:
        return False, None, "Malformed authentication token."

    header_enc, payload_enc, sig_enc = parts

    try:
        # 1. Verify HMAC-SHA256 signature
        signing_input = f"{header_enc}.{payload_enc}".encode("utf-8")
        expected_sig = hmac.new(SECRET_BYTES, signing_input, hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_enc)

        if not hmac.compare_digest(expected_sig, actual_sig):
            return False, None, "Cryptographic token signature mismatch (tampering detected)."

        # 2. Parse payload
        payload_bytes = _b64url_decode(payload_enc)
        payload = json.loads(payload_bytes.decode("utf-8"))

        # 3. Check expiration
        now = int(time.time())
        exp = payload.get("exp", 0)
        if now > exp:
            return False, None, "Onboarding session token has expired. Please verify your email again."

        # 4. Check purpose
        if payload.get("purpose") != "student_onboarding":
            return False, None, "Invalid token purpose."

        # 5. Check email matching if specified
        token_email = payload.get("sub", "").strip().lower()
        if expected_email:
            if token_email != expected_email.strip().lower():
                return False, None, f"Token was issued for '{token_email}' but registration attempted for '{expected_email}'."

        # 6. Check single-use / anti-replay status in SQLite
        token_id = payload.get("jti")
        if not token_id or not db.is_onboarding_token_valid(token_id):
            return False, None, "This verification token has already been used or revoked. Please verify again."

        return True, payload, ""

    except Exception as e:
        return False, None, f"Token validation error: {str(e)}"

def consume_onboarding_token(token_id: str) -> bool:
    """Atomically invalidates the token so it cannot be reused."""
    return db.consume_onboarding_token(token_id)
