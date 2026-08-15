# Sesión: Migración por decomisión de modelos Groq (Llama 3.3 70B / 3.1 8B)

**Fecha:** 2026-08-15
**Agente:** DeepSeek (opencode)

## Tema tratado
Notificación por correo de Groq: decomisión de `llama-3.3-70b-versatile` y `llama-3.1-8b-instant` el **16/08/2026** (PDF en `docs/GROQ/GROQ.pdf`). Migración de los flujos del workspace a los modelos recomendados.

## Decisión de reemplazo (según docs de deprecación de Groq)
- `llama-3.1-8b-instant` → `openai/gpt-oss-20b`
- `llama-3.3-70b-versatile` → `qwen/qwen3.6-27b` (elegido por el usuario; consistente con agent_eda y generadores; alternativa documentada: `openai/gpt-oss-120b`)

## Actividades realizadas

### 1. Diagnóstico de impacto
- Referencias activas al modelo deprecado encontradas y migradas.
- Ya estaban correctos: `agent_eda.py` (primario `qwen/qwen3.6-27b`), generadores de examen/ejercicios (`qwen/qwen3.6-27b` vía OpenRouter), fallback OpenRouter `meta-llama/llama-3.3-70b-instruct:free` (no es Groq).
- `.tmp/*.json` conservan metadata histórica del modelo (sin acción).

### 2. Ediciones aplicadas
- `rag_system.py:131` → `ChatGroq(model="openai/gpt-oss-20b")`
- `rag_system.py:191` → etiqueta de captura `"openai/gpt-oss-20b"`
- `agent_eda.py:57` → fallback `openai/gpt-oss-20b`
- `execution/data_capture.py:26,341` → `"openai/gpt-oss-20b"`
- `Proyectos/SOLANA/x402_service/app/config.py:72` → default `"qwen/qwen3.6-27b"`
- Todos compilan (`python3 -m py_compile`).

### 3. Verificación con API real — PENDIENTE (bloqueada, en pausa)
- `GET /models` y chat completions contra `api.groq.com` devuelven **HTTP 403 Forbidden** con ambas keys (`.groq_api_key` y `GROQ_API_KEY` de `.env`, distintas entre sí).
- TLS/red OK; el bloqueo es de cuenta: keys revocadas/inválidas o cuenta bloqueada.
- Re-ejecutada la prueba de `openai/gpt-oss-20b`, `qwen/qwen3.6-27b`, `openai/gpt-oss-120b` en dos ocasiones tras el diagnóstico → sigue **403 Forbidden** con ambas keys. El usuario sospecha un problema en la página/cuenta de Groq; se decidió **pausar la verificación** hasta que Groq lo resuelva.
- **Acción al regresar:** confirmar que la key responde (recomendado regenerarla en https://console.groq.com/keys y actualizar `.groq_api_key`/`.env` si sigue fallando), luego re-ejecutar la verificación de los 3 modelos.

## Estado al pausar (2026-08-15)
- Migración de código: **COMPLETA y commiteada** (`c672c27`, rama `master`).
- Commit incluye: 4 archivos migrados + `Sessions/2026-08-15_migracion_groq_decomision_llama.md` + `docs/GROQ/GROQ.pdf` (correo original).
- Única tarea pendiente: verificación en vivo de modelos con la API de Groq.

## Pendientes
- [ ] Cuando Groq arregle el 403: verificar `openai/gpt-oss-20b`, `qwen/qwen3.6-27b`, `openai/gpt-oss-120b` con llamada real (script: POST a `https://api.groq.com/openai/v1/chat/completions` con `messages=[{role:user, content:"Responde SOLO con: OK"}]`, `max_tokens=10`).