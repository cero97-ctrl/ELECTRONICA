# 2026-11-20 — plataforma_datos_universitaria_estilo_kaggle

## Tema
plataforma_datos_universitaria_estilo_kaggle

## Contexto
El usuario pidió analizar, corregir y sugerir mejoras a
`Proyectos/SERVIDOR_IA/SERVIDOR_IA.md` (1.565 líneas, transcripción de una
conversación sobre una plataforma universitaria estilo Kaggle on-premise).
El borrador mezclaba diseño, prompts de chat y código con cinco fallos que
impedían el despliegue, secretos embebidos y una autonomía eléctrica
sobreestimada. No había bitácora previa sobre el tema (`Sessions/*SERVIDOR*`,
`Sessions/*kaggle*` sin resultados).

## Decisiones (usuario)
1. El usuario aprobó el plan de corrección presentado en modo plan con
   "ok, procede con tu plan" (2026-11-20). No se inventaron decisiones
   académicas nuevas: se corrigió el diseño existente y se hicieron
   explícitas las deudas que el borrador daba por resueltas.
2. Alcance confirmado por el análisis: propuesta para la universidad, no
   para esta máquina. Se conservó la advertencia de que el entrenamiento
   de modelos del workspace va a Colab con TensorFlow.
3. Se mantuvo una sola métrica para el reto inaugural (AUC-ROC sobre datos
   tabulares) y se movió la regresión/RMSE a un "reto 2" documentado,
   para no mezclar escalas en la misma rúbrica.

## Actividades
- `python3 execution/estado_sesion.py check` (higiene de vistas derivadas).
- `python3 execution/bitacoras.py nueva --tema plataforma_datos_universitaria_estilo_kaggle`.
- Lectura completa del documento original (1-1565) en segmentos.
- Verificación de versiones reales (2026-11-20) antes de fijar tags:
  - Docker Hub: `nginx:1.30-alpine`, `postgres:16-alpine` (via `library/`),
    `jupyterhub/jupyterhub:6.2.0`, `jupyter/scipy-notebook:x86_64-python-3.11.6`,
    `tecnativa/docker-socket-proxy:3.4`.
  - GitHub Releases: `minio/minio:RELEASE.2025-10-15T17-29-55Z`.
  - PyPI: `dockerspawner==14.0.0`, `jupyterhub-idle-culler==2.0.0`,
    `jupyterhub-nativeauthenticator==1.4.0` (el nombre correcto del
    paquete no es `nativeauthenticator`).
- Reescritura completa de `Proyectos/SERVIDOR_IA/SERVIDOR_IA.md`
  (1.660 líneas) en 14 secciones: resumen de correcciones, contexto,
  arquitectura, hardware/costos, datathon, evaluador, JupyterHub,
  generadores, Nginx/portal, operación, rúbrica, alineación 3 capas,
  tests deterministas, guía estudiantes y hoja de ruta.
- Correcciones bloqueantes aplicadas: volumen `datasets` con nombre,
  `id_registro` como clave única con `ID_COLUMN` configurable,
  `bind_url=/hub` en la config única del Hub, `sample_submission.csv`
  generado por ambos scripts, healthchecks + `init_db()` controlado.
- Seguridad: secretos a `${VAR:?...}` con `.env.example`, `.gitignore`
  para `ground_truth*/`, `docker-socket-proxy` en vez de `docker.sock:rw`,
  identidad derivada del token de JupyterHub, `X-Admin-Key` con
  `hmac.compare_digest`, `textContent` en vez de `innerHTML`.
- Evaluador: validación de IDs con `validate="one_to_one"`, predicciones
  finitas y en `[0,1]` para AUC, cuota diaria atómica en
  `America/Caracas` con `SELECT ... FOR UPDATE`, private leaderboard con
  envío final, `compute_score` y `nota_desempeno` como funciones puras.
- Verificación del documento reescrito: 50 backticks (pares), 0 escapes
  `\_`, 0 etiquetas de exportador, 0 prompts `1)`, 11 bloques Python
  compilados con `compile()` sin errores de sintaxis.
- Correcciones de detalle tras la reescritura: 3 palabras no latinas
  introducidas por accidente, `coalesce/effective_score` en el ranking
  privado, `cookie_secret` inválido removido y nota del volumen `datasets`
  ajustada a `docker compose cp`.
- Generación del entregable LaTeX a petición del usuario (modo infográfico):
  `Proyectos/SERVIDOR_IA/SERVIDOR_IA.tex` (2.171 líneas) y
  `SERVIDOR_IA.pdf` (42 páginas, A4). Se usó pandoc (`gfm+tex_math_dollars`,
  `--no-highlight`) solo para el cuerpo, `PREAMBULO_INFOGRAFIA` importado de
  `execution/estilo_infografia.py` (sin duplicar), `verbatim` → `lstlisting`,
  `longtable` con columnas `p{}` para celdas largas, `allowbreak{}` en
  identificadores y `\setcounter{secnumdepth}{0}` para evitar doble numeración
  en el índice (los títulos ya traen "0.", "1.", ...). Guion determinista
  intermedio en `.tmp/generar_tex_servidor_ia.py`; el Markdown original no se
  modificó.
- Verificación del PDF: `verificar_pdf.py` → `status: ok`, 0 errores `!`,
  0 `Overfull \hbox`, 0 solapes; compilación aislada en
  `.tmp/latex_build/servidor_ia/` con 2 pasadas y `clean=False`.
- Corrección de legibilidad del código (reporte del usuario: letras negras
  sobre fondo oscuro). Diagnóstico con PyMuPDF: el texto negro no estaba en
  bloques sueltos sino en las **páginas de continuación** de listados largos
  dentro de `tcolorbox[breakable]` (p. ej. `docker-compose.yml` empieza en la
  pág. 5 en blanco y sigue en la 6 en negro): al romperse la caja, el
  `\color{white}` de `basicstyle` no se reaplica. Reproducción mínima con y sin
  arreglo: sin él la pág. 2 sale 567 chars negros; con él, 0. Solución:
  `colupper=white` en la caja que envuelve `lstlisting`, parche aplicado en el
  generador sobre `PREAMBULO_INFOGRAFIA` sin tocar `execution/estilo_infografia.py`.
  Verificación final: 0 spans negros sobre fondo oscuro en las 42 páginas,
  35.699 chars blancos + resaltado cian/gris de tokens intacto.

## Pendientes
- Verificar en un despliegue real: prefijo `/hub/` con `X-Forwarded-Prefix`,
  redirección de la consola de MinIO en `/minio/`, y compatibilidad de
  `DeviceRequest` con `dockerspawner==14.0.0`.
- Crear los tres archivos `.env.example` y `.gitignore` como artefactos
  físicos dentro de `Proyectos/SERVIDOR_IA/` si se decide adoptar el
  stack (hoy viven como bloques dentro del documento).
- Materializar las 4 filas de la sección 11 (directiva + orquestador +
  script por flujo) y los tests de la sección 12 en `execution/` y
  `directives/` si el usuario decide implementar la plataforma.
- Gobernanza de datos reales: anonimización, retención y revisión ética
  antes de sustituir los datasets sintéticos.
- Decidir si se evalúa Kaggle In Class como piloto Fase 1.
- Si la conversión Markdown→LaTeX se va a repetir, formalizar
  `.tmp/generar_tex_servidor_ia.py` como flujo de 3 capas (directiva YAML +
  orquestador `flujo_*` + script en `execution/`); hoy es sólo un intermedio
  regenerable, no un flujo del repositorio.
