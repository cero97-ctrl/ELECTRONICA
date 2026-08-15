#!/usr/bin/env python3
import os
import sys
import subprocess
import json
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Cargar variables de entorno desde el .env absoluto del proyecto
project_root = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(project_root, ".env"))

# Inicializar el servidor MCP de FastMCP
mcp = FastMCP("Examen Elaborator Server")

@mcp.tool()
def elaborar_nuevo_examen(
    tema: str,
    nivel: str = "intermedia",
    modelo: str = "qwen/qwen3.6-27b",
    api_backend: str = "openrouter",
    output_dir: str = None
) -> str:
    """
    Elabora un examen nuevo y su solucionario (PDF y LaTeX) sobre un tema de electrónica.
    
    Esta herramienta genera un examen completo de 5 preguntas de razonamiento y cálculo,
    crea los documentos LaTeX correspondientes, y compila de forma automática tanto el
    examen como el solucionario a PDF, emitiendo una alerta sonora de completado.
    
    Args:
        tema: El tema específico de electrónica (ej: "Semana 2: Diodos y Rectificadores", "Transistor BJT").
        nivel: Dificultad del examen: 'basica', 'intermedia' o 'avanzada' (default: intermedia).
        modelo: Modelo de lenguaje para la elaboración (default: qwen/qwen3.6-27b).
        api_backend: Backend de API a usar: 'gemini', 'groq' o 'openrouter' (default: openrouter).
        output_dir: Directorio opcional donde guardar el examen y solucionario (default: examenes/).
        
    Returns:
        Un reporte estructurado con las rutas absolutas de los PDFs del examen y solucionario
        generados, el título del examen y el registro de la ejecución.
    """
    if not tema.strip():
        return "Error: El tema no puede estar vacío."
        
    project_root = os.path.dirname(os.path.abspath(__file__))
    flujo_script = os.path.join(project_root, "flujo_elaborar_examen.py")
    python_exe = sys.executable  # Usa el mismo python del servidor MCP
    
    # Resolver directorio de salida
    if not output_dir:
        # Carpeta por defecto
        dest_dir = os.path.join(project_root, "examenes")
    else:
        dest_dir = os.path.abspath(output_dir)
        
    os.makedirs(dest_dir, exist_ok=True)
    
    # Construir el comando para ejecutar flujo_elaborar_examen.py
    cmd = [
        python_exe,
        flujo_script,
        "--tema", tema,
        "--nivel", nivel,
        "--modelo", modelo,
        "--api-backend", api_backend,
        "--output", dest_dir
    ]
    
    print(f"Ejecutando elaboración de examen: {' '.join(cmd)}")
    
    try:
        resultado = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=project_root
        )
        
        # Intentar leer el estado final en .tmp/run_state.json para dar una respuesta rica
        state_file = os.path.join(project_root, ".tmp", "run_state.json")
        state_data = {}
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    state_data = json.load(f)
            except Exception:
                pass
                
        if resultado.returncode == 0:
            titulo = state_data.get("context", {}).get("titulo", "N/A")
            n_preguntas = state_data.get("context", {}).get("n_preguntas", "5")
            
            # Recuperar rutas de PDFs del estado
            examen_pdf = state_data.get("context", {}).get("examen_pdf", "N/A")
            solucionario_pdf = state_data.get("context", {}).get("solucionario_pdf", "N/A")
            
            # Recuperar JSON de evaluación generado en .tmp/
            json_tmp = ""
            for step in state_data.get("steps_completed", []):
                if step.get("step") == 1:
                    json_tmp = step.get("json_tmp", "")
                    
            res_str = (
                f"✅ ¡Examen Elaborado y Compilado Exitosamente!\n\n"
                f"--- DETALLES DEL EXAMEN ---\n"
                f"• Título    : {titulo}\n"
                f"• Preguntas : {n_preguntas}\n"
                f"• Dificultad: {nivel.capitalize()}\n"
                f"• Tema      : {tema}\n\n"
                f"--- ARCHIVOS PDF GENERADOS ---\n"
                f"• Examen PDF      : {examen_pdf}\n"
                f"• Solucionario PDF: {solucionario_pdf}\n\n"
                f"--- ARCHIVOS FUENTE ---\n"
                f"• JSON del examen : {json_tmp}\n\n"
                f"¡Los documentos han sido compilados automáticamente y están listos para imprimir!"
            )
            return res_str
        else:
            stdout_snippet = resultado.stdout[-1500:] if len(resultado.stdout) > 1500 else resultado.stdout
            stderr_snippet = resultado.stderr[-1500:] if len(resultado.stderr) > 1500 else resultado.stderr
            
            res_str = (
                f"❌ El flujo de elaboración de examen falló con código de salida {resultado.returncode}.\n\n"
                f"--- STDERR ---\n"
                f"{stderr_snippet}\n\n"
                f"--- STDOUT ---\n"
                f"{stdout_snippet}"
            )
            return res_str
            
    except Exception as e:
        return f"Error crítico al orquestar la ejecución del flujo: {str(e)}"

if __name__ == "__main__":
    mcp.run()
