from fastapi import FastAPI

from app.routers import business
from app.db import Base, engine
from app.models.business import Business  # ensure model is imported


Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Receptionist Backend")

app.include_router(business.router)


@app.get("/")
def root():
    return {"status": "running"}
