"""Planificación de tareas del agente ContigoAI.

El plan es una secuencia priorizada de pasos. La seguridad siempre va primero
(verificación de riesgo) y luego se ejecutan las herramientas de consulta,
razonamiento y escritura según la intención y el estado de la sesión.

La re-planificación ocurre cuando la verificación de riesgo se activa en
mitad del flujo (por ejemplo, porque la sesión ya tenía un protocolo activo):
el plan se reconstruye con prioridad máxima para derivar.
"""
from deteccion import decidir_herramientas

MOTIVOS = {
    "evaluar_protocolo_riesgo": "verificar señales de riesgo antes de cualquier otra acción",
    "consultar_lineas_ayuda": "entregar canales oficiales de ayuda inmediata",
    "registrar_derivacion": "dejar un registro anónimo de la derivación (escritura)",
    "consultar_recursos_salud_mental": "ofrecer la red pública de salud mental",
    "recuperar_guia_institucional": "fundamentar la respuesta en el corpus RAG",
    "responder_apoyo": "acompañar emocionalmente según la guía institucional",
    "responder_saludo": "responder con cordialidad e invitar a conversar",
    "guardar_resumen_caso": "persistir un resumen para la continuidad (largo plazo)",
}

PLAN_RIESGO = [
    "evaluar_protocolo_riesgo",
    "consultar_lineas_ayuda",
    "registrar_derivacion",
    "consultar_recursos_salud_mental",
    "recuperar_guia_institucional",
    "responder_apoyo",
]


def _deduplicar(nombres: list[str]) -> list[str]:
    vistos, unicos = set(), []
    for nombre in nombres:
        if nombre not in vistos:
            vistos.add(nombre)
            unicos.append(nombre)
    return unicos


def construir_plan(
    intencion: str,
    nivel_riesgo: str,
    estado_sesion: dict | None = None,
    turno: int = 1,
    forzar_protocolo: bool = False,
) -> list[dict]:
    """Devuelve una lista de pasos ordenados por prioridad.

    Cada paso: {"herramienta", "prioridad", "motivo"}.
    """
    estado = estado_sesion or {}
    riesgo_previo = estado.get("riesgo_max", "ninguno")
    protocolo_previo = bool(estado.get("protocolo_activo"))
    usar_plan_riesgo = (
        forzar_protocolo
        or nivel_riesgo == "alto"
        or protocolo_previo
        or riesgo_previo == "alto"
    )

    if usar_plan_riesgo:
        nombres = list(PLAN_RIESGO)
    else:
        base = decidir_herramientas(intencion)
        nombres = ["evaluar_protocolo_riesgo"] + [h for h in base if h != "evaluar_protocolo_riesgo"]
        if nivel_riesgo == "moderado" and "registrar_derivacion" not in nombres:
            posicion = nombres.index("consultar_lineas_ayuda") + 1 if "consultar_lineas_ayuda" in nombres else 1
            nombres.insert(posicion, "registrar_derivacion")

    if (turno >= 2 or nivel_riesgo != "ninguno" or protocolo_previo) and "guardar_resumen_caso" not in nombres:
        nombres.append("guardar_resumen_caso")

    nombres = _deduplicar(nombres)
    return [
        {
            "herramienta": nombre,
            "prioridad": prioridad,
            "motivo": MOTIVOS.get(nombre, "paso del flujo"),
        }
        for prioridad, nombre in enumerate(nombres)
    ]


def replanificar(
    intencion: str, estado_sesion: dict | None = None, turno: int = 1
) -> list[dict]:
    """Reconstruye el plan con la seguridad como prioridad absoluta."""
    return construir_plan(
        intencion,
        nivel_riesgo="alto",
        estado_sesion=estado_sesion,
        turno=turno,
        forzar_protocolo=True,
    )


def nombres_plan(pasos: list[dict]) -> list[str]:
    return [paso["herramienta"] for paso in pasos]


def es_plan_de_riesgo(pasos: list[dict]) -> bool:
    nombres = set(nombres_plan(pasos))
    return {"consultar_lineas_ayuda", "registrar_derivacion"}.issubset(nombres)
