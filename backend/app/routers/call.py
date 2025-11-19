from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import Response
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
    
    # Normalize phone number: add + if missing
    if to_number and not to_number.startswith('+'):
        to_number = '+' + to_number
    
    print(f"📞 Inbound call: To={to_number}, From={from_number}")

    # --------------------------
    # 3. Find business by phone number
    # --------------------------
    business = get_business_by_phone(db, to_number)
    print(f"🔍 Business lookup result: {business}")

    if not business:
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Sorry, this number is not assigned to any business.</Say>
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    # --------------------------
    # 4. Return TwiML for media streaming
    # (Phase 4 will connect audio to GPT)
    # --------------------------
    # Twilio will stream audio to /call/stream
    # Convert HTTPS to WSS for WebSocket
    api_url = os.getenv('API_URL')
    ws_url = api_url.replace('https://', 'wss://').replace('http://', 'ws://')
    stream_url = f"{ws_url}/call/stream"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{stream_url}">
            <Parameter name="business_id" value="{business.id}" />
        </Stream>
    </Connect>
</Response>"""
    
    return Response(content=twiml, media_type="application/xml")
