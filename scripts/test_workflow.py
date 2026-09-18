import os
import sys
import time
from pathlib import Path

# Ensure UTF-8 stdout encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add parent directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.session import init_db, SessionLocal
from database.models import EmailThread, ThreadStatus
from core.state_machine import orchestrator
from core.rag import rag_manager
from core.llm import llm_manager
from core.whisper_transcriber import whisper_transcriber

def run_local_e2e_simulation():
    print("=" * 70)
    print("🚀 STARTING LOCAL END-TO-END WORKFLOW SIMULATION")
    print("=" * 70)

    # 1. Initialize SQLite DB
    init_db()
    db = SessionLocal()

    # 2. Populate RAG database with sample past emails
    print("\n[Step 1] Indexing past email tone & contact history into ChromaDB...")
    rag_manager.add_email(
        email_id="past_test_001",
        sender="vismanth@example.com",
        recipient="alex.dev@techcorp.com",
        subject="Re: Backend Timeline",
        body="Hi Alex, Thanks for checking in! The backend API integration is progressing well. We should have the endpoint ready for staging soon. - Vismanth",
        is_sent=True
    )

    # 3. Simulate Incoming Email
    print("\n[Step 2] Simulating incoming email from Alex...")
    test_msg_id = f"msg_{int(time.time())}"
    test_thread_id = f"thread_{int(time.time())}"
    sender_email = "alex.dev@techcorp.com"
    subject = "Status Update on Staging Release"
    incoming_body = (
        "Hi Vismanth,\n\n"
        "Can you confirm when the new API integration will be deployed to the staging environment? "
        "Our frontend team needs to test the endpoints before Friday.\n\n"
        "Best regards,\nAlex"
    )

    print(f"From: {sender_email}")
    print(f"Subject: {subject}")
    print(f"Body:\n{incoming_body}\n")

    # 4. Run Email Ingestion & Draft Generation via Ollama & RAG
    print("[Step 3] Running RAG retrieval & Ollama LLM generation...")
    email_thread = orchestrator.process_incoming_email(
        db=db,
        message_id=test_msg_id,
        thread_id=test_thread_id,
        sender=sender_email,
        sender_name="Alex Developer",
        recipient="vismanth@example.com",
        subject=subject,
        body=incoming_body
    )

    print("-" * 50)
    print("📊 OLLAMA GENERATED SUMMARY:")
    print(email_thread.summary)
    print("-" * 50)
    print("📝 OLLAMA PROPOSED DRAFT REPLY:")
    print(email_thread.proposed_reply)
    print("-" * 50)
    print(f"DB Thread Status: {email_thread.status}")

    # 5. Simulate User Approval Decision (Path B: Voice Note Revision)
    print("\n[Step 4] Simulating User Voice Note Revision...")
    simulated_voice_transcript = (
        "Tell Alex we need to push the staging deployment to Friday morning instead of Thursday "
        "because of scheduled database migrations."
    )
    print(f"🎙️ User Spoken Voice Note: '{simulated_voice_transcript}'")

    print("\n[Step 5] Revising draft with Ollama based on voice instruction...")
    revised_draft = llm_manager.revise_draft(
        subject=subject,
        sender=sender_email,
        original_email=incoming_body,
        previous_draft=email_thread.proposed_reply,
        feedback=simulated_voice_transcript
    )

    email_thread.proposed_reply = revised_draft
    email_thread.voice_feedback_transcript = simulated_voice_transcript
    email_thread.status = ThreadStatus.SENT.value
    db.commit()

    print("-" * 50)
    print("✨ FINAL REVISED EMAIL READY TO SEND:")
    print(email_thread.proposed_reply)
    print("-" * 50)
    print(f"✅ Final DB Status: {email_thread.status}")

    print("=" * 70)
    print("🎉 LOCAL SIMULATION COMPLETED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_local_e2e_simulation()
