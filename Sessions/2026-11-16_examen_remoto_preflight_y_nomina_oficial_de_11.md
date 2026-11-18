# 2026-11-16 — examen remoto preflight y nomina oficial de 11

## Tema
Examen remoto del 16-nov: pre-flight de la mañana, nómina oficial y redespliegue
de los cuatro Workers con los 11 alumnos inscritos.

## Contexto
- Pre-flight a las 06:16 (solo lectura): los 4 Workers respondían `ok:true`,
  `abierta:false` («todavía no empieza») e `inscritas: 8`; los 4 HTML
  `*_alumno.html` estaban presentes y apuntando al Worker correcto (rojo=base,
  azul/púrpura/legal con su `-<grupo>`); la página seguía en **404** por repo
  privado, como se esperaba hasta las 10:40; git solo tenía cambios de otras
  sesiones.
- Al organizar los grupos, el usuario aportó 9 alumnos y el cruce contra
  `alumnos_cyberseguridad.csv` (8 filas) mostró 3 discrepancias: DIAZ BOADA
  (31764504) y RODRIGUEZ NUÑEZ (29855978) no estaban en la nómina, y CABALLERO
  BARRETO (31604601) estaba sin grupo.
- La fuente oficial es `cursos/CYBERSEGURIDAD/listado_alumnos.pdf` (imprimir del
  sistema): tiene **11 alumnos**, todos `OK/inscrito`, e incluye a ALFONZO REYES
  (31157199), que no estaba en la nómina, ni en la lista del usuario, ni en
  ningún Worker.

## Decisiones (usuario)
1. DIAZ BOADA y RODRIGUEZ NUÑEZ **sí están inscritos**: añadirlos a la nómina y
   redesplegar antes de las 10:40.
2. CABALLERO BARRETO va en el **grupo 3** (Púrpura).
3. ALFONZO REYES va en el **grupo 4** (Legal).
4. La lista oficial es `listado_alumnos.pdf` (11 alumnos).
5. Mantener **la lista completa de 11 en los 4 Workers** (no lista estricta por
   grupo): si un alumno se equivoca de enlace, igual puede entregar; se prefiere
   no arriesgar un 403 hoy.

## Actividades
- `cursos/CYBERSEGURIDAD/evaluaciones/alumnos_cyberseguridad.csv` reescrito con
  los 11 del PDF (TSV, cédula/apellidos/nombres; gitignored). `_leer_nomina`
  devuelve **11** cédulas `V-...`.
- Los **4 Workers redesplegados** con `--nomina` y **sin** `--inicio/--fin`
  (el flujo omite los secretos vacíos, así que la ventana 10:40–11:35 local se
  conservó): base/rojo, `--env azul`, `--env purpura`, `--env legal`; los siete
  secretos `ok` en cada uno.
- Verificado: `/salud` de los 4 → `ok:true`, `abierta:false` («todavía no
  empieza»), **`inscritas: 11`**.
- Listas por grupo en `.tmp/grupo_{1..4}.csv` (cabecera `grupo,cedula,nombre`):
  G1 2 (PAREJO, DIAZ), G2 3 (DELGADO, LÓPEZ, ZAPATA), G3 3 (VELASQUEZ FARIÑAS,
  MARQUEZ, CABALLERO), G4 3 (CAÑA, RODRIGUEZ NUÑEZ, ALFONZO). `leer_lista` sin
  problemas; **11 únicas** y el conjunto coincide exactamente con el secreto
  `CEDULAS` (0 faltan, 0 sobran).
- `listado_alumnos.pdf` queda **untracked** y contiene cédulas y correos: no
  debe commitearse (repo público). Añadido a `.gitignore`
  (`cursos/*/listado_*.pdf`, línea 87) y verificado con `git check-ignore -v`.
- **10:30 pre-flight repetido** justo antes de publicar: los 4 `/salud` →
  `abierta:false` («todavía no empieza»), `inscritas:11`; los 4 HTML apuntan al
  Worker de su grupo (rojo=base, azul/púrpura/legal con `-<grupo>`).
- **Publicado** con `python3 flujo_publicar_cuestionario.py --push
  --visibilidad public` → repo `cero97-ctrl/cuestionarios`, stage
  `.tmp/publicacion/cuestionarios`, 4 archivos con sha256, `publicado:true`,
  `pages_visible:true`. El **primer intento** falló con
  `FALLA: unexpected end of JSON input` (error transitorio de un `gh api`); el
  reintento con `--json` salió verde.
