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
mcp = FastMCP("Examen Evaluator Server")

@mcp.tool()
def evaluar_examen_estudiante(
    pdf_path: str,
    rubrica_path: str = None,
    modelo: str = "gemini-2.5-flash",
    api_backend: str = "gemini",
    dpi: int = 250
) -> str:
    """
    Evalúa un examen en PDF de un estudiante y genera un informe en LaTeX.
    
    Esta herramienta recibe el archivo PDF del examen de un estudiante, ejecuta el pipeline completo de
    evaluación (lectura de PDF, consulta del LLM para calificar, y generación automática del informe
    académico en LaTeX), y emite una alerta de sonido cuando el proceso ha concluido.
    
    Args:
        pdf_path: Ruta absoluta o relativa al archivo PDF del examen.
        rubrica_path: Ruta opcional al archivo YAML de la rúbrica (ej: directives/rubricas/rubrica_practica_lab.yaml).
        modelo: Nombre del modelo a usar (default: gemini-2.5-flash; con api_backend openrouter usa anthropic/claude-opus-5 automáticamente).
        api_backend: Backend de la API a usar: 'gemini', 'openrouter' o 'groq' (default: gemini).
        dpi: Resolución en DPI para renderizar las páginas del PDF a imágenes (default: 250).
        
    Returns:
        Un reporte estructurado con el resultado de la evaluación (puntaje, nivel de desempeño),
        rutas de los archivos generados (.tex, .json) y el registro de la ejecución.
    """
    # Resolver rutas absolutas
    pdf_abs = os.path.abspath(pdf_path)
    if not os.path.exists(pdf_abs):
        return f"Error: El archivo de examen PDF no existe en la ruta: {pdf_path}"
        
    project_root = os.path.dirname(os.path.abspath(__file__))
    flujo_script = os.path.join(project_root, "flujo_evaluar_examen.py")
    
    # Usar el mismo intérprete de python con el que se levantó el servidor MCP
    python_exe = sys.executable
    
    # Construir el comando para ejecutar flujo_evaluar_examen.py
    cmd = [
        python_exe,
        flujo_script,
        "--pdf", pdf_abs,
        "--modelo", modelo,
        "--api-backend", api_backend,
        "--dpi", str(dpi)
    ]
    
    if rubrica_path:
        rubrica_abs = os.path.abspath(rubrica_path)
        if not os.path.exists(rubrica_abs):
            return f"Error: El archivo de rúbrica especificado no existe en: {rubrica_path}"
        cmd += ["--rubrica", rubrica_abs]
        
    print(f"Ejecutando evaluación: {' '.join(cmd)}")
    
    # Ejecutar el flujo de evaluación
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
            estudiante = state_data.get("estudiante", os.path.basename(pdf_path))
            puntaje = state_data.get("context", {}).get("puntaje", "N/A")
            nivel = state_data.get("context", {}).get("nivel", "N/A")
            archivo_tex = state_data.get("context", {}).get("archivo_tex", "N/A")
            archivo_pdf = state_data.get("context", {}).get("archivo_pdf", "N/A")
            
            # Buscar el JSON de evaluación generado en .tmp/
            json_tmp = ""
            for step in state_data.get("steps_completed", []):
                if step.get("step") == 1:
                    json_tmp = step.get("json_tmp", "")
                    
            res_str = (
                f"✅ ¡Flujo de Evaluación Completado Exitosamente para {estudiante}!\n\n"
                f"--- RESULTADO DE LA EVALUACIÓN ---\n"
                f"• Puntaje Sugerido : {puntaje}\n"
                f"• Nivel de Desempeño: {nivel}\n\n"
                f"--- ARCHIVOS GENERADOS ---\n"
                f"• Informe PDF     : {archivo_pdf}\n"
                f"• Informe LaTeX   : {archivo_tex}\n"
                f"• Evaluación JSON  : {json_tmp}\n\n"
                f"¡El informe PDF ha sido compilado automáticamente y está listo para su revisión!"
            )
            return res_str
        else:
            # Si el script falló, extraer el error del stderr u output
            stdout_snippet = resultado.stdout[-1500:] if len(resultado.stdout) > 1500 else resultado.stdout
            stderr_snippet = resultado.stderr[-1500:] if len(resultado.stderr) > 1500 else resultado.stderr
            
            res_str = (
                f"❌ El flujo de evaluación falló con código de salida {resultado.returncode}.\n\n"
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
