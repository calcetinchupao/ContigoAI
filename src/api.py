"""API REST de ContigoAI (FastAPI).

Uso:  uvicorn src.api:app --reload
Endpoints:
- GET  /health → estado del servicio.
- POST /chat   → { "mensaje": "..." } → respuesta del agente con fuentes.
"""
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agente import Agente  # noqa: E402
from config import provider_ok, PROVIDER  # noqa: E402

app = FastAPI(
    title="ContigoAI",
    description="Agente conversacional de apoyo, orientación y derivación (LLM + RAG).",
    version="1.0.0",
)

_AGENTE = Agente()


class ChatRequest(BaseModel):
    mensaje: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    mensaje: str
    respuesta: str
    intencion: str
    nivel_riesgo: str
    protocolo_activado: bool
    herramientas: list[str]
    fuentes: list[str]


@app.get("/health")
def health():
    return {"estado": "ok", "llm_proveedor": PROVIDER, "llm_configurado": provider_ok()}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if not request.mensaje or not request.mensaje.strip():
        raise HTTPException(status_code=422, detail="El campo 'mensaje' no puede estar vacío.")
    try:
        resultado = _AGENTE.procesar(request.mensaje)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {
        "mensaje": request.mensaje,
        **resultado,
    }