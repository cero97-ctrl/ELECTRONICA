# 2026-11-04 — practicas_reales_laboratorio_ii_fisica

## Tema
practicas_reales_laboratorio_ii_fisica

## Contexto
- El curso generado el 2026-11-02 (16 documentos) usaba datos de laboratorio
  plausibles pero inventados: apéndice 3 de instrumentos, valores de capacitores
  e inductancias, materiales y procedimientos de las prácticas 1–8.
- El usuario aportó la fuente real: `cursos/LABORATORIO_II_FISICA/docs/practicas.pdf`
  (escaneo de 56 páginas, Simple Scan 44.0, sin capa de texto, JPEG 2544×3508 a
  300 DPI; UDO Núcleo de Sucre, Prof. César Rodríguez, Cumaná, abril 2011).
- Las prácticas 1–4 existían además en LaTeX exacto en git HEAD (los 9 ficheros
  trackeados borrados del directorio del curso), así que la fuente quedó partida:
  HEAD para P1–P4, OCR del escaneo para P5–P8 y las tablas de componentes.

## Decisiones (usuario)
1. **Fuente = HEAD + OCR**: P1–P4 desde el `.tex` de git HEAD (exacto); el OCR del
   escaneo solo para lo que no estaba disponible (P5–P8, tablas de C y L, fichas
   de instrumentos). Páginas 3–25 del PDF no se OCR-earon a propósito.
2. **Autoridad híbrida**: del original se adoptan materiales, modelos de
   instrumento, procedimiento, número de datos y actividades; del curso generado se
   conservan la teoría, las incertidumbres y la estructura ya validadas.
3. **Semanas 9 y 10 intactas** (no corresponden a prácticas del documento real).
4. **Los añadidos propios se conservan como sección «Ampliación (opcional)»**
   (Zener/LED en P5, Thévenin/superposición en P4, factor de calidad en P7,
   balance de energía en P8): el alumno distingue lo obligatorio de lo complementario.
5. **Inventario de C y L SIN números de bienes**: se reproducen los valores medidos
   con una numeración de posición en la lista, declarada como tal en el apéndice.
6. (Heredada, vigente) Los 9 ficheros trackeados borrados **no se restauran**;
   leerlos con `git show HEAD:<ruta>` es aceptable y el volcado vive solo en
   `.tmp/fuente/`, nunca en `docs/`.

## Actividades
- Fase 0: `git show HEAD:...` → `.tmp/fuente/practicas_1_4.{tex,pdf,txt}` (1075 líneas).
- Fase 1: escrito `execution/ocr_pdf_escaneado.py` (capa 3: lotes, caché reanudable
  por hash del PDF, retry, corte por cuota, códigos 0/1/2/3/4/5) y ejecutado:
  10 peticiones, 0 páginas fallidas; cobertura 1–2 y 26–56; caché en
  `.tmp/ocr_practicas/.cache/86a5926a079f/textos/pagina_NNN.txt`.
- Transcripción: índice real, P5–P8, tabla 1 de capacitores (20 unidades), tablas
  2–3 de inductancias (3 y 5 terminales), fichas Keithley 175/175-A y 179/179-A.
- Inventario real de P1–P8 extraído y tabla de discrepancias presentada al usuario
  (11 filas); respondió con las decisiones 4 y 5.
- Generador (`execution/generar_material_curso.py`):
  - Campo nuevo `practica.ampliacion` → sección «Ampliación (opcional)» con icono
    `plus-circle`, con validación de lista de textos no vacíos.
  - Matemática en prosa: `_tm()` (conserva `$ \ _ ^ { }`, escapa `& # % ~ < >` con
    lookbehind idempotente para no duplicar un `\%` ya escrito) y
    `_validar_matematica()` (`$` pares, llaves balanceadas, `_`/`^` solo dentro de
    `$...$`), aplicados a objetivo, escenario, entregable, materiales, pasos,
    analisis, ampliacion, `tabla_datos.nota` y `apendices[].texto|tabla.nota`.
    Motivo: `_t()` imprimía `$V_C$` como dólares literales y un `\%` del docente se
    volvía `\\%` (salto de línea + comentario → «Command \item invalid in math
    mode» tres líneas más abajo).
  - `_tabla_columnas()` envuelve caption+tabla+nota en una `minipage`: sin ella el
    caption del apéndice de 18 filas del Keithley 175 quedaba huérfano en una
    página y la tabla en la siguiente.
  - Tests: `test_matematica_en_prosa` (+idempotencia de `\%`) → **52 aserciones OK**;
    `AGENTS.md` actualizado a 52.
- `directives/disenar_curso.yaml` v1.1: documentados `practica.ampliacion` y la
  matemática en línea de los campos de prosa.
