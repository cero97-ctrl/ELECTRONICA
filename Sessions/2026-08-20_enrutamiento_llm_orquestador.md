# Sesión: opencode como orquestador del enrutamiento multi-LLM

**Fecha:** 2026-08-20
**Agente:** opencode

## Tema tratado
Actualizar la arquitectura de enrutamiento multi-LLM (`docs/ARQUITECTURA_ENRUTAMIENTO_LLM/arquitectura_enrutamiento_llm.md`) para que el orquestador sea opencode (capa de orquestación local), e incorporar Kimi K3 como nivel intermedio. El usuario pidió explícitamente "que tú seas el orquestador".

## Contexto previo
- Sesión `2026-08-19_centralizar_llm_client.md`: OpenRouter centralizado en `execution/llm_client.py`; política acordada orquestador=opencode, FLASH=`gemini-3.7-flash`, OPUS 5=`claude-opus-5`.
- El documento viejo nombraba a DeepSeek como orquestador y usaba IDs desactualizados (`moonshotai/moonshot-v1-128k`, `google/gemini-2.5-flash`, `anthropic/claude-3-opus`).

## Actividades realizadas
- Verificado el ID real de Kimi K3 en OpenRouter: `moonshotai/kimi-k3` (1M ctx, $3/$15, cache read $0.30, razonamiento *always-on*, propenso a 429) y precios de `claude-opus-5` ($5/$25).
- Reescrito `docs/ARQUITECTURA_ENRUTAMIENTO_LLM/arquitectura_enrutamiento_llm.md`:
  - §1: orquestador = opencode (reemplaza a DeepSeek).
  - §2-3: matriz de decisión de 3 niveles con IDs correctos; Kimi reposicionado como razonamiento intermedio económico (no solo retrieval) + nota de 429 y fallback.
  - §4: directiva del orquestador (opencode) materializada en `.agent/enrutamiento.md` y `directives/enrutamiento_llm.yaml`.
  - §6: referencia reescrita con `execution/llm_client.py`, `max_tokens` y cadena de fallback `kimi → deepseek-v4-pro → opus`.
- Creado `.agent/enrutamiento.md` (auto-cargado por opencode.json): política runtime con matriz, tabla script→nivel, reglas de fallback y restricciones (geo VE, max_tokens, Kimi sin rol developer, JSON balanceado, saldo).
- Creado `directives/enrutamiento_llm.yaml` (Layer 1, SOP): goal, inputs, steps (clasificar → elegir nivel → invocar script con `--api-backend openrouter --modelo`), expected outputs y edge cases.
- Añadido `MODEL_TIERS` a `execution/llm_client.py` como fuente única de IDs por nivel.

## Decisiones
- Decisión de enrutamiento: **directa del orquestador** (sin salida JSON intermedia), según lo elegido por el usuario.
- No se refactorizan los defaults `--modelo` de los scripts existentes; el orquestador sobrescribe con `--modelo <id>` al invocar.
- Orquestador = opencode; DeepSeek deja de ser orquestador en la arquitectura (el modelo de esta sesión, `opencode/deepseek-v4-flash`, es solo el motor del asistente).

## Verificación
- `py_compile execution/llm_client.py` OK.
- `directives/enrutamiento_llm.yaml` parseable con PyYAML.

## Pendientes
- Ninguno.