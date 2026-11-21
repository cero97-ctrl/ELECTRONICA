# 2026-11-21 — correccion_tabla1_practica01_ocr

## Tema
correccion_tabla1_practica01_ocr

## Contexto
- Tras reemplazar P01–P08 por OCR+TikZ, `practica_01.pdf` página 3 mostraba los
  delimitadores `[TABLA:` / `]` del escaneo y la leyenda `] TABLA 1` sin centrar
  al pie de la tabla de resistores. Confirmado con `pdftotext -f 3 -l 3`.
- El OCR es la fuente de verdad de P1–P8; editar el `.tex` derivado se pierde en
  la próxima regeneración.

## Decisiones (usuario)
1. El usuario eligió «OCR + generador y regenerar (Recomendado)»: quitar los
   marcadores del OCR, añadir limpieza defensiva + leyenda centrada al
   generador, regenerar P1–P8 y verificar logs.
2. Sin commit/push sin autorización explícita: los cambios de esta corrección
   quedan sin commitear.

## Actividades
- `execution/generar_practicas_desde_ocr.py`: `RE_MARCA_TABLA` y
  `RE_LEYENDA_TABLA`; `limpiar_markdown()` omite `[TABLA:`; `convertir_bloques()`
  emite `TABLA N` como `\begin{center}\small\textbf{TABLA N}\end{center}`;
  `validar_practicas()` rechaza marcadores residuales y nombra cuál queda.
- `cursos/LABORATORIO_II_FISICA/docs/practicas_ocr_completo.md`: eliminados los
  4 marcadores de P1 (dos `[TABLA:` y dos `]`); conservadas las leyendas.
- `execution/test_generar_practicas_desde_ocr.py`: 9 aserciones nuevas (87 en
  total, 0 fallos), incluido el test del OCR real sin marcadores.
- Regeneración con `flujo_dibujar_figuras_tikz.py --ocr <OCR promovido>
  --salida-practicas cursos/LABORATORIO_II_FISICA/practicas`: 34 figuras
  cacheadas, 8 prácticas, sin llamadas a API (coste $0).
- Verificación: 0 marcadores `[TABLA:` en los `.tex`; 34 entornos TikZ (30
  `circuitikz` + 4 `tikzpicture`); 8 logs con 0 líneas `!` y 0 `Overfull
  \hbox`; `pdftotext` página 3 muestra `TABLA 1` centrada al pie.
- Diff contra `.tmp/practicas_antes_tabla_20261121/`: solo P01 cambió (10
  líneas); P02–P08 byte-idénticos; P09/P10 intactos (SHA-256 verificados).
- Directiva `directives/ocr_a_practicas.yaml` e índice de tests en `AGENTS.md`
  actualizados con el nuevo contrato.

## Incidencia y corrección (commit `e9020374` → `6734a59`)
- El usuario autorizó «Commit nuevo + push». `update_repo.sh` hace `git add -A`
  e incluyó por error `cursos/LABORATORIO_I_FISICA/ALUMNOS_LAB_I_FISICA.pdf`,
  que estaba marcado como «no tocar» en el contexto de la sesión. El fichero
  contiene cédulas, nombres y correos de 2 estudiantes y el repo es público.
  El error fue del orquestador: no excluí el untracked conocido del staging.
- Impacto: el fichero no existía en el historial anterior; apareció por primera
  y única vez en `e9020374`, ya pusheado. La exposición ocurrió antes de la
  corrección; quitarlo del HEAD no habría bastado.
- El usuario autorizó reescribir historia. Copia de seguridad local del PDF en
  `/tmp/opencode/backup_pii_lab_i/` (SHA-256 `d5f890c0…`), ejecutado
  `git filter-repo --invert-paths --path cursos/LABORATORIO_I_FISICA/ALUMNOS_LAB_I_FISICA.pdf`
  (con `Y` a «continuar la ejecución anterior» de 2026-11-08), restaurado el
  PDF al disco y añadida regla explícita en `.gitignore`.
- Solo cambió el último commit (`e9020374` → `6734a59`); `bba5f76b` y anteriores
  conservan su hash. `git log --all -- <ruta>` y `git ls-tree HEAD` dan vacío.
- Lección para el orquestador: antes de `update_repo.sh` con cambios sin marcar,
  revisar `git status --short` y staged explícitamente SOLO los ficheros
  autorizados, o ampliar `.gitignore` primero. Nunca asumir que un untracked
  conocido quedará fuera de un `git add -A`.

## Pendientes
- Completar el force push de la historia reescrita y verificar con un clone
  fresco que el PDF no aparece en el remoto.
- Avisar a quienes hubieran clonado el repo: conservan su copia local del PDF.
- Recordatorio 24-nov antes de 08:00 VET: publicar el cuestionario con
  `flujo_publicar_cuestionario.py ... --visibilidad public --push` y volver a
  `private` al cerrar.
- Desglose por modelo del cargo de $0.04: sin acceso a `/api/v1/activity`
  (403, requiere management key); no bloquea nada.
