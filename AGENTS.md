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
| `.env` | `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_MAX_TOKENS`, `GITHUB_TOKEN`, `TELEGRAM_BOT_TOKEN`, `HF_TOKEN` (+ otras claves de proveedor: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`) |

`opencode.json` loads `instructions: [".agent/*.md"]` — those are your core operating instructions. **This file (`AGENTS.md`) is the authoritative instruction set**; `AGENTS_ES.md` is a Spanish translation that may lag — don't trust it where they differ.

## Know before you act

- **Session logs (continuity):** the `Sessions/` folder (repo root) records one `.md` per session, named by topic (`Sessions/<fecha>_<tema>.md`).
  - **At the start of each new session**, before investigating anything, check `Sessions/` for the most recent log matching the topic the user brings up (glob `Sessions/*<tema>*.md`, fallback to the newest file). Read it to recover what was decided/pending — avoid re-investigating from scratch and burning tokens.
  - **Then create** this session's own log in `Sessions/<fecha>_<tema>.md` via `python3 execution/bitacoras.py nueva --tema "<tema>"` (canonical template: Tema/Contexto/Decisiones (usuario)/Actividades/Pendientes; never overwrites), recording date, topic, activities, decisions and pending items, and commit it with the rest of the session's work.
  - **At session close**, run `python3 execution/bitacoras.py check` and fix any missing day-log or empty sections before finishing — the *semantic* context (why decisions were made, what was discarded, user intent) lives ONLY in these bitácoras; without them the next session re-investigates from scratch.
- **State hygiene (freshness):** `run_state*.json` are *derived views* of the append-only `session_log_*.jsonl`; a view can outlive its run (orphan) and poison MCP responses. **At the start of each session** (or before resuming any multi-step flow), run `python3 execution/estado_sesion.py check`; purge confirmed orphans with `... clean` (never touches the immutable logs).
- **Before modifying any `.tex` file**, read `.agent/latex.md` (16 documented LaTeX pitfalls specific to this project)
- **Before modifying scripts that use LangChain or parse LLM JSON**, read `.agent/python.md` (PromptTemplate jinja2 mode, raw strings, trailing commas, balanced-brace JSON extraction)
- **`requirements.txt` contains only `psutil` and `PyYAML`** — real dependencies live in the conda environment; don't trust it as canonical
- **Conda env automático en shells de opencode:** `.opencode/plugins/conda-env.js` (hook `shell.env`) antepone `elect_env` al PATH y fija `CONDA_PREFIX`/`CONDA_DEFAULT_ENV`/`VIRTUAL_ENV` en toda shell de este workspace — no re-activar ni usar `conda run`; si `CONDA_DEFAULT_ENV` desaparece, revisar ese plugin (requiere reinicio de opencode tras editarlo)
- **Node vía nvm en shells de opencode:** `.opencode/plugins/nvm-env.js` (hook `shell.env`) antepone `~/.nvm/versions/node/v22.23.1/bin` al PATH en toda shell de este workspace (las shells de opencode no cargan nvm y sin él resuelven `node` al v18 EOL del sistema, que queda intacto como reserva); fallback automático a la mayor versión instalada si la fijada desaparece; el único proyecto Node es `Proyectos/cloudflare-agent` (wrangler 3.x, engines >=16.13). Requiere reinicio de opencode tras editarlo
- **No linter, type checker, formatter, or CI** is configured — don't waste time running them
- **Run everything from repo root** — imports use relative paths; `mcp_latex_server.py`, `mcp_sistema_server.py` and `execution/compile_latex.py` have `sys.path.append()` but root-level scripts don't need it. The newer MCP servers (`mcp_analizar_server.py`, `mcp_diagnostico_server.py`, `mcp_elaborar_server.py`, `mcp_evaluar_server.py`) resolve their own `project_root` via `os.path.dirname(os.path.abspath(__file__))` and load `.env` from there — they are path-agnostic and can run from anywhere
- **LLM backends desde VE (geo-bloqueo):** Groq y OpenAI directos devuelven 403 (`unsupported_country_region_territory`) — solo funcionan con VPN a nivel máquina. Los backends accesibles sin VPN son **OpenRouter** (texto, `OPENROUTER_API_KEY`) y **Gemini**. `rag_system.py` y `agent_eda.py` ya usan OpenRouter (`openai/gpt-oss-20b`). Reglas: fijar siempre `max_tokens`/`max_output_tokens` (sin él OpenRouter pide 65536 y con saldo bajo devuelve 402; `OPENROUTER_MAX_TOKENS` en `.env`, default 2048, activo 8192); `qwen/qwen3.6-27b` devuelve su razonamiento como `content` (rompe extracción JSON) → usar `openai/gpt-oss-20b` para salida estructurada
- **Enrutamiento multi-LLM (determinista):** NO elijas el modelo razonando en el chat — construye el descriptor (`--task` del vocabulario controlado, tokens medidos, criticidad, visión) y ejecuta el Enrutador (ver Commands); luego invoca el script con `--api-backend openrouter --modelo <id>`. Fuente única de IDs: `MODEL_TIERS` en `execution/llm_client.py` (flash=`google/gemini-3.7-flash`, deepseek=`deepseek/deepseek-v4.1-flash`, glm=`z-ai/glm-5.2`, opus=`anthropic/claude-opus-5`; Kimi K3 solo por `--modelo-explicito`). Fallback cost-aware ante 429/errores de servicio, máx 3 intentos. Telemetría: `.tmp/routing_log.jsonl`. Política completa: `.agent/enrutamiento.md`, `directives/enrutamiento_llm.yaml`, `docs/ARQUITECTURA_ENRUTAMIENTO_LLM/arquitectura_enrutamiento_llm.md`
- **Motor del asistente opencode (rotativo):** es SOLO la interfaz del orquestador, NO forma parte del routing y NUNCA consume `OPENROUTER_API_KEY`. Las cuotas Free se agotan rápido y el motor puede rotar sin previo aviso, indistintamente entre Free del gateway OpenCode Zen (`opencode/...`) o Free de OpenRouter — verificar el modelo vigente en `/models` en vez de asumirlo. **Facturación en `/models`:** los modelos vía Zen facturan a la cuenta Zen aparte (los Free = $0); los modelos vía proveedor OpenRouter descuentan el saldo de `OPENROUTER_API_KEY`. Los créditos solo se consumen cuando un script de `execution/` llama a `openrouter_chat` (NOTA: `enrutador.py` NO consume — decide 100% local); matriz completa de qué consume y qué no: `.agent/enrutamiento.md` → "Qué consume créditos OpenRouter y qué no". Cambiar el motor no requiere tocar el router

## Integración con Frameworks de Modelos Plugin-based (Cordis, DeepSeek Harness)

Visión general de cómo la arquitectura "todo es plugin" de frameworks como DeepSeek Harness (dsh) y su núcleo Cordis influye en nuestra selección y configuración de modelos dentro de ELECTRONICA:

### 1. Filosofía del Framework Cordis
- **Principio**: "Every part of the product is a plugin" — incluido el adaptador de modelo, el registro de herramientas, el registro de sesiones y el propio bucle del agente.
- **Nucleo sin privilegio**: No hay un núcleo centralizado al que "enganchar"; cualquier componente puede ser reemplazado o recompuesto mediante plugins.
- **Carga layerada**: Bundles → Perfil → Parche en home → Parches de línea de comandos, permitiendo composiciones complejas sin modificar el código base.

### 2. Aplicación a la Selección de Modelos en ELECTRONICA
Aunque nuestro proyecto utiliza un enrutador determinista en `execution/enrutador.py` (no un framework Cordis completo), los principios inspiran nuestras mejores prácticas:

| Concepto Cordis | Aplicación en ELECTRONICA |
|---|---|
| **Modelos como plugins intercambiables** | El enrutador decide el modelo basado en descriptores estructurados (`--task`, `--tokens`, `--critico`), no en criterios probabilísticos en el chat. |
| **Capas de configuración** | Análogo a: default por agente → providers múltiples → selección por sesión. Nuestro `execution/enrutador.py` cubre las capas 1 y 2; la capa 3 es posible mediante ajustes temporales en sesión. |
| **Desacoplamiento de lógica** | Al igual que Cordis separa el agent-loop como un plugin más, nuestro enrutador separa la decisión de modelo de la ejecución del flujo. |
| **Ecosistema de proveedores** | Igual que dsh soporta `llm-deepseek` y `llm-pi-ai` providers, nuestro sistema soporta tiers `flash`, `deepseek`, `glm`, `opus` con fallback cost-aware determinista. |

### 3. Criterios de Selección Extendidos (Integración Profunda)

La tabla seguente combina la política existente con inspiración de DeepSeek Harness:

| Criterio | Política ELECTRONICA | Inspiración Cordis/Harness |
|---|---|---|
| **Volumen de tokens >50K** | `deepseek` (contexto masivo) | Deepseek tier por su contexto nativo de 1M tokens |
| **Tarea crítica (exámenes, producción)** | `opus` | Análogo premium; cambio de modelo sin fork del proyecto |
| **Rutina (parsing, formateo)** | `flash` | Mantener; bajo costo, rápido |
| **JSON estructurado** | Algoritmo `_find_balanced_json` | Igual; el framework Cordis facilitaría plugins de parseo JSON por modelo |
| **Geolocalización (restricciones VE)** | OpenRouter / Gemini | Al igual que dsh evitaGroq/OpenAI sin VPN, nuestro sistema respeta esta restricción |

### 4. Flujo de Trabajo Mejorado
Inspirado en la progresión de dsh, nuestro flujo recomendado es:

1. **Definir descriptor** (`--task`, `--tokens N`, `--critico` true/false)
2. **Ejecutar enrutador** (`python3 execution/enrutador.py <descriptor>`) → JSON `{tier, model, fallback}`
3. **Invocar script** con `--api-backend openrouter --modelo <id>`
4. **Registrar telemetría** en `.tmp/routing_log.jsonl` para afinar umbrales

### 5. Próximas Mejoras para ELECTRONICA
Considerar para futuras iteraciones:
- **Extender `directives/enrutamiento_llm.yaml`** con sección de proveedores adicionales (análogo a `llm-pi-ai.providers` de dsh)
- **Documentar patrón de adaptadores de modelo** en `.agent/python.md` para añadir nuevos proveedores siguiendo el patrón de `execution/llm_client.py`
- **Evaluar arquitectura multi-provider** para simplificar flujos que actualmente requieren cambio manual de modelo
- **Añadir soporte para `--modelo-explicito`** en enrutador para casos de prueba comparativa de tiers

*Nota: Esta sección se inspira en la documentación oficial de DeepSeek Harness (dshdocs.com, deepseekdocs.com) y la filosofía Cordis. No implica adoption completa de dsh, sino selección de principios aplicables a nuestra arquitectura determinista existente.*

## Comparativa: ELECTRONICA vs DeepSeek Harness

A continuación se presenta una tabla comparativa entre nuestro proyecto ELECTRONICA y el framework DeepSeek Harness (dsh), basada en su arquitectura, capacidades y filosofía de diseño:

| Aspecto | ELECTRONICA | DeepSeek Harness (dsh) |
|---|---|---|
| **Propósito Principal** | Espacio de trabajo multidisciplinario: programación, EDA, LaTeX, IoT, blockchain, RAG, sistemas | Framework de agentes de IA de código abierto |
| **Arquitectura Core** | 3 capas deterministas: Directivas → Orquestación → Ejecución scripts Python | Cordis plugin framework con filosofía "todo es plugin" |
| **Selección de Modelo** | Determinística vía `execution/enrutador.py` con descriptores estructurados (`--task`, `--tokens`, `--critico`) | Híbrida: `agent-default-model` por agente + selección en sesión UI; multi-provider via `llm-pi-ai` |
| **Filosofía de Plugins** | Scripts deterministas en `execution/` con responsabilidades únicas; plugins implícitos en directivas YAML | Explicito: "Everything is a plugin" - adaptadores de modelo, bucle de agente, registro de sesiones, herramientas, UI son todos plugins reemplazables |
| **Núcleo Privilegiado** | No aplica (arquitectura layered fija) | Ningún núcleo centralizado; cualquier componente puede ser reemplazado mediante plugins |
| **Carga de Configuración** | Directivas YAML únicas por flujo; `opencode.json` carga `.agent/*.md` | Layered: Bundles → Perfil → Parche home → Parches CLI; plugins npm instalables |
| **Interfaz de Usuario** | Línea de comandos (CLI) centrada; some flujos con servidores MCP FastMCP | UI web local (`http://127.0.0.1:3080`) + modo headless CLI; transición fluida entre ambos |
| **Gestión de Sesiones** | `.tmp/run_state.json` por flujo; logs en `Sessions/` markdown | **Trayectoria (Trajectory)**: append-only event log en `~/.dsh/sessions` con prompts, razonamiento, llamadas a herramientas y resultados; resume/fork/resume soportado nativamente |
| **Modelos Soportados** | Tiers definidos: flash (gemini-3.7-flash), deepseek (deepseek-v4.1-flash), glm (z-ai/glm-5.2), opus (claude-opus-5) | Cualquier modelo OpenAI-compatible via adaptadores; proveedores oficiales (`deepseek-official`), compatibles (`llm-pi-ai`), custom gateways |
| **Ruteo de Decisiones** | 100% determinista en código; mismo descriptor → mismo tier/siempre | Configurable: default por agente overridable en sesión; multi-model en un mismo session posible |
| **Consumo de Créditos** | Matriz documentada: orquestación gratis; scripts `execution/` consumen vía `openrouter_chat` | No especificado en documentación básica; dependería de proveedores configurados |
| **Estado Actual** | Producción estable; workflows definidos y documentados | Developer Preview (`0.1.0-rc.x`, aug 2026); cambios breaking possible |
| **Ecosistema** | Directivas propias + scripts Python especializados | +367 plugins npm (agosto 2026); 1,179+ en directorio; MCP bridges, visión, OCR, memory trackers, Git helpers |
| **Geolocalización** | Restricciones VE: OpenRouter/Gemini; Groq/OpenAI requieren VPN | No especificado explícitamente en docs consultadas |
| **JSON Estructurado** | Algoritmo `_find_balanced_json` para parseo robusto | No especificado; arquitectura plugin facilitaría implementación |
| **Long-term Vision** | Mejorar arquitectura determinista existente; añadir capacidades plugin inspiradas en estándares del sector | Madurar framework Cordis; estabilizar API; crecer ecosistema plugins |

### Puntos en Común

1. **Arquitectura basada en plugins/extensibilidad**: Ambos diseños priorizan la capacidad de extender y reemplazar componentes sin reescribir el núcleo.
2. **Separación de preocupaciones**: Lógica de negocio vs. ejecución técnica.
3. **Enfoque en determinismo**: ELECTRONICA lo hace explícito en el enrutador; DeepSeek Harness lo permite mediante arquitectura plugin pero en preview.
4. **Integración con LLM**: Ambos trabajan con modelos de lenguaje (ya sea vía OpenRouter, APIs directas o adaptadores).
5. **Documentación orientada al flujo de trabajo**: Importancia de SOP y documentación del flujo.

### Diferencias Clave

1. **Madurez**: ELECTRONICA es un proyecto consolidado con workflows definidos; DeepSeek Harness es preview (lanzado aug 2026).
2. **Enfoque de modelo**: ELECTRONICA tiene tiers deterministas codificados; DeepSeek Harness soporta cualquier modelo OpenAI-compatible mediante plugins.
3. **Interfaz**: ELECTRONICA es CLI-first; DeepSeek Harness tiene UI web como interfaz principal con CLI headless opción.
4. **Gestión de sesiones**: DeepSeek Harness tiene sistema de trayectoria advance; ELECTRONICA usa state JSON por flujo.
5. **Ecosistema de terceros**: DeepSeek Harness tiene ecosistema de plugins npm activo; ELECTRONICA tiene directivas YAML y scripts Python propios.

**Nota**: Esta comparativa extrae principios de la filosofía "todo es plugin" de DeepSeek Harness y Cordis, aplicándolos a nuestro contexto determinista. No implica adopción de dsh, sino identificación de patrones aplicables a mejoras futuras en ELECTRONICA.

## Commands

**Tests:** `python test_generator.py` (EDA JSON, zero external deps)

**RAG:** `python rag_system.py` (chat), `python rag_system.py --update` (rebuild vectors) — LLM vía OpenRouter (`openai/gpt-oss-20b`, `OPENROUTER_API_KEY`)

**LaTeX repair:** `python fix_latex.py <file.tex>` (extracts math commands from `\text{}`)

**Saldo OpenRouter:** `python execution/monitor_saldo_openrouter.py` (chequeo puntual), `--watch [--interval N]` (bucle en background, log en `.tmp/saldo_openrouter.log`; alerta audible cerca del auto top-up de $5, que OpenRouter dispara cuando el saldo baja de $3)

**Enrutador LLM:** `python3 execution/enrutador.py --task <tipo> [--tokens N | --archivos f1 f2] [--critico] [--vision] [--modelo-explicito <id>]` → JSON `{tier, model, fallback}`; decisión determinista (tipos de tarea válidos y reglas en `.agent/enrutamiento.md`)

### Orchestrator flows
```
flujo_evaluar_examen.py    --pdf <file.pdf> [--rubrica <yaml>]
flujo_analizar_imagen.py   "glob|file1,file2" [--prompt "..."]
flujo_elaborar_examen.py   --tema "Semana 4: Condensadores" --output examenes/
flujo_elaborar_ejercicios.py --tema "Semana 8: BJT" --path ejercicios/BJT
flujo_libro_a_skill.py      --pdf <libro.pdf> [--tema ...] [--nombre <name>] [--dry-run]
flujo_repo_a_skill.py       --repo <url-github|ruta-local> [--tema ...] [--nombre <name>] [--dry-run] [--incluir glob...] [--excluir glob...]
flujo_imagen_a_kicad.py    circuito.png
flujo_diagnostico.py
flujo_curar_dataset.py     [--min-quality 0.7] [--split 80-10-10] [--dry-run] [--no-alert]
flujo_empaquetar_dataset.py [--format parquet|jsonl] [--license <lic>] [--pack] [--no-alert]
flujo_publicar_hf.py        <dataset> [--repo <id>] [--private] [--dry-run] [--no-alert]
flujo_ruview_rescue.py      (UDP listener :5005 — datos CSI/acelerómetro; config en directives/ruview_rescue.yaml)
flujo_telegram.py           (Telegram gateway polling — config en directives/telegram_gateway.yaml)
flujo_consultar_docs.py     <tech> [--topic ...] [--url ...] [--max-chars N]
flujo_sync_faq_flujo.py     [--watch] [--force] [--no-llm] [--critico] (auto-sincroniza faq_higiene_estado_sesion.md → flujo.{tex,pdf} por hash; SOP en directives/sync_faq_a_flujo.yaml)
flujo_motor_fallback.py      [check|switch|estado|watch|pasivo] [--modelo <vigente>] [--confirmaciones N] [--auto-restart/--no-relaunch] [--pasivo]   (failover del motor: sonda determinista de la cuota free en execution/verificar_cuota_motor.py, conmutación atómica vía execution/aplicar_switch_modelo.py switch, auto-restore al recuperar; SOP en directives/motor_fallback.yaml)
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
- **Diagramas de flujo (convención):** todo flujo grande del repo (flujo_*, mcp_* con sus 3 capas: directiva + orquestador + script) entregado al usuario debe incluir un diagrama de flujo ISO 5807 estilo infográfico en `docs/<tema>/<proceso>_flujo.{tex,pdf}`, generado de forma determinista con `execution/generar_diagrama_flujo.py` a partir de un descriptor JSON (`--descriptor .tmp/descriptor_<proceso>.json --output docs/<tema>/<proceso>_flujo`). El descriptor modela nodos (terminador/proceso/decisión/almacenamiento/entrada-salida/documento/nota) y conexiones con col/fila (tronco en col 0, ramas a la derecha). **Convención de render (patrón `docs/AGENTE_IA/faq_higiene_estado_sesion_flujo.tex`):** cada símbolo muestra SOLO su etiqueta (T/P/D/E/A/N + número, = id del nodo) y las conexiones llevan rótulos cortos Siempre Sí/No; el significado completo vive en la tabla *Leyenda de etiquetas* (Etiqueta | Significado) bajo cada diagrama. SOP: `directives/diagrama_flujo.yaml`. Proceso enorme → dividir en secciones del descriptor (una por página).

## Git quirks

- `chroma_db/` excluded (exceeds GitHub 100 MB) — `git rm -r --cached chroma_db/` if accidentally tracked
- `examen*` pinned in `.gitignore` — exam PDFs/`.tex` starting with `examen` are never committed; likewise raw datasets (`datasets/`) and router telemetry (`.tmp/routing_log.jsonl`)
- `db_state.json` is tracked (not auto-generated in the CI sense, but it's the RAG state file — be careful modifying)
- Repo update flow: `./update_repo.sh [-m "msg"] [--push] [--dry-run]` (commit+pull+push, per `directives/git_update.yaml`) or `./git-update.sh` (shortcut: WIP commit + pull + push)

## Migración de entorno (a otra PC)

Clonar el repo NO basta para migrar el entorno de trabajo. Hay piezas críticas que viven
**fuera del repo** (en `~/.config/opencode/`, `~/.claude/`, home del usuario) y se deben
replicar manualmente en la PC destino:

| Pieza | Ubicación | ¿En el repo? | Qué es |
| :--- | :--- | :--- | :--- |
| **Skills globales** | `~/.config/opencode/skills/<name>/` | No | p. ej. `computacion_cientifica`; reutilizables en cualquier proyecto |
| **Skills externos** | `~/.claude/skills/`, `~/.agents/skills/` | No | auto-cargados (cloudflare, agents-sdk, etc.) |
| **Config global opencode** | `~/.config/opencode/opencode.json(c)`, plugins/agentes globales | No | `default_agent`, permisos, MCP globales |
| **`.env` (claves API)** | `.env` (raíz del repo) | No (gitignored a propósito) | `OPENROUTER_API_KEY`, `GOOGLE_API_KEY`, etc. |
| `.groq_api_key` | raíz del repo | No (gitignored) | clave Groq |
| **Project skills/plugins/agentes** | `.opencode/skills/`, `.opencode/plugin(s)/`, `.opencode/agent(s)/` | **Sí** | viajan con el repo |
| Directivas, flujos, scripts | `directives/`, `flujo_*`, `execution/` | **Sí** | viajan con el repo |

**Checklist de migración (además de `git clone`):**
1. Copiar `~/.config/opencode/` completa (skills globales + config + plugins globales).
2. Copiar `~/.claude/skills/` (y `~/.agents/skills/` si existe) — skills externos auto-cargados.
3. Recrear `.env` y `.groq_api_key` en el repo destino (nunca viajan por git).
4. Entorno conda `elect_env` + `node` vía nvm (ver plugins `.opencode/plugin/conda-env.js` y `nvm-env.js`).
5. Dependencias del proyecto (ver AGENTS.md "Know before you act": `requirements.txt` es mínimo).

> Pendiente: implementar un script de respaldo/exportación de estos elementos cuando se vaya a
> migrar de verdad (acordado 2026-08-27).

## LaTeX conventions

- `\usepackage[spanish,es-noshorthands]{babel}`, `circuitikz`, `siunitx`, `amsmath`
- **ALL generated LaTeX uses the infographic style** from `execution/estilo_infografia.py`:
  - Generators import `PREAMBULO_INFOGRAFIA` (never duplicate preambles) and concatenate it with their document-specific `fancyhead`/colors before `\begin{document}`
  - Already integrated: `generar_informe.py`, `generar_informe_imagen.py`, `generar_examen_latex.py`, `generar_ejercicios_latex.py`, `flujo_diagnostico.py`
  - If you create a **new** LaTeX generator, import `PREAMBULO_INFOGRAFIA` and use `\bandaTitulo{...}{...}` for the opening banner, `tarjetaDato`/`tarjetaIcono`/`caja*` tcolorbox styles, `\section` colored rules, and FontAwesome icons (`\faIcon{...}`)
  - Same infographic look: sourcesanspro, `bandaAzul` banner, section rules via `titlesec`
  - `execution/estilo_infografia.py` must be imported additively and read `.agent/latex.md` before editing
- EDA JSON to EasyEDA: `LIB~...` strings in `shape[]`, sub-elements split by `#@$`, pins by `^^`
