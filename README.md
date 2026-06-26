# ELECTRONICA

Espacio de trabajo multidisciplinario de Electrónica, IoT, Diseño de Circuitos Integrados (EDA) y Redacción Académica, potenciado por un **Asistente IA con arquitectura de 3 capas** (Directives → Orchestration → Execution).

---

## Arquitectura del Sistema

El proyecto sigue un marco de **3 capas** que separa la lógica probabilística del LLM de la ejecución determinista:

| Capa | Directorio | Propósito |
|---|---|---|
| **Layer 1: Directives** | `directives/` | SOPs en YAML que definen flujos de trabajo repetibles |
| **Layer 2: Orchestration** | _Agente IA (OpenCode)_ | Toma decisiones, enruta tareas, valida entradas/salidas |
| **Layer 3: Execution** | `execution/` | Scripts Python deterministas con una sola responsabilidad |

---

## Componentes Principales

### Asistente RAG (`rag_system.py`)
Chatbot académico que procesa `.md`, `.tex` y `.pdf` mediante ChromaDB + Llama 3 (Groq):
- Embeddings multilingües (`paraphrase-multilingual-MiniLM-L12-v2`)
- Actualizaciones incrementales vía `db_state.json`
- Memoria conversacional

### Agente EDA (`agent_eda.py`)
Extrae netlists/BOM de esquemas LaTeX circuitikz y genera JSON para EasyEDA Standard.

### Scripts de Ejecución (`execution/`)
- `env_diagnostic.py` — Diagnóstico del entorno (SO, paquetes, HW, red)
- `scrape_single_site.py` — Extrae contenido principal de una URL
- `alert_user.py` — Emite alertas audibles al completar flujos

### Utilidades
- `clean_latex.py` — Elimina archivos auxiliares de compilación LaTeX
- `md_to_pdf.py` — Convierte Markdown a PDF
- `merge_pdfs.py` — Une múltiples PDFs
- `ren_archivos.py` — Renombra archivos por lotes
- `test_generator.py` — Tests del generador JSON EasyEDA

### Control de Versiones
- `git-update.sh` — Commit WIP + pull + push automatizado
- `update_repo.sh` — Gestor de versiones con opciones (confirm, dry-run, mensaje personalizado)

---

## ⚙️ Instalación y Configuración

1. Activa tu entorno virtual Python (ej. `elect_env` o Conda):
   ```bash
   conda activate elect_env
   ```
2. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Obtén una API Key gratuita de [Groq](https://console.groq.com).
4. Crea `.groq_api_key` en la raíz con tu clave (sin espacios ni comillas).

## 🚀 Uso

**Asistente RAG:**
```bash
python rag_system.py
python rag_system.py --update   # forzar reconstrucción de la base vectorial
```

**Agente EDA:**
```bash
python agent_eda.py
```

**Diagnóstico del entorno:**
```bash
python execution/env_diagnostic.py
```

---

## 📂 Estructura del Proyecto

| Directorio | Descripción |
|---|---|
| `docs/` | Documentación técnica y académica (19 subdirectorios: CIRC_DISP_ELECT/, SMPS/, EDA/, EASYEDA/, RAG/, vLLM/, OPENCODE/, PROTECTOR_120VAC/, ZBAR_PRACTICAS/, etc.) |
| `cursos/` | Material de cursos y tesis (DISP_ELECTRONICOS/, INT_ELECTRONICA/, TESIS/, PLAN_ESTUDIOS/, LABORATORIO_I_FISICA/, LABORATORIO_II_FISICA/) |
| `.agent/` | Instrucciones del sistema para el agente IA (10 archivos .md) |
| `directives/` | SOPs en YAML para flujos de trabajo repetibles (11 archivos) |
| `execution/` | Scripts Python deterministas (3 archivos) |
| `Agente_EDA/` | Recursos para el agente EDA (schemas, pruebas) |
| `chroma_db/` | *(Autogenerado)* Base de datos vectorial local |
| `.tmp/` | Archivos temporales y estado de ejecución (`run_state.json`) |
| `db_state.json` | *(Autogenerado)* Registro de archivos procesados para actualizaciones incrementales |

---

## Convenciones de Código

- **Python:** PEP 8, type hints, docstrings, modularidad, raw strings para contenido LaTeX
- **LaTeX:** UTF-8, `\usepackage[spanish,es-noshorthands]{babel}`, `circuitikz` para diagramas, `siunitx` para unidades
- **EDA:** Formato EasyEDA Standard (`LIB~...` en `shape[]`, sub-elementos `#@$`, pines con `^^`)
- **RAG:** Actualizaciones incrementales, embeddings multilingüe, memoria conversacional
- **3-Layer:** Directives en YAML → Orchestration → Execution scripts
- **Git:** `chroma_db/`, entornos virtuales, `__pycache__/` y auxiliares LaTeX excluidos vía `.gitignore`

---

## 🛠️ Notas sobre Git

La base de datos vectorial `chroma_db/` excede el límite de 100 MB de GitHub, por lo que está excluida permanentemente vía `.gitignore`. Para removerla del índice si se añadió por accidente:

```bash
git rm -r --cached chroma_db/
```

---
*Desarrollado con LangChain, ChromaDB, Llama (Groq) y modelos Open-Source.*