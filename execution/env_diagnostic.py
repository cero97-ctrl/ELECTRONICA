#!/usr/bin/env python3
import sys
import json
import os
import platform
import subprocess

def get_conda_env():
    return os.environ.get("CONDA_DEFAULT_ENV", "N/A")

def get_python_version():
    return platform.python_version()

def get_ram_info():
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "total_gb": round(mem.total / (1024**3), 2),
            "available_gb": round(mem.available / (1024**3), 2),
            "percent_used": mem.percent
        }
    except ImportError:
        return {"error": "psutil no instalado. Instale usando pip install psutil."}

def main():
    diagnostic = {
        "core": {
            "os": platform.system(),
            "release": platform.release(),
            "architecture": platform.machine(),
            "python_version": get_python_version(),
            "conda_env": get_conda_env(),
            "encoding": sys.getdefaultencoding()
        },
        "hardware": {
            "cpu_cores": os.cpu_count(),
            "ram": get_ram_info()
        },
        "network": {
            "git_installed": bool(subprocess.run(["which", "git"], capture_output=True).stdout),
            "curl_installed": bool(subprocess.run(["which", "curl"], capture_output=True).stdout)
        }
    }
    
    print(json.dumps(diagnostic, indent=2))
    sys.exit(0)

if __name__ == "__main__":
    main()
