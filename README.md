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

### Análisis de Imágenes (`flujo_analizar_imagen.py`)
Orquestador que ejecuta el flujo completo de análisis visual:
1. `analizar_imagen.py` — Analiza imágenes con Gemini/OpenRouter (multimodal)
2. `generar_informe_imagen.py` — Genera informe LaTeX con resultados
3. `alert_user.py` — Notifica con alerta audible al completar

### Evaluación de Exámenes y Prácticas (`flujo_evaluar_examen.py`)
Orquestador que ejecuta el flujo completo de evaluación:
1. `evaluar_examen.py` — Evalúa PDF con Gemini/OpenRouter (multimodal)
2. `generar_informe.py` — Genera informe LaTeX con resultados
3. `alert_user.py` — Notifica con alerta audible al completar

Soporta exámenes escritos y prácticas de laboratorio mediante rúbricas
YAML personalizadas en `directives/rubricas/`.

### Gateway de Telegram (Orquestador Remoto)
Orquestador seguro basado en Long Polling (`flujo_telegram.py`) que actúa como puerta de enlace (Gateway) para interactuar con todos los servidores MCP locales de forma remota, sin requerir puertos abiertos ni túneles externos. Integrado mediante un servicio systemd (`telegram_gateway.service`).

### Scripts de Ejecución (`execution/`)
- `env_diagnostic.py` — Diagnóstico del entorno (SO, paquetes, HW, red)
- `scrape_single_site.py` — Extrae contenido principal de una URL
- `analizar_imagen.py` — Analiza imágenes con LLM multimodal (Gemini/OpenRouter)
- `evaluar_examen.py` — Evaluación con LLM multimodal (Gemini/OpenRouter)
- `generar_informe.py` — Genera informe LaTeX desde JSON de evaluación
- `generar_informe_imagen.py` — Genera informe LaTeX desde JSON de análisis de imágenes
- `alert_user.py` — Emite alertas audibles (paplay + fallback bell)

### Utilidades
- `clean_latex.py` — Elimina archivos auxiliares de compilación LaTeX
- `md_to_pdf.py` — Convierte Markdown a PDF
- `merge_pdfs.py` — Une múltiples PDFs
- `ren_archivos.py` — Renombra archivos por lotes
- `test_generator.py` — Tests del generador JSON EasyEDA
- `manage_bot.sh` — Script interactivo para gestionar (Start/Stop/Status) el orquestador de Telegram.

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
3. Obtén una API Key gratuita de [Groq](https://console.groq.com) (usada para texto).
4. Crea `.groq_api_key` en la raíz con tu clave (sin espacios ni comillas).
5. Para evaluación de exámenes (visión): obtén una API Key de [Google AI Studio](https://aistudio.google.com/apikey)
   y configúrala como `GOOGLE_API_KEY` en `.env`.

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

**Analizar imágenes con IA multimodal:**
```bash
python flujo_analizar_imagen.py "docs/IMAGENES/*.jpg" --prompt "Describe este circuito"
python flujo_analizar_imagen.py foto1.jpg,foto2.jpg --modelo gemini-1.5-pro
```

**Evaluar un examen escrito de Electrónica:**
```bash
python flujo_evaluar_examen.py --pdf "cursos/INT_ELECTRONICA/examenes/02/examen_estudiante/alumno.pdf"
```

**Evaluar una práctica de laboratorio:**
```bash
python flujo_evaluar_examen.py \
  --pdf "practicas/01/informe_estudiante/practica_01.pdf" \
  --rubrica "directives/rubricas/rubrica_practica_lab.yaml"
```

**Diagnóstico del entorno:**
```bash
python execution/env_diagnostic.py
```

---

## 📂 Estructura del Proyecto

| Directorio | Descripción |
|---|---|
| `docs/` | Documentación técnica y académica (20 subdirectorios: CIRC_DISP_ELECT/, SMPS/, EDA/, EASYEDA/, IMAGENES/, RAG/, vLLM/, OPENCODE/, PROTECTOR_120VAC/, ZBAR_PRACTICAS/, MANUAL/, etc.) |
| `cursos/` | Material de cursos y tesis (DISP_ELECTRONICOS/, INT_ELECTRONICA/, TESIS/, PLAN_ESTUDIOS/, LABORATORIO_I_FISICA/, LABORATORIO_II_FISICA/) |
| `.agent/` | Instrucciones del sistema para el agente IA (4 archivos: `AGENT_FRAMEWORK.md`, `AGENT_INSTRUCTIONS.md`, `latex.md`, `python.md`) |
| `directives/` | SOPs en YAML para flujos de trabajo repetibles (14 archivos) |
| `directives/rubricas/` | Rúbricas YAML para evaluación de prácticas de laboratorio |
| `execution/` | Scripts Python deterministas (7 archivos) |
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