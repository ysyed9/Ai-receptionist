#!/usr/bin/env python3
"""
WebSocket Test Client for AI Receptionist
Tests the /call/stream endpoint
"""

import asyncio
import websockets
import json
import sys


async def test_websocket():
    uri = "ws://localhost:8000/call/stream?business_id=1"
    
    print(f"🔌 Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected successfully!")
            
            # Send a test message (simulating Twilio)
            test_message = {
                "event": "connected",
                "protocol": "Call",
                "version": "1.0.0"
            }
            
            print(f"📤 Sending: {json.dumps(test_message)}")
            await websocket.send(json.dumps(test_message))
            
            # Send start event
            start_message = {
                "event": "start",
                "streamSid": "test-stream-123",
                "callSid": "test-call-456"
            }
            print(f"📤 Sending: {json.dumps(start_message)}")
            await websocket.send(json.dumps(start_message))
            
            # Wait for messages
            print("\n📨 Listening for messages (Press Ctrl+C to stop)...\n")
            
            try:
                async for message in websocket:
                    if isinstance(message, bytes):
                        print(f"📦 Received binary data: {len(message)} bytes")
                    else:
                        print(f"📨 Received text: {message}")
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted by user")
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ Connection failed with status code: {e.status_code}")
        print(f"   Headers: {e.headers}")
    except websockets.exceptions.WebSocketException as e:
        print(f"❌ WebSocket error: {e}")
    except ConnectionRefusedError:
        print("❌ Connection refused. Is the server running?")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("🧪 AI Receptionist WebSocket Test Client\n")
    
    try:
        asyncio.run(test_websocket())
    except KeyboardInterrupt:
        print("\n\n✋ Test stopped by user")
        sys.exit(0)

