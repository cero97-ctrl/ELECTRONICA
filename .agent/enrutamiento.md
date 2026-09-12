# Política de Enrutamiento Multi-LLM (Orquestador: opencode, decisión DETERMINISTA)

Archivo auto-cargado por `opencode.json` (`instructions: [".agent/*.md"]`). Define cómo
debes clasificar cada requerimiento y enrutarlo a un modelo via OpenRouter. Referencia
completa: `docs/ARQUITECTURA_ENRUTAMIENTO_LLM/arquitectura_enrutamiento_llm.md` y
`directives/enrutamiento_llm.yaml`.

## Principio rector: decisiones DETERMINISTAS, no probabilísticas

La elección de tier/modelo NO la tomas tú razonando en el chat: la toma
**`execution/enrutador.py`** con reglas puras (umbrales de tokens, vocabulario
controlado de tipos de tarea, criticidad). Tu único trabajo es:

1. Extraer el **descriptor estructurado** de la petición (tipo de tarea, tamaño de
   entrada, criticidad, visión) — esto es parsing de intención, no decisión.
2. Invocar `python3 execution/enrutador.py <descriptor>` y usar la salida.
3. Ejecutar el script de `execution/` con `--api-backend openrouter --modelo <id>`.

El mismo descriptor SIEMPRE produce el mismo resultado. No hay "me parece que",
"este es complejo" ni criterio subjetivo: la matriz vive en código, no en tu contexto.

## Cómo extraer el descriptor (lo único no-determinista, y es parsing, no decisión)

Del requerimiento del usuario identifica:

- `--task`: uno de los tipos del vocabulario controlado (ver `execution/enrutador.py`):
  - rutina: `formateo, parsing, sintaxis, validacion, resumen, rag, multimodal, extraccion, conversion`
  - contexto/síntesis: `contexto_masivo, multi_archivo, destilacion, sintesis_logs, auditoria, razonamiento_intermedio`
  - crítico: `arquitectura, calculo_formal, debug, examen, examen_complejo, netlist, kicad, refactor, diseño`
- `--tokens N`: medido (no estimado por criterio). Si la entrada son archivos, pasa
  `--archivos <rutas>` para que el enrutador los mida él mismo.
- `--critico`: `true` si la tarea es de alto impacto (compilar, pagar, evaluar a alumnos, producción).
- `--vision`: `true` si hay imágenes/PDFs.
- `--modelo-explicito <id>`: si el usuario nombró un modelo, respetarlo (override total).

## Niveles (fuente única de IDs: `execution/llm_client.py` → `MODEL_TIERS`)

| Nivel | ID OpenRouter | Costo (USD/M tok) | Uso típico |
| :--- | :--- | :--- | :--- |
| **flash** | `google/gemini-3.7-flash` | bajo | Rutina: parsing/formatting JSON-YAML, resúmenes, RAG, validación sintáctica, multimodal rápido |
| **deepseek** | `deepseek/deepseek-v4.1-flash` | $0.15 / $0.60 | Contexto masivo (>50k tok), lectura multi-archivo/repositorio, síntesis de datasheets/logs, razonamiento intermedio (1M ctx, JSON mode). V4 Pro discontinuado (2026-09-14) sustituido por V4.1 Flash |
| **glm** | `z-ai/glm-5.2` | ~$1 / $3 | Respaldo del tier medio (1M ctx, razonamiento) |
| **opus** | `anthropic/claude-opus-5` | $5 / $25 | Diseño arquitectónico, cálculo formal, debugging profundo, exámenes/evaluación compleja, netlists/EasyEDA |

> **Kimi K3 (`moonshotai/kimi-k3`) NO se enruta automáticamente.** Es propenso a 429 de
> capacidad (upstream Moonshot, sin mitigación posible) y su costo ($2.9/$14) es casi de
> nivel premium. Está disponible SOLO por petición explícita del usuario, vía
> `--modelo-explicito moonshotai/kimi-k3` (`MODELOS_OPCIONALES` en `llm_client.py`).

## Reglas de decisión (implementadas en `execution/enrutador.py`, NO en este chat)

1. **Modelo explícito** del usuario → se respeta tal cual (sin clasificar).
2. **Tokens medidos > 50 000** → tier de contexto masivo (`deepseek`), salvo que la tarea
   sea crítica o de razonamiento crítico → `opus`. Nunca adivines el tamaño: mídilo
   o pásale los archivos al enrutador.
3. **Tipo de tarea** → tier según el vocabulario controlado (flash/deepseek/opus).
4. **`--critico`** → escala a `opus` aunque el tipo sea de rutina.

## Fallback (determinista y cost-aware, del enrutador)

Ante 429 o errores repetidos, escala en cadena sin re-decidir el destino:

- `flash` → `deepseek` → `glm`
- `deepseek` → `glm` → `opus`
- `opus` → `deepseek` → `glm`

Máximo 3 intentos totales; si todos fallan, detener y reportar. La escalada NO se
hace por calidad percibida: solo por fallo de servicio.

## Mapa script → nivel por defecto (default del script, el enrutador puede sobreescribirlo)

| Script / flujo | Nivel default |
| :--- | :--- |
| `rag_system.py` (RAG, embeddings+chat) | flash |
| `execution/analizar_imagen.py`, `execution/evaluar_examen.py`, `execution/extraer_netlist_imagen.py`, `execution/data_capture.py` | flash (multimodal/rutina) |
| `execution/elaborar_examen.py`, `execution/elaborar_ejercicios.py`, `execution/generar_kicad_llm.py`, `agent_eda.py` | opus |
| Cualquier tarea de contexto masivo (logs, repos, datasheets) | deepseek |

## Qué consume créditos OpenRouter y qué no

