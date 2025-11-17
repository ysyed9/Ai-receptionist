from fastapi import FastAPI

from app.routers import business, call, rag, actions


app = FastAPI(title="AI Receptionist API")


app.include_router(business.router)
app.include_router(call.router)
app.include_router(rag.router)
app.include_router(actions.router)


@app.get("/")
def root():
    return {"message": "AI Receptionist is running!"}

