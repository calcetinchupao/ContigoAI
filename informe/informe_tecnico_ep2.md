# INFORME TÉCNICO — ContigoAI: agente conversacional con LLM, RAG, memoria y planificación

**Asignatura:** ISY0101 · Ingeniería de Soluciones con IA
**Equipo:** [NOMBRES DE LOS INTEGRANTES] — Fecha: [FECHA]
**Repositorio:** [ENLACE GITHUB]

> Documento unificado del proyecto: integra el diseño de la solución (Evaluación Parcial N.º 1)
> y el desarrollo del agente funcional (Evaluación Parcial N.º 2). Reemplaza al informe de la EP1.

---

# Parte A — Base de la solución (EP1)

## A1. Análisis del caso organizacional (IE1)

**Organización.** Fundación Contigo, organización sin fines de lucro del rubro de salud mental y apoyo social, de tamaño pequeño-mediano, con profesionales y voluntarios. Opera la línea de orientación y apoyo emocional “Línea Contigo”, dirigida a personas en situación de aislamiento social, soledad o crisis emocional, especialmente quienes no cuentan con una red de apoyo cercana. *Caso ficticio inspirado en servicios reales chilenos (Salud Responde, Línea 4141), con fuentes oficiales para el corpus de RAG.*

**Problema.** Alta demanda y capacidad humana limitada: (1) tiempos de espera elevados; (2) derivación inconsistente con casos de crisis sin derivación oportuna; (3) consultas informativas que saturan la agenda; (4) barrera de acceso para quien no pide ayuda presencialmente. **Impacto:** cobertura insuficiente, derivaciones tardías y desgaste del equipo voluntario.

**Objetivos (medibles):**

| Objetivo | Indicador | Baseline → Meta |
|---|---|---|
| OE1 | Tiempo a primera orientación | 15 min → < 1 min |
| OE2 | Consultas con señal de riesgo derivadas | 60% → ≥ 90% |
| OE3 | Consultas informativas resueltas sin humano | → ≥ 80% |
| OE4 | Respuestas coherentes con fuentes recuperadas | → ≥ 95% (evidencia §E: 100% en 6 casos) |

**Datos disponibles.** Corpus interno simulado (protocolos y guías institucionales), corpus externo oficial citado (MINSAL, 4141, Salud Responde, red de salud mental), y transcripciones anonimizadas de consultas tipo usadas como casos de prueba.

**Restricciones.** No diagnostica ni reemplaza a profesionales o emergencias; ante señales de riesgo se activa un protocolo de seguridad; confidencialidad y anonimización (Ley 19.628); información verificable y oficial; español, tono empático.

**Motivación técnica.** El lenguaje emocional es libre y variado (LLM), los datos de apoyo deben ser oficiales y trazables (RAG), y la actuación debe cambiar según la situación (agente con herramientas).

## A2. Formulación de prompts (IE2)

Prompt de sistema por bloques (`src/prompts.py`): **rol y límites** (no diagnostica), **anclaje en fuentes** (responder solo con los bloques `[FUENTE:...]`), **tono** (validación emocional), **memoria y continuidad** (retomar lo ya contado y mantener el cuidado si hubo riesgo) y **formato** (≤170 palabras + fuentes consultadas). El prompt de usuario une el mensaje, el historial, la memoria relevante y las salidas de las herramientas ejecutadas como único material factual.

[**CUADRO 1: REDACTAR PROPIO (sin IA)** — comparar una versión del prompt sin bloques vs. la optimizada y qué defectos corrige (ambigüedad de rol, riesgo de inventar teléfonos).]

## A3. Pipeline RAG (IE3)

- **Corpus (6 documentos):** guía MINSAL de salud mental, Línea 4141, Salud Responde, directorio de recursos/emergencias, protocolo institucional de riesgo y guía de acompañamiento (`datos/`).
- **Fuentes internas vs. externas:**

| Tipo | Documentos | Rol en el RAG |
|---|---|---|
| Internas (institucionales, simuladas) | `05_protocolo_institucional_riesgo.md`, `06_guia_acompanamiento_emocional.md` | Protocolos y criterios propios de la Fundación |
| Externas (oficiales, citadas) | `01_guia_minsal_salud_mental.md`, `02_linea_4141_prevencion_suicidio.md`, `03_salud_responde.md`, `04_recursos_derivacion_y_emergencias.md` | Red pública, líneas de ayuda y recursos verificados |

- **Ingesta** (`src/ingesta.py`): fragmentación por párrafos y encabezados (≤900 caracteres), ~80 trozos.
- **Embeddings:** `all-MiniLM-L6-v2` vía fastembed (ONNX); respaldo TF-IDF.
- **Recuperación** (`src/rag.py`): similitud coseno, top-k=3, con metadatos de fuente y puntaje.
- **Flujo:** ingesta → índice vectorial → herramienta `recuperar_guia_institucional` → contexto del LLM.

