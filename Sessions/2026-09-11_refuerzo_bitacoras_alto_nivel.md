# 2026-09-11 — Refuerzo eslabón semántico: bitácoras

## Tema
Refuerzo del eslabón de contexto de ALTO nivel (memoria semántica) del workspace:
las bitácoras de sesión en `Sessions/`. El eslabón de bajo nivel (logs append-only +
estado de ejecución) quedó blindado con `estado_sesion.py`; lo que faltaba era
mecanizar el hábito de escribir y validar las bitácoras semánticas.

## Contexto
- Distinción explicada al usuario: el contexto de BAJO nivel son datos reproducibles
  (session_log_*.jsonl, run_state*.json: quién/cuándo/qué se ejecutó); el de ALTO
  nivel es significado (por QUÉ se decidió, qué se descartó, intenciones y matices
  del usuario) que NO vive en ningún log de ejecución.
- Riesgo: si la sesión no escribe su bitácora, la siguiente no puede recuperar el
  razonamiento y volvería a investigar (tokens/créditos) o a decidir sin contexto.
- El usuario aprobó reforzar este eslabón.

## Decisiones (usuario)
1. Reforzar el hábito de bitácoras con herramienta determinista (no confiar en la
   memoria probabilística).
2. Formato canónico: `Sessions/YYYY-MM-DD_<tema>.md` con secciones Tema, Contexto,
   Decisiones (usuario), Actividades, Pendientes. Lo previo a 2026-09-11 es "legado
   transicional" (otra convención), se lista informativo sin penalizar.

## Actividades
- Creado `execution/bitacoras.py` (determinista, 0 créditos):
  - `nueva --tema <tema>`: genera la bitácora canónica de hoy desde la plantilla
    (nunca sobrescribe). Slug seguro del tema para el nombre del archivo.
  - `check [--today]`: valida nombre, fecha parseable (sin futuras), secciones
    mínimas y contenido; clasifica cada bitácora como hoy/reciente/legado y solo
    las hoy/recientes cuentan como anomalías accionables. Reporta si la sesión de
    hoy ya dejó bitácora.
  - Veredictos probados: legado no penaliza (anomalías 0 tras ajuste con
    `FECHA_PLANTILLA`); `nueva` no sobrescribe (prueba doble llamada); `--today`
    reporta la bitácora de la sesión actual.
- Creación de la plantilla pendiente de completar: documento infográfico
  `docs/AGENTE_IA/higiene_estado_sesion.tex/.pdf` generado (sesión previa).

## Pendientes
- Completar/validar las bitácoras recientes (aquellas entre hoy y la adopción de la
  plantilla) si el usuario lo desea; las de `legado` no se tocan.
- Considerar recordatorio automático al inicio/fin de sesión (integración en flujo o
  directiva) usando `bitacoras.py check`.
- (De sesión previa, no tocado) `docs/AGENTE_IA/orquestador_repo_a_skill.mp4`.