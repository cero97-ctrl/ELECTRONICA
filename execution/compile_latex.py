#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
import tempfile
import argparse
from typing import Dict, Any

# Agregar el directorio raíz al path para poder importar clean_latex.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from clean_latex import clean_latex_aux_files
except ImportError:
    # Fallback si no se puede importar
    def clean_latex_aux_files(directory):
        KEEP_EXTENSIONS = [".tex", ".pdf", ".py", ".md", ".json", ".sh", ".png", ".jpg", ".jpeg", ".zip", ".ipynb", ".kicad_sch", ".txt"]
        for root, _, files in os.walk(directory):
            for filename in files:
                filepath = os.path.join(root, filename)
                if os.path.isfile(filepath):
                    _, ext = os.path.splitext(filename)
                    if ext.lower() not in KEEP_EXTENSIONS:
                        try:
                            os.remove(filepath)
                        except Exception:
                            pass

def compile_latex_code(latex_content: str, job_name: str = "document", output_dir: str = None) -> Dict[str, Any]:
    """
    Toma un string con código LaTeX, lo escribe en un archivo temporal,
    lo compila usando pdflatex (2 pasadas para referencias) y limpia auxiliares.
    
    Retorna un diccionario con el estado, ruta del PDF y los logs.
    """
    if not output_dir:
        # Usar un directorio temporal dentro del proyecto .tmp/latex_build/
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(project_root, ".tmp", "latex_build")
    
    os.makedirs(output_dir, exist_ok=True)
    
    tex_path = os.path.join(output_dir, f"{job_name}.tex")
    pdf_path = os.path.join(output_dir, f"{job_name}.pdf")
    log_path = os.path.join(output_dir, f"{job_name}.log")
    
    # Escribir el contenido a compilar
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(latex_content)
        
    print(f"Compilando LaTeX en: {tex_path}")
    
    # Comando de compilación (modo non-stop para que no se quede colgado en caso de error)
    cmd = [
        "pdflatex",
        "-interaction=nonstopmode",
        f"-jobname={job_name}",
        f"-output-directory={output_dir}",
        tex_path
    ]
    
    logs = []
    success = False
    
    # Primera pasada
    proc1 = subprocess.run(cmd, capture_output=True)
    stdout1 = proc1.stdout.decode("utf-8", errors="ignore")
    stderr1 = proc1.stderr.decode("utf-8", errors="ignore")
    logs.append(f"--- PASADA 1 STDOUT ---\n{stdout1}")
    if proc1.stderr:
        logs.append(f"--- PASADA 1 STDERR ---\n{stderr1}")
        
    # Verificar si se generó el PDF. Si no se generó, falló críticamente en la pasada 1.
    if os.path.exists(pdf_path):
        # Segunda pasada para resolver referencias cruzadas, índices y circuitikz
        proc2 = subprocess.run(cmd, capture_output=True)
        stdout2 = proc2.stdout.decode("utf-8", errors="ignore")
        stderr2 = proc2.stderr.decode("utf-8", errors="ignore")
        logs.append(f"--- PASADA 2 STDOUT ---\n{stdout2}")
        if proc2.stderr:
            logs.append(f"--- PASADA 2 STDERR ---\n{stderr2}")
        
        success = os.path.exists(pdf_path)
    else:
        success = False
        
    # Si falló, intentar extraer el error específico del archivo .log
    error_summary = ""
    if not success and os.path.exists(log_path):
        try:
            with open(log_path, "r", errors="ignore") as f:
                log_lines = f.readlines()
            # Buscar líneas que empiezan con '!' que indican error en LaTeX
            errors = [line.strip() for line in log_lines if line.startswith("!")]
            if errors:
                error_summary = "\n".join(errors[:5]) # Mostrar los primeros 5 errores
        except Exception as e:
            error_summary = f"No se pudo leer el archivo de log: {e}"
            
    # Limpiar archivos auxiliares generados en el directorio de salida
    clean_latex_aux_files(output_dir)
    
    # Si todo salió bien, retornar los detalles del PDF
    all_logs = "\n".join(logs)
    if success:
        return {
            "success": True,
            "pdf_path": os.path.abspath(pdf_path),
            "log": all_logs
        }
    else:
        # Si falló pero el PDF por alguna razón existe, o si no existe
        return {
            "success": False,
            "error": error_summary or "Fallo de compilación desconocido. Revisa los logs.",
            "log": all_logs
        }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compilador determinista de LaTeX.")
    parser.add_argument("--test", action="store_true", help="Ejecuta una compilación de prueba simple.")
    
    args = parser.parse_args()
    
    if args.test:
        test_latex = r"""
\documentclass{article}
\usepackage[utf8]{inputenc}
\usepackage[spanish]{babel}
\title{Prueba de Compilación MCP}
\author{Antigravity Agent}
\begin{document}
\maketitle
\section{Introducción}
Esta es una prueba de compilación exitosa delegada desde un servidor MCP.
\end{document}
"""
        res = compile_latex_code(test_latex, job_name="test_mcp")
        print(f"Resultado de la prueba: {res['success']}")
        if res['success']:
            print(f"PDF generado en: {res['pdf_path']}")
        else:
            print(f"Error: {res['error']}")
            print(f"Logs:\n{res['log'][-1000:]}") # Mostrar los últimos 1000 caracteres de log
