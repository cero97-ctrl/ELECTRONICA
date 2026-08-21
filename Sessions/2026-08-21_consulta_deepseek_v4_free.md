# Sesión: DeepSeek V4 fuera del tier Free + actualización de AGENTS.md

**Fecha:** 2026-08-21
**Agente:** opencode

## Tema tratado
El usuario consulta si el modelo DeepSeek V4 (actualmente configurado como `deepseek/deepseek-v4-flash` en el tier Free o como motor del asistente) ha dejado de ser gratuito en OpenRouter.

## Contexto previo
- En la sesión anterior (`2026-08-20_enrutamiento_llm_orquestador.md`), se documentó que el motor del asistente en opencode es `deepseek/deepseek-v4-flash` (un modelo en el tier Free de OpenRouter).
- Se acordó el desacople total de este motor respecto de la arquitectura de enrutamiento local, que usa `google/gemini-3.7-flash`, `deepseek/deepseek-v4-pro`, `z-ai/glm-5.2` y `anthropic/claude-opus-5` con saldo propio (`OPENROUTER_API_KEY`).

## Actividades a realizar
1. Consultar el estado del modelo `deepseek/deepseek-v4-flash` y su gratuidad.
2. Responder a la consulta del usuario de forma concisa y directa.

## Decisiones
- Se consultó en tiempo real la API de OpenRouter (`https://openrouter.ai/api/v1/models`).
- Se confirmó que **DeepSeek V4 (tanto Flash como Pro)** ya no tiene versiones en el tier gratuito (`:free`) de OpenRouter.
- Los precios actuales de DeepSeek V4 Flash son extremadamente bajos (Prompt: ~$0.08 / M token, Completion: ~$0.18 / M token), pero ya no son $0.00.
- Como alternativa en el tier gratuito de OpenRouter para tareas de soporte o asistente, se encuentran activos modelos como `z-ai/glm-5.2:free`, `google/gemma-4-31b-it:free`, y `openai/gpt-oss-20b:free`.

## Pendientes
- Ninguno. La consulta fue resuelta y registrada.

## Segunda parte: actualización de AGENTS.md (mismo día)
El usuario confirmó que opencode conmutó su motor a `google/gemini-3.5-flash` al salir
DeepSeek del tier Free, y luego reportó que la cuota Free de Gemini 3.5 Flash también
se agotó. Pidió actualizar `AGENTS.md`.

### Ediciones aplicadas (AGENTS.md)
1. **Know before you act** — dos bullets nuevos tras el de geo-bloqueo:
   - **Enrutamiento multi-LLM (determinista):** no elegir modelo razonando; descriptor →
     `execution/enrutador.py` → invocar script con `--api-backend openrouter --modelo <id>`.
     IDs en `MODEL_TIERS` (`execution/llm_client.py`), fallback cost-aware máx 3 intentos,
     telemetría `.tmp/routing_log.jsonl`, política en `.agent/enrutamiento.md` +
     `directives/enrutamiento_llm.yaml` + doc de arquitectura.
   - **Motor del asistente opencode (rotativo):** solo interfaz del orquestador, NO parte
     del routing; DeepSeek V4 salió del Free (2026-08-21) → motor `google/gemini-3.5-flash`;
     cuotas Free se agotan rápido y el motor rota sin aviso (Free activos: glm-5.2, gpt-oss-20b,
     gemma-4). Cambiarlo no toca el router.
2. **Commands** — agregado **Enrutador LLM**: `python3 execution/enrutador.py --task <tipo>
   [--tokens N | --archivos f1 f2] [--critico] [--vision] [--modelo-explicito <id>]` → JSON.

### Verificación
- Router probado: `--task contexto_masivo --tokens 80000` → deepseek ✔;
  `--task formateo --tokens 500` → flash ✔ (salida JSON correcta).

### Decisiones
- No se tocó la bullet de geo-bloqueo ni la línea de RAG: siguen exactas.
- El detalle fino del routing vive en `.agent/enrutamiento.md` (auto-cargado); AGENTS.md
  solo lleva el resumen operativo + comando.

## Tercera parte: facturación chat vs ejecución + motor Big Pickle
El usuario preguntó si esa separación estaba documentada en AGENTS.md. Verificación:
parcialmente — había dos brechas.

### Hallazgos
1. La bullet del motor decía `google/gemini-3.5-flash`, pero el motor actual es
   **Big Pickle** (`opencode/big-pickle`), modelo stealth del gateway **OpenCode Zen**
   (Free temporal), elegido por el usuario en `/models`.
2. La distinción de facturación no estaba explícita: modelos vía Zen (`opencode/...`)
   facturan a la cuenta Zen aparte (Free = $0); modelos vía proveedor OpenRouter
   descuentan saldo de `OPENROUTER_API_KEY`. Confirmado con docs oficiales
   (opencode.ai/docs/zen): Zen es pay-as-you-go con auto-recarga, los Free de Zen no
   consumen nada, y "bring your own key" factura directo del proveedor.

### Edición aplicada (AGENTS.md)
- Bullet "Motor del asistente opencode (rotativo)" reescrita: motor actual Big Pickle,
  rotación indistinta entre Free de Zen y de OpenRouter, y nota de **Facturación en
  `/models`** (Zen vs OpenRouter; solo `enrutador.py`, `rag_system.py`, `agent_eda.py`
  consumen créditos OpenRouter).

### Decisiones
- La separación queda explícita: motor del chat = $0 (nunca toca `OPENROUTER_API_KEY`);
  todo el trabajo de ejecución sale del saldo OpenRouter.

## Cuarta parte: guardián del principio determinista
El usuario pidió que se le alerte cuando una petición suya viole el espíritu
determinista del proyecto (a veces pide cambios sin darse cuenta de que rompen el
modelo de 3 capas / decisiones por reglas).

### Edición aplicada (AGENTS.md)
- Nueva subsección **"Determinism guardrail (alert before executing)"** justo tras la
  tabla de la arquitectura de 3 capas. Protocolo: DETENERSE antes de ejecutar, alertar
  con explicación y proponer la alternativa conforme; proceder con lo pedido solo si el
  usuario confirma tras la alerta, registrando la excepción en el log de sesión.
- Violaciones vigiladas: elegir modelo razonando en chat (→ `enrutador.py`), lógica de
  decisión en prompts/chat (→ `execution/*.py`), flujos repetibles sin 3 capas,
  procesamiento inline de datos, rupturas de reproducibilidad o de validación/retry budget.

### Decisiones
- La regla vive en AGENTS.md (auto-cargado por opencode) para persistir en sesiones futuras;
  no se creó directiva nueva porque no es un flujo ejecutable sino una política de conducta
  del orquestador.
