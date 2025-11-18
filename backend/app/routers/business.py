from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.business import BusinessCreate, BusinessOut
from app.services.business_service import create_business, get_business_by_id, list_businesses
from app.db import SessionLocal


router = APIRouter(prefix="/business", tags=["Business"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/create", response_model=BusinessOut)
def create_business_route(data: BusinessCreate, db: Session = Depends(get_db)):
    return create_business(db, data)


@router.get("/{business_id}", response_model=BusinessOut)
def get_business_route(business_id: int, db: Session = Depends(get_db)):
    return get_business_by_id(db, business_id)


@router.get("/", response_model=list[BusinessOut])
def list_businesses_route(db: Session = Depends(get_db)):
    return list_businesses(db)
