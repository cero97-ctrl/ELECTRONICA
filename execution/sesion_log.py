#!/usr/bin/env python3
"""
sesion_log.py — Trazabilidad append-only de sesiones y flujos (Layer 3: Execution)

Inspirado en la trazabilidad {append-only} del Agent Harness DeepSeek (dsh):
cada evento se AÑADE al log y nunca se modifica ni elimina. El log es la fuente
de verdad; los checkpoints/estado (ej. run_state.json) son vistas derivadas.

Contrato:
  - Log por ejecución: .tmp/session_log_<run>.jsonl
  - Cada línea es un evento JSON con hash encadenado (prev): cualquier edición
    o eliminación rompe la cadena y es detectada por `integrity`.
  - Vocabulario CONTROLADO de tipos de evento (--tipo), sanitizado.
  - Entradas por CLI argumentos; salida JSON por stdout; exit 0/1/2/3.

Uso:
  python3 execution/sesion_log.py add --run <id> --tipo <tipo> [--datos '{}']
  python3 execution/sesion_log.py ver --run <id> [--ultimos N] [--tipo X]
  python3 execution/sesion_log.py state --run <id> [--destino .tmp/run_state_<id>.json]
  python3 execution/sesion_log.py resume --run <id>
  python3 execution/sesion_log.py integrity --run <id>

Tipos de evento (vocabulario):
  flujo/inicio  - arranque de un flujo multi-paso
  flujo/paso    - paso completado ({paso, script, status})
  flujo/fin     - flujo terminado correctamente ({status: ok, exit_code})
  flujo/error   - fallo ({paso, script, mensaje})
  tool/call     - invocación de herramienta/script ({script, args})
  tool/result   - resultado de herramienta ({status, exit_code})
  delegacion/decidida  - enrutamiento determinista de delegación a subagente
                         ({task, tier, subagent|null, tokens, critico, vision})
  delegacion/resultado - resultado del subagente delegado ({subagent, status, exit_code})

Códigos de salida:
  0 -> éxito
  1 -> error de argumentos/validación de entrada
  2 -> log inexistente o corrupto (integridad rota)
  3 -> error interno
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = SCRIPT_DIR / ".tmp"

RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,120}$")

TIPOS_EVENTO = {
    "flujo/inicio",
    "flujo/paso",
    "flujo/fin",
    "flujo/error",
    "tool/call",
    "tool/result",
    "delegacion/decidida",
    "delegacion/resultado",
}


def _error(message: str, code: int = 1) -> int:
    print(json.dumps({"status": "error", "code": code, "message": message},
                     ensure_ascii=False))
    return code


def _ok(payload: dict) -> int:
    payload["status"] = "ok"
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _ruta_log(run: str) -> Path:
    return LOG_DIR / f"session_log_{run}.jsonl"


def _hash_linea_prev(prev_raw: bytes) -> str:
    return hashlib.sha256(prev_raw).hexdigest()


def _norm_json(datos: dict | None) -> dict:
    """Serialización canónica y determinista (claves ordenadas)."""
    datos = datos or {}
    if not isinstance(datos, dict):
        raise ValueError("--datos debe ser un objeto JSON")
    return dict(datos)


def _linea_canonica(ev: dict) -> str:
    return json.dumps(ev, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def add(run: str, tipo: str, datos: dict | None) -> int:
    LOG_DIR.mkdir(exist_ok=True)
    ruta = _ruta_log(run)
    prev_raw = b""
    seq = 1
    if ruta.exists():
        raw = ruta.read_bytes()
        # La última línea debe terminar en '\n'; si no, el log está corrupto.
        if raw and not raw.endswith(b"\n"):
            return _error(
                f"Log {ruta} no termina en salto de línea: posible escritura "
                "interrumpida. Ejecuta `sesion_log.py integrity`.",
                code=2,
            )
        lineas = [l for l in raw.splitlines() if l]
        if lineas:
            prev_raw = lineas[-1]
            try:
                ultimo = json.loads(prev_raw)
                seq = int(ultimo["seq"]) + 1
            except (ValueError, KeyError, json.JSONDecodeError):
                return _error(
                    f"Última línea de {ruta} no es un evento válido (seq). "
                    "Ejecuta `sesion_log.py integrity --run <id>`.",
                    code=2,
                )
    ev = {
        "seq": seq,
        "ts": datetime.now(timezone.utc).isoformat(),
        "run": run,
        "tipo": tipo,
        "datos": _norm_json(datos),
        "prev": _hash_linea_prev(prev_raw),
        "append_only": True,
    }
    linea = _linea_canonica(ev) + "\n"
    with ruta.open("a", encoding="utf-8") as f:
        f.write(linea)
    return _ok({"archivo": str(ruta), "seq": seq, "tipo": tipo})


def ver(run: str, ultimos: int | None, tipo: str | None) -> int:
    ruta = _ruta_log(run)
    if not ruta.exists():
        return _error(f"No existe el log de sesión: {ruta}", code=2)
    eventos = []
    with ruta.open("r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                ev = json.loads(linea)
            except json.JSONDecodeError:
                return _error(f"Evento corrupto en {ruta}", code=2)
            if tipo and ev.get("tipo") != tipo:
                continue
            eventos.append(ev)
    if ultimos:
        eventos = eventos[-ultimos:]
    return _ok({"archivo": str(ruta), "total": len(eventos), "eventos": eventos})


def state(run: str, destino: str | None) -> int:
    """Deriva un checkpoint (vista) de run_state.json desde el log. Determinista."""
    ruta = _ruta_log(run)
    if not ruta.exists():
        return _error(f"No existe el log de sesión: {ruta}", code=2)
    eventos = []
    with ruta.open("r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                eventos.append(json.loads(linea))
            except json.JSONDecodeError:
                return _error(f"Evento corrupto en {ruta}", code=2)
    if not eventos:
        return _error(f"Log de sesión vacío: {ruta}", code=2)

    pasos = [e["datos"] for e in eventos if e.get("tipo") == "flujo/paso"]
    errores = [e["datos"] for e in eventos if e.get("tipo") == "flujo/error"]
    ultimo = eventos[-1]
    checkpoint = {
        "run_id": run,
        "source": "session_log",
        "append_only": True,
        "current_step": max([int(p.get("paso", 0)) for p in pasos], default=0),
        "ultimo_evento": ultimo["tipo"],
        "eventos_total": len(eventos),
        "pasos_completados": [int(p.get("paso", 0)) for p in pasos],
        "errores": errores,
        "last_updated": ultimo["ts"],
        "log": str(ruta),
    }
    if destino:
        dest = Path(destino)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        checkpoint["destino"] = str(dest)
    return _ok(checkpoint)


def resume(run: str) -> int:
    """Informa si el run es reanudable y desde qué paso (log append-only)."""
    code = state(run, None)
    if code != 0:
        return code
    ruta = _ruta_log(run)
    eventos = []
    with ruta.open("r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                try:
                    eventos.append(json.loads(linea))
                except json.JSONDecodeError:
                    return _error(f"Evento corrupto en {ruta}", code=2)
    tipos = [e["tipo"] for e in eventos]
    ultimo_error = [e["datos"] for e in eventos if e.get("tipo") == "flujo/error"]
    if "flujo/fin" in tipos:
        reanudable, siguiente = False, None
    elif ultimo_error:
        reanudable, siguiente = True, int(ultimo_error[-1].get("paso", 0))
    else:
        pasos = [int(e["datos"]["paso"]) for e in eventos if e.get("tipo") == "flujo/paso"]
        reanudable, siguiente = True, (max(pasos) + 1 if pasos else 1)
    return _ok({
        "run": run,
        "reanudable": reanudable,
        "siguiente_paso": siguiente,
        "eventos": len(eventos),
        "estado": ("fin" if "flujo/fin" in tipos
                   else "error" if ultimo_error else "en_curso"),
    })


def integrity(run: str) -> int:
    """Verifica la cadena de hashes (append-only) y la secuencia seq/prev."""
    ruta = _ruta_log(run)
    if not ruta.exists():
        return _error(f"No existe el log de sesión: {ruta}", code=2)
    lineas = [l for l in ruta.read_bytes().splitlines() if l]
    if not lineas:
        return _ok({"archivo": str(ruta), "ok": True, "eventos": 0,
                    "mensaje": "log vacío"})
    prev = b""
    for i, raw in enumerate(lineas, start=1):
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            return _error(f"Evento {i} con JSON inválido en {ruta}", code=2)
        if ev.get("seq") != i:
            return _error(
                f"Evento {i}: seq esperado {i}, obtenido {ev.get('seq')}. "
                "¿Se eliminó u ordenó mal una línea?",
                code=2,
            )
        if ev.get("prev") != _hash_linea_prev(prev):
            return _error(
                f"Evento {i}: hash prev de la cadena NO coincide → el log fue "
                "modificado (append-only violado).",
                code=2,
            )
        if not ev.get("append_only"):
            return _error(
                f"Evento {i}: falta la marca append_only → log corrupto.",
                code=2,
            )
        prev = raw
    return _ok({"archivo": str(ruta), "ok": True, "eventos": len(lineas),
                "cadena_hashes": True})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comando", choices=["add", "ver", "state", "resume", "integrity"])
    parser.add_argument("--run", required=True, help="ID de la sesión/ejecución.")
    parser.add_argument("--tipo", help="Tipo de evento (vocabulario controlado).")
    parser.add_argument("--datos", help="JSON opcional con datos del evento.")
    parser.add_argument("--ultimos", type=int, default=None, help="Últimos N eventos.")
    parser.add_argument("--destino", default=None, help="Ruta del checkpoint derivado.")
    args = parser.parse_args()

    if not RUN_ID_RE.match(args.run):
        return _error("run_id inválido (solo [A-Za-z0-9._-], máx 120 chars).")

    comando = args.comando
    if comando == "add":
        if not args.tipo:
            return _error("add requiere --tipo <evento>.")
        if args.tipo not in TIPOS_EVENTO:
            return _error(
                f"tipo '{args.tipo}' no está en el vocabulario: "
                f"{', '.join(sorted(TIPOS_EVENTO))}.",
                code=1,
            )
        datos = None
        if args.datos:
            try:
                datos = json.loads(args.datos)
            except json.JSONDecodeError:
                return _error("--datos debe ser un JSON válido.")
        return add(args.run, args.tipo, datos)

    if comando == "ver":
        return ver(args.run, args.ultimos, args.tipo)

    if comando == "state":
        return state(args.run, args.destino)

    if comando == "resume":
        return resume(args.run)

    if comando == "integrity":
        return integrity(args.run)

    return _error("Comando no soportado.", code=3)


if __name__ == "__main__":
    sys.exit(main())