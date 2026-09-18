import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from integrations.gmail_client import gmail_client
from config import settings

def run_gmail_setup():
    print("=" * 60)
    print("🔑 LIVE GMAIL API OAUTH AUTHENTICATION SETUP")
    print("=" * 60)

    creds_path = Path(settings.GMAIL_CREDENTIALS_FILE)
    if not creds_path.exists():
        print(f"\n❌ ERROR: 'credentials.json' not found at: {creds_path.resolve()}")
        print("\nPlease follow these 3 steps to download your credentials.json file:")
        print("1. Go to Google Cloud Console: https://console.cloud.google.com/")
        print("2. Enable Gmail API and create an 'OAuth 2.0 Client ID' (Desktop App).")
        print("3. Download the JSON file, rename it to 'credentials.json', and save it in:")
        print(f"   {creds_path.parent.resolve()}")
        print("\nOnce placed, re-run this script: py scripts/setup_gmail.py")
        return

    print(f"\nFound credentials.json! Launching browser OAuth consent flow...")
    success = gmail_client.authenticate()

    if success:
        print("\n✅ GMAIL AUTHENTICATION SUCCESSFUL!")
        print(f"Token saved to: {Path(settings.GMAIL_TOKEN_FILE).resolve()}")
        print("Your system can now read incoming emails and send replies live from your Gmail inbox!")
    else:
        print("\n❌ Authentication failed. Please check your credentials file.")

if __name__ == "__main__":
    run_gmail_setup()
