# Informe Técnico ContigoAI (estructura, máx 5 páginas)

> **Importante (rubrica):** el informe debe ser de máx. 5 páginas con citación
> APA. Este documento es el **esquema**; las justificaciones técnicas,
> conclusiones y reflexiones personales deben ser redactadas por ustedes.

## 1. Análisis del caso organizacional (IE1)
- Organización: Fundación Contigo (ONG ficticia inspirada en servicios reales).
- Problema: cobertura limitada de la línea de apoyo, derivaciones irregulares,
  saturación con consultas informativas, barrera de acceso.
- Objetivos: OE1–OE4 (ver `caso/01_propuesta_de_caso.md`).
- Por qué IA: escala 24/7, lenguaje libre y empático, trazabilidad de datos.

## 2. Formulación de prompts (IE2)
- Prompt de sistema por bloques (rol / límites / anclaje RAG / tono / formato).
  Ver `src/prompts.py`.
- Prompt de usuario: mensaje + salidas de herramientas como único material factual.
- Justificación: bloques separados reducen ambigüedad (análisis propio del equipo).

## 3. Diseño e implementación del pipeline RAG (IE3)
- Corpus: 6 documentos (`datos/`): MINSAL, Línea 4141, Salud Responde, recursos,
  protocolo institucional, guía de acompañamiento.
- Ingesta: fragmentación por párrafos/encabezados (máx. 900 caracteres).
- Embeddings: all-MiniLM-L6-v2 (fastembed) → índice numpy. Respaldo TF-IDF.
- Recuperación: similitud coseno, top-k = 4, con metadatos de fuente.
- Flujo: `src/ingesta.py` → `src/rag.py` → herramienta `recuperar_guia_institucional`.

## 4. Arquitectura de la solución (IE4)
- Diagrama Mermaid (`informe/arquitectura.mmd`).
- Componentes: API (FastAPI) · Agente orquestador · Herramientas · RAG ·
  LLM (Groq/Ollama) · Fuentes de datos.
- Tabla de componentes y responsabilidades.

## 5. Evidencia: coherencia datos ↔ respuestas (IE6)
- Matriz de casos de prueba (`pruebas/test_pipeline.py`, 6 casos).
- Comparación entre fragmentos recuperados (similitud) y frases clave de la
  respuesta → tabla de coherencia.
- Resultados de ejecución (logs). _Se completa cuando se configure el LLM._

## 6. Conclusiones (redacción PROPIA, sin IA)
- Resultados vs. objetivos medibles.
- Limitaciones (LLM no configurado en algunos escenarios, corpus simulado).
- **Reflexión personal de cada integrante (obligatoria, escrita sin IA).**

## 7. Referencias (APA)
- MINSAL, Salud Responde, Línea 4141, prevenciondelsuicidio.cl, bibliotecas.duoc.cl/ia

## Sección de IA (obligatoria)
- Declarar qué herramientas de IA se usaron (v. gr. asistente de código para
  implementación, generación de diagramas) y citarlas.