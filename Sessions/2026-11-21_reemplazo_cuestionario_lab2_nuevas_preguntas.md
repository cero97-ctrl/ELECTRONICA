# 2026-11-21 — reemplazo_cuestionario_lab2_nuevas_preguntas

## Tema
Reemplazo del cuestionario web de Laboratorio II de Física por 10 preguntas
nuevas, con regeneración de HTML y redespliegue del Worker `lab2`.

## Contexto
- El usuario pidió sustituir
  `cursos/LABORATORIO_II_FISICA/evaluaciones/web/fuentes/lab_ii_fisica_cuestionario.md`
  por otro markdown con nuevas preguntas.
- El markdown nuevo estaba en `/home/cero/Descargas/lab_ii_fisica_cuestionario_2.md`
  (10 preguntas, etiquetas `**Respuesta:**`/`**Pista:**`/`**Explicación:**`,
  contenido sobre resistencias, código de colores y característica I-V,
  coherente con el material del OCR de las prácticas).
- La fuente `lab_ii_fisica_cuestionario.md` NO es el canónico: es la versión
  pública sin respuestas. Copiar el markdown nuevo encima habría dejado al
  Worker calificando con la clave anterior.

## Decisiones (usuario)
1. Confirmó el archivo nuevo: `/home/cero/Descargas/lab_ii_fisica_cuestionario_2.md`.
2. Eligió **pipeline completo**: dividir → barajar → regenerar HTML →
   redesplegar Worker con la nueva clave.
3. Eligió **barajar** las opciones: las 10 respuestas del canónico nuevo son
   todas `A` (clave degenerada `A A A A A A A A A A`).
4. Eligió **desplegar ahora**, con la ventana aún cerrada y Pages en privado.
5. Pidió **mantener el título actual** `Lab II de Física - Características I-V`.

## Actividades
- Backup de 6 ficheros (3 fuentes + 2 HTML + `index.html`) en
  `.tmp/cuestionario_lab2_reemplazo_20261121/`.
- Cadena determinista con scripts de capa 3:
  1. `execution/dividir_cuestionario.py --canonico lab_ii_fisica_cuestionario_2_origen.md`
     → 37 normalizaciones (`Respuesta` → `Answer`), clave original `A`×10.
  2. `execution/barajar_cuestionario.py --canonico ..._2_origen_respuestas.md
     --salida ..._2_barajado.md` → 10 preguntas barajadas, clave
     `D C D C C D A A A B`, no degenerada.
  3. `execution/dividir_cuestionario.py --canonico ..._2_barajado.md
     --fuente lab_ii_fisica_cuestionario.md
     --respuestas lab_ii_fisica_cuestionario_respuestas.md
     --curso LABORATORIO_II_FISICA --grupos 3 --titulo "Lab II de Física -
     Características I-V" --forzar`.
  - La división regeneró el front matter sin `entrega_url`; se restauró la URL
    del Worker y el deploy la reescribió con `--actualizar-fuente` (idempotente).
- HTML: `flujo_evaluacion_web.py --check` en verde y regeneración de
  `lab_ii_fisica_cuestionario_{alumno,docente}.html` + `index.html`.
  SHA alumno `2a7d4c5c6fb74e9a…`, docente `d2f8a5aa43715099…` (idénticos
  antes y después del deploy).
- Worker: `flujo_desplegar_worker_cuestionarios.py --env lab2 --check` en verde
  (`clave_sha256=4e90265d…`) y deploy real con `--actualizar-fuente`, ventana
  `2026-11-24T12:00:00Z`–`2026-11-24T13:05:00Z`, nómina de 3, sin
  justificaciones. Secretos presentes salvo `ITEMS_JUSTIFICACION` (vacío,
  coherente con el cuestionario).
- Verificación: clave del HTML docente
  `{"1":"D","2":"C","3":"D","4":"C","5":"C","6":"D","7":"A","8":"A","9":"A","10":"B"}`
  coincide con la del deploy; 0 fugas de clave en la variante alumno; 10
  preguntas y `entrega_url` presente; `/salud` → `ok:true`, `abierta:false`
  («todavía no empieza»), `inscritas:3`; repo `cuestionarios-lab2` sigue
  `private` (`has_pages:false` → 404 hasta el 24-nov).
- Tests: 336 aserciones en verde — `test_dividir_cuestionario` 69,
  `test_barajar_cuestionario` 38, `test_md_a_html` 180,
  `test_publicar_cuestionario` 36, `test_desplegar_worker` 13.

## Pendientes
- **24-nov, 08:00 VET**: publicar con
  `python3 flujo_publicar_cuestionario.py --web-dir cursos/LABORATORIO_II_FISICA/evaluaciones/web --repo cero97-ctrl/cuestionarios-lab2 --visibilidad public --push`;
  cerrar a las 09:05 con `--visibilidad private` y después armar el acta de
  `cuestionarios-resultados-lab2`.
- Sin commit/push: los ficheros web están gitignored; solo la bitácora es
  trackeable y queda a la espera de autorización explícita.
