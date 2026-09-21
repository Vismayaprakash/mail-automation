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
    tunnel_domain = os.getenv("TUNNEL_DOMAIN", "").strip()
    if tunnel_domain:
        logger.info(f"Starting Permanent Tunnel for domain: {tunnel_domain}...")
        cmd = ["ngrok", "http", f"--domain={tunnel_domain}", "8000"]
        subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print("\n" + "=" * 70)
        print("🌐 PERMANENT TUNNEL READY!")
        print(f"📌 Webhook Callback URL: https://{tunnel_domain}/webhook/whatsapp")
        print("📌 Verify Token:        mail_automation_secret_verify_token")
        print("=" * 70 + "\n")
        sys.stdout.flush()
        return

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
    """Background thread polling Gmail inbox in parallel multi-message mode."""
    init_db()
    time.sleep(5)
    logger.info("📡 Live Gmail Inbox Poller started in background thread (Parallel Multi-Message Ingest Mode)...")
    while True:
        try:
            from database.session import SessionLocal
            from database.models import EmailThread
            db = SessionLocal()

            # Process all unread emails so every email is summarized and sent to WhatsApp immediately
            unread_emails = gmail_client.fetch_unread_messages()
            for mail in unread_emails:
                logger.info(f"📧 [Parallel Ingest] Processing Email from '{mail['sender']}' | Subject: '{mail['subject']}'")
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
                logger.info(f"📱 WhatsApp Approval Prompt Sent for '{mail['subject']}'!")

            db.close()
        except Exception as e:
            logger.error(f"Error in Gmail poller thread: {e}")
        time.sleep(interval_seconds)

def start_daily_reminder_scheduler(target_hour: int = 9, target_minute: int = 0):
    """Background thread that triggers daily pending email reminder at 9:00 AM local time every day."""
    from datetime import datetime
    time.sleep(2)
    logger.info(f"⏰ Daily Pending Email Reminder Scheduler started (Scheduled Daily for {target_hour:02d}:{target_minute:02d} AM local time)...")
    last_reminder_date = None

    while True:
        try:
            now = datetime.now()
            today_date = now.date()
            if last_reminder_date != today_date:
                if now.hour > target_hour or (now.hour == target_hour and now.minute >= target_minute):
                    from database.session import SessionLocal
                    db = SessionLocal()
                    count = orchestrator.send_daily_pending_reminders(db)
                    db.close()
                    last_reminder_date = today_date
                    logger.info(f"Daily 9:00 AM reminder check complete for date {today_date}. Reminded: {count}")
        except Exception as e:
            logger.error(f"Error in daily reminder scheduler: {e}")
        time.sleep(30)

def main():
    # 1. Start Cloudflare Tunnel in background thread
    t_tunnel = threading.Thread(target=start_cloudflare_tunnel, daemon=True)
    t_tunnel.start()

    # 2. Start Gmail Poller in background thread
    t_poller = threading.Thread(target=start_gmail_poller, daemon=True)
    t_poller.start()

    # 3. Start Daily Reminder Scheduler in background thread
    t_reminder = threading.Thread(target=start_daily_reminder_scheduler, daemon=True)
    t_reminder.start()

    # 4. Start FastAPI Server on main thread
    logger.info("🚀 Starting FastAPI Server on http://localhost:8000 ...")
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
