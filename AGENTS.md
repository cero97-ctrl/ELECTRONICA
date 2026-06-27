# AGENTS.md — ELECTRONICA

## Descripción General

Espacio de trabajo multidisciplinario de Electrónica, IoT, Diseño de Circuitos Integrados (EDA) y Redacción Académica. Opera bajo una **arquitectura de 3 capas** (Directives → Orchestration → Execution) que separa la lógica probabilística del LLM de la ejecución determinista mediante scripts Python especializados. Integra un asistente RAG, un agente EDA para EasyEDA, y material didáctico en LaTeX.

---

## Stack Tecnológico

- **Lenguaje principal:** Python 3 (pydantic, type hints)
- **LaTeX:** circuitikz, siunitx, amsmath, babel spanish
- **Frameworks Python:** LangChain (groq, chroma, huggingface), ChromaDB, sentence-transformers
- **LLM:** Llama 3.3/3.1 vía API de Groq
- **Configuración agente:** OpenCode (.agent/*.md)

---

## Scripts Principales

| Script | Propósito |
|---|---|---|
| `execution/env_diagnostic.py` | Diagnóstico del entorno: SO, paquetes, HW, red. |
| `execution/scrape_single_site.py` | Extrae el contenido principal de una URL y lo guarda en texto. |
| `execution/analizar_imagen.py` | Analiza imágenes con LLM multimodal (Groq/Gemini/OpenRouter) y obtiene descripción JSON. |
| `execution/evaluar_examen.py` | Evalúa exámenes escritos/prácticas con LLM multimodal (Groq/Gemini/OpenRouter). |
| `execution/generar_informe.py` | Genera informe LaTeX a partir del JSON de evaluación. |
| `execution/generar_informe_imagen.py` | Genera informe LaTeX a partir del JSON de análisis de imágenes. |
| `execution/alert_user.py` | Emite alertas audibles (paplay + fallback bell) al completar flujos. |
| `flujo_evaluar_examen.py` | Orquestador Layer 2: flujo completo (evaluar → informe → alertar). |
| `flujo_analizar_imagen.py` | Orquestador Layer 2: flujo completo (analizar imágenes → informe → alertar). |
| `rag_system.py` | Chatbot RAG: vectoriza `.tex`, `.md`, `.pdf` en ChromaDB y responde preguntas con Llama 3 (Groq). |
| `agent_eda.py` | Agente EDA: extrae netlist/BOM de LaTeX circuitikz y genera JSON para EasyEDA Standard. |
| `clean_latex.py` | Elimina archivos auxiliares de compilación LaTeX. |
| `md_to_pdf.py` | Convierte Markdown a PDF. |
| `merge_pdfs.py` | Une múltiples PDFs en uno solo. |
| `ren_archivos.py` | Renombra archivos eliminando cadenas específicas del nombre. |
| `test_generator.py` | Tests del generador JSON EasyEDA (sin dependencias externas). |
| `git-update.sh` | Script de actualización Git: commit WIP + pull + push vía `update_repo.sh`. |
| `update_repo.sh` | Gestor de versiones: pull, add, commit y push con opciones (confirm, dry-run, mensaje personalizado). |

---

## Arquitectura de 3 Capas

El sistema sigue el marco definido en `.agent/AGENT_FRAMEWORK.md`:

| Capa | Directorio | Propósito |
|---|---|---|
| **Layer 1: Directives** | `directives/` | SOPs en YAML (14 archivos) que definen _qué_ hacer: scrape, research, memoria, EDA, FreeCAD, KiCad, git, mantenimiento, análisis de imágenes, evaluación de exámenes y prácticas de laboratorio. |
| **Layer 2: Orchestration** | _El agente IA_ | Toma decisiones, enruta tareas a scripts, valida entradas/salidas, gestiona errores. |
| **Layer 3: Execution** | `execution/` | Scripts Python deterministas (7 archivos) con una sola responsabilidad. |

---

## Estructura de Directorios

- `docs/` — Documentación técnica y académica (20 subdirectorios: CIRC_DISP_ELECT/, SMPS/, EDA/, PROTECTOR_120VAC/, ZBAR_PRACTICAS/, EASYEDA/, IMAGENES/, RAG/, vLLM/, OPENCODE/, MEDIDOR_ENERGIA/, PC_ASUS/, PC_PARA_IA/, SERVIDOR_POWEREDGE_R610/, SISTEMA_INTERNAC/, CIRC_PARA_RESP_RAPIDAS/, PROYECTO_MECATRONICA/, Ventilador_3_Velocidades/, MANUAL/, etc.)
- `cursos/` — Material de cursos y tesis (DISP_ELECTRONICOS/, INT_ELECTRONICA/, TESIS/, PLAN_ESTUDIOS/, LABORATORIO_I_FISICA/, LABORATORIO_II_FISICA/)
- `.agent/` — Instrucciones del sistema para el agente IA (10 archivos .md)
- `directives/` — SOPs en YAML para flujos de trabajo repetibles (14 archivos)
- `directives/rubricas/` — Rúbricas YAML para evaluación de prácticas de laboratorio
- `execution/` — Scripts Python deterministas para la capa de ejecución (7 archivos)
- `chroma_db/` — Base de datos vectorial (autogenerada, excluida de git)
- `Agente_EDA/` — Recursos para el agente EDA (schemas, pruebas)
- `.tmp/` — Archivos temporales y estado de ejecución (`run_state.json`)

---

## Convenciones de Código

- **Python:** PEP 8, type hints, docstrings, modularidad, raw strings para contenido LaTeX
- **LaTeX:** UTF-8, `\usepackage[spanish,es-noshorthands]{babel}`, `circuitikz` para diagramas, `siunitx` para unidades
- **EDA:** Formato EasyEDA Standard (strings `LIB~...` en `shape[]`, sub-elementos `#@$`, pines con `^^`)
- **RAG:** Actualizaciones incrementales vía `db_state.json`, embeddings multilingüe, memoria conversacional
- **3-Layer:** Directives en YAML → Orchestration (agente) → Execution (scripts deterministas). Cada vez que se solicite crear un orquestador, debe interpretarse que dicho orquestador debe ir acompañado de un archivo en la carpeta `directives/` y de al menos otro archivo en la carpeta `execution/` para mantener la concordancia con la arquitectura de 3 capas.
- **Git:** `chroma_db/`, entornos virtuales, `__pycache__/` y auxiliares LaTeX excluidos vía `.gitignore`

---

## Configuración

- API key de Groq en `.groq_api_key` (excluido de git)
- API key de Google (`GOOGLE_API_KEY`) y OpenRouter (`OPENROUTER_API_KEY`) en `.env`
- Instrucciones del agente en `opencode.json`: `{"instructions": [".agent/*.md"]}`
- Dependencias Python: langchain, langchain-groq, langchain-chroma, langchain-huggingface, pypdf, sentence-transformers, pymupdf, google-genai
