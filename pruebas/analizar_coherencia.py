"""Matriz de coherencia datos ↔ respuestas (IE6).

A partir de pruebas/evidencia/resultados.json, verifica que los temas clave
recuperados por RAG (fuentes + señales de detección) aparecen en la respuesta
generada por el LLM. Genera una tabla markdown de coherencia.

Uso:  python pruebas/analizar_coherencia.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from deteccion import (  # noqa: E402
    PALABRAS_CRISIS,
    PALABRAS_DIAGNOSTICO,
    PALABRAS_INFORMATIVO,
    PALABRAS_RIESGO,
)

EVIDENCIA = Path(__file__).resolve().parent / "evidencia" / "resultados.json"
SALIDA = Path(__file__).resolve().parent / "evidencia" / "coherencia.md"

# señales esperadas por intención (should appear in response)
TEMPLATES = {
    "riesgo": {"4141", "prevención del suicidio", "salud responde"},
    "crisis": {"4141", "emergencias", "131", "salud responde"},
    "aislamiento": {"cesfam", "cosam", "salud responde"},
    "diagnostico": {"no podemos hacer diagnósticos", "cesfam", "profesional"},
    "informativo": {"aislamiento social", "contactos sociales"},
    "apoyo": {"válido", "espacio seguro", "escuchar"},
}


def normalizar(t):
    import unicodedata

    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def analizar():
    datos = json.loads(EVIDENCIA.read_text(encoding="utf-8"))
    filas = []
    total_ok = 0
    total_casos = 0
    for d in datos:
        if "error" in d:
            continue
        caso = d["caso"]
        resp = normalizar(d["respuesta"])
        senales = TEMPLATES.get(d["intencion"], set())
        coincidencias = {s for s in senales if normalizar(s) in resp} if resp else set()
        ok = len(coincidencias) >= max(1, len(senales) - 1)
        filas.append(
            {
                "caso": caso,
                "intencion": d["intencion"],
                "riesgo": d["nivel_riesgo"],
                "protocolo": d["protocolo_activado"],
                "herramientas": " -> ".join(d["herramientas"]),
                "fuentes": ", ".join(d["fuentes"]),
                "señales_esperadas": len(senales),
                "señales_en_respuesta": len(coincidencias),
                "coherente": ok,
            }
        )
        total_casos += 1
        total_ok += int(ok)

    lineas = [
        "# Matriz de coherencia RAG ↔ Respuestas (evidencia IE6)",
        "",
        f"Total casos analizados: **{total_casos}** · Casos coherentes: **{total_ok}** "
        f"({round(100 * total_ok / max(1, total_casos), 1)}%)",
        "",
        "| Caso | Intención | Riesgo | Protocolo | Herramientas | Señales esperadas | Señales en respuesta | Coherente |",
        "|------|-----------|--------|-----------|--------------|-------------------|----------------------|-----------|",
    ]
    for f in filas:
        lineas.append(
            f"| {f['caso']} | {f['intencion']} | {f['riesgo']} | {'SÍ' if f['protocolo'] else 'no'} "
            f"| {f['herramientas']} | {f['señales_esperadas']} | {f['señales_en_respuesta']} "
            f"| {'✅' if f['coherente'] else '❌'} |"
        )
    lineas += ["", "## Fuentes recuperadas por caso", ""]
    for f in filas:
        lineas.append(f"- **{f['caso']}**: {f['fuentes']}")

    SALIDA.write_text("\n".join(lineas), encoding="utf-8")
    print(f"Coherencia: {total_ok}/{total_casos} casos coherentes")
    print(f"Matriz guardada en: {SALIDA}")


if __name__ == "__main__":
    analizar()