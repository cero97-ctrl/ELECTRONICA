# 2026-11-01 — curso_ciberseguridad_13_semanas

## Tema
Diseño del curso `cursos/CYBERSEGURIDAD` dentro de ELECTRONICA: material docente
completo generado de forma determinista a partir de un descriptor, con sus tres
capas (directiva + orquestador + script) y diagrama de flujo ISO 5807.

## Contexto
- El usuario quiere un curso de ciberseguridad de 13 semanas impartido en grupos,
  con laboratorio local y material reproducible.
- Existe un repo aparte (`~/MEGA/VS_CODE_WORKSPACE/CYBERSEGURIDAD`, HEAD `0d6c1c5`,
  working tree limpio) que se consideró como fuente. Se descartó anidarlo dentro de
  ELECTRONICA: el curso es material docente, no un repo de código independiente.
- Restricciones aplicadas: 4 GB de RAM (nada de VMs), MEGAsync sincroniza todo
  `/home/cero/MEGA`, `.gitignore:31` ignora `examen*` en cualquier nivel.

## Decisiones (usuario)
1. Rediseñar el curso desde cero y añadir defensa/hardening, criptografía, forense
   y normativa (no solo ofensiva).
2. 13 semanas, 4 grupos de trabajo, **sin** proyecto integrador.
3. Primera entrega: sílabo + plan semanal + guía + prácticas + evaluaciones.
4. Laboratorio Docker local (DVWA / Juice Shop) más objetivos simulados propios.
5. Fuente única de verdad: `cursos/CYBERSEGURIDAD/curso.yaml`; el material se
   regenera desde el descriptor, nunca se edita el `.tex` generado.
6. (Asumido, no consultado) Los instrumentos se nombran `control_fase_N.tex` y
   `evaluacion_final.tex` en vez de `examen_*` porque git los ignoraría.
7. La calificación máxima del curso es **10 puntos**. Se fijó `nota_minima: 5`
   (50 %, criterio habitual de aprobación) como supuesto corregible.
8. Reducir la duración de **13 a 10 semanas** fusionando bloques, no recortando
   temario: Reconocimiento+Escaneo (nueva semana 4), Hardening+Red+detección
   (nueva 6) y Forense 1+Forense 2 (nueva 8). Se conservan las 5 fases
   (I:1-3, II:4-5, III:6-7, IV:8-9, V:10); controles en 3, 5 y 7; informes
   técnicos en 5, 7 y 9; evaluación final en la semana 10.

## Actividades
- Investigación previa: `.gitignore` (trampa `examen*`), MEGAsync, APIs de
  `estilo_infografia.py`, `compile_latex.py`, `verificar_pdf.py`, `generar_diagrama_flujo.py`.
- Escrito `cursos/CYBERSEGURIDAD/curso.yaml` (descriptor): meta con `fecha_iso`
  para reproducibilidad, RA1–RA7, 5 fases (I Fundamentos, II Ofensiva, III Defensa,
  IV Forense, V Cierre), 13 semanas con práctica de 5 pasos y criterios de 10 puntos,
  3 controles de fase, evaluación final, rúbrica, laboratorio y 6 políticas.
- Escrito `execution/generar_material_curso.py` (~900 líneas): validación estricta
  del descriptor, escape propio, generadores LaTeX, rúbrica compatible con
  `evaluar_examen.py`, `docker-compose.yml`, compilación aislada con `clean=False`
  y detección de líneas `!`. `SOURCE_DATE_EPOCH` desde `meta.fecha_iso`.
- Generación verificada: 20 `.tex` + 20 `.pdf`, 0 errores, 0 overfull.
  Determinismo comprobado: dos corridas dan sha256 idéntico.
- Escritas las capas 1 y 2: `directives/disenar_curso.yaml` y
  `flujo_disenar_curso.py` (run_state, verificación independiente de la entrega,
  códigos 1–5 clasificados, `--solo`, `--sin-compilar`, `--json`).
- Flujo probado de punta a punta: `status ok`, 20 `.tex`, 20 PDF,
  run_id `flujo-disenar-curso-20261101-113133`.
- Diagrama ISO 5807 de 4 páginas publicado en
  `docs/CYBERSEGURIDAD/disenar_curso_flujo.{tex,pdf}` (0 solapes, 0 errores).
- Reestructurado el descriptor a 10 semanas con fusión de bloques (decisión 8):
  semanas, fases, controles (4 × 2,5 = 10), evaluación final (4+3+2+1 = 10),
  pesos de curso y referencias cruzadas ("semana 6/11/12") actualizadas.
- Regenerado el material completo: 17 documentos (10 prácticas, 3 controles,
  evaluación final, sílabo, plan semanal y guía). Se borraron los artefactos
  obsoletos `practica_11..13.{tex,pdf}` de la versión de 13 semanas.
- Verificado: sílabo dice 10 semanas y escala 10 con mínimo 5; el plan semanal
  tiene 10 filas; controles cierran en 10,0; evaluación final 4/3/2/1 = 10,0.
  `verificar_pdf` en silabo (4 pág.), plan (5), practica_04 (3) y final (2):
  `status ok`, 0 solapes, 0 overfull.
- Determinismo revalidado tras el cambio: dos corridas de `--solo final` dan
  el mismo sha256 (`f6bb56d8…`).
- Auditoría parcial: `capas` = ok, `directivas` = aviso **preexistente**
  (9 referencias declaradas no implementadas en 8 directivas con `Status: planificado`;
  ninguna es la nueva).

## Pendientes
- Commit del trabajo (no se pidió explícitamente; queda en el working tree).
- Confirmar `nota_minima: 5` si la institución usa otro umbral de aprobación.
- Revisión de contenido por el docente: el YAML define temario y pesos; cualquier
  ajuste va al descriptor y se regenera.
- Prueba real del laboratorio (`docker compose up`) en hardware con RAM suficiente:
  no se levantó aquí por el límite de 3,63 GB.
- Añadir el curso al índice/README del repo si se quiere descubrible.
- Deuda ajena a esta sesión, no tocada: `passwords.txt` y `users.txt` trackeados en
  el repo origen; `cyber_env` inexistente pese a `.vscode/settings.json`.
