from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.sql import func
from app.db import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, index=True, nullable=False)
    call_log_id = Column(Integer, index=True, nullable=True)  # Link to call log
    
    # Contact Information
    caller_number = Column(String(20))
    caller_name = Column(String(200))
    caller_email = Column(String(200))
    
    # Appointment Details
    appointment_date = Column(String(20))  # YYYY-MM-DD
    appointment_time = Column(String(20))  # HH:MM
    service_type = Column(String(200))
    notes = Column(Text)
    
    # Status
    status = Column(String(50), default="pending")  # pending, confirmed, cancelled
    
    # External Booking System
    booking_system = Column(String(50))  # leadconnector, calendly, custom
    booking_url = Column(String(500))
    booking_id = Column(String(200))  # External booking ID
    
    # Extra Metadata (note: 'metadata' is reserved by SQLAlchemy)
    extra_metadata = Column(JSON)  # Additional data
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

