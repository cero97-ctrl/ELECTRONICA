#!/usr/bin/env python3
import os
import sys
import subprocess
import json
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

#: Nombre corto de este servidor: entra en el `run_id` cuando el MCP es el
#: orquestador de la corrida y nadie ha fijado `ELECTRONICA_RUN_ID`.
PREFIX = "evaluar"

# Cargar variables de entorno desde el .env absoluto del proyecto
project_root = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(project_root, ".env"))

# Inicializar el servidor MCP de FastMCP
mcp = FastMCP("Examen Evaluator Server")

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
