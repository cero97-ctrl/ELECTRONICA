# Sesión: Migración por decomisión de modelos Groq (Llama 3.3 70B / 3.1 8B)

**Fecha:** 2026-08-15 (continuada 2026-08-16)
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

### 7. Migración de `rag_system.py` y `agent_eda.py` a OpenRouter — APLICADO (2026-08-15)
- **`rag_system.py`**: import `ChatGroq` → `ChatOpenAI` (`langchain_openai`); carga la key desde `.env` (`OPENROUTER_API_KEY` vía `load_dotenv`) en vez de `.groq_api_key`; `llm = ChatOpenAI(model="openai/gpt-oss-20b", temperature=0, max_tokens=2048, base_url="https://openrouter.ai/api/v1")`.
- **`agent_eda.py`**: `initialize_llm()` crea `ChatOpenAI` con **`openai/gpt-oss-20b` (primario)** y `qwen/qwen3.6-27b` (respaldo), ambos con `max_tokens=2048` y `base_url` de OpenRouter; mensajes de retry/error genéricos.
- **Entorno:** el código corre en conda `elect_env` (tiene `langchain_openai`). `py_compile` OK.
- **Aprendizajes clave:**
  - **Sin `max_tokens` explícito, ChatOpenAI pide 65536** y OpenRouter rechaza con 402 cuando el saldo es bajo → fijar `max_tokens` siempre.
  - **`qwen/qwen3.6-27b` es un modelo de razonamiento que devuelve su cadena de pensamiento como `content`** (y con presupuesto corto deja `content=""`), lo que rompe la extracción JSON. **`openai/gpt-oss-20b` separa el razonamiento del JSON final** → es el modelo fiable para extracción estructurada (por eso es el primario).
  - `meta-llama/llama-3.3-70b-instruct:free` ya no es gratis en OpenRouter (404).
- **`max_tokens` ahora configurable** vía `OPENROUTER_MAX_TOKENS` en `.env`/entorno (default 2048, tier gratuito; subir a 4096-8192 tras recargar créditos). Aplicado en `agent_eda.py` y `rag_system.py`.

### 8. Créditos de OpenRouter — key nueva y verificación FINAL (2026-08-15)
- El usuario generó una **nueva `OPENROUTER_API_KEY`** en `.env`. Sigue en tier limitado: con `max_tokens=4096` devuelve **402** ("can only afford ~2,000 tokens"). Con `max_tokens ≤ 2048` las peticiones pasan.
- **`agent_eda` VERIFICADO end-to-end ✔** con `openai/gpt-oss-20b` + `max_tokens=2048`: extrajo netlist válido de un circuito RC+V (R1 10k, C1 100uF, V1 5V) con esquema correcto (id/type/value/lcspart/x/y) y conexiones, en ~7 s.
- `rag_system`: LLM verificado (mismo patrón ChatOpenAI + gpt-oss-20b funciona). El arranque interactivo es lento por el glob `**/*.{tex,md,pdf}` sobre el workspace grande (comportamiento preexistente, no de la migración); se cortó por timeout sin llegar al chat.
- Para producción con presupuestos mayores: recargar créditos en https://openrouter.ai/settings/credits.

### 9. Recarga de créditos OpenRouter — decisión de pagar con cripto (2026-08-15)
- `max_tokens` **configurable vía `OPENROUTER_MAX_TOKENS`** (default 2048; subir tras recargar) — commiteado en `b91eb5f` (`agent_eda.py` y `rag_system.py`).
- **Tarjeta BDV Internacional:** se intentó por Stripe (método tarjeta). No se confirmó que funcione; alto riesgo de rechazo porque **Venezuela está bajo sanciones OFAC y Stripe no lista VE** como país de facturación. El usuario decidió pagar con cripto.
- **Wallets:** el usuario creó **Rabby**. Nota clave: **Rabby es solo EVM** (no soporta Solana). Para desarrollo Solana a futuro → Phantom/Backpack + CLI de Solana. Rabby sí sirve para el pago USDC EVM.
- **Investigación de pago cripto de OpenRouter** (docs/FAQ 2026):
  - Procesador: **Coinbase Commerce** (checkout con QR por wallet: MetaMask, Base Pay, Phantom, Trust Wallet, Rabby, Rainbow, OKX, Other wallets). **El QR elegido define la red del pago.**
  - **Solo USDC**; comisión del **5%** al comprar; **no reembolsable**; mínimo **$5** por transacción (máx $25k). El checkout muestra monto total = USDC + 5%.
  - **Redes soportadas (mainnet): Ethereum, Polygon y Base** (Base recomendada por tarifas casi nulas). Cualquier otra red (Avalanche, Optimism, Solana, Stellar, Tron) → fondos perdidos.