[**CUADRO 2: REDACTAR PROPIO (sin IA)** — justificar el top-k, el tamaño de trozo y el modelo de embeddings en relación con los objetivos.]

## A4. Arquitectura de componentes (IE4)

Componentes: **API** (FastAPI, `POST /chat`) → **Agente** (`src/agente.py`) que clasifica intención/riesgo (`src/deteccion.py`), planifica y decide las herramientas → **Herramientas** (RAG, líneas de ayuda, recursos, protocolo, apoyo/cordialidad, escritura) → **LLM** (Groq/Ollama) → **Memoria SQLite** (historial, notas, derivaciones). Todo el ciclo entrega **trazabilidad**: intención, riesgo, plan, herramientas, fuentes y traza de nodos.

**[FIGURA 1]** Insertar PNG exportado de `informe/orquestacion_ep2.mmd` (mermaid.live): componentes y orquestación completa.

# Parte B — Agente funcional (EP2)

## B1. Diseño e implementación del agente (IE1, IE2)

**Framework.** El agente se implementó con **LangGraph** (`langgraph>=1.0`), usando un `StateGraph` tipado con seis nodos y aristas condicionales:

```
cargar_contexto → planificar → ejecutar_paso → (replanificar | ejecutar_paso | generar_respuesta)
                                                        ↓
                                            generar_respuesta → guardar_memoria → fin
```

El estado compartido (`EstadoAgente`) transporta mensaje, sesión, historial, memoria recuperada, intención, riesgo, plan, salidas, respuesta y traza.

**Herramientas integradas:**

| Tipo | Herramienta | Implementación |
|---|---|---|
| Consulta | `recuperar_guia_institucional` | RAG sobre corpus oficial (`src/rag.py`) |
| Consulta | `consultar_lineas_ayuda`, `consultar_recursos_salud_mental` | Directorio verificado (`src/herramientas.py`) |
| Razonamiento | `evaluar_protocolo_riesgo` | Protocolo de seguridad con continuidad de sesión |
| Razonamiento | `planificar` / `replanificar` | Plan priorizado por reglas auditables (`src/planificador.py`) |
| Cordialidad | `responder_apoyo`, `responder_saludo` | Acompañamiento emocional y saludo/small talk cálido (`src/herramientas.py`) |
| Escritura | `registrar_derivacion` | Inserta derivación anónima en SQLite |
| Escritura | `guardar_resumen_caso` | Inserta nota con embedding en memoria de largo plazo |

La autonomía se evidencia en la selección y secuenciación de herramientas según intención, riesgo y estado de la sesión, y en la transición condicional que puede cambiar el plan en pleno flujo. La generación de la respuesta queda a cargo del LLM, anclada en las salidas de las herramientas.

[**REDACTAR PROPIO (sin IA):** justificar la elección de LangGraph frente a otras alternativas (LangChain Agents, AutoGen, Haystack), su aporte a la escalabilidad y compatibilidad, y el equilibrio entre reglas auditables y autonomía.]

## B2. Memoria y recuperación de contexto (IE3, IE4)

**Memoria de corto plazo.** Cada conversación usa un `session_id` anónimo. La tabla `turnos` almacena los mensajes de usuario y asistente con intención, riesgo y turno. El nodo `cargar_contexto` recupera los últimos 8 registros hacia el prompt; `guardar_memoria` persiste cada turno para dar continuidad entre peticiones.

**Memoria de largo plazo.** La tabla `memorias` guarda notas y resúmenes con su embedding; `derivaciones` registra las escrituras de la herramienta homónima; `sesiones` conserva `riesgo_max` y `protocolo_activo`, lo que mantiene el cuidado aunque el mensaje actual no repita señales de riesgo.

**Recuperación semántica.** Antes de planificar, el agente embeddea el mensaje con `all-MiniLM-L6-v2` y busca por similitud coseno las `k=3` notas más relevantes de la sesión (umbral 0.20, aislamiento por `session_id`).

**Trazabilidad y privacidad.** `GET /memoria/{session_id}` expone estado, turnos, notas y derivaciones. No se solicitan datos personales; la base local (`datos/memoria/`) se excluye de Git.

[**REDACTAR PROPIO (sin IA):** justificar el diseño de memoria (corto vs. largo plazo), la elección de SQLite, del modelo de embeddings, de `k=3` y del umbral 0.20; explicar cómo asegura la continuidad en flujos prolongados.]

## B3. Planificación y toma de decisiones (IE5)

El plan es una lista de pasos con `prioridad`, `herramienta` y `motivo`. La verificación de riesgo ocupa siempre la prioridad 0; luego se ejecutan las herramientas de la intención detectada y, según el estado, las de escritura y el resumen de continuidad. La arista condicional decide: (1) **re-planificar** si el protocolo se activó y el plan vigente no es de seguridad; (2) **seguir ejecutando** si quedan pasos; (3) **generar la respuesta** cuando el plan termina.

