"""Trazas locales de EP3. Nunca persiste mensajes, respuestas ni identificadores de sesión.

Los spans se correlacionan con ContextVar (también bajo concurrencia) y se guardan
atómicamente al terminar cada invocación. No implementa el protocolo OpenTelemetry.
"""
from collections import Counter, defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from functools import wraps
import json
import logging
import math
import os
from pathlib import Path
import sqlite3
import time
import threading
import uuid

from config import BASE_DIR

try:
    import psutil
except ImportError:
    psutil = None

_ACTUAL = ContextVar("contigoai_traza", default=None)
_PADRE = ContextVar("contigoai_span", default=None)
ORIGENES = {"chat", "evaluacion_simulada", "evaluacion_real", "fallo_controlado"}


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def memoria_mb():
    try:
        return round(psutil.Process().memory_info().rss / 1024**2, 3) if psutil else None
    except (OSError, psutil.Error if psutil else OSError):
        return None


def percentil(valores, p):
    if not valores:
        return None
    orden = sorted(valores)
    posicion = (len(orden) - 1) * p
    inferior = math.floor(posicion)
    superior = math.ceil(posicion)
    return round(orden[inferior] + (orden[superior] - orden[inferior]) * (posicion - inferior), 3)


def promedio(valores):
    valores = [v for v in valores if v is not None]
    return round(sum(valores) / len(valores), 3) if valores else None


@contextmanager
def tramo(nombre):
    """Mide una etapa; los nombres se definen en código, nunca desde el usuario."""
    registro = _ACTUAL.get()
    if registro is None:
        yield
        return
    span_id = uuid.uuid4().hex[:16]
    inicio = time.perf_counter()
    span = {"span_id": span_id, "parent_id": _PADRE.get(), "nombre": nombre,
            "inicio_ms": round((inicio - registro["_inicio"]) * 1000, 3), "estado": "ok"}
    registro["eventos"].append(span)
    token = _PADRE.set(span_id)
    try:
        yield
    except Exception as exc:
        span.update(estado="error", error_tipo=type(exc).__name__)
        raise
    finally:
        span["duracion_ms"] = round((time.perf_counter() - inicio) * 1000, 3)
        _PADRE.reset(token)


def medir_nodo(nombre):
    def decorador(funcion):
        @wraps(funcion)
        def medida(*args, **kwargs):
            with tramo(nombre):
                return funcion(*args, **kwargs)
        return medida
    return decorador


def registrar_llm(*, entrada=None, salida=None, reintento=False):
    registro = _ACTUAL.get()
    if registro is None:
        return
    if reintento:
        registro["reintentos_llm"] += 1
    for nombre, valor in (("tokens_entrada", entrada), ("tokens_salida", salida)):
        if isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0:
            registro[nombre] = (registro[nombre] or 0) + valor


class ErrorAgente(RuntimeError):
    def __init__(self, trace_id):
        super().__init__("No se pudo completar la respuesta. Reintenta en unos momentos.")
        self.trace_id = trace_id


