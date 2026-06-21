# AGENTS.md — ELECTRONICA

## Descripción General

Espacio de trabajo multidisciplinario de Electrónica, IoT, Diseño de Circuitos Integrados (EDA) y Redacción Académica. Integra un asistente RAG, un agente EDA para EasyEDA, y material didáctico en LaTeX.

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
|---|---|
| `rag_system.py` | Chatbot RAG: vectoriza `.tex`, `.md`, `.pdf` en ChromaDB y responde preguntas con Llama 3 (Groq). |
| `agent_eda.py` | Agente EDA: extrae netlist/BOM de LaTeX circuitikz y genera JSON para EasyEDA Standard. |
| `clean_latex.py` | Elimina archivos auxiliares de compilación LaTeX. |
| `md_to_pdf.py` | Convierte Markdown a PDF. |
| `merge_pdfs.py` | Une múltiples PDFs en uno solo. |
| `ren_archivos.py` | Renombra archivos eliminando cadenas específicas del nombre. |
| `test_generator.py` | Tests del generador JSON EasyEDA (sin dependencias externas). |

---

## Estructura de Directorios

- `docs/` — Documentación técnica y académica (CIRC_DISP_ELECT/, SMPS/, EDA/, PROTECTOR_120VAC/, ZBAR_PRACTICAS/, etc.)
- `cursos/` — Material de cursos y tesis (DISP_ELECTRONICOS/, INT_ELECTRONICA/, TESIS/, LABORATORIO_*)
- `.agent/` — Instrucciones del sistema para el agente IA (8 archivos .md)
- `chroma_db/` — Base de datos vectorial (autogenerada, excluida de git)
- `Agente_EDA/` — Recursos para el agente EDA (schemas, pruebas)

---

## Convenciones de Código

- **Python:** PEP 8, type hints, docstrings, modularidad, raw strings para contenido LaTeX
- **LaTeX:** UTF-8, `\usepackage[spanish,es-noshorthands]{babel}`, `circuitikz` para diagramas, `siunitx` para unidades
- **EDA:** Formato EasyEDA Standard (strings `LIB~...` en `shape[]`, sub-elementos `#@$`, pines con `^^`)
- **RAG:** Actualizaciones incrementales vía `db_state.json`, embeddings multilingüe, memoria conversacional
- **Git:** `chroma_db/`, entornos virtuales, `__pycache__/` y auxiliares LaTeX excluidos vía `.gitignore`

---

## Configuración

- API key de Groq en `.groq_api_key` (excluido de git)
- Instrucciones del agente en `opencode.json`: `{"instructions": [".agent/*.md"]}`
- Dependencias Python: langchain, langchain-groq, langchain-chroma, langchain-huggingface, pypdf, sentence-transformers
