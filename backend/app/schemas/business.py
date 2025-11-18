from pydantic import BaseModel
from typing import Optional, Dict, Any


class BusinessCreate(BaseModel):
    name: str
    phone_number: Optional[str] = None
    forwarding_number: Optional[str] = None
    tone: Optional[str] = "friendly"
    instructions: Optional[str] = None
    business_hours: Optional[Dict[str, Any]] = {}
    allowed_actions: Optional[Dict[str, Any]] = {}
    appointment_credentials: Optional[Dict[str, Any]] = {}


class BusinessOut(BaseModel):
    id: int
    name: str
    phone_number: str | None
    forwarding_number: str | None
    tone: str
    instructions: str | None
    business_hours: dict | None
    allowed_actions: dict | None
    appointment_credentials: dict | None

    class Config:
        from_attributes = True

