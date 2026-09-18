# 📧 Local AI Mail Automation System (RAG + WhatsApp Voice Approval)

An end-to-end, privacy-focused, **100% local AI** email automation and voice-guided approval system. 

It monitors incoming emails, retrieves past interaction history using a local Vector Database (RAG), generates draft responses using a local Ollama LLM (`qwen2.5:7b`), and dispatches approval requests via WhatsApp. If rejected or corrected via a WhatsApp voice note, the system transcribes the audio locally using `Whisper`, rewrites the email according to your spoken instructions, sends the email, and confirms back to WhatsApp.

---

## 🏗️ System Architecture

```text
Incoming Email (Gmail) ➔ RAG (ChromaDB + past emails) ➔ Local LLM (Ollama qwen2.5:7b)
                                                                 │
                                                   WhatsApp Approval Request
                                                                 │
                          ┌──────────────────────────────────────┴──────────────────────────────────────┐
                          ▼                                                                             ▼
                   User replies "YES"                                                 User sends Voice Note
                          │                                                                             │
                    Gmail API Send                                                          Local Whisper Speech-to-Text
                          │                                                                             │
                 WhatsApp Confirmation                                                     Ollama Revise & Gmail API Send
                                                                                                        │
                                                                                           WhatsApp Confirmation
```

---

## 📋 Prerequisites & Installation

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start Local Ollama LLM
Make sure Ollama is installed and running on your laptop:
```bash
# Start Ollama service (if not already running)
ollama serve

# Pull Qwen 2.5 7B model
ollama pull qwen2.5:7b
```

---

## 🚀 Running the System

### Option A: Run Local E2E Simulation Test
You can test the full pipeline (RAG + Ollama + Voice Revision) locally right away without setting up live API webhooks:

```bash
python scripts/test_workflow.py
```

### Option B: Start FastAPI Webhook Server
Start the local FastAPI backend server:

```bash
uvicorn main:app --reload --port 8000
```
- Access API documentation: `http://localhost:8000/docs`
- Gmail Webhook Endpoint: `POST http://localhost:8000/webhook/gmail`
- WhatsApp Webhook Endpoint: `POST / GET http://localhost:8000/webhook/whatsapp`

---

## 🔒 Configuration (`.env`)

Copy `.env.example` to `.env` to configure ports and API keys:

```env
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2
WHISPER_MODEL_SIZE=base

DATABASE_URL=sqlite:///./data/mail_automation.db

# Live Credentials (Optional for local testing)
GMAIL_CREDENTIALS_FILE=./credentials.json
WHATSAPP_PHONE_NUMBER_ID=your_id
WHATSAPP_ACCESS_TOKEN=your_token
WHATSAPP_VERIFY_TOKEN=mail_automation_secret_verify_token
```

---

## 📁 Project Structure

```text
Mail Automation/
├── config.py                 # System configuration & env parser
├── main.py                   # FastAPI server entry point
├── database/
│   ├── models.py             # SQLAlchemy DB schemas (EmailThread, Contact, AuditLog)
│   └── session.py            # SQLite database session manager
├── core/
│   ├── llm.py                # Ollama integration (Summarize, Draft, Revise)
│   ├── rag.py                # ChromaDB RAG vector store for email tone context
│   ├── whisper_transcriber.py# Local Whisper speech-to-text transcriber
│   └── state_machine.py      # End-to-end workflow state orchestrator
├── integrations/
│   ├── gmail_client.py       # Gmail API integration (Fetch & Send)
│   └── whatsapp_client.py    # WhatsApp Cloud API client (Send & Media Download)
├── scripts/
│   ├── ingest_past_mails.py  # Ingest historical emails into ChromaDB RAG
│   └── test_workflow.py      # End-to-end local workflow simulator
├── requirements.txt          # Project Python dependencies
└── .env.example              # Sample environment template
```
