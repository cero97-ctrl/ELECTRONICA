# Espacio de Trabajo de Electrónica & Asistente IA (RAG)

Este repositorio contiene apuntes, tesis y guías relacionadas con Electrónica, Internet de las Cosas (IoT), y Diseño de Circuitos Integrados (EDA / OpenROAD), todo esto potenciado por un **Asistente de Inteligencia Artificial basado en RAG** (Retrieval-Augmented Generation).

## 🧠 Asistente RAG (`rag_system.py`)

El script principal `rag_system.py` es un chatbot académico personalizado que lee, vectoriza y responde preguntas basándose **estrictamente** en los documentos locales de este espacio de trabajo.

### Características Principales:
- **Soporte Multiformato:** Procesa archivos Markdown (`.md`), LaTeX (`.tex`) y PDF (`.pdf`).
- **Actualizaciones Incrementales:** Detecta automáticamente archivos nuevos o modificados para actualizar la base de conocimientos sin reprocesar todo desde cero.
- **Modelo Multilingüe:** Utiliza embeddings locales de Hugging Face (`paraphrase-multilingual-MiniLM-L12-v2`) altamente optimizados para entender el español a la perfección.
- **Memoria Conversacional:** El bot es consciente del historial de la charla actual, permitiendo conversaciones fluidas y contextualizadas.
- **LLM Ultrarrápido:** Impulsado por Llama 3 (vía la API de Groq) para inferencias casi instantáneas.

## ⚙️ Instalación y Configuración

1. Activa tu entorno virtual de Python (ej. `elect_env`).
2. Instala las dependencias requeridas (LangChain, ChromaDB, HuggingFace, PyPDF, etc.):
   ```bash
   pip install langchain langchain-community langchain-classic langchain-chroma langchain-huggingface langchain-groq pypdf sentence-transformers
   ```
3. Obtén una API Key gratuita de Groq.
4. Crea un archivo oculto llamado `.groq_api_key` en la raíz de este directorio y pega tu clave allí (sin espacios ni comillas).

## 🚀 Uso

Para iniciar el asistente interactivo. Este comando también buscará automáticamente archivos nuevos o modificados y actualizará la base de datos en segundo plano:
```bash
python rag_system.py
```

Si eliminaste archivos o deseas forzar el borrado y la reconstrucción total de la base de datos vectorial:
```bash
python rag_system.py --update
```
Escribe `salir`, `exit` o `quit` para terminar la sesión de chat.

## 📂 Estructura del Proyecto

- `rag_system.py`: Script principal del sistema RAG y chatbot interactivo.
- `docs/`: Documentación del proyecto, guías y apuntes.
  - `guia_rag.tex`: Documento académico que explica cómo implementar este mismo sistema RAG paso a paso.
  - `registro_errores_latex.md`: Base de conocimientos e instrucciones estrictas para la IA sobre correcciones de LaTeX.
  - `EDA/`: Apuntes sobre automatización de diseño electrónico y OpenROAD.
- `cursos/`: Material detallado sobre Tesis y cursos de IoT con Raspberry Pi y Python.
- `.gemini/`: Directorio oculto que contiene el contexto y directrices personalizadas para el asistente de IA (Gemini).
  - `07_context.md`: Almacena la memoria conversacional y los resúmenes de las sesiones anteriores, autogenerados por el sistema RAG al salir.
  - `*.md` (ej. `01_latex_standards.md`): Archivos de instrucciones que definen los estándares, convenciones de código y reglas de formato del proyecto.
- `chroma_db/`: *(Autogenerado)* Directorio que almacena la base de datos vectorial local.
- `db_state.json`: *(Autogenerado)* Archivo que mantiene el registro de los archivos ya procesados para las actualizaciones incrementales.

---
*Desarrollado con LangChain y modelos Open-Source.*