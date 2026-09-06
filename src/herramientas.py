"""Herramientas del agente ContigoAI. Cada herramienta entrega contenido
estructurado (texto + fuentes) que el LLM debe usar para generar su respuesta.

Catálogo:
- recuperar_guia_institucional(consulta): RAG sobre documentos oficiales.
- consultar_recursos_salud_mental(): directorio de la red pública.
- consultar_lineas_ayuda(): líneas de ayuda y emergencias.
- evaluar_protocolo_riesgo(mensaje): activa protocolo ante señales de riesgo.
- responder_apoyo(): principios y frases de acompañamiento.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deteccion import normalizar  # noqa: E402
from rag import Recuperador  # noqa: E402

_RECUPERADOR: Recuperador | None = None


def _recuperador() -> Recuperador:
    global _RECUPERADOR
    if _RECUPERADOR is None:
        _RECUPERADOR = Recuperador(k=3)
    return _RECUPERADOR


def recuperar_guia_institucional(consulta: str) -> dict:
    """Busca en el corpus oficial (RAG) los trozos más relevantes."""
    resultados = _recuperador().recuperar(consulta)
    trozos_largos = [r["texto"] for r in resultados]
    fragmentos = "\n\n".join(
        f"[FUENTE: {r['fuente']} | sim {r['similitud']}]\n{r['texto'][:600]}"
        for r in resultados
    )
    return {
        "herramienta": "recuperar_guia_institucional",
        "contenido": fragmentos,
        "fuentes": [f"{r['fuente']} (similitud {r['similitud']})" for r in resultados],
        "trozos_largos": trozos_largos,
    }


def consultar_recursos_salud_mental() -> dict:
    """Directorio verificado de la red de salud mental pública chilena."""
    contenido = (
        "CHILE · RED DE SALUD MENTAL (recursos verificados):\n"
        "- CESFAM de la comuna: primer nivel, atención gratuita con FONASA.\n"
        "- COSAM (Centro Comunitario de Salud Mental): tratamiento ambulatorio especializado (vía red pública).\n"
        "- Hospitales / urgencia psiquiátrica: situaciones agudas (presencial).\n"
        "- Salud Responde (MINSAL): 600 360 7777, 24/7, orientación en salud.\n"
    )
    return {
        "herramienta": "consultar_recursos_salud_mental",
        "contenido": contenido,
        "fuentes": ["04_recursos_derivacion_y_emergencias.md", "01_guia_minsal_salud_mental.md"],
    }


def consultar_lineas_ayuda() -> dict:
    """Líneas de ayuda y emergencias disponibles en Chile."""
    contenido = (
        "CHILE · LÍNEAS DE AYUDA 24/7:\n"
        "- Línea de Prevención del Suicidio 4141: escribir por WhatsApp al 4141. Gratuita, 24/7, confidencial.\n"
        "- Salud Responde: 600 360 7777 (MINSAL, orientación 24/7).\n"
        "- Fono Infancia: 800 200 818 (niños, niñas y adolescentes).\n"
        "- EMERGENCIAS (peligro inminente): SAMU 131 · Carabineros 133 · Bomberos 132.\n"
    )
    return {
        "herramienta": "consultar_lineas_ayuda",
        "contenido": contenido,
        "fuentes": ["02_linea_4141_prevencion_suicidio.md", "04_recursos_derivacion_y_emergencias.md"],
    }


PROTOCOLO_PASOS = [
    "1. Acoger con empatía, sin juzgar ni minimizar.",
    "2. Derivar de inmediato a la Línea 4141 (WhatsApp 4141, 24/7, gratuito y confidencial).",
    "3. Complementar con Salud Responde 600 360 7777.",
    "4. Si hay peligro inminente: llamar a SAMU 131 o Carabineros 133.",
    "5. Preguntar si hay alguien cercano que pueda acompañar a la persona ahora.",
    "6. No cerrar sin haber entregado todo el listado de recursos.",
]


def evaluar_protocolo_riesgo(mensaje: str) -> dict:
    """Activa el protocolo institucional de riesgo. El agente NO diagnostica."""
    t = normalizar(mensaje)
    activo = detectar_es_riesgo_alto(t)
    return {
        "herramienta": "evaluar_protocolo_riesgo",
        "protocolo_activado": activo,
        "nivel": "alto" if activo else "ninguno",
        "contenido": "\n".join(PROTOCOLO_PASOS) if activo else "Protocolo no activado.",
        "fuentes": ["05_protocolo_institucional_riesgo.md"],
    }


def detectar_es_riesgo_alto(t: str) -> bool:
    from deteccion import PALABRAS_RIESGO

    return any(p in t for p in PALABRAS_RIESGO)


def responder_apoyo() -> dict:
    """Principios de acompañamiento y validación emocional."""
    contenido = (
        "Acompañamiento emocional (guía institucional):\n"
        "- Responder primero acogiendo, validando y sin juzgar ('Gracias por escribir a este espacio', "
        "'Lo que sientes es válido').\n"
        "- Evitar frases minimizadoras ('no es para tanto', 'anímate').\n"
        "- Mantener la respuesta breve y clara, apta para chat.\n"
        "- No diagnosticar, no medicar ni reemplazar la atención profesional.\n"
    )
    return {
        "herramienta": "responder_apoyo",
        "contenido": contenido,
        "fuentes": ["06_guia_acompanamiento_emocional.md"],
    }


EJECUTOR = {
    "recuperar_guia_institucional": lambda texto: recuperar_guia_institucional(texto),
    "consultar_recursos_salud_mental": lambda _t: consultar_recursos_salud_mental(),
    "consultar_lineas_ayuda": lambda _t: consultar_lineas_ayuda(),
    "evaluar_protocolo_riesgo": lambda texto: evaluar_protocolo_riesgo(texto),
    "responder_apoyo": lambda _t: responder_apoyo(),
}