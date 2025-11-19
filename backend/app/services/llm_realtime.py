import os
import json
import asyncio
import logging
from openai import AsyncOpenAI
from app.services.rag_service import search_knowledge
from app.services.business_service import get_business_by_id
from app.db import SessionLocal
from fastapi import WebSocket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def log(msg):
    logger.info(msg)
    print(msg, flush=True)


async def handle_realtime_audio(websocket: WebSocket, business_id: int, initial_stream_sid: str = None):
    """
    Main pipeline: Twilio WS <-> this function <-> OpenAI Realtime WS
    """
    
    log(f"🔄 Starting GPT Realtime session for business_id={business_id}...")

    # Load business settings
    db = SessionLocal()
    business = get_business_by_id(db, business_id)
    db.close()

    if not business:
        log(f"❌ Business {business_id} not found!")
        await websocket.close()
        return
    
    log(f"✅ Business loaded: {business.name}")

    # Track Twilio stream
    stream_sid = initial_stream_sid
    twilio_connected = asyncio.Event()
    
    # If we already have stream_sid, mark as connected
    if stream_sid:
        log(f"✅ Twilio already connected (streamSid={stream_sid})")
        twilio_connected.set()

    try:
        log("🔌 Connecting to OpenAI Realtime API...")
        async with client.beta.realtime.connect(
            model=os.getenv("OPENAI_MODEL_REALTIME", "gpt-4o-realtime-preview-2024-12-17")
        ) as openai_ws:
            log("🤖 GPT Realtime session established!")
            
            # Configure session
            log("📝 Configuring OpenAI session with g711_ulaw audio format...")
            await openai_ws.session.update(
                session={
                    "modalities": ["text", "audio"],
                    "instructions": f"""You are the AI receptionist for {business.name}.
Tone: {business.tone}
Instructions: {business.instructions}

When someone connects, immediately greet them with: "Hello! Thank you for calling {business.name}. How can I help you today?"

If a caller asks business-related questions, check RAG memory using function: rag_search.

Allowed actions: {json.dumps(business.allowed_actions)}""",
                    "voice": "alloy",
                    "input_audio_format": "g711_ulaw",
                    "output_audio_format": "g711_ulaw",
                    "input_audio_transcription": {"model": "whisper-1"},
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 500
                    },
                    "tools": [
                        {
                            "type": "function",
                            "name": "rag_search",
                            "description": "Search business knowledge base",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "Search query"}
                                },
                                "required": ["query"]
                            }
                        },
                        {
                            "type": "function",
                            "name": "transfer_call",
                            "description": "Transfer call to forwarding number",
                            "parameters": {"type": "object", "properties": {}}
                        }
                    ],
                    "tool_choice": "auto"
                }
            )
            log("✅ Session configured: g711_ulaw, voice=alloy")

            async def openai_to_twilio():
                """AI → Twilio (audio out)"""
                log("📤 openai_to_twilio loop started")
                
                # Wait for Twilio stream to be ready
                await twilio_connected.wait()
                log("✅ Twilio connected, starting to send AI audio")
                
                # Track timestamp for outbound audio
                import time
                timestamp_ms = 0
                
                try:
                    async for event in openai_ws:
                        event_type = event.type
                        
                        # Send audio to Twilio
                        if event_type == "response.audio.delta":
                            if hasattr(event, 'delta') and event.delta and stream_sid:
                                # Send as Twilio media message (audio is base64 from OpenAI)
                                payload = event.delta
                                print(f"🔊 Sending {len(payload)} bytes at timestamp {timestamp_ms}", flush=True)
                                
                                await websocket.send_text(json.dumps({
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {
                                        "payload": payload,
                                        "timestamp": str(timestamp_ms)
                                    }
                                }))
                                
                                # Increment timestamp (20ms per chunk for 8khz mulaw)
                                timestamp_ms += 20
                                print(f"✅ Sent to Twilio", flush=True)
                        
                        # Handle function calls
                        elif event_type == "response.function_call_arguments.done":
                            function_name = event.name
                            args = json.loads(event.arguments)
                            
                            if function_name == "rag_search":
                                results = search_knowledge(business_id, args.get("query", ""))
                                await openai_ws.conversation.item.create(
                                    item={
                                        "type": "function_call_output",
                                        "call_id": event.call_id,
                                        "output": json.dumps({
                                            "results": results[:3] if results else [],
                                            "count": len(results) if results else 0
                                        })
                                    }
                                )
                                await openai_ws.response.create()
                            
                            elif function_name == "transfer_call":
                                if business.forwarding_number:
                                    await websocket.send_text(json.dumps({
                                        "action": "transfer",
                                        "number": business.forwarding_number
                                    }))
                        
                        # Log transcriptions
                        elif event_type == "conversation.item.input_audio_transcription.completed":
                            log(f"[USER]: {event.transcript}")
                        elif event_type == "response.text.delta":
                            print(f"[AI]: {event.delta}", end="", flush=True)
                        elif event_type == "response.text.done":
                            print()
                            
                except Exception as e:
                    log(f"❌ Error in openai_to_twilio: {e}")
                    import traceback
                    traceback.print_exc()

            async def twilio_to_openai():
                """Twilio → GPT (audio in)"""
                nonlocal stream_sid
                log("📥 twilio_to_openai loop started")
                
                # Send greeting immediately if stream is already ready
                if stream_sid:
                    log("📣 Sending greeting trigger...")
                    try:
                        await openai_ws.conversation.item.create(
                            item={
                                "type": "message",
                                "role": "user",
                                "content": [{"type": "input_text", "text": "Hello"}]
                            }
                        )
                        await openai_ws.response.create()
                        log("✅ Greeting triggered!")
                    except Exception as e:
                        log(f"❌ Error sending greeting: {e}")
                
                try:
                    while True:
                        message = await websocket.receive()
                        
                        if "text" in message:
                            try:
                                data = json.loads(message["text"])
                                event = data.get("event")
                                
                                if event == "connected":
                                    log("🔗 Twilio connected")
                                    continue
                                
                                if event == "start":
                                    # Update stream_sid if it wasn't set initially
                                    if not stream_sid:
                                        stream_sid = data.get('start', {}).get('streamSid') or data.get('streamSid')
                                        log(f"▶️ Twilio stream started (streamSid={stream_sid})")
                                        twilio_connected.set()
                                    continue
                                
                                if event == "stop":
                                    log("⏹ Twilio stream stopped")
                                    break
                                
                                if event == "media":
                                    payload = data.get("media", {}).get("payload", "")
                                    if payload:
                                        # Payload is base64 from Twilio
                                        await openai_ws.input_audio_buffer.append(audio=payload)
                                    continue
                                    
                            except json.JSONDecodeError:
                                pass
                            except Exception as ex:
                                log(f"⚠️ Error processing message: {ex}")
                                import traceback
                                traceback.print_exc()
                        
                        elif "bytes" in message:
                            # Handle raw bytes (for testing)
                            import base64
                            audio_bytes = message["bytes"]
                            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
                            await openai_ws.input_audio_buffer.append(audio=audio_b64)
                                
                except Exception as e:
                    log(f"❌ Error in twilio_to_openai: {e}")
                    import traceback
                    traceback.print_exc()

            # Run both tasks concurrently
            log("🚀 Starting audio bridge...")
            await asyncio.gather(
                twilio_to_openai(),
                openai_to_twilio()
            )
            log("✅ Audio bridge completed")
            
    except Exception as e:
        log(f"❌ Error in realtime session: {e}")
        import traceback
        traceback.print_exc()
        await websocket.close()
        