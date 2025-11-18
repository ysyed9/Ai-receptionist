from sqlalchemy.orm import Session
from app.models.business import Business
from app.schemas.business import BusinessCreate


def create_business(db: Session, data: BusinessCreate):
    business = Business(
        name=data.name,
        phone_number=data.phone_number,
        forwarding_number=data.forwarding_number,
        tone=data.tone,
        instructions=data.instructions,
        business_hours=data.business_hours,
        allowed_actions=data.allowed_actions,
        appointment_credentials=data.appointment_credentials
    )
    db.add(business)
    db.commit()
    db.refresh(business)
    return business


def get_business_by_id(db: Session, business_id: int):
    return db.query(Business).filter(Business.id == business_id).first()


def get_business_by_phone(db: Session, phone: str):
    return db.query(Business).filter(Business.phone_number == phone).first()


def list_businesses(db: Session):
    return db.query(Business).all()

