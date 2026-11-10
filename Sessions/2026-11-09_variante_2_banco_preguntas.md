# 2026-11-09 — variante 2 banco preguntas

## Tema
Redactar e integrar la variante 2 `utilizable` del banco privado de controles en
los tres cursos (CYBERSEGURIDAD, LABORATORIO_I_FISICA, LABORATORIO_II_FISICA).

## Contexto
- Los tres bancos solo tenían la variante 1 en estado `comprometida`, así que
  `--solo controles` sin `--variante` fallaba por diseño (no hay ninguna
  `utilizable`). El pendiente se había aplazado deliberadamente el 2026-11-08.
- El descriptor público ya no lleva enunciados; el banco privado (gitignored) es
  la única fuente del texto y se aplica con `--variante N` determinista.

## Decisiones (usuario)
1. La redacción la hace el agente y la revisa el usuario; **0 créditos** OpenRouter
   (no se usa `flujo_elaborar_examen.py` con tier opus).
2. Equivalencia entre variantes: **mismos temas por slot** que la variante 1, para
   que los dos exámenes sean comparables en dificultad.
3. Generar **solo** la variante 2 (no se prepara una variante 3).
4. Aprobó los 28 enunciados redactados antes de escribirlos en los bancos.

## Actividades
- Borradores en `.tmp/borrador_variante2_<curso>.yaml`, validados
  estructuralmente (12/8/8 preguntas, 4 por control, 2,5 pt, sin `%` literal).
  Presentados al usuario para revisión; dos desviaciones explicadas y aprobadas:
  ciber fase 2 slot 4 con hallazgos explícitos, y lab II fase 2 slot 2 sobre
  inductor (complementa al capacitor de la variante 1).
- Anexada la variante 2 (`estado: utilizable`, `creada: '2026-11-09'`) a los tres
  `cursos/*/evaluaciones/banco_preguntas.yaml` con cirugía textual (se conservan
  comentarios y formato). Actualizado `meta.aviso` para reflejar que la 2 es la
  variante vigente. Ficheros siguen ignorados por git.
- Generación sin flags (`--solo controles`, sin `--variante`) en los 3 cursos:
  el generador elige la variante 2 automáticamente y compila **7 PDF** (3 ciber +
  2 + 2 laboratorios) con `status: ok`, 0 errores y 0 overfull.
- Guardarraíl comprobado: `--variante 1` sin `--permitir-comprometida` sigue
  devolviendo `banco_invalido` (código 6).
- Determinismo: dos corridas seguidas producen los mismos `.tex` (md5 idéntico).
- Fuga: `git grep` de dos frases de la variante 2 en ficheros versionados →
  0 coincidencias.
- Render: `pdftotext` del control de laboratorio muestra `L = 24,0 ± 0,2 cm`
  (sin `$`, `\pm` ni `\pi` literales).
- `execution/test_generar_material_curso.py`: 103 aserciones, 0 fallos.

## Pendientes
- Commit de esta bitácora (los bancos y los `.tex`/`.pdf` de controles no se
  versionan: gitignored por diseño).
- Dimensión `examen_filtrado` en `flujo_auditar_repo.py` (sigue aplazada por
  decisión del usuario del 2026-11-08).
- Si se quiere una tercera variante o reutilizar la 2 en otro semestre, hay que
  volver a redactar y marcarla `utilizable`; la variante 2 no debe publicarse.
