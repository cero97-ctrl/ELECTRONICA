# 2026-11-18 — cuestionario web laboratorio ii fisica

## Tema
Generar las páginas HTML del cuestionario de **Laboratorio II de Física** (variantes
alumno y docente) replicando el pipeline de Laboratorio I y Ciberseguridad, y desplegar
el Worker de entregas para los 3 grupos.

## Contexto
- El canónico del banco (`evaluaciones/web/fuentes/lab_ii_fisica_cuestionario.md`) trae
  la clave dentro con etiquetas **en español** (`**Respuesta:**`, `**Pista:**`,
  `**Explicación:**`) y sin front matter.
- `execution/md_a_html.py` solo reconoce `**Answer:**` / `**Hint:**` / `**Explanation:**`.
  Una etiqueta desconocida **no falla**: `_parsear_cuestionario()` pega la respuesta, la
  pista y la explicación al texto de la última opción, y `--check` seguía devolviendo
  `ok` con `tiene_clave: false`. Era una fuga silenciosa de la clave al HTML del alumno.
- La clave del banco era degenerada: las 10 respuestas correctas eran `A`.
- En Lab I esa traducción ES→EN y el título humano se hicieron **a mano**, así que no
  eran reproducibles.

## Decisiones (usuario)
1. **MathJax por CDN** (1a): el HTML deja de ser «sin red»; se acepta el CDN de MathJax
   como única URL externa, porque sin él la matemática se lee `$R = V/I$` en crudo y el
   alumno ya necesita internet para entregar. Se descartó auto-hospedar ~1,5 MB.
2. **Barajar la clave degenerada** (2a) con `execution/barajar_cuestionario.py`.
3. **Título**: «Lab II de Física - Características I-V» (no el «Electricidad Cuestionario»
   del banco).
4. **Desplegar también el Worker** (4b) para que los 3 alumnos entreguen en línea.
5. Ventanas de examen (9a): **Lab II el martes 24-nov-2026, 08:00–09:00 VET** y
   **Lab I el jueves 26-nov-2026, 08:00–09:00 VET** (60 min cada uno; VET = UTC−4, sin
   horario de verano → `12:00Z–13:00Z`).
6. Nómina: las 3 cédulas del archivo son **todos** los alumnos.
7. Repo de resultados: crear `cuestionarios-resultados-lab2` **privado**.
8. Publicación del HTML: en GitHub Pages con **visibilidad privada** (404 hasta el día
   del examen).

## Actividades
- **MathJax fijado como contrato**, no como parche suelto: docstring de `md_a_html.py`,
  `directives/evaluacion_web.yaml` (goal, expected_outputs, security) y
  `test_md_a_html.py` (helper `_red_externa()` que tolera solo el CDN). `180/180`.
- **`dividir_cuestionario.py` extendido** con `ETIQUETAS` ES→EN (contadas en
  `normalizaciones`) y `--titulo` (título del front matter separado del `# ...` interno,
  que es el nombre del banco). Tests nuevos: etiquetas ES y título separado → `69/69`.
- **Cadena real ejecutada**:
  1. `cp lab_ii_fisica_cuestionario.md → _origen.md` (evidencia intacta del banco).
  2. `dividir_cuestionario.py --canonico _origen.md --titulo "Lab II de Física -
     Características I-V" --curso LABORATORIO_II_FISICA --grupos 3` → **36
     normalizaciones** (30 etiquetas + 6 puntos y coma de ancho completo), clave
     `A A A A A A A A A A`.
  3. `barajar_cuestionario.py` (semilla = nombre del archivo, determinista) → clave
     `A D D B D A B A A B` (A×4, B×3, D×3, C×0); `clave_despues_degenerada: false`.
  4. Re-división desde el canónico barajado → fuente sin clave, `normalizaciones: 0`.
  5. `flujo_evaluacion_web.py --fuente .../lab_ii_fisica_cuestionario.md` → HTML alumno,
     docente e `index.html`.
