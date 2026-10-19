"""Pruebas del agente funcional (planificación, memoria, continuidad y API).

Cubre:
1. Planificación priorizada (seguridad primero).
2. Memoria de corto plazo (historial por sesión).
3. Memoria de largo plazo con recuperación semántica.
4. Continuidad multi-turno y re-planificación por riesgo persistente.
5. Herramientas de escritura (derivaciones y resúmenes persistidos).
6. Integración con la API (`session_id` y endpoint de memoria).
7. Cordialidad: un saludo recibe trato cálido, sin recursos ni fuentes.

Usa un LLM simulado (no consume tokens ni requiere red).

Uso:  python pruebas/test_ep2.py
"""
import os
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))

DB_PRUEBA = Path(tempfile.gettempdir()) / f"contigoai_ep2_{os.getpid()}.db"
for sufijo in ("", "-wal", "-shm"):
    archivo = Path(str(DB_PRUEBA) + sufijo)
    if archivo.exists():
        archivo.unlink()
os.environ["CONTIGOAI_DB"] = str(DB_PRUEBA)

import llm  # noqa: E402
from agente import Agente  # noqa: E402
from memoria import Memoria  # noqa: E402
from planificador import construir_plan, es_plan_de_riesgo, nombres_plan  # noqa: E402

PROMPTS_RECIBIDOS = []


def _llm_simulado(sistema, usuario):
    PROMPTS_RECIBIDOS.append(usuario)
    return (
        "Gracias por contarme esto; no estás solo/a. "
        "Si lo necesitas, escribe al WhatsApp 4141 (24/7) o llama a Salud Responde 600 360 7777."
    )


llm.completar = _llm_simulado


def test_planificador():
    plan = construir_plan("apoyo", "ninguno", None, 1)
    nombres = nombres_plan(plan)
    assert nombres[0] == "evaluar_protocolo_riesgo", nombres
    assert [p["prioridad"] for p in plan] == list(range(len(plan))), plan
    assert "registrar_derivacion" not in nombres, nombres
    assert not es_plan_de_riesgo(plan)

    plan_riesgo = construir_plan("riesgo", "alto")
    nombres_riesgo = nombres_plan(plan_riesgo)
    assert es_plan_de_riesgo(plan_riesgo)
    assert nombres_riesgo.index("consultar_lineas_ayuda") < nombres_riesgo.index(
        "registrar_derivacion"
    )
    print("PLANIFICADOR OK: seguridad primero y prioridades ordenadas")
    return True


def test_memoria_corto_plazo():
    memoria = Memoria(DB_PRUEBA)
    sid = "prueba-memoria"
    memoria.registrar_turno(
        sid, 1, "usuario", "llevo semanas sin hablar con nadie", "aislamiento", "ninguno"
    )
    memoria.registrar_turno(
        sid, 1, "asistente", "respuesta de prueba", "aislamiento", "ninguno"
    )
    historial = memoria.historial(sid)
    assert len(historial) == 2, historial
    assert historial[0]["rol"] == "usuario", historial
    assert "semanas sin hablar" in historial[0]["texto"], historial
    print("MEMORIA CORTO PLAZO OK: historial recuperado por sesión")
    return True


def test_memoria_semantica():
    memoria = Memoria(DB_PRUEBA)
    sid = "prueba-semantica"
    memoria.guardar_nota(sid, "La persona reporta ansiedad y ataques de pánico.")
    memoria.guardar_nota(sid, "La persona habla de su trabajo y su jefe.")
    memoria.guardar_nota(sid, "La persona extraña a su familia.")
    resultados = memoria.buscar_contexto(sid, "estoy muy ansioso y con pánico", k=2)
    assert resultados, "No se recuperó ninguna nota"
    assert "ansiedad" in resultados[0]["texto"].lower(), resultados
    print(
        "MEMORIA SEMÁNTICA OK: consulta 'ansioso' → "
        f"{resultados[0]['texto'][:50]!r} (sim {resultados[0]['similitud']})"
    )
    return True


