import logging
from sqlalchemy.orm import Session
from database.models import EmailThread, ThreadStatus, AuditLog
from core.llm import llm_manager
from core.rag import rag_manager
from core.whisper_transcriber import whisper_transcriber
from integrations.gmail_client import gmail_client
from integrations.whatsapp_client import whatsapp_client

logger = logging.getLogger(__name__)

class WorkflowOrchestrator:
    """Orchestrates end-to-end workflow between Email, RAG, Ollama, Whisper, DB, and WhatsApp."""

    def __init__(self):
        self.active_thread_id: str = None

    def process_incoming_email(
        self,
        db: Session,
        message_id: str,
        thread_id: str,
        sender: str,
        sender_name: str,
        recipient: str,
        subject: str,
        body: str
    ) -> EmailThread:
        """Process a new incoming email: retrieve RAG context, generate Ollama summary & draft, store DB, send WhatsApp approval."""
        
        # Check if already processed
        existing = db.query(EmailThread).filter(EmailThread.message_id == message_id).first()
        if existing:
            logger.info(f"Email {message_id} already processed. Skipping.")
            return existing

        logger.info(f"Processing new email from {sender} - '{subject}'")

        # Step 1: Retrieve RAG context from ChromaDB
        rag_context = rag_manager.query_context(sender_email=sender, current_email_body=body)

        # Step 2: Generate Ollama Summary & Draft Reply
        summary = llm_manager.summarize_email(subject=subject, sender=sender, body=body)
        proposed_reply = llm_manager.generate_draft(subject=subject, sender=sender, body=body, rag_context=rag_context)

        # Step 3: Save to SQLite Database
        email_thread = EmailThread(
            thread_id=thread_id,
            message_id=message_id,
            sender=sender,
            sender_name=sender_name or sender,
            recipient=recipient,
            subject=subject,
            body=body,
            summary=summary,
            proposed_reply=proposed_reply,
            status=ThreadStatus.PENDING_APPROVAL.value
        )
        db.add(email_thread)
        db.commit()
        db.refresh(email_thread)

        # Step 4: Dispatch WhatsApp Approval Request with Previous Context
        self.active_thread_id = thread_id
        past_context = self._get_past_context(db=db, sender=sender, current_message_id=message_id)

        wa_msg_id = whatsapp_client.send_approval_request(
            thread_id=thread_id,
            sender_name=email_thread.sender_name,
            sender_email=sender,
            subject=subject,
            summary=summary,
            draft_reply=proposed_reply,
            past_context=past_context
        )
        
        email_thread.whatsapp_message_id = wa_msg_id
        db.add(AuditLog(thread_id=thread_id, action="EMAIL_RECEIVED_DRAFT_SENT", details=f"WhatsApp ID: {wa_msg_id}"))
        db.commit()

        return email_thread

    def _get_past_context(self, db: Session, sender: str, current_message_id: str) -> str:
        """Fetch summary of previous interactions with this contact for WhatsApp notification."""
        try:
            past_threads = db.query(EmailThread).filter(
                (EmailThread.sender == sender) | (EmailThread.recipient == sender),
                EmailThread.message_id != current_message_id
            ).order_by(EmailThread.created_at.desc()).limit(3).all()

            if not past_threads:
                return "No previous interaction history found with this contact."

            lines = []
            for t in reversed(past_threads):
                t_summary = (t.summary or t.body or "").strip().replace("\n", " ")
                if len(t_summary) > 120:
                    t_summary = t_summary[:117] + "..."
                lines.append(f"* *{t.subject}* [{t.status}]: {t_summary}")

            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error fetching past context for {sender}: {e}")
            return ""

    def approve_and_send(self, db: Session, thread_id: str) -> bool:
        """Approve and dispatch the current email draft via Gmail API."""
        thread = db.query(EmailThread).filter(EmailThread.thread_id == thread_id).first()
        if not thread:
            logger.error(f"Thread {thread_id} not found in database.")
            return False

        logger.info(f"Approved thread {thread_id}. Sending email via Gmail API...")

        # Step 1: Send via Gmail API
        success = gmail_client.send_email(
            to_email=thread.sender,
            subject=f"Re: {thread.subject}",
            body_text=thread.proposed_reply,
            thread_id=thread.thread_id
        )

        if success:
            thread.status = ThreadStatus.SENT.value
            self.active_thread_id = None
            db.commit()

            # Step 2: Index sent email in RAG for learning tone
            rag_manager.add_email(
                email_id=f"sent_{thread.message_id}",
                sender=thread.recipient,
                recipient=thread.sender,
                subject=f"Re: {thread.subject}",
                body=thread.proposed_reply,
                is_sent=True
            )

            # Step 3: Notify WhatsApp
            whatsapp_client.send_text_message(
                f"✅ *Email Sent Successfully!*\n\nReplied to: {thread.sender_name}\nSubject: Re: {thread.subject}"
            )
            db.add(AuditLog(thread_id=thread_id, action="EMAIL_APPROVED_AND_SENT", details=thread.proposed_reply[:100]))
            db.commit()
            return True

        return False

    def reject_thread(self, db: Session, thread_id: str) -> bool:
        """Reject/skip the current email thread without sending any reply."""
        thread = db.query(EmailThread).filter(EmailThread.thread_id == thread_id).first()
        if not thread:
            logger.error(f"Thread {thread_id} not found in database.")
            return False

        logger.info(f"Rejected thread {thread_id}. Marking status as REJECTED and skipping email reply.")
        thread.status = ThreadStatus.REJECTED.value
        self.active_thread_id = None
        db.commit()

        whatsapp_client.send_text_message(
            f"⏭️ *Email Skipped*\n\nSkipped reply for: {thread.sender_name}\nSubject: {thread.subject}\nProceeding to next email."
        )
        db.add(AuditLog(thread_id=thread_id, action="EMAIL_REJECTED_SKIPPED", details=f"Thread {thread_id} skipped by user."))
        db.commit()
        return True

    def revise_via_voice(self, db: Session, thread_id: str, audio_file_path: str) -> bool:
        """Transcribe voice note, revise draft with Ollama, update DB, and send NEW WhatsApp approval request (DO NOT AUTO-SEND)."""
        thread = db.query(EmailThread).filter(EmailThread.thread_id == thread_id).first()
        if not thread:
            logger.error(f"Thread {thread_id} not found.")
            return False

        logger.info(f"Transcribing voice revision for thread {thread_id}...")

        # Step 1: Transcribe local voice audio with Whisper
        transcript = whisper_transcriber.transcribe(audio_file_path)
        logger.info(f"Whisper Transcript: '{transcript}'")
        thread.voice_feedback_transcript = transcript

        # Step 2: Revise draft reply using Ollama
        revised_reply = llm_manager.revise_draft(
            subject=thread.subject,
            sender=thread.sender,
            original_email=thread.body,
            previous_draft=thread.proposed_reply,
            feedback=transcript
        )

        thread.proposed_reply = revised_reply
        thread.status = ThreadStatus.PENDING_APPROVAL.value
        db.commit()

        # Step 3: Send NEW WhatsApp Approval Request with revised draft (DO NOT SEND EMAIL YET)
        summary_with_transcript = f"{thread.summary}\n\n🎙️ *Voice Feedback Transcribed:*\n\"{transcript}\""
        
        wa_msg_id = whatsapp_client.send_approval_request(
            thread_id=thread_id,
            sender_name=thread.sender_name,
            sender_email=thread.sender,
            subject=thread.subject,
            summary=summary_with_transcript,
            draft_reply=revised_reply
        )

        thread.whatsapp_message_id = wa_msg_id
        db.add(AuditLog(thread_id=thread_id, action="VOICE_REVISION_DRAFT_UPDATED", details=transcript))
        db.commit()
        return True

orchestrator = WorkflowOrchestrator()
