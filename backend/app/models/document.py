from sqlalchemy import Column, Integer, String, Text
from app.db import Base


class BusinessDocument(Base):
    __tablename__ = "business_documents"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, index=True)
    text = Column(Text)
    source = Column(String(200))   # "upload", "website", "faq"

