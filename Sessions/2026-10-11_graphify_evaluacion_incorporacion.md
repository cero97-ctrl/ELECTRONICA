# 2026-10-11 — graphify_evaluacion_incorporacion

## Tema
graphify_evaluacion_incorporacion

## Contexto
- El usuario pide examinar el repo `Graphify-Labs/graphify` y su posible adopción en
  ELECTRONICA. En el chat se elige la opción "Evaluación de adopción" (no instalación
  real) y luego se pide volcar esa evaluación en un documento LaTeX/PDF que sirva de
  guía para implementar Graphify en la nueva PC "HP EliteDesk 805 G6".
- Recuperado contexto previo: `Sessions/2026-10-10_veredicto_hardware_hp_elitedesk.md`
  (decisión de compra, Unidad B: 256 GB, $340) y estilo del doc hermano
  `docs/PC_PARA_IA/HP_ELITEDESK_VEREDICTO.tex`.

## Decisiones (usuario)
1. Alcance = **evaluación de adopción**, no instalación (nada se ejecuta contra el repo).
2. Entregable = documento **LaTeX/PDF** de "evaluación de incorporación" con guía de
   implementación para la HP EliteDesk 805 G6.
3. (Asumido, sin contradicción del usuario) Ubicación del doc en
   `docs/AGENTE_IA/graphify_evaluacion_incorporacion.tex` (familia AGENTE_IA, hermana de
   `dsh_evaluacion_incorporacion.tex`); reutilizar el preámbulo infográfico inline de la
   familia `PC_PARA_IA`.

## Actividades
- Análisis de Graphify: `README.md`, `ARCHITECTURE.md`, `pyproject.toml` y releases
  v0.9.76–v0.9.85. Datos clave: repo `Graphify-Labs/graphify`, v0.9.85 (2026-10-10),
  Apache-2.0+MIT, Python ≥3.10, PyPI `graphifyy` (CLI `graphify`), deps networkx/numpy/
  rapidfuzz/tree-sitter (~26 gramáticas), extras `[leiden]`/`[mcp]`; salida
  `graph.json`/`graph.html`/`GRAPH_REPORT.md`; sin vectores y sin telemetría; pipeline
  determinista para código, pase semántico con LLM solo para docs/PDF/imágenes.
- Inspección local: `execution/`, `rag_system.py`, `db_state.json`, `requirements.txt`;
  memoria (3,63 GB, ~641 MB libres); `uvx` 0.11.11; repo 1,4 GB / 2105 ficheros.
- Entregada en chat la **Evaluación de adopción** (encaje, beneficios, riesgos,
  comparativa con el RAG, veredicto, plan por fases).
- Creada bitácora con `execution/bitacoras.py nueva --tema graphify_evaluacion_incorporacion`.
- Generado el documento:
  - Preámbulo reutilizado por corte deterministico (`sed -n '1,332p'`) del doc de la HP;
    añadidos `\usepackage{url}` y `\usepackage{needspace}` más cabecera propia
    (`\fancyhead`, `\hypersetup`, `\iconoBanda`).
  - Cuerpo de 10 secciones: resumen ejecutivo, qué es Graphify, encaje con las 3 capas,
    beneficios, riesgos (tabla), comparación con el RAG, veredicto, guía de
    implementación en la HP EliteDesk, criterios de aceptación y referencias.
  - Compilación: `pdflatex` (3 pasadas) → **0 errores**, 10 páginas, 0 solapes;
    verificado con `execution/verificar_pdf.py` → `{"status":"ok"}`.
  - Corregida trampa #17 de `.agent/latex.md`: `cajaMejora` es `.style`, no entorno →
    usada como opción de `tcolorbox` (dos ocurrencias). Único overfull restante (6,79 pt)
    es el glyph del icono de `\bandaTitulo` (fontawesome 30pt): cosmético, ajeno al cuerpo.
  - Limpiados los auxiliares (`aux/log/out/toc`); quedan solo `.tex` (35,8 KB) y `.pdf`.

## Pendientes
- **Piloto real** de Graphify en la HP EliteDesk (listo para cuando llegue el equipo):
  `uv tool install graphifyy` → `graphify install --platform opencode` (merge manual de
  `AGENTS.md`) → `graphify extract --code-only .` → verificar determinismo por hash.
- Si la adopción deja de ser "herramienta" y pasa a "flujo", crear las 3 capas:
  `directives/graphify_code.yaml` + orquestador + `execution/graphify_build.py`.
- El pase semántico (docs/PDF) nunca debe resolverse inline: va por
  `execution/enrutador.py` (`--task destilacion`).
- Al recibir la HP: confirmar CPU **4650GE** (no 4350GE), `execution/env_diagnostic.py`
  (AVX2) y `flujo_auditar_sistema.py` (ya anotado como criterio de aceptación del doc de
  hardware).
