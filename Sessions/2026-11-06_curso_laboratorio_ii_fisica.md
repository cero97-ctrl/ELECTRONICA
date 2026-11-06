# 2026-11-06 — curso_laboratorio_ii_fisica

## Tema
Ajuste del curso Laboratorio II de Física: el curso real tiene **3 grupos**, no 4.

## Contexto
- El usuario informó que el curso tiene tres grupos; el descriptor y todo el
  material generado se habían planificado con cuatro.
- El conteo de grupos vive en 4 puntos de `cursos/LABORATORIO_II_FISICA/curso.yaml`
  (`meta.grupos`, `meta.modalidad`, `grupos.cantidad`, `grupos.asignacion`) y se
  propaga por el generador al sílabo, la guía y la tabla de modalidad de las 10
  prácticas. `plan_semanal`, controles, evaluación final y README no mencionan el
  número de grupos.
- Los «cuatro» restantes del descriptor son contenido de laboratorio (cuatro
  métodos de medición, caja de décadas de cuatro órdenes, cuatro roles por mesa)
  y NO se tocan: los roles siguen siendo 4.

## Decisiones (usuario)
1. El curso tiene **3 grupos**; ajustar descriptor y material regenerando desde
   `curso.yaml` (fuente única de verdad), no editando los `.tex` a mano.

## Actividades
- Editado `curso.yaml`: `meta.grupos: 3`, modalidad «mesas de tres grupos»,
  `grupos.cantidad: 3`, asignación «Tres grupos fijos…».
- Regenerado con `flujo_disenar_curso.py --solo silabo,guia,practicas`:
  12 documentos LaTeX / 12 PDF (run `flujo-disenar-curso-20261106-133221`).
- Verificado: 0 residuos de «4 grupos / cuatro grupos» en `.tex/.md/.yaml`;
  las 10 prácticas dicen «3 grupos con roles rotativos»; sílabo «3 grupos de
  trabajo» y «mesas de tres grupos»; guía «El curso trabaja con 3 grupos.
  Tres grupos fijos…».
- Conjunto de cambios: `curso.yaml` + 12 `.tex` + 12 `.pdf` (25 ficheros).

## Pendientes
- Commit y push del ajuste (no hecho: se hace cuando el usuario lo pida).
