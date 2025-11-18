from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.schemas.rag import RAGIngest, RAGSearch
from app.services.rag_service import ingest_text, search_knowledge
from app.services.crawler import crawl_website


router = APIRouter(prefix="/rag", tags=["RAG"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/ingest")
def ingest_route(data: RAGIngest, db: Session = Depends(get_db)):
    ingest_text(db, data.business_id, data.text, data.source)
    return {"status": "ingested"}


@router.post("/crawl")
def crawl_route(business_id: int, url: str, db: Session = Depends(get_db)):
    text = crawl_website(url)
    ingest_text(db, business_id, text, "website")
    return {"status": "website ingested"}


@router.post("/search")
def search_route(data: RAGSearch):
    results = search_knowledge(data.business_id, data.query)
    return {"results": results}
