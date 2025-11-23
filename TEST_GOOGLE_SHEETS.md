# 🧪 Testing Google Sheets Integration

## ✅ What's Configured

When the AI schedules an appointment during a call, it will:
1. ✅ Save appointment to database
2. ✅ **Log job details to Google Sheets** (new!)
3. ✅ Send SMS confirmation
4. ✅ Update "Confirmation Sent" status in Google Sheets

## 🔧 Setup Steps (One-Time)

### Step 1: Share Google Sheet with Service Account

**IMPORTANT:** You must share your Google Sheet with the service account for it to work!

1. Open your Google Sheet:
   https://docs.google.com/spreadsheets/d/1UKvumBWo7JR_7TGLf_jjmfccijiavkAvA63iVs_JE4Q/edit

2. Click **"Share"** button (top right)

3. Add this email: `ai-receptionist-sheets@ai-receptionist-479101.iam.gserviceaccount.com`

4. Give it **"Editor"** access

5. Click **"Send"**

### Step 2: Start Docker and Rebuild Backend

```bash
# 1. Start Docker Desktop first

# 2. Then rebuild and start:
./stop && docker compose build backend && ./start
```

This installs the new dependencies (`gspread`, `google-auth`) needed for Google Sheets.

## 🧪 How to Test

### Option 1: Test with Real Call (Recommended)

1. **Call the dental office number:**
   - Phone: `(817) 552-4604`

2. **Schedule an appointment:**
   - The AI will ask for your name, email, date, and time
   - Provide test information like:
     - Name: "Test User"
     - Email: "test@example.com"
     - Date: "Tomorrow" or specific date
     - Time: "10:00 AM" or specific time
     - Service: "Dental cleaning" or any service

3. **Check your Google Sheet:**
   - Open: https://docs.google.com/spreadsheets/d/1UKvumBWo7JR_7TGLf_jjmfccijiavkAvA63iVs_JE4Q/edit
   - Look for the "Jobs" worksheet/tab
   - You should see a new row with all the appointment details!

### Option 2: Check Backend Logs

While the call is happening or after, check the logs:

```bash
docker logs -f ai-backend | grep -i "sheets\|sms\|appointment"
```

You should see:
- `✅ Job logged to Google Sheets`
- `✅ SMS confirmation sent to +...`

## 📋 What Gets Logged to Google Sheets

Each row in the "Jobs" worksheet will have:

| Column | Description |
|--------|-------------|
| Date Created | When the appointment was booked |
| Customer Name | Caller's name |
| Customer Email | Caller's email |
| Customer Phone | Caller's phone number |
| Appointment Date | Date of appointment (YYYY-MM-DD) |
| Appointment Time | Time of appointment (HH:MM) |
| Service Type | Type of service requested |
| Status | "Booked" |
| Confirmation Sent | "Yes" or "Pending" |
| Booking ID | LeadConnector booking ID (if applicable) |
| Booking System | "leadconnector" or other |

## ✅ Success Indicators

If everything is working, you'll see:

1. **In Google Sheets:**
   - New row appears in "Jobs" worksheet
   - All columns filled with appointment data
   - "Confirmation Sent" column shows "Yes" (after SMS)

2. **In Backend Logs:**
   - `✅ Job logged to Google Sheets`
   - `✅ SMS confirmation sent to +1234567890`
   - No error messages about Google Sheets

3. **On Your Phone:**
   - SMS confirmation message received

## ❌ Troubleshooting

### "Failed to log to Google Sheets"

**Solution:** Make sure you've shared the Google Sheet with the service account email:
- `ai-receptionist-sheets@ai-receptionist-479101.iam.gserviceaccount.com`
- Must have "Editor" access

### "Spreadsheet not found" error

**Solution:** Check that `spreadsheet_id` in config.yaml matches your sheet:
- Current ID: `1UKvumBWo7JR_7TGLf_jjmfccijiavkAvA63iVs_JE4Q`
- Get it from your Google Sheets URL

### No entries appearing

**Solution:**
1. Check backend logs: `docker logs ai-backend`
2. Make sure Docker is running
3. Make sure backend was rebuilt with new dependencies
4. Verify the appointment was actually scheduled during the call

## 🎉 Ready to Test!

Once Docker is running and the sheet is shared, make a test call to see it in action!

