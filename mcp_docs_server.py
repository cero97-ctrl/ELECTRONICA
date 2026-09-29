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

#: Nombre corto de este servidor: entra en el `run_id` cuando el MCP es el
#: orquestador de la corrida y nadie ha fijado `ELECTRONICA_RUN_ID`.
PREFIX = "docs"

project_root = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(project_root, ".env"))

mcp = FastMCP("Docs Reference Server")


@mcp.tool()
# --- Lectura de la vista por corrida ---------------------------------------
# Todo lo de la vista vive en `execution/run_state.py` (capa 3). Este servidor no
# reimplementa el emparejamiento vista<->log ni el nombre: los usa. Una copia
# del criterio aqui seria una segunda verdad divergiendo en silencio.
def _importar_run_state(project_root: str):
    """Importa el helper de capa 3. `None` si no esta disponible (y se avisa)."""
    ejecucion = os.path.join(project_root, "execution")
    if ejecucion not in sys.path:
        sys.path.insert(0, ejecucion)
    try:
        import run_state  # noqa: E402  (capa 3, resolucion explicita)
        return run_state
    except Exception as exc:  # pragma: no cover
        print(f"aviso: no se pudo importar execution/run_state.py ({exc}); "
              f"el estado del flujo no se reportara", file=sys.stderr)
        return None


def _leer_vista(rs, run_id: str) -> dict:
    """La vista de ESTA corrida, o `{}` si el flujo no llegó a escribir.

    Con el `run_id` fijado por el orquestador la lectura es exacta: no hay que
    deducir cual de las vistas es la nuestra. `{}` significa "el flujo salio
    antes de escribir, o fallo sin llegar" — un estado real que el MCP debe
    reportar como tal, no rellenando con la vista de otra corrida.
    """
    if rs is None or not run_id:
        return {}
    datos = rs.leer_vista(rs.ruta_vista(run_id))
    return datos if isinstance(datos, dict) else {}


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

    # Foto de las vistas ANTES de lanzar el subproceso (capa 3: `run_state.py`).
    # Con un nombre fijo bastaba un `mtime`; con la vista por corrida la
    # pregunta es "¿que vistas escribio ESTA corrida?", y la foto la responde sin
    # depender de un reloj ni de adivinar el nombre del fichero de esta corrida.
    _RS = _importar_run_state(project_root)
    # El MCP es el ORQUESTADOR de esta corrida, asi que le fija el nombre. Sin
    # esto solo puede buscar "la vista nueva mas reciente", y si otra corrida
    # escribe a la vez se atribuye su vista a esta: un fallo silencioso que
    # devuelve el resultado de OTRO flujo con exit code 0.
    _run_id = _RS.run_id_de_la_corrida(f"mcp-{PREFIX}") if _RS else ""
    _entorno = dict(os.environ)
    if _run_id:
        _entorno[_RS.ENV_RUN_ID] = _run_id
    try:
        resultado = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", cwd=project_root
        )

        # Estado final: SOLO la vista que escribio ESTA corrida (nueva o
        # modificada respecto a la foto). Una vista huerfana —el flujo salio
        # antes de escribir, o fallo sin llegar al ultimo save— no se reporta
        # como resultado actual; ver `execution/estado_sesion.py`.
        state_data = _leer_vista(_RS, _run_id)

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