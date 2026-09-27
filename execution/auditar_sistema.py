"""Capa 3 de `flujo_auditar_sistema.py`: MEDIR el sistema, solo lectura.

Este script NO decide si el sistema esta bien. Solo produce hechos contables: si
eliese el estado aqui, dos auditorias con umbrales distintos darian veredictos
distintos para la misma maquina y la reproducibilidad se perderia en la capa
equivocada. Los umbrales y el estado viven en el interprete de la capa 2
(`flujo_auditar_sistema.py`); aqui solo hay medicion.

Igual que en el resto de capa 3 del repo: entradas por CLI, salida por stdout
como JSON, codigos de salida categorizados, y cero escrituras. No se toca nada,
no se purga nada y no se necesita sudo. Todo lo que se lee es de `/proc`,
`/sys` o de `systemctl show` (que es consulta, no accion).

Mediciones y su trampa documentada:

- `medir_memoria`      RAM: `MemAvailable`, no `MemFree`. La diferencia es que
                       `MemFree` ignora la cache recuperable y en un escritorio
                       con escritorio abierto puede dar un 3% con la RAM
                       medio ocupada; `MemAvailable` es la que el kernel calcula
                       para "cuanto puedes pedir sin swap".
- `medir_intercambio`  SEPARA zram de swap en disco, y no es cosmetico. zram
                       lleno es su estado de diseno: es RAM comprimida, y "usado"
                       ahi no significa presion de memoria. Swap en disco lleno
                       si significa, porque cada pagina ha vuelto al almacenamiento lento. Juntarlos produce una falsa alarma
                       en un 92% de zram y un falso verde si se promedia.
- `medir_cpu`          load normalizado por nucleos (un load de 2 en 2 nucleos es
                       saturacion, en 16 es ocioso) mas `steal`, que delata una
                       VM limitada por el anfitrion y no se arregla desde dentro.
- `medir_servicios`    `LoadState` distingue "no instalado" de "fallido", que es
                       la distincion honesta: lo primero es `no_verificado`, lo
                       segundo es `fallo`.
- `medir_aceleracion`  un informe de sistema que no dice si hay GPU hace que
                       alguien intente entrenar aqui. La ausencia de GPU
                       discreta es un HECHO del entorno, no un defecto: se
                       registra con estado `ok` y la nota de que el
                       entrenamiento va a Colab.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Servicios que este repo declara y mantiene. Viven en AGENTS.md y en
# manage_bot.sh / manage_waydroid.sh. No es la lista de todo systemd: auditar
# las 300 unidades del sistema operativo no es el trabajo de este flujo, y
# avisar de unidades ajenas convertira el informe en ruido.
SERVICIOS_REPO = ("telegram_gateway.service", "waydroid-container.service")

PROC = Path("/proc")
SYS = Path("/sys")


def _error(message: str, code: int) -> int:
    """Error a stderr, codigo categorizado, y no se sigue."""
    print(json.dumps({"status": "error", "code": code, "message": message},
                     ensure_ascii=False, indent=2), file=sys.stderr)
    return code


# ---------------------------------------------------------------------------
# Memoria
# ---------------------------------------------------------------------------

def _leer_meminfo() -> dict[str, int] | None:
    """Parsea /proc/meminfo en kB. None si el fichero no esta o no se entiende."""
    ruta = PROC / "meminfo"
    if not ruta.is_file():
        return None
    valores: dict[str, int] = {}
    try:
        for linea in ruta.read_text(encoding="utf-8", errors="replace").splitlines():
            clave, _, resto = linea.partition(":")
            campos = resto.split()
            if not campos:
                continue
            try:
                valores[clave.strip()] = int(campos[0])
            except ValueError:
                # Campos como "HugePages_Total" no, pero si unidades compostas
                # ("kB" con decimales). Un valor no numerico se salta, no tumba.
                continue
    except OSError:
        return None
    return valores


def medir_memoria() -> dict[str, Any]:
    """RAM total, disponible y porcentaje usado. `no_medible` si falta la fuente."""
    m = _leer_meminfo()
    if m is None:
        return {"no_medible": "/proc/meminfo ausente o ilegible"}
    total = m.get("MemTotal")
    disponible = m.get("MemAvailable")
    if not total:
        return {"no_medible": "/proc/meminfo sin MemTotal"}
    if disponible is None:
        # Sin MemAvailable no se puede decir cuanto se puede pedir sin swap, y
        # estimarlo con MemFree daria un numero con apariencia de medido.
        return {"no_medible": "/proc/meminfo sin MemAvailable (kernel antiguo?)"}
    libre = m.get("MemFree", 0)
    swap_total = m.get("SwapTotal", 0)
    swap_libre = m.get("SwapFree", 0)
    return {
        "total_kb": total,
        "disponible_kb": disponible,
        "usado_pct": round(100.0 * (1.0 - disponible / total), 1),
        # Contexto, no veredicto: la cache recuperable explica por que
        # disponible >> libre sin que haya un problema.
        "libre_kb": libre,
        "cache_recuperable_kb": max(0, libre - m.get("Cached", 0) + m.get("Cached", 0)),
        "swap_total_kb": swap_total,
        "swap_usado_kb": max(0, swap_total - swap_libre),
    }


# ---------------------------------------------------------------------------
# Intercambio: zram y swap en disco, por separado
# ---------------------------------------------------------------------------

def _leer_swaps() -> list[dict[str, Any]] | None:
    """Filas de /proc/swaps. None si el fichero no esta."""
    ruta = PROC / "swaps"
    if not ruta.is_file():
        return None
    filas: list[dict[str, Any]] = []
    try:
        lineas = ruta.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for linea in lineas[1:]:  # la primera es la cabecera
        campos = linea.split()
        if len(campos) < 4:
            continue
        try:
            filas.append({
                "nombre": campos[0],
                "tipo": campos[1],
                "tamaño_kb": int(campos[2]),
                "usado_kb": int(campos[3]),
            })
        except ValueError:
            continue
    return filas


def _zram_indices() -> list[str]:
    """Indices de /sys/block/zram*, ordenados numericamente."""
    if not SYS.joinpath("block").is_dir():
        return []
    encontrados: list[int] = []
    for entrada in SYS.joinpath("block").iterdir():
        if entrada.name.startswith("zram") and entrada.name[4:].isdigit():
            encontrados.append(int(entrada.name[4:]))
    return [f"zram{i}" for i in sorted(encontrados)]


def _zram_compresion(indice: str) -> dict[str, Any]:
    """Razon de compresion de un zram, si se puede leer. Contexto, no veredicto.

    `mm_stat` lleva: orig_data_size, compr_data_size, mem_used_total,
    mem_limit, mem_used_max, same_pages, compacted_pages, huge_pages.
    """
    base = SYS / "block" / indice
    stats: dict[str, Any] = {}
    mm = base / "mm_stat"
    if mm.is_file():
        try:
            partes = mm.read_text(encoding="utf-8", errors="replace").split()
            if len(partes) >= 2:
                orig, compr = int(partes[0]), int(partes[1])
                if compr > 0:
                    stats["bytes_originales"] = orig
                    stats["bytes_comprimidos"] = compr
                    stats["razon_compresion"] = round(orig / compr, 2)
        except (OSError, ValueError):
            pass
    algoritmo = base / "comp_algorithm"
    if algoritmo.is_file():
        try:
            texto = algoritmo.read_text(encoding="utf-8", errors="replace")
            stats["algoritmo_activo"] = texto.strip("[] \n")
        except OSError:
            pass
    return stats


def medir_intercambio() -> dict[str, Any]:
    """zram y swap en disco, medidos y SEPARADOS.

    El campo `zram_lleno_es_normal` va explicito porque es la fuente de la falsa
    alarma mas comun en maquinas con zram: un zram al 92% es su estado de
    diseno, no una presion de memoria.
    """
    filas = _leer_swaps()
    if filas is None:
        return {"no_medible": "/proc/swaps ausente o ilegible"}

    zram: dict[str, Any] = {"presente": False, "usado_pct": 0.0, "usado_kb": 0,
                           "total_kb": 0, "dispositivos": []}
    disco: dict[str, Any] = {"usado_pct": 0.0, "usado_kb": 0, "total_kb": 0,
                            "dispositivos": []}
    for f in filas:
        nombre, total, usado = f["nombre"], f["tamaño_kb"], f["usado_kb"]
        usado_pct = round(100.0 * usado / total, 1) if total else 0.0
        if "zram" in nombre or f["tipo"] == "partition" and nombre.startswith("/dev/zram"):
            zram["presente"] = True
            zram["total_kb"] += total
            zram["usado_kb"] += usado
            zram["dispositivos"].append(
                {"nombre": nombre, "usado_pct": usado_pct, "usado_kb": usado,
                 "total_kb": total, **_zram_compresion(
                     nombre.rsplit("/", 1)[-1] if "/" in nombre else "")})
        else:
            disco["total_kb"] += total
            disco["usado_kb"] += usado
            disco["dispositivos"].append(
                {"nombre": nombre, "tipo": f["tipo"], "usado_pct": usado_pct,
                 "usado_kb": usado, "total_kb": total})

    if disco["total_kb"]:
        disco["usado_pct"] = round(100.0 * disco["usado_kb"] / disco["total_kb"], 1)
    if zram["total_kb"]:
        zram["usado_pct"] = round(100.0 * zram["usado_kb"] / zram["total_kb"], 1)
    zram["zram_lleno_es_normal"] = True
    zram["nota"] = (
        "zram es RAM comprimida: su llenado es el estado de diseno y NO es "
        "presion de memoria. El ratio de compresion es lo que demuestra lo que "
        "ocurre por dentro. Solo el swap en disco de abajo indica presion real."
    )
    return {
        "zram": zram,
        "swap_disco": disco,
        "indices_zram_detectados": _zram_indices(),
    }


# ---------------------------------------------------------------------------
# CPU
# ---------------------------------------------------------------------------

def _leer_psi(recurso: str) -> dict[str, Any] | None:
    """PSI de /proc/pressure. None si el kernel no lo expone (needs CONFIG_PSI)."""
    ruta = PROC / "pressure" / recurso
    if not ruta.is_file():
        return None
    # /proc/pressure trae DOS filas por recurso: `some` (alguna tarea parada) y
    # `full` (todas paradas). Se guardan por separado y sin mixing: una version
    # anterior usaba claves planas, asi que la fila `full` (suele ir a 0)
    # pisaba a `some` y la presion de CPU se reportaba como 0.0 siendo 33.09.
    # Subestimar la presion es peor que no medirla.
    out: dict[str, dict[str, float]] = {"some": {}, "full": {}}
    try:
        texto = ruta.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for linea in texto.splitlines():
        partes = linea.split()
        if len(partes) < 2 or partes[0] not in out:
            continue
        fila = out[partes[0]]
        for token in partes[1:]:
            clave, sep, valor = token.partition("=")
            if not sep:
                continue
            try:
                fila[clave] = float(valor)
            except ValueError:
                continue
    vacio = all(not v for v in out.values())
    return None if vacio else out


def _psi_some(psi: dict[str, Any] | None) -> float | None:
    """PSI `some` de un recurso. `some` y no `full`: `full` solo mide cuando
    TODAS las tareas estan paradas, y para saber si el equipo va tirado lo que
    cuenta es que alguna lo este."""
    if not psi:
        return None
    fila = psi.get("some") or {}
    return fila.get("avg60")


def medir_cpu() -> dict[str, Any]:
    """Carga normalizada por nucleos, `steal` y presion PSI. Contables, sin veredicto."""
    loadavg: list[float] = []
    carga = PROC / "loadavg"
    if carga.is_file():
        try:
            campos = carga.read_text(encoding="utf-8").split()
            loadavg = [float(c) for c in campos[:3]]
        except (OSError, ValueError):
            loadavg = []
    nucleos = os.cpu_count() or 0

    # /proc/stat: user nice system idle iowait irq softirq steal guest guest_nice
    steal_pct = None
    stat = PROC / "stat"
    if stat.is_file():
        try:
            primera = stat.read_text(encoding="utf-8").splitlines()[0]
            if primera.startswith("cpu "):
                t = [int(x) for x in primera.split()[1:]]
                if len(t) >= 8:
                    total = sum(t)
                    # guest ya va incluido en user y no debe contarse dos veces
                    total -= t[8] if len(t) >= 9 else 0
                    if total > 0:
                        steal_pct = round(100.0 * t[7] / total, 2)
        except (OSError, ValueError, IndexError):
            steal_pct = None

    d: dict[str, Any] = {
        "nucleos": nucleos,
        "loadavg": loadavg,
        "steal_pct": steal_pct,
        "psi_cpu": _leer_psi("cpu"),
        "psi_io": _leer_psi("io"),
    }
    if nucleos and len(loadavg) == 3:
        d["load_por_nucleo"] = [round(v / nucleos, 2) for v in loadavg]
    else:
        d["load_por_nucleo"] = None
    if not loadavg or not nucleos:
        d["no_medible"] = "loadavg o numero de nucleos no disponible"
    return d


# ---------------------------------------------------------------------------
# Servicios
# ---------------------------------------------------------------------------

def medir_servicios(unidades: tuple[str, ...] = SERVICIOS_REPO) -> dict[str, Any]:
    """Estado de los servicios del repo. `LoadState` separa no-instalado de fallido."""
    if not shutil_which_systemctl():
        return {"no_medible": "systemctl no disponible: no se puede consultar el estado"}
    try:
        proc = subprocess.run(
            ["systemctl", "show", *unidades, "-p", "Id", "-p", "LoadState",
             "-p", "ActiveState", "-p", "SubState"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"no_medible": f"systemctl show fallo: {type(exc).__name__}"}
    if proc.returncode != 0:
        return {"no_medible": f"systemctl show devolvio {proc.returncode}: "
                              f"{proc.stderr.strip()[:120] or 'sin detalle'}"}

    # `systemctl show` separa cada unidad con una linea en blanco.
    servicios: list[dict[str, Any]] = []
    actual: dict[str, str] = {}
    for linea in proc.stdout.splitlines() + [""]:
        if not linea.strip():
            if actual:
                servicios.append(actual)
                actual = {}
            continue
        clave, _, valor = linea.partition("=")
        actual[clave.strip()] = valor.strip()
    return {
        "servicios": servicios,
        "consulta": "systemctl show (solo lectura)",
    }


def shutil_which_systemctl() -> bool:
    """True si systemctl esta en el PATH. Wrapper para poder simularlo en tests."""
    import shutil
    return shutil.which("systemctl") is not None


# ---------------------------------------------------------------------------
# Aceleracion
# ---------------------------------------------------------------------------

def medir_aceleracion() -> dict[str, Any]:
    """Deteccion de GPU. Hecho del entorno, NO un defecto del sistema."""
    d: dict[str, Any] = {"gpu_discreta": False, "modelos": [],
                         "aceleracion_por_defecto": False}
    try:
        hay_nvidia = subprocess.run(
            ["nvidia-smi", "-L"], capture_output=True, text=True, timeout=15,
        )
        if hay_nvidia.returncode == 0 and hay_nvidia.stdout.strip():
            d["gpu_discreta"] = True
            d["modelos"].extend(
                x.strip() for x in hay_nvidia.stdout.splitlines() if x.strip())
    except (OSError, subprocess.SubprocessError):
        pass  # nvidia-smi no existe: es lo normal en una maquina sin NVIDIA

    import shutil
    if shutil.which("lspci"):
        try:
            lspci = subprocess.run(
                ["lspci"], capture_output=True, text=True, timeout=20,
            )
            for linea in lspci.stdout.splitlines():
                bajo = linea.lower()
                if "vga" in bajo or "3d controller" in bajo or "display" in bajo:
                    d["modelos"].append(linea.split(":", 2)[-1].strip())
        except (OSError, subprocess.SubprocessError):
            pass
    d["entrenamiento_local_posible"] = d["gpu_discreta"]
    d["nota"] = (
        "Sin GPU discreta el entrenamiento de modelos va a Google Colab con "
        "TensorFlow. En esta maquina solo es legitimo: inferencia, prototipos y "
        "validacion. Con GPU, ademas, puede fallar por falta de RAM, no de VRAM."
    )
    return d


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def medir_todo() -> dict[str, Any]:
    """Todas las mediciones crudas. Sin umbrales, sin estados, sin accion."""
    return {
        "memoria": medir_memoria(),
        "intercambio": medir_intercambio(),
        "cpu": medir_cpu(),
        "servicios": medir_servicios(),
        "aceleracion": medir_aceleracion(),
    }


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Mide RAM, intercambio, CPU, servicios y aceleracion. Solo lectura.",
    )
    p.add_argument("--json", action="store_true",
                   help="salida completa en JSON (por defecto si no hay subcomando)")
    return p


def main(argv: list[str] | None = None) -> int:
    construir_parser().parse_args(argv)
    datos = medir_todo()
    if not isinstance(datos, dict):  # guardia de contrato, no deberia ocurrir
        return _error("medir_todo no devolvio un dict", 5)
    print(json.dumps({"status": "ok", "mediciones": datos}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
