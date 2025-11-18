from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.business import Business
from app.schemas.business import BusinessCreate
from fastapi import HTTPException


def create_business(db: Session, data: BusinessCreate):
    # Check if phone number already exists (if provided)
    if data.phone_number:
        existing = get_business_by_phone(db, data.phone_number)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Business with phone number {data.phone_number} already exists"
            )
    
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
    try:
        db.add(business)
        db.commit()
        db.refresh(business)
        return business
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Database integrity error: {str(e)}"
        )


def get_business_by_id(db: Session, business_id: int):
    return db.query(Business).filter(Business.id == business_id).first()


def get_business_by_phone(db: Session, phone: str):
    return db.query(Business).filter(Business.phone_number == phone).first()


def list_businesses(db: Session):
    return db.query(Business).all()

