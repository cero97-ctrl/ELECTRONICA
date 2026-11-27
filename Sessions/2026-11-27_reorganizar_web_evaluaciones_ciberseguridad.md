# 2026-11-27 — reorganizar_web_evaluaciones_ciberseguridad

## Tema
reorganizar_web_evaluaciones_ciberseguridad

## Contexto
- El usuario pidió mover todo el contenido de
  `cursos/CYBERSEGURIDAD/evaluaciones/web/` a una subcarpeta `SEMANA_01`
  dentro de esa misma ruta, sin tocar el material aprobado y publicado de la
  semana 02 ni los archivos sin seguimiento de Laboratorio I.
- Al revisar antes de ejecutar se detectó una violación del espíritu
  determinista: `execution/publicar_cuestionario.py` exige `web/` como nombre
  exacto y recolecta los `*_alumno.html` solo en su raíz, y
  `flujo_evaluacion_web.py` busca las fuentes por defecto en
  `web/fuentes/*.md`. Mover sin adaptar rompería ambos comandos. Se alertó y se
  propuso la alternativa conforme; el usuario eligió «Mover y adaptar flujos».

## Decisiones (usuario)
1. La carpeta destino se llama exactamente `SEMANA_01` y queda en
   `cursos/CYBERSEGURIDAD/evaluaciones/web/SEMANA_01/`.
2. Se mueve todo y se adaptan publicador, conversor, orquestadores, directivas
   y pruebas para que los comandos sigan funcionando con rutas por defecto.
3. No se hace commit ni push de este cambio hasta autorización explícita.
4. No se toca el material de la semana 02 ni los dos archivos sin seguimiento
   de Laboratorio I (`practicas/web/` y `publicar_lab1_practicas_web.sh`).
5. Decisión técnica derivada de la alternativa aceptada: la barrera admite
   **tanto** `web/` (raíz, la siguen usando Laboratorio I y II) **como**
   `web/SEMANA_NN` (Ciberseguridad). Restringirla solo a `SEMANA_NN` habría
   roto los comandos de publicación de los otros cursos, que el usuario pidió
   mantener funcionando. Se rechaza cualquier nivel adicional, p. ej.
   `web/SEMANA_01/fuentes/`.
6. El usuario colocó `ROL_ROJO_CUESTIONARIO.md` con 10 preguntas en
   `SEMANA_02/fuentes/`, con respuestas en español (`**Respuesta:**`,
   `**Pista:**`, `**Explicación:**`). Se detectó que el conversor solo entiende
   las marcas en inglés y que, de generar sin corregir, la clave se filtraría en
   la opción D de la variante alumno. Se detuvo antes de generar, se explicó el
   riesgo en lenguaje sencillo y el usuario eligió **separar automáticamente**
   con un script determinista (no adaptar el conversor ni generar con fuga).

## Actividades
- Se verificó el estado derivado (`execution/estado_sesion.py check`: `ok`, 0
  acciones) y se creó esta bitácora con `execution/bitacoras.py nueva`.
- Se movieron los 10 elementos de la raíz de `web/` a `SEMANA_01/`
  (`fuentes/`, `index.html` y 8 HTML). Se compararon los SHA-256 de los 17
  archivos antes y después: idénticos. En la raíz de `web/` solo queda
  `SEMANA_01/`.
- Capa 3 adaptada: `execution/publicar_cuestionario.py` (default
  `.../web/SEMANA_01`, barrera `web/` o `web/SEMANA_NN`),
  `execution/md_a_html.py` (barrera de salida con el mismo criterio),
  `execution/descargar_resultados.py` (ruta de ejemplo).
- Capa 2 adaptada: `flujo_publicar_cuestionario.py`,
  `flujo_evaluacion_web.py` (dos patrones por defecto: semanas y raíz),
  `flujo_acta_cuestionario.py` y `flujo_desplegar_worker_cuestionarios.py`.
- Directivas actualizadas: `publicar_cuestionario.yaml`, `evaluacion_web.yaml`,
  `acta_cuestionario.yaml` y `entregar_respuestas_worker.yaml` (incluidos los
  comandos de recuperación, que ahora apuntan a `web/SEMANA_01/`).
