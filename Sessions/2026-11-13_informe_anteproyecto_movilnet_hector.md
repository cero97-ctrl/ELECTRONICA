# 2026-11-13 — informe_anteproyecto_movilnet_hector

## Tema
Informe de análisis crítico del anteproyecto de grado de Héctor Saldivia
(control energético Arduino/ESP32 para la radio base Movilnet de San José de
Aerocuar).

## Contexto
- El usuario aportó `cursos/TESIS/HECTOR/Anteproyecto_Movilnet.pdf` (28 páginas,
  6.899 palabras, sin figuras, tablas ni bibliografía) y pidió leerlo, analizarlo
  y entregar un informe en LaTeX (tex/pdf) en la misma carpeta.
- La lectura directa del PDF no es posible con el motor del asistente (sin soporte
  de entrada PDF), así que el texto se extrajo con `pdftotext -layout` a
  `.tmp/anteproyecto.txt`.
- No había bitácora previa del tema en `Sessions/` (se verificó el listado).

## Decisiones (usuario)
1. El informe se guarda en `cursos/TESIS/HECTOR/`, junto al anteproyecto.
2. Se entrega en LaTeX y PDF (formato explícito pedido).
3. Enfoque crítico-académico, conforme a la directriz del workspace para revisión
   de propuestas de grado (objetivos SMART, modularización, rigor metodológico).

## Actividades
- Extracción y lectura completa del anteproyecto (28 pp.).
- Verificación estructural: `pdfimages` confirma una sola imagen (escudo de
  portada); no hay figuras ni tablas; no existe lista de referencias; índice con
  5 entradas frente a 9 secciones reales.
- Análisis técnico: arquitectura Arduino UNO + ESP32 redundante; divisor resistivo
  insuficiente para estimar SoC (curva plana de LiFePO4, error de ADC); módulo relé
  frente a interfaz real de arranque (precalentamiento, solenoide, presión de
  aceite, parada de emergencia, transferencia con enclavamiento); MQ-135 no mide
  CO2/CO/NOx con trazabilidad; conectividad Wi-Fi y ciberseguridad del lazo de
  control; balance energético (el ahorro de diésel no es automático si el banco se
  recarga con el mismo generador); separación GEI vs contaminantes locales;
  cálculo de emisiones con factor IPCC (2,68 kg CO2/L) y tabla de sensibilidad;
  el argumento sonoro no queda resuelto por el control de arranque.
- Análisis metodológico: tensión positivismo/enfoque mixto sin instrumentos
  cualitativos; RUP como metodología única para hardware; pre-experimento sin
  protocolo de medición ni criterios de aceptación; se propone cuadro de
  operacionalización de variables y reformulación SMART de los 4 objetivos.
- Análisis documental: cero referencias; citas incompletas ("Peter landau",
  "Parr 2"); antecedente venezolano rotulado como internacional; topónimo
  "Aereocuar"/"Aerocuar"; erratas y numeración inconsistente.
- Generación del entregable: cuerpo en `.tmp/cuerpo_informe_hector.tex`, ensamblado
  con `PREAMBULO_INFOGRAFIA` (estilo canónico) y compilado aislado en
  `.tmp/latex_build/`. Resultado: 16 páginas, 0 errores `!`, 0 `Overfull \hbox`.
- Entregables: `cursos/TESIS/HECTOR/Informe_Analisis_Anteproyecto_Movilnet.tex`
  y `.pdf`.

## Pendientes
- El usuario no ha pedido correcciones sobre el anteproyecto ni una segunda
  versión del informe; queda a la espera de su revisión.
- Las correcciones de prioridad 1 propuestas en el informe (hipótesis medible,
  instrumento de consumo, interfaz de arranque segura, bibliografía) son
  responsabilidad del autor del anteproyecto, no de este workspace.
