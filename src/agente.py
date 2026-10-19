"""Agente orquestador ContigoAI implementado como grafo de LangGraph.

Flujo del grafo:
    cargar_contexto → planificar → ejecutar_paso → (replanificar | ejecutar_paso | generar_respuesta)
                                                         ↓
                                             generar_respuesta → guardar_memoria → fin

- LangGraph orquesta el estado, los bucles de ejecución de herramientas y las
  transiciones condicionales (re-planificación ante señales de riesgo).
- La memoria de corto plazo (historial) y de largo plazo (notas semánticas y
  derivaciones) vive en SQLite (`memoria.py`).
- El planificador (`planificador.py`) ordena las herramientas por prioridad.
- La seguridad se evalúa siempre primero; si el protocolo se activa por
  continuidad de la sesión, el agente re-planifica en pleno flujo.

Uso (demo interactiva):  python src/agente.py
"""
import sys
import uuid
from pathlib import Path
from typing import TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent))

from langgraph.graph import END, START, StateGraph  # noqa: E402

import llm  # noqa: E402
from config import provider_ok  # noqa: E402
from deteccion import clasificar_intencion, detectar_riesgo  # noqa: E402
from herramientas import (  # noqa: E402
    EJECUTOR,
    evaluar_protocolo_riesgo,
    guardar_resumen_caso,
    registrar_derivacion,
)
from memoria import Memoria  # noqa: E402
from planificador import (  # noqa: E402
    construir_plan,
    es_plan_de_riesgo,
    nombres_plan,
    replanificar,
)
from prompts import SYSTEM_PROMPT, construir_mensaje_usuario  # noqa: E402


class EstadoAgente(TypedDict, total=False):
    """Estado compartido por los nodos del grafo."""

    mensaje: str
    session_id: str
    turno: int
    turnos_previos: int
    historial: list[dict]
    estado_sesion: dict
    memoria_contexto: list[dict]
    intencion: str
    nivel_riesgo: str
    protocolo_activado: bool
    plan: list[dict]
    plan_inicial: list[str]
    indice_paso: int
    replanificado: bool
    salidas: list[dict]
    respuesta: str
    fuentes: list[str]
    traza: list[str]


