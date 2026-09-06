# Propuesta de Caso Organizacional — ContigoAI

**Asignatura:** ISY0101 · Ingeniería de Soluciones con IA
**Evaluación Parcial N.º 1:** Diseño de Solución con LLM y RAG
**Equipo:** (completar integrantes)
**Fecha:** 6 de septiembre de 2026

---

## 1. Nombre y breve descripción de la organización

**Fundación Contigo** — Organización **sin fines de lucro** del rubro de **salud mental y apoyo social**, de tamaño pequeño-mediano, con un equipo de profesionales y voluntarios. Opera una **línea de orientación y apoyo emocional** ("Línea Contigo") dirigida a personas en situación de **aislamiento social, soledad o crisis emocional**, especialmente quienes no cuentan con una red de apoyo cercana.

> La organización es **ficticia** por razones de disponibilidad de datos, pero está inspirada en servicios reales chilenos (p. ej. Salud Responde, Fundación para la Prevención del Suicidio, líneas 4141 y *Salud Mental Responde*) y utiliza **exclusivamente fuentes oficiales simuladas o citadas** (MINSAL, guías de salud mental) para el corpus de RAG.

## 2. Identificación y descripción del problema

La "Línea Contigo" recibe un volumen creciente de consultas (alta demanda por efectos del aislamiento social pospandémico), pero su capacidad de atención humana es limitada:

1. **Tiempos de espera elevados** para obtener una primera orientación: la línea no está disponible 24/7 y colapsa en horarios pico.
2. **Derivación inconsistente**: depende del criterio individual del voluntario; hay casos de **crisis emocional que no reciben derivación oportuna** a recursos profesionales, lo que representa un riesgo real.
3. **Desconocimiento de recursos**: parte importante de las consultas son **informativas** (¿qué es el aislamiento?, ¿dónde puedo pedir ayuda?) que saturan la agenda sin requerir atención humana.
4. **Barrera de acceso**: muchas personas en soledad no escriben por vergüenza o costo, pero sí usarían un canal anónimo e inmediato.

**Impacto actual:** cobertura insuficiente de la población objetivo, derivaciones tardías en contextos de riesgo y desgaste del equipo voluntario.

## 3. Objetivos de la intervención

**Objetivo general:**
Implementar un **agente conversacional (ContigoAI)** que brinde orientación inicial inmediata, detecte señales de riesgo emocional y derive a recursos oficiales chilenos, complementando —sin reemplazar— la atención humana de la Fundación Contigo.

**Objetivos específicos (medibles):**

| # | Objetivo específico | Indicador medible (baseline → meta) |
|---|---------------------|-------------------------------------|
| OE1 | Reducir el tiempo de primera orientación | De ~15 min en horario pico a **< 1 min** de primera respuesta automática (medido con logs de la API) |
| OE2 | Aumentar la derivación oportuna en señales de riesgo | De ~60% de consultas con señal de riesgo derivadas a **≥ 90%**, validando con casos de prueba etiquetados |
| OE3 | Resolver automáticamente consultas informativas | Cubrir **≥ 80%** de las consultas de tipo informativo sin intervención humana |
| OE4 | Garantizar respuestas respaldadas en fuentes oficiales | **≥ 95%** de respuestas coherentes con los fragmentos recuperados por RAG (evaluación manual sobre matriz de casos) |

## 4. Datos disponibles o que se pueden obtener

- **Corpus interno (simulado):** guías y folletos institucionales de la Fundación Contigo sobre acompañamiento, protocolos de riesgo y recursos de derivación. Se simulan porque el sistema se desarrolla fuera de la organización real.
- **Corpus externo (oficial y citado):** documentos públicos de MINSAL sobre salud mental, material oficial de la línea de prevención del suicidio **4141**, información de **Salud Responde** y directorio de centros de atención pública de salud mental en Chile.
- **Datos de operación (simulados):** conjunto de transcripciones anonimizadas de consultas tipo (aislamiento, crisis, riesgo, informativa, solicitud de diagnóstico) utilizadas como **casos de prueba** y para la matriz de coherencia datos↔respuestas.

## 5. Restricciones o requerimientos particulares

1. **No** se diagnostica, no se realiza terapia ni se reemplaza a la atención profesional o a los servicios de emergencia.
2. Ante **señales de riesgo** (p. ej. ideación suicida) se debe **activar un protocolo de seguridad** y orientar a ayuda inmediata (4141, Salud Responde, emergencias 131/133).
3. **Confidencialidad y anonimización** de los datos, en línea con la Ley 19.628 (protección de la vida privada en Chile).
4. Las respuestas deben basarse en **información verificable y oficial**; el modelo no debe inventar recursos ni teléfonos.
5. Idioma español; tono empático, claro y sin tecnicismos innecesarios.

## 6. Motivación para el uso de agentes de IA, LLMs y RAG

- **LLM:** permite comprender lenguaje natural libre y emocional, y generar respuestas empáticas adaptadas a cada caso, algo inviable con flujos de texto reglados.
- **RAG:** garantiza que la información (recursos, teléfonos, protocolos, instituciones) provenga de **documentos oficiales verificables** y no de la "alucinación" del modelo, entregando trazabilidad (fuente por respuesta).
- **Agente:** decide de forma autónoma **qué hacer según la situación** (responder, consultar el corpus, activar protocolo de riesgo, recomendar derivación), integrando herramientas en una sola conversación.

## 7. Referencias o anexos relevantes

- MINSAL — Salud mental: planes y programas. https://www.minsal.cl/salud-mental/
- Salud Responde (línea 600 360 7777).
- Línea de prevención del suicidio **4141** (WhatsApp) y canales oficiales.
- OMS — Salud mental y apoyo psicosocial.
- Bibliotecas DUOC — Lineamientos de uso de IA. https://bibliotecas.duoc.cl/ia