class Observatorio:
    def __init__(self, ruta=None):
        self.ruta = Path(ruta or os.getenv("CONTIGOAI_OBS_DB") or
                         BASE_DIR / "datos" / "observabilidad" / "metricas.db")
        self._esquema_listo = False
        self._inicio_lock = threading.Lock()

    @contextmanager
    def conexion(self):
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.ruta, timeout=10)
        try:
            with self._inicio_lock:
                if not self._esquema_listo:
                    con.execute("PRAGMA journal_mode=WAL")
                    con.execute("""CREATE TABLE IF NOT EXISTS ejecuciones (
                        trace_id TEXT PRIMARY KEY, fecha TEXT NOT NULL,
                        origen TEXT NOT NULL, estado TEXT NOT NULL, datos TEXT NOT NULL)""")
                    con.execute("CREATE INDEX IF NOT EXISTS idx_ejecuciones_fecha ON ejecuciones(fecha)")
                    con.commit()
                    self._esquema_listo = True
            yield con
            con.commit()
        finally:
            con.close()

    def guardar(self, registro):
        # Retención limitada y sin cascadas hacia la memoria de conversaciones.
        dias = max(1, int(os.getenv("CONTIGOAI_OBS_RETENCION_DIAS", "30")))
        limite = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat(timespec="milliseconds")
        with self.conexion() as con:
            con.execute("INSERT INTO ejecuciones VALUES (?, ?, ?, ?, ?)",
                        (registro["trace_id"], registro["fecha"], registro["origen"],
                         registro["estado"], json.dumps(registro, ensure_ascii=False)))
            con.execute("DELETE FROM ejecuciones WHERE fecha < ?", (limite,))

    @contextmanager
    def ejecucion(self, caracteres, evaluacion=None):
        evaluacion = evaluacion or {}
        origen = evaluacion.get("origen", "chat")
        if origen not in ORIGENES:
            raise ValueError("Origen de observabilidad no permitido")
        registro = {
            "trace_id": uuid.uuid4().hex, "fecha": ahora(), "origen": origen,
            "estado": "ok", "error_tipo": None, "caracteres_entrada": caracteres,
            "caracteres_salida": 0, "tokens_entrada": None, "tokens_salida": None,
            "reintentos_llm": 0, "eventos": [], "rss_inicio_mb": memoria_mb(),
            "intencion": None, "nivel_riesgo": None, "protocolo_activado": None,
            "herramientas": [], "replanificado": False, "evaluacion": None,
            "_inicio": time.perf_counter(),
        }
        # Estas etiquetas provienen exclusivamente del runner, nunca del endpoint /chat.
        if evaluacion:
            registro["evaluacion"] = {k: evaluacion[k] for k in
                ("lote", "caso", "grupo", "repeticion", "esperado") if k in evaluacion}
        token = _ACTUAL.set(registro)
        padre_token = _PADRE.set(None)
        cpu = time.thread_time()
        try:
            yield registro
        except Exception as exc:
            registro.update(estado="error", error_tipo=type(exc).__name__)
            raise
        finally:
            registro["latencia_ms"] = round((time.perf_counter() - registro.pop("_inicio")) * 1000, 3)
            registro["cpu_hilo_ms"] = round((time.thread_time() - cpu) * 1000, 3)
            registro["rss_fin_mb"] = memoria_mb()
            if registro["evaluacion"] and "esperado" in registro["evaluacion"]:
                esperado = registro["evaluacion"]["esperado"]
                aciertos = {k: registro.get(k) == v for k, v in esperado.items()
                            if k in {"intencion", "nivel_riesgo", "protocolo_activado"}}
                if "herramientas" in esperado:
                    aciertos["herramientas"] = set(esperado["herramientas"]).issubset(registro["herramientas"])
                registro["evaluacion"]["aciertos"] = aciertos
                registro["evaluacion"]["correcto"] = bool(aciertos) and all(aciertos.values()) and registro["estado"] == "ok"
            _ACTUAL.reset(token)
            _PADRE.reset(padre_token)
            try:
                self.guardar(registro)
                registro["registrada"] = True
            except (OSError, sqlite3.Error, ValueError):
                # El monitoreo no debe bloquear la atención ni filtrar excepciones.
                registro["registrada"] = False
                logging.getLogger(__name__).warning("No se pudo persistir una traza de observabilidad")

    def consultar(self, dias=7, origen=None, estado=None, limite=5000):
        if not 1 <= dias <= 365 or not 1 <= limite <= 10000:
            raise ValueError("Rango de consulta no permitido")
        desde = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat(timespec="milliseconds")
        sql, parametros = "SELECT datos FROM ejecuciones WHERE fecha >= ?", [desde]
        for campo, valor in (("origen", origen), ("estado", estado)):
            if valor:
                sql += f" AND {campo} = ?"
                parametros.append(valor)
        sql += " ORDER BY fecha DESC, trace_id DESC LIMIT ?"
        parametros.append(limite)
        with self.conexion() as con:
            return [json.loads(fila[0]) for fila in con.execute(sql, parametros)]

    def detalle(self, trace_id):
        with self.conexion() as con:
            fila = con.execute("SELECT datos FROM ejecuciones WHERE trace_id = ?", (trace_id,)).fetchone()
        return json.loads(fila[0]) if fila else None