class Agente:
    """Orquestador del agente conversacional basado en LangGraph."""

    def __init__(self, memoria: Memoria | None = None):
        self.memoria = memoria or Memoria()
        self.grafo = self._construir_grafo()

    # ------------------------------------------------------------------
    # Construcción del grafo
    # ------------------------------------------------------------------
    def _construir_grafo(self):
        grafo = StateGraph(EstadoAgente)
        grafo.add_node("cargar_contexto", self._cargar_contexto)
        grafo.add_node("planificar", self._planificar)
        grafo.add_node("ejecutar_paso", self._ejecutar_paso)
        grafo.add_node("replanificar", self._replanificar)
        grafo.add_node("generar_respuesta", self._generar_respuesta)
        grafo.add_node("guardar_memoria", self._guardar_memoria)

        grafo.add_edge(START, "cargar_contexto")
        grafo.add_edge("cargar_contexto", "planificar")
        grafo.add_edge("planificar", "ejecutar_paso")
        grafo.add_conditional_edges(
            "ejecutar_paso",
            self._ruta,
            {
                "replanificar": "replanificar",
                "ejecutar_paso": "ejecutar_paso",
                "generar_respuesta": "generar_respuesta",
            },
        )
        grafo.add_edge("replanificar", "ejecutar_paso")
        grafo.add_edge("generar_respuesta", "guardar_memoria")
        grafo.add_edge("guardar_memoria", END)
        return grafo.compile()

    # ------------------------------------------------------------------
    # Nodos
    # ------------------------------------------------------------------
    @staticmethod
    def _traza(estado: EstadoAgente, texto: str) -> list[str]:
        return estado.get("traza", []) + [texto]

    def _cargar_contexto(self, estado: EstadoAgente) -> dict:
        sid = estado["session_id"]
        self.memoria.asegurar_sesion(sid)
        estado_sesion = self.memoria.estado_sesion(sid)
        historial = self.memoria.historial(sid, limite=8)
        memoria_contexto = self.memoria.buscar_contexto(sid, estado["mensaje"], k=3)
        traza = self._traza(
            estado,
            f"cargar_contexto: {len(historial)} turnos previos y "
            f"{len(memoria_contexto)} notas semánticas recuperadas",
        )
        return {
            "historial": historial,
            "estado_sesion": estado_sesion,
            "memoria_contexto": memoria_contexto,
            "turnos_previos": estado_sesion["turnos"],
            "turno": estado_sesion["turnos"] + 1,
            "traza": traza,
        }

    def _planificar(self, estado: EstadoAgente) -> dict:
        intencion = clasificar_intencion(estado["mensaje"])
        nivel_riesgo = detectar_riesgo(estado["mensaje"])
        # El plan inicial se basa en el mensaje actual. La continuidad de la
        # sesión se resuelve en la verificación de riesgo (y puede re-planificar).
        plan = construir_plan(intencion, nivel_riesgo, None, estado.get("turno", 1))
        traza = self._traza(
            estado,
            f"planificar: intención={intencion}, riesgo={nivel_riesgo}, "
            f"plan={' → '.join(nombres_plan(plan))}",
        )
        return {
            "intencion": intencion,
            "nivel_riesgo": nivel_riesgo,
            "plan": plan,
            "plan_inicial": nombres_plan(plan),
            "indice_paso": 0,
            "replanificado": False,
            "protocolo_activado": False,
            "salidas": [],
            "traza": traza,
        }

    def _resumen_para_memoria(self, estado: EstadoAgente) -> str:
        partes = [
            f"usuario: {turno['texto'][:200]}"
            for turno in estado.get("historial", [])[-6:]
            if turno.get("rol") == "usuario"
        ]
        partes.append(f"usuario: {estado['mensaje'][:200]}")
        return " | ".join(partes)[-1000:]

    def _ejecutar_paso(self, estado: EstadoAgente) -> dict:
        plan = estado["plan"]
        indice = estado.get("indice_paso", 0)
        paso = plan[indice]
        nombre = paso["herramienta"]
        salidas = list(estado.get("salidas", []))

        if nombre == "evaluar_protocolo_riesgo":
            sesion = estado.get("estado_sesion", {})
            riesgo_previo = "alto" if sesion.get("protocolo_activo") else sesion.get("riesgo_max", "ninguno")
            salida = evaluar_protocolo_riesgo(estado["mensaje"], riesgo_previo)
        elif nombre == "registrar_derivacion":
            recursos = next(
                (
                    s.get("contenido", "")
                    for s in reversed(salidas)
                    if s.get("herramienta") == "consultar_lineas_ayuda"
                ),
                "Línea 4141 / Salud Responde 600 360 7777 / emergencias 131 y 133",
            )
            nivel_para_registro = (
                "alto" if estado.get("protocolo_activado") else estado.get("nivel_riesgo", "ninguno")
            )
            salida = registrar_derivacion(
                estado["session_id"],
                estado["mensaje"],
                nivel_para_registro,
                recursos,
            )
        elif nombre == "guardar_resumen_caso":
            nivel_efectivo = (
                "alto" if estado.get("protocolo_activado") else estado.get("nivel_riesgo", "ninguno")
            )
            salida = guardar_resumen_caso(
                estado["session_id"],
                self._resumen_para_memoria(estado),
                nivel_efectivo,
                estado.get("intencion", "apoyo"),
            )
        else:
            salida = EJECUTOR[nombre](estado["mensaje"])

        salidas.append(salida)
        protocolo = bool(estado.get("protocolo_activado")) or bool(
            salida.get("protocolo_activado")
        )
        traza = self._traza(
            estado,
            f"ejecutar_paso [{indice + 1}/{len(plan)}] {nombre} "
            f"(prioridad {paso['prioridad']})",
        )
        return {
            "salidas": salidas,
            "indice_paso": indice + 1,
            "protocolo_activado": protocolo,
            "traza": traza,
        }

    def _ruta(self, estado: EstadoAgente) -> str:
        """Arista condicional: re-planificar, seguir ejecutando o responder."""
        if (
            estado.get("protocolo_activado")
            and not estado.get("replanificado")
            and not es_plan_de_riesgo(estado.get("plan", []))
        ):
            return "replanificar"
        if estado.get("indice_paso", 0) < len(estado.get("plan", [])):
            return "ejecutar_paso"
        return "generar_respuesta"

    def _replanificar(self, estado: EstadoAgente) -> dict:
        nuevo_plan = replanificar(
            estado.get("intencion", "apoyo"),
            estado.get("estado_sesion", {}),
            estado.get("turno", 1),
        )
        traza = self._traza(
            estado,
            "replanificar: el protocolo de riesgo sigue activo por continuidad "
            f"de la sesión; nuevo plan={' → '.join(nombres_plan(nuevo_plan))}",
        )
        return {
            "plan": nuevo_plan,
            "indice_paso": 0,
            "replanificado": True,
            "traza": traza,
        }

    def _generar_respuesta(self, estado: EstadoAgente) -> dict:
        if not provider_ok():
            raise RuntimeError(
                "El proveedor de LLM no está configurado. Agrega tu clave a .env "
                "(ver .env.example) o ejecuta: python -c \"import ollama\" con Ollama local."
            )
        mensaje_usuario = construir_mensaje_usuario(
            estado["mensaje"],
            estado.get("salidas", []),
            estado.get("historial"),
            estado.get("memoria_contexto"),
        )
        respuesta = llm.completar(SYSTEM_PROMPT, mensaje_usuario)
        fuentes = sorted(
            {
                f.split(" (similitud")[0].strip()
                for salida in estado.get("salidas", [])
                for f in salida.get("fuentes", [])[:4]
            }
        )
        traza = self._traza(
            estado, f"generar_respuesta: respuesta generada ({len(respuesta)} caracteres)"
        )
        return {"respuesta": respuesta, "fuentes": fuentes, "traza": traza}

    def _guardar_memoria(self, estado: EstadoAgente) -> dict:
        sid = estado["session_id"]
        turno = estado.get("turno", 1)
        intencion = estado.get("intencion", "apoyo")
        nivel = estado.get("nivel_riesgo", "ninguno")
        salidas = estado.get("salidas", [])
        herramientas = []
        for salida in salidas:
            nombre = salida.get("herramienta")
            if nombre and nombre not in herramientas:
                herramientas.append(nombre)

        self.memoria.registrar_turno(
            sid, turno, "usuario", estado["mensaje"], intencion, nivel
        )
        self.memoria.registrar_turno(
            sid, turno, "asistente", estado.get("respuesta", ""), intencion, nivel
        )
        self.memoria.actualizar_estado(
            sid, intencion, nivel, estado.get("protocolo_activado", False), herramientas
        )
        nota = (
            f"Turno {turno}: la persona dijo: {estado['mensaje'][:300]}. "
            f"Intención={intencion}; riesgo={nivel}; "
            f"protocolo={'activo' if estado.get('protocolo_activado') else 'no'}."
        )
        self.memoria.guardar_nota(sid, nota, tipo="turno")
        traza = self._traza(estado, "guardar_memoria: turno persistido en SQLite (corto y largo plazo)")
        return {"traza": traza}

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def procesar(self, mensaje: str, session_id: str = "anonimo") -> dict:
        session_id = (session_id or "anonimo").strip()[:120] or "anonimo"
        estado_inicial: EstadoAgente = {
            "mensaje": mensaje,
            "session_id": session_id,
            "traza": [],
        }
        final = self.grafo.invoke(estado_inicial)
        salidas = final.get("salidas", [])
        herramientas = []
        for salida in salidas:
            nombre = salida.get("herramienta")
            if nombre and nombre not in herramientas:
                herramientas.append(nombre)

        return {
            "respuesta": final.get("respuesta", ""),
            "intencion": final.get("intencion", "apoyo"),
            "nivel_riesgo": final.get("nivel_riesgo", "ninguno"),
            "protocolo_activado": bool(final.get("protocolo_activado")),
            "herramientas": herramientas,
            "fuentes": final.get("fuentes", []),
            "session_id": session_id,
            "turno": final.get("turno", 1),
            "plan": nombres_plan(final.get("plan", [])),
            "plan_inicial": final.get("plan_inicial", []),
            "replanificado": bool(final.get("replanificado")),
            "memoria": {
                "turnos_previos": final.get("turnos_previos", 0),
                "notas_recuperadas": len(final.get("memoria_contexto", [])),
                "notas": [
                    {
                        "tipo": nota["tipo"],
                        "similitud": nota["similitud"],
                        "texto": nota["texto"][:160],
                    }
                    for nota in final.get("memoria_contexto", [])
                ],
            },
            "traza": final.get("traza", []),
        }


