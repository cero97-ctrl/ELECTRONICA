#!/usr/bin/env python3
import sys
import json
import os
import platform
import subprocess
import shutil
import socket

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
        # Fallback manual en Linux leyendo /proc/meminfo
        if os.path.exists("/proc/meminfo"):
            try:
                mem_total = 0
                mem_free = 0
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if "MemTotal" in line:
                            mem_total = int(line.split()[1]) * 1024
                        elif "MemAvailable" in line or "MemFree" in line:
                            if not mem_free: # priorizar MemAvailable
                                mem_free = int(line.split()[1]) * 1024
                return {
                    "total_gb": round(mem_total / (1024**3), 2),
                    "available_gb": round(mem_free / (1024**3), 2),
                    "percent_used": round(((mem_total - mem_free) / mem_total) * 100, 1) if mem_total else 0
                }
            except Exception:
                pass
        return {"error": "psutil no instalado"}

def get_disk_info():
    try:
        total, used, free = shutil.disk_usage("/")
        return {
            "total_gb": round(total / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
            "percent_used": round((used / total) * 100, 1)
        }
    except Exception as e:
        return {"error": str(e)}

def get_cpu_model():
    if platform.system() == "Linux" and os.path.exists("/proc/cpuinfo"):
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        return line.split(":", 1)[1].strip()
        except Exception:
            pass
    return platform.processor() or "Desconocido"

def get_gpu_info():
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            res = subprocess.run([nvidia_smi, "--query-gpu=name,memory.total,memory.free,utilization.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True)
            if res.returncode == 0:
                parts = res.stdout.strip().split("\n")
                gpus = []
                for p in parts:
                    if p.strip():
                        gpu_parts = p.split(",")
                        gpus.append({
                            "name": gpu_parts[0].strip(),
                            "memory_total_mb": float(gpu_parts[1].strip()),
                            "memory_free_mb": float(gpu_parts[2].strip()),
                            "utilization_percent": float(gpu_parts[3].strip())
                        })
                return gpus
        except Exception:
            pass
    return []

def get_system_uptime():
    if os.path.exists("/proc/uptime"):
        try:
            with open("/proc/uptime", "r") as f:
                uptime_seconds = float(f.readline().split()[0])
                uptime_hours = round(uptime_seconds / 3600, 1)
                return f"{uptime_hours} horas"
        except Exception:
            pass
    return "N/A"

def main():
    diagnostic = {
        "core": {
            "os": platform.system(),
            "release": platform.release(),
            "architecture": platform.machine(),
            "hostname": socket.gethostname(),
            "python_version": get_python_version(),
            "conda_env": get_conda_env(),
            "encoding": sys.getdefaultencoding(),
            "uptime": get_system_uptime()
        },
        "hardware": {
            "cpu_model": get_cpu_model(),
            "cpu_cores": os.cpu_count(),
            "ram": get_ram_info(),
            "disk": get_disk_info(),
            "gpus": get_gpu_info()
        },
        "network": {
            "git_installed": bool(shutil.which("git")),
            "curl_installed": bool(shutil.which("curl")),
            "pdflatex_installed": bool(shutil.which("pdflatex"))
        }
    }
    
    print(json.dumps(diagnostic, indent=2))
    sys.exit(0)

if __name__ == "__main__":
    main()