- Pruebas: `test_publicar_cuestionario.py` 46/46, `test_md_a_html.py` 186/186,
  `test_descargar_resultados.py` 135/135, `test_desplegar_worker.py` 13/13;
  los cuatro YAML parsean y `py_compile` no reporta errores. Se añadieron
  aserciones nuevas para la barrera por semana y para los dos patrones del
  conversor.
- Verificación en seco: `flujo_publicar_cuestionario.py --dry-run --json`
  prepara exactamente 4 `*_alumno.html` (sin docente, sin clave) en
  `.tmp/publicacion/cuestionarios/`; `flujo_evaluacion_web.py --check
  --dry-run` encuentra las 4 fuentes de `SEMANA_01` y sus 4 archivos de
  respuestas. Los 8 enlaces relativos del `index.html` movido apuntan a
  archivos existentes (0 enlaces rotos): las rutas relativas se conservan
  porque fuentes y HTML se movieron juntos.
- Se dejó pendiente, sin tocar, un fallo preexistente de Laboratorio II:
  `lab_ii_fisica_cuestionario_2_barajado.md` contiene `**Answer:**` y el
  conversor lo rechaza con código 3. El patrón de raíz que lo detecta ya
  existía antes de este cambio.
- A petición del usuario, se creó `cursos/CYBERSEGURIDAD/evaluaciones/web/SEMANA_02/`
  con la misma estructura de directorios que `SEMANA_01` (únicamente `fuentes/`)
  y sin ningún archivo. No se copió ni se movió contenido.
- Se añadió el flujo de separación en las tres capas:
  `directives/separar_respuestas_web.yaml` (SOP),
  `flujo_preparar_fuente_web.py` (orquestador con `run_state` y trazas) y
  `execution/separar_respuestas_md.py` (lógica pura). Más
  `execution/test_separar_respuestas_md.py` (43 aserciones, sin red). El script
  valida la pareja con `md_a_html.cargar_clave()` en un directorio temporal
  **antes** de escribir, guarda un respaldo byte-idéntico del original y nunca
  imprime la clave.
- Se ejecutó el flujo sobre el archivo real: 10 preguntas separadas. Se crearon
  `ROL_ROJO_CUESTIONARIO.md` (limpio),
  `ROL_ROJO_CUESTIONARIO_respuestas.md` (clave) y
  `ROL_ROJO_CUESTIONARIO_original_con_respuestas.md` (respaldo). El check en
  seco pasó de `tiene_clave: false` a `tiene_clave: true`.
- Se generaron `rol_rojo_cuestionario_alumno.html` (27 924 bytes) y
  `rol_rojo_cuestionario_docente.html` (27 233 bytes) en `SEMANA_02/`. El alumno
  no contiene `const CLAVE`; el docente sí. El `index.html` local enlaza al
  docente, pero es material privado: el dry-run del publicador con
  `--web-dir .../SEMANA_02` preparó **solo** `rol_rojo_cuestionario_alumno.html`
  y un índice sin docente ni clave.
- El respaldo con marcas en español no se cuela en el glob por defecto: el
  check global pasó de 11 a 12 fuentes (solo se añadió la fuente limpia).
- Pruebas finales: `test_separar_respuestas_md.py` 43/43,
  `test_md_a_html.py` 186/186, `test_publicar_cuestionario.py` 46/46;
  `py_compile` sin errores y la nueva directiva parsea como YAML.

- Con autorización explícita del usuario, se publicó `SEMANA_02` en un repo
  propio, `cero97-ctrl/cuestionarios-ciberseguridad-s02` (URL
  `https://cero97-ctrl.github.io/cuestionarios-ciberseguridad-s02/`). No se
  reutilizó `cero97-ctrl/cuestionarios`: contiene los 4 HTML de la semana 01 y
  el push es `--force`, así que habría borrado ese material. El repo quedó
  público con Pages activo; el árbol remoto tiene solo `.nojekyll`,
  `index.html` y `rol_rojo_cuestionario_alumno.html`, sin docente ni clave.
- Verificación posterior al push, no solo el reporte del flujo: `curl` devolvió
  HTTP 200 con UA de navegador; el SHA-256 del HTML remoto
  (`5b3cd2b7…`) es idéntico al local; `gh api` confirmó visibilidad `public`,
  rama `main` y los 3 archivos del árbol.
