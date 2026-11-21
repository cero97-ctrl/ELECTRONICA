#!/usr/bin/env python3
"""
flujo_sincronizar_titulos_practicas.py — Orquestador de la sync de títulos (Layer 2)

Ejecuta la directiva sincronizar_titulos_practicas.yaml:
  1. sincronizar_titulos_practicas.py --check  → lista cambios sin escribir
  2. sincronizar_titulos_practicas.py --apply  → edición quirúrgica + verificación
  3. flujo_crear_repo_semilla.py --forzar      → propaga a la semilla de grupos
  4. execution/test_generar_repo_semilla.py    → fija los títulos oficiales

La lógica de extracción y edición vive SOLO en la capa 3; aquí solo se encadena.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
PYTHON = sys.executable
SINCRONIZAR = SCRIPT_DIR / "execution" / "sincronizar_titulos_practicas.py"
SEMILLA = SCRIPT_DIR / "flujo_crear_repo_semilla.py"
TEST = SCRIPT_DIR / "execution" / "test_generar_repo_semilla.py"
ALERTAR = SCRIPT_DIR / "execution" / "alert_user.py"
CURSO_POR_DEFECTO = SCRIPT_DIR / "cursos/LABORATORIO_II_FISICA/curso.yaml"

sys.path.insert(0, str(SCRIPT_DIR / "execution"))
import run_state as RS  # noqa: E402


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ejecutar(cmd: list[str]) -> tuple[int, dict]:
    resultado = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    try:
        datos = json.loads(resultado.stdout)
    except json.JSONDecodeError:
        datos = {}
    return resultado.returncode, datos


def sincronizar(curso: Path, solo_check: bool, propagar: bool, alert: bool,
                como_json: bool) -> int:
    run_id = RS.run_id_de_la_corrida("flujo-sincronizar-titulos-practicas")
    state = {
        "run_id": run_id,
        "directive": "sincronizar_titulos_practicas.yaml",
        "started_at": ahora(),
        "last_updated": ahora(),
        "current_step": 0,
        "steps_completed": [],
        "steps_failed": [],
        "context": {"curso": str(curso), "check": solo_check, "propagar": propagar},
    }

    def guardar() -> None:
        state["last_updated"] = ahora()
        RS.escribir_vista(RS.ruta_vista(run_id), state)

    guardar()
    base = [PYTHON, str(SINCRONIZAR), "--curso", str(curso), "--json"]

    codigo, datos = _ejecutar(base + ["--check"])
    if codigo != 0:
        state["steps_failed"].append({"step": 1, "code": codigo, "detalle": datos.get("message")})
        guardar()
        if alert:
            subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        print(json.dumps(datos, ensure_ascii=False, indent=2) if como_json else
              f"error en la comprobación: {datos.get('message', codigo)}", file=sys.stderr)
        return codigo
    state["steps_completed"].append({"step": 1, "script": "sincronizar --check", "status": "ok"})
    guardar()

    if solo_check:
        print(json.dumps({"status": "ok", "check": True,
                          "n_cambios": datos.get("n_cambios"), "run_id": run_id},
                         ensure_ascii=False, indent=2) if como_json else
              f"{datos.get('n_cambios')} títulos por sincronizar (sin escribir)")
        return 0

    codigo, datos = _ejecutar(base + ["--apply"])
    if codigo != 0:
        state["steps_failed"].append({"step": 2, "code": codigo, "detalle": datos.get("message")})
        guardar()
        if alert:
            subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        print(json.dumps(datos, ensure_ascii=False, indent=2) if como_json else
              f"error al aplicar: {datos.get('message', codigo)}", file=sys.stderr)
        return codigo
    state["steps_completed"].append({"step": 2, "script": "sincronizar --apply",
                                     "n_cambios": datos.get("n_cambios"), "status": "ok"})
    guardar()

    if propagar:
        ejecucion = subprocess.run(
            [PYTHON, str(SEMILLA), "--curso", str(curso), "--forzar", "--json", "--no-alert"],
            capture_output=True, text=True, encoding="utf-8",
        )
        if ejecucion.returncode != 0:
            state["steps_failed"].append({"step": 3, "script": "flujo_crear_repo_semilla",
                                          "code": ejecucion.returncode})
            guardar()
            if alert:
                subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
            print(ejecucion.stderr or ejecucion.stdout, file=sys.stderr)
            return ejecucion.returncode
        state["steps_completed"].append({"step": 3, "script": "flujo_crear_repo_semilla",
                                         "status": "ok"})
        guardar()

    ejecucion = subprocess.run([PYTHON, str(TEST)], capture_output=True, text=True, encoding="utf-8")
    if ejecucion.returncode != 0:
        state["steps_failed"].append({"step": 4, "script": "test_generar_repo_semilla",
                                      "code": ejecucion.returncode})
        guardar()
        if alert:
            subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        print(ejecucion.stdout[-2000:], file=sys.stderr)
        return ejecucion.returncode
    state["steps_completed"].append({"step": 4, "script": "test_generar_repo_semilla",
                                     "status": "ok"})
    guardar()

    if alert:
        subprocess.run([PYTHON, str(ALERTAR), "success"], capture_output=True)
    informe = {
        "status": "ok", "code": 0, "run_id": run_id,
        "curso": str(curso), "titulos_actualizados": datos.get("n_cambios"),
        "semilla_regenerada": propagar,
    }
    print(json.dumps(informe, ensure_ascii=False, indent=2) if como_json else
          f"títulos sincronizados ({datos.get('n_cambios')} cambios); semilla regenerada={propagar}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sincroniza los títulos de práctica desde los .tex al descriptor del curso."
    )
    parser.add_argument("--curso", default=str(CURSO_POR_DEFECTO))
    parser.add_argument("--check", action="store_true", help="Solo reporta cambios.")
    parser.add_argument("--no-propagar", action="store_true", help="No regenera la semilla.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-alert", action="store_true")
    args = parser.parse_args(argv)
    return sincronizar(
        curso=Path(args.curso).resolve(),
        solo_check=args.check,
        propagar=not args.no_propagar,
        alert=not args.no_alert,
        como_json=args.json,
    )


if __name__ == "__main__":
    sys.exit(main())
