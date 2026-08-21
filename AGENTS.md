# AGENTS.md — ELECTRONICA

## 3-Layer Architecture (must follow for every new workflow)

| Layer | Where | What |
|---|---|---|
| **Directives** | `directives/*.yaml` | SOP — *what* to do |
| **Orchestration** | `flujo_*`, `mcp_*` (root) | Decision/validation logic; may serve MCP tools |
| **Execution** | `execution/*.py` | Deterministic script — *how* |

A new workflow must include all three layers; never write just an orchestrator without a directive and execution script.

### Determinism guardrail (alert before executing)

El usuario pidió explícitamente ser alertado cuando una de sus peticiones viole el espíritu determinista del proyecto. Si detectas una de estas violaciones, **DETENTE, alerta al usuario explicando el porqué y propone la alternativa conforme ANTES de ejecutar**:
- Elegir modelo/tier razonando en el chat → ejecutar `execution/enrutador.py` (la decisión es función pura del descriptor).
- Meter lógica de decisión/negocio dentro de prompts o del chat → esa lógica vive en `execution/*.py`.
- Crear un flujo repetible sin sus 3 capas (directiva + orquestador + script).
- Procesar/raspear datos inline en el chat en lugar de un script determinista reutilizable.
- Cambios que rompan reproducibilidad (mismo input → output distinto) o se salten la validación de entradas/salidas y el retry budget (máx 3).

Solo procedas con la petición original si el usuario la confirma tras la alerta (decisión consciente suya); registra la excepción en el log de sesión.

## Configuration

| File | Content |
|---|---|
| `.groq_api_key` | Groq API key (fallback provider `groq`) |
| `.env` | `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_MAX_TOKENS`, `TELEGRAM_BOT_TOKEN`, `HF_TOKEN` |

`opencode.json` loads `instructions: [".agent/*.md"]` — those are your core operating instructions.

## Know before you act

- **Session logs (continuity):** the `Sessions/` folder (repo root) records one `.md` per session, named by topic (`Sessions/<fecha>_<tema>.md`).
  - **At the start of each new session**, before investigating anything, check `Sessions/` for the most recent log matching the topic the user brings up (glob `Sessions/*<tema>*.md`, fallback to the newest file). Read it to recover what was decided/pending — avoid re-investigating from scratch and burning tokens.
  - **Then create** this session's own log in `Sessions/<fecha>_<tema>.md` recording date, topic, activities, decisions and pending items, and commit it with the rest of the session's work.
