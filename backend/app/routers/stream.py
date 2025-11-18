from fastapi import APIRouter, WebSocket, Request
from typing import Optional
from app.services.llm_realtime import handle_realtime_audio

router = APIRouter(prefix="/call", tags=["Streaming"])


@router.websocket("/stream")
async def stream_audio(websocket: WebSocket, business_id: int):
    """
    WebSocket endpoint for Twilio Media Streams.
    
    Twilio will connect directly to this WebSocket endpoint
    and stream audio bidirectionally.
    """
    try:
        await websocket.accept()
        print(f"⚡ Twilio WS connected (business_id={business_id})")
        await handle_realtime_audio(websocket, business_id)
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        import traceback
        traceback.print_exc()


@router.get("/stream")
async def stream_preflight(request: Request, business_id: Optional[int] = None):
    """
    Twilio performs a GET request to the Stream URL before 
    establishing the WebSocket connection.
    
    This MUST return 200 OK or Twilio will not proceed.
    FastAPI automatically routes WebSocket upgrades to the 
    @router.websocket() handler above.
    """
    print(f"🟢 Twilio preflight GET /call/stream (business_id={business_id})")
    return {"status": "ok"}
