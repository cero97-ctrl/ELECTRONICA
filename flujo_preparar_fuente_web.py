#!/usr/bin/env python3
"""Capa 2: prepara una fuente web escrita con respuestas en español.

Orquesta `execution/separar_respuestas_md.py`, que es quien contiene la lógica:
deja el cuestionario limpio, crea el solucionario en el formato del conversor y
guarda un respaldo del original. Este flujo solo resuelve la ruta, encadena el
script, deja trazabilidad y reporta; no reescribe markdown por su cuenta.

Uso:
    python3 flujo_preparar_fuente_web.py
    python3 flujo_preparar_fuente_web.py --fuente cursos/OTRO/evaluaciones/web/SEMANA_01/fuentes/X.md
    python3 flujo_preparar_fuente_web.py --json
    python3 flujo_preparar_fuente_web.py --forzar   # sobrescribe un solucionario previo

Códigos de salida: 0 ok · 1 error de E/S · 3 validación fallida ·
4 no separable · 5 el solucionario ya existe y no se pasó --forzar.
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
SEPARADOR = EJECUCION / "separar_respuestas_md.py"
SESION_LOG = EJECUCION / "sesion_log.py"
ALERTAR = EJECUCION / "alert_user.py"
FUENTE_POR_DEFECTO = (
    "cursos/CYBERSEGURIDAD/evaluaciones/web/SEMANA_02/fuentes/ROL_ROJO_CUESTIONARIO_S2.md"
)

sys.path.insert(0, str(EJECUCION))
import run_state  # noqa: E402  (capa 3: vista por corrida)


def _trazar(run_id: str, tipo: str, datos: dict) -> bool:
    try:
        proc = subprocess.run(
            [
                PYTHON,
                str(SESION_LOG),
                "add",
                "--run",
                run_id,
                "--tipo",
                tipo,
                "--datos",
                json.dumps(datos, ensure_ascii=False),
            ],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def _separar(args: argparse.Namespace) -> dict:
    cmd = [PYTHON, str(SEPARADOR), "--fuente", args.fuente, "--json"]
    if args.forzar:
        cmd.append("--forzar")
    try:
        proc = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "error", "code": 1, "message": f"no se pudo ejecutar: {exc}"}
    try:
        datos = json.loads(proc.stdout)
    except json.JSONDecodeError:
        datos = {
            "status": "error",
            "code": 1,
            "message": (proc.stdout or proc.stderr or "sin salida")[-800:],
        }
    datos.setdefault("code", proc.returncode)
    return datos


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fuente", default=FUENTE_POR_DEFECTO, help="Markdown a separar.")
    parser.add_argument("--forzar", action="store_true", help="Sobrescribe un solucionario previo.")
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    parser.add_argument("--no-alert", action="store_true", help="Sin alerta audible.")
    args = parser.parse_args()

    run_id = run_state.run_id_de_la_corrida("preparar-fuente-web")
    ruta_estado = run_state.ruta_vista(run_id)
    _trazar(run_id, "flujo/inicio", {"fuente": args.fuente, "forzar": args.forzar})

    resultado = _separar(args)
    codigo = int(resultado.get("code", 1))
    estado = "ok" if codigo == 0 else "error"

    if ruta_estado is not None:
        run_state.escribir_vista(
            ruta_estado,
            {
                "run_id": run_id,
                "current_step": 1,
                "status": estado,
                "exit_code": codigo,
                "fuente": args.fuente,
                "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
        )

    _trazar(run_id, "flujo/fin", {"status": estado, "exit_code": codigo})
    if ruta_estado is not None:
        run_state.retirar_vista(ruta_estado)

    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    elif codigo == 0:
        print(f"Fuente preparada: {resultado['fuente']} ({resultado['preguntas']} preguntas)")
        print(f"  solucionario: {resultado['respuestas']}")
        print(f"  respaldo:     {resultado['respaldo']}")
    else:
        print(f"FALLA ({codigo}): {resultado.get('message', 'error')}", file=sys.stderr)

    if codigo == 0 and not args.no_alert:
        try:
            subprocess.run(
                [PYTHON, str(ALERTAR), "success", "--message", "Fuente web preparada"],
                cwd=RAIZ,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            pass

    return codigo


if __name__ == "__main__":
    sys.exit(main())
