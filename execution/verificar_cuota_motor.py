#!/usr/bin/env python3
"""
execution/verificar_cuota_motor.py — Sonda determinista de cuota del motor orquestador.

Detecta si el motor free de opencode (por defecto opencode/big-pickle) ha agotado su
cuota gratuita lanzando una sonda real: `opencode run -m <modelo> --format json "ping"`.

Clasificación (función pura; misma entrada -> mismo estado):
    ok            — el modelo respondió (cuota disponible)
    agotada       — el error contiene firma de cuota/rate/429/balance (cuota free agotada)
    error_infra   — fallo de infraestructura (modelo inválido, sin red, clave rota): NO conmutar
    indeterminado — sin eventos claros (timeout, salida vacía con error de programa)

Cada sonda consume ~8-9k tokens de la cuota free del motor (system prompt de opencode).
Por eso existe el modo `--pasivo`: escanea opencode.log buscando firmas de cuota ya
reportadas por una sesión TUI en curso, sin gastar tokens (solo informativo).

Salida (stdout): JSON {estado, modelo, retry_en_segundos, detalles, sonda}
Códigos de salida: 0 ok | 1 agotada | 2 error_infra | 3 indeterminado

Uso:
    python3 execution/verificar_cuota_motor.py [--modelo opencode/big-pickle]
        [--timeout 120] [--dir /tmp] [--print-logs]
        [--pasivo] [--log ~/.local/share/opencode/log/opencode.log] [--ventana-min 20]
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Firmas de agotamiento de cuota / rate limit del proveedor (Zen/OpenRouter). Conservador:
# a partir de la primera captura real de un 429 de Zen se afinará (ver directiva edge cases).
_FIRMAS_CUOTA = re.compile(
    r"(?ix)("
    r"429"
    r"|quota"
    r"|rate\s?limit"
    r"|usage\s?limit"
    r"|usage.?exceeded"
    r"|exceeded.*(?:budget|limit|quota)"
    r"|no\s?credits?"
    r"|insufficient"
    r"|balance"
    r"|payment"
    r"|reset.{0,12}(?:in|at)"
    r"|retry.{0,12}(?:after|in)"
    r"|too\s?many\s?request"
    r"|free\s?(?:tier|quota)"
    r")"
)
# Extracción best-effort de la ventana de reset (segundos).
_RETRY_RE = re.compile(
    r"\b(?:reset|retry|resume|after)\b[\s:.-]*(?:in|after|at|of)?[\s:.-]*"
    r"(\d+)\s*(ms|s|sec|secs|second|seconds|min|mins|minute|minutes|h|hrs|hours)?",
    re.IGNORECASE,
)

PROBE_PROMPT = "diag: responde unicamente OK"


def _clasificar_mensaje(mensaje: str) -> bool:
    """True si el mensaje tiene firma sólida de agotamiento de cuota (función pura)."""
    if not mensaje:
        return False
    return bool(_FIRMAS_CUOTA.search(mensaje))


def _extraer_retry(mensaje: str) -> int | None:
    """Devuelve la ventana de reset en segundos si es extraíble; None si no."""
    if not mensaje:
        return None
    # Fechas ISO ("reset at 2026-09-21T18:00:00Z") no son ventana en segundos.
    if re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", mensaje):
        return None
    m = _RETRY_RE.search(mensaje)
    if not m:
        return None
    valor = int(m.group(1))
    unidad = (m.group(2) or "").lower()
    if unidad in ("ms",):
        return valor // 1000
    if unidad in ("min", "mins", "minute", "minutes"):
        return valor * 60
    if unidad in ("h", "hrs", "hours"):
        return valor * 3600
    if unidad in ("", "s", "sec", "secs", "second", "seconds"):
        return valor
    return valor


def _componer_mensaje_error(evento: dict) -> tuple[str, str]:
    """Extrae (mensaje, nombre) del evento {"type":"error",...} de opencode run."""
    err = evento.get("error") or {}
    nombre = err.get("name", "UnknownError")
    data = err.get("data")
    if isinstance(data, str):
        return data, nombre
    if isinstance(data, dict):
        partes = []
        for k, v in data.items():
            if isinstance(v, (dict, list)) is False:
                partes.append(f"{k}={v}")
            else:
                partes.append(f"{k}={json.dumps(v, ensure_ascii=False)}")
        return " | ".join(partes), nombre
    return json.dumps(data, ensure_ascii=False) if data is not None else "", nombre


def sondear(modelo: str, timeout: int, cwd: str, print_logs: bool) -> tuple[str, dict]:
    """Ejecuta la sonda y devuelve (estado, detalles).

    Estado: ok | agotada | error_infra | indeterminado
    """
    cmd = ["opencode", "run", "-m", modelo, "--format", "json", "--dir", cwd]
    if print_logs:
        cmd.append("--print-logs")
    cmd.append(PROBE_PROMPT)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return "indeterminado", {"motivo": "timeout", "timeout_s": timeout}
    except FileNotFoundError:
        return "error_infra", {"motivo": "opencode no encontrado en PATH"}

    stdout = proc.stdout or ""
    stderr = (proc.stderr or "").strip()[-2000:]
    detalles: dict = {"exit": proc.returncode}

    if _clasificar_mensaje(stderr) and proc.returncode != 0:
        return "agotada", {
            "motivo": "stderr con firma de cuota",
            "mensaje": stderr,
            "retry_en_segundos": _extraer_retry(stderr),
        }

    errores = []
    textos = []
    for linea in stdout.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        try:
            ev = json.loads(linea)
        except json.JSONDecodeError:
            continue
        tipo = ev.get("type")
        if tipo == "error":
            mensaje, nombre = _componer_mensaje_error(ev)
            errores.append({"mensaje": mensaje, "nombre": nombre})
        elif tipo == "text":
            textos.append(ev.get("part", {}).get("text", ""))

    if errores:
        ultimo = errores[-1]
        mensaje = ultimo["mensaje"]
        detalles["error"] = ultimo
        if _clasificar_mensaje(mensaje):
            return ("agotada", {
                **detalles,
                "motivo": "evento error con firma de cuota",
                "mensaje": mensaje,
                "retry_en_segundos": _extraer_retry(mensaje),
            })
        return "error_infra", {**detalles, "motivo": "evento error sin firma de cuota"}

    if textos and textos[-1].strip():
        return "ok", {**detalles, "respuesta": textos[-1][:120]}

    if proc.returncode == 0 and not stdout.strip():
        # Sin salida pero exit 0: respuesta vacía -> no se confirma cuota.
        return "indeterminado", {**detalles, "motivo": "salida vacía con exit 0"}

    return "indeterminado", {**detalles, "motivo": "sin eventos JSON reconocidos",
                             "stderr": stderr}


def _escanear_log_pasivo(log: Path, ventana_min: int) -> dict:
    """Escaneo pasivo (0 tokens): busca firmas de cuota en las últimas líneas del log."""
    if not log.is_file():
        return {"estado": "indeterminado", "motivo": f"log no encontrado: {log}"}
    try:
        chunk = log.read_bytes()[-2_000_000:].decode("utf-8", errors="replace")
    except OSError as e:
        return {"estado": "indeterminado", "motivo": str(e)}

    coincidencias = []
    for num, linea in enumerate(chunk.splitlines()):
        if _clasificar_mensaje(linea):
            coincidencias.append(linea[:400])

    if not coincidencias:
        return {"estado": "ok", "motivo": "sin firmas de cuota en la ventana"}
    ultima = coincidencias[-1]
    return {
        "estado": "agotada" if len(coincidencias) >= 2 else "indeterminado",
        "motivo": f"{len(coincidencias)} líneas con firma de cuota",
        "retry_en_segundos": _extraer_retry(ultima),
        "muestra": ultima,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sonda determinista de cuota del motor.")
    parser.add_argument("--modelo", default="opencode/big-pickle",
                        help="Modelo free del motor a sondear.")
    parser.add_argument("--timeout", type=int, default=120,
                        help="Timeout de la sonda en segundos.")
    parser.add_argument("--dir", default="/tmp",
                        help="Directorio de trabajo de la sonda (debe existir).")
    parser.add_argument("--print-logs", action="store_true",
                        help="Pasar --print-logs a opencode run (logs a stderr).")
    parser.add_argument("--pasivo", action="store_true",
                        help="Modo pasivo: escanea el log sin gastar tokens (informativo).")
    parser.add_argument("--log", type=Path,
                        default=Path.home() / ".local/share/opencode/log/opencode.log",
                        help="Ruta del log de opencode para el modo pasivo.")
    parser.add_argument("--ventana-min", type=int, default=20,
                        help="Ventana de líneas a escanear en modo pasivo (aprox bytes).")
    args = parser.parse_args()

    if args.pasivo:
        estado, detalles = _escanear_log_pasivo(args.log, args.ventana_min)
    else:
        estado, detalles = sondear(args.modelo, args.timeout, args.dir, args.print_logs)

    salida = {
        "estado": estado,
        "modelo": args.modelo,
        "sonda": "pasiva" if args.pasivo else "activa",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "retry_en_segundos": detalles.pop("retry_en_segundos", None),
        "detalles": detalles,
    }
    print(json.dumps(salida, ensure_ascii=False))

    codigo = {"ok": 0, "agotada": 1, "error_infra": 2, "indeterminado": 3}[estado]
    sys.exit(codigo)


if __name__ == "__main__":
    main()