# 🔒 Security Fix: Google Sheets Credentials

## ✅ Changes Made

1. **Removed credentials from `config.yaml`** - Private keys are no longer in the config file
2. **Updated code to read from environment variables** - Credentials now come from `.env` file
3. **`.env` is already in `.gitignore`** - Your credentials won't be committed to git

## 📋 What You Need to Do

Add the following line to your `backend/.env` file with your Google Service Account credentials JSON:

```bash
GOOGLE_SHEETS_CREDENTIALS_JSON='{"type": "service_account", "project_id": "YOUR_PROJECT_ID", "private_key_id": "YOUR_PRIVATE_KEY_ID", "private_key": "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY\n-----END PRIVATE KEY-----\n", "client_email": "YOUR_SERVICE_ACCOUNT@YOUR_PROJECT.iam.gserviceaccount.com", "client_id": "YOUR_CLIENT_ID", "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token", "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs", "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/YOUR_SERVICE_ACCOUNT", "universe_domain": "googleapis.com"}'
```

**Note:** Replace the placeholder values above with your actual Google Service Account credentials. You can find these in the JSON key file downloaded from Google Cloud Console.

## 🔄 Alternative: Use File Path

If you prefer to store the credentials as a JSON file instead, you can:

1. Save the credentials JSON to a file: `backend/google_sheets_credentials.json`
2. Add this to your `backend/.env`:

```bash
GOOGLE_SHEETS_CREDENTIALS_PATH=/app/google_sheets_credentials.json
```

(Note: Use `/app/` path when running in Docker, or `./google_sheets_credentials.json` for local)

## ✅ Verification

After adding the credentials to `.env`, restart the backend:

```bash
docker restart ai-backend
```

The system will now read credentials from environment variables instead of the config file.

## 🔐 Security Benefits

- ✅ Private keys are no longer in version control
- ✅ `.env` file is in `.gitignore` (already configured)
- ✅ Credentials can be different per environment
- ✅ Easier to rotate credentials without touching code

## ⚠️ Important

1. **NEVER commit `.env` files to git**
2. **Share `.env.example`** instead (with placeholder values)
3. **Rotate credentials** if they were ever exposed in git history
4. **Use environment variables** in production (Docker, Kubernetes, etc.)