- `curso.yaml`: semanas 1–8 reescritas con el contenido real (materiales, modelos
  Keithley, procedimientos con el número de datos del original, análisis con las
  linealizaciones reales, `ampliacion` donde aplica); apéndices 2–3 sustituidos por
  cinco apéndices reales (capacitores, inductancias de 3 y de 5 terminales,
  Keithley 175/175-A, Keithley 179/179-A) sin números de bienes; formulario del
  puente corregido a `$R_x = R_1 R_3 / R_2$`.
- Regeneración: `python3 flujo_disenar_curso.py --curso cursos/LABORATORIO_II_FISICA/curso.yaml --no-alert`
  → 16 `.tex` / 16 PDF, **0 líneas `!`, 0 `Overfull \hbox`, 0 `Overfull \vbox`,
  0 `\$` escapados**; determinismo comprobado (dos corridas `--sin-compilar`,
  16 `.tex` idénticos); verificación visual de páginas (P4 red de 2 mallas, P7
  `1/\sqrt{2}`, apéndices de C/L y Keithley).
- Procedencia: `cursos/LABORATORIO_II_FISICA/docs/practicas_ocr.md` generado desde
  la caché del OCR (33 páginas, sin edición manual) con cabecera de cobertura
  (1–2 y 26–56; 3–25 omitidas a propósito) y advertencia de que el OCR no es
  fuente de verdad tipográfica.
- Higiene: `flujo_auditar_repo.py --solo pdf_stale,directivas,capas,secretos` →
  `con_avisos`, 0 fallos; los 2 pares `.tex/.pdf` desfasados que aparecieron
  (`docs/AGENTE_IA/rea_evaluacion_incorporacion.*` y
  `docs/CYBERSEGURIDAD/disenar_curso_flujo.*`, preexistentes) se recompilaron con el
  patrón aislado de `.tmp/latex_build/` y `pdf_stale` quedó **limpio** (219/219).
  `execution/estado_sesion.py check` → ok.

## Pendientes
- Commit hecho al cierre de la reanudación: `499086b` (61 ficheros: curso,
  generador + tests, flujo OCR, bitácoras, `.agent/latex.md`), sin push. Quedó
  fuera a propósito el backlog de otras sesiones (cursos/CYBERSEGURIDAD,
  docs/CYBERSEGURIDAD, asignar_tareas, REA y sus Sessions), aún sin trackear.
- Auditoría completa (`flujo_auditar_repo.py` sin `--solo`) no se re-corrió tras el
  último cambio; las pasadas parciales (`pdf_stale,directivas,capas,secretos` y
  `capas,directivas`) dieron 0 fallos y el aviso de `directivas` es el histórico de
  capacidades `Status: planificado`.

## Actividades (reanudación)
- Cerradas las tres capas del flujo OCR, que había quedado como script huérfano:
  - Capa 1: `directives/ocr_pdf_escaneado.yaml` (Status: activo; SOP con modos
    `--check`/`--dry-run`, edge cases de cuota 429, capa de texto, marcas omitidas).
  - Capa 2: `flujo_ocr_pdf.py` (valida entradas, lanza la capa 3 como subproceso,
    valida el markdown página a página con `validar_entrega`, guarda la vista por
    corrida y alerta; no reintenta en bucle: el budget vive en la capa 3).
  - Capa 3 (test): `execution/test_ocr_pdf_escaneado.py`, 34 aserciones sin red
    (rangos de páginas, loteo, marcas `@@@PAGINA@@@`, aceptabilidad, budget 3,
    detección de cuota).
  - `AGENTS.md`: línea del test y del flujo en sus secciones.
- Verificado sin gastar cuota: `flujo_ocr_pdf.py --check` sobre `practicas.pdf`
  reporta 33/33 páginas en caché y 0 faltantes; `--dry-run` estima 0 peticiones.
- Auditoría `--solo capas,directivas`: 25/25 flujos con capa 3, 0 fallos; la
  directiva nueva cuenta como implementada.
- Al reanudar: auditoría completa (`flujo_auditar_repo.py`, 14 dimensiones) con
  0 fallos; commit A `fb72b83` (esta bitácora), commit B `2ed963b` (curso de
  ciberseguridad 10 semanas/escala 10 + `flujo_asignar_tareas` + sus 3 capas +
  diagrama + bitácoras 11-01/11-02 + 2 líneas de AGENTS.md), commit C `e4c0799`
  (informe REA `.tex/.pdf` + fuente + bitácoras 10-12/10-19). Push de los 4
  commits a `origin/master` (`7f114db..e4c0799`). Árbol de trabajo limpio.
