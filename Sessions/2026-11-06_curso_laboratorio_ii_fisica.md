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
- Commit y push del ajuste: `4278bb9` (el remoto había avanzado con trabajo de
  otra sesión sobre Laboratorio I hasta `5503205`; el commit entró encima sin
  conflicto).
- Guía de arranque `docs/semana_1.{tex,pdf}` (4 páginas): pasos del grupo antes,
  durante y después de la primera sesión, con el montaje de la práctica 1, los 4
  roles (y la regla de 3 integrantes → uno asume dos roles), la estructura
  `semana_01/`, el contrato JSON del análisis, la rúbrica de 7 criterios y los
  pesos del curso. Generada reutilizando `_documento()` de
  `execution/generar_material_curso.py` (preámbulo infográfico estándar) con datos
  de `curso.yaml`; compilada aislada en `.tmp/latex_build/semana_1_lab2/` y copiada
  (0 errores, 0 overfull). Espejo de `cursos/LABORATORIO_I_FISICA/docs/semana_1`.
- Commit y push de la guía: `95d2f81`.
- Convención de resultados de evaluaciones: el repo es PÚBLICO (`gh repo view`:
  visibility PUBLIC), así que las notas no pueden viajar por git. Creada
  `cursos/LABORATORIO_II_FISICA/evaluaciones/resultados/` con regla nueva en
  `.gitignore` (`cursos/*/evaluaciones/resultados/**` + excepción README, misma
  pauta que `docs/REFERENCIA`). Estructura local: `actas.csv` (cabecera
  fecha,semana,grupo,documento,nota_sobre_10,nota_fiable,informe) y
  `semana_NN/grupo_N/` para entrega + informe + JSON; ya creadas
  `semana_01/grupo_{1,2,3}`. Verificado con `git check-ignore` y `git add -n`:
  solo el README es stageable.

- Convención de resultados commiteada y subida: `f5a480e` (README de
  `resultados/` + regla de `.gitignore` + esta bitácora).

## Pendientes
- (Ninguno. Pausa acordada por el usuario; al reanudar, revisar si llegaron
  entregas de la semana 1 para evaluarlas con la convención de `resultados/`.)
