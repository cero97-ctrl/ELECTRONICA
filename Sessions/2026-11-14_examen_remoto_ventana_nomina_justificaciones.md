# 2026-11-14 — examen remoto ventana nomina justificaciones

## Tema
examen remoto ventana nomina justificaciones

## Contexto
- El examen de ciberseguridad (4 roles) se rinde **a distancia el 16-nov-2026,
  10:40–11:30 (UTC−4)** en lugar de en el aula. La versión anterior estaba
  publicada con entrega remota sin ventana, sin nómina y devolviendo la nota al
  navegador: con la prueba en casa eso permite entregar fuera de hora, entregar
  por otro y usar la nota como oráculo para probar respuestas.
- Objetivo declarado por el usuario: **minimizar el uso de IA**. La palanca no es
  prohibirla (no es verificable) sino pedir evidencia propia y hacerla barata de
  revisar: dos preguntas por cuestionario exigen justificar con archivo, línea,
  hash o salida de comando del repositorio del grupo.
- Se detectó además que las claves eran degeneradas (ROL LEGAL: 10 respuestas
  «A»), lo que hacía trivial acertar sin leer.

## Decisiones (usuario)
1. La prueba es remota, con ventana horaria y **un solo intento**.
2. La página **no devuelve la nota**; el alumno ve «Entrega registrada» y la nota
   sale en el acta.
3. **Nómina**: se valida inscripción, pero **no se inventa el mapeo
   cédula→grupo** (no existe en el repo). El alumno declara su grupo y el archivo
   se archiva en `grupo_<NN>`; la incoherencia se detecta en el acta.
4. `CEDULAS` va como **secreto** del Worker, no como `vars` (`wrangler.jsonc` es
   público).
5. Dos preguntas por cuestionario exigen justificación de evidencia; el mínimo es
   40 caracteres.
6. Las claves se barajan de forma determinista hasta dejar de ser degeneradas.

## Actividades
- **`execution/md_a_html.py`**: marcador `**Justificación:**` (regex + captura en
  fuente y respuestas), `MIN_JUSTIFICACION = 40`, `_items_justificacion()` que
  valida el front matter `justificacion_items` contra las preguntas que traen el
  marcador (falta/sobra/repite/inexistente/no entero → código 3), comparación en
  `_cruzar`, `cargar_clave()` devuelve `justificacion_items`, y el HTML del alumno
  renderiza un `textarea#j{n}` (`minlength=40`, `maxlength=1500`, `required`) con
  `const JUSTIFICAR`/`MIN_JUSTIFICACION` y conteo de `pegas`/`duracion_s`.
  Tests: **117/117** (antes 87).
- **`execution/dividir_cuestionario.py`**: emite `justificacion_items` en el front
  matter y la instrucción en la fuente; tests **56/56**.
- **`execution/barajar_cuestionario.py`** (nuevo): barajado determinista con
  semilla = nombre del archivo; remapea la letra de `**Answer:**` y las viñetas
  `- X ✓/✗`; `_verificar()` exige que no cambien enunciado, multiconjunto de
  opciones, texto de la respuesta correcta ni justificación. Claves resultantes:
  Rojo `C C C A D B B D D D`, Azul `B A C A D B C D B B`,
  Púrpura `B C C C C D A A B B`, Legal `B A C D A C D A D D`. Tests nuevos:
  **38/38**.
- **8 justificaciones escritas** en los 4 canónicos (Rojo 7,10 · Azul 4,9 ·
  Púrpura 5,10 · Legal 3,9), cada una pidiendo cita concreta del repositorio del
  grupo. Canónicos re-divididos y HTML regenerado (alumno + docente) y verificado:
  2 `textarea` por alumno, 0 `const CLAVE`, clave del docente = clave nueva.
- **Worker** (`src/logica.js`, `src/index.js`): cuerpo 16 KiB, validación de
  justificaciones (40..1500, sin claves de más), `duracion_s` 0..7200, `pegas`
  0..500, `ventana(ahora, inicio, fin)`, `cedulaInscrita()`, 403 fuera de ventana
  (antes de leer el cuerpo), 403 cédula no inscrita, **409 entrega duplicada**,
  respuesta `{recibido:true}` y `/salud` → `{ok, ventana, inscritas}`. Tests
  **32/32**.
