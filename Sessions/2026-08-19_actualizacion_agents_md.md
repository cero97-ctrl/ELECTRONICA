# Sesión: Actualización de AGENTS.md tras migración a OpenRouter

**Fecha:** 2026-08-19
**Agente:** opencode

## Tema tratado
El usuario pidió actualizar `AGENTS.md` si era necesario, tras los cambios de la sesión de migración de Groq a OpenRouter (2026-08-15/16).

## Actividades realizadas
- Revisados `AGENTS.md`, `Sessions/2026-08-15_migracion_groq_decomision_llama.md`, estado git y usos de `.groq_api_key`/OpenRouter en el código.
- Confirmado que AGENTS.md estaba desactualizado respecto a:
  - Backend LLM por defecto (Groq → OpenRouter, geo-bloqueo desde VE).
  - `OPENROUTER_MAX_TOKENS` y `HF_TOKEN` en `.env`.
  - Nuevo script `execution/monitor_saldo_openrouter.py`.

## Ediciones aplicadas (AGENTS.md)
1. **Configuration:** `.groq_api_key` ahora se describe como "fallback provider `groq`"; `.env` incluye `OPENROUTER_MAX_TOKENS` y `HF_TOKEN`.
2. **Know before you act:** nueva bullet sobre geo-bloqueo VE (Groq/OpenAI 403 sin VPN; usar OpenRouter o Gemini; fijar `max_tokens` siempre; `qwen/qwen3.6-27b` rompe extracción JSON).
3. **Commands:** RAG ahora indica LLM vía OpenRouter (`openai/gpt-oss-20b`); agregado comando de `monitor_saldo_openrouter.py` (chequeo puntual y `--watch`).

## Decisiones
- `.groq_api_key` se mantiene documentado porque sigue leyéndose como fallback en `execution/elaborar_examen.py`, `analizar_imagen.py` y `evaluar_examen.py`.

## Pendientes
- Ninguno.