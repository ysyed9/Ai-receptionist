import os
import weaviate
from openai import OpenAI
from sqlalchemy.orm import Session
from app.services.chunker import chunk_text
from app.models.document import BusinessDocument


client = OpenAI()

weaviate_client = weaviate.Client(os.getenv("WEAVIATE_URL"))

CLASS_NAME = os.getenv("WEAVIATE_CLASS_NAME")  # BusinessDocs


def embed_text(text: str):
    response = client.embeddings.create(
        model=os.getenv("OPENAI_EMBEDDINGS"),
        input=text
    )
    return response.data[0].embedding


def ingest_text(db: Session, business_id: int, text: str, source="manual"):
    chunks = chunk_text(text)

    for chunk in chunks:
        vector = embed_text(chunk)

        # Store in vector DB
        weaviate_client.data_object.create(
            data_obj={
                "business_id": str(business_id),
                "text": chunk
            },
            class_name=CLASS_NAME,
            vector=vector
        )

        # Store raw text in Postgres
        db_obj = BusinessDocument(
            business_id=business_id,
            text=chunk,
            source=source
        )
        db.add(db_obj)

    db.commit()
    return True


def search_knowledge(business_id: int, query: str):
    query_vector = embed_text(query)

    nearVector = {"vector": query_vector}

    result = weaviate_client.query.get(
        CLASS_NAME,
        ["text", "business_id"]
    ).with_near_vector(nearVector).with_limit(5).do()

    if "data" in result:
        return result["data"]["Get"][CLASS_NAME]

    return []