- **Before modifying any `.tex` file**, read `.agent/latex.md` (16 documented LaTeX pitfalls specific to this project)
- **Before modifying scripts that use LangChain or parse LLM JSON**, read `.agent/python.md` (PromptTemplate jinja2 mode, raw strings, trailing commas, balanced-brace JSON extraction)
- **`requirements.txt` contains only `psutil` and `PyYAML`** — real dependencies live in the conda environment; don't trust it as canonical
- **Conda env automático en shells de opencode:** `.opencode/plugins/conda-env.js` (hook `shell.env`) antepone `elect_env` al PATH y fija `CONDA_PREFIX`/`CONDA_DEFAULT_ENV`/`VIRTUAL_ENV` en toda shell de este workspace — no re-activar ni usar `conda run`; si `CONDA_DEFAULT_ENV` desaparece, revisar ese plugin (requiere reinicio de opencode tras editarlo)
- **No linter, type checker, formatter, or CI** is configured — don't waste time running them
- **Run everything from repo root** — imports use relative paths; `mcp_latex_server.py`, `mcp_sistema_server.py` and `execution/compile_latex.py` have `sys.path.append()` but root-level scripts don't need it. The newer MCP servers (`mcp_analizar_server.py`, `mcp_diagnostico_server.py`, `mcp_elaborar_server.py`, `mcp_evaluar_server.py`) resolve their own `project_root` via `os.path.dirname(os.path.abspath(__file__))` and load `.env` from there — they are path-agnostic and can run from anywhere
- **LLM backends desde VE (geo-bloqueo):** Groq y OpenAI directos devuelven 403 (`unsupported_country_region_territory`) — solo funcionan con VPN a nivel máquina. Los backends accesibles sin VPN son **OpenRouter** (texto, `OPENROUTER_API_KEY`) y **Gemini**. `rag_system.py` y `agent_eda.py` ya usan OpenRouter (`openai/gpt-oss-20b`). Reglas: fijar siempre `max_tokens`/`max_output_tokens` (sin él OpenRouter pide 65536 y con saldo bajo devuelve 402; `OPENROUTER_MAX_TOKENS` en `.env`, default 2048, activo 8192); `qwen/qwen3.6-27b` devuelve su razonamiento como `content` (rompe extracción JSON) → usar `openai/gpt-oss-20b` para salida estructurada
- **Enrutamiento multi-LLM (determinista):** NO elijas el modelo razonando en el chat — construye el descriptor (`--task` del vocabulario controlado, tokens medidos, criticidad, visión) y ejecuta el Enrutador (ver Commands); luego invoca el script con `--api-backend openrouter --modelo <id>`. Fuente única de IDs: `MODEL_TIERS` en `execution/llm_client.py` (flash=`google/gemini-3.7-flash`, deepseek=`deepseek/deepseek-v4-pro`, glm=`z-ai/glm-5.2`, opus=`anthropic/claude-opus-5`; Kimi K3 solo por `--modelo-explicito`). Fallback cost-aware ante 429/errores de servicio, máx 3 intentos. Telemetría: `.tmp/routing_log.jsonl`. Política completa: `.agent/enrutamiento.md`, `directives/enrutamiento_llm.yaml`, `docs/ARQUITECTURA_ENRUTAMIENTO_LLM/arquitectura_enrutamiento_llm.md`
- **Motor del asistente opencode (rotativo):** es SOLO la interfaz del orquestador, NO forma parte del routing y NUNCA consume `OPENROUTER_API_KEY`. DeepSeek V4 dejó el tier Free de OpenRouter (2026-08-21); el motor pasó brevemente a `google/gemini-3.5-flash` y hoy es **Big Pickle** (`opencode/big-pickle`, modelo stealth del gateway OpenCode Zen, Free temporal). Las cuotas Free se agotan rápido y el motor puede rotar sin previo aviso, indistintamente entre Free de Zen (`opencode/big-pickle`, `x-preview-f-free`, `mimo-v2.5-free`, ...) o de OpenRouter (`z-ai/glm-5.2:free`, `openai/gpt-oss-20b:free`, `google/gemma-4-*:free`). **Facturación en `/models`:** los modelos vía Zen (`opencode/...`) facturan a la cuenta Zen aparte (los Free = $0); los modelos vía proveedor OpenRouter descuentan el saldo de `OPENROUTER_API_KEY`. Solo la ejecución real (`enrutador.py`, `rag_system.py`, `agent_eda.py`) consume créditos OpenRouter. Cambiar el motor no requiere tocar el router
- **Clipboard en el TUI (terminal Terminator/X11):** el toast "Copied to clipboard" de opencode usa OSC 52, que Terminator/VTE no soporta — ese texto NO llega al portapapeles del sistema; verificar con `xclip -o -selection clipboard` antes de asumir que existe. Copia real desde el TUI: `Shift`+seleccionar → `Ctrl+Shift+C`; pegar: `Ctrl+Shift+V`

## Commands

**Tests:** `python test_generator.py` (EDA JSON, zero external deps)

**RAG:** `python rag_system.py` (chat), `python rag_system.py --update` (rebuild vectors) — LLM vía OpenRouter (`openai/gpt-oss-20b`, `OPENROUTER_API_KEY`)

**LaTeX repair:** `python fix_latex.py <file.tex>` (extracts math commands from `\text{}`)

**Saldo OpenRouter:** `python execution/monitor_saldo_openrouter.py` (chequeo puntual), `--watch [--interval N]` (bucle en background, log en `.tmp/saldo_openrouter.log`; alerta audible cerca del auto top-up de $10)

**Enrutador LLM:** `python3 execution/enrutador.py --task <tipo> [--tokens N | --archivos f1 f2] [--critico] [--vision] [--modelo-explicito <id>]` → JSON `{tier, model, fallback}`; decisión determinista (tipos de tarea válidos y reglas en `.agent/enrutamiento.md`)

