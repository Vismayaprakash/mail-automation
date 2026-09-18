import logging
import os
import tempfile
from fastapi import FastAPI, Depends, Request, Response, HTTPException, status
from sqlalchemy.orm import Session
from config import settings
from database.session import init_db, get_db
from database.models import EmailThread, ThreadStatus
from core.state_machine import orchestrator
from integrations.whatsapp_client import whatsapp_client

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mail_automation")

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

@app.on_event("startup")
def on_startup():
    """Initialize database tables on server startup."""
    init_db()
    logger.info(f"{settings.APP_NAME} started successfully.")

@app.get("/")
def read_root():
    return {
        "status": "online",
        "app": settings.APP_NAME,
        "ollama_model": settings.OLLAMA_MODEL,
        "whisper_size": settings.WHISPER_MODEL_SIZE
    }

# ---------------------------------------------------------
# Gmail Webhook / Notification Endpoint
# ---------------------------------------------------------
@app.post("/webhook/gmail")
async def gmail_webhook(request: Request, db: Session = Depends(get_db)):
    """Webhook endpoint triggered when a new email arrives in Gmail."""
    try:
        data = await request.json()
        logger.info(f"Received Gmail Webhook Payload: {data}")
        
        message_id = data.get("message_id")
        thread_id = data.get("thread_id")
        sender = data.get("sender")
        sender_name = data.get("sender_name", sender)
        recipient = data.get("recipient", settings.GMAIL_USER_EMAIL)
        subject = data.get("subject", "No Subject")
        body = data.get("body", "")

        if not message_id or not sender:
            raise HTTPException(status_code=400, detail="Missing required email fields (message_id, sender).")

        email_thread = orchestrator.process_incoming_email(
            db=db,
            message_id=message_id,
            thread_id=thread_id or message_id,
            sender=sender,
            sender_name=sender_name,
            recipient=recipient,
            subject=subject,
            body=body
        )

        return {"status": "success", "thread_id": email_thread.thread_id, "email_status": email_thread.status}
    except Exception as e:
        logger.error(f"Error processing Gmail webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------
# WhatsApp Cloud API Webhook Endpoints
# ---------------------------------------------------------
@app.get("/webhook/whatsapp")
def verify_whatsapp_webhook(request: Request):
    """Webhook verification endpoint required by Meta WhatsApp Cloud API."""
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp Webhook verified successfully.")
        return Response(content=challenge, media_type="text/plain")
    
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification token mismatch.")

PROCESSED_MSG_IDS = set()

def process_voice_note_async(thread_id: str, media_id: str):
    """Background execution for downloading and processing voice note revisions without delaying HTTP 200 OK to Meta."""
    from database.session import SessionLocal
    db = SessionLocal()
    try:
        temp_dir = tempfile.gettempdir()
        audio_path = os.path.join(temp_dir, f"wa_voice_{media_id}.ogg")
        downloaded = whatsapp_client.download_media(media_id, audio_path)
        if downloaded and os.path.exists(audio_path):
            orchestrator.revise_via_voice(
                db=db,
                thread_id=thread_id,
                audio_file_path=audio_path
            )
    except Exception as e:
        logger.error(f"Error processing voice note in background thread: {e}")
    finally:
        db.close()

def process_text_revision_async(thread_id: str, user_text: str):
    """Background execution for text revision without delaying HTTP 200 OK."""
    from database.session import SessionLocal
    db = SessionLocal()
    try:
        pending_thread = db.query(EmailThread).filter(EmailThread.thread_id == thread_id).first()
        if pending_thread:
            logger.info(f"Received text revision instruction: '{user_text}'")
            revised = llm_manager.revise_draft(
                subject=pending_thread.subject,
                sender=pending_thread.sender,
                original_email=pending_thread.body,
                previous_draft=pending_thread.proposed_reply,
                feedback=user_text
            )
            pending_thread.proposed_reply = revised
            db.commit()
            
            whatsapp_client.send_approval_request(
                thread_id=pending_thread.thread_id,
                sender_name=pending_thread.sender_name,
                sender_email=pending_thread.sender,
                subject=pending_thread.subject,
                summary=f"{pending_thread.summary}\n\n📝 *Text Feedback Applied:*\n\"{user_text}\"",
                draft_reply=revised
            )
    except Exception as e:
        logger.error(f"Error processing text revision in background: {e}")
    finally:
        db.close()

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    """Webhook endpoint receiving user WhatsApp messages (text approvals or audio voice notes)."""
    try:
        body = await request.json()
        logger.info(f"Received WhatsApp Payload: {body}")

        # Extract entry & message payload
        entries = body.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                val = change.get("value", {})
                messages = val.get("messages", [])
                for msg in messages:
                    msg_id = msg.get("id")
                    if msg_id and msg_id in PROCESSED_MSG_IDS:
                        logger.info(f"Duplicate WhatsApp message ID '{msg_id}'. Ignoring retry.")
                        continue
                    if msg_id:
                        PROCESSED_MSG_IDS.add(msg_id)

                    # Ignore stale messages queued by Meta while server was offline (> 2 minutes old)
                    import time
                    msg_ts = int(msg.get("timestamp", 0))
                    current_ts = int(time.time())
                    if msg_ts > 0 and (current_ts - msg_ts > 120):
                        logger.info(f"Stale WhatsApp message ID '{msg_id}' from Meta backlog queue (Age: {current_ts - msg_ts}s). Ignoring.")
                        continue

                    msg_type = msg.get("type")
                    
                    # Fetch active or oldest pending approval thread (FIFO lock)
                    pending_thread = None
                    if orchestrator.active_thread_id:
                        pending_thread = db.query(EmailThread).filter(
                            EmailThread.thread_id == orchestrator.active_thread_id,
                            EmailThread.status == ThreadStatus.PENDING_APPROVAL.value
                        ).first()

                    if not pending_thread:
                        pending_thread = db.query(EmailThread).filter(
                            EmailThread.status == ThreadStatus.PENDING_APPROVAL.value
                        ).order_by(EmailThread.created_at.asc()).first()

                    if not pending_thread:
                        logger.warning("Received WhatsApp reply but no pending email thread found.")
                        continue

                    # Case 1: User sent Text
                    if msg_type == "text":
                        user_text = msg.get("text", {}).get("body", "").strip()
                        upper_text = user_text.upper()
                        
                        # 1. Greetings / Session Pings -> Just resend current prompt, DO NOT REVISE OR SEND
                        if upper_text in ["HI", "HELLO", "HEY", "START", "PING", "HELP"]:
                            logger.info(f"Received greeting '{user_text}'. Re-sending active approval prompt.")
                            whatsapp_client.send_approval_request(
                                thread_id=pending_thread.thread_id,
                                sender_name=pending_thread.sender_name,
                                sender_email=pending_thread.sender,
                                subject=pending_thread.subject,
                                summary=pending_thread.summary,
                                draft_reply=pending_thread.proposed_reply
                            )
                            continue

                        # 2. Explicit Approval -> ONLY "YES" or "APPROVE"
                        if upper_text in ["YES", "APPROVE"]:
                            logger.info(f"User explicitly approved thread '{pending_thread.subject}'. Sending email via Gmail API.")
                            orchestrator.approve_and_send(db, pending_thread.thread_id)
                        
                        # 3. Explicit Rejection -> "NO" or "REJECT"
                        elif upper_text in ["NO", "REJECT"]:
                            whatsapp_client.send_text_message(
                                f"⏸️ Reply rejected for thread '{pending_thread.subject}'. Send a voice note or text with instructions to revise."
                            )
                        
                        # 4. Text Revision Instructions -> Revise draft asynchronously
                        else:
                            import threading
                            threading.Thread(
                                target=process_text_revision_async,
                                args=(pending_thread.thread_id, user_text),
                                daemon=True
                            ).start()

                    # Case 2: User sent Voice Note / Audio
                    elif msg_type in ["audio", "voice"]:
                        media_id = msg.get("audio", {}).get("id") or msg.get("voice", {}).get("id")
                        if media_id:
                            import threading
                            threading.Thread(
                                target=process_voice_note_async,
                                args=(pending_thread.thread_id, media_id),
                                daemon=True
                            ).start()

        return {"status": "event_received"}
    except Exception as e:
        logger.error(f"Error handling WhatsApp webhook: {e}")
        return {"status": "error", "message": str(e)}
