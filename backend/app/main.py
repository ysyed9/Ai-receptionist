from fastapi import FastAPI

from app.routers import business, rag, call, stream
from app.db import Base, engine
from app.models import business as business_model, document  # ensure models are imported


Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Receptionist Backend")

app.include_router(business.router)
app.include_router(rag.router)
app.include_router(call.router)
app.include_router(stream.router)


@app.get("/")
def root():
    return {"status": "running"}
