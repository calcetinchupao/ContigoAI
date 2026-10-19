"""API REST de ContigoAI (FastAPI).

Uso:  uvicorn src.api:app --reload
Endpoints:
- GET  /health → estado del servicio.
- POST /chat   → { "mensaje": "..." } → respuesta del agente con fuentes.
"""
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agente import Agente  # noqa: E402
from config import provider_ok, PROVIDER  # noqa: E402

app = FastAPI(
    title="ContigoAI",
    description=(
        "Agente conversacional de apoyo, orientación y derivación (LLM + RAG) "
        "con memoria, planificación y herramientas de escritura (LangGraph)."
    ),
    version="2.0.0",
)

_AGENTE = Agente()
STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/", include_in_schema=False)
def inicio():
    """Interfaz web de chat estilo ChatGPT."""
    return FileResponse(STATIC_DIR / "index.html")


class ChatRequest(BaseModel):
    mensaje: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(default="anonimo", max_length=120)


class ChatResponse(BaseModel):
    mensaje: str
    respuesta: str
    intencion: str
    nivel_riesgo: str
    protocolo_activado: bool
    herramientas: list[str]
    fuentes: list[str]
    session_id: str
    turno: int
    plan: list[str]
    plan_inicial: list[str]
    replanificado: bool
    memoria: dict
    traza: list[str]


@app.get("/health")
def health():
    return {"estado": "ok", "llm_proveedor": PROVIDER, "llm_configurado": provider_ok()}


@app.get("/memoria/{session_id}")
def memoria_sesion(session_id: str):
    """Estado, turnos, notas y derivaciones de una sesión."""
    memoria = _AGENTE.memoria
    return {
        "estado": memoria.estado_sesion(session_id),
        "ultimos_turnos": memoria.historial(session_id, limite=20),
        "notas": memoria.notas(session_id, limite=20),
        "derivaciones": memoria.derivaciones(session_id, limite=20),
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if not request.mensaje or not request.mensaje.strip():
        raise HTTPException(status_code=422, detail="El campo 'mensaje' no puede estar vacío.")
    try:
        resultado = _AGENTE.procesar(request.mensaje, session_id=request.session_id)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {
        "mensaje": request.mensaje,
        **resultado,
    }