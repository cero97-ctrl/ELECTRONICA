import os
import subprocess

def apagar_equipo():
    """
    Ejecuta el comando para apagar el equipo.
    Utiliza 'sudo' de forma segura ya que el usuario configuró NOPASSWD en visudo
    específicamente para el comando '/usr/bin/systemctl poweroff'.
    """
    try:
        resultado = subprocess.run(["sudo", "systemctl", "poweroff"], capture_output=True, text=True, check=True)
        return {"status": "success", "message": "Comando de apagado enviado exitosamente al sistema."}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": f"Error al intentar apagar el equipo: {e.stderr}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
