# 2026-09-21_motor_fallback

## Tema
Flujo determinista de failover del motor del orquestador: detección de cuota free
agotada (motor `opencode/big-pickle`) y conmutación atómica al motor de respaldo
(`openrouter/qwen/qwen3.8-max-0902`) con auto-restore.

## Contexto
El motor free del orquestador (TUI opencode) se agota sin aviso y rompe la sesión.
El agotamiento se detecta por firma (429|quota|rate|limit|usage|reset|retry) del
resultado de la sonda. La decisión de conmutar es funcion pura de la firma del
resultado — nunca una decisión razonada en el chat (determinismo garantizado).

## Decisiones (usuario)
1. Conmutación hands-free vía tmux (relanzar la TUI automáticamente con el motor de
   respaldo).
2. Auto-restore: al recuperar la cuota free, restaurar el motor free original y
   relanzar la TUI (restore automático desde el watcher, sin intervención).

## Actividades
- Crear `directives/motor_fallback.yaml` — SOP YAML válido con 4 pasos, entradas
  requeridas, casos borde (error_infra / indeterminado → no conmutar).
- Crear `.tmp/descriptor_motor_fallback.json` — descriptor ISO 5807 con 13 nodos
  (detector, confirmaciones consecutivas N, backup marker, switch atómico, alerta,
  watcher, auto-restore) + conexiones con etiquetas.
- Crear `flujo_motor_fallback.py` — orquestador (check|switch|restore|watch|pasivo,
  retry budget max 3, escritura atómica + backup).
- Crear `execution/verificar_cuota_motor.py` — sonda determinista que clasifica
  ok | agotada | error_infra | indeterminado.
- Crear `execution/aplicar_switch_modelo.py` — switch/restore con validación +
  backup + marker `.tmp/motor_fallback.json` + escritura atómica.
- Generar `docs/AGENTE_IA/motor_fallback_flujo.{tex,pdf}` — diagrama ISO 5807
  infográfico (3 páginas, 0 solapes) vía `generar_diagrama_flujo.py`.

## Pendientes
- Registrar la firma de un 429 real de la cuota free del motor (afinar regex del
  detector con la primera captura real del opencode/log).
- Probar el modo `--no-tokens` (escaneo pasivo de opencode.log) end-to-end.
- Commit del flujo completo (directiva + orquestador + execution + diagrama + .tex).
