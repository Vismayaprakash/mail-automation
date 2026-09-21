from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum
import enum
from database.session import Base

class ThreadStatus(str, enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    REVISING = "REVISING"
    APPROVED = "APPROVED"
    SENT = "SENT"
    REJECTED = "REJECTED"

class EmailThread(Base):
    __tablename__ = "email_threads"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(String, index=True, nullable=False)
    message_id = Column(String, unique=True, index=True, nullable=False)
    sender = Column(String, index=True, nullable=False)
    sender_name = Column(String, nullable=True)
    recipient = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    
    summary = Column(Text, nullable=True)
    proposed_reply = Column(Text, nullable=True)
    status = Column(String, default=ThreadStatus.PENDING_APPROVAL.value)
    
    whatsapp_message_id = Column(String, nullable=True)
    voice_feedback_transcript = Column(Text, nullable=True)
    attachments = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    relationship_notes = Column(Text, nullable=True)
    last_interaction = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(String, index=True, nullable=True)
    action = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
