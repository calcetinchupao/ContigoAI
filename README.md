# ContigoAI

Agente conversacional de apoyo, orientación y derivación para personas en situación de **aislamiento social, soledad o crisis emocional** en Chile.

Proyecto para la Evaluación Parcial N.º 1 de **ISY0101 · Ingeniería de Soluciones con IA** (Uso de LLM + RAG + Agentes).

## ¿Qué hace?

ContigoAI es un **agente** que decide qué herramienta usar según lo que escribe la persona:

- `recuperar_guia_institucional` → RAG sobre documentos oficiales (MINSAL, Salud Responde, 4141).
- `consultar_recursos_salud_mental` / `consultar_lineas_ayuda` → entrega recursos oficiales de derivación.
- `evaluar_protocolo_riesgo` → ante señales de riesgo (p. ej. *"no quiero seguir viviendo"*) activa un protocolo de seguridad.
- `responder_apoyo` → respuesta empática de contenido.

**No** diagnostica, no hace terapia y no reemplaza a profesionales ni a servicios de emergencia.

## Estructura

```
ContigoAI/
├── caso/           # Propuesta de caso y objetivos (documento de aprobación)
├── datos/          # Corpus para RAG (documentos oficiales)
├── src/            # Código (RAG, agente, API)
├── pruebas/        # Casos de prueba y evidencia
├── informe/        # Informe técnico (5 páginas)
└── README.md
```

## Requisitos

- Python 3.11+ 
- Un LLM accesible (recomendado: **Groq**, capa gratuita — ver `docs/LLM.md`) o **Ollama** local.

## Ejecución

```bash
pip install -r requirements.txt
cp .env.example .env   # completar GROQ_API_KEY o configurar Ollama
python src/ingesta.py  # construir índice RAG desde datos/
python src/agente.py   # demo interactiva en consola
uvicorn src.api:app --reload   # API REST en http://localhost:8000
```

Endpoints:

- `POST /chat` → envío de mensaje del usuario, respuesta del agente con fuentes citadas.
- `GET /health` → estado del servicio.

## Evaluación

Proyecto diseñado para los indicadores IE1–IE5 (Encargo) y IE6–IE9 (Presentación):

- IE1 Diseño del proyecto de agente · IE2 Prompts · IE3 Flujo RAG · IE4 Arquitectura · IE5 Informe técnico.

---

*Diseñado como caso organizacional ficticio (Fundación Contigo) inspirado en servicios reales chilenos. Las fuentes utilizadas para RAG son documentos públicos oficiales citados.*