def resumir(registros):
    total = len(registros)
    errores = sum(r["estado"] == "error" for r in registros)
    evaluadas = [r for r in registros if r.get("evaluacion") and "correcto" in r["evaluacion"]]
    correctas = sum(r["evaluacion"]["correcto"] for r in evaluadas)
    grupos, etapas, por_dia = defaultdict(list), defaultdict(list), defaultdict(list)
    for r in registros:
        por_dia[r["fecha"][:10]].append(r)
        for evento in r["eventos"]:
            etapas[evento["nombre"]].append(evento)
        ev = r.get("evaluacion") or {}
        if r["estado"] == "ok" and ev.get("lote") and ev.get("caso"):
            firma = json.dumps([r["intencion"], r["nivel_riesgo"], r["protocolo_activado"], r["herramientas"]])
            grupos[(r["origen"], ev["lote"], ev["caso"])].append(firma)
    repetidos = [v for v in grupos.values() if len(v) >= 2]
    comparaciones = sum(len(v) * (len(v) - 1) // 2 for v in repetidos)
    coincidencias = sum(sum(n * (n - 1) // 2 for n in Counter(v).values()) for v in repetidos)
    etapas_resumen = [{"nombre": n, "ejecuciones": len(v),
                       "media_ms": promedio([e["duracion_ms"] for e in v]),
                       "p95_ms": percentil([e["duracion_ms"] for e in v], .95),
                       "errores": sum(e["estado"] == "error" for e in v)} for n, v in etapas.items()]
    etapas_resumen.sort(key=lambda e: e["media_ms"], reverse=True)
    fallos = Counter(r["error_tipo"] for r in registros if r["estado"] == "error")
    hallazgos = []
    if errores:
        hallazgos.append({"tipo": "errores", "evidencia": f"{errores} de {total} ejecuciones terminaron con error.",
                          "accion": "Revisar los spans fallidos y separar fallos controlados de incidentes reales."})
    if etapas_resumen:
        lenta = etapas_resumen[0]
        hallazgos.append({"tipo": "latencia", "evidencia": f"Etapa con mayor tiempo medio: {lenta['nombre']} ({lenta['media_ms']} ms).",
                          "accion": "Comparar su p95 por escenario antes de cambiar caché, modelo o concurrencia. Los spans anidados se solapan."})
    if evaluadas and correctas < len(evaluadas):
        hallazgos.append({"tipo": "calidad", "evidencia": f"{len(evaluadas) - correctas} casos no cumplieron todas las etiquetas esperadas.",
                          "accion": "Inspeccionar caso y aciertos en el detalle; ampliar ejemplos y validar con revisión humana."})
    if not evaluadas:
        hallazgos.append({"tipo": "sin_etiquetas", "evidencia": "No hay casos etiquetados en este filtro.",
                          "accion": "Ejecutar la evaluación para medir precisión. Una conversación sin etiqueta no permite calcularla."})
    return {
        "total": total, "errores": errores, "tasa_error_pct": round(100 * errores / total, 2) if total else None,
        "latencia_media_ms": promedio([r["latencia_ms"] for r in registros]),
        "latencia_p50_ms": percentil([r["latencia_ms"] for r in registros], .5),
        "latencia_p95_ms": percentil([r["latencia_ms"] for r in registros], .95),
        "cpu_hilo_media_ms": promedio([r["cpu_hilo_ms"] for r in registros]),
        "rss_fin_media_mb": promedio([r["rss_fin_mb"] for r in registros]),
        "tokens_entrada": sum(r["tokens_entrada"] or 0 for r in registros),
        "tokens_salida": sum(r["tokens_salida"] or 0 for r in registros),
        "ejecuciones_con_tokens": sum(r["tokens_entrada"] is not None for r in registros),
        "reintentos_llm": sum(r["reintentos_llm"] for r in registros),
        "precision_pct": round(100 * correctas / len(evaluadas), 2) if evaluadas else None,
        "casos_evaluados": len(evaluadas), "casos_correctos": correctas,
        "consistencia_pct": round(100 * coincidencias / comparaciones, 2) if comparaciones else None,
        "pares_comparados": comparaciones, "grupos_repetidos": len(repetidos),
        "etapas": etapas_resumen, "errores_por_tipo": dict(fallos), "hallazgos": hallazgos,
        "serie": [{"dia": dia, "total": len(v), "errores": sum(r["estado"] == "error" for r in v),
                   "latencia_ms": promedio([r["latencia_ms"] for r in v])} for dia, v in sorted(por_dia.items())],
        "por_origen": dict(Counter(r["origen"] for r in registros)),
        "limite_consulta": 5000, "muestra_posiblemente_truncada": total >= 5000,
    }
