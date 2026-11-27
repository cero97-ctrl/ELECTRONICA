# 2026-11-27 — justificaciones_cuestionarios_semana_02

## Tema
justificaciones_cuestionarios_semana_02

## Contexto
- El usuario pidió añadir a las 10 preguntas de cada uno de los 4 cuestionarios
  web de Ciberseguridad SEMANA_02 un recuadro de justificación, enviarlo a un
  Worker y archivarlo con la entrega, manteniendo el flujo de publicar en
  GitHub Pages para revisión visual y volver a ocultar.
- SEMANA_02 ya tenía 4 fuentes limpias + 4 solucionarios + 4 HTML por rol, con
  `aviso`, tabla fija en la pregunta 10 e infografías aprobadas. No tenía
  `justificacion_items` ni `entrega_url`: los recuadros eran solo visuales.
- Los Workers de SEMANA_01 (`cuestionarios-worker` y `-azul/-purpura/-legal`)
  están desplegados y NO se pueden sobrescribir.

## Decisiones (usuario)
1. Enviar el texto escrito por los estudiantes al Worker y archivarlo junto con
   las respuestas (no solo mostrar el textarea).
2. Poner recuadro de justificación en las 10 preguntas de los 4 roles.
3. Publicar los `*_alumno.html`, esperar el OK visual del usuario y volver a
   ocultar el repo (como en la sesión anterior).
4. Ventana de entrega ABIERTA: no fijar `VENTANA_INICIO`/`VENTANA_FIN`; se podrán
   fijar después sin redesplegar.
5. Usar la nómina oficial `cursos/CYBERSEGURIDAD/evaluaciones/alumnos_cyberseguridad.csv`
   (11 renglones) como secreto `CEDULAS` de los 4 Workers.
6. Las fuentes llevan sufijo `_S2` para que el `cuestionario_id` (
   `rol_<rol>_cuestionario_s2`) no colisione con SEMANA_01.
7. Mantener el `aviso` aprobado, la tabla de la pregunta 10 y las infografías;
   no tocar Laboratorio I ni Laboratorio II.

## Actividades
- Renombradas las 12 fuentes de SEMANA_02 con sufijo `_S2` (fuente, respuestas y
  respaldo original) y actualizada la ruta por defecto en
  `flujo_preparar_fuente_web.py`, `directives/separar_respuestas_web.yaml` y
  `execution/test_separar_respuestas_md.py`.
- Nueva capa 3 `execution/agregar_justificaciones_web.py`: inserta
  `**Justificación:** <instrucción>` después de la última opción de cada
  pregunta, escribe `justificacion_items: [1..10]` y `grupos: 4` en el front
  matter de la fuente y del solucionario, valida el par con
  `md_a_html.cargar_clave` en un temporal y escribe de forma atómica.
- Nueva capa 2 `flujo_agregar_justificaciones_web.py` y SOP
  `directives/agregar_justificaciones_web.yaml`. Pruebas nuevas:
  `execution/test_agregar_justificaciones_web.py` (11 aserciones).
- Aplicado a las 4 fuentes: 10 `**Justificación:**` por fuente, mismos 10 en su
  solucionario, `aviso` conservado.
- `Proyectos/cuestionarios-worker/wrangler.jsonc`: 4 entornos nuevos (`s2`,
  `s2_azul`, `s2_purpura`, `s2_legal`) con nombres `cuestionarios-worker-s2*`,
  `CUESTIONARIO_ID` con sufijo `_s2`, `GRUPOS=4` y el repo de resultados
  compartido (la ruta del acta ya prefija el ID del cuestionario).
- `npm test` del Worker: 32/32. Los cuatro `--check` terminaron en 0 con 10
  preguntas y `justificacion_items = [1..10]`.
- Desplegados los 4 Workers con la nómina oficial (11 cédulas) y
  `--actualizar-fuente`: URL `https://cuestionarios-worker-s2*.cero-agents.workers.dev`;
  secretos `CLAVE_JSON`, `GITHUB_TOKEN`, `CEDULAS`, `ITEMS_JUSTIFICACION` y
  `MIN_JUSTIFICACION` presentes; sin `VENTANA_*` (ventana abierta). Cada fuente
  lleva su `entrega_url`.
- Regenerados los 8 HTML con los nuevos slugs `_s2`. Verificado: 10 `<textarea>`
  y 10 instrucciones por `*_alumno.html`, 0 claves en la variante alumno,
  `aviso` y la tabla de la pregunta 10 conservados, URL del Worker correcta.
  Las 4 variantes alumno antiguas se sobrescribieron con el contenido nuevo
  para no romper enlaces ya compartidos.
- Pruebas: separador 47/47, md_a_html 197/197, publicador 51/51, desplegador
  13/13, insertador de justificaciones 11/11.
