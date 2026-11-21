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

## Pendientes
- Autorización de commit/push para estos ficheros (no ejecutado).
- Recordatorio 24-nov antes de 08:00 VET: publicar el cuestionario con
  `flujo_publicar_cuestionario.py ... --visibilidad public --push` y volver a
  `private` al cerrar.
- Desglose por modelo del cargo de $0.04: sin acceso a `/api/v1/activity`
  (403, requiere management key); no bloquea nada.
