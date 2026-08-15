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

### 3. Verificación con API real — PENDIENTE (bloqueada por GEO-BLOQUEO, no por keys)
- `GET /models` y chat completions contra `api.groq.com` devuelven **HTTP 403 Forbidden** con ambas keys (`.groq_api_key` y `GROQ_API_KEY` de `.env`, distintas entre sí).
- **CAUSA RAÍZ (2026-08-15):** bloqueo geográfico. La IP real del workspace está en **Venezuela (VE)** (ipinfo: 38.74.253.102, Cumaná), región NO soportada por Groq/OpenAI.
- Evidencia: OpenAI devuelve `403 unsupported_country_region_territory` para `gpt-4o-mini` con la key nueva (key válida, región bloqueada). El mismo bloqueo aplica a Groq. Las keys NO están revocadas — simplemente se rechaza la petición por país.
- El usuario confirmó que para acceder a las páginas de Groq y OpenAI necesita VPN (consistente con el geo-bloqueo).
- **Conclusión operativa:** los backends directos `groq`/`openai` NO funcionan desde VE sin VPN en toda la máquina. El gateway accesible es **OpenRouter** (prueba 200 OK).

### 4. Verificación alternativa por OpenRouter — COMPLETADA ✔ (2026-08-15)
- Con `OPENROUTER_API_KEY` se probaron los 3 modelos en `https://openrouter.ai/api/v1/chat/completions`:
  - `openai/gpt-oss-20b` → **OK** (provider SiliconFlow)
  - `qwen/qwen3.6-27b` → **OK** (provider Morph)
  - `openai/gpt-oss-120b` → **OK** (provider DeepInfra)
- **Ojo importante:** son **modelos de razonamiento** — gastan tokens de salida en "thinking" antes del `content`. Con `max_tokens=10` devuelven `content: null` (todo el presupuesto fue a reasoning: 34-98 tokens en una respuesta trivial). Usar `max_output_tokens`/`max_tokens` holgados.

### 5. Mapa de conectividad desde VE (2026-08-15)
| Backend | Prueba | Estado desde VE |
|---|---|---|
| Groq (`api.groq.com`) | GET /models | ❌ 403 geo-bloqueo |
| OpenAI (`api.openai.com`) | gpt-4o-mini | ❌ 403 `unsupported_country_region_territory` |
| Gemini (`generativelanguage.googleapis.com`) | GET /models | ✅ 200 |
| OpenRouter (`openrouter.ai`) | chat completions | ✅ 200 |
| HuggingFace / Telegram | (uso previo) | ✅ OK |

→ Estrategia: Gemini y OpenRouter funcionan sin VPN. Los flujos con backend `groq`/`openai` deben ir por OpenRouter (o VPN a nivel máquina).

### 6. OpenRouter como backend por defecto — APLICADO (2026-08-15)
- Decisión del usuario: cambiar los flujos que default a `groq` para que default a `openrouter` (funciona sin VPN desde VE; sirve los mismos modelos GPT-OSS/Qwen3.6).
- Archivos editados (default `groq` → `openrouter`):
  - `flujo_elaborar_examen.py:334`
  - `flujo_elaborar_ejercicios.py:270`
  - `execution/elaborar_examen.py:469`
  - `mcp_elaborar_server.py:21,35`
- Verificado: `py_compile` OK y `--help` muestra `(default: openrouter)`.
- Sin cambio: flujos con default `gemini` (funciona desde VE): `flujo_analizar_imagen`, `flujo_evaluar_examen`, `flujo_imagen_a_kicad`, `execution/evaluar_examen`, `execution/analizar_imagen`, `execution/extraer_netlist_imagen`, `execution/elaborar_ejercicios`, `execution/generar_kicad_llm`.

## Estado (2026-08-15)
- Migración de modelos Groq: **COMPLETA y commiteada** (`c672c27`).
- OpenRouter como backend por defecto en flujos de elaboración: aplicado (este commit).
- Verificación OpenRouter de los 3 modelos: completada.

## Pendientes
- [ ] **`rag_system.py` y `agent_eda.py`** usan `ChatGroq` DIRECTO (sin `--api-backend`): seguirán fallando desde VE sin VPN. Evaluar migrarlos a OpenRouter (ChatOpenAI con `base_url=https://openrouter.ai/api/v1`) o dejarlos para uso con VPN.