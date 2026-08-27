# Sesión 2026-08-27 — Revisión de docs de agentes IA (backtracking y codebase-memory)

## Tema
Revisión y corrección de dos documentos en `docs/AGENTE_IA/` que contienen conversaciones con LLM técnicas sobre patrones de agentes IA: *Backtracking* y *CodeBase Memory*.

## Actividades
1. **Revisión de `conversacion_backtracking_agentes_ia.md`**: el documento describía el "Backtracking" como técnica de corrección de errores en agentes IA. Se detectaron matices a corregir:
   - Confundía dos técnicas: *Tree of Thoughts* (rebobinar razonamiento) vs *checkpoint/rollback de estado* (revertir artefactos) — el agente real revierte artefactos, no su razonamiento.
   - Faltaban: retry budget (máx 3), análisis de causa raíz (Lógica/Entorno/Recursos) antes de reintentar, verificación determinista vs validación de I/O, y principio "fail loudly".
2. **Versión corregida de backtracking**: se reescribió el documento separando ambas técnicas (con tabla), ciclo de producción en 7 pasos, diagrama corregido con flujo de escalada al humano, y resumen de matices. Alineado con la filosofía real del workspace (self-annealing, retry budget, `Sessions/`, `.agent/*.md`, actualización de directivas).
3. **Revisión de `conversacion_codebase_memory.md`**: sobre la herramienta `DeusData/codebase-memory-mcp`. Se contrastó con el repositorio real vía búsqueda web:
   - Confirmado: binario estático, tree-sitter (158 lenguajes), capa Hybrid LSP, UI 3D en `localhost:9749`, OpenCode entre los clientes soportados.
   - Corregido: "SQLite en RAM+LZ4" (en realidad persistente en `~/.cache/codebase-memory-mcp/`, WAL, sobrevive reinicios); "99% menos tokens" es marketing del README (el paper arXiv:2603.27277 reporta ~10×/≈90%); C puro (no C/C++); 14 tools MCP (no 15); "LSP" ≠ procesos LSP (es implementación embebida de resolución de tipos).
   - Añadido: watcher de auto-sync incremental, modo CLI, `get_architecture`, y sección de contraste RAG (semántico) vs grafo estructural (simbólico) — ortogonales y complementarios, relevante porque el workspace ya tiene RAG con ChromaDB.

## Decisiones
- Ambos documentos se reescribieron en su misma ruta con formato de conversación preservado y matices anotados inline como **\[Corrección v2]**, más resumen de matices al final.
- No se tocó ningún script de `execution/`; trabajo documental puro, sin consumo de créditos OpenRouter.

## Entregables
- `docs/AGENTE_IA/conversacion_backtracking_agentes_ia.md` (versión corregida)
- `docs/AGENTE_IA/conversacion_codebase_memory.md` (versión corregida)
- `Sessions/2026-08-27_revision_docs_agentes_ia.md` (este log)

## Pendientes
- El usuario puede querer revisar la precisión de las cifras citadas de los benchmarks del preprint (arXiv:2603.27277) si el documento se usa como referencia citable.
- Confirmar si se commitea esta sesión (es política del workspace commitear con el resto del trabajo).