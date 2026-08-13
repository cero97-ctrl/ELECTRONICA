#!/usr/bin/env python3
"""
flujo_diagnostico.py — Orquestador del flujo de diagnóstico de sistema (Layer 2)

Ejecuta el flujo completo definido en la directiva diagnostico_mcp.yaml:
  1. env_diagnostic.py -> Obtiene la telemetría del sistema (JSON)
  2. Formatea a LaTeX -> Genera el archivo .tex del informe técnico
  3. compile_latex    -> Compila a PDF y limpia auxiliares
  4. alert_user.py    -> Notifica al usuario con alerta sonora
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
TMP_DIR   = SCRIPT_DIR / ".tmp"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from execution.estilo_infografia import PREAMBULO_INFOGRAFIA

# ── Configuración ──────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent.resolve()
PYTHON       = sys.executable
DIAGNOSTIC   = SCRIPT_DIR / "execution" / "env_diagnostic.py"
ALERTAR      = SCRIPT_DIR / "execution" / "alert_user.py"
TMP_DIR      = SCRIPT_DIR / ".tmp"
STATE_FILE   = TMP_DIR / "run_state.json"
DEFAULT_OUT  = SCRIPT_DIR / "docs" / "DIAGNOSTICOS"

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def print_step(num: int, total: int, desc: str) -> None:
    bar = "─" * 56
    print(f"\n{bar}")
    print(f"  Paso {num}/{total}  │  {desc}")
    print(f"{bar}")

def print_ok(msg: str) -> None:
    print(f"  ✅  {msg}")

def print_err(msg: str) -> None:
    print(f"  ❌  {msg}", file=sys.stderr)

def save_state(state: dict) -> None:
    TMP_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def escape_latex(text: str) -> str:
    if text is None:
        return "N/A"
    text = str(text)
    # Reemplazar backslash primero para evitar escape infinito
    text = text.replace("\\", "\\textbackslash{}")
    # Escapar caracteres especiales de LaTeX
    for char in ["_", "%", "&", "#", "$", "{", "}", "~", "^"]:
        text = text.replace(char, "\\" + char)
    return text

def generar_latex_reporte(telemetria: dict, fecha_str: str) -> str:
    core = telemetria.get("core", {})
    hw = telemetria.get("hardware", {})
    net = telemetria.get("network", {})
    ram = hw.get("ram", {})
    disk = hw.get("disk", {})
    gpus = hw.get("gpus", [])
    
    # Escapar los valores de texto para evitar errores de compilación
    os_name = escape_latex(core.get("os", "N/A"))
    release = escape_latex(core.get("release", "N/A"))
    arch = escape_latex(core.get("architecture", "N/A"))
    hostname = escape_latex(core.get("hostname", "N/A"))
    py_ver = escape_latex(core.get("python_version", "N/A"))
    conda_env = escape_latex(core.get("conda_env", "N/A"))
    encoding = escape_latex(core.get("encoding", "N/A"))
    uptime = escape_latex(core.get("uptime", "N/A"))
    cpu_model = escape_latex(hw.get("cpu_model", "N/A"))
    
    # Procesar GPUs
    gpu_section = ""
    if gpus:
        gpu_section = "\\subsection{Tarjetas Gráficas (GPUs)}\n"
        gpu_section += "Se han detectado las siguientes GPUs activas de NVIDIA:\n"
        gpu_section += "\\begin{itemize}\n"
        for g in gpus:
            name = escape_latex(g.get("name", "N/A"))
            mem_tot = g.get("memory_total_mb", 0)
            mem_free = g.get("memory_free_mb", 0)
            util = g.get("utilization_percent", 0)
            gpu_section += f"  \\item \\textbf{{{name}}}: Memoria Total: {mem_tot} MB, Memoria Libre: {mem_free} MB, Utilización: {util}\\%.\n"
        gpu_section += "\\end{itemize}\n"
    else:
        gpu_section = "\\subsection{Tarjetas Gráficas (GPUs)}\nNo se detectaron GPUs aceleradas de NVIDIA activas o `nvidia-smi` no está instalado.\n"

    # Formatear el contenido LaTeX del informe
    latex = PREAMBULO_INFOGRAFIA + r"""
% ── Cabeceras específicas del informe ──────────────────────────────────────────
\fancyhead[L]{\small\color{azulNoche}\textbf{Reporte de Diagnóstico} --- Sistema}
\fancyhead[R]{\small """ + fecha_str + r"""}
\renewcommand{\headrulewidth}{0pt}

% ─────────────────────────────────────────────────────────────────────────────
\begin{document}

% ══ PORTADA INFográfica ════════════════════════════════════════════════════════
\bandaTitulo{Reporte Técnico de Diagnóstico del Sistema}{Generado por el Agente IA (Orquestador MCP)}