Principio: el **chat del orquestador es gratis** — tu motor rota entre modelos Free
(Zen u OpenRouter Free) y NUNCA toca `OPENROUTER_API_KEY`. Los créditos se descuentan
ÚNICAMENTE cuando un script de `execution/` llama a `openrouter_chat` de
`execution/llm_client.py`. Tareas típicas y su consumo:

| Instrucción del usuario | ¿Créditos? | Por qué |
| :--- | :--- | :--- |
| Editar/crear archivos, compilar LaTeX, git, diagnóstico de sistema, scraping determinista, cualquier trabajo tuyo en el chat | **No** | Orquestación pura; el motor del asistente rota entre modelos Free |
| `python3 execution/enrutador.py ...` | **No** | Decisión 100% local y determinista ($0); solo decide, no llama a ninguna API |
| `flujo_elaborar_examen.py` / `flujo_elaborar_ejercicios.py` | **Sí** | Default openrouter + tier opus ($5/$25 M tok) — la combinación más cara |
| `flujo_evaluar_examen.py`, `rag_system.py`, `agent_eda.py`, `extraer_netlist_imagen.py`, `generar_kicad_llm.py` | **Sí** | Llamadas vía `openrouter_chat` |
| `flujo_analizar_imagen.py` | Solo con `--api-backend openrouter` | Default es Gemini free tier (20 req/día/modelo); con openrouter consume créditos |
| `flujo_sync_faq_flujo.py` | Solo con cambios estructurales (re-traducción LLM quirúrgica) | Campos deterministas/hash → **No**; re-traducción semántica → **Sí** vía enrutador (flash default, `--critico` → opus). `--no-llm` evita créditos y aborta si el cambio es estructural |
| Cualquier flujo LLM con `--api-backend gemini` | **No** | Corre dentro de la cuota free de Gemini (20 req/día/modelo), con menor calidad/estabilidad en tareas críticas |

Regla práctica para decidir si avisar al usuario sobre costo: mira el comando que vas a
ejecutar. Si lleva `--api-backend openrouter` (o su default lo trae), avisa antes;
si es edición/compilación/diagnóstico o backend gemini, corre sin avisar.

Verificación: saldo puntual con `execution/monitor_saldo_openrouter.py`; decisiones
enrutadas (no gasto real) en `.tmp/routing_log.jsonl`.

## Restricciones

- **Geo VE:** Groq/OpenAI directos devuelven 403 (solo con VPN). Usar siempre OpenRouter
  o Gemini. Todos los IDs de este archivo funcionan vía OpenRouter sin VPN.
- **`max_tokens` obligatorio:** respetar `OPENROUTER_MAX_TOKENS` del `.env` (default 2048,
  activo 8192). Sin `max_tokens`, OpenRouter pide 65536 y con saldo bajo devuelve 402.
- **Kimi K3 (razonamiento):** no soporta el rol `developer`; usar `system`/`user`.
  El límite de salida se pasa como `max_completion_tokens`. Consume tokens de salida en
  razonamiento *always-on*: mantener `max_tokens` acotado.
- **JSON estructurado:** para extraer respuestas JSON del LLM usar el algoritmo de llaves
  balanceadas (`_find_balanced_json`, ver `.agent/python.md`), nunca regex non-greedy.
- **Telemetría:** cada decisión se registra en `.tmp/routing_log.jsonl` (tier, tokens,
  modelo, timestamp). Usarla para afinar umbrales; no afines la política a ojo.
- **Saldo OpenRouter:** vigilar con `python execution/monitor_saldo_openrouter.py`; cerca
  del auto top-up de $5 (cuando el saldo baja de $3), priorizar tiers baratos (flash/deepseek) y evitar opus para no agotar saldo.

## Delegación a subagentes (multi-proveedor estilo dsh)

Inspirado en el seam `ctx.subagents` + `tool-subagent` de dsh (un contrato, muchos
proveedores), ELECTRONICA puede delegar subtareas a subagentes opencode especializados:

- **Decisión determinista:** `python3 execution/enrutador.py --delegacion <descriptor>`
  devuelve además `subagent` y `delegacion_reason`. Mapeo fijo en código (`SUBAGENTS`):
  `flash → sub-rutina`, `deepseek → sub-sintesis`, `opus → sub-critico`. Con
  `--modelo-explicito` el subagente sale `null` (elección del orquestador; solo el
  modelo es override).
- **Subagentes (`.opencode/agents/`):** agentes opencode SIN modelo fijo → heredan el
  motor rotativo del asistente y **no consumen créditos OpenRouter**. La especialización
  es por persona y permisos: `sub-rutina` (lectura, sin edición), `sub-sintesis`
  (lectura masiva + edición), `sub-critico` (razonamiento + edición). Requieren
  reinicio de opencode tras crearlos/editarlos.
- **Flujo:** extraer descriptor → `enrutador.py --delegacion` → registrar
  `delegacion/decidida` (sesion_log.py) → Task tool (`subagent_type = <subagent>`) →
  validar → registrar `delegacion/resultado`. SOP completo:
  `directives/delegacion_subagentes.yaml`.
- **Fallback:** mismo retry budget (máx 3) y mismas cadenas cost-aware del router; no
  se cambia de subagente por calidad de salida, solo por fallo de servicio.

## Refinamiento (ver `directives/enrutamiento_llm.yaml` → `refinement_protocol`)

Al resolver problemas reales, perfecciona el flujo así: hallazgo → Sessions/ + telemetría
(`.tmp/routing_log.jsonl`) → causa raíz → cambio en `execution/enrutador.py`/directiva →
verificación (pruebas + determinismo) → commit. El determinismo es inviolable: el mismo
descriptor SIEMPRE produce el mismo tier; los umbrales se afinan con evidencia, no a ojo.