- **Ruta elegida por el usuario (la más larga pero viable con sus opciones):**
  **AirTM (comprar USDC) → Binance (vía Binance Pay, envío interno sin red) → OpenRouter (retiro USDC por red Base, QR "Base Pay")**.
  - Motivo: AirTM solo ofrece USDC (Ethereum) de las redes soportadas por OpenRouter; Binance permite salir por **Base** (barato/rápido). Alternativa más corta: AirTM→USDC(Ethereum) directo al checkout, pero el gas ETH es caro.
  - Pasos: en OpenRouter elegir QR **"Base Pay"** → copiar dirección de depósito (red Base) → Binance retirar USDC red **Base** → pegar dirección → confirmar.
  - Regla de oro: **la red del checkout debe coincidir exactamente con la red del envío**; verificar antes de firmar. En Binance, los USDC vía Binance Pay llegan a la wallet Pay/Funding (posible transferencia interna antes de retirar).
- **ACTUALIZACIÓN de plan (mismo día):** el usuario **agregó como método de pago una tarjeta recargable en USD del Banco Bancamiga** (banco con sede en su ciudad) en OpenRouter. **Depositará ≥ $15 mañana en taquilla** y pagará los créditos con la tarjeta (vía Stripe). Si Stripe la rechaza por país de facturación (VE sancionado), se cae a la ruta cripto ya definida.
- **RECARGA COMPLETADA ✔ (2026-08-16):** depósito de $15 en la tarjeta TDD recargable de Bancamiga y compra de créditos en OpenRouter (auto top-up 10/$5 activo). Saldo resultante: **$9.82** (deducido el saldo negativo previo de -$0.18). **La tarjeta de Bancamiga SÍ fue aceptada por Stripe.**
- **Verificación de tier pago (2026-08-16):**
  - `GET /api/v1/auth/key` → `is_free_tier: false`, `limit: null` (sin tope de presupuesto por petición), `usage_monthly: $0.017`.
  - `chat/completions` con `openai/gpt-oss-20b` y `max_tokens=8192` → `finish_reason: stop`, `content: OK`, costo $0.000009. Sin 402.
  - **`agent_eda` re-verificado end-to-end ✔** con el nuevo presupuesto: extrajo 5 resistencias (R1 5Ω, R2/R3 20Ω, R4 15Ω, R5 2.5Ω) con LCSC y generó JSON EasyEDA válido (shape[]: 5 LIB, 7 W, 3 N, 2 J).
- **`OPENROUTER_MAX_TOKENS=8192` activado** en `.env` (default 2048 en el código se mantiene como mínimo seguro).

## Estado (2026-08-16)
- Migración de modelos Groq: **COMPLETA y commiteada** (`c672c27`).
- OpenRouter como backend por defecto en flujos de elaboración: aplicado.
- `rag_system.py` y `agent_eda.py` migrados a OpenRouter: aplicado (este commit) con `gpt-oss-20b`/`max_tokens=2048`.
- `max_tokens` configurable (`OPENROUTER_MAX_TOKENS`): commiteado (`b91eb5f`).
- Verificación funcional: `agent_eda` end-to-end OK; `rag_system` LLM OK (arranque lento preexistente).
- **Recarga de créditos: COMPLETADA ✔** — saldo $9.82, tier pago activo, tarjeta Bancamiga aceptada por Stripe, auto top-up 10/$5 activo.
- **`OPENROUTER_MAX_TOKENS=8192` activado** en `.env` y verificado (petición 8192 OK, `agent_eda` end-to-end OK con JSON EasyEDA válido).

## Pendientes
- [x] Recargar créditos de OpenRouter (tarjeta Bancamiga, auto top-up 10/$5) — **completado 2026-08-16**, saldo $9.82.
- [x] Activar `OPENROUTER_MAX_TOKENS=8192` y verificar presupuesto alto — **completado 2026-08-16**.
- [ ] Monitorear el gasto: $9.82 alcanza para ~1000+ peticiones de netlist (costo ~$0.009 c/u); auto top-up repondrá $10 al bajar de $5.
- [ ] Revisar si los QR de Phantom (Solana) en el checkout implican que OpenRouter ya acepta USDC en Solana (si aplica, abarataría recargas futuras desde AirTM Solana).
- [ ] El resto de flujos con backend `gemini` quedan OK (funciona desde VE sin VPN).