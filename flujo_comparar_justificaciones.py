#!/usr/bin/env python3
"""Capa 2: genera la tabla privada que faceda justificaciones y explicaciones.

No decide nada: valida las fuentes, invoca la capa 3 y comprueba que los
archivos que ésta dice haber escrito existen y cuadran. La tabla contiene
nombres, cédulas y la clave, así que la capa 3 sólo escribe en rutas ignoradas
por git; aquí se verifica además que los caminos reportados existen de verdad.

Uso:
    python3 flujo_comparar_justificaciones.py --check
    python3 flujo_comparar_justificaciones.py --json
    python3 flujo_comparar_justificaciones.py --local .tmp/resultados --sin-pdf

Códigos: 0 ok · 1 E/S · 3 fuente/ruta inválida · 4 red/credenciales ·
5 entregas descartadas · 6 verificación del flujo fallida.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
EJECUCION = RAIZ / "execution"
PYTHON = sys.executable
SCRIPT = EJECUCION / "comparar_justificaciones.py"
SESION_LOG = EJECUCION / "sesion_log.py"
ALERTAR = EJECUCION / "alert_user.py"
SEMANA = "SEMANA_02"

DIAGNOSTICO = {
    0: "tabla generada",
    1: "error de E/S",
    3: "fuente o ruta de salida inválida",
    4: "red o credenciales",
    5: "hubo entregas descartadas (se informan en `descartados`)",
    6: "falló la verificación del flujo",
}

sys.path.insert(0, str(EJECUCION))
import run_state  # noqa: E402  (capa 3: vista por corrida)


def _trazar(run_id: str, tipo: str, datos: dict) -> None:
    try:
        subprocess.run(
            [PYTHON, str(SESION_LOG), "add", "--run", run_id, "--tipo", tipo,
             "--datos", json.dumps(datos, ensure_ascii=False)],
            cwd=RAIZ, capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _ejecutar(cmd: list[str]) -> dict:
    try:
        proc = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "error", "code": 1, "message": f"no se pudo ejecutar: {exc}"}
    try:
        datos = json.loads(proc.stdout)
    except json.JSONDecodeError:
        datos = {
            "status": "error",
            "code": proc.returncode or 1,
            "message": (proc.stdout or proc.stderr or "sin salida")[-800:],
        }
    datos.setdefault("code", proc.returncode)
    return datos


def _verificar(resultado: dict, sin_pdf: bool) -> list[str]:
    """Comprueba archivos, filas y que la tabla lleva la etiqueta de privacidad."""
    problemas: list[str] = []
    ruta_md = Path(str(resultado.get("md") or ""))
    if not ruta_md.is_file():
        return [f"la capa 3 no escribió el Markdown: {ruta_md}"]
    contenido = ruta_md.read_text(encoding="utf-8", errors="ignore")
    if len(contenido) < 100 or "# Comparativa de justificaciones" not in contenido:
        problemas.append("el Markdown no parece la tabla esperada")
    filas = resultado.get("filas")
    if not isinstance(filas, int):
        return problemas + ["la capa 3 no reportó `filas`"]
    coincide = re.search(r"(?m)^> filas: (\d+)$", contenido)
    if coincide is None or int(coincide.group(1)) != filas:
        problemas.append(f"el Markdown no declara {filas} filas")
    if "uso docente" not in contenido.lower():
        problemas.append("la tabla no lleva el aviso de uso docente privado")
    if not sin_pdf:
        ruta_pdf = Path(str(resultado.get("pdf") or ""))
        if not ruta_pdf.is_file():
            problemas.append(f"la capa 3 no escribió el PDF: {ruta_pdf}")
        elif ruta_pdf.stat().st_size < 2048:
            problemas.append(f"el PDF es sospechosamente pequeño: {ruta_pdf}")
    return problemas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fuente", action="append", default=[], help="Markdown (repetible).")
    parser.add_argument("--semana", default=SEMANA, help="Carpeta bajo evaluaciones/web/.")
    parser.add_argument("--repo", default=None, help="Repo privado de resultados.")
    parser.add_argument("--rama", default="main", help="Rama del repo.")
    parser.add_argument("--local", default=None, help="Lee JSON locales en vez de la API.")
    parser.add_argument("--token-env", default=None, help="Variable del token de lectura.")
    parser.add_argument("--salida", default=None, help="Ruta del Markdown.")
    parser.add_argument("--pdf", default=None, help="Ruta del PDF.")
    parser.add_argument("--sin-pdf", action="store_true", help="Sólo Markdown.")
    parser.add_argument("--check", action="store_true", help="Sólo valida fuentes.")
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
        print("FALLA (3): no hay fuentes; pasar --fuente o revisar --semana", file=sys.stderr)
        return 3

    run_id = run_state.run_id_de_la_corrida("comparar-justificaciones")
    vista = run_state.ruta_vista(run_id)
    _trazar(run_id, "flujo/inicio", {
        "fuentes": [f.name for f in fuentes], "check": args.check, "local": bool(args.local),
    })

    cmd = [PYTHON, str(SCRIPT)]
    for fuente in fuentes:
        cmd += ["--fuente", str(fuente)]
    for flag, valor in (
        ("--repo", args.repo), ("--rama", args.rama), ("--local", args.local),
        ("--token-env", args.token_env), ("--salida", args.salida), ("--pdf", args.pdf),
    ):
        if valor:
            cmd += [flag, valor]
    if args.sin_pdf:
        cmd.append("--sin-pdf")
    if args.check:
        cmd.append("--check")
    cmd.append("--json")

    datos = _ejecutar(cmd)
    codigo = int(datos.get("code", 1))
    if args.check:
        problemas: list[str] = []
    elif codigo == 0:
        problemas = _verificar(datos, args.sin_pdf)
        if problemas:
            codigo = 6
    else:
        problemas = []

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

    if problemas:
        datos["problemas_verificacion"] = problemas
    datos["diagnostico"] = DIAGNOSTICO.get(codigo, "desconocido")
    if args.json:
        print(json.dumps(datos, ensure_ascii=False, indent=2))
    elif codigo == 0:
        print(f"Tabla generada: {datos.get('md')} ({datos.get('filas')} filas).")
        if not args.sin_pdf:
            print(f"PDF: {datos.get('pdf')}")
    else:
        mensaje = datos.get("message") or "; ".join(problemas) or datos["diagnostico"]
        print(f"FALLA ({codigo}): {mensaje}", file=sys.stderr)

    if codigo == 0 and not args.check and not args.no_alert:
        try:
            subprocess.run([PYTHON, str(ALERTAR), "success"], cwd=RAIZ, capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            pass
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
