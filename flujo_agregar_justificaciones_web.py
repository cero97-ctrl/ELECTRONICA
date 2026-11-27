#!/usr/bin/env python3
"""Capa 2: añade recuadros de justificación a los cuestionarios de una semana.

No decide la instrucción ni qué preguntas llevan recuadro: pasa las fuentes al
script determinista de la capa 3, que toma todas las preguntas y valida el
resultado con el parser compartido por el HTML y el Worker.

Uso:
    python3 flujo_agregar_justificaciones_web.py [--semana SEMANA_02] [--check]

Códigos: 0 ok · 1 E/S · 3 fuente inválida · 4 sin fuentes.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
EJECUCION = RAIZ / "execution"
PYTHON = sys.executable
SCRIPT = EJECUCION / "agregar_justificaciones_web.py"
SESION_LOG = EJECUCION / "sesion_log.py"
ALERTAR = EJECUCION / "alert_user.py"

sys.path.insert(0, str(EJECUCION))
import run_state  # noqa: E402


def _trazar(run_id: str, tipo: str, datos: dict) -> None:
    try:
        subprocess.run(
            [PYTHON, str(SESION_LOG), "add", "--run", run_id, "--tipo", tipo,
             "--datos", json.dumps(datos, ensure_ascii=False)],
            cwd=RAIZ, capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semana", default="SEMANA_02", help="Carpeta bajo evaluaciones/web/.")
    parser.add_argument("--fuente", action="append", default=[], help="Fuente concreta (repetible).")
    parser.add_argument("--instruccion", default=None, help="Texto de la instrucción.")
    parser.add_argument("--forzar", action="store_true", help="Reemplaza instrucciones previas.")
    parser.add_argument("--check", action="store_true", help="Valida sin escribir.")
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    parser.add_argument("--no-alert", action="store_true", help="Sin alerta audible.")
    args = parser.parse_args()

    fuentes: list[Path]
    if args.fuente:
        fuentes = [Path(f).resolve() for f in args.fuente]
    else:
        carpeta = RAIZ / "cursos/CYBERSEGURIDAD/evaluaciones/web" / args.semana / "fuentes"
        fuentes = sorted(
            p for p in carpeta.glob("ROL_*_CUESTIONARIO_S2.md") if p.is_file()
        )
    if not fuentes:
        mensaje = f"no hay fuentes en {args.semana} (se esperan ROL_*_CUESTIONARIO_S2.md)"
        print(json.dumps({"status": "error", "code": 4, "message": mensaje}) if args.json else f"FALLA: {mensaje}", file=sys.stderr)
        return 4

    run_id = run_state.run_id_de_la_corrida("agregar-justificaciones-web")
    vista = run_state.ruta_vista(run_id)
    _trazar(run_id, "flujo/inicio", {"semana": args.semana, "fuentes": len(fuentes), "check": args.check})

    cmd = [PYTHON, str(SCRIPT)]
    for fuente in fuentes:
        cmd += ["--fuente", str(fuente)]
    if args.instruccion:
        cmd += ["--instruccion", args.instruccion]
    if args.forzar:
        cmd.append("--forzar")
    if args.check:
        cmd.append("--check")
    cmd.append("--json")

    try:
        proc = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError) as exc:
        codigo, salida, error = 1, "", str(exc)
    else:
        codigo, salida, error = proc.returncode, proc.stdout, proc.stderr

    if vista is not None:
        run_state.escribir_vista(vista, {
            "run_id": run_id,
            "current_step": 1,
            "status": "ok" if codigo == 0 else "error",
            "exit_code": codigo,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
    _trazar(run_id, "flujo/fin", {"status": "ok" if codigo == 0 else "error", "exit_code": codigo})
    if vista is not None:
        run_state.retirar_vista(vista)

    if args.json:
        if salida.strip():
            print(salida.strip())
        if error.strip():
            print(error.strip(), file=sys.stderr)
    elif codigo == 0:
        print(f"Justificaciones añadidas a {len(fuentes)} fuente(s) de {args.semana}.")
    else:
        print((error or salida).strip(), file=sys.stderr)

    if codigo == 0 and not args.check and not args.no_alert:
        try:
            subprocess.run([PYTHON, str(ALERTAR), "success"], cwd=RAIZ, capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            pass
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
