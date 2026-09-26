#!/usr/bin/env python3
import sys
import json
import os
import platform
import subprocess
import shlex
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
            "free_gb": round(mem.free / (1024**3), 2),
            "percent_used": mem.percent,
            "fuente": "psutil"
        }
    except ImportError:
        pass
    # Fallback manual en Linux leyendo /proc/meminfo.
    # OJO: hay que usar MemAvailable, NO MemFree. En Linux el "libre" excluye
    # buff/cache, que el kernel puede devolver en cualquier momento; MemAvailable es
    # la cifra de memoria realmente asignable. Confundirlas daba 0.15 GB de
    # "disponible" cuando habia 1.4 GB, y un 95.9% de uso falso. Con un limite
    # estricto de RAM en el proyecto, ese dato hacia abortar tareas sin motivo.
    # El parseo es por clave exacta: antes un "if not mem_free # priorizar
    # MemAvailable"tomaba MemFree porque en /proc/meminfo aparece ANTES que
    # MemAvailable, asi que la guarda se cumplia con el campo equivocado.
    try:
        with open("/proc/meminfo", "r") as f:
            claves = {}
            for line in f:
                partes = line.split()
                if len(partes) >= 2 and partes[0].endswith(":"):
                    claves[partes[0][:-1]] = int(partes[1]) * 1024
        total = claves.get("MemTotal", 0)
        # available = free + buffers + cache (lo que el kernel puede concedes sin swap)
        disponible = claves.get("MemAvailable", 0)
        if not disponible:
            disponible = (claves.get("MemFree", 0) + claves.get("Buffers", 0)
                          + claves.get("Cached", 0))
        if not total:
            raise ValueError("MemTotal ausente en /proc/meminfo")
        return {
            "total_gb": round(total / (1024**3), 2),
            "available_gb": round(disponible / (1024**3), 2),
            "free_gb": round(claves.get("MemFree", 0) / (1024**3), 2),
            "percent_used": round(((total - disponible) / total) * 100, 1),
            "fuente": "proc_meminfo"
        }
    except (OSError, ValueError, IndexError):
        return {"error": "no se pudo leer la RAM (psutil ausente y /proc/meminfo ilegible)"}

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

def get_board_info():
    """Placa base y BIOS via DMI de sysfs (sin sudo, sin dmidecode).

    dmidecode requiere root, asi que se leen los ficheros de
    /sys/devices/virtual/dmi/id/, que suelen ser 444. En maquinas virtuales o
   ylon confines DMI no existe: se devuelve disponible=False en vez de fallar.
    """
    base = "/sys/devices/virtual/dmi/id"
    campos = {
        "placa_fabricante": "board_vendor",
        "placa_modelo": "board_name",
        "placa_version": "board_version",
        "bios_fabricante": "bios_vendor",
        "bios_version": "bios_version",
        "bios_fecha": "bios_date",
    }
    info = {}
    for destino, origen in campos.items():
        ruta = os.path.join(base, origen)
        try:
            with open(ruta, "r") as f:
                valor = f.read().strip()
            if valor:
                info[destino] = valor
        except (OSError, UnicodeDecodeError):
            continue
    if not info:
        return {"disponible": False,
                "motivo": "DMI no expuesto por el kernel (maquina virtual o contenedor)"}
    info["disponible"] = True
    return info


def get_disk_devices():
    """Discos fisicos con modelo y tipo (SSD vs HDD) via lsblk.

    `get_disk_info` solo da totales del sistema de ficheros; esto responde a
    "que disco tengo y es SSD o HDD", que es lo que decide si una copia de
    seguridad o un build va a ser lento. ROTA=1 significa giratorio (HDD).

    Se usa -P (--pairs) y NO un split() ingenuo: MODEL contiene espacios
    ("SAMSUNG MZALQ256HAJD-000L2"), que descuadraban todas las columnas
    siguientes y devolvian tamano_gb=null. Con -P cada campo llega como
    clave="valor" y el modelo con espacios se conserva intacto.
    Se filtra zram: es RAM comprimida, no un disco de almacenamiento.
    """
    lsblk = shutil.which("lsblk")
    if not lsblk:
        return {"disponible": False, "motivo": "lsblk no instalado"}
    try:
        res = subprocess.run(
            [lsblk, "-d", "-b", "-P", "-o", "NAME,MODEL,SIZE,ROTA,TYPE,TRAN"],
            capture_output=True, text=True, check=False)
        if res.returncode != 0:
            return {"disponible": False, "motivo": "lsblk fallo o no permisos"}
        discos = []
        for linea in res.stdout.strip().splitlines():
            if "=" not in linea:
                continue
            campos = {}
            for par in shlex.split(linea):
                if "=" in par:
                    clave, _, valor = par.partition("=")
                    campos[clave] = valor
            nombre = campos.get("NAME", "")
            if not nombre or nombre.startswith("zram") or nombre.startswith("loop"):
                continue
            modelo = campos.get("MODEL", "") or "desconocido"
            try:
                tam_gb = round(int(campos.get("SIZE", "0")) / (1024**3), 1)
            except ValueError:
                tam_gb = None
            discos.append({
                "nombre": nombre,
                "modelo": modelo,
                "tamano_gb": tam_gb,
                # ROTA=0 es SSD/NVMe, ROTA=1 es HDD mecanico
                "tipo": "HDD" if campos.get("ROTA") == "1" else "SSD/NVMe",
                "transporte": campos.get("TRAN") or "desconocido",
                "tipo_nodo": campos.get("TYPE", ""),
            })
        if not discos:
            return {"disponible": False, "motivo": "lsblk no devolvio discos de almacenamiento"}
        return {"disponible": True, "discos": discos}
    except (OSError, subprocess.SubprocessError):
        return {"disponible": False, "motivo": "error ejecutando lsblk"}


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
            "placa": get_board_info(),
            "ram": get_ram_info(),
            "disk": get_disk_info(),
            "dispositivos": get_disk_devices(),
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
