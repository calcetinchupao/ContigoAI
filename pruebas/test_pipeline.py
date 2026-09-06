"""Pruebas del pipeline ContigoAI (sin LLM).

Evalúa: detección de intención/riesgo, decisión de herramientas del agente y
ejecución de herramientas (RAG, protocolo, líneas de ayuda).

Uso:  python pruebas/test_pipeline.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from deteccion import clasificar_intencion, decidir_herramientas, detectar_riesgo  # noqa: E402
from herramientas import EJECUTOR  # noqa: E402

CASOS = [
    # (mensaje, intención esperada, riesgo esperado, protocolo_activado esperado)
    ("no quiero seguir viviendo", "riesgo", "alto", True),
    ("estoy desesperado y no sé qué hacer", "crisis", "moderado", False),
    ("llevo semanas sin hablar con nadie", "aislamiento", "ninguno", False),
    ("¿puedes decirme si tengo depresión?", "diagnostico", "ninguno", False),
    ("¿qué es el aislamiento social?", "informativo", "ninguno", False),
    ("gracias, solo quería desahogarme", "apoyo", "ninguno", False),
]


def test_casos():
    aprobados = 0
    for mensaje, inten_esperada, riesgo_esperado, proto_esperado in CASOS:
        inten = clasificar_intencion(mensaje)
        riesgo = detectar_riesgo(mensaje)
        plan = decidir_herramientas(inten)
        ejecutada = EJECUTOR[plan[0]](mensaje)
        proto = bool(ejecutada.get("protocolo_activado", False))
        resultado_llm = ejecutada.get("contenido", "")
        ok = (
            inten == inten_esperada
            and riesgo == riesgo_esperado
            and proto == proto_esperado
            and len(resultado_llm) > 10
        )
        aprobados += int(ok)
        print(
            f"{'OK ' if ok else 'FALLA'} | {mensaje!r:50s} | "
            f"intención={inten:11s} riesgo={riesgo:8s} protocolo={proto} | herramientas={plan}"
        )
    print(f"\nResultado: {aprobados}/{len(CASOS)} casos OK")
    return aprobados == len(CASOS)


def test_rag_ejecucion():
    """Verifica que la herramienta de RAG devuelve trozos con fuente."""
    out = EJECUTOR["recuperar_guia_institucional"]("no quiero seguir viviendo")
    assert out["contenido"].startswith("[FUENTE:"), "RAG no devolvió trozos citados"
    assert out["fuentes"], "RAG sin metadatos de fuente"
    print(f"RAG OK · top simulitudes: {[f.split('(')[0] for f in out['fuentes'][:3]]}")
    return True


if __name__ == "__main__":
    ok1 = test_casos()
    ok2 = test_rag_ejecucion()
    print("\nTODAS LAS PRUEBAS OK" if ok1 and ok2 else "\nHAY FALLAS")
    sys.exit(0 if ok1 and ok2 else 1)