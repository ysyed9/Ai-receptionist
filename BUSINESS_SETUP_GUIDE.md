# 📁 Business Configuration System

## ✅ What Was Created

You now have a **file-based business configuration system** that automatically syncs to your database when the backend starts!

### Folder Structure

```
backend/businesses/
  spark-dental/                    ← Example business (already configured)
    config.yaml                    ← Business settings
    prompt.md                      ← AI personality & instructions
    knowledge/                     ← Knowledge base files
      services.txt                 ← Services offered
      pricing.txt                  ← Pricing info
      faq.txt                      ← Common questions
  README.md                        ← Full documentation
```

## 🚀 How It Works

1. **On Backend Startup**: All businesses in `backend/businesses/` are automatically loaded
2. **Phone Number = Key**: Businesses are matched by phone number (creates new or updates existing)
3. **Knowledge Ingestion**: All `.txt` and `.md` files in `knowledge/` are ingested into RAG
4. **Database is Live**: The AI reads from the database at runtime, not files

## 📊 What You'll See on Startup

```
🚀 Starting AI Receptionist Backend...
============================================================
🔄 SYNCING BUSINESSES FROM FILES TO DATABASE
============================================================

📂 Found 1 business folder(s)

📁 Processing: spark-dental
----------------------------------------
🔄 Updating business: Spark Dental
   ✅ Business ID: 8
   📞 Phone: +15176284976
   📚 Ingesting 3 knowledge files...
      ✅ faq.txt
      ✅ pricing.txt
      ✅ services.txt

============================================================
✅ SYNC COMPLETE
============================================================
```

## ➕ Adding a New Business

### Step 1: Create the folder structure

```bash
cd backend/businesses
mkdir my-restaurant
mkdir my-restaurant/knowledge
```

### Step 2: Create `config.yaml`

```yaml
name: "My Restaurant"
slug: "my-restaurant"
phone_number: "+15551234567"
forwarding_number: "+15559876543"
website_url: "https://myrestaurant.com/"

tone: "warm and welcoming"

business_hours:
  mon: "11am-10pm"
  tue: "11am-10pm"
  wed: "11am-10pm"
  thu: "11am-10pm"
  fri: "11am-11pm"
  sat: "11am-11pm"
  sun: "12pm-9pm"

allowed_actions:
  sms: true
  transfer: true
  booking: true
  rag_search: true

appointment_credentials:
  system: "opentable"
  api_key: ""

# Auto-crawl website (optional but recommended!)
auto_crawl_website: true
```

### Step 3: Create `prompt.md`

```markdown
# AI Receptionist Instructions

## Your Role
You are the friendly host at My Restaurant, a family-owned Italian restaurant.

## Personality
- Warm and welcoming
- Enthusiastic about our food
- Patient and helpful

## Your Goals
1. Answer questions about menu, hours, location
2. Take reservations
3. Handle special requests

## Example Responses

**Q: "What's on the menu?"**
A: "We specialize in authentic Italian cuisine! Let me check our current menu..." [rag_search]

**Q: "Can I make a reservation?"**
A: "Absolutely! What day and time would you like to dine with us?"
```

### Step 4: Add knowledge files

```
knowledge/
  menu.txt      ← Full menu with descriptions and prices
  hours.txt     ← Hours, location, parking info
  specials.txt  ← Daily specials and promotions
```

### Step 5: Restart backend

```bash
docker compose restart backend
```

The new business will be automatically created and all knowledge ingested!

## ✏️ Editing an Existing Business

1. **Edit the files** in `backend/businesses/your-business/`
2. **Restart backend**: `docker compose restart backend`
3. **Changes sync automatically** - updated in database

## 🧪 Testing Your Changes

### Test the phone line
Call your business number: **(517) 628-4976** for Spark Dental

### Test knowledge retrieval
Ask questions covered in your knowledge files:
- "What services do you offer?"
- "How much is a cleaning?"
- "What are your hours?"

The AI should search the knowledge base and provide accurate answers!

## 🌐 Auto Website Crawling (NEW!)

You can now automatically crawl and ingest website content! Just add to your `config.yaml`:

```yaml
website_url: "https://yourbusiness.com/"
auto_crawl_website: true
```

On backend startup, the system will:
- ✅ Crawl your entire website
- ✅ Extract all text content
- ✅ Ingest into RAG knowledge base
- ✅ Keep AI up-to-date with latest website info

**No manual knowledge files needed!** Just point to your website.

## 📚 Example: Midtown Family Dentistry (Current)

**Phone**: (517) 628-4976

**Website**: https://www.midtowndentistrydallas.com/

**Auto-Crawled**: Yes! (14,103 characters ingested from website)

**AI Personality**:
- Warm, welcoming, and family-friendly
- Bilingual (English/Spanish)
- Patient with anxious callers
- Emphasizes same-day appointments and flexible hours

Try calling and ask:
- "What are your hours?"
- "Do you see kids?"
- "Do you accept my insurance?"
- "Can I get a same-day appointment?"

## 🎯 Best Practices

1. **Keep prompt.md focused** - core personality and guidelines only
2. **Put facts in knowledge/** - services, pricing, policies
3. **Use descriptive filenames** - `services.txt`, not `doc1.txt`
4. **Test after changes** - always call to verify
5. **Version control** - commit your business configs to git

## 🔍 Troubleshooting

**Business not syncing?**
```bash
# Check backend logs
docker logs ai-backend --tail 100

# Manually trigger sync
docker exec ai-backend python -c "from app.services.business_sync import sync_all_businesses; sync_all_businesses()"
```

**YAML syntax error?**
- Use a YAML validator
- Check indentation (use spaces, not tabs)
- Ensure quotes around strings with special chars

**Knowledge not working?**
- Files must be `.txt` or `.md`
- Files must be in `knowledge/` folder
- Check logs for ingestion confirmation

## 📖 Full Documentation

See `backend/businesses/README.md` for complete details.

---

## 🎉 Summary

You can now manage all your businesses through simple text files:
- ✅ Easy to edit and version control
- ✅ Auto-syncs to database on startup
- ✅ No database commands needed
- ✅ Perfect for multi-tenant setup

Just edit the files and restart the backend! 🚀

