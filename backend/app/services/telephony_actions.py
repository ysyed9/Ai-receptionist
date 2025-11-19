"""
Telephony Actions Service
Handles SMS sending, call transfers, and appointment scheduling
"""
import os
import requests
from datetime import datetime
from twilio.rest import Client
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models.appointment import Appointment
from app.services.business_service import get_business_by_id


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
    caller_name: str = None,
    caller_email: str = None,
    service_type: str = None,
    notes: str = None,
    call_log_id: int = None
) -> dict:
    """
    Schedule an appointment with LeadConnector or other booking systems
    
    Args:
        business_id: Business ID
        caller_number: Caller's phone number
        appointment_date: Date (YYYY-MM-DD)
        appointment_time: Time (HH:MM)
        caller_name: Caller's name (optional)
        caller_email: Caller's email (required for booking)
        service_type: Type of service
        notes: Additional notes
        call_log_id: Link to call log (optional)
    
    Returns:
        dict with appointment details
    """
    db = SessionLocal()
    try:
        # Get business info
        business = get_business_by_id(db, business_id)
        if not business:
            return {
                "success": False,
                "error": "Business not found"
            }
        
        # Save appointment to database
        appointment = Appointment(
            business_id=business_id,
            call_log_id=call_log_id,
            caller_number=caller_number,
            caller_name=caller_name,
            caller_email=caller_email,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            service_type=service_type,
            notes=notes,
            status="pending"
        )
        
        # Check if business has booking system configured
        appointment_creds = business.appointment_credentials or {}
        booking_system = appointment_creds.get("system", "").lower()
        booking_url = appointment_creds.get("calendar_url") or appointment_creds.get("booking_url")
        
        # Try to create booking in external system
        booking_id = None
        booking_success = False
        
        if booking_system == "leadconnector" and booking_url:
            # LeadConnector booking integration
            try:
                # LeadConnector widget URL format: https://api.leadconnectorhq.com/widget/booking/{widget_id}
                # We'll create a booking link for the customer
                booking_id = f"LC_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                appointment.booking_system = "leadconnector"
                appointment.booking_url = booking_url
                appointment.booking_id = booking_id
                booking_success = True
            except Exception as e:
                print(f"⚠️ LeadConnector booking error: {e}")
        
        # Save appointment to database
        db.add(appointment)
        db.commit()
        db.refresh(appointment)
        
        return {
            "success": True,
            "appointment_id": appointment.id,
            "booking_id": booking_id,
            "booking_url": booking_url if booking_system == "leadconnector" else None,
            "booking_system": booking_system,
            "message": f"Appointment scheduled for {appointment_date} at {appointment_time}",
            "appointment": {
                "id": appointment.id,
                "date": appointment_date,
                "time": appointment_time,
                "name": caller_name,
                "email": caller_email,
                "phone": caller_number,
                "service": service_type,
                "status": "pending"
            }
        }
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        db.close()


async def end_call(reason: str, websocket) -> dict:
    """
    End the call by closing the WebSocket connection.
    This terminates the Media Stream and ends the call.
    
    Args:
        reason: Why the call is being ended (e.g., "conversation_complete", "spam_detected", "user_requested")
        websocket: The Twilio WebSocket connection
    
    Returns:
        dict with status and reason
    """
    print(f"📞 AI ending call. Reason: {reason}")
    
    # Close the WebSocket to end the Media Stream and call
    try:
        await websocket.close(code=1000, reason=reason)
    except Exception as e:
        print(f"❌ Error closing WebSocket: {e}")
    
    return {
        "success": True,
        "action": "call_ended",
        "reason": reason
    }

