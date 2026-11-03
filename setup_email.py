"""
AURA AI Attendance - Email Delivery Setup
Sets up ahmad.dilnawaz.md@gmail.com with your Google App Password.
"""

import sys
import os
import getpass
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent / ".env"

def main():
    print("=" * 65)
    print("  AURA AI // Email Delivery Configuration Setup")
    print("=" * 65)
    print("  Sender Email : ahmad.dilnawaz.md@gmail.com")
    print("  Mail Server  : smtp.gmail.com (Port 587)")
    print("=" * 65)
    print()
    print("To allow AURA to dispatch real OTP emails to student inboxes:")
    print("1. Log in to your personal Gmail: ahmad.dilnawaz.md@gmail.com")
    print("2. Go to Google Security: https://myaccount.google.com/security")
    print("3. Ensure 2-Step Verification is ON.")
    print("4. Open App Passwords: https://myaccount.google.com/apppasswords")
    print("   (Since this is personal Gmail, this setting is 100% available!)")
    print("5. Generate a 16-character App Password (e.g. 'AURA Attendance').")
    print()

    # Read password without echoing to terminal
    app_pass = getpass.getpass("Enter your 16-character Google App Password: ").strip()
    if not app_pass:
        print("[!] No password entered. Aborted.")
        return

    clean_pass = app_pass.replace(" ", "")

    content = f"""# AURA AI Attendance - Secure Environment Variables
AURA_SMTP_HOST=smtp.gmail.com
AURA_SMTP_PORT=587
AURA_SMTP_USER=ahmad.dilnawaz.md@gmail.com
AURA_SMTP_PASS={clean_pass}
AURA_SMTP_FROM=ahmad.dilnawaz.md@gmail.com
"""
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    print()
    print("Saved successfully to .env (Protected by .gitignore)!")
    print("Testing connection and sending a test email to ahmad.dilnawaz.md@gmail.com...")

    # Test delivery
    import email_service
    res = email_service.send_verification_email("ahmad.dilnawaz.md@gmail.com", "849201", "Dilnawaz")
    print()
    print("Delivery Test Result:", res.get("message"))
    if res.get("mode") == "smtp":
        print()
        print(" SUCCESS! Check your inbox at ahmad.dilnawaz.md@gmail.com for the test OTP.")
        print("   Students will now receive their OTPs directly in their respective emails!")
    else:
        print(" SMTP connection failed. Please double check that 2-Step Verification is ON and the 16-letter App Password is correct.")
    print()
    print("Delivery Test Result:", res.get("message"))
    if res.get("mode") == "smtp":
        print()
        print(" SUCCESS! Check your inbox at ahmad.dilnawaz.md@gmail.com for the test OTP.")
        print("   Students will now receive their OTPs directly in their respective emails!")
    else:
        print(" SMTP connection failed. Please double check that 2-Step Verification is ON and the 16-letter App Password is correct.")

if __name__ == "__main__":
    main()
