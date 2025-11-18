from fastapi import APIRouter, WebSocket
from app.services.llm_realtime import handle_realtime_audio


router = APIRouter(prefix="/call", tags=["Streaming"])


@router.websocket("/stream")
async def stream_audio(websocket: WebSocket, business_id: int):
    await websocket.accept()
    await handle_realtime_audio(websocket, business_id)

