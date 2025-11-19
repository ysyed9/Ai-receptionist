"""
Telephony Actions Service
Handles SMS sending, call transfers, and appointment scheduling
"""
import os
from datetime import datetime
from twilio.rest import Client
from sqlalchemy.orm import Session
from app.db import SessionLocal


TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def send_sms(to_number: str, message: str, from_number: str = None) -> dict:
    """
    Send SMS via Twilio
    
    Args:
        to_number: Phone number to send SMS to
        message: SMS message content
        from_number: Optional Twilio phone number (uses default if not provided)
    
    Returns:
        dict with status and message_id
    """
    if not twilio_client:
        return {
            "success": False,
            "error": "Twilio client not configured"
        }
    
    try:
        # Use default Twilio number if not provided
        if not from_number:
            from_number = os.getenv("TWILIO_PHONE_NUMBER")
        
        message_obj = twilio_client.messages.create(
            body=message,
            from_=from_number,
            to=to_number
        )
        
        return {
            "success": True,
            "message_id": message_obj.sid,
            "status": message_obj.status
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def transfer_call(stream_sid: str, to_number: str) -> dict:
    """
    Transfer a call to another number
    
    Args:
        stream_sid: Twilio stream SID
        to_number: Phone number to transfer to
    
    Returns:
        dict with status
    """
    # Note: Actual transfer is handled via WebSocket message to Twilio
    # This function is for logging/validation
    return {
        "success": True,
        "action": "transfer",
        "to_number": to_number,
        "stream_sid": stream_sid
    }


def schedule_appointment(
    business_id: int,
    caller_number: str,
    appointment_date: str,
    appointment_time: str,
    service_type: str = None,
    notes: str = None
) -> dict:
    """
    Schedule an appointment (placeholder - integrate with calendar system)
    
    Args:
        business_id: Business ID
        caller_number: Caller's phone number
        appointment_date: Date (YYYY-MM-DD)
        appointment_time: Time (HH:MM)
        service_type: Type of service
        notes: Additional notes
    
    Returns:
        dict with appointment details
    """
    # TODO: Integrate with actual appointment system (Calendly, etc.)
    # For now, this is a placeholder that logs the appointment
    
    db = SessionLocal()
    try:
        # In a real implementation, you would:
        # 1. Check business appointment_credentials
        # 2. Call calendar API (Calendly, Google Calendar, etc.)
        # 3. Create appointment
        # 4. Send confirmation
        
        appointment_data = {
            "business_id": business_id,
            "caller_number": caller_number,
            "appointment_date": appointment_date,
            "appointment_time": appointment_time,
            "service_type": service_type,
            "notes": notes,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Placeholder: Just return the appointment data
        # In production, save to database and create calendar event
        return {
            "success": True,
            "appointment": appointment_data,
            "message": "Appointment scheduled (placeholder - not saved to calendar)"
        }
    finally:
        db.close()

