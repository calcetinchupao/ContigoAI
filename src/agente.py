"""Agente orquestador ContigoAI.

Flujo:
1. clasificar intención y riesgo (deteccion.py) → reglas auditables.
2. el agente decide las herramientas a ejecutar (decidir_herramientas).
3. ejecuta cada herramienta (herramientas.py — RAG, líneas de ayuda, protocolo).
4. construye el mensaje con las salidas (prompts.py) y llama al LLM.
5. devuelve respuesta + fuentes + trazabilidad (intención, herramientas, protocolo).

Uso (demo interactiva):  python src/agente.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import llm  # noqa: E402
from config import provider_ok  # noqa: E402
from deteccion import clasificar_intencion, decidir_herramientas, detectar_riesgo  # noqa: E402
from herramientas import EJECUTOR  # noqa: E402
from prompts import SYSTEM_PROMPT, construir_mensaje_usuario  # noqa: E402


class Agente:
    """Orquestador del agente conversacional."""

    def procesar(self, mensaje: str) -> dict:
        # Paso 1-2: decidir intención y plan de herramientas (decisión del agente)
        intencion = clasificar_intencion(mensaje)
        nivel_riesgo = detectar_riesgo(mensaje)
        plan = decidir_herramientas(intencion)

        # Paso 3: ejecutar herramientas
        salidas = []
        for herramienta in plan:
            try:
                ejecutar = EJECUTOR[herramienta]
                salidas.append(ejecutar(mensaje))
            except FileNotFoundError as e:
                raise SystemExit(f"Error de índice RAG: {e}") from e

        protocolo_activado = any(s.get("protocolo_activado") for s in salidas)

        # Paso 4: generar respuesta con LLM anclado en las herramientas
        if not provider_ok():
            raise RuntimeError(
                "El proveedor de LLM no está configurado. Agrega tu clave a .env "
                "(ver .env.example) o ejecuta: python -c \"import ollama\" con Ollama local."
            )
        mensaje_usuario = construir_mensaje_usuario(mensaje, salidas)
        respuesta = llm.completar(SYSTEM_PROMPT, mensaje_usuario)

        # Paso 5: trazabilidad
        fuentes = sorted(
            {
                f.split(" (similitud")[0].strip()
                for s in salidas
                for f in s.get("fuentes", [])[:4]
            }
        )
        return {
            "respuesta": respuesta,
            "intencion": intencion,
            "nivel_riesgo": nivel_riesgo,
            "protocolo_activado": bool(protocolo_activado),
            "herramientas": plan,
            "fuentes": fuentes,
        }


def demo_interactiva() -> None:
    agente = Agente()
    print("=" * 60)
    print("ContigoAI · modo demo. Escribe 'salir' para terminar.")
    print("=" * 60)
    while True:
        try:
            mensaje = input("\nTú: ").strip()
        except EOFError:
            break
        if not mensaje:
            continue
        if mensaje.lower() in ("salir", "exit", "quit"):
            break
        try:
            resultado = agente.procesar(mensaje)
        except RuntimeError as e:
            print(f"\n⚠ {e}")
            continue
        print(f"\n=== DECISIÓN DEL AGENTE ===")
        print(f"Intención: {resultado['intencion']} | Riesgo: {resultado['nivel_riesgo']} | "
              f"Protocolo: {'ACTIVADO' if resultado['protocolo_activado'] else 'no'}")
        print(f"Herramientas: {' → '.join(resultado['herramientas'])}")
        print(f"\nContigoAI: {resultado['respuesta']}")
        if resultado["fuentes"]:
            print(f"\n(Fuentes: {', '.join(resultado['fuentes'])})")


if __name__ == "__main__":
    demo_interactiva()