- Verificación externa: índice y los 4 `*_alumno.html` → **200**; ninguna
  variante alumno contiene `const CLAVE`, `**Answer:**` ni `Modo docente`.
- **Incidencia durante el examen (resuelta)**: Lorena Zapata (31686438, G2 Azul)
  no podía enviar; terminó enviando. Su entrega está en
  `resultados/rol_azul_cuestionario/grupo_02/V-31686438.json` con **10
  respuestas**, justificaciones de las preguntas 4 (57 car.) y 9 (87 car.),
  `grupo:2`, `duracion_s:2105`. Causa más probable: el botón queda **deshabilitado**
  hasta que hay 10 respuestas y las justificaciones del grupo llegan a
  **40 caracteres** (`JUSTIFICAR`: Rojo 7 y 10 · Azul 4 y 9 · Púrpura 5 y 10 ·
  Legal 3 y 9); las textareas cortas se marcan en naranja pero no hay texto que
  explique el bloqueo. Los 3 alumnos de Azul ya tienen entrega (LÓPEZ 624 B,
  ZAPATA 603 B, DELGADO 741 B).

## Pendientes
- **10:30** repetir pre-flight (`/salud` ×4 → `abierta:false`, `inscritas:11`).
- **10:38** ~~publicar~~ **hecho**: repo público y 4 HTML en 200.
- **10:40** enviar el WhatsApp de apertura (mensaje en la bitácora del 15-nov,
  sección «Mensaje de WhatsApp (para enviar a las 10:40)»).
- **11:35** `--visibilidad private`.
- **11:40** actas con `--lista .tmp/grupo_N.csv` (una por grupo), salida por
  defecto en `evaluaciones/resultados/acta_<slug>.csv`.
- Decidir si `listado_alumnos.pdf` entra en `.gitignore` para que no se commitee
  por accidente (contiene datos personales).

## Cierre del examen y acta consolidada de la semana (11:35–12:05)
- **11:35 cierre**: `--visibilidad private` → repo privado; índice y los 4
  `*_alumno.html` responden **404**; los 4 `/salud` dan `abierta:false`,
  `motivo:"ya terminó"`, `inscritas:11`.
- **Actas por grupo** en `cursos/CYBERSEGURIDAD/evaluaciones/resultados/`
  (9 entregas de 11): Rojo 2/2 (10.00, 10.00) · Azul 3/3 (10, 10, 9) ·
  Púrpura 3/3 con **3 filas `revisar`** (justificación de la pregunta 10 casi
  idéntica entre VELASQUEZ 10.00, CABALLERO 10.00 y MARQUEZ 7.00;
  `justificaciones: copiada`) · Legal 1/3 (RODRIGUEZ NUÑEZ 9.00).
- **Faltantes de Legal**: ALFONZO REYES V-31157199 y CAÑA VELASQUEZ V-31157564.
  Sin corte eléctrico reportado, la contingencia del 17-nov no aplica salvo que
  presenten una falla verificable.
- **Acta consolidada pedida por el profesor**: se alertó que generarla a mano
  violaba el determinismo (se repetirá cada semana) y se acordó extender el flujo
  existente en sus 3 capas:
  - **Capa 3**: `execution/acta_semana.py` — une los `acta_*.csv` por cédula
    normalizada, ordena por `(grupo, cédula)`, calcula faltantes desde las
    nóminas (`--lista` repetible), reutiliza `latex_acta` + `_compilar_pdf` y
    escribe `<resultados>/SEMANA_NN/acta_semana_NN.{tex,pdf}`.
  - **Capa 2**: `flujo_acta_cuestionario.py --consolidar --semana N
    [--listas-dir DIR] [--salida-dir DIR] [--curso X]` — verifica `.tex`
    cerrado con `\end{document}`, PDF > 2 KB y `entregas` reportado.
  - **Capa 1**: sección `consolidar_semana` en `directives/acta_cuestionario.yaml`.
  - **Test**: `execution/test_acta_semana.py`, **44/44**, sin red ni pdflatex.
- **Entregable**: `evaluaciones/resultados/SEMANA_01/acta_semana_01.{tex,pdf}`
  — 9 entregas, G1 2 · G2 3 · G3 3 · G4 1, 3 filas a revisar, 2 faltantes,
  `verificar_pdf.py`: 0 errores `!`, 0 `Overfull \hbox`, 0 solapes, 1 página.
  El `.tex` es determinista (mismo sha256 en dos corridas).
- Regresión comprobada: `test_descargar_resultados.py` 96/96.

