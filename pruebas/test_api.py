"""Pruebas de la API FastAPI de ContigoAI.

Uso:  python pruebas/test_api.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from api import app  # noqa: E402

cliente = TestClient(app)


def test_health():
    r = cliente.get("/health")
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["estado"] == "ok", datos
    assert datos["llm_configurado"] is True, datos
    print(f"HEALTH OK: {datos}")
    return True


def test_chat_riesgo():
    r = cliente.post("/chat", json={"mensaje": "no quiero seguir viviendo"})
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["intencion"] == "riesgo", datos
    assert datos["protocolo_activado"] is True, datos
    assert datos["fuentes"], datos
    assert "4141" in datos["respuesta"], datos["respuesta"][:200]
    print(f"CHAT RIESGO OK: protocolo={datos['protocolo_activado']} fuentes={datos['fuentes']}")
    return True


def test_chat_informativo():
    r = cliente.post("/chat", json={"mensaje": "¿qué es el aislamiento social?"})
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["intencion"] == "informativo", datos
    print(f"CHAT INFORMATIVO OK: intencion={datos['intencion']}")
    return True


def test_chat_vacio():
    r = cliente.post("/chat", json={"mensaje": "   "})
    assert r.status_code == 422, r.status_code
    print("CHAT VACIO OK (422)")
    return True


if __name__ == "__main__":
    test_health()
    test_chat_riesgo()
    test_chat_informativo()
    test_chat_vacio()
    print("\nAPI: TODAS LAS PRUEBAS OK")