from pydantic import BaseModel


class RAGIngest(BaseModel):
    business_id: int
    text: str
    source: str = "manual"


class RAGSearch(BaseModel):
    business_id: int
    query: str