- **`flujo_desplegar_worker_cuestionarios.py`**: nuevos `--nomina`, `--inicio`,
  `--fin`, `--min-justificacion`; `_leer_nomina()` normaliza igual que el Worker
  (TSV → `V-########`); sube los secretos `CEDULAS`, `ITEMS_JUSTIFICACION`,
  `VENTANA_INICIO`, `VENTANA_FIN`, `MIN_JUSTIFICACION` y los reporta.
- **`execution/descargar_resultados.py`**: `normalizar_justificaciones()`,
  `marcar_copias()` (difflib, umbral 0.85, marca **ambas** filas con la cédula de
  la otra), columnas `justificaciones`/`duracion_s`/`pegas` en el CSV y columna
  `J` con icono en el PDF (7 columnas). Una justificación ausente **no anula** la
  entrega: la nota vale y la fila queda `revisar`. Tests **96/96**.
- **Despliegue**: los 4 Workers redesplegados con nómina (8 cédulas) y ventana
  `2026-11-16T14:40:00Z`–`15:30:00Z`; `/salud` en los cuatro devuelve
  `{"abierta":false,"motivo":"todavía no empieza","inscritas":8}`; un POST real
  fuera de ventana devuelve 403 con ese motivo.
- Acta de prueba compilada (3 filas sintéticas): 0 errores `!`, 0 `Overfull
  \hbox` con la tabla de 7 columnas.
- **Verificación de coherencia clave/HTML/Worker**: `md_a_html.cargar_clave()`
  (fuente única) devuelve `justificacion_items` = [7,10] Rojo, [4,9] Azul,
  [5,10] Púrpura, [3,9] Legal y `entrega_url` de cada Worker; coincide con
  `const JUSTIFICAR` y con los `textarea#jN` de los 4 HTML publicados.
- **Matriz de `--check` del despliegue**: base = ROJO (sin `--env`), y
  `--env azul|purpura|legal` para el resto; las combinaciones cruzadas se
  rechazan (la barrera `CUESTIONARIO_ID` impide escribir una clave en el Worker
  de otro rol).
- **Publicado oculto**: `flujo_publicar_cuestionario.py --push` subió los 4
  `*_alumno.html` nuevos al repo privado; los blobs remotos coinciden byte a byte
  con los locales (`git hash-object` == sha del contenido remoto). Repo sigue
  `private: true`, `has_pages: false` → 404.
- **Bug encontrado y corregido**: `--push` sobre un repo privado abortaba con
  código 4 porque intentaba habilitar Pages (HTTP 422 «Your current plan does not
  support GitHub Pages») *después* de haber subido el contenido. Ahora ambos
  publicadores (`execution/publicar_cuestionario.py` y
  `execution/publicar_material_sara.py`, que comparte la mecánica) omiten Pages
  mientras el repo sea privado y no esperan el 200. Documentado en
  `directives/publicar_cuestionario.yaml`.
- Directivas actualizadas: `entregar_respuestas_worker.yaml`,
  `evaluacion_web.yaml`, `acta_cuestionario.yaml`.

## Pendientes
- **Publicar el día del examen (solo Ciberseguridad)**: el contenido nuevo ya
  está subido y oculto (repo privado, 404). ~10:15 (25 min antes) ejecutar
  `python3 flujo_publicar_cuestionario.py --visibilidad public`; recordar el
  `cache-control: max-age=600` del CDN y comprobar las 4 URLs en el navegador.
  **Alcance**: ese comando publica *un* curso —`--web-dir` por defecto
  `cursos/CYBERSEGURIDAD/evaluaciones/web`, `--repo` por defecto
  `cero97-ctrl/cuestionarios`—, no el repo entero. Hoy Ciberseguridad es la
  única carpeta `evaluaciones/web`, pero otro curso exigiría su propio
  `--web-dir` y su propio repo: el índice se genera con todos los
  `*_alumno.html` de la carpeta y la visibilidad es por repo, así que
  compartirlo mezclaría los cursos y ataría sus fechas de publicación.
- Probar una entrega real de punta a punta con la ventana abierta (o abriendo la
  ventana unos minutos) y borrarla después con `gh api -X DELETE`.
- Verificar que `ITEMS_JUSTIFICACION` del Worker coincide con el HTML publicado
  (los dos salen de la misma fuente, pero es la única pareja que puede divergir
  sin que nadie lo note).
- No tocado (ajeno a esta sesión): material de Sara (`SARA/`, `flujo_material_sara.py`),
  anteproyecto de Héctor (`cursos/TESIS/HECTOR/`).
