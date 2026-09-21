import sys
import logging
from pathlib import Path

# Ensure UTF-8 stdout encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.session import init_db, SessionLocal
from core.state_machine import orchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("send_pending_reminders")

def main():
    init_db()
    db = SessionLocal()
    try:
        count = orchestrator.send_daily_pending_reminders(db)
        logger.info(f"Daily pending reminder execution finished. Total reminded: {count}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
