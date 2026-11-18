# 2026-11-12 — material_didactico_sara

## Tema
Web de material didáctico para Sara (3.º año de bachillerato): Matemáticas, Física y Química, con explicaciones paso a paso, ejercicios con corrección y esquemas visuales, en HTML autocontenido dentro de `SARA/`.

## Contexto
- El usuario pidió una página web de apoyo para su hija Sara, dentro del espectro autista. Se preguntó curso, materias y formato; respondió: `3º año`, `Matemáticas, Física, Química`, `Explicaciones paso a paso`, `Ejercicios con corrección` y `Esquemas y resúmenes visuales`.
- El repo exige arquitectura de 3 capas (directiva + orquestador + script determinista), HTML sin CDN ni recursos externos y salidas reproducibles. Se usó `execution/md_a_html.py` / `flujo_evaluacion_web.py` como referencia de estilo y convenciones, sin reutilizar su lógica de cuestionarios.
- Restricción de diseño acordada: baja estimulación sensorial (sin animaciones, sonidos, temporizadores ni puntajes), lenguaje literal, orden fijo de secciones y controles de accesibilidad.

## Decisiones (usuario)
1. Curso: 3.º año de bachillerato.
2. Materias: Matemáticas, Física y Química.
3. Formato: explicaciones paso a paso + ejercicios con corrección + esquemas/resúmenes visuales.
4. Diseño de baja estimulación: sin cronómetros, sin puntajes, sin animaciones; feedback textual no punitivo.
5. El sitio debe ser local/offline (sin CDN) y con ajustes de tamaño de texto y alto contraste persistentes.
6. Publicar el sitio en GitHub Pages para que Sara lo abra desde el colegio: repo `cero97-ctrl/material-sara`, **público** (decidido el 2026-11-12, igual que los cuestionarios del curso).
7. **Título neutro en la versión pública:** la marca y el pie pierden el nombre «Sara» («Material de estudio · 3.º año de bachillerato»); el nombre solo queda en la copia local. El nombre de una menor no debe ir en una página pública indexable.

## Actividades
- **Capa 3** `execution/generar_material_sara.py`: valida los YAML (materia, título, slug, objetivo, idea, pasos, ejemplo, esquema, ejercicios, recordatorio, nota), renderiza CSS/JS inline, genera portada, índices por materia y páginas de tema, navegación anterior/siguiente, barrera de escritura (solo dentro de `SARA/`, solo `.html`) y CLI `--check/--dry-run/--json`. Códigos: `0` ok, `1` E/S, `3` contenido inválido, `5` salida fuera de `SARA/`.
- **Capa 1** `directives/material_didactico_sara.yaml`: SOP, contrato de campos, accesibilidad, casos límite y cómo añadir temas.
- **Capa 2** `flujo_material_sara.py`: orquestador que delega en el generador e informa la ruta de apertura.
- **Contenido:** 10 temas en `SARA/contenido/`:
  - Matemáticas: funciones y plano cartesiano, ecuación cuadrática, sistemas de dos ecuaciones y conversión entre decimal, binario y hexadecimal (añadido a petición del usuario).
  - Física: movimiento rectilíneo uniforme, segunda ley de Newton, circuitos serie/paralelo.
  - Química: el átomo y sus partículas, enlaces químicos, mol y estequiometría.
