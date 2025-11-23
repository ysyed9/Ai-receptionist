"""
Google Sheets Service
Logs job/appointment details to Google Sheets after booking
"""
import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from typing import Optional, Dict, Any


def get_google_sheets_client(credentials_json: Dict[str, Any] = None, credentials_path: str = None):
    """
    Get authenticated Google Sheets client
    
    Args:
        credentials_json: Service account credentials as dict (DEPRECATED - use env vars)
        credentials_path: Path to service account JSON file
    
    Returns:
        gspread.Client or None if credentials invalid
    """
    try:
        import json
        
        # PRIORITY 1: Try environment variable (JSON string) - MOST SECURE
        env_creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON")
        if env_creds_json:
            try:
                # Parse JSON string from environment variable
                creds_dict = json.loads(env_creds_json)
                creds = Credentials.from_service_account_info(
                    creds_dict,
                    scopes=['https://www.googleapis.com/auth/spreadsheets']
                )
                return gspread.authorize(creds)
            except json.JSONDecodeError:
                print("⚠️  GOOGLE_SHEETS_CREDENTIALS_JSON is not valid JSON")
            except Exception as e:
                print(f"⚠️  Error parsing GOOGLE_SHEETS_CREDENTIALS_JSON: {e}")
        
        # PRIORITY 2: Try environment variable (file path) - SECURE
        env_creds_path = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH")
        if env_creds_path and os.path.exists(env_creds_path):
            creds = Credentials.from_service_account_file(
                env_creds_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            return gspread.authorize(creds)
        
        # PRIORITY 3: Try file path parameter (fallback)
        if credentials_path and os.path.exists(credentials_path):
            creds = Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            return gspread.authorize(creds)
        
        # PRIORITY 4: Try credentials from dict parameter (DEPRECATED - only for backwards compat)
        if credentials_json:
            print("⚠️  Using credentials_json parameter is deprecated. Use GOOGLE_SHEETS_CREDENTIALS_JSON env var instead.")
            creds = Credentials.from_service_account_info(
                credentials_json,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            return gspread.authorize(creds)
        
        print("⚠️  No Google Sheets credentials found. Set GOOGLE_SHEETS_CREDENTIALS_JSON or GOOGLE_SHEETS_CREDENTIALS_PATH environment variable.")
        return None
        
    except Exception as e:
        print(f"❌ Error authenticating Google Sheets: {e}")
        return None


def log_job_to_sheets(
    spreadsheet_id: str,
    worksheet_name: str,
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    appointment_date: str,
    appointment_time: str,
    service_type: str,
    status: str = "Booked",
    confirmation_sent: str = "Yes",
    call_summary: str = None,
    credentials_json: Dict[str, Any] = None,
    credentials_path: str = None,
    extra_data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Log job/appointment details to Google Sheets
    
    Args:
        spreadsheet_id: Google Sheets spreadsheet ID (from URL)
        worksheet_name: Name of the worksheet/tab
        customer_name: Customer's name
        customer_email: Customer's email
        customer_phone: Customer's phone number
        appointment_date: Appointment date (YYYY-MM-DD)
        appointment_time: Appointment time (HH:MM)
        service_type: Type of service requested
        status: Job status (default: "Booked")
        confirmation_sent: Whether SMS confirmation was sent (default: "Yes")
        call_summary: Summary of what was discussed on the call (optional)
        credentials_json: Service account credentials as dict
        credentials_path: Path to service account JSON file
        extra_data: Additional fields to log
    
    Returns:
        dict with success status and details
    """
    try:
        # Get authenticated client
        client = get_google_sheets_client(credentials_json, credentials_path)
        if not client:
            return {
                "success": False,
                "error": "Failed to authenticate with Google Sheets"
            }
        
        # Open spreadsheet
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        # Get or create worksheet
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
            # Check if headers exist and if "Call Summary" column is missing
            all_values = worksheet.get_all_values()
            if len(all_values) > 0:
                headers = all_values[0]
                # Check if "Call Summary" column exists
                if "Call Summary" not in headers:
                    # Add "Call Summary" column header
                    headers.append("Call Summary")
                    worksheet.update(values=[headers], range_name='A1:Z1')
                    print(f"   ✅ Added 'Call Summary' column to existing worksheet")
        except gspread.exceptions.WorksheetNotFound:
            # Create worksheet if it doesn't exist
            worksheet = spreadsheet.add_worksheet(
                title=worksheet_name,
                rows=1000,
                cols=20
            )
            # Add headers if new worksheet
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
                "Call Summary"
            ]
            if extra_data:
                headers.extend(extra_data.keys())
            worksheet.append_row(headers)
        
        # Prepare row data
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_data = [
            current_time,
            customer_name or "",
            customer_email or "",
            customer_phone or "",
            appointment_date or "",
            appointment_time or "",
            service_type or "",
            status,
            confirmation_sent,
            call_summary or ""  # Call summary
        ]
        
        # Add extra data if provided
        if extra_data:
            row_data.extend([extra_data.get(key, "") for key in extra_data.keys()])
        
        # Append row to worksheet
        worksheet.append_row(row_data)
        
        print(f"✅ Job logged to Google Sheets: {spreadsheet_id}/{worksheet_name}")
        
        return {
            "success": True,
            "spreadsheet_id": spreadsheet_id,
            "worksheet": worksheet_name,
            "timestamp": current_time
        }
        
    except gspread.exceptions.SpreadsheetNotFound:
        return {
            "success": False,
            "error": f"Spreadsheet not found: {spreadsheet_id}"
        }
    except gspread.exceptions.APIError as e:
        return {
            "success": False,
            "error": f"Google Sheets API error: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error logging to Google Sheets: {str(e)}"
        }

