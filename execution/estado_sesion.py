#!/usr/bin/env python3
"""
estado_sesion.py — Verificación de salud del estado de sesión/ejecución
(Layer 3: Execution).

Detecta artefactos de estado OBSTETOS o HUÉRFANOS en .tmp/ antes de que un
orquestador o un servidor MCP los trate como "estado vigente". El log
append-only (.tmp/session_log_<run>.jsonl) es la fuente de verdad; los
run_state*.json son vistas derivadas que pueden sobrevivir a su corrida.

Regla central de veredicto (conservadora, "con certeza"):
  - Log del run EXISTE y su último evento es flujo/fin   → run TERMINADO
    → su run_state es HUÉRFANO → candidato a --clean.
  - Log del run EXISTE y último evento NO es flujo/fin   → en curso/error
    (reanudable) → run_state VIGENTE, nunca se borra.
  - NO existe log para el run_id → NO verificable (flujo sin trazabilidad);
    se advierte pero NO se borra (no hay certeza).

Diagnósticos adicionales (solo advertencia, no borrado):
  - Modelo del run_state obsoleto/en desuso (ej. deepseek-v4-pro).
  - Integridad de cadena de hashes de cada log (sesion_log.py integrity).
  - run_state con JSON inválido o sin run_id (posible escritura a medias).

Comandos:
  check   — informe JSON por artefacto (sales a stdout).
  clean   — borra SOLO run_state cuya corrida está terminada con certeza.
            Nunca toca los logs append-only (fuente de verdad inmutable).

Uso:
  python3 execution/estado_sesion.py check [--run <id>]
  python3 execution/estado_sesion.py clean [--run <id>] [--dry-run]

Códigos de salida:
  0 -> ok (check: sin anomalías; clean: hecho/nada que hacer)
  1 -> error de argumentos
  2 -> ocurrencia grave (check con anomalías estructurales en el estado vigente)
  3 -> error interno
"""

import argparse
import glob
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = SCRIPT_DIR / ".tmp"

#: Modelos en desuso conocidos (migrados/discontinuados). Detección por substring.
MODELOS_OBSOLETOS = ["deepseek-v4-pro", "deepseek/deepseek-v4-pro"]


def _error(message: str, code: int = 1) -> int:
    print(json.dumps({"status": "error", "code": code, "message": message},
                     ensure_ascii=False))
    return code


def _ok(payload: dict, code: int = 0) -> int:
    payload["status"] = "ok"
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


def _ruta_log(run_id: str) -> Path:
    return TMP_DIR / f"session_log_{run_id}.jsonl"


def _ruta_run_state(run_id: str) -> Path:
    return TMP_DIR / f"run_state_{run_id}.json"


