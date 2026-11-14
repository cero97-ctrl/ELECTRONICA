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

- **Consulta al repositorio durante el examen**: permitida y prevista. La página
  no bloquea la navegación (no hay detector de ventanas ni de foco); lo que se
  evalúa es que citen su propia evidencia, y las consignas ya lo piden («Cita el
  archivo de hashes de tu grupo», «Pega la línea de tu propia salida de `grep`»).
  Los repos de grupo son **privados**, así que necesitan su sesión de GitHub en
  la otra ventana.
- **Protección contra cortes de luz: opción C** (aviso + `beforeunload` +
  borrador en `localStorage`), elegida por el usuario «porque en Venezuela
  tenemos actualmente problemas con el fluido eléctrico». Se descartaron A (solo
  cartel) y B (cartel + aviso al salir) por no sobrevivir a un apagón.
- **El aviso de material va solo en el examen remoto** (variante alumno con
  `entrega_url`): en el laboratorio el docente está presente y decirlo por
  escrito sería ruido.
- **Se les dice que copiar y pegar queda anotado** (`pegas`), para que peguen la
  evidencia real en vez de reescribirla de memoria y que el acta pierda valor.
- **El borrador caduca a las 24 h** (`BORRADOR_CADUCIDAD_HORAS`): dato personal
  en un PC que puede ser prestado.
- **Al recargar tras enviar**: mensaje «Entrega registrada» con nombre, cédula y
  hora, **sin** mostrar sus respuestas; el registro guardado no lleva el examen
  resuelto.
- **Aviso visible si la huella no coincide** (cuestionario regenerado después de
  que un alumno ya lo abrió).
- **E2E con Worker de pega** autorizado y ejecutado antes de publicar.

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

- **Borrador local del examen remoto** en `execution/md_a_html.py`:
  `_huella_cuestionario()` (12 hex de SHA-256 sobre número, enunciado y
  opciones; sin respuestas ni instrucción de justificación), `_aviso_material()`,
  CSS `.aviso-material`/`.borrador-estado` (ocultos en `@media print`), y
  `_js_alumno(..., huella=)` con `guardar/leerBorrador/restaurar/`
  `marcarEntregado/guardarEntregado/hayBorrador/decirBorrador/sinAlmacen`,
  `beforeunload`, `let inicio` y hooks de guardado en `change`/`input`/`paste`.
  `_render_alumno` inserta el aviso y pasa la huella solo si hay `entrega_url`.
- Tests del conversor: **117 → 168** aserciones (`test_aviso_material`,
  `test_borrador_autoguardado`, `test_huella_determinista`). El único fallo
  inicial era del test, no del código: `FUENTE` y `FUENTE_JUST` comparten
  enunciado y opciones, y la huella excluye a propósito la justificación; se
  sustituyó por el caso real (opciones barajadas → otra huella).
- **E2E en Chrome headless real** contra un Worker de pega (`.tmp/e2e/`:
  `stub_worker.py` con CORS y archivo de cuerpos, `build.py`, `extra.py`,
  servidor estático en :8000, perfil persistente en `/tmp/chrome-*`), usando el
  cuestionario real del ROL ROJO con `entrega_url` apuntando al stub:
  - fase 1: responde 2 preguntas y una justificación → borrador escrito con la
    clave `cuestionario.v1.rol_rojo_cuestionario.29d1575d6768`, preguntas fijadas.
  - fase 2 (recarga): restaura datos, respuestas **y candados** (`disabled`,
    `bloqueada`), justificación, `pegas: 1` e `inicio`; aviso «Borrador
    restaurado (guardado a las 10:49:03 a. m.)».
  - fase 3 (retoma y envía): el stub recibe las 10 respuestas, 2 justificaciones,
    `duracion_s: 101` (**desde la primera carga**, no desde la recarga) y
    `pegas: 1`; el registro guardado queda sin `respuestas` ni `justificaciones`.
  - fase 4 (recarga tras enviar): «Entrega registrada a nombre de Ana Prueba
    (C.I. V-12345678) el 14/11/2026, 10:50:45 a. m.», **0 controles habilitados**,
    sin respuestas visibles.
  - rama caducidad (borrador de 25 h): «El borrador anterior tenía más de 24
    horas y se descartó», y desaparece de `localStorage`.
  - rama huella distinta: «El cuestionario cambió desde tu última visita: el
    borrador anterior no aplica».
  - Efecto colateral comprobado: el candado sobrevive a la recarga, así que
    recargar ya no sirve para re-responder (antes sí).
- Regenerados los 4 `_alumno.html` con `flujo_evaluacion_web.py --variantes
  alumno`: 4 huellas distintas (Rojo `29d1575d6768`, Azul `63a8eecbb2a9`,
  Púrpura `767810e236b2`, Legal `e58731fcd649`), un aviso por página, 0
  `const CLAVE`, `JUSTIFICAR` intacto ([7,10] / [4,9] / [5,10] / [3,9]).
  `node --check` del JS extraído: válido.
- Directivas: `evaluacion_web.yaml` (bloque `contract.borrador` y 4 casos límite
  nuevos) y `entregar_respuestas_worker.yaml` (`duracion_s` y `pegas` se miden
  desde la primera carga). `AGENTS.md`: 117 → 168 aserciones.
- Verificado que el `index.html` **local** enlaza a la variante docente (carpeta
  gitignored, es el índice del profesor) mientras que el publicado lo genera la
  capa 3 sin docente, que es lo que cubre `test_publicar_cuestionario` (23/23).
- Commit de la tarea anterior revisado y autorizado por el usuario; al prepararlo
  se detectó y corrigió una fuga (cédulas reales de la nómina en fixtures y en un
  ejemplo de la directiva) y se añadió `cursos/*/evaluaciones/alumnos_*.csv` a
  `.gitignore`.

## Pendientes
- **Volver a publicar el HTML** (`python3 flujo_publicar_cuestionario.py --push`):
  la versión subida al repo privado es la anterior al borrador. El repo sigue
  privado, así que publicar no lo hace visible.
- **Publicar el día del examen (solo Ciberseguridad)**: ~10:15 (25 min antes) ejecutar
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
- **No re-barajar ni regenerar el cuestionario después de publicar**: cambia la
  huella y los borradores de quien ya abrió la página se descartan (avisan, pero
  pierden lo respondido).
- Si se toca el JS del alumno, repetir dos comprobaciones baratas: `node --check`
  del `<script>` extraído y el E2E de `.tmp/e2e/` (se regenera con `build.py` y
  `extra.py`; requiere `google-chrome` y dos servidores locales).
- No tocado (ajeno a esta sesión): material de Sara (`SARA/`, `flujo_material_sara.py`),
  anteproyecto de Héctor (`cursos/TESIS/HECTOR/`).