- **Pruebas** `execution/test_generar_material_sara.py`: **67/67 aserciones OK**. Cubren validación, slugs, determinismo, cero recursos externos, enlaces internos, estructura de cada página, `lang="es"`, un solo `<h1>` y enlace de salto.
- **Generación real:** `python3 flujo_material_sara.py` → `SARA/index.html`, 3 índices de materia y 10 páginas de tema (14 páginas y 22 ejercicios en total).
- **Tema nuevo (conversión de bases):** `SARA/contenido/matematicas/04_conversion_decimal_binario_hexadecimal.yaml`. Explica las bases 10/2/16, la división con restos, la agrupación de cuatro bits, el ejemplo 45 → 101101 → 2D, una tabla de equivalencias 0–F y 4 ejercicios. Verificado: 4 `fieldset`, cero recursos externos, solo navegación «Anterior» por ser el último tema, y capturas de escritorio/móvil sin desbordes.
- **Marca neutra en el generador:** cabecera, pie y `<title>` pierden el nombre de Sara («Material de estudio · 3.º año de bachillerato»); sitio regenerado (10 temas, 14 páginas) y 67/67 pruebas OK. El nombre queda solo en rutas locales (`SARA/`, nombre del repo), nunca en el contenido servido.
- **Capa 3 compartida `execution/publicar_github.py`:** la mecánica de git/Pages (commit con identidad y fecha fijas, `push --force`, habilitar Pages, espera del 200, visibilidad por API REST) vivía duplicada en el publicador de cuestionarios; ahora se define una sola vez y `publicar_cuestionario.py` la importa (sus 23/23 pruebas siguen en verde y el sha256 del payload no cambió: `44a55676…` Azul).
- **Publicación del sitio (3 capas):** `directives/publicar_material_sara.yaml` + `flujo_publicar_material_sara.py` + `execution/publicar_material_sara.py` (+ `execution/test_publicar_material_sara.py`, **29/29 aserciones**). Barreras: origen único `SARA/` (código 5), solo `.html`, sin symlinks, sin `http(s)://`/`<link`/`src=`/`@import`, sin `href` absolutos, externos, que escapen de la raíz o rotos, y sin referencias a `contenido/*.yaml`; el stage preserva las rutas relativas y añade `.nojekyll`.
- **Publicado y verificado:** `flujo_publicar_material_sara.py --push` → repo público `cero97-ctrl/material-sara`; portada y 3 páginas anidadas en 200 con sha256 idéntico al stage (`9f34d25a…`, `7c402966…`, `6ecfb3c5…`, `df79a192…`); el árbol del repo es solo `.nojekyll` + 14 `.html`; 0 apariciones de «Sara» en lo servido. URL: https://cero97-ctrl.github.io/material-sara/
- **Verificación visual:** capturas en Chrome de portada, tema de ecuación cuadrática (escritorio y móvil 390 px), tema de química con tabla (móvil), tema de conversión de bases (escritorio y móvil) y alto contraste. Sin desbordes horizontales; tablas y botones caben en móvil.
- **Correcciones durante la revisión:**
  - El test esperaba 7 páginas y el sitio genera 13; se corrigió el conteo.
  - El título de esquema usaba la clase de la fuente y salía en mayúsculas; se añadió `.titulo-esquema` en minúscula normal.
  - La portada usaba una caja `.nota` roja para «No hay tiempo límite»; se cambió a `.calma` verde.
  - El alto contraste dejaba el tinte de materia (`--tinte`) en azul claro porque la variable se define en `body`; se añadió la anulación para `.matematicas/.fisica/.quimica` y bordes para `.objetivo/.resultado`.
  - **Trampa de verificación:** el JS de ajustes borra `data-contraste`/`data-texto` al cargar si `localStorage` está vacío; las capturas de prueba deben quitar los `<script>` o inicializar el almacenamiento, o el HTML parece ignorar el alto contraste.
- **Materias con color propio:** Matemáticas azul, Física violeta, Química verde; el color es orientativo, no la única señal (siempre hay texto).

## Pendientes
- **Publicación en GitHub Pages: HECHA** (`cero97-ctrl/material-sara`, público, marca neutra). Para actualizar el sitio publicado: regenerar con `flujo_material_sara.py`, pasar `execution/test_publicar_material_sara.py` y ejecutar `flujo_publicar_material_sara.py --push`. Para ocultarlo: `--visibilidad private` (la URL pasa a 404; el CDN tarda hasta ~10 min en vaciarse).
- **Commit:** no se ha hecho; requiere petición explícita del usuario. Archivos nuevos: `SARA/`, `directives/material_didactico_sara.yaml`, `directives/publicar_material_sara.yaml`, `execution/generar_material_sara.py`, `execution/test_generar_material_sara.py`, `execution/publicar_github.py`, `execution/publicar_material_sara.py`, `execution/test_publicar_material_sara.py`, `flujo_material_sara.py`, `flujo_publicar_material_sara.py`; modificados: `execution/publicar_cuestionario.py` (importa la mecánica compartida), `AGENTS.md` y esta bitácora.
- **Prueba de interacción real:** la corrección de ejercicios se validó visualmente y por estructura, pero no con un test automatizado de DOM (no hay jsdom/puppeteer en el entorno). Si se quiere, se puede añadir una prueba con Chrome/CDP.
- **Ampliación de contenido:** el flujo acepta nuevos YAML sin tocar código; solo hay que añadirlos en `SARA/contenido/<materia>/` y regenerar.
- **Impresión:** hay estilos `@media print`, pero no se ha generado una captura/PDF de prueba.
