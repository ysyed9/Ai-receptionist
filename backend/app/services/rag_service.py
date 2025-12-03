import os
from weaviate import Client
from weaviate.auth import AuthApiKey
from openai import OpenAI
from sqlalchemy.orm import Session
from app.services.chunker import chunk_text
from app.models.document import BusinessDocument


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Lazy initialization of weaviate client
_weaviate_client = None
CLASS_NAME = os.getenv("WEAVIATE_CLASS_NAME", "BusinessDocs")


def get_weaviate_client():
    global _weaviate_client
    if _weaviate_client is None:
        weaviate_url = os.getenv("WEAVIATE_URL")
        weaviate_api_key = os.getenv("WEAVIATE_API_KEY")
        
        if not weaviate_url:
            raise ValueError("WEAVIATE_URL environment variable is not set")
        
        print(f"🔗 Connecting to Weaviate at {weaviate_url}")
        
        try:
            # Build authentication if API key is provided
            auth_config = None
            if weaviate_api_key and weaviate_api_key.lower() != "none" and weaviate_api_key.strip():
                auth_config = AuthApiKey(weaviate_api_key)
                print(f"🔑 Using API key authentication")
            else:
                print(f"🔓 No API key provided, connecting without authentication")
            
            # Create client with authentication (v4 syntax)
            _weaviate_client = Client(
                url=weaviate_url,
                auth_client_secret=auth_config
            )
            print(f"✅ Connected to Weaviate")
        except Exception as e:
            print(f"❌ Failed to connect to Weaviate: {e}")
            raise
    return _weaviate_client


def embed_text(text: str):
    response = client.embeddings.create(
        model=os.getenv("OPENAI_EMBEDDINGS"),
        input=text
    )
    return response.data[0].embedding


def ingest_text(db: Session, business_id: int, text: str, source="manual"):
    chunks = chunk_text(text)
    
    try:
        weaviate_client = get_weaviate_client()
    except Exception as e:
        raise Exception(f"Connection to Weaviate failed. Details: {e}")

    # Get or create collection
    try:
        collection = weaviate_client.collections.get(CLASS_NAME)
    except Exception:
        # Collection doesn't exist, create it
        try:
            weaviate_client.collections.create(
                name=CLASS_NAME,
                properties=[
                    {"name": "text", "dataType": ["text"]},
                    {"name": "business_id", "dataType": ["text"]},
                ]
            )
            collection = weaviate_client.collections.get(CLASS_NAME)
        except Exception as e:
            raise Exception(f"Failed to create Weaviate collection: {e}")

    for chunk in chunks:
        vector = embed_text(chunk)

        # Store in vector DB using v4.x API
        try:
            collection.data.insert(
                properties={
                    "business_id": str(business_id),
                    "text": chunk
                },
                vector=vector
            )
        except Exception as e:
            raise Exception(f"Failed to insert into Weaviate: {e}")

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
    weaviate_client = get_weaviate_client()

    try:
        collection = weaviate_client.collections.get(CLASS_NAME)
        
        # Query using v4.x API
        response = collection.query.near_vector(
            near_vector=query_vector,
            limit=5,
            return_properties=["text", "business_id"]
        )
        
        # Extract results
        results = []
        if response.objects:
            for obj in response.objects:
                results.append({
                    "text": obj.properties.get("text"),
                    "business_id": obj.properties.get("business_id")
                })
        
        return results
    except Exception as e:
        print(f"Search error: {e}")
        return []
