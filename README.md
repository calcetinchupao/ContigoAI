# ContigoAI

Agente conversacional de apoyo, orientación y derivación para personas en situación de **aislamiento social, soledad o crisis emocional** en Chile.

Proyecto de **ISY0101 · Ingeniería de Soluciones con IA**:
- **EP1** — Diseño de Solución con LLM y RAG (IE1–IE9).
- **EP2** — Desarrollo de un Agente Funcional con framework, memoria y planificación (IE1–IE10).

## ¿Qué hace?

ContigoAI integra herramientas de **consulta, razonamiento y escritura** dentro de un grafo de agente (LangGraph):

- `recuperar_guia_institucional` → RAG sobre documentos oficiales (MINSAL, Salud Responde, 4141).
- `consultar_recursos_salud_mental` / `consultar_lineas_ayuda` → recursos oficiales de derivación.
- `evaluar_protocolo_riesgo` → activa el protocolo de seguridad ante señales de riesgo.
- `responder_apoyo` → principios de acompañamiento emocional.
- `responder_saludo` → saludo cordial y conversación casual (sin recursos ni fuentes para un simple "hola").
- `registrar_derivacion` → **escritura**: registra una derivación anónima en SQLite.
- `guardar_resumen_caso` → **escritura**: guarda un resumen en la memoria de largo plazo.

Además:
- **Memoria de corto plazo**: historial por `session_id` (persistido).
- **Memoria de largo plazo**: notas y resúmenes con embeddings y búsqueda semántica.
- **Planificación**: el agente ordena las herramientas por prioridad (seguridad primero).
- **Re-planificación**: si el protocolo sigue activo por continuidad de la sesión, el plan se reconstruye en pleno flujo.
- **Trazabilidad**: cada respuesta expone plan, herramientas, fuentes, memoria usada y trazas de los nodos.

**No** diagnostica, no hace terapia y no reemplaza a profesionales ni a servicios de emergencia.

## Arquitectura

Grafo LangGraph:

```
cargar_contexto → planificar → ejecutar_paso → (replanificar | ejecutar_paso | generar_respuesta)
                                                        ↓
                                            generar_respuesta → guardar_memoria → fin
```

- `src/agente.py`: define el grafo, los nodos y las aristas condicionales.
- `src/planificador.py`: planes priorizados y re-planificación.
- `src/memoria.py`: memoria SQLite (corto y largo plazo + búsqueda semántica).
- `src/herramientas.py`: herramientas de consulta, razonamiento y escritura.
- `src/api.py`: API FastAPI con `session_id` y endpoint de memoria.
- `src/rag.py`, `src/ingesta.py`, `src/embeddings.py`: pipeline RAG de la EP1 reutilizado.
- `informe/orquestacion_ep2.mmd`: diagrama de orquestación (exportable en mermaid.live).

## Estructura

```
ContigoAI/
├── datos/          # Corpus RAG e índice vectorial
├── src/            # Código (grafo, memoria, planificador, RAG, API)
├── pruebas/        # Pruebas y evidencia
├── informe/        # Informe unificado (EP1 + EP2) y diagrama
└── README.md
```

## Requisitos

- Python 3.11+
- Un LLM accesible (recomendado: **Groq** — ver `docs/LLM.md` — o **Ollama** local).
- Dependencias de `requirements.txt` (incluye `langgraph`).

## Ejecución

```bash
pip install -r requirements.txt
cp .env.example .env   # completar GROQ_API_KEY (ver docs/LLM.md)
python src/ingesta.py  # construir índice RAG desde datos/
python src/agente.py   # demo interactiva en consola
uvicorn src.api:app --reload   # servidor web
```

## Cómo usarlo

| Modo | Comando / URL | Qué hace |
|------|---------------|----------|
| **Chat web** | http://localhost:8000 | Conversar, ver plan, re-planificación, memoria y fuentes |
| **Consola** | `python src/agente.py` | Demo con trazabilidad del plan y la memoria |
| **API docs** | http://localhost:8000/docs | Probar `POST /chat` y `GET /memoria/{session_id}` |
| **Memoria** | `GET /memoria/{session_id}` | Ver turnos, notas y derivaciones de una sesión |

Endpoints:

- `POST /chat` → `{ "mensaje": "...", "session_id": "..." }`; devuelve respuesta, plan, herramientas, fuentes, memoria y traza.
- `GET /memoria/{session_id}` → estado de la sesión, últimos turnos, notas y derivaciones.
- `GET /health` → estado del servicio.

La interfaz web genera un `session_id` por conversación y lo conserva en el navegador. El botón **Nueva conversación** inicia una sesión distinta.

## Memoria y privacidad

- La base de memoria se guarda en `datos/memoria/contigoai.db` (ignorada por Git).
- Se puede cambiar con la variable de entorno `CONTIGOAI_DB=/ruta/alternativa.db`.
- El `session_id` es un identificador anónimo; el sistema no solicita datos personales.
- Las derivaciones guardan nivel de riesgo, recursos y un resumen breve, sin identidad de la persona.

## Pruebas y evidencia

```bash
python pruebas/test_pipeline.py      # pipeline RAG y herramientas (EP1)
python pruebas/test_ep2.py           # planificación, memoria, continuidad y API (sin LLM)
python pruebas/test_api.py           # API con LLM real
python pruebas/run_evidencia_ep2.py  # evidencia multi-turno con LLM real
python pruebas/run_evidencia_ep2.py --sin-llm   # misma evidencia, sin red
```

Evidencia EP2 generada:

- `pruebas/evidencia/ep2_memoria_planificacion.md`
- `pruebas/evidencia/ep2_resultados.json`

## Evaluación

- **EP1**: IE1 diseño del proyecto · IE2 prompts · IE3 RAG · IE4 arquitectura · IE5 informe · IE6 coherencia datos↔respuestas · IE7 diagrama · IE8 fundamentación · IE9 comunicación técnica.
- **EP2**: IE1 herramientas autónomas · IE2 framework de agentes · IE3 memoria · IE4 contexto semántico · IE5 planificación · IE6 informe técnico · IE7 demo de decisiones · IE8 diagrama y README · IE9 justificación de componentes · IE10 comunicación técnica.

El informe unificado (EP1 + EP2) está en `informe/informe_tecnico_ep2.md`; las secciones marcadas `[REDACTAR PROPIO (sin IA)]` y `[REDACTAR SIN IA]` deben ser completadas por el equipo.

---

*Caso organizacional ficticio (Fundación Contigo) inspirado en servicios reales chilenos. Las fuentes del RAG son documentos públicos oficiales citados.*
