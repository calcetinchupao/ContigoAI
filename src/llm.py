"""Clientes de LLM (Groq / Ollama / OpenAI-compatible) mediante HTTP."""
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (  # noqa: E402
    GROQ_API_KEY,
    GROQ_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_BASE_URL,
    PROVIDER,
)

MAX_REINTENTOS = 5


def _chat_openai_compatible(
    base_url: str, api_key: str, modelo: str, sistema: str, usuario: str
) -> str:
    if not api_key:
        raise RuntimeError("Falta API key para el proveedor configurado (revisa .env).")
    url = f"{base_url}/chat/completions"
    payload = {
        "model": modelo,
        "messages": [
            {"role": "system", "content": sistema},
            {"role": "user", "content": usuario},
        ],
        "temperature": 0.3,
        "max_tokens": 600,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    for intento in range(MAX_REINTENTOS):
        try:
            r = httpx.post(url, json=payload, headers=headers, timeout=90)
            if r.status_code in (429, 500, 502, 503, 529):
                espera = 2 ** intento
                time.sleep(espera)
                continue
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Error LLM ({e.response.status_code}): {e.response.text[:300]}") from e
        except httpx.HTTPError as e:
            raise RuntimeError(f"Error de conexión con el LLM: {e}") from e
    raise RuntimeError("El LLM no respondió tras varios reintentos (exceso de tasa de uso).")


def _chat_ollama(sistema: str, usuario: str) -> str:
    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": sistema},
            {"role": "user", "content": usuario},
        ],
        "stream": False,
        "options": {"temperature": 0.3},
    }
    try:
        r = httpx.post(url, json=payload, timeout=240)
        r.raise_for_status()
        return r.json()["message"]["content"]
    except (httpx.HTTPError, KeyError) as e:
        raise RuntimeError(
            "No se pudo conectar con Ollama. Verifica: ollama serve y ollama pull llama3.2"
        ) from e


def completar(sistema: str, usuario: str) -> str:
    """Genera una respuesta usando el proveedor configurado en .env."""
    if PROVIDER == "groq":
        return _chat_openai_compatible(
            "https://api.groq.com/openai/v1", GROQ_API_KEY, GROQ_MODEL, sistema, usuario
        )
    if PROVIDER == "openai":
        return _chat_openai_compatible(OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL, sistema, usuario)
    if PROVIDER == "ollama":
        return _chat_ollama(sistema, usuario)
    raise RuntimeError(f"Proveedor LLM no soportado: {PROVIDER}")