- **Verificación**: alumno con 0 ocurrencias de `const CLAVE`, `Answer:`, `Respuesta:`,
  `Pista:`, `Explicación:`, `✓`, `✗`, `Modo docente`; 10 preguntas; 1 sola URL externa
  (MathJax). Docente con `const CLAVE` de 10 entradas y la clave barajada. Las 10
  marcas `✓` apuntan a la letra correcta.
- **Entorno `lab2`** añadido a `Proyectos/cuestionarios-worker/wrangler.jsonc`
  (`cuestionarios-worker-lab2`, `GRUPOS: 3`, `CUESTIONARIO_ID:
  lab_ii_fisica_cuestionario`) sin tocar el `lab1` que el usuario tenía sin commitear.
  `--check` en verde (dry-run de wrangler OK).
- **Repo `cero97-ctrl/cuestionarios-resultados-lab2` creado privado**; el usuario creó
  un PAT fine-grained con acceso a los tres repos de resultados.
- **`_token_resultados(env)`**: el flujo ahora prefiere
  `GITHUB_TOKEN_RESULTADOS_<ENTORNO>` (mayúsculas, `-` → `_`) y cae al genérico. El
  usuario guardó el token como `GITHUB_TOKEN_RESULTADOS_LAB_II`, que **no** coincide con
  la clave del entorno (`lab2`); se renombró a `GITHUB_TOKEN_RESULTADOS_LAB2`
  conservando el valor. Verificado por hash: `--env lab2` resuelve el token nuevo,
  `--env lab1`/`azul`/sin entorno siguen con el de siempre (sin regresión).
  Directiva `entregar_respuestas_worker.yaml` actualizada con la convención.
- **Despliegue hecho** (`--env lab2 --inicio 2026-11-24T12:00:00Z --fin
  2026-11-24T13:00:00Z --actualizar-fuente`): Worker
  `https://cuestionarios-worker-lab2.cero-agents.workers.dev`, `salud: true`, secretos
  `CLAVE_JSON`/`GITHUB_TOKEN`/`CEDULAS`/`VENTANA_INICIO`/`VENTANA_FIN`/
  `MIN_JUSTIFICACION` presentes (`ITEMS_JUSTIFICACION` vacío porque el cuestionario no
  pide justificaciones). `entrega_url` escrito en la fuente.
- **Smoke test real del Worker**: `/salud` → `{"ok":true,"ventana":{"abierta":false,
  "motivo":"todavía no empieza"},"inscritas":3}`; `POST` con cédula inscrita y clave
  completa → **403 fuera de la ventana** (no archiva nada, la validación va antes del
  `guardarEnRepo`).
- **HTML regenerado** con `entrega_url`: el alumno lleva `const ENTREGA_URL`, 10
  preguntas, `JUSTIFICAR = []` y **0 fugas** (`const CLAVE`, `Answer:`, `Respuesta:`,
  `Pista:`, `Explicación:`, `✓`, `✗`, `Modo docente`); las dos únicas URLs externas son
  MathJax y el Worker.
- **Colisión de publicación detectada antes de publicar**: `cero97-ctrl/cuestionarios`
  ya contiene los 4 cuestionarios de roles y `publicar_git()` hace `git init` + `add -A`
  + `push --force`, así que publicar ahí los habría borrado. El usuario eligió repo
  aparte → **`cuestionarios-lab2` privado**, con solo `.nojekyll`, `index.html` y
  `lab_ii_fisica_cuestionario_alumno.html` (sha256 idéntico al local:
  `2558e1dd…`), `pages_visible: false` (404 hasta el día del examen) y los roles
  intactos (6 ficheros).
