from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from twilio.request_validator import RequestValidator
from app.db import SessionLocal
from app.services.business_service import get_business_by_phone
import os


router = APIRouter(prefix="/call", tags=["Calls"])


TWILIO_WEBHOOK_SECRET = os.getenv("TWILIO_WEBHOOK_SECRET")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")


validator = RequestValidator(AUTH_TOKEN)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/inbound")
async def inbound_call(request: Request, db: Session = Depends(get_db)):
    """
    Handle incoming phone calls from Twilio.
    """

    # --------------------------
    # 1. Validate Twilio Request
    # --------------------------
    url = str(request.url)
    form = await request.form()
    data = dict(form)

    signature = request.headers.get("X-Twilio-Signature", "")

    if os.getenv("TWILIO_VALIDATE_SIGNATURES") == "true":
        if not validator.validate(url, data, signature):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    # --------------------------
    # 2. Extract caller + business number
    # --------------------------
    to_number = data.get("To") or data.get("Called")
    from_number = data.get("From")

    if not to_number:
        raise HTTPException(status_code=400, detail="Missing 'To' number")

    # Clean number format
    to_number = to_number.strip()

    # --------------------------
    # 3. Find business by phone number
    # --------------------------
    business = get_business_by_phone(db, to_number)

    if not business:
        return f"""
        <Response>
            <Say>Sorry, this number is not assigned to any business.</Say>
        </Response>
        """

    # --------------------------
    # 4. Return TwiML for media streaming
    # (Phase 4 will connect audio to GPT)
    # --------------------------
    # Twilio will stream audio to /call/stream
    stream_url = f"{os.getenv('API_URL')}/call/stream?business_id={business.id}"

    return f"""
    <Response>
        <Connect>
            <Stream url="{stream_url}" />
        </Connect>
    </Response>
    """