% Información básica del sistema
\section{Resumen del Sistema}
Este documento presenta el diagnóstico del hardware y software de la máquina anfitriona donde están alojados los servidores MCP locales del espacio de trabajo. El diagnóstico ha sido generado y compilado de forma automática de extremo a extremo.

\section{Especificaciones del Software y Núcleo}
A continuación se detallan las características principales del sistema operativo y del entorno virtual de desarrollo de Python.

\begin{table}[h!]
\centering
\begin{tabular}{ll}
\hline
\textbf{Parámetro} & \textbf{Valor} \\ \hline
Sistema Operativo & """ + os_name + r""" \\
Versión/Release & """ + release + r""" \\
Arquitectura & """ + arch + r""" \\
Nombre del Host (Hostname) & """ + hostname + r""" \\
Versión de Python & """ + py_ver + r""" \\
Entorno Conda Activo & """ + conda_env + r""" \\
Codificación por Defecto & """ + encoding + r""" \\
Tiempo de Actividad (Uptime) & """ + uptime + r""" \\ \hline
\end{tabular}
\caption{Características del software y sistema base.}
\end{table}

\section{Especificaciones de Hardware}
Detalles del procesador, memoria RAM disponible y almacenamiento en disco.

\subsection{Procesador (CPU)}
\begin{itemize}
    \item \textbf{Modelo:} """ + cpu_model + r"""
    \item \textbf{Núcleos (Cores):} """ + str(hw.get("cpu_cores", "N/A")) + r""" núcleos lógicos
\end{itemize}

\subsection{Memoria RAM}
\begin{itemize}
    \item \textbf{Memoria Total:} """ + str(ram.get("total_gb", "N/A")) + r""" GB
    \item \textbf{Memoria Disponible:} """ + str(ram.get("available_gb", "N/A")) + r""" GB
    \item \textbf{Porcentaje en Uso:} """ + str(ram.get("percent_used", "N/A")) + r"""\%
\end{itemize}

\subsection{Almacenamiento (Disco Raíz)}
\begin{itemize}
    \item \textbf{Capacidad Total:} """ + str(disk.get("total_gb", "N/A")) + r""" GB
    \item \textbf{Espacio Usado:} """ + str(disk.get("used_gb", "N/A")) + r""" GB
    \item \textbf{Espacio Libre:} """ + str(disk.get("free_gb", "N/A")) + r""" GB
    \item \textbf{Porcentaje en Uso:} """ + str(disk.get("percent_used", "N/A")) + r"""\%
\end{itemize}

""" + gpu_section + r"""

\section{Herramientas de Desarrollo y Compilación}
Estado de instalación de herramientas de desarrollo esenciales en el sistema:

\begin{itemize}
    \item \textbf{Git:} """ + ("Instalado" if net.get("git_installed") else "No detectado") + r"""
    \item \textbf{Curl:} """ + ("Instalado" if net.get("curl_installed") else "No detectado") + r"""
    \item \textbf{PdfLaTeX (Compilador LaTeX):} """ + ("Instalado" if net.get("pdflatex_installed") else "No detectado") + r"""
\end{itemize}

