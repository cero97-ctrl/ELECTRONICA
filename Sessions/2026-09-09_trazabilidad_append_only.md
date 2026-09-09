# Sesión 2026-09-09 — Trazabilidad append-only de sesiones/flujos

## Contexto
Decisión de la sesión previa (2026-09-08, exploración de DeepSeek Harness/dsh):
incorporar a ELECTRONICA la trazabilidad **append-only** de dsh ("cada run es
totalmente traceable; el log de eventos crece en un solo sentido"). Se adapta a la
arquitectura determinista de 3 capas, sin adoptar dsh ni Cordis como kernel.

## Actividades

### Capa 3 — Ejecución: `execution/sesion_log.py` (nuevo)
Helper determinista (stdlib puro) para logs append-only en JSONL:
- Log por ejecución: `.tmp/session_log_<run_id>.jsonl`
- Cada evento: `{seq, ts, run, tipo, datos, prev, append_only:true}` con **hash
  encadenado** (`prev` = sha256 de la línea anterior) → manipulación detectable.
- Vocabulario controlado de eventos: `flujo/inicio`, `flujo/paso`, `flujo/fin`,
  `flujo/error`, `tool/call`, `tool/result`. `--run` sanitizado (regex
  `[A-Za-z0-9._-]`), `--datos` JSON validado.
- Subcomandos: `add`, `ver`, `state` (deriva checkpoint/vista), `resume`
  (reanudable + siguiente_paso), `integrity` (cadena de hashes + seq contiguo).
- Exit codes 0/1/2/3: 1=entrada inválida, 2=log inexistente/corrupto, 3=interno.

### Capa 1 — Directiva: `directives/trazabilidad_sesiones.yaml` (nuevo)
SOP que documenta: cuándo registrar cada evento (inicio/paso/error/fin), el
vocabulario, y los edge cases (manipulación → integrity exit 2; escritura
interrumpida; run_id malicioso; reanudación tras error). `run_state.json` pasa a
ser vista derivada (comando `state`), no fuente primaria.

### Capa 2 — Orquestación: `flujo_repo_a_skill.py` (piloto)
Integración en el flujo piloto, sin romper su checkpoint:
- Constante `SESION_LOG` + helper `registrar_evento(state, tipo, datos)` con
  fallo blando (la traza nunca aborta el flujo).
- Eventos: `flujo/inicio` tras `save_state` inicial; `flujo/paso` desde
  `estado_ok`; `flujo/error` en los 4 puntos de aborto (extracción, síntesis,
  validación estricta, instalación); `flujo/fin` al completar.

### Verificación (0 créditos OpenRouter)
- `add`/`ver`/`state`/`resume`/`integrity` probados a mano (run de 5 eventos).
- Manipulación simulada (sed seq 1→99) → `integrity` exit 2, mensaje claro.
- `run_id` malicioso (`../etc/evil`) rechazado (exit 1).
- `resume` correcto en los 3 estados: fin (no reanudable), error (reanudable
  desde el paso del último error), en curso.
- Integración orquestador verificada con simulación (no se ejecutó la síntesis:
  consume créditos y el usuario no lo pidió).

## Decisiones
- `.gitignore`: se añaden `.tmp/session_log_*.jsonl` y `.tmp/run_state_*.json`
  (trazas de runtime, como `routing_log.jsonl`).
- El log append-only es la fuente de verdad; `run_state.json` es una vista
  derivable (`sesion_log.py state --run <id>`).
- La escritura de eventos nunca rompe el flujo (fallo blando con warning).
- Migración gradual: los demás flujos pueden adoptar `registrar_evento` según la
  directiva sin abandonar su `save_state`.

## Pendientes
- Probar `flujo_repo_a_skill.py` de extremo a extremo con la traza (consume
  créditos OpenRouter: solicitarlo explícitamente).
- Migrar otros flujos (`flujo_libro_a_skill`, `flujo_diagnostico`, etc.) al patrón
  `registrar_evento` cuando aporte valor.
- Hands-on de los 4 modos de dsh (postergado de la sesión previa).
- Reiniciar opencode para cargar el skill `dsh` (sigue pendiente).