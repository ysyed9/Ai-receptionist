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
from app.services.google_sheets import log_job_to_sheets, get_google_sheets_client


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
        
        # Update appointment status to "Booked"
        appointment.status = "Booked"
        db.commit()
        
        # Get call transcript/summary from call log if available
        call_summary = None
        if call_log_id:
            try:
                from app.models.call_log import CallLog
                call_log = db.query(CallLog).filter(CallLog.id == call_log_id).first()
                if call_log and call_log.transcript:
                    # Use transcript as summary (or generate a shorter summary if needed)
                    transcript = call_log.transcript.strip()
                    # Limit summary length to avoid Google Sheets cell limits (50k chars)
                    if len(transcript) > 1000:
                        # Use first 1000 chars + "..."
                        call_summary = transcript[:1000] + "..."
                    else:
                        call_summary = transcript
                    print(f"✅ Retrieved call transcript ({len(call_summary)} chars)")
            except Exception as e:
                print(f"⚠️ Could not retrieve call transcript: {e}")
        
        # Log to Google Sheets (if configured)
        sheets_logged = False
        sheets_config = business.google_sheets_credentials or {}
        spreadsheet_id = sheets_config.get("spreadsheet_id")
        worksheet_name = sheets_config.get("worksheet_name", "Jobs")
        # Credentials now come from environment variables (GOOGLE_SHEETS_CREDENTIALS_JSON or GOOGLE_SHEETS_CREDENTIALS_PATH)
        # DO NOT use credentials_json from config for security reasons
        sheets_creds_path = sheets_config.get("credentials_path")  # Still allow path override in config if needed
        
        if spreadsheet_id:
            try:
                sheets_result = log_job_to_sheets(
                    spreadsheet_id=spreadsheet_id,
                    worksheet_name=worksheet_name,
                    customer_name=caller_name or "",
                    customer_email=caller_email or "",
                    customer_phone=caller_number or "",
                    appointment_date=appointment_date,
                    appointment_time=appointment_time,
                    service_type=service_type or "",
                    status="Booked",
                    confirmation_sent="Pending",  # Will update after SMS
                    call_summary=call_summary or "",  # Add call summary
                    credentials_json=None,  # Use environment variable instead
                    credentials_path=sheets_creds_path,  # Allow path override from config if needed
                    extra_data={
                        "Booking ID": booking_id or "",
                        "Booking System": booking_system or ""
                    }
                )
                if sheets_result.get("success"):
                    sheets_logged = True
                    print(f"✅ Job logged to Google Sheets")
                else:
                    print(f"⚠️ Failed to log to Google Sheets: {sheets_result.get('error')}")
            except Exception as e:
                print(f"⚠️ Error logging to Google Sheets: {e}")
        
        # Send SMS confirmation via Twilio (if configured)
        sms_sent = False
        if caller_number and business.allowed_actions.get("sms", False):
            try:
                business_phone = business.phone_number or os.getenv("TWILIO_PHONE_NUMBER")
                
                # Create confirmation message
                sms_message = f"Hi {caller_name or 'there'}! Your appointment with {business.name} is confirmed for {appointment_date} at {appointment_time}."
                if service_type:
                    sms_message += f" Service: {service_type}."
                sms_message += f" Thank you!"
                
                sms_result = send_sms(
                    to_number=caller_number,
                    message=sms_message,
                    from_number=business_phone
                )
                
                if sms_result.get("success"):
                    sms_sent = True
                    
                    # Update Google Sheets confirmation status if logged
                    if sheets_logged and spreadsheet_id:
                        try:
                            # Credentials now come from environment variables
                            client = get_google_sheets_client(credentials_json=None, credentials_path=sheets_creds_path)
                            if client:
                                spreadsheet = client.open_by_key(spreadsheet_id)
                                worksheet = spreadsheet.worksheet(worksheet_name)
                                # Find the last row and update confirmation status
                                all_values = worksheet.get_all_values()
                                if all_values:
                                    last_row = len(all_values)
                                    # Update confirmation column (column 9, index 8)
                                    worksheet.update_cell(last_row, 9, "Yes")
                        except Exception as e:
                            print(f"⚠️ Could not update Google Sheets confirmation status: {e}")
                    
                    print(f"✅ SMS confirmation sent to {caller_number}")
                else:
                    print(f"⚠️ Failed to send SMS: {sms_result.get('error')}")
            except Exception as e:
                print(f"⚠️ Error sending SMS confirmation: {e}")
        
        return {
            "success": True,
            "appointment_id": appointment.id,
            "booking_id": booking_id,
            "booking_url": booking_url if booking_system == "leadconnector" else None,
            "booking_system": booking_system,
            "sms_sent": sms_sent,
            "sheets_logged": sheets_logged,
            "message": f"Appointment scheduled for {appointment_date} at {appointment_time}",
            "appointment": {
                "id": appointment.id,
                "date": appointment_date,
                "time": appointment_time,
                "name": caller_name,
                "email": caller_email,
                "phone": caller_number,
                "service": service_type,
                "status": "Booked"
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