## Corrección del acta: el ⚠ no siempre significa «la nota no cuadra»
- El profesor preguntó qué significaba el ⚠ del pie. Se revisó el código: el pie
  decía «difieren de la nota que devolvió el Worker», pero las 3 filas de Púrpura
  tienen `nota == nota_recalculada`; están marcadas por `marcar_copias`
  (justificación de la pregunta 10 ≥85 % idéntica entre los tres). El motivo real
  (`avisos`) vivía solo en el CSV, así que el PDF no era autoexplicativo.
- Arreglado en `latex_acta` (`execution/descargar_resultados.py`):
  - Pie corregido: ⚠ = nota/`aciertos` que no cuadran, **o** justificación
    incompleta **o** coincidente con la de otro alumno.
  - Caja «A revisar a mano» con cédula, nombre y motivo de cada fila (acepta
    `avisos` como lista o como el string unido con `;` que trae el CSV, con
    fallback a `justif_estado`).
- `test_acta_semana.py`: 52/52 (8 aserciones nuevas sobre la caja y el pie);
  `test_descargar_resultados.py` sigue 96/96.
- `acta_semana_01.pdf` regenerado: 2 páginas, caja con los 3 motivos,
  `verificar_pdf.py` → 0 errores `!`, 0 overfull, 0 solapes.

## El ⚠ de Púrpura era un falso positivo: ítems de evidencia exentos
- Se compararon las justificaciones de la pregunta 10 de Velásquez, Márquez y
  Caballero: **son idénticas byte a byte** (1292 car., `ratio=1.000`), pero la
  pregunta pide literalmente «muestra el árbol real de tu repositorio para la
  semana 1». Es el mismo repo del grupo en los tres casos: el texto idéntico es
  lo esperado, no una copia. La pregunta 5 sí difiere (509/765/868 car.).
- Se descartó re-corregir a mano: la nota era correcta (10/10/7) y lo que
  mentía era la señal. Arreglo en la regla, no en los datos.
- **Regla nueva (`justificacion_evidencia`)**: subconjunto de
  `justificacion_items` cuyos ítems quedan exentos de `marcar_copias` (igualdad
  y similitud). Debe ser subconjunto: eximir una pregunta que no exige
  justificación es un error (código 3).
  - `execution/md_a_html.py`: `_items_evidencia()` + validación en `validar()`
    y exposición en `cargar_clave()`.
  - `execution/descargar_resultados.py`: `marcar_copias(..., evidencia=())`.
  - `execution/dividir_cuestionario.py`: `_evidencia_canonica()`, propagación en
    `dividir()` y comprobación de ida y vuelta en `_verificar()`.
- **Datos**: `justificacion_evidencia: [10]` en la fuente de Púrpura y en su
  canónico (git-ignored). La huella depende solo de las preguntas, así que el
  HTML publicado y los borradores locales no cambian y el Worker no se toca.
- **Pie del acta**: la remisión a la caja «A revisar a mano» ahora es
  condicional; sin filas revisables el pie no menciona una caja que no existe.
- **Tests**: `test_md_a_html.py` 179/179 · `test_descargar_resultados.py`
  100/100 · `test_dividir_cuestionario.py` 59/59 · `test_acta_semana.py` 54/54 ·
  `test_barajar_cuestionario.py` 38/38 · `test_publicar_cuestionario.py` 36/36.
- **Actas regeneradas**: Púrpura `a_revisar: 0` (10/10/7) y consolidada
  `SEMANA_01` 9 entregas, `a_revisar: 0`, sin caja, 1 página,
  `verificar_pdf.py` limpio y `.tex` determinista (mismo sha256 en dos corridas).

## Nombres corregidos en las entregas archivadas
- El acta muestra el nombre que el alumno escribió en el formulario, no el de la
  nómina, así que dos entregas salían con el nombre mal escrito. Se corrigió la
  fuente de verdad —el JSON archivado en el repo privado
  `cero97-ctrl/cuestionarios-resultados`— con la API de contenidos, cambiando
  solo la línea `"nombre"` (el resto del archivo, byte a byte):
  - `V-31686569` · `victor marquez` → `Víctor Márquez` (`7df822ad`, acentos en `32adbbb1`).
  - `V-29855978` · `Juan Rodroguez` → `Juan Rodríguez` (`d6947923`).
- Actas de Púrpura y Legal regeneradas y consolidada `SEMANA_01` (9 entregas,
  `a_revisar: 0`); `verificar_pdf.py` limpio en las tres y `.tex` determinista
  (mismo sha256 en dos corridas). La nómina oficial ya tenía los nombres
  correctos: no se tocó.
