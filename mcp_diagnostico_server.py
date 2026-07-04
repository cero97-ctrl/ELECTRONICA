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
mcp = FastMCP("System Diagnostic Server")

@mcp.tool()
def generar_diagnostico_sistema(
    output_dir: str = None,
    filename: str = "informe_diagnostico"
) -> str:
    """
    Realiza un diagnóstico de hardware y software del PC local y compila un reporte en PDF.
    
    Esta herramienta ejecuta la telemetría del sistema (OS, CPU, RAM, GPU, disco),
    formatea los datos en un reporte LaTeX técnico profesional y compila automáticamente
    el reporte a PDF, emitiendo una alerta acústica de completado.
    
    Args:
        output_dir: Directorio de destino para guardar el reporte LaTeX y PDF (default: docs/DIAGNOSTICOS/).
        filename: Nombre del archivo del informe sin extensión (default: informe_diagnostico).
        
    Returns:
        Un reporte estructurado con las rutas de los archivos generados y un resumen técnico clave.
    """
    flujo_script = os.path.join(project_root, "flujo_diagnostico.py")
    python_exe = sys.executable  # Usa el mismo python del servidor MCP
    
    # Resolver directorio de salida
    if not output_dir:
        dest_dir = os.path.join(project_root, "docs", "DIAGNOSTICOS")
    else:
        dest_dir = os.path.abspath(output_dir)
        
    os.makedirs(dest_dir, exist_ok=True)
    
    # Construir el comando para ejecutar flujo_diagnostico.py
    cmd = [
        python_exe,
        flujo_script,
        "--output-dir", dest_dir,
        "--filename", filename
    ]
    
    print(f"Ejecutando diagnóstico de sistema: {' '.join(cmd)}")
    
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
            archivo_tex = state_data.get("context", {}).get("archivo_tex", "N/A")
            archivo_pdf = state_data.get("context", {}).get("archivo_pdf", "N/A")
            telemetria = state_data.get("context", {}).get("telemetria", {})
            
            res_str = (
                f"✅ ¡Telemetría y Reporte de Diagnóstico Completados Exitosamente!\n\n"
                f"--- RECURSOS DE HARDWARE Y SOFTWARE DISPONIBLES (TELEMETRÍA CRUDA) ---\n"
                f"```json\n"
                f"{json.dumps(telemetria, indent=2, ensure_ascii=False)}\n"
                f"```\n\n"
                f"--- ARCHIVOS PDF GENERADOS ---\n"
                f"• Reporte PDF     : {archivo_pdf}\n"
                f"• Reporte LaTeX   : {archivo_tex}\n\n"
                f"¡El informe de diagnóstico de hardware/software ha sido compilado y está listo en docs/DIAGNOSTICOS/!"
            )
            return res_str
        else:
            stdout_snippet = resultado.stdout[-1500:] if len(resultado.stdout) > 1500 else resultado.stdout
            stderr_snippet = resultado.stderr[-1500:] if len(resultado.stderr) > 1500 else resultado.stderr
            
            res_str = (
                f"❌ El flujo de diagnóstico falló con código de salida {resultado.returncode}.\n\n"
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
