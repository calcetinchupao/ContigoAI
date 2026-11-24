"""API del chat y dashboard local de observabilidad. Ejecutar: uvicorn src.api:app."""
import csv
import io
import json
import os
import secrets
import sys
import uuid
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agente import Agente  # noqa: E402
from config import provider_ok, PROVIDER  # noqa: E402
from observabilidad import ErrorAgente, resumir  # noqa: E402

app = FastAPI(title="ContigoAI", version="3.0.0", description="Agente con memoria, planificación y observabilidad EP3.")
_AGENTE = Agente()
STATIC_DIR = Path(__file__).resolve().parent / "static"


def autorizar_monitor(request: Request, x_observabilidad_token: str | None = Header(default=None)):
    """Sin clave: solo acceso local directo. Con clave: siempre se exige el header."""
    clave = os.getenv("CONTIGOAI_OBS_TOKEN", "").strip()
    if clave:
        if not secrets.compare_digest((x_observabilidad_token or "").encode(), clave.encode()):
            raise HTTPException(status_code=401, detail="Ingresa la clave de monitoreo.")
    elif not request.client or request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(status_code=403, detail="Monitoreo disponible solo desde este equipo; configura CONTIGOAI_OBS_TOKEN para acceso remoto.")


@app.middleware("http")
async def privacidad_http(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.get("/", include_in_schema=False)
def inicio():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/observabilidad", include_in_schema=False)
def dashboard():
    return FileResponse(STATIC_DIR / "observabilidad.html")


class ChatRequest(BaseModel):
    mensaje: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex, min_length=1, max_length=120)


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
    observabilidad: dict


@app.get("/health")
def health():
    return {"estado": "ok", "llm_proveedor": PROVIDER, "llm_configurado": provider_ok()}


@app.get("/memoria/{session_id}", dependencies=[Depends(autorizar_monitor)])
def memoria_sesion(session_id: str):
    memoria = _AGENTE.memoria
    return {"estado": memoria.estado_sesion(session_id), "ultimos_turnos": memoria.historial(session_id, limite=20),
            "notas": memoria.notas(session_id, limite=20), "derivaciones": memoria.derivaciones(session_id, limite=20)}


@app.delete("/memoria/{session_id}", dependencies=[Depends(autorizar_monitor)])
def eliminar_memoria(session_id: str):
    _AGENTE.memoria.eliminar_sesion(session_id)
    return {"eliminada": True}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if not request.mensaje.strip():
        raise HTTPException(status_code=422, detail="El mensaje no puede estar vacío.")
    try:
        resultado = _AGENTE.procesar(request.mensaje, session_id=request.session_id)
    except ErrorAgente as exc:
        raise HTTPException(status_code=503, detail={"mensaje": str(exc), "trace_id": exc.trace_id}) from exc
    return {"mensaje": request.mensaje, **resultado}


def filtros(
    dias: int = Query(default=7, ge=1, le=365),
    origen: Literal["chat", "evaluacion_simulada", "evaluacion_real", "fallo_controlado"] | None = None,
    estado: Literal["ok", "error"] | None = None,
):
    return {"dias": dias, "origen": origen, "estado": estado}


@app.get("/api/observabilidad/resumen", dependencies=[Depends(autorizar_monitor)])
def resumen_monitoreo(filtro: dict = Depends(filtros)):
    return resumir(_AGENTE.observatorio.consultar(**filtro))


@app.get("/api/observabilidad/trazas", dependencies=[Depends(autorizar_monitor)])
def trazas_monitoreo(filtro: dict = Depends(filtros), limite: int = Query(default=100, ge=1, le=500)):
    return _AGENTE.observatorio.consultar(**filtro, limite=limite)


@app.get("/api/observabilidad/trazas/{trace_id}", dependencies=[Depends(autorizar_monitor)])
def detalle_traza(trace_id: str):
    registro = _AGENTE.observatorio.detalle(trace_id)
    if registro is None:
        raise HTTPException(status_code=404, detail="Traza no encontrada")
    return registro


@app.get("/api/observabilidad/exportar", dependencies=[Depends(autorizar_monitor)])
def exportar_monitoreo(formato: Literal["csv", "json"] = "csv", filtro: dict = Depends(filtros)):
    registros = _AGENTE.observatorio.consultar(**filtro)
    if formato == "json":
        contenido, tipo = json.dumps(registros, ensure_ascii=False, indent=2), "application/json"
    else:
        salida = io.StringIO(newline="")
        campos = ["trace_id", "fecha", "origen", "estado", "error_tipo", "intencion", "nivel_riesgo",
                  "latencia_ms", "cpu_hilo_ms", "rss_fin_mb", "tokens_entrada", "tokens_salida", "reintentos_llm"]
        writer = csv.DictWriter(salida, fieldnames=campos, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(registros)
        contenido, tipo = "\ufeff" + salida.getvalue(), "text/csv; charset=utf-8"
    return Response(contenido, media_type=tipo, headers={"Content-Disposition": f'attachment; filename="contigoai_metricas.{formato}"'})
