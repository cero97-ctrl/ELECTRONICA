# 2026-11-21 — repo_semilla_estudiantes_lab2

## Tema
repo_semilla_estudiantes_lab2

## Contexto
El usuario pidió preparar el repo semilla que cada grupo de Lab II de Física
puede clonar con el árbol de entregas acordado (datos crudos, análisis, figuras y
README por semana), `.gitignore` y plantillas de `README.md`, usando directiva +
orquestador + script determinista (3 capas), no edición manual. El repo de
ELECTRONICA es público, así que la semilla no puede contener nombres, cédulas ni
credenciales: los integrantes se dejan como marcadores y se rellenan en el repo
privado de cada grupo. La fuente de verdad de títulos, roles y corte es
`cursos/LABORATORIO_II_FISICA/curso.yaml`.

## Decisiones (usuario)
1. El usuario aceptó la propuesta literal: «Si quieres, puedo preparar un repo
   semilla con ese árbol, el .gitignore y la plantilla de README.md para que
   cada grupo lo clone — lo haría con directiva + script determinista (3 capas),
   no a mano. ¿Lo quieres?» → «si por favor has esto».
2. Se mantiene el contrato de entregas ya acordado para Lab II: datos crudos
   intactos, correcciones solo en `analisis/`, cada cifra trazable a CSV o
   script, scripts ejecutables de punta a punta, sin credenciales, resultados
   con incertidumbre, informe grupal con conclusiones firmadas individualmente.
3. Sin commit ni push sin autorización explícita (no se han pedido aquí).

## Actividades
- `python3 execution/estado_sesion.py check` → `veredicto_global: ok`, sin
  huérfanos que purgar. Bitácora creada con `execution/bitacoras.py nueva`.
- Capa 3: `execution/generar_repo_semilla.py`. Lee `curso.yaml`, valida que
  existan exactamente las semanas 1..10 con `practica.titulo`, los cuatro roles
  de `grupos.roles` y `entregas.corte`; construye un plan puro de 43 archivos y
  lo escribe con reemplazo atómico por archivo. Nunca borra; sin `--forzar`
  rechaza pisar archivos existentes y con él sobrescribe solo los generados.
  `--check` valida sin escribir. Salida JSON con `status`, `code`, `semanas`,
  `archivos`, `roles`, `problemas`.
- Pruebas: `execution/test_generar_repo_semilla.py` → 41/41 aserciones OK
  (estructura, títulos reales de las semanas 1 y 10, roles, marcadores sin PII,
  determinismo byte a byte, escritura atómica, barrera anti-pisado, `--forzar`
  sin borrado de CSV propios, códigos 2/3/4 y `--check` sin escribir).
  Dos aserciones se corrigieron por estar mal formuladas (buscaban texto sin
  backticks y confundían un comentario de `.gitignore` con una regla); el
  generador no se tocó.
- Capa 1: `directives/crear_repo_semilla_estudiantes.yaml` v1.0 con goal,
  required_inputs, steps (validar → generar → verificar → diagrama → notificar),
  expected_outputs y 5 edge cases.
- Capa 2: `flujo_crear_repo_semilla.py` con `run_state`, `--check`, `--json`,
  `--no-alert`, diagnóstico por código de salida y verificación de entrega; la
  regla fina de verificación NO se duplica: vive en la capa 3.
- Ejecución real: `python3 flujo_crear_repo_semilla.py --json --no-alert` →
  `status: ok`, 10 semanas, 43 archivos, `run_id
  flujo-crear-repo-semilla-20261121-105325`. Semilla en
  `cursos/LABORATORIO_II_FISICA/plantillas/repo_grupo/`: README raíz,
  `.gitignore`, 10 `semana_NN/README.md` con los títulos reales, carpetas
  `datos/`, `analisis/`, `figuras/` con `.gitkeep` y `semana_10/portafolio/`.
- Inspección de PII: 0 coincidencias de cédulas, `V-`, correos o `@` en la
  plantilla. `git check-ignore` confirma que la semilla es trackeable (el
  `.gitignore` del repo no la excluye).
- Diagrama ISO 5807: descriptor `.tmp/descriptor_repo_semilla_estudiantes.json`
  y `docs/AGENTE_IA/repo_semilla_estudiantes_flujo.{tex,pdf}`. El primer intento
  compiló con 1 solape entre las etiquetas `Siempre`/`No` del ciclo `D3 ↔ P6`; se
  rompió el par de flechas opuestas haciendo que la corrección vuelva a `P5`.
  Verificación final: 0 líneas `!`, 0 `Overfull \hbox`, 0 solapes.

## Continuación — corrección del título de la semana 01 (misma sesión)
El usuario señaló que `plantillas/repo_grupo/semana_01/README.md` mostraba
«Semana 01 — Característica corriente-tensión de un resistor», un resumen de
`curso.yaml`, en lugar del título impreso en `practica_01.tex`. Al comparar los
10 `.tex` con el descriptor, los 10 títulos diferían. El usuario eligió
**corregir `curso.yaml`** (mantener un único descriptor) en lugar de hacer que
el generador leyera los `.tex`.

- Capa 3: `execution/sincronizar_titulos_practicas.py`. Extrae `\bandaTitulo`
  de `practica_NN.tex`, normaliza `---` → `—`, valida el prefijo `Práctica NN`
  y sustituye SOLO la línea `titulo:` dentro de cada bloque `practica:` del
  YAML (edición quirúrgica: comentarios, anclas, `titulo:` de nivel semana y
  espaciado intactos). `--check` solo reporta; `--apply` escribe con relectura
  y verificación. Sin flags, solo reporta.
- Capa 1: `directives/sincronizar_titulos_practicas.yaml` v1.0.
- Capa 2: `flujo_sincronizar_titulos_practicas.py` con `run_state`, encadena
  check → apply → regenerar semilla → test.
- Ejecución: 10 títulos actualizados, semilla regenerada (43 archivos), idempotencia
  confirmada (`--check` posterior → 0 cambios). `git diff` de `curso.yaml`:
  exactamente 10 líneas cambiadas, sin otro byte tocado.
- Ajuste adicional en `generar_repo_semilla.py`: el README semanal empieza
  ahora por el título oficial exacto (`# Práctica 01 — …`) y la semana pasa a
  una línea de contexto, para evitar el encabezado redundante
  «Semana 01 — Práctica 01 — …». Tests actualizados: 41/41 OK.
- Regresión descartada: `execution/test_generar_material_curso.py` 124/124 OK y
  `flujo_disenar_curso.py --solo plan_semanal` compila con 0 errores y 0
  `Overfull \hbox` pese a los títulos más largos.

## Cierre
- El usuario autorizó commit+push de esta corrección el 2026-11-21; se incluye
  en el mismo commit que la bitácora y los 10 títulos sincronizados.
- El commit anterior `db019d1` (semilla original) ya estaba pusheado.
- No se tocó `cursos/LABORATORIO_I_FISICA/ALUMNOS_LAB_I_FISICA.pdf`.

## Pendientes
- Recordatorio del 24-nov antes de 08:00 VET: publicar el cuestionario con
  `flujo_publicar_cuestionario.py --web-dir cursos/LABORATORIO_II_FISICA/evaluaciones/web --repo cero97-ctrl/cuestionarios-lab2 --visibilidad public --push`
  y volver a `private` al cierre.
- Consciente: `flujo_desplegar_worker_cuestionarios.py` duplica el bloque de
  secretos si falta `GITHUB_TOKEN`; no se ejecutó en esta sesión.
