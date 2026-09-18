import sys
import time
import logging
from pathlib import Path

# Ensure UTF-8 stdout encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.session import init_db, SessionLocal
from integrations.gmail_client import gmail_client
from core.state_machine import orchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("gmail_poller")

def start_polling(interval_seconds: int = 15):
    """Periodically check live Gmail inbox for new unread emails."""
    init_db()
    logger.info("=" * 60)
    logger.info("📡 LIVE GMAIL INBOX POLLER STARTED")
    logger.info(f"Checking for new user emails every {interval_seconds} seconds...")
    logger.info("=" * 60)

    while True:
        try:
            db = SessionLocal()
            unread_emails = gmail_client.fetch_unread_messages()
            
            if unread_emails:
                logger.info(f"Found {len(unread_emails)} new user email(s) in inbox!")
                for mail in unread_emails:
                    logger.info(f"\n📧 Processing Email: From '{mail['sender']}' | Subject: '{mail['subject']}'")
                    logger.info("🤖 Generating RAG Context & Ollama AI Draft...")
                    
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
                    
                    # Mark email as read in Gmail after processing
                    gmail_client.mark_as_read(mail["message_id"])
                    logger.info(f"📱 WhatsApp Approval Prompt Sent for '{mail['subject']}'!")
            
            db.close()
        except Exception as e:
            logger.error(f"Error during Gmail polling loop: {e}")

        time.sleep(interval_seconds)

if __name__ == "__main__":
    start_polling()
