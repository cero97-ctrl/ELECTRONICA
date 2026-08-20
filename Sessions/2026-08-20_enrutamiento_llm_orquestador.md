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

## Segunda iteración: decisión DETERMINISTA
El usuario pidió que las decisiones sean deterministas, no probabilísticas (para no
contradecir la filosofía del framework: complejidad en código, no en el contexto del LLM).

- Creado `execution/enrutador.py`: decisión por REGLAS PURAS (sin criterio del LLM).
  Precedencia: modelo explícito > umbral de tokens medidos (>50k) > tipo de tarea
  (vocabulario controlado) > criticidad. El mismo descriptor → siempre el mismo tier.
  Cadenas de fallback deterministas y cost-aware:
  flash → kimi → kimi_fallback; kimi → kimi_fallback → opus; opus → kimi → kimi_fallback.
  Telemetría de cada decisión en `.tmp/routing_log.jsonl`.
- Actualizado `.agent/enrutamiento.md`, `directives/enrutamiento_llm.yaml` (v2.0) y
  `arquitectura_enrutamiento_llm.md` (§2 "Enrutamiento Determinista", §4 directiva):
  el orquestador SOLO extrae el descriptor (parsing de intención) y delega la elección
  en `execution/enrutador.py`; nunca elige el modelo razonando en el chat.
- `MODEL_TIERS` ampliado con `kimi_fallback` = `deepseek/deepseek-v4-pro`.

## Tercera iteración: Kimi K3 fuera del enrutamiento automático
El usuario reportó (experiencia real con la web) que Kimi K3 está saturado la mayor
parte del tiempo y el producto falla a K2.6 de forma invisible. Coincide con la
investigación: el 429 es del upstream Moonshot, sin mitigación desde ningún gateway.

- Decisiones: **demover Kimi K3 de los tiers** y darle el rol de modelo opcional
  (solo `--modelo-explicito`). Tier medio = **DeepSeek V4 Pro** (`deepseek/deepseek-v4-pro`,
  $0.44/$0.87, 1M ctx, 18 providers) con **GLM-5.2** (`z-ai/glm-5.2`, 25 providers) de respaldo.
- `execution/llm_client.py`: `MODEL_TIERS` = {flash, deepseek, glm, opus};
  `MODELOS_OPCIONALES` = {kimi_k3}.
- `execution/enrutador.py`: cadenas de fallback cost-aware actualizadas
  (flash→deepseek→glm; deepseek→glm→opus; opus→deepseek→glm). Umbral >50k → deepseek.
- Actualizados `.agent/enrutamiento.md`, `directives/enrutamiento_llm.yaml` (v2.1) y
  `arquitectura_enrutamiento_llm.md` (§3 tier medio DeepSeek/GLM, nota Kimi K3 opcional).

## Cuarta iteración: desacople del motor del asistente
El usuario aclaró que el motor del asistente en opencode es DeepSeek V4 Flash porque
está en el tier Free, y que cuando opencode lo retire escogerá otro motor Free.

- Añadida nota en `arquitectura_enrutamiento_llm.md` §1: el motor del asistente es SOLO
  la interfaz del orquestador, NO forma parte del routing (la decisión se consume con
  `OPENROUTER_API_KEY` vía `enrutador.py` + `MODEL_TIERS`). Cambiar el motor Free a
  futuro no requiere tocar el router (commit `90e9a6e`).

## Estado final de la arquitectura (2026-08-20, mañana)

| Nivel | Modelo | Rol |
| :--- | :--- | :--- |
| flash | `google/gemini-3.7-flash` | Rutina: parsing/formatting, RAG, multimodal rápido |
| deepseek | `deepseek/deepseek-v4-pro` | Contexto masivo (>50k tok) / razonamiento intermedio (1M ctx) |
| glm | `z-ai/glm-5.2` | Respaldo del tier medio |
| opus | `anthropic/claude-opus-5` | Razonamiento crítico: diseño, cálculo formal, debugging, exámenes |
| (opcional) | `moonshotai/kimi-k3` | Solo por petición explícita (`--modelo-explicito`) |

Fallback cost-aware: `flash→deepseek→glm`; `deepseek→glm→opus`; `opus→deepseek→glm`.
Decisión de tier: determinista en `execution/enrutador.py`; opencode solo extrae el
descriptor. Telemetría en `.tmp/routing_log.jsonl` (gitignored).

## Decisiones
- Decisión de enrutamiento: **DETERMINISTA** vía `execution/enrutador.py`; opencode solo
  hace parsing de intención y ejecución. (Elegido por el usuario sobre la opción de
  salida JSON intermedia.)
- No se refactorizan los defaults `--modelo` de los scripts existentes; el orquestador
  sobrescribe con `--modelo <model>` devuelto por el router.
- Orquestador = opencode; DeepSeek deja de ser orquestador en la arquitectura (el modelo
  de esta sesión, `opencode/deepseek-v4-flash`, es solo el motor del asistente).
- Kimi K3 queda como modelo opcional por petición explícita (no se enruta automáticamente).

## Verificación
- `py_compile` OK en `execution/enrutador.py` y `execution/llm_client.py`.
- `directives/enrutamiento_llm.yaml` parseable con PyYAML.
- Pruebas del router: formateo→flash, contexto_masivo (80k y 30k)→deepseek,
  examen_complejo→opus, parsing+critico→opus, multi_archivo→deepseek,
  override explícito `moonshotai/kimi-k3`→ok.
- Determinismo verificado: misma entrada → idéntica salida en ejecuciones repetidas.

## Pendientes
- Ninguno.