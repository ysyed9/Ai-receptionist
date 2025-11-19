# Business Configuration Folders

This directory contains business configurations that automatically sync to the database when the backend starts.

## 📁 Folder Structure

Each business should have its own folder with this structure:

```
businesses/
  your-business-name/
    config.yaml          # Required: Business settings
    prompt.md            # Required: AI instructions
    knowledge/           # Optional: Knowledge base files
      services.txt
      pricing.txt
      faq.txt
      ...
```

## 📝 File Formats

### `config.yaml` (Required)

```yaml
name: "Your Business Name"
slug: "your-business-name"
phone_number: "+15551234567"
forwarding_number: "+15559876543"
website_url: "https://yourbusiness.com/"

tone: "friendly and professional"

business_hours:
  mon: "9am-5pm"
  tue: "9am-5pm"
  wed: "9am-5pm"
  thu: "9am-5pm"
  fri: "9am-5pm"
  sat: "closed"
  sun: "closed"

allowed_actions:
  sms: true
  transfer: true
  booking: true
  rag_search: true

appointment_credentials:
  system: "calendly"
  api_key: ""
  calendar_url: ""

# Auto-crawl website on sync (optional)
auto_crawl_website: true
```

### `prompt.md` (Required)

This is the AI personality and instructions. Write it in plain English.

```markdown
# AI Receptionist Instructions

## Your Role
You are the receptionist for [Business Name]...

## Personality & Tone
- Be friendly and helpful
- Use clear language
- ...

## What to do when...
[Your instructions here]
```

### `knowledge/*.txt` or `knowledge/*.md` (Optional)

Any `.txt` or `.md` files in the `knowledge/` folder will be automatically ingested into the RAG system.

**Examples:**
- `services.txt` - List of services offered
- `pricing.txt` - Pricing information
- `faq.txt` - Common questions and answers
- `policies.txt` - Business policies
- `about.txt` - About the business

## 🔄 How Sync Works

1. **On Backend Startup**: The backend automatically reads all folders in `businesses/`
2. **Creates or Updates**: Each business is created (if new) or updated (if exists)
3. **Phone Number is Key**: Businesses are matched by phone number
4. **Website Crawling**: If `auto_crawl_website: true` and `website_url` is set, the website is automatically crawled and ingested
5. **Knowledge Ingestion**: All files in `knowledge/` are ingested into the RAG vector database
6. **Database is Source of Truth**: At runtime, the backend uses the database (not files)

## 🌐 Auto Website Crawling

If you set `auto_crawl_website: true` and provide a `website_url` in your `config.yaml`, the system will:
- **Automatically crawl** the website on every backend startup
- **Extract text content** from all pages
- **Ingest into RAG** so the AI can answer questions about your website content
- **No manual updates needed** - just restart backend to refresh website content

This is perfect for keeping your AI receptionist up-to-date with your latest website information!

## ✅ Adding a New Business

1. **Create a folder**: `mkdir businesses/acme-corp`
2. **Copy template**: Copy `spark-dental/` as a starting point
3. **Edit files**: Update `config.yaml`, `prompt.md`, and knowledge files
4. **Restart backend**: The business will be automatically synced

```bash
docker compose restart backend
```

## 🔧 Editing an Existing Business

1. **Edit the files** in the business folder
2. **Restart backend** to sync changes

```bash
docker compose restart backend
```

## 📊 Verification

Check the backend logs on startup to see sync results:

```
🔄 SYNCING BUSINESSES FROM FILES TO DATABASE
📂 Found 1 business folder(s)

📁 Processing: spark-dental
----------------------------------------
✨ Creating new business: Spark Dental
   ✅ Business ID: 1
   📞 Phone: +15176284976
   📚 Ingesting 3 knowledge files...
      ✅ services.txt
      ✅ pricing.txt
      ✅ faq.txt

✅ SYNC COMPLETE
```

## 🎯 Best Practices

1. **Use descriptive filenames** in knowledge folder
2. **Keep prompt.md focused** - it's the AI's core instructions
3. **Update knowledge files** - don't put everything in the prompt
4. **Test after changes** - call the business number to test
5. **Version control** - commit your business configs to git

## 🚨 Troubleshooting

**Business not showing up?**
- Check `config.yaml` syntax (valid YAML)
- Ensure phone number is unique
- Check backend logs for errors

**Knowledge not working?**
- Verify files are in `knowledge/` folder
- Check file extensions (`.txt` or `.md`)
- Look for RAG ingestion logs on startup

**AI not following instructions?**
- Make `prompt.md` more specific
- Use examples in the prompt
- Check if RAG search is enabled in `allowed_actions`

## 📦 Example Business

See `spark-dental/` for a complete working example.

