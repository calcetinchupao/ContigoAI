# Configurar el LLM para ContigoAI

ContigoAI necesita un LLM para generar las respuestas. Las respuestas siempre
están **ancladas en el RAG**: el modelo no inventa, solo redacta con base en
los fragmentos y herramientas que le entrega el agente.

## Opción A — Groq (recomendada)

Capa gratuita, rápida, no requiere tarjeta de crédito.

1. Entra a https://console.groq.com/keys y crea una cuenta (email o Google).
2. Clic en **Create API Key** → copia la clave.
3. Edita `.env` (copiado desde `.env.example`):

   ```env
   LLM_PROVIDER=groq
   GROQ_API_KEY=tu_clave_aqui
   GROQ_MODEL=llama-3.1-8b-instant
   ```

   Modelos gratis disponibles: `llama-3.1-8b-instant`, `llama-3.3-70b-versatile`,
   `openai/gpt-oss-120b`.

## Opción B — Ollama (local, 100% gratis, sin key)

1. Instalar desde https://ollama.com
2. `ollama pull llama3.2`
3. En `.env`:

   ```env
   LLM_PROVIDER=ollama
   OLLAMA_MODEL=llama3.2
   ```

## Opción C — OpenAI / proveedor compatible

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

## Verificar

```bash
python src/agente.py
```

Escribe una consulta (p. ej. *"no quiero seguir viviendo"*) y observa la
decisión del agente (intención, riesgo, herramientas) y la respuesta con
fuentes citadas.

> **Nota de seguridad:** la API key vive en `.env`, que está en `.gitignore`.
> Nunca subas tu clave al repositorio.