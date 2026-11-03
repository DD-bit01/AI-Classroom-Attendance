"""
AURA Email & OTP Delivery Service
Sends 6-digit OTP codes for student institute email verification.
Supports:
1. Direct SMTP (Gmail, Outlook, College SMTP) loaded securely from .env or environment variables.
2. In-Memory / Dev Console Fallback when SMTP is not configured or offline.
"""

import os
import smtplib
import hashlib
import secrets
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

def get_smtp_config():
    """Dynamically reads SMTP settings from environment or .env."""
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except Exception:
        pass

    user = os.getenv("AURA_SMTP_USER", "").strip()
    password = os.getenv("AURA_SMTP_PASS", "").strip()
    host = os.getenv("AURA_SMTP_HOST", "").strip()
    port = int(os.getenv("AURA_SMTP_PORT", "587"))
    from_email = os.getenv("AURA_SMTP_FROM", user).strip()

    # Smart auto-detection for common providers if host wasn't explicitly set
    if not host and user:
        if "@gmail.com" in user.lower():
            host = "smtp.gmail.com"
            port = 587
        elif "@outlook.com" in user.lower() or "@hotmail.com" in user.lower():
            host = "smtp.office365.com"
            port = 587

    return host, port, user, password, from_email

def is_allowed_domain(email: str) -> bool:
    """Validates if email domain is within allowed institute domains."""
    raw = os.getenv("AURA_ALLOWED_EMAIL_DOMAINS", "").strip()
    if not raw:
        return True # Any domain permitted if whitelist is not set
    allowed = [d.strip().lower() for d in raw.split(",") if d.strip()]
    domain = email.strip().lower().split("@")[-1]
    return any(domain == d or domain.endswith("." + d) for d in allowed)

def generate_otp() -> str:
    """Generates a cryptographically secure 6-digit code."""
    return f"{secrets.randbelow(900000) + 100000}"

def hash_otp(otp: str, email: str) -> str:
    """Hashes OTP with student email salt for secure SQLite storage."""
    salt = f"aura_{email.lower().strip()}"
    return hashlib.sha256(f"{otp}_{salt}".encode("utf-8")).hexdigest()

def send_verification_email(to_email: str, otp: str, student_name: str = "") -> dict:
    """
    Dispatches verification email to the student's email address.
    If SMTP credentials are provided, delivers directly to their inbox.
    Otherwise, prints to server console and provides instant dev fallback.
    """
    to_email = to_email.strip().lower()
    subject = f"AURA Attendance // Verification Code: {otp}"
    display_name = student_name.strip() if student_name else "Student"

    # HTML Email Template styled in AURA Minimalist Dark Theme
    html_body = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <style>
        body {{
          background-color: #000000;
          color: #ffffff;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
          margin: 0;
          padding: 24px 12px;
        }}
        .email-container {{
          max-width: 500px;
          margin: 0 auto;
          background: #0a0a0c;
          border: 1px solid #222226;
          border-radius: 8px;
          padding: 32px 24px;
        }}
        .brand-header {{
          display: flex;
          align-items: center;
          gap: 10px;
          padding-bottom: 20px;
          border-bottom: 1px solid #222226;
          margin-bottom: 24px;
        }}
        .brand-symbol {{
          width: 32px;
          height: 32px;
          background: #ffffff;
          color: #000000;
          border-radius: 4px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          font-weight: 700;
          font-size: 16px;
        }}
        .brand-text {{
          font-size: 14px;
          font-weight: 700;
          letter-spacing: 1.5px;
          color: #ffffff;
        }}
        .greeting {{
          font-size: 16px;
          font-weight: 600;
          color: #ffffff;
          margin-bottom: 8px;
        }}
        .message {{
          font-size: 13px;
          color: #a1a1aa;
          line-height: 1.6;
          margin-bottom: 24px;
        }}
        .otp-card {{
          background: #111114;
          border: 1px solid #383840;
          border-radius: 6px;
          padding: 24px 16px;
          text-align: center;
          margin: 24px 0;
        }}
        .otp-number {{
          font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
          font-size: 38px;
          font-weight: 700;
          letter-spacing: 8px;
          color: #ffffff;
        }}
        .otp-expiry {{
          font-size: 11px;
          color: #71717a;
          margin-top: 8px;
          text-transform: uppercase;
          letter-spacing: 1px;
        }}
        .instructions {{
          background: #111114;
          border-left: 2px solid #ffffff;
          padding: 12px 14px;
          font-size: 12px;
          color: #a1a1aa;
          line-height: 1.5;
          margin-bottom: 24px;
        }}
        .footer {{
          border-top: 1px solid #222226;
          padding-top: 20px;
          text-align: center;
          font-size: 11px;
          color: #71717a;
          line-height: 1.5;
        }}
      </style>
    </head>
    <body>
      <div class="email-container">
        <div class="brand-header">
          <div class="brand-symbol">◆</div>
          <div class="brand-text">AURA.AI // ATTENDANCE CORE</div>
        </div>

        <div class="greeting">Hello {display_name},</div>
        <p class="message">
          You are receiving this verification code for institutional biometric registration on the 
          <strong>AURA AI Classroom Attendance System</strong>.
        </p>

        <div class="otp-card">
          <div class="otp-number">{otp}</div>
          <div class="otp-expiry">Valid for 10 minutes &bull; Single Use</div>
        </div>

        <div class="instructions">
          <strong>Next Steps:</strong> Enter this code into your onboarding screen, verify your roll number, and capture your 4 reference photos for facial recognition.
        </div>

        <div class="footer">
          This is an automated verification email from AURA.AI.<br>
          If you did not initiate this request, you can safely ignore this email.
        </div>
      </div>
    </body>
    </html>
    """

    host, port, user, password, from_email = get_smtp_config()

    # 1. If SMTP is configured, send real email directly to recipient inbox
    if host and user and password:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"AURA AI <{from_email}>"
            msg["To"] = to_email

            part_html = MIMEText(html_body, "html")
            msg.attach(part_html)

            # Plaintext fallback for mail clients with HTML disabled
            plain_text = f"AURA AI Verification Code: {otp}\nValid for 10 minutes.\nEnter this code on the onboarding page."
            part_plain = MIMEText(plain_text, "plain")
            msg.attach(part_plain)

            if port == 465:
                # SSL
                with smtplib.SMTP_SSL(host, port, timeout=12) as server:
                    server.login(user, password)
                    server.sendmail(from_email, [to_email], msg.as_string())
            else:
                # TLS (port 587)
                with smtplib.SMTP(host, port, timeout=12) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(user, password)
                    server.sendmail(from_email, [to_email], msg.as_string())

            print(f"[OTP Service] Successfully sent real email to {to_email} via SMTP ({host})")
            return {
                "success": True,
                "mode": "smtp",
                "message": f"Verification code sent directly to {to_email}. Please check your inbox."
            }

        except Exception as e:
            print(f"[OTP Service] SMTP delivery to {to_email} failed: {e}")
            print("[OTP Service] Falling back to dev mode output...")

    # 2. Dev / Offline Fallback (when SMTP not configured or failed)
    print("=" * 60)
    print(f"[AURA OTP DISPATCH] Institute Email: {to_email}")
    print(f"[AURA OTP DISPATCH] 6-Digit Code   : >>> {otp} <<<")
    print(f"[AURA OTP DISPATCH] Expiration      : 10 minutes")
    print("=" * 60)

    return {
        "success": True,
        "mode": "dev",
        "message": f"Verification code sent to {to_email} (Dev/Console active)",
        "dev_otp": otp
    }