- Commit `7dd7919` con 19 archivos (14 modificados + 5 nuevos: la bitácora, la
  directiva, el separador, su prueba y el orquestador). Quedaron deliberadamente
  fuera los dos untracked de Laboratorio I (`practicas/web/` y
  `publicar_lab1_practicas_web.sh`). Push fast-forward de
  `8a3e1a8..7dd7919`; antes del push HEAD traía 3 commits de auditoría del
  25-nov que también se subieron. `origin/master...HEAD` quedó en `0 0`.

- A petición del usuario se identificó el cuestionario publicado como del grupo
  con rol Rojo **en la propia fuente**, no editando el HTML a mano: se añadió
  front matter a `SEMANA_02/fuentes/ROL_ROJO_CUESTIONARIO.md` con
  `titulo: "Criptografía Práctica — Rol Rojo"` y `grupo: "Rol Rojo"`. El
  conversor ya renderiza esos campos en `<title>`, `<h1>`, `<p class="meta">`
  (`Cuestionario · Grupo Rol Rojo`) y en el índice; antes solo aparecía
  «Criptografía Práctica» y la palabra «Rojo» dentro de la pregunta 7.
- Se regeneró con `flujo_evaluacion_web.py` y se republicó con
  `flujo_publicar_cuestionario.py --push --visibilidad public`. La primera
  verificación con `curl` seguía mostrando la versión antigua: era caché del
  CDN (`cache-control: max-age=600`), no un push fallido. Con cache-buster,
  el HTML servido es byte-idéntico al local (SHA-256 `57482256…`), el índice
  dice «Criptografía Práctica — Rol Rojo» y sigue sin mención al docente.
  El contenido de `cursos/*/evaluaciones/web/**` está gitignored a propósito,
  así que este ajuste no generó commit de código.

- El usuario entregó después los otros tres markdowns de la semana 02 en
  `fuentes/` (`ROL_AZUL_CUESTIONARIO.md`, `ROL_PURPURA_CUESTIONARIO.md`,
  `ROL_LEGAL_CUESTIONARIO.md`), cada uno con 10 preguntas y respuestas en
  español (`**Respuesta:**`, `**Pista:**`, `**Explicación:**`). Se separaron con
  `flujo_preparar_fuente_web.py` (uno por rol, sin `--forzar`): fuente limpia +
  `_respuestas.md` + `_original_con_respuestas.md`, convalidado por las 43
  aserciones del separador. A la fuente limpia se le añadió front matter con
  `titulo` y `grupo` para que la página diga «Rol Azul», «Rol Púrpura» y
  «Legal — Reporte técnico», igual que ya decía «Rol Rojo».
- Se generaron los 8 HTML con `flujo_evaluacion_web.py` (4 alumnos sin
  `const CLAVE`, 4 docentes con clave) y se publicaron los 4 alumnos en el MISMO
  repo `cero97-ctrl/cuestionarios-ciberseguridad-s02` con un índice común y
  cuatro enlaces, ninguno al docente. Decisión del usuario: dejarlo visible
  para que lo revise y ocultarlo solo cuando él lo indique. El seco con
  `--visibilidad` solo cambia visibilidad y no prepara el payload: hubo que
  repetirlo sin esa bandera para verificar los cuatro archivos.
- Verificación remota con cache-buster: los cuatro HTML servidos son
  byte-idénticos a los locales (SHA `5940fd99…`, `ee2558ac…`, `b509db79…`,
  `57482256…`); el índice lista los cuatro roles y no menciona al docente.
  Justo tras el push Pages sirvió 404 para los archivos nuevos durante unos
  segundos; se resolvió solo (el `pages_visible: true` del flujo mira la URL
  raíz, que estaba cacheada). Pruebas: separador 43/43, `md_a_html` 186/186,
  publicador 46/46.

## Pendientes
- Confirmación visual explícita de las 4 infografías `SEM_2` (siguen fuera de
  git).
- No reabrir el material aprobado de la semana 02.
- **No ocultar todavía**: el usuario quiere revisar primero cómo se ve la
  página, y avisará cuando haya que pasar
  `cero97-ctrl/cuestionarios-ciberseguridad-s02` a `--visibilidad private`
  (mismo comando que en la semana 01; el CDN puede servir la copia cacheada
  hasta ~10 min, así que hacerlo con horas de antelación).
