"""Detección de intención y de señales de riesgo.

La clasificación es determinista (reglas) a propósito: en un contexto de
salud mental la activación del protocolo de riesgo debe ser predecible y
auditable, no depender de la muestra estocástica de un LLM. El LLM queda
para la *generación* de la respuesta, siempre anclada en el RAG y en las
herramientas.
"""
import re

PALABRAS_RIESGO = [
    "no quiero seguir viviendo",
    "quiero morir",
    "quiero morirme",
    "acabar con mi vida",
    "terminar con mi vida",
    "hacerme daño",
    "quitarme la vida",
    "suicid",
    "matarme",
    "desaparecer para siempre",
    "última noche",
    "último día",
    "no aguanto más la vida",
    "preferiría no existir",
    "me quiero matar",
]

PALABRAS_CRISIS = [
    "desesperad",
    "no sé qué hacer",
    "ansiedad",
    "ataque de pánico",
    "pánico",
    "angust",
    "colapsad",
    "no puedo más",
    "llorando",
    "al borde",
    "desbordad",
    "perdido",
    "sin salida",
]

PALABRAS_AISLAMIENTO = [
    "soledad",
    "sin hablar con nadie",
    "hablar con nadie",
    "con nadie",
    "sin nadie",
    "sin amigos",
    "sin familia",
    "nadie me habla",
    "nadie me escribe",
    "nadie me escucha",
    "nadie con quien hablar",
    "aislad",
    "no salgo de mi casa",
    "no tengo a nadie",
    "no tengo amigos",
    "no tengo familia",
    "me siento invisible",
    "me siento solo",
    "me siento sola",
    "estoy solo",
    "estoy sola",
    "vivo solo",
    "vivo sola",
    "vivo sin nadie",
    "todo el día solo",
    "todo el día sola",
    "quedado solo",
    "quedado sola",
    "quedó solo",
]

PALABRAS_DIAGNOSTICO = [
    "tengo depresión",
    "estoy deprimido",
    "estoy deprimida",
    "qué enfermedad tengo",
    "diagnostic",
    "soy deprimido",
    "soy ansioso",
    "puedes decirme si tengo",
    "trastorno",
]

PALABRAS_INFORMATIVO = [
    "qué es",
    "qué significa",
    "qué son",
    "información sobre",
    "dónde puedo",
    "dónde ir",
    "como funciona",
    "cómo funciona",
    "cuál es",
    "cuáles son",
    "explic",
]


def normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto.strip().lower())


def detectar_riesgo(texto: str) -> str:
    """Devuelve 'alto', 'moderado' o 'ninguno'."""
    t = normalizar(texto)
    if any(p in t for p in PALABRAS_RIESGO):
        return "alto"
    if any(p in t for p in PALABRAS_CRISIS):
        return "moderado"
    return "ninguno"


def clasificar_intencion(texto: str) -> str:
    """Intención principal: riesgo, crisis, aislamiento, diagnostico,
    informativo o apoyo."""
    t = normalizar(texto)
    if detectar_riesgo(texto) == "alto":
        return "riesgo"
    if any(p in t for p in PALABRAS_CRISIS):
        return "crisis"
    if any(p in t for p in PALABRAS_DIAGNOSTICO):
        return "diagnostico"
    if any(p in t for p in PALABRAS_AISLAMIENTO):
        return "aislamiento"
    if any(p in t for p in PALABRAS_INFORMATIVO):
        return "informativo"
    return "apoyo"


def decidir_herramientas(intencion: str) -> list[str]:
    """El agente decide qué herramientas ejecutar según la intención."""
    plan = {
        "riesgo": ["evaluar_protocolo_riesgo", "consultar_lineas_ayuda", "recuperar_guia_institucional"],
        "crisis": ["consultar_lineas_ayuda", "consultar_recursos_salud_mental", "recuperar_guia_institucional"],
        "aislamiento": ["recuperar_guia_institucional", "responder_apoyo", "consultar_recursos_salud_mental"],
        "diagnostico": ["recuperar_guia_institucional", "responder_apoyo"],
        "informativo": ["recuperar_guia_institucional"],
        "apoyo": ["responder_apoyo", "recuperar_guia_institucional"],
    }
    return plan.get(intencion, ["responder_apoyo"])