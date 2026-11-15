#!/usr/bin/env python3
"""flujo_fusionar_actas.py — Capa 2: une el acta regular con las de recuperación.

SOP: directives/fusionar_actas.yaml
Capa 3: execution/fusionar_actas.py

No decide nada sobre las notas: cada acta trae su `nota_recalculada` con la clave
que le corresponde y aquí solo se unen por cédula. Lo que sí verifica es la
invariante de la unión —`filas == regular + recuperación`— porque un acta que
pierde una entrega en silencio es peor que un error visible.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
EJECUCION = RAIZ / "execution"
PYTHON = sys.executable
FUSIONADOR = EJECUCION / "fusionar_actas.py"
ALERTA = EJECUCION / "alert_user.py"

DIAGNOSTICO = {
    0: "acta fusionada y verificada",
    1: "error de E/S al escribir o verificación fallida",
    3: "datos inconsistentes (conflicto, cabecera distinta, cédula inválida, acta vacía) o uso incorrecto",
}


def _correr(args: argparse.Namespace) -> dict:
    cmd = [PYTHON, str(FUSIONADOR), "--acta", args.acta, "--json"]
    for ruta in args.recuperacion:
        cmd.extend(["--recuperacion", ruta])
    if args.lista:
        cmd.extend(["--lista", args.lista])
    cmd.extend(["--salida", args.salida])
    try:
        proc = subprocess.run(
            cmd, cwd=RAIZ, capture_output=True, text=True, timeout=300
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "error", "code": 1, "message": f"no se pudo ejecutar: {exc}"}
    try:
        datos = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            "status": "error",
            "code": proc.returncode or 1,
            "message": (proc.stdout or proc.stderr or "sin salida")[-800:],
        }
    datos.setdefault("code", proc.returncode)
    return datos


def _verificar(datos: dict) -> list[str]:
    """Comprueba que lo que la capa 3 dice haber escrito existe y cuadra."""
    if datos.get("status") != "ok":
        return []
    problemas: list[str] = []
    ruta = datos.get("acta")
    if not ruta:
        return ["la capa 3 no reportó `acta`"]
    salida = Path(ruta)
    if not salida.is_file():
        return [f"el acta fusionada no existe: {salida}"]
    texto = salida.read_text(encoding="utf-8")
    lineas = texto.splitlines()
    if not lineas:
        return ["el acta fusionada está vacía"]
    if not lineas[0].endswith(",origen"):
        problemas.append("la cabecera no termina en `origen`")
    if "_cedula" in texto:
        problemas.append("el acta filtra la columna interna `_cedula`")

    filas = datos.get("filas")
    regular = datos.get("regular")
    recuperacion = datos.get("recuperacion")
    if not all(isinstance(v, int) for v in (filas, regular, recuperacion)):
        problemas.append("la capa 3 no reportó los conteos")
    else:
        if filas != regular + recuperacion:
            problemas.append(
                f"filas={filas} no es regular+recuperación={regular + recuperacion}: "
                "se perdió o duplicó una entrega"
            )
        if len(lineas) - 1 != filas:
            problemas.append(
                f"el CSV tiene {len(lineas) - 1} filas y se reportaron {filas}"
            )
    return problemas


def _avisar() -> None:
    try:
        subprocess.run(
            [PYTHON, str(ALERTA), "success"],
            cwd=RAIZ,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fusiona el acta regular con las actas de recuperación."
    )
    parser.add_argument("--acta", required=True, help="Acta CSV del examen regular.")
    parser.add_argument(
        "--recuperacion",
        action="append",
        default=[],
        required=True,
        help="Acta CSV de recuperación (repetible, una por grupo).",
    )
    parser.add_argument("--lista", default=None, help="Nómina para reportar faltantes.")
    parser.add_argument(
        "--salida",
        default=".tmp/acta_fusionada.csv",
        help="CSV de salida (debe estar ignorado por git).",
    )
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    parser.add_argument("--no-alert", action="store_true", help="No emitir alerta.")
    args = parser.parse_args()

    faltantes_rutas = [
        ruta
        for ruta in [args.acta, *args.recuperacion]
        if not Path(ruta).is_file()
    ]
    if faltantes_rutas:
        datos = {
            "status": "error",
            "code": 3,
            "problemas": [f"no existe {ruta}" for ruta in faltantes_rutas],
        }
        if args.json:
            print(json.dumps(datos, ensure_ascii=False, indent=2))
        else:
            for problema in datos["problemas"]:
                print(f"error: {problema}", file=sys.stderr)
        return 3

    datos = _correr(args)
    problemas = _verificar(datos)

    if datos.get("status") != "ok" or problemas:
        codigo = 1 if problemas and datos.get("status") == "ok" else datos.get("code", 1)
        datos = dict(datos, status="error", code=codigo)
        if problemas:
            datos["problemas_verificacion"] = problemas
        if args.json:
            print(json.dumps(datos, ensure_ascii=False, indent=2))
        else:
            mensaje = datos.get("message")
            if mensaje:
                print(f"error: {mensaje}", file=sys.stderr)
            for problema in datos.get("problemas", []) + problemas:
                print(f"  - {problema}", file=sys.stderr)
        return codigo

    if args.json:
        print(json.dumps(datos, ensure_ascii=False, indent=2))
    else:
        print(
            f"acta fusionada: {datos['filas']} filas "
            f"({datos['regular']} regular + {datos['recuperacion']} recuperación) "
            f"-> {datos['acta']}"
        )
        if datos.get("faltantes"):
            print(f"  sin entrega: {', '.join(datos['faltantes'])}")
        for aviso in datos.get("avisos", []):
            print(f"  aviso: {aviso}")
    if not args.no_alert:
        _avisar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
