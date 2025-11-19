import os
import json
import asyncio
import logging
from openai import AsyncOpenAI
from app.services.rag_service import search_knowledge
from app.services.business_service import get_business_by_id
from app.services.call_logging import create_call_log, update_call_log, end_call_log
from app.services.telephony_actions import send_sms, transfer_call, schedule_appointment
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
    call_log = None
    transcript_parts = []
    caller_number = None
    called_number = None
    
    # If we already have stream_sid, mark as connected
    if stream_sid:
        log(f"✅ Twilio already connected (streamSid={stream_sid})")
        twilio_connected.set()
        # Create call log
        call_log = create_call_log(
            business_id=business_id,
            stream_sid=stream_sid,
            caller_number=caller_number,
            called_number=called_number
        )
        log(f"📝 Call log created: {call_log.id}")

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

When someone connects, greet them warmly and naturally, then be ready to help with whatever they need.

IMPORTANT: After greeting, you MUST actively listen and respond to whatever the caller says. Do not just greet and wait silently - actually help them with their questions or requests.

If a caller asks business-related questions, check RAG memory using function: rag_search.

Allowed actions: {json.dumps(business.allowed_actions)}""",
                    "voice": "shimmer",
                    "input_audio_format": "g711_ulaw",
                    "output_audio_format": "g711_ulaw",
                    "input_audio_transcription": {"model": "whisper-1"},
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.6,
                        "prefix_padding_ms": 500,
                        "silence_duration_ms": 1000
                    },
                    "tools": [
                        {
                            "type": "function",
                            "name": "rag_search",
                            "description": "Search business knowledge base for information",
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
                        },
                        {
                            "type": "function",
                            "name": "send_sms",
                            "description": "Send SMS text message to caller",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "to_number": {"type": "string", "description": "Phone number to send SMS to"},
                                    "message": {"type": "string", "description": "SMS message content"}
                                },
                                "required": ["to_number", "message"]
                            }
                        },
                        {
                            "type": "function",
                            "name": "schedule_appointment",
                            "description": "Schedule an appointment for the caller. You MUST ask for the caller's name and email before scheduling. Collect all required information: name, email, date, time, and optionally service type and notes.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "appointment_date": {"type": "string", "description": "Date in YYYY-MM-DD format (e.g., 2024-12-25)"},
                                    "appointment_time": {"type": "string", "description": "Time in HH:MM format (e.g., 14:30 for 2:30 PM)"},
                                    "caller_name": {"type": "string", "description": "Caller's full name (REQUIRED - ask for this before scheduling)"},
                                    "caller_email": {"type": "string", "description": "Caller's email address (REQUIRED - ask for this before scheduling)"},
                                    "service_type": {"type": "string", "description": "Type of service or appointment reason (optional, e.g., 'cleaning', 'consultation', 'emergency')"},
                                    "notes": {"type": "string", "description": "Additional notes or special requests (optional)"}
                                },
                                "required": ["appointment_date", "appointment_time", "caller_name", "caller_email"]
                            }
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
                            
                            # Log action
                            if call_log:
                                update_call_log(stream_sid, action=function_name)
                            
                            if function_name == "rag_search":
                                query = args.get("query", "")
                                log(f"🔍 RAG search: {query}")
                                results = search_knowledge(business_id, query)
                                
                                # Log RAG query in metadata
                                if call_log:
                                    update_call_log(
                                        stream_sid,
                                        metadata={"rag_queries": [query]}
                                    )
                                
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
                                log(f"📞 Transferring call...")
                                if business.forwarding_number:
                                    transfer_result = transfer_call(stream_sid, business.forwarding_number)
                                    await websocket.send_text(json.dumps({
                                        "event": "transfer",
                                        "streamSid": stream_sid,
                                        "transfer": {
                                            "to": business.forwarding_number
                                        }
                                    }))
                                    if call_log:
                                        update_call_log(stream_sid, status="transferred")
                            
                            elif function_name == "send_sms":
                                to_number = args.get("to_number")
                                message = args.get("message")
                                log(f"📱 Sending SMS to {to_number}: {message[:50]}...")
                                
                                sms_result = send_sms(to_number, message)
                                
                                await openai_ws.conversation.item.create(
                                    item={
                                        "type": "function_call_output",
                                        "call_id": event.call_id,
                                        "output": json.dumps({
                                            "success": sms_result.get("success", False),
                                            "message": "SMS sent successfully" if sms_result.get("success") else f"Failed: {sms_result.get('error', 'Unknown error')}"
                                        })
                                    }
                                )
                                await openai_ws.response.create()
                            
                            elif function_name == "schedule_appointment":
                                appointment_date = args.get("appointment_date")
                                appointment_time = args.get("appointment_time")
                                caller_name = args.get("caller_name")
                                caller_email = args.get("caller_email")
                                service_type = args.get("service_type")
                                notes = args.get("notes")
                                
                                log(f"📅 Scheduling appointment: {appointment_date} at {appointment_time} for {caller_name} ({caller_email})")
                                
                                # Get call_log_id if available
                                call_log_id = None
                                if call_log:
                                    call_log_id = call_log.id
                                
                                appointment_result = schedule_appointment(
                                    business_id=business_id,
                                    caller_number=caller_number or "unknown",
                                    appointment_date=appointment_date,
                                    appointment_time=appointment_time,
                                    caller_name=caller_name,
                                    caller_email=caller_email,
                                    service_type=service_type,
                                    notes=notes,
                                    call_log_id=call_log_id
                                )
                                
                                # Prepare response message
                                response_message = appointment_result.get("message", "Appointment scheduled")
                                if appointment_result.get("booking_url"):
                                    response_message += f" I'll send you a booking link at {caller_email} to confirm the details."
                                
                                await openai_ws.conversation.item.create(
                                    item={
                                        "type": "function_call_output",
                                        "call_id": event.call_id,
                                        "output": json.dumps({
                                            "success": appointment_result.get("success", False),
                                            "message": response_message,
                                            "appointment": appointment_result.get("appointment", {}),
                                            "booking_url": appointment_result.get("booking_url"),
                                            "error": appointment_result.get("error") if not appointment_result.get("success") else None
                                        })
                                    }
                                )
                                await openai_ws.response.create()
                        
                        # Log transcriptions
                        elif event_type == "conversation.item.input_audio_transcription.completed":
                            user_text = event.transcript
                            log(f"[USER]: {user_text}")
                            transcript_parts.append(f"USER: {user_text}")
                            
                            # Update call log with transcript
                            if call_log and stream_sid:
                                full_transcript = "\n".join(transcript_parts)
                                update_call_log(stream_sid, transcript=full_transcript)
                        
                        elif event_type == "response.text.delta":
                            ai_text = event.delta
                            print(f"[AI]: {ai_text}", end="", flush=True)
                            # Don't add to transcript yet - wait for done
                        
                        elif event_type == "response.text.done":
                            ai_full_text = event.text if hasattr(event, 'text') else ""
                            print()
                            if ai_full_text:
                                transcript_parts.append(f"AI: {ai_full_text}")
                                # Update call log with transcript
                                if call_log and stream_sid:
                                    full_transcript = "\n".join(transcript_parts)
                                    update_call_log(stream_sid, transcript=full_transcript)
                            
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
                    log("📣 Triggering initial greeting...")
                    try:
                        # Trigger a response by creating a response item
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
                                        
                                        # Extract caller/called numbers if available
                                        start_data = data.get('start', {})
                                        caller_number = start_data.get('callerNumber') or data.get('callerNumber')
                                        called_number = start_data.get('calledNumber') or data.get('calledNumber')
                                        
                                        # Create call log if not already created
                                        if not call_log:
                                            call_log = create_call_log(
                                                business_id=business_id,
                                                stream_sid=stream_sid,
                                                caller_number=caller_number,
                                                called_number=called_number
                                            )
                                            log(f"📝 Call log created: {call_log.id}")
                                    continue
                                
                                if event == "stop":
                                    log("⏹ Twilio stream stopped")
                                    # End call log
                                    if call_log and stream_sid:
                                        end_call_log(stream_sid)
                                        log(f"📝 Call log ended: {call_log.id}")
                                    break
                                
                                if event == "media":
                                    payload = data.get("media", {}).get("payload", "")
                                    if payload:
                                        # Twilio sends base64 mulaw payload
                                        # OpenAI expects base64 mulaw
                                        await openai_ws.send({
                                            "type": "input_audio_buffer.append",
                                            "audio": payload
                                        })
                                        await openai_ws.send({
                                            "type": "input_audio_buffer.commit"
                                        })
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
                            await openai_ws.send({
                                "type": "input_audio_buffer.append",
                                "audio": audio_b64
                            })
                            await openai_ws.send({
                                "type": "input_audio_buffer.commit"
                            })
                                
                except Exception as e:
                    log(f"❌ Error in twilio_to_openai: {e}")
                    import traceback
                    traceback.print_exc()

            # Run both tasks concurrently
            log("🚀 Starting audio bridge...")
            try:
                await asyncio.gather(
                    twilio_to_openai(),
                    openai_to_twilio()
                )
            finally:
                # Ensure call log is ended
                if call_log and stream_sid:
                    end_call_log(stream_sid)
                    log(f"📝 Call log finalized: {call_log.id}")
            
            log("✅ Audio bridge completed")
            
    except Exception as e:
        log(f"❌ Error in realtime session: {e}")
        import traceback
        traceback.print_exc()
        # End call log on error
        if call_log and stream_sid:
            end_call_log(stream_sid)
            update_call_log(stream_sid, status="failed")
        await websocket.close()
        