def test_agente_multiturno():
    agente = Agente()
    sid = "prueba-multiturno"

    r1 = agente.procesar("no quiero seguir viviendo", sid)
    assert r1["nivel_riesgo"] == "alto", r1
    assert r1["protocolo_activado"] is True, r1
    assert "registrar_derivacion" in r1["herramientas"], r1
    assert "guardar_resumen_caso" in r1["herramientas"], r1
    assert r1["memoria"]["turnos_previos"] == 0, r1["memoria"]

    r2 = agente.procesar("gracias por escucharme, sigo aquí", sid)
    assert r2["intencion"] == "apoyo", r2
    assert r2["protocolo_activado"] is True, r2
    assert r2["replanificado"] is True, r2
    assert "consultar_lineas_ayuda" in r2["plan"], r2
    assert r2["memoria"]["turnos_previos"] == 1, r2["memoria"]
    assert r2["memoria"]["notas_recuperadas"] >= 1, r2["memoria"]
    assert any("Historial reciente" in p for p in PROMPTS_RECIBIDOS), (
        "El prompt no incluyó el historial de la conversación"
    )

    derivaciones = agente.memoria.derivaciones(sid)
    assert len(derivaciones) >= 2, derivaciones
    notas = agente.memoria.notas(sid, tipo="resumen_caso")
    assert notas, "No se guardaron resúmenes de caso"
    estado = agente.memoria.estado_sesion(sid)
    assert estado["protocolo_activo"] is True, estado
    assert estado["riesgo_max"] == "alto", estado

    print(
        "AGENTE MULTITURNO OK: continuidad + re-planificación "
        f"(turno 2, plan={r2['plan']})"
    )
    return True


def test_saludo_cordial():
    agente = Agente()
    sid = "prueba-saludo"

    r1 = agente.procesar("Hola, ¿cómo estás?", sid)
    assert r1["intencion"] == "saludo", r1
    assert "responder_saludo" in r1["herramientas"], r1
    assert "recuperar_guia_institucional" not in r1["herramientas"], r1
    assert r1["protocolo_activado"] is False, r1
    assert r1["fuentes"] == [], r1["fuentes"]
    assert r1["respuesta"], r1

    r2 = agente.procesar("buenas tardes, ¿qué es el COSAM?", sid)
    assert r2["intencion"] == "informativo", r2
    assert "recuperar_guia_institucional" in r2["herramientas"], r2

    print("SALUDO CORDIAL OK: trato cálido sin recursos ni fuentes para small talk")
    return True


def test_api_memoria():
    from fastapi.testclient import TestClient

    from api import app

    cliente = TestClient(app)
    sid = "prueba-api"

    r1 = cliente.post(
        "/chat",
        json={"mensaje": "llevo semanas sin hablar con nadie", "session_id": sid},
    )
    assert r1.status_code == 200, r1.text
    datos1 = r1.json()
    assert datos1["session_id"] == sid, datos1
    assert datos1["plan"], datos1
    assert datos1["traza"], datos1
    assert datos1["memoria"]["turnos_previos"] == 0, datos1["memoria"]

    r2 = cliente.post(
        "/chat", json={"mensaje": "gracias por escucharme", "session_id": sid}
    )
    assert r2.status_code == 200, r2.text
    datos2 = r2.json()
    assert datos2["memoria"]["turnos_previos"] == 1, datos2["memoria"]

    memoria = cliente.get(f"/memoria/{sid}")
    assert memoria.status_code == 200, memoria.text
    cuerpo = memoria.json()
    assert len(cuerpo["ultimos_turnos"]) >= 4, cuerpo["ultimos_turnos"]
    assert cuerpo["estado"]["turnos"] == 2, cuerpo["estado"]

    print("API OK: session_id, trazas y endpoint /memoria funcionando")
    return True


def main():
    pruebas = [
        test_planificador,
        test_memoria_corto_plazo,
        test_memoria_semantica,
        test_agente_multiturno,
        test_saludo_cordial,
        test_api_memoria,
    ]
    aprobadas = 0
    for prueba in pruebas:
        try:
            prueba()
            aprobadas += 1
        except AssertionError as e:
            print(f"FALLA {prueba.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {prueba.__name__}: {type(e).__name__}: {e}")
    print(f"\nResultado: {aprobadas}/{len(pruebas)} pruebas OK")
    return aprobadas == len(pruebas)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
