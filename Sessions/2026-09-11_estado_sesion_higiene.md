# 2026-09-11 — Higiene de estado: run_state huérfano y guards en MCPs

## Tema
Refuerzo del punto más débil de la continuidad de sesión: confiar en estado
obsoleto/artefactos huérfanos de `.tmp/`.

## Contexto
- Detección previa (auditoría): `run_state.json` puede SOBREVIVIR a su corrida.
  El log append-only `session_log_*.jsonl` es la fuente de verdad; `run_state*.json`
  son vistas derivadas que un flujo `flujo/fin` puede dejar huérfanas.
- Caso real encontrado: `.tmp/run_state.json` apuntaba a
  `flujo-repo-a-skill-2026-09-09T12-29-54` (dry-run de trazabilidad) con modelo
  `deepseek/deepseek-v4-pro` (discontinuado 2026-09-14), mientras su log tenía
  `flujo/fin` (corrida terminada). Servidores MCP leen ese archivo global como
  "estado del flujo recién lanzado" → riesgo de responder con estado de OTRA corrida.

## Decisiones (usuario)
1. Script de salud `check` + `--clean` que borre SOLO lo marcado huérfano/obsoleto
   con certeza.
2. Protección integrada YA en los servidores MCP que leen `run_state.json`.
3. Borrar el `run_state.json` huérfano actual al cierre.

## Actividades
- Creado `execution/estado_sesion.py` (determinista, 0 créditos):
  - `check`: escanea `run_state.json` y `run_state_*.json`, cruza contra su
    `session_log_*.jsonl`, clasifica `huerfano | vigente | no_verificable | corrupto`
    y detecta modelos obsoletos por substring (`deepseek-v4-pro`). Solo diagnostica.
  - `clean [--dry-run]`: borra ÚNICAMENTE vistas cuya corrida terminó con
    `flujo/fin` (certeza). Nunca borra logs append-only. Los flujos sin trazabilidad
    (sin log) son `no_verificable` y NO se borran.
  - Exit 0 con `veredicto_global: atencion` en anomalías.
- Guard en 5 servidores MCP (`mcp_evaluar_server.py`, `mcp_diagnostico_server.py`,
  `mcp_analizar_server.py`, `mcp_elaborar_server.py`, `mcp_docs_server.py`):
  capturan `mtime_before` del `run_state.json` ANTES de `subprocess.run` del flujo y
  solo leen el estado si el archivo fue REEESCRITO durante la corrida (`mtime > before`).
  Un fallo del flujo sin llegar a escribir → no se reporta estado de otra corrida.
  (Corrección sobre el criterio inicial `flujo/fin`, que era inválido: un flujo que
  corre bien también termina en `flujo/fin` y su estado SÍ es válido.)
- Directiva ampliada: `directives/trazabilidad_sesiones.yaml` → edge case
  "run_state.json obsoleto o huérfano al inicio de sesión/consulta MCP".
- `AGENTS.md`: nueva regla "State hygiene (freshness)" — al arrancar cada sesión o
  antes de reanudar un flujo multi-paso, correr `estado_sesion.py check` y purgar con
  `clean`.
- Pruebas: caso A (huérfano no reescrito → `{}`), caso B (reescrito por corrida →
  estado válido); `check` + `clean` real sobre el huérfano actual lo purgó y el log
  quedó intacto.

## Veredicto del estado real actual
- `.tmp/run_state.json` (huérfano, `flujo-repo-a-skill`) → **borrado**.
- `session_log_flujo-repo-a-skill-2026-09-09T12-29-54.jsonl` → intacto (fuente de verdad).
- Post-clean: `check` reporta `veredicto_global: ok`.

## Pendientes
- (Pendiente de sesión anterior, NO tocado) `docs/AGENTE_IA/orquestador_repo_a_skill.mp4`
  — borrado pendiente de aprobación.
- Considerar educar a los flujos para que emitan su run_id al final del stdout
  (facilitaría validación futura sin depender de mtime).