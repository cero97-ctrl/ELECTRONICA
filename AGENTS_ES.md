# AGENTS_ES.md — ELECTRONICA

> Traducción al español de `AGENTS.md`. El contenido operativo es idéntico; solo cambia el idioma de las descripciones. Los comandos, rutas y nombres de archivo no se traducen.

## Arquitectura de 3 capas (obligatoria en todo nuevo flujo de trabajo)

| Capa | Dónde | Qué hace |
|---|---|---|
| **Directivas** | `directives/*.yaml` | SOP — *qué* hacer |
| **Orquestación** | `flujo_*`, `mcp_*` (raíz) | Lógica de decisión/validación; puede servir herramientas MCP |
| **Ejecución** | `execution/*.py` | Script determinista — *cómo* |

Un nuevo flujo de trabajo debe incluir las tres capas; nunca escribas solo un orquestador sin su directiva y su script de ejecución.

## Configuración

| Archivo | Contenido |
|---|---|
| `.groq_api_key` | Clave de API de Groq (LLMs de texto) |
| `.env` | `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`, `TELEGRAM_BOT_TOKEN` |

`opencode.json` carga `instructions: [".agent/*.md"]` — esas son tus instrucciones operativas principales.

## Antes de actuar

- **Antes de modificar cualquier archivo `.tex`**, lee `.agent/latex.md` (16 errores LaTeX documentados específicos de este proyecto)
- **Antes de modificar scripts que usen LangChain o parseen JSON de un LLM**, lee `.agent/python.md` (PromptTemplate en modo jinja2, raw strings, trailing commas, extracción de JSON con llaves balanceadas)
- **`requirements.txt` solo contiene `psutil` y `PyYAML`** — las dependencias reales viven en el entorno conda; no lo tomes como fuente canónica
- **No hay linter, type checker, formatter ni CI** configurados — no pierdas tiempo ejecutándolos
- **Ejecuta todo desde la raíz del repositorio** — los imports usan rutas relativas; `mcp_latex_server.py`, `mcp_sistema_server.py` y `execution/compile_latex.py` tienen `sys.path.append()` pero los scripts de nivel raíz no lo necesitan. Los MCP servers más nuevos (`mcp_analizar_server.py`, `mcp_diagnostico_server.py`, `mcp_elaborar_server.py`, `mcp_evaluar_server.py`) resuelven su propio `project_root` vía `os.path.dirname(os.path.abspath(__file__))` y cargan `.env` desde ahí — son agnósticos de la ruta y pueden ejecutarse desde cualquier lugar

## Comandos

**Tests:** `python test_generator.py` (JSON EDA, cero dependencias externas)

**RAG:** `python rag_system.py` (chat), `python rag_system.py --update` (reconstruir vectores)

**Reparación LaTeX:** `python fix_latex.py <archivo.tex>` (extrae comandos matemáticos de `\text{}`)

### Flujos orquestadores
```
flujo_evaluar_examen.py    --pdf <archivo.pdf> [--rubrica <yaml>]
flujo_analizar_imagen.py   "glob|archivo1,archivo2" [--prompt "..."]
flujo_elaborar_examen.py   --tema "Semana 4: Condensadores" --output examenes/
flujo_elaborar_ejercicios.py --tema "Semana 8: BJT" --path ejercicios/BJT
flujo_imagen_a_kicad.py    circuito.png
flujo_diagnostico.py
flujo_curar_dataset.py     [--min-quality 0.7] [--split 80-10-10] [--dry-run] [--no-alert]
flujo_empaquetar_dataset.py [--format parquet|jsonl] [--license <lic>] [--pack] [--no-alert]
flujo_publicar_hf.py        <dataset> [--repo <id>] [--private] [--dry-run] [--no-alert]
flujo_ruview_rescue.py      (listener UDP :5005 — datos CSI/acelerómetro; config en directives/ruview_rescue.yaml)
flujo_telegram.py           (Telegram gateway polling — config en directives/telegram_gateway.yaml)
```

### Servidores MCP (`mcp_*_server.py`, FastMCP)
```
mcp_analizar_server.py     Circuit Vision Server   → flujo_analizar_imagen (directives/analizar_imagen_mcp.yaml)
mcp_diagnostico_server.py  System Diagnostic      → flujo_diagnostico     (directives/diagnostico_mcp.yaml)
mcp_elaborar_server.py     Examen Elaborator      → flujo_elaborar_examen (directives/elaborar_examen_mcp.yaml)
mcp_evaluar_server.py      Examen Evaluator       → flujo_evaluar_examen  (directives/evaluar_examen_mcp.yaml)
mcp_latex_server.py        LaTeX Compiler         → compile_latex.py      (directives/latex_mcp_server.yaml)
mcp_sistema_server.py      System Control         → system_control.py     (directives/sistema_mcp.yaml)
```

### Servicios del sistema
```
sudo ./manage_bot.sh       — Telegram gateway (telegram_gateway.service)
sudo ./manage_waydroid.sh  — Contenedor Android Waydroid
```

## Convenciones de salida

- El JSON intermedio vive en `.tmp/` (p. ej. `.tmp/analisis_*.json`)
- `.tmp/run_state.json` rastrea el progreso de flujos multi-paso (paso, exit code, timestamp)
- Datasets de entrenamiento LLM: captura cruda en `datasets/*.jsonl` (`execution/data_capture.py`, pasivo, gitignored); curado/particionado en `datasets/curated/` (`execution/curar_datasets.py` o `flujo_curar_dataset.py`); paquetes HF (Parquet+LICENSE+README) en `datasets/paquetes/` (`execution/empaquetar_dataset.py` o `flujo_empaquetar_dataset.py`); publicación HF Hub (`execution/publicar_hf.py` o `flujo_publicar_hf.py`, requiere `HF_TOKEN` en `.env`)
- Los entregables LaTeX van a `docs/` o `cursos/` bajo sus directorios temáticos
- Los artefactos de compilación LaTeX van a `.tmp/latex_build/` (auto-limpiados por `compile_latex.py`)

## Particularidades de Git

- `chroma_db/` excluido (supera los 100 MB de GitHub) — `git rm -r --cached chroma_db/` si se rastrea por accidente
- `examen*` fijado en `.gitignore` — los PDF/`.tex` de exámenes que empiecen con `examen` nunca se confirman
- `db_state.json` está rastreado (no se autogenera en el sentido de CI, pero es el archivo de estado del RAG — ten cuidado al modificarlo)

## Convenciones LaTeX

- `\usepackage[spanish,es-noshorthands]{babel}`, `circuitikz`, `siunitx`, `amsmath`
- JSON EDA a EasyEDA: strings `LIB~...` en `shape[]`, sub-elementos separados por `#@$`, pines por `^^`
