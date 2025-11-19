import os
import json
import asyncio
import logging
from openai import AsyncOpenAI
from app.services.rag_service import search_knowledge
from app.services.business_service import get_business_by_id
from app.services.call_logging import create_call_log, update_call_log, end_call_log
from app.services.telephony_actions import send_sms, transfer_call, schedule_appointment, end_call
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
    
    # Track call ending state
    end_call_requested = False
    end_call_reason = None
    last_audio_sent_time = 0
    
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
            log("📝 Configuring OpenAI session with pcm16 audio format...")
            
            # Build the full instructions
            full_instructions = f"""CRITICAL LANGUAGE RULE: YOU MUST START IN ENGLISH. Your first greeting MUST be in English. Only switch languages if the caller explicitly speaks another language first.

🚨 CRITICAL CALL MANAGEMENT RULES (YOU MUST FOLLOW THESE):
1. ALWAYS ask "Is there anything else I can help you with?" after answering questions
2. When caller says "no", "that's all", "goodbye", "bye", or similar:
   → Say: "Perfect! Thank you for calling [business name]. Have a great day!"
   → IMMEDIATELY use the end_call function with reason="conversation_complete"
   → DO NOT WAIT - call the function right after saying goodbye
3. When you detect silence (no response from caller):
   → First silence: Say "Hello? Are you still there?"
   → Second silence: Say "I'm not hearing anything. If you're still there, please let me know."
   → Third silence: Say "I'll disconnect now. Feel free to call back anytime!" → IMMEDIATELY use end_call with reason="silent_caller"
4. After scheduling an appointment:
   → Confirm details
   → Say goodbye
   → IMMEDIATELY use end_call with reason="conversation_complete"
5. YOU MUST ACTIVELY USE THE end_call FUNCTION - it's required, not optional

{business.instructions}

TECHNICAL NOTES:
- Use the rag_search function to search the knowledge base for business information
- Use the end_call function to end calls (required after conversations complete)
- Allowed actions for this business: {json.dumps(business.allowed_actions)}
- Tone for this business: {business.tone}"""
            
            # Log the first 500 chars of instructions to verify
            log(f"📋 Instructions preview (first 500 chars):")
            log(f"   {full_instructions[:500]}...")
            log(f"   Total length: {len(full_instructions)} characters")
            
            await openai_ws.session.update(
                session={
                    "modalities": ["text", "audio"],
                    "instructions": full_instructions,
                    "voice": "shimmer",
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {
                        "model": "whisper-1"
                    },
                        "turn_detection": {
                            "type": "server_vad",
                            "threshold": 0.4,
                            "prefix_padding_ms": 200,
                            "silence_duration_ms": 800
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
                        },
                        {
                            "type": "function",
                            "name": "end_call",
                            "description": "🚨 REQUIRED: End the call by closing the connection. You MUST call this function after saying goodbye. Use when: 1) Caller says 'no', 'that's all', 'goodbye', 'thanks', 'bye' - call IMMEDIATELY after your goodbye message, 2) After 3 attempts with no response from silent caller, 3) After scheduling appointment and confirming details, 4) Spam/robocall detected. DO NOT wait for caller to hang up - YOU must end the call.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "reason": {"type": "string", "description": "Reason for ending: 'conversation_complete' (normal end), 'silent_caller' (no response), 'spam_detected', 'abusive_caller'", "enum": ["conversation_complete", "silent_caller", "spam_detected", "abusive_caller"]}
                                },
                                "required": ["reason"]
                            }
                        }
                    ],
                    "tool_choice": "auto"
                }
            )
            log("✅ Session configured: pcm16 in/out, voice=shimmer, English forced")

            async def openai_to_twilio():
                """AI → Twilio (audio out)"""
                nonlocal end_call_requested, end_call_reason, last_audio_sent_time
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
                        
                        # LOG ALL EVENTS for debugging (except audio deltas which are too frequent)
                        if event_type not in ["response.audio.delta", "response.audio_transcript.delta"]:
                            log(f"🎯 OpenAI event: {event_type}")
                        
                        # LOG ERROR DETAILS
                        if event_type == "error":
                            error_msg = getattr(event, 'error', {})
                            log(f"❌ OpenAI ERROR: {error_msg}")
                        
                        # Track response start
                        if event_type == "response.created":
                            log(f"🎯 AI response started generating")
                            # Reset timestamp for new response
                            timestamp_ms = 0
                        
                        elif event_type == "response.done":
                            log(f"✅ AI response complete")
                            
                            # Check if we should end the call now that AI is done speaking
                            if end_call_requested:
                                # Calculate how long to wait based on audio duration
                                # Audio needs time to be sent AND played by Twilio
                                audio_duration_seconds = last_audio_sent_time / 1000.0
                                wait_time = audio_duration_seconds + 1.0  # Add 1 second buffer
                                
                                log(f"📞 AI finished generating response. Last audio at {last_audio_sent_time}ms")
                                log(f"⏳ Waiting {wait_time:.1f} seconds for audio to finish playing...")
                                await asyncio.sleep(wait_time)
                                
                                log(f"📞 Ending call now. Reason: {end_call_reason}")
                                await end_call(end_call_reason, websocket)
                                return  # Exit the loop
                        
                        # Send audio to Twilio
                        elif event_type == "response.audio.delta":
                            if hasattr(event, 'delta') and event.delta and stream_sid:
                                # OpenAI sends PCM16 at 24kHz, need to resample to 8kHz and convert to mulaw
                                import base64
                                import audioop
                                
                                try:
                                    # Decode base64 PCM16 audio from OpenAI (24kHz)
                                    pcm16_24khz = base64.b64decode(event.delta)
                                    
                                    # Resample from 24kHz to 8kHz (Twilio's rate)
                                    pcm16_8khz, _ = audioop.ratecv(
                                        pcm16_24khz,  # input audio data
                                        2,             # sample width (16-bit = 2 bytes)
                                        1,             # number of channels (mono)
                                        24000,         # input sample rate (24kHz)
                                        8000,          # output sample rate (8kHz)
                                        None           # state (None for first call)
                                    )
                                    
                                    # Convert PCM16 to mulaw (8-bit)
                                    mulaw_data = audioop.lin2ulaw(pcm16_8khz, 2)  # 2 = 16-bit width
                                    
                                    # Encode mulaw to base64 for Twilio
                                    mulaw_b64 = base64.b64encode(mulaw_data).decode('utf-8')
                                    
                                    # Log first audio chunk to confirm AI is responding
                                    if timestamp_ms == 0:
                                        log(f"🔊 AI started responding - sending audio to caller")
                                        log(f"   stream_sid={stream_sid}, 24kHz_len={len(pcm16_24khz)}, 8kHz_len={len(pcm16_8khz)}, mulaw_len={len(mulaw_data)}")
                                    
                                    media_msg = {
                                        "event": "media",
                                        "streamSid": stream_sid,
                                        "media": {
                                            "payload": mulaw_b64,
                                            "timestamp": str(timestamp_ms)
                                        }
                                    }
                                    await websocket.send_text(json.dumps(media_msg))
                                    
                                    # Track when we last sent audio (for call ending timing)
                                    last_audio_sent_time = timestamp_ms
                                    
                                    # Log first few chunks to confirm sending
                                    if timestamp_ms < 100:  # First 5 chunks (100ms)
                                        log(f"📤 Sent audio chunk to Twilio: timestamp={timestamp_ms}ms, mulaw_len={len(mulaw_data)}")
                                    
                                    # Increment timestamp based on mulaw length (8kHz, 1 byte = 1 sample)
                                    duration_ms = int((len(mulaw_data) / 8000.0) * 1000)
                                    timestamp_ms += duration_ms
                                    
                                except Exception as send_error:
                                    log(f"❌ Error converting/sending audio to Twilio: {send_error}")
                                    import traceback
                                    traceback.print_exc()
                            else:
                                if not stream_sid:
                                    if timestamp_ms == 0:
                                        log(f"⚠️ Cannot send audio: stream_sid is None")
                                elif not hasattr(event, 'delta') or not event.delta:
                                    if timestamp_ms == 0:
                                        log(f"⚠️ Cannot send audio: event.delta is missing or empty")
                        
                        elif event_type == "response.audio_transcript.delta":
                            # AI is generating audio transcript (what it's saying)
                            ai_speech = event.delta if hasattr(event, 'delta') else ""
                            if ai_speech:
                                print(f"[AI SPEAKING]: {ai_speech}", end="", flush=True)
                        
                        elif event_type == "response.audio_transcript.done":
                            # AI finished speaking
                            ai_full_speech = event.transcript if hasattr(event, 'transcript') else ""
                            print()
                            if ai_full_speech:
                                log(f"[AI SAID]: {ai_full_speech}")
                        
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
                            
                            elif function_name == "end_call":
                                reason = args.get("reason", "user_requested")
                                log(f"📞 AI requesting to end call. Reason: {reason}")
                                log("⏳ Will end call after AI finishes current response...")
                                
                                # Set flag to end call after response is done
                                end_call_requested = True
                                end_call_reason = reason
                                
                                # Update call log with reason
                                if call_log:
                                    update_call_log(stream_sid, status=f"ended_by_ai_{reason}")
                                
                                # Tell OpenAI the function executed successfully
                                await openai_ws.conversation.item.create(
                                    item={
                                        "type": "function_call_output",
                                        "call_id": event.call_id,
                                        "output": json.dumps({
                                            "success": True,
                                            "message": "Confirmed. Finish your goodbye message."
                                        })
                                    }
                                )
                                
                                # Trigger the response to continue
                                await openai_ws.response.create()
                        
                        # Log transcriptions
                        elif event_type == "conversation.item.input_audio_transcription.completed":
                            user_text = event.transcript if hasattr(event, 'transcript') else ""
                            if user_text and user_text.strip():
                                log(f"[USER]: {user_text}")
                                transcript_parts.append(f"USER: {user_text}")
                                
                                # Update call log with transcript
                                if call_log and stream_sid:
                                    full_transcript = "\n".join(transcript_parts)
                                    update_call_log(stream_sid, transcript=full_transcript)
                                
                                # Ensure response is created after receiving transcription
                                log(f"✅ User input received, waiting for AI response...")
                            else:
                                # Empty transcription - might be silence or audio quality issue
                                log(f"⚠️ Received empty transcription - audio might not be clear")
                        
                        elif event_type == "response.response_audio_transcript.delta":
                            # AI is generating audio transcript
                            log(f"🎵 AI generating audio response...")
                        
                        elif event_type == "response.response_audio_transcript.done":
                            # AI finished generating audio
                            log(f"✅ AI audio response complete")
                        
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
                            
                except RuntimeError as e:
                    if "disconnect message has been received" in str(e) or "WebSocket" in str(e):
                        log("✅ WebSocket closed gracefully (call ended)")
                    else:
                        log(f"❌ Runtime error in openai_to_twilio: {e}")
                        import traceback
                        traceback.print_exc()
                except Exception as e:
                    log(f"❌ Error in openai_to_twilio: {e}")
                    import traceback
                    traceback.print_exc()

            async def twilio_to_openai():
                """Twilio → GPT (audio in)"""
                nonlocal stream_sid, call_log, caller_number, called_number
                log("📥 twilio_to_openai loop started")
                
                # Send greeting immediately if stream is already ready
                if stream_sid:
                    log("📣 Triggering initial greeting...")
                    try:
                        # Trigger greeting - let the prompt handle the exact wording
                        await openai_ws.conversation.item.create(
                            item={
                                "type": "message",
                                "role": "user",
                                "content": [{
                                    "type": "input_text",
                                    "text": "A caller has just connected to the phone line. Greet them professionally as instructed."
                                }]
                            }
                        )
                        # Trigger a response
                        await openai_ws.response.create()
                        log("✅ Initial greeting triggered!")
                    except Exception as e:
                        log(f"❌ Error sending greeting: {e}")
                
                try:
                    while True:
                        message = await websocket.receive()
                        
                        if "text" in message:
                            try:
                                data = json.loads(message["text"])
                                event = data.get("event")
                                
                                # Log all events for debugging
                                if event not in ["media", "connected", "start", "stop"]:
                                    log(f"📬 Twilio event: {event}")
                                    if event in ["dtmf", "mark"]:
                                        log(f"   Data: {json.dumps(data)[:200]}")
                                
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
                                    # Commit any remaining audio before stopping
                                    try:
                                        await openai_ws.send({
                                            "type": "input_audio_buffer.commit"
                                        })
                                        log("✅ Committed final audio buffer")
                                    except:
                                        pass
                                    # End call log
                                    if call_log and stream_sid:
                                        end_call_log(stream_sid)
                                        log(f"📝 Call log ended: {call_log.id}")
                                    break
                                
                                if event == "media":
                                    payload = data.get("media", {}).get("payload", "")
                                    media_data = data.get("media", {})
                                    
                                    # Log ALL media events to debug
                                    if not hasattr(twilio_to_openai, '_media_count'):
                                        twilio_to_openai._media_count = 0
                                        twilio_to_openai._audio_buffer = []
                                    twilio_to_openai._media_count += 1
                                    
                                    if twilio_to_openai._media_count <= 10 or twilio_to_openai._media_count % 50 == 0:
                                        log(f"📦 Media event #{twilio_to_openai._media_count}: payload_len={len(payload) if payload else 0}, has_timestamp={('timestamp' in media_data)}")
                                    
                                    # Debug: Check payload validity
                                    if twilio_to_openai._media_count <= 5:
                                        log(f"🔍 Payload check: payload exists={payload is not None}, payload len={len(payload) if payload else 0}, payload type={type(payload)}")
                                    
                                    if payload and len(payload) > 0:
                                        # Twilio sends base64 mulaw payload at 8kHz
                                        # OpenAI input needs PCM16 at 24kHz
                                        try:
                                            import base64
                                            import audioop
                                            
                                            # Initialize resampling state if needed
                                            if not hasattr(twilio_to_openai, '_resample_state'):
                                                twilio_to_openai._resample_state = None
                                            
                                            # Decode base64 mulaw from Twilio
                                            mulaw_data = base64.b64decode(payload)
                                            
                                            # Convert mulaw to PCM16
                                            pcm16_8khz = audioop.ulaw2lin(mulaw_data, 2)  # 2 = 16-bit width
                                            
                                            # Resample from 8kHz to 24kHz (OpenAI's preferred rate)
                                            # Use state to maintain continuity across frames
                                            pcm16_24khz, twilio_to_openai._resample_state = audioop.ratecv(
                                                pcm16_8khz,                      # input audio data
                                                2,                               # sample width (16-bit = 2 bytes)
                                                1,                               # number of channels (mono)
                                                8000,                            # input sample rate (8kHz)
                                                24000,                           # output sample rate (24kHz)
                                                twilio_to_openai._resample_state # state for continuity
                                            )
                                            
                                            # Encode to base64 for OpenAI
                                            pcm16_b64 = base64.b64encode(pcm16_24khz).decode('utf-8')
                                            
                                            # Append audio to buffer
                                            await openai_ws.send({
                                                "type": "input_audio_buffer.append",
                                                "audio": pcm16_b64
                                            })
                                            
                                            # DO NOT COMMIT MANUALLY - Let OpenAI's server VAD handle it!
                                            # Manual commits cause "buffer too small" errors
                                            # OpenAI will auto-commit when VAD detects speech boundaries
                                            
                                            # Log first few frames to confirm processing
                                            if twilio_to_openai._media_count <= 10:
                                                log(f"🎤 Audio frame #{twilio_to_openai._media_count}: mulaw={len(mulaw_data)}b, pcm16_8k={len(pcm16_8khz)}b, pcm16_24k={len(pcm16_24khz)}b → appended ✅")
                                        except Exception as audio_error:
                                            log(f"⚠️ Error converting/sending audio to OpenAI: {audio_error}")
                                            import traceback
                                            traceback.print_exc()
                                    else:
                                        if not payload or len(payload) == 0:
                                            if twilio_to_openai._media_count <= 5:
                                                log(f"⚠️ Media event #{twilio_to_openai._media_count}: Received empty/null payload from Twilio")
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
                                
                except RuntimeError as e:
                    if "disconnect message has been received" in str(e):
                        log("✅ WebSocket closed gracefully (call ended)")
                    else:
                        log(f"❌ Runtime error in twilio_to_openai: {e}")
                        import traceback
                        traceback.print_exc()
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
        