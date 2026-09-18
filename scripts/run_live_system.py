import os
import sys
import time
import subprocess
import threading
import logging
from pathlib import Path

# Ensure UTF-8 stdout encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.session import init_db
from integrations.gmail_client import gmail_client
from core.state_machine import orchestrator
import uvicorn
from main import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("live_system")

def find_cloudflared():
    paths = [
        r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
        r"C:\Program Files\cloudflared\cloudflared.exe",
        "cloudflared"
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return "cloudflared"

def start_cloudflare_tunnel():
    exe = find_cloudflared()
    logger.info("Starting Cloudflare HTTPS Tunnel...")
    proc = subprocess.Popen(
        [exe, "tunnel", "--url", "http://localhost:8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="ignore",
        bufsize=1
    )
    
    tunnel_url = None
    for line in proc.stdout:
        if "trycloudflare.com" in line:
            for part in line.split():
                if "https://" in part and "trycloudflare.com" in part:
                    tunnel_url = part.strip('| ')
                    break
            if tunnel_url:
                print("\n" + "=" * 70)
                print("🌐 LIVE CLOUDFLARE HTTPS TUNNEL READY!")
                print(f"📌 Webhook Callback URL: {tunnel_url.rstrip('/')}/webhook/whatsapp")
                print("📌 Verify Token:        mail_automation_secret_verify_token")
                print("=" * 70 + "\n")
                sys.stdout.flush()
                break

def start_gmail_poller(interval_seconds: int = 15):
    """Background thread polling Gmail inbox with strict 1-by-1 sequential execution."""
    init_db()
    time.sleep(5)
    logger.info("📡 Live Gmail Inbox Poller started in background thread (Strict 1-by-1 Mode)...")
    while True:
        try:
            from database.session import SessionLocal
            from database.models import EmailThread, ThreadStatus
            db = SessionLocal()

            # 1. Check if there is ANY email currently waiting for user approval or voice revision
            pending_count = db.query(EmailThread).filter(
                EmailThread.status.in_([ThreadStatus.PENDING_APPROVAL.value, ThreadStatus.REVISING.value])
            ).count()

            if pending_count > 0:
                # An email thread is currently active & waiting for user WhatsApp action! PAUSE polling!
                db.close()
                time.sleep(interval_seconds)
                continue

            # 2. Only fetch when no active thread is pending (Process ONE email at a time)
            unread_emails = gmail_client.fetch_unread_messages()
            if unread_emails:
                mail = unread_emails[0]  # Take ONLY the first unread email!
                logger.info(f"📧 [Sequential 1-by-1] Processing Email from '{mail['sender']}' | Subject: '{mail['subject']}'")
                email_thread = orchestrator.process_incoming_email(
                    db=db,
                    message_id=mail["message_id"],
                    thread_id=mail["thread_id"],
                    sender=mail["sender"],
                    sender_name=mail["sender_name"],
                    recipient=mail["recipient"],
                    subject=mail["subject"],
                    body=mail["body"]
                )
                gmail_client.mark_as_read(mail["message_id"])
                logger.info(f"📱 WhatsApp Approval Prompt Sent for '{mail['subject']}'! Pausing inbox poller until completed.")
            db.close()
        except Exception as e:
            logger.error(f"Error in Gmail poller thread: {e}")
        time.sleep(interval_seconds)

def main():
    # 1. Start Cloudflare Tunnel in background thread
    t_tunnel = threading.Thread(target=start_cloudflare_tunnel, daemon=True)
    t_tunnel.start()

    # 2. Start Gmail Poller in background thread
    t_poller = threading.Thread(target=start_gmail_poller, daemon=True)
    t_poller.start()

    # 3. Start FastAPI Server on main thread
    logger.info("🚀 Starting FastAPI Server on http://localhost:8000 ...")
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
