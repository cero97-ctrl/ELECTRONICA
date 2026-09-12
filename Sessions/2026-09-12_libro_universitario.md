# 2026-09-12 — Libro universitario en PDF (planificado a futuro)

## Tema
Recopilar lo desarrollado en este workspace en un **libro en PDF** con formato
infográfico, destinado a los estudiantes de la universidad donde trabaja el usuario.

## Contexto
- Tarea **planificada a futuro**, NO a ejecutar hoy. Solo registro de intención y
  alcance para retomar cuando el usuario lo decida.
- La solicitud surgió al cierre de una sesión sobre el ajuste del documento de la PC
  de IA (B650 Workstation), tras confirmar que la filosofía de 3 capas
  (directivas/orquestación/ejecución) permanece intacta.

## Decisiones (usuario)
1. Registrar el libro como tarea futura en una bitácora dedicada
   `Sessions/2026-09-12_libro_universitario.md` (no mezclarlo con el pendiente de la
   sesión de la PC).
2. El libro irá en **formato PDF** con el estilo infográfico del proyecto
   (`execution/estilo_infografia.py` → `PREAMBULO_INFOGRAFIA`), apto para entrega a
   estudiantes universitarios.
3. Material potencial a incluir (alcance preliminar, a cerrar en el futuro):
   arquitectura de 3 capas, flujos `flujo_*`/`mcp_*` con sus diagramas ISO 5807,
   enrutamiento multi-LLM determinista, memoria persistente (bitácoras `Sessions/`,
   RAG/ChromaDB), y entregables LaTeX ya existentes (`docs/`, `cursos/`, `GIDEAL/`).

## Actividades
- 2026-09-12: creación de esta bitácora como registro de la tarea futura.
- (Sin actividades de desarrollo: la tarea es a futuro.)

## Pendientes
- **Planificar** el libro universitario en PDF (cuando el usuario lo indique):
  1. Crear bitácora/tema dedicado en `docs/` (ej. `LIBRO_UNIVERSITARIO/`) con el
     índice propuesto y la selección de material.
  2. Definir capítulos: arquitectura 3 capas, flujos/orquestadores, enrutamiento
     LLM, memoria, entregables tipo.
  3. **Restricción de contenido:** excluir material gitignoreado (datasets crudos en
     `datasets/`, PDFs de exámenes `examen*`, telemetría `.tmp/`).
  4. Generar el PDF con el motor infográfico y verificar con `verificar_pdf.py`.