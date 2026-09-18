import sys
from pathlib import Path

# Ensure UTF-8 stdout encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.rag import rag_manager

def ingest_sample_past_emails():
    """Ingest sample past emails into ChromaDB to prime the local RAG engine with tone & history."""
    
    sample_emails = [
        {
            "id": "past_001",
            "sender": "vismanth@example.com",
            "recipient": "alex.dev@techcorp.com",
            "subject": "Re: API Integration Timeline",
            "body": "Hi Alex,\n\nThanks for checking in! The backend API integration is progressing well. We should have the endpoint ready for staging by Thursday afternoon.\n\nBest regards,\nVismanth",
            "is_sent": True
        },
        {
            "id": "past_002",
            "sender": "vismanth@example.com",
            "recipient": "sarah.m@designstudio.io",
            "subject": "Re: Feedback on UI Wireframes",
            "body": "Hey Sarah,\n\nLove the new dark mode aesthetics! The layout looks super clean. Could we adjust the button padding slightly on mobile?\n\nCheers,\nVismanth",
            "is_sent": True
        },
        {
            "id": "past_003",
            "sender": "vismanth@example.com",
            "recipient": "client.support@cloudhost.net",
            "subject": "Re: Server Maintenance Schedule",
            "body": "Hello Support Team,\n\nUnderstood. Please notify us 24 hours prior to starting scheduled maintenance.\n\nThanks,\nVismanth",
            "is_sent": True
        }
    ]

    print("Indexing past emails into ChromaDB...")
    for mail in sample_emails:
        rag_manager.add_email(
            email_id=mail["id"],
            sender=mail["sender"],
            recipient=mail["recipient"],
            subject=mail["subject"],
            body=mail["body"],
            is_sent=mail["is_sent"]
        )
    
    print("✅ Successfully indexed 3 sample past emails into local RAG ChromaDB!")

if __name__ == "__main__":
    ingest_sample_past_emails()
