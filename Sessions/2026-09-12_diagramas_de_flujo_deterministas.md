# 2026-09-12 — diagramas_de_flujo_deterministas

## Tema
Institucionalizar diagramas de flujo ISO 5807 generados de forma determinista para todo
flujo grande del repo terminado (Opción B del plan aprobado).

## Contexto
- El usuario pidió que "tener un Diagrama de Flujo me ayuda a entender con rapidez
  cualquier proceso hayamos terminado". Tras analizar patrones existentes
  (docs/AGENTE_IA/faq_higiene_estado_sesion_flujo.tex con estilos TiKZ ISO 5807 canónicos)
  y tras un cuestionario, se eligió: alcance = "solo flujos grandes del repo" e
  implementación = "generador determinista" en vez de copiar a mano diagramas TikZ.
- Antes de esta sesión el font/plantillas de estilo vivían duplicados en cada .tex que
  dibujaba diagramas; no existía un script layer-3 para producirlos.

## Decisiones (usuario)
1. El generador es determinista: mismo descriptor JSON -> mismo .tex -> mismo diagrama
   (la variación del hash binario del PDF se acepta como timestamp de metadata de
   pdflatex, irrelevante; el .tex sí es byte-idéntico).
2. Alcance: aplicar la convención SOLO a flujos grandes (flujo_*, mcp_* con 3 capas);
   no se genera retroactivamente para todos los procesos pasados.
3. El orquestador (agente) es quien modela el proceso terminado como descriptor JSON
   (parsing/geometría), y ejecuta el generador; la lógica de render vive en el script.
4. Formato de entrega: docs/<tema>/<proceso>_flujo.{tex,pdf}; descriptor intermedio en
   .tmp/descriptor_<proceso>.json (regenerable, no versionado).

## Actividades
- Creado execution/generar_diagrama_flujo.py (Layer 3): valida descriptor (tipos de nodo
  del vocabulario: terminador/proceso/decision/almacenamiento/entradasalida/documento/
  nota; ids únicos; conexiones consistentes), genera .tex con PREAMBULO_INFOGRAFIA +
  bloque de estilos ISO 5807 embebido en el propio script, compila 2 pasadas vía
  compile_latex.py y verifica vía verificar_pdf.py. CLI: --descriptor (obligatorio),
  --output (copia PDF+tex al destino), --dry-run (solo .tex). Path-agnostic (resolve
  project_root por __file__ y añade sys.path). Códigos 1=descriptor inválido,
  2=compilación fallida.
- Pitfall resuelto: f-strings con llaves LaTeX anidadas (single '}' no permitido) en las
  plantillas de \section — resuelto componiendo textos con interpolación simple fuera de
  las cadenas heredoc.
- Creado directives/diagrama_flujo.yaml (Layer 1 SOP): goal, required_inputs (descriptor,
  output), steps (extraer_estructura -> generar -> verificar -> publicar), expected_outputs,
  edge_cases.
- Actualizado AGENTS.md (Output conventions): convención de diagramas para flujos grandes.
- Test de referencia: descriptor .tmp/descriptor_sync_faq_flujo.json modela el proceso
  sync FAQ->flujo; generado y publicado a docs/AGENTE_IA/sync_faq_flujo_flujo.{tex,pdf}.
  Resultado: 3 páginas, 0 errores LaTeX, 0 overfull, 0 solapes (verificación doble del
  generador y de verificar_pdf.py independiente). Determinismo confirmado (tex idéntico
  en 2a ejecución). Validación de error OK (tipo 'circulo' -> exit 1).

## Pendientes
- Commitear la convención (3 capas: script + directiva + AGENTS.md + bitácora + PDF de
  referencia) cuando el usuario lo autorice.
- Aplicar la convención a flujos grandes futuros al cerrarlos (no retroactivo).