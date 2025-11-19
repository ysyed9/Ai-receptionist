"""
Call Logging Service
Tracks and saves call transcripts, actions, and metadata
"""
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.call_log import CallLog
from app.db import SessionLocal


def create_call_log(
    business_id: int,
    stream_sid: str,
    caller_number: str = None,
    called_number: str = None
) -> CallLog:
    """Create a new call log entry"""
    db = SessionLocal()
    try:
        call_log = CallLog(
            business_id=business_id,
            stream_sid=stream_sid,
            caller_number=caller_number,
            called_number=called_number,
            status="active",
            transcript="",
            actions_taken=[],
            metadata={}
        )
        db.add(call_log)
        db.commit()
        db.refresh(call_log)
        return call_log
    finally:
        db.close()


def update_call_log(
    stream_sid: str,
    transcript: str = None,
    action: str = None,
    status: str = None,
    metadata: dict = None
):
    """Update an existing call log"""
    db = SessionLocal()
    try:
        call_log = db.query(CallLog).filter(CallLog.stream_sid == stream_sid).first()
        if not call_log:
            return None
        
        if transcript is not None:
            call_log.transcript = transcript
        
        if action:
            if call_log.actions_taken is None:
                call_log.actions_taken = []
            if action not in call_log.actions_taken:
                call_log.actions_taken.append(action)
        
        if status:
            call_log.status = status
        
        if metadata:
            if call_log.metadata is None:
                call_log.metadata = {}
            # Merge metadata - handle arrays specially
            for key, value in metadata.items():
                if key in call_log.metadata and isinstance(call_log.metadata[key], list) and isinstance(value, list):
                    # Merge arrays
                    call_log.metadata[key] = list(set(call_log.metadata[key] + value))
                else:
                    call_log.metadata[key] = value
        
        db.commit()
        db.refresh(call_log)
        return call_log
    finally:
        db.close()


def end_call_log(stream_sid: str):
    """End a call log and calculate duration"""
    db = SessionLocal()
    try:
        call_log = db.query(CallLog).filter(CallLog.stream_sid == stream_sid).first()
        if not call_log:
            return None
        
        call_log.end_time = datetime.utcnow()
        call_log.status = "completed"
        
        if call_log.start_time:
            duration = (call_log.end_time - call_log.start_time).total_seconds()
            call_log.duration_seconds = duration
        
        db.commit()
        db.refresh(call_log)
        return call_log
    finally:
        db.close()


def get_call_log(stream_sid: str) -> CallLog:
    """Get a call log by stream SID"""
    db = SessionLocal()
    try:
        return db.query(CallLog).filter(CallLog.stream_sid == stream_sid).first()
    finally:
        db.close()

