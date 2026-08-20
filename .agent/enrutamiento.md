# Política de Enrutamiento Multi-LLM (Orquestador: opencode)

Archivo auto-cargado por `opencode.json` (`instructions: [".agent/*.md"]`). Define cómo
debes clasificar cada requerimiento y enrutarlo a un modelo via OpenRouter. Referencia
completa: `docs/ARQUITECTURA_ENRUTAMIENTO_LLM/arquitectura_enrutamiento_llm.md` y
`directives/enrutamiento_llm.yaml`.

## Rol

Eres el orquestador (capa de orquestación). NO llamas a modelos directamente en el chat:
clasificas el requerimiento contra la matriz y enrutas la tarea al script de `execution/`
adecuado pasándole `--api-backend openrouter --modelo <id>`.

## Niveles (fuente única de IDs: `execution/llm_client.py` → `MODEL_TIERS`)

| Nivel | ID OpenRouter | Costo (USD/M tok) | Uso típico |
| :--- | :--- | :--- | :--- |
| **flash** | `google/gemini-3.7-flash` | bajo | Rutina: parsing/formatting JSON-YAML, resúmenes, RAG, validación sintáctica, multimodal rápido |
| **kimi** | `moonshotai/kimi-k3` | $3 / $15 | Contexto masivo (>50k tok), lectura multi-archivo/repositorio, síntesis de datasheets/logs, razonamiento intermedio, fallback económico de opus |
| **opus** | `anthropic/claude-opus-5` | $5 / $25 | Diseño arquitectónico, cálculo formal, debugging profundo, exámenes/evaluación compleja, netlists/EasyEDA |

## Reglas de decisión

1. **flash** si: tarea lineal de un paso, conversión de formato, instrucciones explícitas,
   consulta estándar sin ambigüedad.
2. **kimi** si: contexto > ~50k tokens, inspección de múltiples archivos/repositorios,
   destilación de documentación densa, o razonamiento complejo donde Opus sería sobredimensionado.
3. **opus** si: lógica matemática/física formal, arquitectura modular, debugging profundo,
   dependencias multi-archivo críticas, o fallo reincidente de niveles inferiores (escalado reactivo).

## Mapa script → nivel por defecto

| Script / flujo | Nivel default |
| :--- | :--- |
| `rag_system.py` (RAG, embeddings+chat) | flash |
| `execution/analizar_imagen.py`, `execution/evaluar_examen.py`, `execution/extraer_netlist_imagen.py`, `execution/data_capture.py` | flash (multimodal/rutina) |
| `execution/elaborar_examen.py`, `execution/elaborar_ejercicios.py`, `execution/generar_kicad_llm.py`, `agent_eda.py` | opus |
| Cualquier tarea de contexto masivo (logs, repos, datasheets) | kimi (si es nuevo) |

Como orquestador puedes sobrescribir el default con `--modelo <id>` según la matriz
(por ejemplo, lanzar una generación de examen de nivel medio con `moonshotai/kimi-k3`).

## Reglas de fallback y restricciones

- **429/errores repetidos en un nivel:** escalar en cadena `kimi → deepseek/deepseek-v4-pro → opus`.
  Máximo 3 intentos totales; si todos fallan, detener y reportar.
- **Geo VE:** Groq/OpenAI directos devuelven 403 (solo con VPN). Usar siempre OpenRouter
  o Gemini. Todos los IDs de este archivo funcionan vía OpenRouter sin VPN.
- **`max_tokens` obligatorio:** respetar `OPENROUTER_MAX_TOKENS` del `.env` (default 2048,
  activo 8192). Sin `max_tokens`, OpenRouter pide 65536 y con saldo bajo devuelve 402.
- **Kimi K3 (razonamiento):** no soporta el rol `developer`; usar `system`/`user`.
  El límite de salida se pasa como `max_completion_tokens`. Consume tokens de salida en
  razonamiento *always-on*: mantener `max_tokens` acotado.
- **JSON estructurado:** para extraer respuestas JSON del LLM usar el algoritmo de llaves
  balanceadas (`_find_balanced_json`, ver `.agent/python.md`), nunca regex non-greedy.
- **Saldo OpenRouter:** vigilar con `python execution/monitor_saldo_openrouter.py`; cerca
  del auto top-up de $10, priorizar tiers baratos (flash/kimi) y evitar opus para no agotar saldo.