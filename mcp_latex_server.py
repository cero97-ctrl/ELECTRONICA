#!/usr/bin/env python3
import os
import sys
from mcp.server.fastmcp import FastMCP

# Añadir el directorio del proyecto al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from execution.compile_latex import compile_latex_code

# Inicializar el servidor MCP de FastMCP
mcp = FastMCP("LaTeX Compiler Server")

@mcp.tool()
def compilar_latex(codigo_latex: str, nombre_documento: str = "documento_mcp") -> str:
    """
    Compila un fragmento o documento de LaTeX completo a PDF.
    
    Esta herramienta recibe código LaTeX en texto plano, lo compila de forma remota/aislada
    y retorna la ruta absoluta del archivo PDF generado en el servidor o el log de error detallado.
    
    Args:
        codigo_latex: Código fuente de LaTeX completo (incluyendo \\documentclass, etc.).
        nombre_documento: Nombre base para los archivos generados (opcional).
    
    Returns:
        Un mensaje descriptivo con la ruta absoluta del archivo PDF compilado o
        un resumen detallado de los errores de compilación de pdflatex.
    """
    try:
        resultado = compile_latex_code(codigo_latex, job_name=nombre_documento)
        
        if resultado["success"]:
            pdf_path = resultado["pdf_path"]
            return (
                f"¡Compilación Exitosa!\n"
                f"El archivo PDF ha sido generado y guardado en:\n"
                f"{pdf_path}\n\n"
                f"Puedes abrir o transferir este archivo según sea necesario."
            )
        else:
            error_msg = resultado.get("error", "Fallo desconocido en pdflatex.")
            log_output = resultado.get("log", "")
            # Limitar el log de error para no saturar el contexto de la IA
            log_snippet = log_output[-1500:] if len(log_output) > 1500 else log_output
            
            return (
                f"Fallo en la compilación de LaTeX.\n\n"
                f"--- RESUMEN DE ERROR ---\n"
                f"{error_msg}\n\n"
                f"--- FRAGMENTO DEL LOG DE COMPILACIÓN ---\n"
                f"{log_snippet}"
            )
            
    except Exception as e:
        return f"Error crítico al intentar invocar la compilación: {str(e)}"

if __name__ == "__main__":
    # Iniciar el servidor MCP (por defecto usa transporte de entrada/salida estándar stdio)
    mcp.run()
