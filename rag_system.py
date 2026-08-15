#!/usr/bin/env python
import os
import sys
import shutil
import json
import glob
import argparse
from datetime import datetime

from langchain_community.document_loaders import DirectoryLoader, TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI

from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_classic.chains import create_history_aware_retriever

from execution.data_capture import data_capture

# 1. Configurar API Key de OpenRouter (desde .env o variable de entorno)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    print("Error: No se encontró OPENROUTER_API_KEY en el archivo .env o en las variables de entorno.")
    sys.exit(1)

# 2. Configurar Embeddings y Directorio de la Base de Datos
persist_dir = os.path.join(os.path.dirname(__file__), "chroma_db")
db_state_path = os.path.join(os.path.dirname(__file__), "db_state.json")
embeddings = HuggingFaceEmbeddings(model_name="paraphrase-multilingual-MiniLM-L12-v2")

# --- Funciones de gestión de estado y escaneo de archivos ---
def load_state(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_state(path, state):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)

def get_workspace_files(root_dir, patterns, exclusions):
    all_files = {}
    for pattern in patterns:
        for filepath in glob.glob(os.path.join(root_dir, pattern), recursive=True):
            if any(ex in filepath for ex in exclusions) or not os.path.isfile(filepath):
                continue
            all_files[filepath] = os.path.getmtime(filepath)
    return all_files

# Comprobar si se solicitó una actualización forzada desde la consola
parser = argparse.ArgumentParser(
    description="Asistente de Inteligencia Artificial (RAG) para el espacio de trabajo de Electrónica.",
    epilog="Para terminar la sesión interactiva, escribe 'salir', 'exit' o 'quit' en el chat."
)
parser.add_argument("--update", action="store_true", help="Fuerza el borrado y la reconstrucción total de la base de datos vectorial ChromaDB.")
parser.add_argument("--no-capture-data", action="store_true", help="Desactiva la captura de datos de entrenamiento (datasets/).")
args = parser.parse_args()

if args.no_capture_data:
    data_capture.enabled = False

update_db = args.update
if update_db and os.path.exists(persist_dir):
    print("Se solicitó actualización forzada. Borrando base de datos y estado antiguos...")
    shutil.rmtree(persist_dir)
    if os.path.exists(db_state_path):
        os.remove(db_state_path)

# --- Lógica de Carga y Actualización Incremental ---
print("Cargando/Inicializando base de conocimientos ChromaDB...")
vectorstore = Chroma(persist_directory=persist_dir, embedding_function=embeddings)

print("Buscando archivos nuevos o modificados en el espacio de trabajo...")
dir_path = "/home/cero/MEGA/VS_CODE_WORKSPACE/ELECTRONICA"
file_patterns = ["**/*.tex", "**/*.md", "**/*.pdf"]
file_exclusions = ["(copia)"]

processed_files_state = load_state(db_state_path)
current_files_state = get_workspace_files(dir_path, file_patterns, file_exclusions)

files_to_process = {
    f for f, mtime in current_files_state.items()
    if f not in processed_files_state or mtime > processed_files_state.get(f, 0)
}

if not files_to_process and os.path.exists(persist_dir) and os.listdir(persist_dir):
    print("La base de conocimientos está actualizada. No se encontraron cambios.")
else:
    if not files_to_process and not (os.path.exists(persist_dir) and os.listdir(persist_dir)):
        print("Base de datos vacía. Procesando todos los archivos encontrados...")
        files_to_process = set(current_files_state.keys())

    if files_to_process:
        print(f"Se encontraron {len(files_to_process)} archivos nuevos o modificados para procesar.")
        docs = []
        for filepath in files_to_process:
            try:
                loader = PyPDFLoader(filepath) if filepath.endswith(".pdf") else TextLoader(filepath, encoding="utf-8")
                docs.extend(loader.load())
            except Exception as e:
                print(f"  - Error cargando {filepath}: {e}")

        if docs:
            print(f"Se cargaron {len(docs)} documentos. Dividiendo y procesando...")
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            splits = text_splitter.split_documents(docs)
            
            print("Añadiendo nuevos fragmentos a la base de conocimientos...")
            vectorstore.add_documents(documents=splits)
            
            print("Actualizando estado de los archivos procesados...")
            processed_files_state.update({f: current_files_state[f] for f in files_to_process})
            save_state(db_state_path, processed_files_state)
            print("¡Actualización incremental completada!")
    else:
        print("No se encontraron archivos para procesar.")

