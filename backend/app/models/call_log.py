from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Float
from sqlalchemy.sql import func
from app.db import Base


class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, index=True, nullable=False)
    stream_sid = Column(String(100), unique=True, index=True)  # Twilio stream SID
    caller_number = Column(String(20))
    called_number = Column(String(20))
    
    # Timing
    start_time = Column(DateTime(timezone=True), server_default=func.now())
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # Content
    transcript = Column(Text)  # Full conversation transcript
    actions_taken = Column(JSON)  # List of actions: ["rag_search", "transfer_call", "send_sms", etc.]
    
    # Status
    status = Column(String(50), default="active")  # active, completed, transferred, failed
    
    # Metadata
    metadata = Column(JSON)  # Additional data like RAG queries, function calls, etc.
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

