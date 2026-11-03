"""
AURA Email & OTP Delivery Service
Sends 6-digit OTP codes for student institute email verification.
Supports:
1. Direct SMTP (Gmail, Outlook, College SMTP) via environment variables.
2. In-Memory / Dev Console Fallback when SMTP is not configured.
"""

import os
import smtplib
import hashlib
import secrets
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configuration (defaults to console/dev mode if not provided in env)
SMTP_HOST = os.getenv("AURA_SMTP_HOST", "")
SMTP_PORT = int(os.getenv("AURA_SMTP_PORT", "587"))
SMTP_USER = os.getenv("AURA_SMTP_USER", "")
SMTP_PASS = os.getenv("AURA_SMTP_PASS", "")
SMTP_FROM = os.getenv("AURA_SMTP_FROM", SMTP_USER or "noreply-aura@attendance.edu")

# Institute Email Domains (optional filter, comma separated, e.g. "nitrr.ac.in,iiit.ac.in")
ALLOWED_DOMAINS_RAW = os.getenv("AURA_ALLOWED_EMAIL_DOMAINS", "")
ALLOWED_DOMAINS = [d.strip().lower() for d in ALLOWED_DOMAINS_RAW.split(",") if d.strip()]

def is_allowed_domain(email: str) -> bool:
    if not ALLOWED_DOMAINS:
        return True # Any valid email allowed if domain whitelist not configured
    domain = email.strip().lower().split("@")[-1]
    return any(domain == d or domain.endswith("." + d) for d in ALLOWED_DOMAINS)

def generate_otp() -> str:
    """Generates a secure 6-digit verification code."""
    return f"{secrets.randbelow(900000) + 100000}"

def hash_otp(otp: str, email: str) -> str:
    """Hashes OTP with email salt for secure storage in SQLite."""
    salt = f"aura_{email.lower().strip()}"
    return hashlib.sha256(f"{otp}_{salt}".encode("utf-8")).hexdigest()

def send_verification_email(to_email: str, otp: str, student_name: str = "") -> dict:
    """
    Sends verification email via SMTP if configured, or prints to terminal / logs in dev mode.
    """
    to_email = to_email.strip().lower()
    subject = f"AURA AI Attendance // Verification Code: {otp}"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0b0f19; margin: 0; padding: 24px; color: #e2e8f0; }}
        .card {{ max-width: 480px; margin: 0 auto; background: #131b2e; border: 1px solid #1e293b; border-radius: 16px; padding: 32px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
        .brand {{ display: flex; align-items: center; gap: 10px; margin-bottom: 24px; }}
        .symbol {{ color: #22c55e; font-size: 24px; font-weight: bold; }}
        .title {{ font-size: 18px; font-weight: 700; color: #ffffff; letter-spacing: 0.05em; }}
        .otp-box {{ background: #0f172a; border: 1.5px dashed #22c55e; border-radius: 12px; padding: 20px; text-align: center; margin: 28px 0; }}
        .otp-code {{ font-family: 'Courier New', Courier, monospace; font-size: 38px; font-weight: 800; color: #4ade80; letter-spacing: 8px; }}
        .hint {{ font-size: 13px; color: #94a3b8; line-height: 1.6; }}
        .footer {{ margin-top: 28px; font-size: 11px; color: #64748b; text-align: center; border-top: 1px solid #1e293b; padding-top: 16px; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="brand">
          <span class="symbol">◆</span>
          <span class="title">AURA // AI CLASSROOM ATTENDANCE</span>
        </div>
        <p style="margin: 0 0 8px 0; font-size: 15px; color: #cbd5e1;">Hello {student_name or 'Student'},</p>
        <p class="hint">Use the 6-digit one-time verification code below to confirm your institute email address and complete your facial attendance onboarding.</p>
        
        <div class="otp-box">
          <div class="otp-code">{otp}</div>
          <div style="font-size: 11px; color: #64748b; margin-top: 6px;">Valid for 10 minutes</div>
        </div>

        <p class="hint">Please do not share this OTP with anyone. After verification, you will capture 4 portrait photos from different angles for classroom facial matching.</p>

        <div class="footer">
          Automated Facial Attendance Service &bull; Self-Service Student Onboarding
        </div>
      </div>
    </body>
    </html>
    """

    # If SMTP is configured, send actual email
    if SMTP_HOST and SMTP_USER and SMTP_PASS:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"AURA Attendance <{SMTP_FROM}>"
            msg["To"] = to_email
            
            part = MIMEText(html_body, "html")
            msg.attach(part)

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=12) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_FROM, [to_email], msg.as_string())
            
            print(f"[OTP Service] Sent email to {to_email} via SMTP ({SMTP_HOST})")
            return {"success": True, "mode": "smtp", "message": f"Verification code sent to {to_email}"}
        except Exception as e:
            print(f"[OTP Service] SMTP send error ({e}), falling back to dev mode...")
            # Fall through to dev console mode

    # Development / Fallback mode: Print to console and return OTP in response for instant testing
    print("=" * 60)
    print(f"[AURA OTP DISPATCH] Institute Email: {to_email}")
    print(f"[AURA OTP DISPATCH] 6-Digit Code   : >>> {otp} <<<")
    print(f"[AURA OTP DISPATCH] Expiration      : 10 minutes")
    print("=" * 60)

    return {
        "success": True,
        "mode": "dev",
        "message": f"Verification code dispatched to {to_email} (Dev Mode Active)",
        "dev_otp": otp # Provided for zero-friction local/offline testing
    }