### Orchestrator flows
```
flujo_evaluar_examen.py    --pdf <file.pdf> [--rubrica <yaml>]
flujo_analizar_imagen.py   "glob|file1,file2" [--prompt "..."]
flujo_elaborar_examen.py   --tema "Semana 4: Condensadores" --output examenes/
flujo_elaborar_ejercicios.py --tema "Semana 8: BJT" --path ejercicios/BJT
flujo_imagen_a_kicad.py    circuito.png
flujo_diagnostico.py
flujo_curar_dataset.py     [--min-quality 0.7] [--split 80-10-10] [--dry-run] [--no-alert]
flujo_empaquetar_dataset.py [--format parquet|jsonl] [--license <lic>] [--pack] [--no-alert]
flujo_publicar_hf.py        <dataset> [--repo <id>] [--private] [--dry-run] [--no-alert]
flujo_ruview_rescue.py      (UDP listener :5005 — datos CSI/acelerómetro; config en directives/ruview_rescue.yaml)
flujo_telegram.py           (Telegram gateway polling — config en directives/telegram_gateway.yaml)
flujo_consultar_docs.py     <tech> [--topic ...] [--url ...] [--max-chars N]
```

### MCP servers (`mcp_*_server.py`, FastMCP)
```
mcp_analizar_server.py     Circuit Vision Server   → flujo_analizar_imagen (directives/analizar_imagen_mcp.yaml)
mcp_diagnostico_server.py  System Diagnostic      → flujo_diagnostico     (directives/diagnostico_mcp.yaml)
mcp_elaborar_server.py     Examen Elaborator      → flujo_elaborar_examen (directives/elaborar_examen_mcp.yaml)
mcp_evaluar_server.py      Examen Evaluator       → flujo_evaluar_examen  (directives/evaluar_examen_mcp.yaml)
mcp_latex_server.py        LaTeX Compiler         → compile_latex.py      (directives/latex_mcp_server.yaml)
mcp_sistema_server.py      System Control         → system_control.py     (directives/sistema_mcp.yaml)
mcp_docs_server.py         Docs Reference Server  → flujo_consultar_docs  (directives/consultar_docs_mcp.yaml)
```

### System services
```
sudo ./manage_bot.sh       — Telegram gateway (telegram_gateway.service)
sudo ./manage_waydroid.sh  — Waydroid Android container
```

## Output conventions

- Intermediate JSON lives in `.tmp/` (e.g., `.tmp/analisis_*.json`)
- `.tmp/run_state.json` tracks multi-step flow progress (step, exit code, timestamp)
- Datasets de entrenamiento LLM: raw capture en `datasets/*.jsonl` (`execution/data_capture.py`, pasivo, gitignored); curado/particionado en `datasets/curated/` (`execution/curar_datasets.py` o `flujo_curar_dataset.py`); paquetes HF (Parquet+LICENSE+README) en `datasets/paquetes/` (`execution/empaquetar_dataset.py` o `flujo_empaquetar_dataset.py`); publicación HF Hub (`execution/publicar_hf.py` o `flujo_publicar_hf.py`, requiere `HF_TOKEN` en `.env`)
- LaTeX deliverables go to `docs/` or `cursos/` under their topic directories
- LaTeX build artifacts go to `.tmp/latex_build/` (auto-cleaned by `compile_latex.py`)

## Git quirks

- `chroma_db/` excluded (exceeds GitHub 100 MB) — `git rm -r --cached chroma_db/` if accidentally tracked
- `examen*` pinned in `.gitignore` — exam PDFs/`.tex` starting with `examen` are never committed
- `db_state.json` is tracked (not auto-generated in the CI sense, but it's the RAG state file — be careful modifying)

## LaTeX conventions

- `\usepackage[spanish,es-noshorthands]{babel}`, `circuitikz`, `siunitx`, `amsmath`
- **ALL generated LaTeX uses the infographic style** from `execution/estilo_infografia.py`:
  - Generators import `PREAMBULO_INFOGRAFIA` (never duplicate preambles) and concatenate it with their document-specific `fancyhead`/colors before `\begin{document}`
  - Already integrated: `generar_informe.py`, `generar_informe_imagen.py`, `generar_examen_latex.py`, `generar_ejercicios_latex.py`, `flujo_diagnostico.py`
  - If you create a **new** LaTeX generator, import `PREAMBULO_INFOGRAFIA` and use `\bandaTitulo{...}{...}` for the opening banner, `tarjetaDato`/`tarjetaIcono`/`caja*` tcolorbox styles, `\section` colored rules, and FontAwesome icons (`\faIcon{...}`)
  - Same infographic look: sourcesanspro, `bandaAzul` banner, section rules via `titlesec`
  - `execution/estilo_infografia.py` must be imported additively and read `.agent/latex.md` before editing
- EDA JSON to EasyEDA: `LIB~...` strings in `shape[]`, sub-elements split by `#@$`, pins by `^^`
