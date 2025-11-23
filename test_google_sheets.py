#!/usr/bin/env python3
"""
Test Google Sheets Integration
Tests the Google Sheets logging functionality

Run this inside Docker:
docker exec -it ai-backend python /app/test_google_sheets.py
"""
import sys
import os
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, "/app")

try:
    import yaml
except ImportError:
    print("⚠️  PyYAML not installed. Trying alternative...")
    try:
        from ruamel.yaml import YAML
        yaml = YAML()
        yaml_safe_load = yaml.load
    except ImportError:
        print("❌ Neither PyYAML nor ruamel.yaml available")
        print("   Please install: pip install pyyaml")
        sys.exit(1)

from app.services.google_sheets import get_google_sheets_client, log_job_to_sheets


def test_google_sheets():
    """Test Google Sheets connection and logging"""
    
    print("=" * 60)
    print("🧪 TESTING GOOGLE SHEETS INTEGRATION")
    print("=" * 60)
    print()
    
    # Load config - try multiple paths
    possible_paths = [
        Path("/app/businesses/midtowndentistrydallas/config.yaml"),  # Docker path
        Path(__file__).parent / "backend" / "businesses" / "midtowndentistrydallas" / "config.yaml",  # Local path
        Path("backend/businesses/midtowndentistrydallas/config.yaml"),  # Relative path
    ]
    
    config_path = None
    for path in possible_paths:
        if path.exists():
            config_path = path
            break
    
    if not config_path:
        print(f"❌ Config file not found. Tried:")
        for p in possible_paths:
            print(f"   - {p}")
        return False
    
    print(f"📄 Loading config from: {config_path}")
    with open(config_path, 'r') as f:
        try:
            config = yaml.safe_load(f)
        except AttributeError:
            # ruamel.yaml uses load() not safe_load()
            config = yaml.load(f)
    
    sheets_config = config.get('google_sheets_credentials', {})
    
    if not sheets_config:
        print("❌ No google_sheets_credentials found in config")
        return False
    
    spreadsheet_id = sheets_config.get('spreadsheet_id')
    worksheet_name = sheets_config.get('worksheet_name', 'Jobs')
    credentials_json = sheets_config.get('credentials_json')
    
    if not spreadsheet_id:
        print("❌ No spreadsheet_id configured")
        return False
    
    if not credentials_json:
        print("❌ No credentials_json configured")
        return False
    
    print(f"✅ Found spreadsheet_id: {spreadsheet_id}")
    print(f"✅ Found worksheet_name: {worksheet_name}")
    print()
    
    # Test 1: Authenticate with Google Sheets
    print("🔐 Test 1: Authenticating with Google Sheets API...")
    try:
        client = get_google_sheets_client(credentials_json=credentials_json)
        if client:
            print("✅ Authentication successful!")
        else:
            print("❌ Authentication failed - client is None")
            return False
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return False
    
    print()
    
    # Test 2: Access the spreadsheet
    print(f"📊 Test 2: Accessing spreadsheet...")
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        print(f"✅ Successfully accessed spreadsheet: {spreadsheet.title}")
    except Exception as e:
        print(f"❌ Error accessing spreadsheet: {e}")
        print()
        print("💡 Make sure you've shared the Google Sheet with this email:")
        print(f"   {credentials_json.get('client_email')}")
        return False
    
    print()
    
    # Test 3: Create or access worksheet
    print(f"📋 Test 3: Creating/accessing worksheet '{worksheet_name}'...")
    try:
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
            print(f"✅ Worksheet '{worksheet_name}' already exists")
        except:
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=20)
            print(f"✅ Created new worksheet '{worksheet_name}'")
        
        # Check if headers exist
        all_values = worksheet.get_all_values()
        if not all_values or len(all_values) == 0:
            print("   📝 Adding headers...")
            headers = [
                "Date Created",
                "Customer Name",
                "Customer Email",
                "Customer Phone",
                "Appointment Date",
                "Appointment Time",
                "Service Type",
                "Status",
                "Confirmation Sent",
                "Booking ID",
                "Booking System"
            ]
            worksheet.append_row(headers)
            print("   ✅ Headers added")
        else:
            print(f"   ✅ Worksheet has {len(all_values)} rows")
        
    except Exception as e:
        print(f"❌ Error with worksheet: {e}")
        return False
    
    print()
    
    # Test 4: Log a test entry
    print("✍️  Test 4: Logging test entry to Google Sheets...")
    try:
        result = log_job_to_sheets(
            spreadsheet_id=spreadsheet_id,
            worksheet_name=worksheet_name,
            customer_name="Test Customer",
            customer_email="test@example.com",
            customer_phone="+1234567890",
            appointment_date="2025-11-22",
            appointment_time="10:00 AM",
            service_type="Test Appointment",
            status="Booked",
            confirmation_sent="Yes",
            credentials_json=credentials_json,
            extra_data={
                "Booking ID": "TEST123",
                "Booking System": "test"
            }
        )
        
        if result.get("success"):
            print("✅ Test entry logged successfully!")
            print(f"   Timestamp: {result.get('timestamp')}")
        else:
            print(f"❌ Failed to log entry: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Error logging test entry: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()
    print("=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print()
    print("🎉 Google Sheets integration is working correctly!")
    print()
    print("📋 Check your Google Sheet to see the test entry:")
    print(f"   https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")
    print()
    
    return True


if __name__ == "__main__":
    success = test_google_sheets()
    sys.exit(0 if success else 1)

