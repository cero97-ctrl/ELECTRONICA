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
| **kimi** | `moonshotai/kimi-k3` | $3 / $15 | Contexto masivo (>50k tok), lectura multi-archivo/repositorio, síntesis de datasheets/logs, razonamiento intermedio |
| **kimi_fallback** | `deepseek/deepseek-v4-pro` | intermedio | Sustituto de kimi ante 429/errores (razonamiento, 1M ctx) |
| **opus** | `anthropic/claude-opus-5` | $5 / $25 | Diseño arquitectónico, cálculo formal, debugging profundo, exámenes/evaluación compleja, netlists/EasyEDA |

## Reglas de decisión (implementadas en `execution/enrutador.py`, NO en este chat)

1. **Modelo explícito** del usuario → se respeta tal cual (sin clasificar).
2. **Tokens medidos > 50 000** → tier de contexto masivo (`kimi`), salvo que la tarea
   sea crítica o de razonamiento crítico → `opus`. Nunca adivines el tamaño: mídilo
   o pásale los archivos al enrutador.
3. **Tipo de tarea** → tier según el vocabulario controlado (flash/kimi/opus).
4. **`--critico`** → escala a `opus` aunque el tipo sea de rutina.

## Fallback (determinista y cost-aware, del enrutador)

Ante 429 o errores repetidos, escala en cadena sin re-decidir el destino:

- `flash` → `kimi` → `kimi_fallback`
- `kimi` → `kimi_fallback` → `opus` (opus solo si el tier original era kimi/opus)
- `opus` → `kimi` → `kimi_fallback`

Máximo 3 intentos totales; si todos fallan, detener y reportar. La escalada NO se
hace por calidad percibida: solo por fallo de servicio.

## Mapa script → nivel por defecto (default del script, el enrutador puede sobreescribirlo)

| Script / flujo | Nivel default |
| :--- | :--- |
| `rag_system.py` (RAG, embeddings+chat) | flash |
| `execution/analizar_imagen.py`, `execution/evaluar_examen.py`, `execution/extraer_netlist_imagen.py`, `execution/data_capture.py` | flash (multimodal/rutina) |
| `execution/elaborar_examen.py`, `execution/elaborar_ejercicios.py`, `execution/generar_kicad_llm.py`, `agent_eda.py` | opus |
| Cualquier tarea de contexto masivo (logs, repos, datasheets) | kimi |

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
  del auto top-up de $10, priorizar tiers baratos (flash/kimi) y evitar opus para no agotar saldo.