- Publicados los 4 `*_alumno.html` (solo variante alumno, índice sin docente)
  en `https://cero97-ctrl.github.io/cuestionarios-ciberseguridad-s02/` y el repo
  puesto en `public`. Verificación remota con cache-buster: las 4 páginas dan
  HTTP 200, 10 textareas cada una y 0 claves; el índice enlaza solo los 4
  archivos `_s2_alumno.html`. Los alias antiguos se retiraron del payload para
  que el índice no muestre duplicados (el sitio estaba oculto, así que no había
  enlaces públicos vigentes que romper).
- Tras la revisión del usuario pidió quitar del bloque «Antes de empezar» toda
  referencia a abrir/consultar el repositorio (contradecía el `aviso`). Cambio
  hecho en la capa 3 `execution/md_a_html.py::_aviso_material`, con SOP en
  `directives/evaluacion_web.yaml` y 6 aserciones nuevas en
  `execution/test_md_a_html.py` (201/201). Ya no contradice el aviso; el texto
  conserva borrador, caducidad y fijación al primer clic. No cambia la huella
  del cuestionario, así que no invalida entregas.
- Regenerado y republicado. Verificado en el repo remoto y en Pages (con
  `Cache-Control: no-cache`): 4 páginas con 10 textareas, 0 menciones a
  repositorio/GitHub en «Antes de empezar» y 0 claves.
- El usuario amplió el requisito: **ninguna pregunta de los cuatro cuestionarios
  debe requerir consultar el repositorio y ninguna justificación debe pedir
  evidencia allí**. Cambios aplicados:
  - Instrucción canónica de `execution/agregar_justificaciones_web.py` →
    «Explica con tus propias palabras por qué elegiste esa opción, apoyándote en
    el enunciado y en los conceptos vistos en clase.»; SOP y test actualizados.
    Reescritas las 40 justificaciones con `--forzar` en las 4 fuentes y sus 4
    solucionarios.
  - Enunciados reescritos para no mencionar «repositorio»: Azul P8 (ya hecho),
    Legal P4, Púrpura P3 y P9, Rojo P6 — en fuente, solucionario y copia
    `_original_con_respuestas.md`. Quedan solo las menciones permitidas: el
    `aviso` aprobado y dos opciones que describen políticas (no piden abrir
    ningún repo). Las respuestas y la clave del Worker NO cambiaron, así que no
    hace falta redeploy ni tocar secretos.
  - Regenerados los 8 HTML: 10 textareas por alumno, 0 instrucciones viejas,
    0 claves. Pruebas: md_a_html 201/201, separador 47/47, insertador 11/11.
- El mensaje del usuario llegó truncado en «Aun no publico...»; preguntado,
  eligió **publicar la versión corregida** para revisión. Republicado en el repo
  `cero97-ctrl/cuestionarios-ciberseguridad-s02` con `--visibilidad public`.
- Verificación remota: el blob de GitHub trae la instrucción nueva 10× y la
  vieja 0×. Pages sirvió primero una copia en caché; con
  `Cache-Control: no-cache, no-store, max-age=0` + `Pragma: no-cache` las 4
  páginas muestran 10 textareas, 10 instrucciones nuevas, 0 instrucciones
  viejas, 0 claves y 0 enunciados con «repositorio». Índice HTTP 200.
- Trampa de caché documentada: un `?cb=<epoch>` simple devolvió la versión
  anterior durante unos minutos aunque `x-cache: MISS`; hay que obligar con los
  headers `no-cache, no-store` para fiarse de la verificación.
- El usuario dio el OK visual y pidió ocultar. Ejecutado `--visibilidad private`
  con `--push`: repo `private`, `pages_visible=false`. Verificado: raíz e
  `index.html` dan **HTTP 404**; la página directa seguía sirviéndose desde la
  caché de Pages (`x-cache: HIT`, `age ~175 s`, TTL 600 s) justo tras el cambio,
  así que se lanzó una comprobación diferida en background para confirmar el
  404 también en enlaces directos una vez expire la caché.
- Pruebas finales: separador 47/47, md_a_html 201/201, publicador 51/51,
  desplegador 13/13, insertador 11/11; `bitacoras.py check` → `veredicto_global:
  ok`, 0 anomalías.
- **Estado actual: OCULTO** (repo privado). Pendiente solo confirmar la expiración
  de caché del enlace directo y commitear/pushear el trabajo local.

## Pendientes
- Verificar `npm test` del Worker y `flujo_desplegar_worker_cuestionarios.py
  --check` para los 4 entornos.
- Desplegar los 4 Workers con `--nomina` y `--actualizar-fuente` (sin
  `--inicio`/`--fin`).
- Regenerar los 8 HTML y verificar 10 textareas por `*_alumno.html`, botón de
  entrega habilitado y ausencia de clave/docente en la variante alumno.
- Publicar con `--visibilidad public`, esperar OK del usuario y ocultar con
  `--visibilidad private`.
- Tests finales, `bitacoras.py check`, commit y push.