def _leer_json(ruta: Path) -> dict | None:
    try:
        with ruta.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _estado_log(run_id: str) -> dict:
    """Clasifica el log del run sin cargar la cadena completa:
    ausente | en_curso | error | fin. Lee solo los tipos del JSONL."""
    ruta = _ruta_log(run_id)
    if not ruta.exists():
        return {"presente": False, "estado": "ausente"}
    tipos = []
    try:
        with ruta.open("r", encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    ev = json.loads(linea)
                except json.JSONDecodeError:
                    continue
                tipos.append(ev.get("tipo"))
    except OSError:
        return {"presente": True, "estado": "error",
                "detalle": "no legible"}
    if "flujo/fin" in tipos:
        return {"presente": True, "estado": "fin",
                "ultimo": tipos[-1] if tipos else None}
    if "flujo/error" in tipos:
        return {"presente": True, "estado": "error",
                "ultimo": tipos[-1] if tipos else None}
    if tipos:
        return {"presente": True, "estado": "en_curso",
                "ultimo": tipos[-1]}
    return {"presente": True, "estado": "vacio"}


def _modelo_obsoleto(modelo) -> str | None:
    if not isinstance(modelo, str) or not modelo:
        return None
    for m in MODELOS_OBSOLETOS:
        if m.lower() in modelo.lower():
            return m
    return None


def _chequear_run_state(ruta: Path, estado_log: dict) -> dict:
    """Veredicto de un archivo run_state* respecto a su corrida."""
    base = {
        "archivo": str(ruta),
        "run_id": None,
        "veredicto": "indefinido",
        "razon": "",
        "corrida": estado_log.get("estado", "ausente"),
    }
    datos = _leer_json(ruta)
    if datos is None:
        base.update(veredicto="corrupto",
                    razon="run_state no es JSON válido (escritura incompleta).")
        return base
    run_id = datos.get("run_id")
    base["run_id"] = run_id
    modelo = datos.get("modelo") or datos.get("model")
    if modelo:
        obsoleto = _modelo_obsoleto(modelo)
        if obsoleto:
            base["modelo_obsoleto"] = obsoleto
    # El nombre del archivo es la autoridad de a qué run pertenece la vista.
    if estado_log["presente"] and estado_log["estado"] == "fin":
        base.update(veredicto="huerfano",
                    razon="la corrida terminó (flujo/fin); la vista sobrevivió.")
    elif estado_log["presente"] and estado_log["estado"] in ("error", "en_curso", "vacio"):
        base.update(veredicto="vigente",
                    razon="corrida sin flujo/fin: estado reanudable o en curso.")
    else:
        base.update(veredicto="no_verificable",
                    razon="sin log append-only (flujo sin trazabilidad); no se borra.")
    return base


def _candidatos() -> list[Path]:
    """run_state.json global + run_state_<id>.json nombrados."""
    rutas = [TMP_DIR / "run_state.json"]
    rutas += [Path(p) for p in glob.glob(str(TMP_DIR / "run_state_*.json"))]
    return [r for r in rutas if r.exists()]


def _run_id_desde_archivo(ruta: Path) -> str | None:
    if ruta.name == "run_state.json":
        datos = _leer_json(ruta)
        id_ = (datos or {}).get("run_id") if isinstance(datos, dict) else None
        return id_ if id_ else None
    # run_state_<run>.json
    return ruta.stem[len("run_state_"):].strip() or None


def check(run: str | None) -> int:
    anomalias = 0
    checks: list[dict] = []

    # 1) Logs append-only existentes: presencia/legibilidad.
    # (La cadena de hashes la valida `sesion_log.py integrity`; aquí solo
    # confirmamos qué corridas tienen traza para cruzar contra run_state*.)
    logs: list[dict] = []
    for log in sorted(TMP_DIR.glob("session_log_*.jsonl")):
        run_id = log.name[len("session_log_"):-len(".jsonl")]
        if run and run_id != run:
            continue
        logs.append({"archivo": str(log), "run": run_id,
                     "estado": _estado_log(run_id)["estado"]})

    # 2) run_state*: veredicto contra su corrida.
    cands = _candidatos()
    if run:
        cands = [c for c in cands if _run_id_desde_archivo(c) == run]

    for ruta in sorted(cands):
        run_id = _run_id_desde_archivo(ruta)
        if not run_id:
            checks.append({
                "archivo": str(ruta), "veredicto": "corrupto",
                "razon": "run_state sin run_id (escritura incompleta).",
            })
            anomalias += 1
            continue
        estado_log = _estado_log(run_id)
        check_state = _chequear_run_state(ruta, estado_log)
        checks.append(check_state)
        if check_state["veredicto"] in ("huerfano", "corrupto"):
            anomalias += 1
        if check_state.get("modelo_obsoleto"):
            check_state["advertencia"] = (
                f"modelo del estado obsoleto: {check_state['modelo_obsoleto']}")

    acciones = []
    for c in checks:
        if c["veredicto"] == "huerfano":
            acciones.append(
                f"borrar {c['archivo']} (corrida terminada; regenerable con "
                "`sesion_log.py state`).")

    payload = {
        "checks": checks,
        "acciones_recomendadas": acciones,
        "registros_log": logs,
    }
    if anomalias:
        payload["veredicto_global"] = "atencion"
        payload["anomalias"] = anomalias
        return _ok(payload, 0)
    payload["veredicto_global"] = "ok"
    return _ok(payload, 0)


def clean(run: str | None, dry_run: bool) -> int:
    """Borra SOLO run_state (global o <run>) cuya corrida terminó (certeza)."""
    eliminados: list[str] = []
    omitidos: list[str] = []
    cands = _candidatos()
    if run:
        cands = [c for c in cands if _run_id_desde_archivo(c) == run]
    for ruta in sorted(cands):
        run_id = _run_id_desde_archivo(ruta)
        if not run_id:
            omitidos.append(str(ruta))
            continue
        estado_log = _estado_log(run_id)
        v = _chequear_run_state(ruta, estado_log)
        if v["veredicto"] == "huerfano":
            if dry_run:
                eliminados.append(f"[dry-run] {ruta}")
            else:
                try:
                    ruta.unlink(missing_ok=True)
                    eliminados.append(str(ruta))
                except OSError as exc:
                    return _error(f"No se pudo borrar {ruta}: {exc}", code=2)
    payload = {
        "eliminados": eliminados,
        "omitidos": omitidos,
        "nota": "Los logs append-only nunca se borran (fuente de verdad).",
    }
    return _ok(payload, 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comando", choices=["check", "clean"])
    parser.add_argument("--run", default=None, help="Acotar a un run_id.")
    parser.add_argument("--dry-run", action="store_true",
                        help="(clean) No borrar; solo listar lo que se borraría.")
    args = parser.parse_args()

    if args.comando == "check":
        return check(args.run)
    if args.comando == "clean":
        return clean(args.run, args.dry_run)
    return _error("Comando no soportado.", code=3)


if __name__ == "__main__":
    sys.exit(main())