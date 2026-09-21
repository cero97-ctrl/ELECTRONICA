# 2026-09-21 — OmniRoute

## Tema
Análisis del gateway AI OmniRoute (diegosouzapw/OmniRoute) y su relación con la
arquitectura de enrutamiento determinista del workspace.

## Contexto
- El usuario preguntó si conocía OmniRoute y proporcionó el repositorio
  https://github.com/diegosouzapw/OmniRoute como referencia canónica.
- OmniRoute es un gateway AI local-first (MIT, TypeScript/Next 16, v3.8.51,
  ~68.8k stars): agrega 357+ proveedores (152 con free tier) detrás de un único
  endpoint OpenAI-compatible en `localhost:20128/v1`, con auto-fallback
  cuota-aware, 19 estrategias de ruteo, compresión de tokens (RTK+Caveman,
  15-95%) y soporte MCP/A2A. Compatible con Claude Code, Codex, Cursor, Cline,
  Copilot y OpenCode (plugin `@omniroute/opencode-provider`).
- Relevancia para el workspace: puente potencial de fallback económico para
  `openrouter_chat`, respetando la decisión determinista de `enrutador.py`.

## Decisiones (usuario)
1. "Analízalo simplemente": análisis informativo, sin integración ni instalación.
2. "Documenta este análisis (bitácora / doc)": registro de sesión en
   `Sessions/2026-09-21_omniroute.md` + documento de análisis en
   `docs/ARQUITECTURA_ENRUTAMIENTO_LLM/analisis_omniroute.md` (mismo directorio
   y formato markdown que la doc de autoridad sobre enrutamiento).

## Actividades
- Búsqueda web de "OmniRoute software tool" y fetch del README del repo
  diegosouzapw/OmniRoute (branch release/v3.8.51).
- `estado_sesion.py check`: veredicto ok, sin run_state huérfanos a purgar.
- Creación de bitácora vía `execution/bitacoras.py nueva --tema "OmniRoute"`.
- Redacción de `docs/ARQUITECTURA_ENRUTAMIENTO_LLM/analisis_omniroute.md`
  (qué es, arquitectura, fortalezas, debilidades/riesgos, relevancia para el
  workspace, y comparativa de principio con enrutador.py).
- Commit de la bitácora y la doc con el trabajo de la sesión.

## Pendientes
- (Ninguno acordado.) Evaluar a futuro si OmniRoute vale como capa de fallback
  gratuita para proveedores de OpenRouter con saldo bajo; requiere nueva decisión
  del usuario y quedaría fuera del espíritu determinista si se usa solo como
  ejecutor (la decisión de modelo seguiría en `enrutador.py`).