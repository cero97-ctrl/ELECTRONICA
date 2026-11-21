# 2026-11-20 — cuestionario_lab_i_ventana_945

## Tema
Mover la ventana de entregas del cuestionario de **Laboratorio I de Física**
del jueves 26-nov-2026: el inicio pasa de 08:00 a **09:45 VET**, con cierre
15 min después de la duración del examen.

## Contexto
- La bitácora `Sessions/2026-11-18_cuestionario_web_laboratorio_ii_fisica.md`
  fijaba Lab I en 26-nov, 08:00–09:00 VET (`12:00Z`–`13:05Z`, 60 min + 5 de
  holgura) en el Worker `cuestionarios-worker-lab1` (`env.lab1`), con 2 inscritas.
- La fuente de verdad de la ventana son los secretos `VENTANA_INICIO` y
  `VENTANA_FIN` del Worker, **no** un archivo del repo: se cambian con
  `--inicio/--fin` del flujo, sin tocar código ni el HTML.
- Al mover solo el inicio, el fin antiguo (`09:00 VET`) quedaba **antes** del
  inicio nuevo: el Worker habría rechazado las 2 entregas con 403. Por eso
  hacía falta decidir también el cierre y el momento de publicar la página
  (el repo `cero97-ctrl/cuestionarios-lab1` está privado → 404 hasta el flip).
- `flujo_desplegar_worker_cuestionarios.py` omite los secretos vacíos, así que
  al no pasar `--nomina` el secreto `CEDULAS` se conserva.

## Decisiones (usuario)
1. **Inicio**: jueves 26-nov-2026, 09:45 VET → `2026-11-26T13:45:00Z`.
2. **Cierre**: 10:50 VET → `2026-11-26T14:50:00Z` (60 min de examen + 5 min de
   holgura para Pages; se conserva la duración que ya tenía Lab I).
3. **Publicación del HTML**: el flip a público del repo `cuestionarios-lab1`
   se hace **a las 09:45**, con la apertura, en vez de las 08:00 previstas.
   Evita dejar las preguntas accesibles 1 h 45 antes del inicio.

## Actividades
- Bitácora de sesión creada con `execution/bitacoras.py nueva`; `estado_sesion.py
  check` → `veredicto_global: ok`.
- Lectura de `/salud` antes del cambio: `ok:true`, `abierta:false`
  («todavía no empieza»), `inscritas:2`.
- Fuente confirmada:
  `cursos/LABORATORIO_I_FISICA/evaluaciones/web/fuentes/lab_i_fisica_cuestionario.md`,
  con `entrega_url: https://cuestionarios-worker-lab1.cero-agents.workers.dev`
  y `CUESTIONARIO_ID` alineado con `env.lab1`.
- **Dry-run** (`--check --json`, sin escribir en la cuenta): `code 0`,
  `cuestionario: lab_i_fisica_cuestionario`, `worker: cuestionarios-worker-lab1`,
  10 preguntas, `justificacion_items: []`, `nomina: 0`, ventana
  `13:45Z–14:50Z`, `clave_sha256: 7364424d…c7`.
- **Redespliegue real** con
  `--env lab1 --inicio 2026-11-26T13:45:00Z --fin 2026-11-26T14:50:00Z`
  (sin `--nomina`, sin `--actualizar-fuente`): `status ok`, `/salud true`,
  secretos presentes `CLAVE_JSON`, `GITHUB_TOKEN`, `CEDULAS`, `VENTANA_INICIO`,
  `VENTANA_FIN`, `MIN_JUSTIFICACION`; `ITEMS_JUSTIFICACION` vacío (correcto).
  Misma huella de clave antes y después (`7364424d…c7`).
- Verificación independiente: `wrangler secret list --format json --env lab1`
  confirma los 6 secretos; `/salud` sigue `abierta:false, inscritas:2`;
  `TZ=America/Caracas date -d` confirma jueves 09:45 y 10:50 (UTC−4).
  `git status` sin cambios nuevos salvo esta bitácora: ni la fuente ni los
  archivos sin commitear de sesiones anteriores se tocaron.
- **Commit `147b7dfd`** del trabajo pendiente de la sesión del 18-nov (16
  archivos: 13 modificados + bitácora del 18-nov, `test_desplegar_worker.py` y
  `token_resultados.py`). Divergencia previa `0 0`; stage explícito porque
  `update_repo.sh` hace `git add -A` y habría incluido el PDF personal y esta
  bitácora. **Push a `origin/master` hecho** (`f449b039..147b7dfd`): divergencia
  final `0 0`. Fuera del commit: `cursos/LABORATORIO_I_FISICA/ALUMNOS_LAB_I_FISICA.pdf`
  y esta bitácora.

## Pendientes
- **26-nov, 09:45**: publicar con
  `python3 flujo_publicar_cuestionario.py --web-dir cursos/LABORATORIO_I_FISICA/evaluaciones/web --repo cero97-ctrl/cuestionarios-lab1 --visibilidad public --push`
  (Pages puede tardar ~1 min; si sale 404, esperar y recargar). Enviar el
  WhatsApp de apertura con la hora nueva: **09:45–10:50**, no 08:00–09:00.
- **26-nov, 10:50**: el mismo comando con `--visibilidad private`; el contenido
  deja de servirse cuando expire la caché (hasta ~10 min después). Después,
  `flujo_acta_cuestionario.py` sobre `cuestionarios-resultados-lab1`.
- **No tocar Lab II**: su ventana sigue siendo 24-nov 08:00–09:05 VET
  (`12:00Z–13:05Z`) en `cuestionarios-worker-lab2` y su repo `cuestionarios-lab2`.
- El HTML no imprime día ni hora: si se quiere en la página, hay que añadir la
  ventana al front matter y al generador (pendiente heredado del 18-nov).
- **Hallazgo fuera de alcance (no corregido)**: `flujo_desplegar_worker_cuestionarios.py`
  repite el bloque de `extras` + `_secretos` + `GITHUB_TOKEN` dentro de la rama
  `if not presentes["GITHUB_TOKEN"]` (aprox. líneas 510–545 y 557–592). Hoy no
  se ejecutó porque el token ya estaba fijado, pero en un redespliegue con el
  token ausente escribiría los secretos dos veces. Revisar en otra sesión.