- **`execution/test_desplegar_worker.py`** nuevo (13 aserciones): fija la precedencia
  `GITHUB_TOKEN_RESULTADOS_<ENTORNO>` → genérico, que un token en blanco no cuenta, que
  el `GITHUB_TOKEN` general nunca se usa, y que `main()` pasa `args.env`. Documentado en
  `AGENTS.md`. El fallo que previene es silencioso: un token del curso equivocado
  despliega en verde y solo revienta en la primera entrega.
- **Nombres del `.env` corregidos** (el sufijo `_1` era un préstamo del nombre genérico,
  no una convención): `GITHUB_TOKEN_RESULTADOS` volvió a llevar el token de
  ciberseguridad (el que abren los 4 roles), `GITHUB_TOKEN_RESULTADOS_1` pasó a
  `GITHUB_TOKEN_RESULTADOS_LAB1` con el token de Lab I, y `_LAB2` se quedó. Verificado
  por hash: ningún valor cambió de dueño. Antes del cambio, los cuatro roles de
  ciberseguridad leían el nombre genérico con el token de **Lab I**, que no abre su repo
  (404): un redespliegue habría salido en verde y fallado en la primera entrega.
- **`execution/token_resultados.py`** nueva capa 3: una sola regla para nombrar la
  variable (`variable(sufijo)`, `sufijo_de_repo(repo)`), compartida por el despliegue del
  Worker (elige por `--env`) y por el acta (elige por `--repo`), para que el mismo curso
  no despliegue con un token y lea con otro.
- **El acta deriva el token del repo**: `descargar_resultados.py` ya no tiene un default
  fijo (`GITHUB_TOKEN_RESULTADOS`) sino que lo calcula del sufijo del repo
  (`...-resultados-lab2` → `_LAB2`); `--token-env` sigue mandando. Tests nuevos en
  `test_descargar_resultados.py` (100 → **109 aserciones**): derivación por repo, repo
  ajeno sin sufijo, override explícito, y que `main()` pida la variable correcta y la
  nombre en el error sin tocar la red.
- **Paridad de Lab I con Lab II** (el usuario detectó que a Lab I le faltaban «Antes de
  empezar» y el botón de envío): no era un descuido de la plantilla, ambos bloques están
  condicionados a `entrega_url` (`_aviso_material` y `_entrega_alumno` en `md_a_html.py`),
  y el docstring de `_aviso_material` explica por qué: ese texto habla de repositorio,
  borrador y evidencia, o sea de examen remoto. La infraestructura de Lab I estaba a
  medio camino (`env.lab1` y repo de resultados creados, Worker **no** desplegado, sin
  `entrega_url`).
- **Worker de Lab I desplegado**: `cuestionarios-worker-lab1.cero-agents.workers.dev`
  (`--env lab1`, nómina de 2 alumnos, `--actualizar-fuente`). Después se fijó su ventana
  (ver más abajo) y `/salud` quedó en `{"ok":true,"ventana":{"abierta":false,
  "motivo":"todavía no empieza"},"inscritas":2}`.
- **HTML de Lab I regenerado** con `entrega_url`: ahora tiene el bloque «Antes de
  empezar», el botón «Enviar mis respuestas», 0 fugas de clave y solo dos URLs externas
  (MathJax + Worker de lab1).
- **Lab I publicado en su propio repo** `cero97-ctrl/cuestionarios-lab1` (privado), para
  que cada curso tenga su URL y el índice de uno no liste el otro:
  `.../cuestionarios-lab1/` (Lab I) y `.../cuestionarios-lab2/` (Lab II), cada uno con
  `.nojekyll`, `index.html` y **solo** su `*_alumno.html`. El repo de Lab II quedó
  intacto. Los dos HTML viejos duplicados (`cuestionario_lab_i_fisica_*`, corrida de las
  12:26) se movieron a `.tmp/lab1_html_duplicados/` para que el publicador no los
  subiera como segunda versión.

