import sys
import os
import logging
from pathlib import Path

# Ensure UTF-8 stdout encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(r"c:\Users\visma\Desktop\Mail Automation")

from database.session import init_db, SessionLocal
from integrations.gmail_client import gmail_client
from core.state_machine import orchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("poll_now")

def poll_now():
    init_db()
    db = SessionLocal()
    try:
        logger.info("📡 Checking Gmail inbox for new unread messages...")
        unread_emails = gmail_client.fetch_unread_messages()
        logger.info(f"Found {len(unread_emails)} unread actionable email(s) in Gmail inbox.")
        
        for mail in unread_emails:
            logger.info(f"📧 Processing Email from '{mail['sender']}' | Subject: '{mail['subject']}'")
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
    finally:
        db.close()

if __name__ == "__main__":
    poll_now()
