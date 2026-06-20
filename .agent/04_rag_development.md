# Desarrollo y Mantenimiento del Asistente RAG (`rag_system.py`)

- **Stack Principal:** LangChain, ChromaDB (Vector Store), Hugging Face Embeddings (`paraphrase-multilingual-MiniLM-L12-v2`), y LLMs de alta velocidad a través de la API de Groq (ej. Llama 3).
- **Manejo de Archivos:** El sistema debe procesar ágilmente formatos académicos y técnicos: `.md`, `.tex` y `.pdf`.
- **Optimización Incremental:** El script debe ser capaz de detectar cambios y sincronizarse de manera inteligente, actualizando solo los archivos nuevos o modificados consultando el archivo de estado `db_state.json`.
- **Estilo de Código Python:** 
  - Modularidad: Mantener la separación de responsabilidades (Extracción, Vectorización, Retrieval, Interfaz).
  - Robustez: Proveer manejo de excepciones adecuado.
  - Calidad: Usar *Type Hinting* y comentarios claros en el código.
- **Memoria Conversacional:** Asegurar que la cadena de LangChain preserve el historial de la conversación para responder a preguntas contextuales dependientes del historial de chat.