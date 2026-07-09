# AGENTS.md — ELECTRONICA

## 3-Layer Architecture (must follow for every new workflow)

| Layer | Where | What |
|---|---|---|
| **Directives** | `directives/*.yaml` | SOP — *what* to do |
| **Orchestration** | `flujo_*`, `mcp_*` (root) | Decision/validation logic; may serve MCP tools |
| **Execution** | `execution/*.py` | Deterministic script — *how* |

A new workflow must include all three layers; never write just an orchestrator without a directive and execution script.

## Configuration

| File | Content |
|---|---|
| `.groq_api_key` | Groq API key (text LLMs) |
| `.env` | `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`, `TELEGRAM_BOT_TOKEN` |

`opencode.json` loads `instructions: [".agent/*.md"]` — those are your core operating instructions.

## Know before you act

- **Before modifying any `.tex` file**, read `.agent/latex.md` (15 documented LaTeX pitfalls specific to this project)
- **Before modifying scripts that use LangChain or parse LLM JSON**, read `.agent/python.md` (PromptTemplate jinja2 mode, raw strings, trailing commas, balanced-brace JSON extraction)
- **`requirements.txt` contains only `psutil` and `PyYAML`** — real dependencies live in the conda environment; don't trust it as canonical
- **No linter, type checker, formatter, or CI** is configured — don't waste time running them
- **Run everything from repo root** — imports use relative paths; `mcp_*_server.py` and `execution/compile_latex.py` have `sys.path.append()` but root-level scripts don't need it

## Commands

**Tests:** `python test_generator.py` (EDA JSON, zero external deps)

**RAG:** `python rag_system.py` (chat), `python rag_system.py --update` (rebuild vectors)

**LaTeX repair:** `python fix_latex.py <file.tex>` (extracts math commands from `\text{}`)

### Orchestrator flows
```
flujo_evaluar_examen.py    --pdf <file.pdf> [--rubrica <yaml>]
flujo_analizar_imagen.py   "glob|file1,file2" [--prompt "..."]
flujo_elaborar_examen.py   --tema "Semana 4: Condensadores" --output examenes/
flujo_elaborar_ejercicios.py --tema "Semana 8: BJT" --path ejercicios/BJT
flujo_imagen_a_kicad.py    circuito.png
flujo_diagnostico.py
```

### System services
```
sudo ./manage_bot.sh       — Telegram gateway (telegram_gateway.service)
sudo ./manage_waydroid.sh  — Waydroid Android container
```

## Output conventions

- Intermediate JSON lives in `.tmp/` (e.g., `.tmp/analisis_*.json`)
- `.tmp/run_state.json` tracks multi-step flow progress (step, exit code, timestamp)
- LaTeX deliverables go to `docs/` or `cursos/` under their topic directories
- LaTeX build artifacts go to `.tmp/latex_build/` (auto-cleaned by `compile_latex.py`)

## Git quirks

- `chroma_db/` excluded (exceeds GitHub 100 MB) — `git rm -r --cached chroma_db/` if accidentally tracked
- `examen*` pinned in `.gitignore` — exam PDFs/`.tex` starting with `examen` are never committed
- `db_state.json` is tracked (not auto-generated in the CI sense, but it's the RAG state file — be careful modifying)

## LaTeX conventions

- `\usepackage[spanish,es-noshorthands]{babel}`, `circuitikz`, `siunitx`, `amsmath`
- EDA JSON to EasyEDA: `LIB~...` strings in `shape[]`, sub-elements split by `#@$`, pins by `^^`
