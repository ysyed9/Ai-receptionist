from sqlalchemy import Column, Integer, String, Text, JSON
from app.db import Base


class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    phone_number = Column(String(20), unique=True)
    forwarding_number = Column(String(20))
    tone = Column(String(200), default="friendly and helpful")
    instructions = Column(Text)
    business_hours = Column(JSON)
    allowed_actions = Column(JSON)
    appointment_credentials = Column(JSON)

