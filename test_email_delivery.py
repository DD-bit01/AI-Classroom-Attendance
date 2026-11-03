"""
AURA Email & OTP Delivery Test Script
Run this script to verify that your SMTP configuration in .env can send real emails.
Usage:
    python test_email_delivery.py your_email@example.com
"""

import sys
import os
from email_service import send_verification_email, get_smtp_config

def main():
    host, port, user, password, from_email = get_smtp_config()

    print("=" * 60)
    print("  AURA AI // Email Delivery Configuration Check")
    print("=" * 60)
    print(f"SMTP Host : {host or '[NOT SET]'}")
    print(f"SMTP Port : {port}")
    print(f"SMTP User : {user or '[NOT SET]'}")
    print(f"SMTP Pass : {'*' * len(password) if password else '[NOT SET]'}")
    print(f"From Email: {from_email or '[NOT SET]'}")
    print("=" * 60)

    if not host or not user or not password:
        print("\n[!] SMTP credentials are not yet fully configured in .env.")
        print("    Please set AURA_SMTP_USER and AURA_SMTP_PASS in .env file.")
        print("    Example:")
        print("      AURA_SMTP_HOST=smtp.gmail.com")
        print("      AURA_SMTP_PORT=587")
        print("      AURA_SMTP_USER=your_email@gmail.com")
        print("      AURA_SMTP_PASS=xxxx xxxx xxxx xxxx (16-char Google App Password)")
        print("=" * 60)
        return

    target_email = sys.argv[1] if len(sys.argv) > 1 else user
    print(f"\nAttempting to send real test OTP email to: {target_email}...")

    res = send_verification_email(target_email, "849201", student_name="Test Student")
    print("\nResult:", res)
    if res.get("mode") == "smtp":
        print("\nSUCCESS! Real email delivered to your inbox!")
    else:
        print("\nEmail could not be delivered via SMTP (check error log above).")

if __name__ == "__main__":
    main()
