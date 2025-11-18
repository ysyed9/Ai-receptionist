from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os

from app.routers import business, rag, call, stream
from app.db import Base, engine
from app.models import business as business_model, document  # ensure models are imported


Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Receptionist Backend")

# Add CORS middleware for WebSocket testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(business.router)
app.include_router(rag.router)
app.include_router(call.router)
app.include_router(stream.router)


@app.get("/")
def root():
    return {"status": "running"}


@app.get("/test")
async def test_page():
    """Serve WebSocket test page"""
    test_file = os.path.join(os.path.dirname(__file__), "..", "test_websocket.html")
    if os.path.exists(test_file):
        return FileResponse(test_file)
    return {"error": "Test page not found"}


@app.get("/test/audio")
async def test_audio_page():
    """Serve Audio Stream test page"""
    test_file = os.path.join(os.path.dirname(__file__), "..", "test_audio_stream.html")
    if os.path.exists(test_file):
        return FileResponse(test_file)
    return {"error": "Audio test page not found"}
