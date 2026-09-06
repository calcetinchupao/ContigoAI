# INFORME TÉCNICO — ContigoAI: agente conversacional de apoyo y derivación (LLM + RAG)

**Asignatura:** ISY0101 · Ingeniería de Soluciones con IA — Evaluación Parcial N.º 1
**Equipo:** [NOMBRES DE LOS INTEGRANTES] — Fecha: [FECHA]
**Repositorio:** [ENLACE GITHUB]

---

## 1. Análisis del caso organizacional (IE1)

**Organización.** Fundación Contigo, organización sin fines de lucro que opera la línea de orientación y apoyo emocional "Línea Contigo" para personas en aislamiento social, soledad o crisis emocional en Chile. *Caso ficticio inspirado en servicios reales (Salud Responde, Línea 4141) con fuentes oficiales para el corpus de RAG.*

**Problema.** Alta demanda y capacidad humana limitada: tiempos de espera elevados, derivación inconsistente a recursos profesionales (riesgo de derivación tardía en crisis), saturación por consultas informativas y barrera de acceso para personas que no piden ayuda de forma presencial.

**Objetivos (medibles):**
| Objetivo | Indicador | Baseline → Meta |
|---|---|---|
| OE1 | Tiempo a primera orientación | 15 min → < 1 min |
| OE2 | Consultas con señal de riesgo derivadas | 60% → ≥ 90% |
| OE3 | Consultas informativas resueltas sin humano | → ≥ 80% |
| OE4 | Respuestas coherentes con fuentes recuperadas | → ≥ 95% (evidencia §5: 100% en 6 casos) |

**Motivación técnica.** El lenguaje emocional es libre y variado (LLM), los datos de apoyo deben ser oficiales y trazables (RAG), y la actuación debe cambiar según la situación (agente con herramientas).

## 2. Formulación de prompts (IE2)

Prompt de sistema por bloques (`src/prompts.py`): **rol y límites** (no diagnostica), **anclaje en fuentes** (responder solo con los `[FUENTE:...]`), **tono** (validación emocional) y **formato** (≤150 palabras + fuentes consultadas). Prompt de usuario = mensaje + salidas de las herramientas ejecutadas como único material factual.

[**CUADRO 2: REDACTAR PROPIO** — tabla comparando una versión del prompt sin bloques vs. la optimizada y qué defectos corrige (p. ej. ambigüedad de rol, riesgo de inventar teléfonos).]

## 3. Diseño e implementación del pipeline RAG (IE3)

- **Corpus (6 documentos):** guía MINSAL salud mental, Línea 4141, Salud Responde, directorio de recursos/emergencias, protocolo institucional de riesgo, guía de acompañamiento (`datos/`).
- **Fuentes internas vs. externas:**

| Tipo | Documentos | Rol en el RAG |
|---|---|---|
| Internas (institucionales, simuladas) | `05_protocolo_institucional_riesgo.md`, `06_guia_acompanamiento_emocional.md` | Protocolos y criterios de acompañamiento propios de la Fundación |
| Externas (oficiales, citadas) | `01_guia_minsal_salud_mental.md`, `02_linea_4141_prevencion_suicidio.md`, `03_salud_responde.md`, `04_recursos_derivacion_y_emergencias.md` | Red pública, líneas de ayuda y recursos verificados |
- **Ingesta** (`src/ingesta.py`): fragmentación por párrafos y encabezados (≤900 caracteres), 80 trozos.
- **Embeddings:** all-MiniLM-L6-v2 vía fastembed (ONNX); respaldo TF-IDF.
- **Recuperación** (`src/rag.py`): similitud coseno, top-k=3, con metadatos de fuente y puntaje.
- **Flujo:** ingesta → índice vectorial → herramienta `recuperar_guia_institucional` → contexto del LLM.

[**FIGURA RAG**: incluir aquí el diagrama de flujo del pipeline. Pueden exportar PNG desde `informe/arquitectura.mmd` en mermaid.live.]

