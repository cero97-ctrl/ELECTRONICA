# 2026-11-21 — repo_semilla_estudiantes_lab1

## Tema
Repo semilla de grupos para Laboratorio I de Física, reutilizando la plantilla
de Laboratorio II sin duplicar lógica.

## Contexto
- El usuario pidió una plantilla de repo para `LABORATORIO_I_FISICA` análoga a
  la ya publicada de Laboratorio II, indicando que los títulos oficiales de
  talleres y prácticas viven en `cursos/LABORATORIO_I_FISICA/practicas/`.
- Lab I no es idéntico a Lab II: las semanas 1..4 son **talleres**
  (`taller_NN.tex`) y las 5..10 son **prácticas** (`practica_NN.tex`).
- El descriptor de Lab I traía resúmenes cortos en `practica.titulo`, igual que
  le pasaba a Lab II antes de la corrección `b83ac74`.
- Lab I tuvo una purga de PII (`git filter-repo`); la semilla debía quedar sin
  nombres, cédulas ni el PDF `ALUMNOS_LAB_I_FISICA.pdf`.

## Decisiones (usuario)
1. Crear la plantilla para Lab I con los títulos tomados de los `.tex` de
   `practicas/`, igual que se hizo para Lab II.
2. No se autorizó commit/push en esta petición (la autorización anterior cubrió
   solo `db019d1` y `b83ac74`). Los cambios quedan en el árbol de trabajo.

## Actividades
- **Sin duplicar capas:** se generalizaron los scripts ya existentes en vez de
  crear un generador paralelo.
  - `execution/generar_repo_semilla.py`: el nombre del curso sale de
    `meta.titulo`; el README semanal infiere `taller` vs `práctica` del prefijo
    del título y cita `taller_NN.tex` / `practica_NN.tex` según corresponda.
    Lab II queda byte a byte igual.
  - `execution/sincronizar_titulos_practicas.py`: `ruta_y_prefijo()` decide por
    existencia de archivo (`practica_NN.tex`, si no `taller_NN.tex`), sin
    adivinar por nombre de curso.
  - `flujo_sincronizar_titulos_practicas.py`: acepta `--curso` y `--salida` y
    propaga ambos al regenerar la semilla. Antes regeneraba siempre la de Lab II,
    lo que habría sobrescrito la semilla equivocada.
- **Bug detectado y corregido antes de aplicar:** Lab I citaba sus títulos con
  comillas simples y el título 2 contiene `': '`
  («Taller 02 — Del objeto al resultado: propagar sin inventar cifras»).
  Escribirlo como scalar plano habría roto el YAML. Se añadieron
  `descomillar()` / `cotizar()` para leer sin comillas, preservar el estilo
  original y citar cuando el valor lo exige. Quedó fijado con 26 aserciones en
  el test nuevo `execution/test_sincronizar_titulos_practicas.py`.
- **Sincronización aplicada a Lab I:** 10 títulos actualizados en
  `curso.yaml` (4 talleres + 6 prácticas), edición quirúrgica de 10 líneas, con
  las comillas simples originales preservadas. `--check` posterior → 0 cambios.
- **Semilla generada:** `cursos/LABORATORIO_I_FISICA/plantillas/repo_grupo/`
  con 43 archivos, 10 semanas, `portafolio/` en la 10 y 0 datos personales
  (única coincidencia de búsqueda: la propia advertencia de privacidad).
- **Regresión descartada:** Lab II no aparece en `git status` (semilla y
  `curso.yaml` intactos). Tests: semilla 54/54, sincronizador 26/26, material
  de curso 124/124.
- **Directivas versionadas:** `crear_repo_semilla_estudiantes.yaml` y
  `sincronizar_titulos_practicas.yaml` pasan a v1.1 documentando ambos cursos,
  el `--salida` y el caso del `': '`.

## Cierre
- El usuario autorizó commit+push el 2026-11-21; se incluye en el mismo commit
  que los 10 títulos, la semilla de 43 archivos y los scripts generalizados.

## Pendientes
- Si se quiere el diagrama ISO 5807 de este flujo, reutilizar el ya existente
  `docs/AGENTE_IA/repo_semilla_estudiantes_flujo.{tex,pdf}`: el descriptor no
  cambió, así que no hace falta regenerarlo.
- Recordatorio del 24-nov antes de 08:00 VET: publicar el cuestionario de Lab II
  (`flujo_publicar_cuestionario.py --visibilidad public --push`) y volver a
  `private` al cierre.
