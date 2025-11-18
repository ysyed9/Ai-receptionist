import os
import json
import asyncio
import sys
import logging
from openai import AsyncOpenAI
from app.services.rag_service import search_knowledge
from app.services.business_service import get_business_by_id
from sqlalchemy.orm import Session
from app.db import SessionLocal
from fastapi import WebSocket

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def log(msg):
    """Log with both logger and print"""
    logger.info(msg)
    print(msg, flush=True)


async def handle_realtime_audio(websocket: WebSocket, business_id: int):
    """
    Main pipeline:
       Twilio WS <-> this function <-> OpenAI Realtime WS
    """
    
    log(f"🔄 Twilio WS connected → Starting GPT Realtime session for business_id={business_id}...")

    # -----------------------------
    # 1. Load business settings
    # -----------------------------
    db = SessionLocal()
    business = get_business_by_id(db, business_id)
    db.close()

    if not business:
        log(f"❌ Business {business_id} not found!")
        await websocket.close()
        return
    
    log(f"✅ Business loaded: {business.name}")

    # -----------------------------
    # 2. Open GPT Realtime Session
    # -----------------------------
    try:
        log("🔌 Connecting to OpenAI Realtime API...")
        async with client.beta.realtime.connect(
            model=os.getenv("OPENAI_MODEL_REALTIME", "gpt-4o-realtime-preview-2024-12-17")
        ) as openai_ws:
            log("🤖 GPT Realtime session successfully established!")
            
            # Configure session
            await openai_ws.session.update(
                session={
                    "modalities": ["text", "audio"],
                    "instructions": f"""
You are the AI receptionist for {business.name}.
Tone: {business.tone}
Instructions: {business.instructions}

When someone connects, immediately greet them with: "Hello! Thank you for calling {business.name}. How can I help you today?"

If a caller asks business-related questions, always check RAG memory first using function: rag_search.

Allowed actions:
{json.dumps(business.allowed_actions)}
""",
                    "voice": "alloy",
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {
                        "model": "whisper-1"
                    },
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
                            "description": "Search business knowledge base for information.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "The search query"
                                    }
                                },
                                "required": ["query"]
                            }
                        },
                        {
                            "type": "function",
                            "name": "transfer_call",
                            "description": "Transfer the call to the forwarding number.",
                            "parameters": {
                                "type": "object",
                                "properties": {}
                            }
                        }
                    ],
                    "tool_choice": "auto"
                }
            )
            
            # Send an initial message to trigger greeting
            print("📣 Sending initial message to trigger AI greeting...")
            await openai_ws.conversation.item.create(
                item={
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Hello"}]
                }
            )
            await openai_ws.response.create()
            print("✅ Initial greeting triggered!")

            # -----------------------------
            # 3. Async audio bridge loop
            # -----------------------------
            log("🔄 Starting audio bridge loops...")
            
            async def openai_to_twilio():
                """AI → Twilio (audio out)"""
                log("📤 openai_to_twilio loop started")
                try:
                    async for event in openai_ws:
                        event_type = event.type
                        print(f"🔔 OpenAI event: {event_type}")
                        
                        # Send audio back to Twilio
                        if event_type == "response.audio.delta":
                            print(f"🎵 Got audio delta event!")
                            if hasattr(event, 'delta') and event.delta:
                                # Delta should be base64-encoded, decode it to bytes
                                import base64
                                pcm = base64.b64decode(event.delta)
                                await websocket.send_bytes(pcm)
                                print(f"🔊 Sent AI audio frame ({len(pcm)} bytes)")
                            else:
                                print(f"⚠️ Audio delta event has no delta data")
                        
                        # Handle function calls
                        elif event_type == "response.function_call_arguments.done":
                            function_name = event.name
                            args = json.loads(event.arguments)
                            
                            if function_name == "rag_search":
                                # Execute RAG search
                                results = search_knowledge(business_id, args.get("query", ""))
                                
                                # Send results back to OpenAI
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
                                # Handle call transfer
                                if business.forwarding_number:
                                    # Send TwiML to transfer
                                    await websocket.send_text(json.dumps({
                                        "action": "transfer",
                                        "number": business.forwarding_number
                                    }))
                        
                        # Log transcriptions
                        elif event_type == "conversation.item.input_audio_transcription.completed":
                            print(f"[USER]: {event.transcript}")
                        
                        elif event_type == "response.text.delta":
                            print(f"[AI]: {event.delta}", end="", flush=True)
                        
                        elif event_type == "response.text.done":
                            print()  # New line after response
                            
                except Exception as e:
                    print(f"Error in openai_to_twilio: {e}")

            async def twilio_to_openai():
                """Twilio → GPT (audio in)"""
                log("📥 twilio_to_openai loop started")
                frame_count = 0
                try:
                    while True:
                        print(f"🔄 Waiting for message... (frame {frame_count})")
                        message = await websocket.receive()
                        frame_count += 1
                        print(f"📬 Message received! Keys: {message.keys()}")
                        
                        # Handle text messages (JSON events from Twilio)
                        if "text" in message:
                            text_data = message["text"]
                            print(f"📝 Text message: {text_data[:200]}")
                            try:
                                data = json.loads(text_data)
                                print(f"✅ JSON parsed. Event type: {data.get('event')}")
                                
                                # Twilio events
                                if data.get("event") == "connected":
                                    print("🔗 Twilio: connected event")
                                    continue
                                
                                if data.get("event") == "start":
                                    streamSid = data.get('streamSid', 'unknown')
                                    print(f"▶️ Twilio: start event (streamSid={streamSid})")
                                    continue
                                
                                if data.get("event") == "stop":
                                    print("⏹ Twilio: stop event")
                                    break
                                
                                if data.get("event") == "media":
                                    # Twilio sends base64 PCM16
                                    print(f"📦 Media event received!")
                                    payload = data.get("media", {}).get("payload", "")
                                    if payload:
                                        # Payload is already base64-encoded from Twilio, pass it directly
                                        print(f"🎤 Received Twilio audio frame - sending to OpenAI...")
                                        await openai_ws.input_audio_buffer.append(audio=payload)
                                        # Trigger a response from OpenAI
                                        await openai_ws.response.create()
                                        print(f"✅ Audio sent to OpenAI and response triggered!")
                                    else:
                                        print(f"⚠️ No payload in media event")
                                    continue
                                    
                            except json.JSONDecodeError as je:
                                print(f"⚠️ JSON decode error: {je}")
                                pass
                            except Exception as ex:
                                log(f"⚠️ Error processing text message: {ex}")
                                import traceback
                                traceback.print_exc()
                        
                        # Handle binary audio data (raw bytes from test page)
                        elif "bytes" in message:
                            import base64
                            audio_bytes = message["bytes"]
                            print(f"🎤 Received RAW audio frame ({len(audio_bytes)} bytes)")
                            # Base64 encode for OpenAI
                            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
                            await openai_ws.input_audio_buffer.append(audio=audio_b64)
                            await openai_ws.response.create()
                            print(f"✅ RAW audio sent to OpenAI and response triggered!")
                                
                except Exception as e:
                    log(f"❌ Error in twilio_to_openai: {e}")
                    import traceback
                    traceback.print_exc()

            # Run both tasks concurrently
            log("🚀 Starting concurrent audio bridge tasks...")
            await asyncio.gather(
                twilio_to_openai(),
                openai_to_twilio()
            )
            log("✅ Audio bridge tasks completed")
            
    except Exception as e:
        log(f"❌ Error in realtime session: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        await websocket.close()