[**CUADRO 3: REDACTAR PROPIO** — justificación del top-k, del tamaño de trozo y del modelo de embeddings en relación con los objetivos.]

## 4. Arquitectura de la solución (IE4)

Componentes: **API** (FastAPI, `POST /chat`) → **Agente orquestador** (`src/agente.py`) que clasifica intención/riesgo (módulo de detección) y **decide las herramientas** a ejecutar → **Herramientas** (RAG, líneas de ayuda, protocolo de riesgo, apoyo) → **LLM** (Groq, llama/gpt-oss; configurable Ollama). Todo el ciclo entrega **trazabilidad**: intención, riesgo, herramientas usadas, fuentes y similitud.

[**FIGURA ARQUITECTURA**: pegar PNG exportado de `informe/arquitectura_componentes.mmd`.]

[**CUADRO 4: REDACTAR PROPIO** — ¿por qué la decisión de herramientas es por reglas auditables en vez de solo LLM? (seguridad y reproducibilidad en contexto de salud) y qué rol cumple el LLM.]

## 5. Evidencia: coherencia entre datos recuperados y respuestas (IE6)

`pruebas/test_pipeline.py` (6 casos) y `pruebas/run_evidencia.py` (LLM real, Groq). Resultado de coherencia: **6/6 (100%)** — ver `pruebas/evidencia/coherencia.md`.

| Caso | Intención | Riesgo | Protocolo | Herramientas | Coherente |
|---|---|---|---|---|---|
| "no quiero seguir viviendo" | riesgo | alto | SÍ | protocolo → líneas → RAG | ✅ |
| "estoy desesperado…" | crisis | moderado | no | líneas → recursos → RAG | ✅ |
| "llevo semanas sin hablar con nadie" | aislamiento | ninguno | no | RAG → apoyo → recursos | ✅ |
| "¿tengo depresión?" | diagnostico | ninguno | no | RAG → apoyo | ✅ |
| "¿qué es el aislamiento social?" | informativo | ninguno | no | RAG | ✅ |
| "gracias, solo quería desahogarme" | apoyo | ninguno | no | apoyo → RAG | ✅ |

Ejemplo: en *"no quiero seguir viviendo"* el RAG recuperó `02_linea_4141_prevencion_suicidio.md` y `05_protocolo_institucional_riesgo.md` (sim 0.64/0.62), el agente activó el protocolo y la respuesta cita WhatsApp 4141 (24/7, gratuito) y Salud Responde 600 360 7777. La coherencia se midió verificando que las señales esperadas (recursos, prohibición de diagnóstico, tono de validación) aparecen en la respuesta generada.

## 6. Conclusiones y reflexión individual — [REDACTAR SIN IA]

[**OBLIGATORIO** — Cada integrante debe redactar aquí, sin apoyo de IA: qué se logró respecto a los objetivos, lecciones, limitaciones y su aporte personal al proyecto. Dos reflexiones diferenciadas.]

## 7. Declaración de uso de IA (obligatorio)

Se utilizó IA como asistente de implementación (generación de código, diagramas y estructura de documentos). **Las justificaciones técnicas, conclusiones y reflexiones de esta sección fueron revisadas y son propias del equipo.** Herramientas: [LISTA].

## Referencias (APA)

1. Ministerio de Salud de Chile (2026). *Salud mental: planes y programas*. https://www.minsal.cl/salud-mental/
2. Ministerio de Salud de Chile. (s. f.). *Salud Responde* (600 360 7777). https://saludresponde.minsal.cl/
3. Línea de Prevención del Suicidio 4141. (2026). *Prevención del suicidio en Chile*. https://prevenciondelsuicidio.cl/
4. Organización Mundial de la Salud. (2022). *Informe mundial sobre la salud mental*. OMS.
5. Duoc UC. (2026). *Lineamientos de uso de inteligencia artificial*. https://bibliotecas.duoc.cl/ia

---

**Nota de formato:** máximo 5 páginas, Word o PDF, citación APA. Exportar los diagramas `.mmd` como PNG (mermaid.live) e insertar las figuras.