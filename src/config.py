"""Configuración de ContigoAI: carga de variables de entorno y proveedor de LLM."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

PROVIDER = os.getenv("LLM_PROVIDER", "groq").strip().lower()

# Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()

# Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip().rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2").strip()

# OpenAI / compatibles
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2").strip()

DATOS_DIR = BASE_DIR / "datos"
INDICE_DIR = BASE_DIR / "datos" / ".indice"


def provider_ok() -> bool:
    """Indica si el proveedor configurado está listo (tiene key / está accesible)."""
    if PROVIDER == "groq":
        return bool(GROQ_API_KEY)
    if PROVIDER == "openai":
        return bool(OPENAI_API_KEY)
    if PROVIDER == "ollama":
        return True
    return False