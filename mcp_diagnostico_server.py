#!/usr/bin/env python3
import os
import sys
import subprocess
import json
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

#: Nombre corto de este servidor: entra en el `run_id` cuando el MCP es el
#: orquestador de la corrida y nadie ha fijado `ELECTRONICA_RUN_ID`.
PREFIX = "diagnostico"

# Cargar variables de entorno desde el .env absoluto del proyecto
project_root = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(project_root, ".env"))

# Inicializar el servidor MCP de FastMCP
mcp = FastMCP("System Diagnostic Server")

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
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=project_root,
            env=_entorno
        )
        
        # Estado final: SOLO la vista que escribio ESTA corrida (nueva o
        # modificada respecto a la foto). Una vista huerfana —el flujo salio
        # antes de escribir, o fallo sin llegar al ultimo save— no se reporta
        # como resultado actual; ver `execution/estado_sesion.py`.
        state_data = _leer_vista(_RS, _run_id)
                
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
