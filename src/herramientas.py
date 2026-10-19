"""Herramientas del agente ContigoAI. Cada herramienta entrega contenido
estructurado (texto + fuentes) que el LLM debe usar para generar su respuesta.

Catálogo de consulta y razonamiento:
- recuperar_guia_institucional(consulta): RAG sobre documentos oficiales.
- consultar_recursos_salud_mental(): directorio de la red pública.
- consultar_lineas_ayuda(): líneas de ayuda y emergencias.
- evaluar_protocolo_riesgo(mensaje, riesgo_previo): activa protocolo ante señales.
- responder_apoyo(): principios y frases de acompañamiento.
- responder_saludo(): cordialidad y small talk (saludos, conversación casual).

Herramientas de escritura:
- registrar_derivacion(...): deja un registro anónimo de la derivación.
- guardar_resumen_caso(...): guarda un resumen en la memoria de largo plazo.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deteccion import normalizar  # noqa: E402
from rag import Recuperador  # noqa: E402

_RECUPERADOR: Recuperador | None = None
_MEMORIA = None


def _recuperador() -> Recuperador:
    global _RECUPERADOR
    if _RECUPERADOR is None:
        _RECUPERADOR = Recuperador(k=3)
    return _RECUPERADOR


def _memoria():
    """Instancia perezosa de la memoria persistente (SQLite)."""
    global _MEMORIA
    if _MEMORIA is None:
        from memoria import Memoria

        _MEMORIA = Memoria()
    return _MEMORIA


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


def evaluar_protocolo_riesgo(mensaje: str, riesgo_previo: str = "ninguno") -> dict:
    """Activa el protocolo institucional de riesgo. El agente NO diagnostica.

    `riesgo_previo` permite mantener la continuidad: si la sesión ya tenía un
    protocolo activo, este sigue vigente aunque el mensaje actual no repita
    palabras de riesgo.
    """
    t = normalizar(mensaje)
    activo = detectar_es_riesgo_alto(t) or riesgo_previo == "alto"
    return {
        "herramienta": "evaluar_protocolo_riesgo",
        "protocolo_activado": activo,
        "nivel": "alto" if activo else "ninguno",
        "contenido": "\n".join(PROTOCOLO_PASOS) if activo else "Protocolo no activado.",
        "fuentes": ["05_protocolo_institucional_riesgo.md"] if activo else [],
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


def responder_saludo() -> dict:
    """Cordialidad: cómo responder a un saludo o a una conversación casual."""
    contenido = (
        "Saludo y cordialidad (guía institucional):\n"
        "- Responde el saludo con calidez y naturalidad ('¡Hola! Qué bueno que escribiste. Estoy aquí para ti.').\n"
        "- Preséntate brevemente si es el primer mensaje: eres ContigoAI, de la Fundación Contigo, "
        "un espacio de apoyo y orientación.\n"
        "- Invita a contar qué la trae por aquí, sin interrogarla ni lanzar recursos de inmediato.\n"
        "- Si solo quiere conversar o agradecer, conversa con cordialidad: acompaña al ritmo de la persona "
        "y no conviertas un saludo en un formulario.\n"
        "- Mantén el tono humano y breve; el saludo no necesita citas ni recursos.\n"
    )
    return {
        "herramienta": "responder_saludo",
        "contenido": contenido,
        "fuentes": [],
    }


def registrar_derivacion(
    session_id: str, mensaje: str, nivel_riesgo: str, recursos: str
) -> dict:
    """Herramienta de ESCRITURA: registra una derivación anónima.

    Guarda el nivel de riesgo, los recursos entregados y un resumen breve del
    caso. No guarda datos personales: la sesión es un identificador anónimo.
    """
    resumen = mensaje.strip()[:240]
    registro_id = _memoria().registrar_derivacion(
        session_id=session_id,
        nivel_riesgo=nivel_riesgo,
        recursos=recursos.strip()[:600],
        resumen=resumen,
    )
    return {
        "herramienta": "registrar_derivacion",
        "contenido": (
            f"Derivación registrada de forma anónima (registro {registro_id}). "
            f"Nivel de riesgo: {nivel_riesgo}. Recursos entregados: {recursos.strip()[:200]}"
        ),
        "registro_id": registro_id,
        "fuentes": [],
    }


def guardar_resumen_caso(
    session_id: str, resumen: str, nivel_riesgo: str = "ninguno", intencion: str = "apoyo"
) -> dict:
    """Herramienta de ESCRITURA: guarda un resumen en la memoria de largo plazo."""
    texto = (
        f"Resumen de caso (intención={intencion}, riesgo={nivel_riesgo}): "
        f"{resumen.strip()[:1000]}"
    )
    nota_id = _memoria().guardar_nota(session_id, texto, tipo="resumen_caso")
    return {
        "herramienta": "guardar_resumen_caso",
        "contenido": (
            f"Resumen de continuidad guardado en memoria de largo plazo (nota {nota_id})."
        ),
        "nota_id": nota_id,
        "fuentes": [],
    }


HERRAMIENTAS_ESCRITURA = {"registrar_derivacion", "guardar_resumen_caso"}

EJECUTOR = {
    "recuperar_guia_institucional": lambda texto: recuperar_guia_institucional(texto),
    "consultar_recursos_salud_mental": lambda _t: consultar_recursos_salud_mental(),
    "consultar_lineas_ayuda": lambda _t: consultar_lineas_ayuda(),
    "evaluar_protocolo_riesgo": lambda texto: evaluar_protocolo_riesgo(texto),
    "responder_apoyo": lambda _t: responder_apoyo(),
    "responder_saludo": lambda _t: responder_saludo(),
}