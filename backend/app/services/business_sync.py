"""
Business File Sync Service
Automatically syncs business configs from files to database on startup
"""
import os
import yaml
from pathlib import Path
from sqlalchemy.orm import Session
from app.models.business import Business
from app.services.rag_service import ingest_text
from app.db import SessionLocal


BUSINESSES_DIR = Path(__file__).parent.parent.parent / "businesses"


def load_business_config(business_folder: Path) -> dict:
    """Load config.yaml from business folder"""
    config_path = business_folder / "config.yaml"
    
    if not config_path.exists():
        print(f"⚠️  No config.yaml found in {business_folder.name}")
        return None
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config


def load_prompt(business_folder: Path) -> str:
    """Load prompt.md from business folder"""
    prompt_path = business_folder / "prompt.md"
    
    if not prompt_path.exists():
        print(f"⚠️  No prompt.md found in {business_folder.name}")
        return ""
    
    with open(prompt_path, 'r') as f:
        return f.read()


def load_knowledge_files(business_folder: Path) -> list:
    """Load all .txt and .md files from knowledge folder"""
    knowledge_folder = business_folder / "knowledge"
    
    if not knowledge_folder.exists():
        return []
    
    files = []
    for file_path in knowledge_folder.glob("*"):
        if file_path.suffix in ['.txt', '.md']:
            with open(file_path, 'r') as f:
                content = f.read()
                files.append({
                    'filename': file_path.name,
                    'content': content
                })
    
    return files


def sync_business_to_db(db: Session, config: dict, prompt: str) -> Business:
    """Create or update business in database"""
    
    # Check if business already exists (by phone number)
    business = db.query(Business).filter(
        Business.phone_number == config['phone_number']
    ).first()
    
    # Combine prompt with config instructions
    full_instructions = prompt
    if config.get('instructions'):
        full_instructions += f"\n\nAdditional notes: {config['instructions']}"
    
    if business:
        # Update existing
        print(f"🔄 Updating business: {config['name']}")
        business.name = config['name']
        business.forwarding_number = config.get('forwarding_number')
        business.tone = config.get('tone', 'friendly')
        business.instructions = full_instructions
        business.business_hours = config.get('business_hours', {})
        business.allowed_actions = config.get('allowed_actions', {})
        business.appointment_credentials = config.get('appointment_credentials', {})
    else:
        # Create new
        print(f"✨ Creating new business: {config['name']}")
        business = Business(
            name=config['name'],
            phone_number=config['phone_number'],
            forwarding_number=config.get('forwarding_number'),
            tone=config.get('tone', 'friendly'),
            instructions=full_instructions,
            business_hours=config.get('business_hours', {}),
            allowed_actions=config.get('allowed_actions', {}),
            appointment_credentials=config.get('appointment_credentials', {})
        )
        db.add(business)
    
    db.commit()
    db.refresh(business)
    
    return business


def ingest_knowledge_files(db: Session, business_id: int, knowledge_files: list):
    """Ingest all knowledge files into RAG system"""
    
    if not knowledge_files:
        print(f"   📚 No knowledge files to ingest")
        return
    
    print(f"   📚 Ingesting {len(knowledge_files)} knowledge files...")
    
    for file_data in knowledge_files:
        try:
            ingest_text(
                db=db,
                business_id=business_id,
                text=file_data['content'],
                source=f"file:{file_data['filename']}"
            )
            print(f"      ✅ {file_data['filename']}")
        except Exception as e:
            print(f"      ❌ {file_data['filename']}: {e}")


def sync_all_businesses():
    """Main sync function - syncs all businesses from files to database"""
    
    print("\n" + "="*60)
    print("🔄 SYNCING BUSINESSES FROM FILES TO DATABASE")
    print("="*60 + "\n")
    
    if not BUSINESSES_DIR.exists():
        print(f"⚠️  Businesses directory not found: {BUSINESSES_DIR}")
        print(f"   Create it with: mkdir -p {BUSINESSES_DIR}")
        return
    
    # Get all business folders
    business_folders = [f for f in BUSINESSES_DIR.iterdir() if f.is_dir()]
    
    if not business_folders:
        print(f"⚠️  No business folders found in {BUSINESSES_DIR}")
        return
    
    print(f"📂 Found {len(business_folders)} business folder(s)\n")
    
    db = SessionLocal()
    
    try:
        for folder in business_folders:
            print(f"📁 Processing: {folder.name}")
            print("-" * 40)
            
            # Load config
            config = load_business_config(folder)
            if not config:
                continue
            
            # Load prompt
            prompt = load_prompt(folder)
            
            # Load knowledge files
            knowledge_files = load_knowledge_files(folder)
            
            # Sync to database
            business = sync_business_to_db(db, config, prompt)
            print(f"   ✅ Business ID: {business.id}")
            print(f"   📞 Phone: {business.phone_number}")
            
            # Ingest knowledge
            ingest_knowledge_files(db, business.id, knowledge_files)
            
            print()
    
    except Exception as e:
        print(f"\n❌ Error during sync: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()
        
        # Close Weaviate connection to prevent resource leak
        try:
            from app.services.rag_service import get_weaviate_client
            weaviate_client = get_weaviate_client()
            if weaviate_client:
                weaviate_client.close()
        except Exception:
            pass
    
    print("="*60)
    print("✅ SYNC COMPLETE")
    print("="*60 + "\n")
    
    # Flush stdout to ensure logs appear
    import sys
    sys.stdout.flush()


if __name__ == "__main__":
    # Can be run standalone for testing
    sync_all_businesses()

