import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from explicit .env file location
load_dotenv(BASE_DIR / ".env")

class Settings:
    # App Settings
    APP_NAME: str = "Local AI Mail Automation"
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    
    # Ollama Local LLM
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    
    # RAG Vector Store & Embeddings
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", str(BASE_DIR / "data" / "chroma_db"))
    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
    
    # Whisper Local Speech-to-Text
    WHISPER_MODEL_SIZE: str = os.getenv("WHISPER_MODEL_SIZE", "base")
    WHISPER_DEVICE: str = os.getenv("WHISPER_DEVICE", "cpu")  # 'cpu', 'cuda', or 'auto'
    
    # SQLite Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'mail_automation.db'}")
    
    # Gmail API Credentials
    GMAIL_CREDENTIALS_FILE: str = os.getenv("GMAIL_CREDENTIALS_FILE", str(BASE_DIR / "credentials.json"))
    GMAIL_TOKEN_FILE: str = os.getenv("GMAIL_TOKEN_FILE", str(BASE_DIR / "token.json"))
    GMAIL_USER_EMAIL: str = os.getenv("GMAIL_USER_EMAIL", "me")
    
    # WhatsApp Cloud API Credentials
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    WHATSAPP_ACCESS_TOKEN: str = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
    # Tunneling & Webhook Settings
    WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "mail_automation_secret_verify_token").strip()
    USER_PHONE_NUMBER: str = os.getenv("USER_PHONE_NUMBER", "").strip().lstrip('+')
    TUNNEL_DOMAIN: str = os.getenv("TUNNEL_DOMAIN", "").strip()

settings = Settings()

# Ensure data directory exists
os.makedirs(BASE_DIR / "data", exist_ok=True)