\end{document}
"""
    return latex

def flujo_completo(output_dir: Path, filename: str) -> int:
    run_id = f"flujo-diagnostico-{now_iso()[:19].replace(':', '-')}"
    output_tex = output_dir / f"{filename}.tex"
    
    state = {
        "run_id": run_id,
        "directive": "diagnostico_mcp.yaml",
        "started_at": now_iso(),
        "last_updated": now_iso(),
        "current_step": 0,
        "steps_completed": [],
        "steps_failed": [],
        "context": {}
    }
    save_state(state)
    
    total_pasos = 4
    
    # ══ PASO 1: Obtener Telemetría (JSON) ═════════════════════════════════════
    print_step(1, total_pasos, "Obteniendo telemetría del sistema...")
    cmd_diag = [PYTHON, str(DIAGNOSTIC)]
    
    res = subprocess.run(cmd_diag, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        print_err(f"Falló env_diagnostic.py (código {res.returncode}): {res.stderr}")
        state["steps_failed"].append({"step": 1, "script": "env_diagnostic.py", "code": res.returncode, "message": res.stderr})
        save_state(state)
        subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return 1
        
    try:
        telemetria = json.loads(res.stdout)
    except json.JSONDecodeError as e:
        print_err(f"Error al decodificar JSON de telemetría: {str(e)}")
        state["steps_failed"].append({"step": 1, "script": "env_diagnostic.py", "code": 1, "message": "JSON inválido"})
        save_state(state)
        subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return 1
        
    print_ok("Telemetría obtenida con éxito.")
    state["current_step"] = 1
    state["steps_completed"].append({
        "step": 1, "script": "env_diagnostic.py", "status": "ok"
    })
    state["context"]["telemetria"] = telemetria
    state["last_updated"] = now_iso()
    save_state(state)
    
    # ══ PASO 2: Generar LaTeX del informe ═════════════════════════════════════
    print_step(2, total_pasos, "Generando archivo LaTeX del reporte...")
    fecha_str = datetime.now().strftime("%d de %B de %Y a las %H:%M")
    
    try:
        latex_code = generar_latex_reporte(telemetria, fecha_str)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_tex.write_text(latex_code, encoding="utf-8")
        print_ok(f"Reporte LaTeX escrito en: {output_tex}")
        
        state["current_step"] = 2
        state["steps_completed"].append({
            "step": 2, "script": "generar_latex_reporte", "status": "ok",
            "archivo_tex": str(output_tex)
        })
        state["context"]["archivo_tex"] = str(output_tex)
        state["last_updated"] = now_iso()
        save_state(state)
    except Exception as e:
        print_err(f"Fallo al generar archivo LaTeX: {str(e)}")
        state["steps_failed"].append({"step": 2, "script": "generar_latex_reporte", "code": 1, "message": str(e)})
        save_state(state)
        subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return 1
        
    # ══ PASO 3: Compilar LaTeX a PDF ══════════════════════════════════════════
    print_step(3, total_pasos, "Compilando reporte LaTeX a PDF...")
    
    informe_pdf = "N/A"
    try:
        from execution.compile_latex import compile_latex_code
        
        job_name = output_tex.stem
        output_parent = str(output_tex.parent.resolve())
        
        comp_res = compile_latex_code(latex_code, job_name=job_name, output_dir=output_parent)
        
        if comp_res["success"]:
            informe_pdf = Path(comp_res["pdf_path"])
            print_ok(f"Reporte PDF generado: {informe_pdf}")
            
            state["current_step"] = 3
            state["steps_completed"].append({
                "step": 3, "script": "compile_latex.py", "status": "ok",
                "archivo_pdf": str(informe_pdf)
            })
            state["context"]["archivo_pdf"] = str(informe_pdf)
            state["last_updated"] = now_iso()
            save_state(state)
        else:
            err_msg = comp_res.get("error", "Error desconocido en pdflatex")
            print_err(f"Falló la compilación del reporte PDF: {err_msg}")
            state["steps_failed"].append({
                "step": 3, "script": "compile_latex.py", "code": 1, "message": err_msg
            })
            save_state(state)
            subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
            return 1
    except Exception as e:
        print_err(f"Error crítico al compilar reporte PDF: {str(e)}")
        state["steps_failed"].append({"step": 3, "script": "compile_latex.py", "code": 1, "message": str(e)})
        save_state(state)
        subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return 1
        
    # ══ PASO 4: Notificación Acústica ═════════════════════════════════════════
    print_step(4, total_pasos, "Notificando al usuario...")
    subprocess.run([PYTHON, str(ALERTAR), "success"], capture_output=True)
    print_ok("Alerta acústica emitida con éxito.")
    
    state["current_step"] = 4
    state["steps_completed"].append({
        "step": 4, "script": "alert_user.py", "status": "ok", "tipo": "success"
    })
    state["last_updated"] = now_iso()
    save_state(state)
    
    # ══ RESUMEN FINAL ═════════════════════════════════════════════════════════
    ram_data = telemetria.get("hardware", {}).get("ram", {})
    disk_data = telemetria.get("hardware", {}).get("disk", {})
    
    bar = "═" * 56
    print(f"\n{bar}")
    print("  FLUJO COMPLETADO — Diagnóstico de Sistema")
    print(f"{bar}")
    print(f"  Hostname          : {telemetria.get('core', {}).get('hostname', 'N/A')}")
    print(f"  Procesador        : {telemetria.get('hardware', {}).get('cpu_model', 'N/A')}")
    print(f"  RAM Total / Libre : {ram_data.get('total_gb', 0)} GB / {ram_data.get('available_gb', 0)} GB")
    print(f"  Disco Total/Libre : {disk_data.get('total_gb', 0)} GB / {disk_data.get('free_gb', 0)} GB")
    print(f"  Reporte PDF       : {informe_pdf}")
    print(f"  Reporte LaTeX     : {output_tex}")
    print(f"{bar}\n")
    
    return 0

def main():
    parser = argparse.ArgumentParser(description="Flujo de Diagnóstico de Sistema con compilación LaTeX.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUT), help="Directorio donde guardar el PDF final.")
    parser.add_argument("--filename", default="informe_diagnostico", help="Nombre del archivo del informe (sin extensión).")
    
    args = parser.parse_args()
    
    out_dir = Path(args.output_dir).resolve()
    
    print(f"\n{'═'*56}")
    print("  ELECTRÓNICA — Flujo de Diagnóstico de Sistema")
    print(f"{'═'*56}")
    print(f"  Directiva : diagnostico_mcp.yaml")
    print(f"  Salida    : {out_dir}")
    print(f"  Archivo   : {args.filename}")
    print(f"{'═'*56}")
    
    code = flujo_completo(out_dir, args.filename)
    sys.exit(code)

if __name__ == "__main__":
    main()
