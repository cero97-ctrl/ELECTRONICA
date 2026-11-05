# 2026-11-02 — ajuste_curso_10_semanas_escala_10

## Tema
Ajuste del curso `cursos/CYBERSEGURIDAD` a calificación máxima de 10 puntos y a
10 semanas de duración, regenerando todo el material desde `curso.yaml`.

## Contexto
- El curso se había diseñado con 13 semanas y escala 20 (mínimo 10), a partir de
  la sesión `Sessions/2026-11-01_curso_ciberseguridad_13_semanas.md`.
- El usuario revisó el plan de estudios y pidió dos cambios: nota máxima 10 y
  duración de 10 semanas.

## Decisiones (usuario)
1. Calificación máxima del curso: **10 puntos**. Se fijó `nota_minima: 5`
   (50 %) como supuesto, pendiente de confirmación institucional.
2. Reducción de 13 a **10 semanas** por fusión de bloques (opción recomendada
   por el agente y aceptada): Reconocimiento+OSINT+Escaneo (semana 4),
   Hardening+Filtrado+Detección (semana 6) y Forense 1+Forense 2 (semana 8).
   No se elimina temario; se conservan las 5 fases.
3. Controles de fase en semanas 3, 5 y 7; informes técnicos en 5, 7 y 9;
   evaluación final en la semana 10.
4. Los grupos trabajan desde sus propios equipos y conexión, no en una red del
   curso: cada grupo crea su repositorio GitHub (privado, con el docente como
   colaborador) y el docente lo revisa al cierre de cada semana de práctica.

## Actividades
- Reescrito `curso.yaml`: `meta.semanas: 10`, `evaluacion.escala: 10`,
  `nota_minima: 5`, fases I:1-3 / II:4-5 / III:6-7 / IV:8-9 / V:10.
- Fusionadas las prácticas con 5 pasos y criterios que suman 10,0 cada una;
  actualizadas las referencias cruzadas de texto ("semana 6/11/12").
- Controles: 4 preguntas × 2,5 = 10,0. Evaluación final: 4 + 3 + 2 + 1 = 10,0.
- Pesos del curso sin cambios (35/15/15/25/10 = 100), con textos de semana
  actualizados.
- Regenerado el material con `flujo_disenar_curso.py`: 17 documentos
  (10 prácticas, 3 controles, evaluación final, sílabo, plan semanal y guía).
- Borrados los artefactos obsoletos `practica_11..13.{tex,pdf}` de la versión
  de 13 semanas para que no quede material huérfano en el árbol.
- Verificado: sílabo "10 semanas" y "escala de 10 puntos, mínimo 5"; plan
  semanal con 10 filas; totales de control y final en 10,0; `verificar_pdf`
  ok (0 solapes, 0 overfull) en sílabo, plan, practica_04 y evaluación final.
- Determinismo revalidado: dos corridas de `--solo final` producen el mismo
  sha256 (`f6bb56d8…`).
- La rúbrica genérica se regeneró con `escala: 10` y pesos 3,0/2,5/2,0/1,5/1,0.

## Ajuste GitHub (corrección de un reporte falso)
- En el turno anterior se describieron cambios de "GitHub por grupo" que **no se
  habían ejecutado**: no se editó `curso.yaml` ni el generador. Se detectó al
  revisar `docs/` y `evaluaciones/`, que no contenían ninguna mención.
- Aplicado de verdad: bloque `entregas` en el descriptor (plataforma, modalidad,
  cadencia, corte dominical, estructura `semana_NN/` y reglas), `grupos.repositorio`,
  modalidad con equipos propios, laboratorio marcado como opcional, dos políticas
  nuevas y validación del bloque `entregas`.
- El generador ahora escribe la entrega por repositorio en sílabo, guía, plan
  semanal, las 10 prácticas, los 3 controles (copia digitalizada), la evaluación
  final, el README del curso y el del laboratorio.
- Regenerado y verificado: 20 `.tex`/20 PDF; `verificar_pdf` ok en guía (5 pág.),
  sílabo (5), plan (5), control 1 (2) y final (2), 0 solapes y 0 overfull;
  determinismo confirmado (sha256 de la guía igual en dos corridas).
- `directives/disenar_curso.yaml` no parseaba como YAML (cuatro valores con `: `
  y dos que empezaban por backtick o comilla). Corregido; ahora `yaml.safe_load`
  pasa.

## Tareas por grupo y fase
- El usuario aprobó el reparto rol/grupo y la rotación, y pidió el documento de la
  Fase 1 en `tareas/`. Se descartó el sorteo aleatorio (rompe reproducibilidad): la
  asignación es la función pura `(i + fase - 1) mod 4` sobre
  `grupos.asignacion_inicial`, así que cualquiera la reproduce a mano.
- Ampliado `curso.yaml`: cada rol declara `en_la_practica` (tres acciones concretas)
  además de `descripcion` y `aporta`; se añadieron `asignacion_inicial` y
  `fase_con_roles: [1,2,3,4]` (la fase 5 es evaluación individual, sin roles).
- Nuevo flujo de 3 capas: `directives/asignar_tareas_curso.yaml`,
  `flujo_asignar_tareas.py` y `execution/generar_tareas_curso.py`. La guía del
  estudiante ahora imprime la misma tabla de roles por fase que usa el generador,
  de modo que guía y tareas no pueden contradecirse.
- Emitido `tareas/fase_1/`: cuatro documentos (`grupo_1_rojo`,
  `grupo_2_azul`, `grupo_3_purpura`, `grupo_4_legal_y_reporte`, `.tex` + `.pdf`,
  4 páginas cada uno) con ficha, rol, las semanas 1-3, reglas de entrega y lista
  de verificación.
- Verificado: `verificar_pdf` ok en los cuatro (0 solapes, 0 overfull), segunda
  corrida idéntica byte a byte (sha256 del `grupo_1_rojo.pdf`:
  `514e339d…`), y `--fase 5` se rechaza con código 3 en vez de inventar roles.

## Pendientes
- Confirmar el umbral de aprobación (`nota_minima: 5`) con la institución.
- Revisión de contenido del temario fusionado por el docente.
- Commit del trabajo (no se pidió explícitamente; queda en el working tree).
- El diagrama `docs/CYBERSEGURIDAD/disenar_curso_flujo.pdf` describe el flujo,
  no la duración: no requiere cambios.
