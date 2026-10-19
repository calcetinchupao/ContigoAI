"""Genera evidencia de memoria, planificación y re-planificación.

Ejecuta una conversación de 4 turnos en una misma sesión y guarda:
- pruebas/evidencia/ep2_resultados.json
- pruebas/evidencia/ep2_memoria_planificacion.md

Uso:
    python pruebas/run_evidencia_ep2.py            # usa el LLM real configurado
    python pruebas/run_evidencia_ep2.py --sin-llm  # sin red (respuestas simuladas)
"""
import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))

import llm  # noqa: E402
from agente import Agente  # noqa: E402
from config import PROVIDER  # noqa: E402

EVIDENCIA = BASE / "pruebas" / "evidencia"
GUION = [
    "Llevo semanas sin hablar con nadie y me siento muy solo.",
    "Ayer te conté que estoy solo; hoy sigo igual.",
    "A veces siento que no quiero seguir viviendo.",
    "Gracias por escucharme, sigo aquí.",
]


def _md(texto: str) -> str:
    return " ".join(str(texto).split()).replace("|", "\\|")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sin-llm", action="store_true")
    args = parser.parse_args()

    if args.sin_llm:
        llm.completar = lambda sistema, usuario: (
            "[RESPUESTA SIMULADA] Gracias por contarme esto. No estás solo/a. "
            "WhatsApp 4141 / Salud Responde 600 360 7777 / emergencias 131 y 133."
        )
        proveedor = "simulado"
    else:
        proveedor = PROVIDER

    agente = Agente()
    session_id = f"evidencia-{uuid.uuid4().hex[:8]}"
    resultados = []

    print(f"Sesión de evidencia: {session_id} (proveedor: {proveedor})")
    for indice, mensaje in enumerate(GUION, start=1):
        resultado = agente.procesar(mensaje, session_id=session_id)
        resultados.append(
            {
                "turno": indice,
                "mensaje": mensaje,
                "intencion": resultado["intencion"],
                "nivel_riesgo": resultado["nivel_riesgo"],
                "protocolo_activado": resultado["protocolo_activado"],
                "plan_inicial": resultado["plan_inicial"],
                "plan_final": resultado["plan"],
                "replanificado": resultado["replanificado"],
                "herramientas": resultado["herramientas"],
                "fuentes": resultado["fuentes"],
                "memoria": resultado["memoria"],
                "respuesta": resultado["respuesta"],
                "traza": resultado["traza"],
            }
        )
        print(
            f"Turno {indice}: intención={resultado['intencion']} "
            f"riesgo={resultado['nivel_riesgo']} "
            f"protocolo={resultado['protocolo_activado']} "
            f"replan={resultado['replanificado']} "
            f"memoria={resultado['memoria']['turnos_previos']} turnos/"
            f"{resultado['memoria']['notas_recuperadas']} notas"
        )

    estado = agente.memoria.estado_sesion(session_id)
    derivaciones = agente.memoria.derivaciones(session_id)
    notas = agente.memoria.notas(session_id, limite=50)

    payload = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "proveedor": proveedor,
        "session_id": session_id,
        "guion": GUION,
        "resultados": resultados,
        "estado_final_sesion": estado,
        "derivaciones": derivaciones,
        "notas": notas,
    }
    EVIDENCIA.mkdir(parents=True, exist_ok=True)
    (EVIDENCIA / "ep2_resultados.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lineas = [
        "# Evidencia EP2 — Memoria, planificación y re-planificación",
        "",
        f"**Generado:** {payload['generado']}  ",
        f"**Proveedor LLM:** {proveedor}  ",
        f"**Sesión:** `{session_id}`  ",
        f"**Guion:** {len(GUION)} turnos en la misma conversación",
        "",
        "## Resumen por turno",
        "",
        "| Turno | Mensaje | Intención | Riesgo | Protocolo | Plan inicial | Plan final | ¿Re-planificó? | Herramientas | Memoria |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in resultados:
        lineas.append(
            "| {turno} | {mensaje} | {intencion} | {riesgo} | {protocolo} | {inicial} | "
            "{final} | {replan} | {herramientas} | {memoria} |".format(
                turno=r["turno"],
                mensaje=_md(r["mensaje"]),
                intencion=r["intencion"],
                riesgo=r["nivel_riesgo"],
                protocolo="SÍ" if r["protocolo_activado"] else "no",
                inicial=_md(" → ".join(r["plan_inicial"])),
                final=_md(" → ".join(r["plan_final"])),
                replan="SÍ" if r["replanificado"] else "no",
                herramientas=_md(" → ".join(r["herramientas"])),
                memoria=(
                    f"{r['memoria']['turnos_previos']} turnos / "
                    f"{r['memoria']['notas_recuperadas']} notas"
                ),
            )
        )

    lineas += ["", "## Trazabilidad de cada turno", ""]
    for r in resultados:
        lineas += [
            f"### Turno {r['turno']}",
            "",
            f"**Mensaje:** {r['mensaje']}",
            "",
            "```",
            *r["traza"],
            "```",
            "",
        ]

    lineas += [
        "## Estado final de la sesión (memoria de corto plazo)",
        "",
        "```json",
        json.dumps(estado, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Escrituras persistidas (memoria de largo plazo)",
        "",
        f"- **Derivaciones registradas:** {len(derivaciones)}",
    ]
    for derivacion in derivaciones:
        lineas.append(
            f"  - Registro {derivacion['id']} · riesgo={derivacion['nivel_riesgo']} · "
            f"resumen={_md(derivacion['resumen'][:120])}"
        )
    lineas.append(f"- **Notas semánticas guardadas:** {len(notas)}")
    for nota in notas[:8]:
        lineas.append(f"  - [{nota['tipo']}] {_md(nota['texto'][:160])}")

    lineas += ["", "## Respuestas del agente (extracto)", ""]
    for r in resultados:
        extracto = _md(r["respuesta"][:600])
        lineas += [
            f"### Turno {r['turno']}",
            "",
            f"> {extracto}",
            "",
            f"**Fuentes:** {', '.join(r['fuentes']) or '—'}",
            "",
        ]

    (EVIDENCIA / "ep2_memoria_planificacion.md").write_text(
        "\n".join(lineas), encoding="utf-8"
    )

    print(f"\nEvidencia guardada en {EVIDENCIA}")
    print("- ep2_resultados.json")
    print("- ep2_memoria_planificacion.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