# 5. Configurar el recuperador y el modelo de lenguaje (LLM)
retriever = vectorstore.as_retriever(search_kwargs={"k": 4}) # Recupera los 4 fragmentos más relevantes para ahorrar tokens
# Presupuesto de salida configurable (OPENROUTER_MAX_TOKENS en .env/entorno).
# Default 2048: compatible con el tier gratuito de OpenRouter. Subir (ej. 8192) tras recargar créditos.
OPENROUTER_MAX_TOKENS = int(os.environ.get("OPENROUTER_MAX_TOKENS", "2048"))
llm = ChatOpenAI(model="openai/gpt-oss-20b", temperature=0, max_tokens=OPENROUTER_MAX_TOKENS,
                 api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")

# 6. Crear memoria conversacional y el Prompt RAG
# 6.1 Prompt para contextualizar la pregunta usando el historial
contextualize_q_system_prompt = (
    "Dada una conversación y una pregunta reciente del usuario "
    "que podría hacer referencia al contexto en el historial de chat, "
    "formula una pregunta independiente que pueda entenderse sin el historial. "
    "NO respondas la pregunta, solo reformúlala si es necesario, o devuélvela tal cual."
)
contextualize_q_prompt = ChatPromptTemplate.from_messages([
    ("system", contextualize_q_system_prompt),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])
history_aware_retriever = create_history_aware_retriever(llm, retriever, contextualize_q_prompt)

# 6.2 Crear el Prompt RAG para la respuesta final
system_prompt = (
    "Eres un asistente académico experto. Usa los siguientes fragmentos de contexto "
    "para responder a la pregunta del usuario. Si no sabes la respuesta, di que no lo sabes.\n\n"
    "{context}"
)
qa_prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
])

# 7. Ensamblar y ejecutar la cadena RAG con memoria
question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

print("\n¡El sistema RAG está listo! Escribe 'salir' para terminar.")
chat_history = []
try:
    while True:
        pregunta = input("\nTu pregunta: ")
        if pregunta.lower() in ['salir', 'exit', 'quit']:
            break
            
        if not pregunta.strip():
            continue

        response = rag_chain.invoke({
            "input": pregunta,
            "chat_history": chat_history[-6:] # Limita el historial a los últimos 6 mensajes (3 turnos) para ahorrar tokens
        })

        print("\n--- RESPUESTA ---")
        print(response["answer"])

        # Captura pasiva de datos de entrenamiento (dataset RAG, ShareGPT)
        try:
            data_capture.capture_rag(
                user_query=pregunta,
                assistant_response=response["answer"],
                system_prompt=system_prompt,
                retrieved_context=response["context"],
                domain="electronica",
                model="openai/gpt-oss-20b",
            )
        except Exception as e:
            print(f"  ⚠  (captura de datos omitida: {e})")

        # Actualizar el historial de chat
        chat_history.append(HumanMessage(content=pregunta))
        chat_history.append(AIMessage(content=response["answer"]))

        print("\n--- FRAGMENTOS RECUPERADOS (CONTEXTO) ---")
        for i, doc in enumerate(response["context"]):
            print(f"\n[Fragmento {i+1}]")
            print(f"Fuente: {doc.metadata.get('source', 'Desconocida')}")
            print(f"Contenido (primeros 300 caracteres): {doc.page_content[:300]}...")
            print("-" * 50)
except (KeyboardInterrupt, EOFError):
    print("\n\nSaliendo del sistema interactivo...")
finally:
    if chat_history:
        print("\nGenerando resumen de la sesión para actualizar la memoria de contexto...")
        try:
            # Preparamos el historial para el LLM
            formatted_history = "\n".join([f"{'Usuario' if isinstance(msg, HumanMessage) else 'IA'}: {msg.content}" for msg in chat_history])
            summary_prompt = (
                "Resume los temas principales, problemas resueltos y decisiones de esta sesión de forma concisa "
                "en formato Markdown (usa viñetas breves). No saludes, ve directo al grano para que sirva de 'memoria'.\n\n"
                f"Conversación:\n{formatted_history}"
            )
            summary_response = llm.invoke(summary_prompt).content
            
            context_file_path = os.path.join(os.path.dirname(__file__), ".gemini", "07_context.md")
            os.makedirs(os.path.dirname(context_file_path), exist_ok=True)
            
            with open(context_file_path, "a", encoding="utf-8") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"\n## Resumen de Sesión ({timestamp})\n\n")
                f.write(f"{summary_response}\n")
            print(f"¡Contexto actualizado exitosamente en {context_file_path}!")
            
            # Añadir el resumen a la base de datos vectorial (ChromaDB)
            print("Integrando la memoria de la sesión en ChromaDB...")
            vectorstore.add_texts(
                texts=[f"Resumen de sesión de trabajo ({timestamp}):\n{summary_response}"],
                metadatas=[{"source": "memoria_sesion", "timestamp": timestamp}]
            )
            print("¡Memoria integrada exitosamente en la base de conocimientos RAG!")
        except Exception as e:
            print(f"Error al guardar el contexto o actualizar ChromaDB: {e}")
    print("¡Hasta luego!")