**Ejemplo real (evidencia):** en el turno 3 la persona expresa riesgo alto y se ejecuta el plan de seguridad completo; en el turno 4 escribe “Gracias por escucharme, sigo aquí”: el plan inicial sería de apoyo, pero la verificación detecta el protocolo activo por continuidad, **re-planifica** y vuelve a entregar líneas de ayuda, derivación y recursos.

[**REDACTAR PROPIO (sin IA):** fundamentar las prioridades definidas, los criterios de re-planificación y por qué la seguridad se resuelve con reglas deterministas y no solo con el LLM.]

# Parte C — Documentación y evidencias

## C1. Documentación técnica

- **README** con instalación, ejecución, endpoints, memoria, pruebas y estructura.
- **Diagrama** de componentes y orquestación: `informe/orquestacion_ep2.mmd`.
- **API** FastAPI: `POST /chat` (mensaje + `session_id`), `GET /memoria/{session_id}`, `GET /health`.
- **Interfaz web** que muestra plan inicial, plan final, re-planificación, herramientas, memoria y fuentes.

## C2. Evidencia: coherencia y pruebas (IE6)

- **Coherencia datos ↔ respuestas (EP1):** 6/6 casos (100%) con LLM real — detalle en `pruebas/evidencia/coherencia.md` y `pruebas/evidencia/resultados.json`.
- **Pruebas EP2:** `pruebas/test_ep2.py` 5/5 (planificador, memoria, semántica, continuidad, API); `pruebas/test_pipeline.py` 6/6 (regresión); `pruebas/test_api.py` 5/5 con LLM real.
- **Evidencia multi-turno (EP2):** conversación real de 4 turnos con memoria, derivaciones persistidas y re-planificación — `pruebas/evidencia/ep2_memoria_planificacion.md` y `ep2_resultados.json`.

| Suite | Qué valida | Resultado |
|---|---|---|
| `pruebas/test_pipeline.py` | Intención, riesgo, RAG y protocolo (EP1) | 6/6 |
| `pruebas/test_ep2.py` | Planificación, memoria, continuidad y API | 5/5 |
| `pruebas/test_api.py` | API con LLM real (Groq) | 5/5 |
| `pruebas/run_evidencia_ep2.py` | Conversación de 4 turnos con memoria y re-planificación | Evidencia generada |

[**REDACTAR PROPIO (sin IA):** analizar los resultados, limitaciones (dependencia del LLM, memoria por sesión, ausencia de autenticación) y mejoras futuras.]

## C3. Conclusiones y reflexión individual — [REDACTAR SIN IA]

[**OBLIGATORIO — sin apoyo de IA.** Cada integrante escribe su reflexión personal: aprendizaje, aporte al proyecto y dificultades. Dos reflexiones diferenciadas.]

## C4. Declaración de uso de IA (obligatorio)

Se utilizó IA como asistente de implementación y documentación técnica (estructura del grafo, módulos de memoria y planificación, pruebas y borradores de diagramas). **Las justificaciones técnicas, conclusiones y reflexiones individuales fueron redactadas por el equipo sin IA.** Herramientas utilizadas: [COMPLETAR LISTA].

## Referencias (APA)

1. LangChain. (2026). *LangGraph documentation* (Versión 1.2) [Software]. https://langchain-ai.github.io/langgraph/
2. LangChain. (2026). *LangChain documentation* [Software]. https://python.langchain.com/
3. SQLite. (s. f.). *SQLite documentation*. https://www.sqlite.org/docs.html
4. FastAPI. (2026). *FastAPI documentation*. https://fastapi.tiangolo.com/
5. Qdrant. (2026). *FastEmbed* [Software]. https://github.com/qdrant/fastembed
6. Hugging Face. (2026). *sentence-transformers/all-MiniLM-L6-v2*. https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
7. Groq. (2026). *GroqCloud documentation*. https://console.groq.com/docs
8. Ministerio de Salud de Chile. (2026). *Salud mental: planes y programas*. https://www.minsal.cl/salud-mental/
9. Ministerio de Salud de Chile. (s. f.). *Salud Responde* (600 360 7777). https://saludresponde.minsal.cl/
10. Línea de Prevención del Suicidio 4141. (2026). *Prevención del suicidio en Chile*. https://prevenciondelsuicidio.cl/
11. Organización Mundial de la Salud. (2022). *Informe mundial sobre la salud mental*. OMS.
12. Duoc UC. (2026). *Lineamientos de uso de inteligencia artificial*. https://bibliotecas.duoc.cl/ia

---

**Nota de formato:** el informe de entrega debe exportarse a Word o PDF con un máximo de cinco páginas y citación APA; si se requiere respetar ese límite, la Parte B y la Parte C son la entrega de la EP2 y la Parte A puede resumirse. Exportar `informe/orquestacion_ep2.mmd` como PNG e insertarlo como Figura 1.
