from fastapi import APIRouter, WebSocket, Request
from typing import Optional
from app.services.llm_realtime import handle_realtime_audio

print("=" * 80, flush=True)
print("🟢 STREAM.PY MODULE LOADED", flush=True)
print("=" * 80, flush=True)

router = APIRouter(prefix="/call", tags=["Streaming"])

print("🟢 STREAM ROUTER CREATED", flush=True)


@router.websocket("/stream")
async def stream_audio(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio Media Streams.
    
    Twilio will connect directly to this WebSocket endpoint
    and stream audio bidirectionally.
    """
    print("\n" + "="*80, flush=True)
    print("🔵🔵🔵 WEBSOCKET HANDLER CALLED 🔵🔵🔵", flush=True)
    print("="*80 + "\n", flush=True)
    print("🔵 WebSocket connection attempt...", flush=True)
    try:
        print("🔵 Accepting WebSocket...", flush=True)
        await websocket.accept()
        print("✅ WebSocket ACCEPTED", flush=True)
        
        # Wait for Twilio's "start" event which contains custom parameters
        print("🔵 Waiting for Twilio start event with business_id...", flush=True)
        import json
        business_id = 0
        stream_sid = None
        
        async for message in websocket.iter_text():
            data = json.loads(message)
            event = data.get("event")
            print(f"📨 Received event: {event}", flush=True)
            
            if event == "start":
                # Extract business_id from custom parameters
                custom_params = data.get("start", {}).get("customParameters", {})
                business_id = int(custom_params.get("business_id", 0))
                stream_sid = data.get('start', {}).get('streamSid') or data.get('streamSid')
                print(f"✅ Got business_id={business_id}, streamSid={stream_sid}", flush=True)
                break
        
        if business_id == 0:
            print("❌ NO BUSINESS ID RECEIVED - REJECT", flush=True)
            await websocket.close()
            return
        
        print(f"🚀 Calling handle_realtime_audio...", flush=True)
        await handle_realtime_audio(websocket, business_id, stream_sid)
        print("✅ handle_realtime_audio completed", flush=True)
    except Exception as e:
        print(f"❌ WebSocket error: {e}", flush=True)
        import traceback
        traceback.print_exc()

print("🟢 WEBSOCKET ROUTE REGISTERED", flush=True)

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
