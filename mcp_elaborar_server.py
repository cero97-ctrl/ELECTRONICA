#!/usr/bin/env python3
import os
import sys
import subprocess
import json
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

#: Nombre corto de este servidor: entra en el `run_id` cuando el MCP es el
#: orquestador de la corrida y nadie ha fijado `ELECTRONICA_RUN_ID`.
PREFIX = "elaborar"

# Cargar variables de entorno desde el .env absoluto del proyecto
project_root = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(project_root, ".env"))

# Inicializar el servidor MCP de FastMCP
mcp = FastMCP("Examen Elaborator Server")

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


def elaborar_nuevo_examen(
    tema: str,
    nivel: str = "intermedia",
    modelo: str = "anthropic/claude-opus-5",
    api_backend: str = "openrouter",
    output_dir: str = None
) -> str:
    """
    Elabora un examen nuevo y su solucionario (PDF y LaTeX) sobre un tema de electrónica.
    
    Esta herramienta genera un examen completo de 5 preguntas de razonamiento y cálculo,
    crea los documentos LaTeX correspondientes, y compila de forma automática tanto el
    examen como el solucionario a PDF, emitiendo una alerta sonora de completado.
    
    Args:
        tema: El tema específico de electrónica (ej: "Semana 2: Diodos y Rectificadores", "Transistor BJT").
        nivel: Dificultad del examen: 'basica', 'intermedia' o 'avanzada' (default: intermedia).
        modelo: Nombre del modelo a usar (default: anthropic/claude-opus-5 para tareas complejas).
        api_backend: Backend de API a usar: 'gemini', 'groq' o 'openrouter' (default: openrouter).
        output_dir: Directorio opcional donde guardar el examen y solucionario (default: examenes/).
        
    Returns:
        Un reporte estructurado con las rutas absolutas de los PDFs del examen y solucionario
        generados, el título del examen y el registro de la ejecución.
    """
    if not tema.strip():
        return "Error: El tema no puede estar vacío."
        
    project_root = os.path.dirname(os.path.abspath(__file__))
    flujo_script = os.path.join(project_root, "flujo_elaborar_examen.py")
    python_exe = sys.executable  # Usa el mismo python del servidor MCP
    
    # Resolver directorio de salida
    if not output_dir:
        # Carpeta por defecto
        dest_dir = os.path.join(project_root, "examenes")
    else:
        dest_dir = os.path.abspath(output_dir)
        
    os.makedirs(dest_dir, exist_ok=True)
    
    # Construir el comando para ejecutar flujo_elaborar_examen.py
    cmd = [
        python_exe,
        flujo_script,
        "--tema", tema,
        "--nivel", nivel,
        "--modelo", modelo,
        "--api-backend", api_backend,
        "--output", dest_dir
    ]
    
    print(f"Ejecutando elaboración de examen: {' '.join(cmd)}")
    
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
            titulo = state_data.get("context", {}).get("titulo", "N/A")
            n_preguntas = state_data.get("context", {}).get("n_preguntas", "5")
            
            # Recuperar rutas de PDFs del estado
            examen_pdf = state_data.get("context", {}).get("examen_pdf", "N/A")
            solucionario_pdf = state_data.get("context", {}).get("solucionario_pdf", "N/A")
            
            # Recuperar JSON de evaluación generado en .tmp/
            json_tmp = ""
            for step in state_data.get("steps_completed", []):
                if step.get("step") == 1:
                    json_tmp = step.get("json_tmp", "")
                    
            res_str = (
                f"✅ ¡Examen Elaborado y Compilado Exitosamente!\n\n"
                f"--- DETALLES DEL EXAMEN ---\n"
                f"• Título    : {titulo}\n"
                f"• Preguntas : {n_preguntas}\n"
                f"• Dificultad: {nivel.capitalize()}\n"
                f"• Tema      : {tema}\n\n"
                f"--- ARCHIVOS PDF GENERADOS ---\n"
                f"• Examen PDF      : {examen_pdf}\n"
                f"• Solucionario PDF: {solucionario_pdf}\n\n"
                f"--- ARCHIVOS FUENTE ---\n"
                f"• JSON del examen : {json_tmp}\n\n"
                f"¡Los documentos han sido compilados automáticamente y están listos para imprimir!"
            )
            return res_str
        else:
            stdout_snippet = resultado.stdout[-1500:] if len(resultado.stdout) > 1500 else resultado.stdout
            stderr_snippet = resultado.stderr[-1500:] if len(resultado.stderr) > 1500 else resultado.stderr
            
            res_str = (
                f"❌ El flujo de elaboración de examen falló con código de salida {resultado.returncode}.\n\n"
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
