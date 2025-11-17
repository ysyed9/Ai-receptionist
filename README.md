# 📞🤖 AI Receptionist Backend

A multi-tenant, real-time AI receptionist engine for businesses.

This backend powers intelligent phone receptionists using OpenAI Realtime, Twilio voice routing, and advanced RAG (Retrieval-Augmented Generation).

Each business is fully isolated with its own tone, knowledge base, hours, and call actions.

## 🚀 Features

### ✅ Multi-Tenant Business System

Each business has its own:

- Phone number
- Forwarding number
- Tone / personality
- Instructions
- Business hours
- Allowed actions
- Appointment credentials
- Separate vector knowledge base

### 🎙️ Realtime AI Answering

- OpenAI Realtime API
- Twilio voice → AI → Twilio audio pipeline
- Barge-in detection
- Human-like conversations
- Can transfer calls, book appointments, send SMS

### 📚 RAG Knowledge Retrieval

- Website crawling
- Document upload
- Chunking & embedding
- Stored in Weaviate vector database
- Retrieved per question

### 🔧 Function Calling

AI can execute real actions:

- `transfer_call`
- `send_sms`
- `schedule_appointment`
- `update_contact`
- `trigger_workflow`
- `custom_action`

### 📞 Telephony Routing (Twilio)

- Map inbound calls → business
- Create realtime LLM session
- Stream audio bi-directionally

### 📊 Logging & Analytics

- Call transcripts
- Actions taken
- Embeddings used
- Errors
- Multi-tenant logs

## 🏗️ Architecture Overview

```
                          ┌───────────────────────┐
                          │       Frontend         │
                          │   (Dashboard / SaaS)   │
                          └───────────┬────────────┘
                                      │
                                      ▼
                          ┌───────────────────────┐
                          │       FastAPI API      │
                          │  (Business + Calls)    │
                          └───────────┬────────────┘
                                      │
                 ┌────────────────────┼────────────────────┐
                 ▼                    ▼                    ▼
        ┌────────────────┐   ┌────────────────┐   ┌─────────────────┐
        │    Postgres     │   │   Weaviate     │   │     Redis        │
        │ Business data   │   │ RAG embeddings │   │ Call sessions    │
        └────────────────┘   └────────────────┘   └─────────────────┘
                                      │
                                      ▼
                          ┌───────────────────────┐
                          │     OpenAI Realtime   │
                          │ Voice, functions, RAG │
                          └───────────┬────────────┘
                                      │
                                      ▼
                          ┌───────────────────────┐
                          │        Twilio          │
                          │ Phone calls routing    │
                          └───────────────────────┘
```

## 📂 Folder Structure

```
ai-receptionist-saas/

│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── db.py
│   │   ├── config.py
│   │   ├── models/
│   │   │   ├── business.py
│   │   │   └── call_log.py
│   │   ├── schemas/
│   │   │   └── business.py
│   │   ├── routers/
│   │   │   ├── business.py
│   │   │   ├── call.py
│   │   │   ├── rag.py
│   │   │   └── actions.py
│   │   └── services/
│   │       ├── business_service.py
│   │       ├── rag_service.py
│   │       ├── llm_realtime.py
│   │       ├── telephony.py
│   │       └── functions.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── docker-compose.yml
└── README.md
```

## ⚙️ Environment Setup

### 1. Clone repo

```bash
git clone https://github.com/yourname/ai-receptionist
cd ai-receptionist/backend
```

### 2. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create .env

```env
APP_ENV=development
APP_SECRET=CHANGE_ME
API_URL=http://localhost:8000

OPENAI_API_KEY=sk-xxxx
OPENAI_MODEL_REST=gpt-4o-mini
OPENAI_MODEL_REALTIME=gpt-4o-realtime-preview
OPENAI_EMBEDDINGS=text-embedding-3-large

TELEPHONY_PROVIDER=twilio
TWILIO_ACCOUNT_SID=ACxxxx
TWILIO_AUTH_TOKEN=xxxx
TWILIO_WEBHOOK_SECRET=xxxx

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ai_reception
POSTGRES_USER=ai_user
POSTGRES_PASSWORD=ai_password
DATABASE_URL=postgresql://ai_user:ai_password@localhost:5432/ai_reception

WEAVIATE_URL=http://weaviate:8080
WEAVIATE_API_KEY=none
WEAVIATE_CLASS_NAME=BusinessDocs

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_URL=redis://redis:6379
```

## 🐳 Docker Setup

From project root:

```bash
docker-compose up --build
```

This starts:

- FastAPI backend (port 8000)
- Postgres (port 5433→container 5432)
- Weaviate (port 8080)
- Redis (port 6379)

## 🧪 Testing Services

### Test API

```bash
GET http://localhost:8000
```

### Test Weaviate

```bash
GET http://localhost:8080/v1/.well-known/ready
```

### Test Redis

```bash
docker exec -it ai-redis redis-cli
PING
```

### Test Postgres

```bash
psql -U ai_user -d ai_reception
```

## 📘 API Endpoints

### ➤ Create Business

```
POST /business/create
```

### ➤ Get Business

```
GET /business/{id}
```

### ➤ List Businesses

```
GET /business/
```

### ➤ Ingest Knowledge (RAG)

```
POST /rag/add
```

### ➤ Twilio Inbound Call Webhook

```
POST /call/inbound
```
