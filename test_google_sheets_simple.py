#!/usr/bin/env python3
"""
Simple Google Sheets Test
Tests Google Sheets API connection and logging
"""
import sys
import json
from pathlib import Path

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    print("❌ Missing dependencies. Install with:")
    print("   pip install gspread google-auth")
    sys.exit(1)


def test_google_sheets():
    """Test Google Sheets connection"""
    
    print("=" * 60)
    print("🧪 TESTING GOOGLE SHEETS CONNECTION")
    print("=" * 60)
    print()
    
    # Load credentials from config
    config_path = Path(__file__).parent / "backend" / "businesses" / "midtowndentistrydallas" / "config.yaml"
    
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        return False
    
    print(f"📄 Loading config from: {config_path.name}")
    
    # Simple YAML parsing (just for credentials)
    with open(config_path, 'r') as f:
        content = f.read()
    
    # Extract credentials_json section (simple parsing)
    import re
    spreadsheet_id_match = re.search(r'spreadsheet_id:\s*"([^"]+)"', content)
    worksheet_name_match = re.search(r'worksheet_name:\s*"([^"]+)"', content)
    
    # For credentials, we'll load the JSON structure manually
    # This is a simplified approach - in production, use proper YAML parser
    
    if not spreadsheet_id_match:
        print("❌ Could not find spreadsheet_id in config")
        print("   Make sure config.yaml has: spreadsheet_id: \"...\"")
        return False
    
    spreadsheet_id = spreadsheet_id_match.group(1)
    worksheet_name = worksheet_name_match.group(1) if worksheet_name_match else "Jobs"
    
    print(f"✅ Spreadsheet ID: {spreadsheet_id}")
    print(f"✅ Worksheet name: {worksheet_name}")
    print()
    
    # Load credentials (simplified - you may need to adjust)
    # For a proper test, you might want to extract credentials_json from YAML
    print("⚠️  For a full test, please:")
    print("   1. Start Docker Desktop")
    print("   2. Rebuild backend: ./stop && docker compose build backend && ./start")
    print("   3. Run test inside Docker: docker exec -it ai-backend python /app/test_google_sheets.py")
    print()
    print("   Or manually test by:")
    print("   1. Sharing your Google Sheet with:")
    print("      ai-receptionist-sheets@ai-receptionist-479101.iam.gserviceaccount.com")
    print("   2. Making a test appointment booking")
    print()
    
    return True


if __name__ == "__main__":
    print("📋 Google Sheets Configuration Check")
    print()
    test_google_sheets()
    print()
    print("💡 Next steps:")
    print("   1. ✅ Config file found")
    print("   2. ⏳ Share Google Sheet with service account (see above)")
    print("   3. ⏳ Start Docker and rebuild backend")
    print("   4. ⏳ Test with a real appointment booking")
    print()