def demo_interactiva() -> None:
    agente = Agente()
    session_id = f"demo-{uuid.uuid4().hex[:8]}"
    print("=" * 60)
    print(f"ContigoAI · modo demo (sesión {session_id})")
    print("Escribe 'salir' para terminar.")
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
            resultado = agente.procesar(mensaje, session_id=session_id)
        except RuntimeError as e:
            print(f"\n[ERROR] {e}")
            continue
        print("\n=== DECISIÓN DEL AGENTE ===")
        print(
            f"Turno: {resultado['turno']} | Intención: {resultado['intencion']} | "
            f"Riesgo: {resultado['nivel_riesgo']} | "
            f"Protocolo: {'ACTIVADO' if resultado['protocolo_activado'] else 'no'}"
        )
        print(f"Plan inicial: {' → '.join(resultado['plan_inicial'])}")
        print(f"Plan final:   {' → '.join(resultado['plan'])}")
        print(f"Re-planificado: {'sí' if resultado['replanificado'] else 'no'}")
        print(f"Memoria: {resultado['memoria']['turnos_previos']} turnos previos, "
              f"{resultado['memoria']['notas_recuperadas']} notas recuperadas")
        print(f"\nContigoAI: {resultado['respuesta']}")
        if resultado["fuentes"]:
            print(f"\n(Fuentes: {', '.join(resultado['fuentes'])})")


if __name__ == "__main__":
    demo_interactiva()