## Pendientes
- **Ventanas fijadas como secretos del Worker** (la fuente de verdad es el Worker, no un
  archivo duplicado). `--inicio/--fin` se escriben tal cual en `VENTANA_INICIO`/`VENTANA_FIN`
  (`extras` del flujo), así que el valor del comando es el valor desplegado:

  | Curso | Fecha (VET) | ISO UTC | Worker | `/salud` hoy |
  |---|---|---|---|---|
  | Lab II | martes 24-nov-2026, 08:00–09:00 | `2026-11-24T12:00:00Z`–`2026-11-24T13:05:00Z` | `cuestionarios-worker-lab2` | `abierta:false, "todavía no empieza", inscritas:3` |
  | Lab I | jueves 26-nov-2026, 08:00–09:00 | `2026-11-26T12:00:00Z`–`2026-11-26T13:05:00Z` | `cuestionarios-worker-lab1` | `abierta:false, "todavía no empieza", inscritas:2` |

  VET es UTC−4 todo el año (Venezuela no aplica horario de verano), de ahí las 12:00Z.
  El cierre lleva los **5 minutos de holgura** que exige la directiva
  (`entregar_respuestas_worker.yaml`): 60 min de examen + 5 de margen para que Pages
  sirva la página y quien entra a las 08:00 tenga la hora completa; la duración del
  examen sigue siendo 60 min. Los límites son **inclusivos** (`t < desde` / `t > hasta`
  en `logica.js`). `date -d` confirmó que 24-nov-2026 es martes y 26-nov-2026 es jueves.
  Re-desplegar con otros `--inicio/--fin` cambia la ventana sin tocar código; sin
  `--nomina` el secreto `CEDULAS` persiste (se comprobó: `inscritas` sigue en 3 y 2).
- **El día de cada examen**: el repo de ese curso está **privado** → Pages responde 404.
  Hay que pasarlo a público (y volver a privado al cerrar), **solo el del examen que toca**:
  ```bash
  # Lab II, 24-nov
  python3 flujo_publicar_cuestionario.py --web-dir cursos/LABORATORIO_II_FISICA/evaluaciones/web \
    --repo cero97-ctrl/cuestionarios-lab2 --visibilidad public --push
  # Lab I, 26-nov
  python3 flujo_publicar_cuestionario.py --web-dir cursos/LABORATORIO_I_FISICA/evaluaciones/web \
    --repo cero97-ctrl/cuestionarios-lab1 --visibilidad public --push
  ```
  Al cerrar, el mismo comando con `--visibilidad private`. Como son repos separados,
  publicar uno no expone el otro.
- **El HTML no muestra la fecha del examen**: el bloque «Antes de empezar» es genérico
  (repo, borrador, evidencia) y no imprime día ni hora. Si se quiere que el alumno lo lea
  en la página, hay que añadir la ventana al front matter y al generador; hoy se avisa por
  el canal del curso.
- Tras cada examen: descargar entregas y armar el acta con
  `flujo_acta_cuestionario.py` (repos `cuestionarios-resultados-lab2` / `-lab1`).
- **Riesgo corregido**: `cuestionarios-resultados-lab1` pasó de público a privado
  (estaba vacío y sin Pages; no quedó nada servido).
- **`.env` ya no tiene variables muertas**: `GITHUB_TOKEN_RESULTADOS` (cyber),
  `GITHUB_TOKEN_RESULTADOS_LAB1` y `GITHUB_TOKEN_RESULTADOS_LAB2` son las tres que lee
  el código. `GITHUB_TOKEN` (ghp_, 40 chars) sigue **caducado** (401 en los tres repos) y
  ningún flujo lo usa.
- Sin commitear a propósito: `Sessions/2026-11-06_curso_laboratorio_ii_fisica.md`
  (acuerdo previo), `cursos/LABORATORIO_I_FISICA/ALUMNOS_LAB_I_FISICA.pdf` (trabajo del
  usuario) y los HTML/fuentes de Lab II (ruta gitignored por diseño).
