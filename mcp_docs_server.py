#!/usr/bin/env python3
"""
mcp_docs_server.py — Docs Reference Server (FastMCP)

Servidor MCP que expone la consulta de documentación oficial vigente de tecnologías
de desarrollo como herramienta. Ejecuta flujo_consultar_docs.py (directiva
consultar_docs_mcp.yaml) y devuelve la documentación Markdown obtenida.

Uso:
    python3 mcp_docs_server.py
    npx @modelcontextprotocol/inspector python3 mcp_docs_server.py
"""

import json
import os
import subprocess
import sys
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

project_root = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(project_root, ".env"))

mcp = FastMCP("Docs Reference Server")


@mcp.tool()
def consultar_docs_recientes(
    tecnologia: str,
    topic: str = None,
    url: str = None,
    max_chars: int = 200000,
) -> str:
    """
    Consulta la documentación oficial vigente de una tecnología y la devuelve como Markdown.

    El servidor obtiene la documentación más reciente directamente de la fuente oficial
    (con caché de 24 horas), evitando quedar desactualizado respecto a APIs nuevas.
    El contenido se guarda en .tmp/docs_cache/<tecnologia>.md y se devuelve un resumen
    con la ruta absoluta, el título, la fuente y el tamaño.

    Args:
        tecnologia: Nombre de la tecnología (p.ej. nextjs, supabase, expo, react,
                    langchain, openai, fastapi, flask, esp-idf). Usa --list en
                    flujo para ver todas.
        topic: Sub-ruta o tema opcional dentro de la documentación.
        url: URL directa de documentación (alternativa a tecnologia).
        max_chars: Truncar el contenido a N caracteres (default: 200000).

    Returns:
        Un reporte estructurado con la ruta del archivo Markdown, título, fuente,
        tamaño y las primeras líneas del contenido consultado.
    """
    if not tecnologia and not url:
        return "Error: Debe indicarse 'tecnologia' o 'url'."

    flujo_script = os.path.join(project_root, "flujo_consultar_docs.py")
    python_exe = sys.executable

    cmd = [python_exe, flujo_script]
    if tecnologia:
        cmd.append(tecnologia)
    if url:
        cmd += ["--url", url]
    if topic:
        cmd += ["--topic", topic]
    cmd += ["--max-chars", str(max_chars)]

    print(f"Ejecutando consulta de documentación: {' '.join(cmd)}")

    state_file = os.path.join(project_root, ".tmp", "run_state.json")
    mtime_before = os.path.getmtime(state_file) if os.path.exists(state_file) else None
    try:
        resultado = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", cwd=project_root
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
            ctx = state_data.get("context", {})
            archivo = ctx.get("archivo", "N/A")
            title = ctx.get("title", "N/A")
            chars = ctx.get("chars", "N/A")
            url_final = ctx.get("url_final", "N/A")
            cached = ctx.get("cached", False)

            preview = ""
            if archivo and os.path.exists(archivo):
                with open(archivo, "r", encoding="utf-8") as f:
                    preview = f.read(800)
                    if os.path.getsize(archivo) > 800:
                        preview += "\n…"

            res_str = (
                f"✅ Documentación consultada exitosamente.\n\n"
                f"--- DOCUMENTACIÓN: {tecnologia or url} ---\n"
                f"• Título      : {title}\n"
                f"• Fuente      : {url_final}\n"
                f"• Caracteres  : {chars}\n"
                f"• Archivo     : {archivo}\n"
                f"• Caché 24h   : {'sí' if cached else 'no'}\n\n"
                f"--- PREVIEW (primeras líneas) ---\n{preview}\n\n"
                f"Para leer el contenido completo, abre el archivo Markdown indicado."
            )
            return res_str

        stdout_snippet = resultado.stdout[-1500:] if len(resultado.stdout) > 1500 else resultado.stdout
        stderr_snippet = resultado.stderr[-1500:] if len(resultado.stderr) > 1500 else resultado.stderr
        res_str = (
            f"❌ El flujo de consulta de documentación falló con código {resultado.returncode}.\n\n"
            f"--- STDERR ---\n{stderr_snippet}\n\n"
            f"--- STDOUT ---\n{stdout_snippet}"
        )
        return res_str

    except Exception as e:
        return f"Error crítico al orquestar la ejecución del flujo: {str(e)}"


if __name__ == "__main__":
    mcp.run()