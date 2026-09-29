# 2026-09-19 — problemas_resueltos_7_8

## Tema
problemas_resueltos_7_8

## Contexto
- Continuación de la sesión de revisión de los apuntes `docs/CIRC_DISP_ELECT/Tema_7_Respuesta_AC.pdf`
  y `Tema_8_Modelo_Híbrido.pdf` (Prof. Julima Anato). Tras el informe `revision.tex/pdf`,
  el usuario pidió generar 20 problemas resueltos y bien explicados "como para un adolescente
  de 15 años" (10 de cada tema) y guardarlos en `problemas_resueltos_7_8.tex/pdf`, eliminando
  los auxiliares de compilación.

## Decisiones (usuario)
1. Aprobó el plan de autoría DIRECTA (yo, sin LLM): no consume créditos OpenRouter y permite
   ajustar el nivel "15 años" y explicar el porqué de cada paso. Se descartó
   `flujo_elaborar_ejercicios.py` (LLM tier opus, consume créditos, produce bancos de ejercicios
   no "resueltos+explicados").
2. Ubicación `docs/CIRC_DISP_ELECT/` (junto a los PDFs y a `revision.tex`), estilo infografía
   del repo, compilado con `compile_latex_code(clean=True)`.

## Actividades
- Validación previa de figuras con compilación de prueba aislada (`.tmp/figtest.py`) para
  proteger el retry budget. Hallazgo: la fuente de corriente controlada NO es `cccs` en esta
  versión de circuitikz; el bipolo correcto es `cI` / `cisource` (verificado grepeando
  `pgfcircbipoles.tex`). Corregido y re-validado: 0 errores.
- Diseño de un circuito de ejemplo coherente para dar continuidad numérica entre problemas:
  Tema 7 (VCC=12V, RC=2.2k, RE=220, RL=4.7k, β=100, VCEsat=0.2V; RC//RL≈1.5k; Q≈(3mA,4.74V));
  Tema 8 (hie=1k, hfe=100, RB=10k, mismos RC/RL/RE). Puente didáctico: hie≈β·25mV/ICQ, re≈25mV/ICQ.
  Todos los resultados numéricos verificados a mano (Zi=909Ω, Zo=2.2k, Av=-150, Ai=-29; sin CE:
  Zi≈7.0k, Av≈-6.46, Ai≈-9.6; MDS ICQ=3.01mA; diseño R1≈2.5k, R2≈18.5k).
- Generador `.tmp/gen_problemas_7_8.py` (importa `PREAMBULO_INFOGRAFIA`, añade 3 cajas tcolorbox
  propias: problemaBox/solucionBox/porqueBox) + cuerpo `.tmp/cuerpo_problemas_7_8.tex`.
- Estructura por problema: enunciado (caja azul) + solución paso a paso (caja verde) + "¿Por qué?"
  intuitivo (caja amarilla) + etiqueta de dificultad (\facil/\intermedio/\dificil). Incluye 2 figuras
  (recta de carga en tikz; modelo híbrido en circuitikz), hoja de fórmulas final y notas de notación.
- Compilación: 1ª pasada detectó 1 overfull hbox (32pt) en la caja de datos del circuito → se partió
  la ecuación en dos renglones. Recompilado con clean=True: SUCCESS, 14 páginas, 0 errores,
  0 referencias rotas, 0 overfull >10pt. Auxiliares eliminados automáticamente.
- Verificación final: la carpeta queda solo con `.tex`/`.pdf`; conteo de 20 problemaBox (7.1-7.10,
  8.1-8.10). Limpieza de dirs de prueba `.tmp/inspeccion` y `.tmp/figtest_build`.
- CORRECCIÓN posterior (petición del usuario): en la Figura 2 (modelo híbrido, `fig:hibrido`) las
  ramas de salida `R_C` y `R_L` salían en diagonal desde el colector. Se redibujó la salida con un
  riel horizontal de colector y las tres ramas (fuente `h_fe·i_b`, `R_C`, `R_L`) cayendo VERTICALES
  a tierra (paralelo correcto) + puntos de conexión `circ`. `R_L` de (7.9,3)→(7.9,0). Recompilado:
  0 errores, 0 overfull, 14 págs., auxiliares limpiados.
- AJUSTE posterior (petición del usuario): la etiqueta de la fuente de corriente `h_fe·i_b` solapaba
  a `R_C`/`R_L`. Se desplazaron ambas ramas a la derecha (`R_C` x=6.6→7.6, `R_L` x=7.9→8.9) y se
  extendió el riel de colector hasta x=8.9. Recompilado: 0 errores, 0 overfull (la figura más ancha
  sigue dentro de márgenes), 14 págs., auxiliares limpiados.

## Pendientes
- Ninguno del pedido. (Opcional, si el usuario lo desea: versión PDF con soluciones ocultas para
  usar como práctica, o exportar los problemas a ejercicios/ con `flujo_elaborar_ejercicios.py`.)
