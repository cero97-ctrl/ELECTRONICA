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
mcp = FastMCP("Circuit Vision Server")

@mcp.tool()
def analizar_imagenes_circuito(
    imagenes: str,
    prompt: str = "Describe detalladamente lo que ves en la(s) imagen(es).",
    modelo: str = "gemini-2.5-flash",
    api_backend: str = "gemini",
    output_dir: str = None
) -> str:
    """
    Analiza una o más imágenes de circuitos (esquemáticos, fotos) con un LLM multimodal y genera su informe PDF.
    
    Esta herramienta ejecuta el pipeline de visión completo: procesa las imágenes, solicita el análisis
    al LLM multimodal, convierte el análisis en un informe de LaTeX y lo compila de forma automática
    a PDF, emitiendo una alerta acústica de completado.
    
    Args:
        imagenes: Ruta(s) a los archivos de imagen separados por coma (ej: "esquema1.png", "foto2.jpg") o patrón glob.
        prompt: Instrucción o pregunta específica de análisis para el modelo.
        modelo: Nombre del modelo a usar (default: gemini-2.5-flash).
        api_backend: Backend de la API a usar: 'gemini' o 'openrouter' (default: gemini).
        output_dir: Directorio opcional donde guardar el informe LaTeX y PDF.
        
    Returns:
        Un reporte estructurado con el resumen del análisis, elementos detectados y la ruta absoluta del informe PDF.
    """
    if not imagenes.strip():
        return "Error: Las rutas de imágenes no pueden estar vacías."
        
    flujo_script = os.path.join(project_root, "flujo_analizar_imagen.py")
    python_exe = sys.executable  # Usa el mismo python del servidor MCP
    
    # Construir el comando
    cmd = [
        python_exe,
        flujo_script,
        imagenes,
        "--modelo", modelo,
        "--prompt", prompt,
        "--api-backend", api_backend
    ]
    
    if output_dir:
        cmd.extend(["--output-dir", os.path.abspath(output_dir)])
        
    print(f"Ejecutando análisis de imágenes: {' '.join(cmd)}")
    
    state_file = os.path.join(project_root, ".tmp", "run_state.json")
    mtime_before = os.path.getmtime(state_file) if os.path.exists(state_file) else None
    try:
        resultado = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=project_root
        )
        
        # Leer el estado final SOLO si el run_state.json fue reescrito por ESTA
        # corrida (si el flujo salió antes de escribir o falló sin llegar, el
        # archivo conserva un mtime viejo de otra corrida → vista HUÉRFANA que
        # no debe reportarse como resultado actual; ver execution/estado_sesion.py).
        state_data = {}
        if os.path.exists(state_file):
            try:
                if mtime_before is not None and os.path.getmtime(state_file) <= mtime_before:
                    pass  # archivo no modificado por esta corrida: no usar
                else:
                    with open(state_file, "r", encoding="utf-8") as f:
                        state_data = json.load(f)
            except Exception:
                state_data = {}
                
        if resultado.returncode == 0:
            descripcion = state_data.get("context", {}).get("descripcion", "N/A")
            archivo_tex = state_data.get("context", {}).get("archivo_tex", "N/A")
            archivo_pdf = state_data.get("context", {}).get("archivo_pdf", "N/A")
            archivos_procesados = state_data.get("context", {}).get("archivos", [])
            
            # Buscar el JSON intermedio generado
            json_tmp = ""
            for step in state_data.get("steps_completed", []):
                if step.get("step") == 1:
                    json_tmp = step.get("json_tmp", "")
                    
            res_str = (
                f"✅ ¡Análisis Visual y Compilación Completados Exitosamente!\n\n"
                f"--- RESUMEN DEL ANÁLISIS ---\n"
                f"• Imágenes Analizadas: {len(archivos_procesados)}\n"
                f"• Descripción General:\n{descripcion}\n\n"
                f"--- ARCHIVOS GENERADOS ---\n"
                f"• Informe PDF     : {archivo_pdf}\n"
                f"• Informe LaTeX   : {archivo_tex}\n"
                f"• Análisis JSON   : {json_tmp}\n\n"
                f"¡El informe PDF técnico ha sido compilado automáticamente y está listo para su consulta!"
            )
            return res_str
        else:
            stdout_snippet = resultado.stdout[-1500:] if len(resultado.stdout) > 1500 else resultado.stdout
            stderr_snippet = resultado.stderr[-1500:] if len(resultado.stderr) > 1500 else resultado.stderr
            
            res_str = (
                f"❌ El flujo de análisis visual falló con código de salida {resultado.returncode}.\n\n"
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
