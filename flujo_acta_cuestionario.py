#!/usr/bin/env python3
"""Capa 2: descarga las entregas del cuestionario y arma el acta.

Orquesta `execution/descargar_resultados.py`. Aquí no se decide nada sobre las
notas: la capa 3 recalcula cada una con la clave vigente y marca `revisar` lo
que no cuadra. Este flujo resuelve rutas, encadena el script, **verifica** lo que
la capa 3 dijo haber escrito y deja trazabilidad.

El acta lleva nombres y cédulas, así que la capa 3 solo la escribe en rutas que
git ignora; este flujo comprueba además que el CSV y el PDF existen de verdad y
que el número de filas coincide con las entregas reportadas.

Uso:
    python3 flujo_acta_cuestionario.py
    python3 flujo_acta_cuestionario.py --lista estudiantes.csv
    python3 flujo_acta_cuestionario.py --sin-pdf --json

Códigos de salida: 0 ok · 1 E/S · 3 fuente/clave inválida o uso incorrecto ·
4 red/credenciales · 5 entregas archivadas inválidas (acta con avisos).
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
EJECUCION = RAIZ / "execution"
PYTHON = sys.executable
DESCARGADOR = EJECUCION / "descargar_resultados.py"
CONSOLIDADOR = EJECUCION / "acta_semana.py"
SESION_LOG = EJECUCION / "sesion_log.py"
ALERTAR = EJECUCION / "alert_user.py"
FUENTE_POR_DEFECTO = (
    "cursos/CYBERSEGURIDAD/evaluaciones/web/fuentes/ROL_ROJO_Cuestionario.md"
)

DIAGNOSTICO = {
    0: "acta generada",
    1: "error de E/S al leer o escribir",
    3: "fuente/clave inválida, uso incorrecto o ruta de salida no ignorada por git",
    4: "red o credenciales (token ausente, 401/403/404)",
    5: "hay entregas archivadas inválidas: el acta se generó con avisos",
}

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


def _descargar(args: argparse.Namespace) -> dict:
    cmd = [
        PYTHON,
        str(DESCARGADOR),
        "--fuente",
        args.fuente,
        "--rama",
        args.rama,
        "--json",
    ]
    for flag, valor in (
        ("--respuestas", args.respuestas),
        ("--repo", args.repo),
        ("--cuestionario", args.cuestionario),
        ("--lista", args.lista),
        ("--salida", args.salida),
        ("--pdf", args.pdf),
        ("--fecha", args.fecha),
        ("--token-env", args.token_env),
    ):
        if valor:
            cmd.extend([flag, valor])
    if args.sin_pdf:
        cmd.append("--sin-pdf")
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
    """Comprueba que lo que la capa 3 dice haber escrito existe y cuadra."""
    problemas: list[str] = []
    entregas = resultado.get("entregas")
    if not isinstance(entregas, int):
        return ["la capa 3 no reportó `entregas`"]

    ruta_csv = resultado.get("acta_csv")
    if not ruta_csv:
        return ["la capa 3 no reportó `acta_csv`"]
    csv_path = Path(ruta_csv)
    if not csv_path.is_file():
        return [f"el acta CSV no existe: {csv_path}"]
    try:
        with csv_path.open(newline="", encoding="utf-8") as fh:
            filas = list(csv.DictReader(fh))
    except (OSError, csv.Error) as exc:
        return [f"el acta CSV no se pudo leer: {exc}"]
    if len(filas) != entregas:
        problemas.append(
            f"el CSV tiene {len(filas)} fila(s) y la capa 3 reportó {entregas} entrega(s)"
        )
    if entregas and any(not f.get("cedula") for f in filas):
        problemas.append("hay filas sin cédula en el acta")

    if not sin_pdf:
        ruta_pdf = resultado.get("acta_pdf")
        if not ruta_pdf:
            problemas.append("se pidió PDF y la capa 3 no reportó `acta_pdf`")
        elif not Path(ruta_pdf).is_file():
            problemas.append(f"el acta PDF no existe: {ruta_pdf}")
        elif Path(ruta_pdf).stat().st_size < 2048:
            problemas.append(f"el acta PDF es sospechosamente pequeño: {ruta_pdf}")

    return problemas


def _consolidar(args: argparse.Namespace) -> int:
    """Une los acta_*.csv de una semana en un solo (tex, pdf) y lo verifica."""
    if not args.semana:
        print("FALLA (3): --consolidar exige --semana N", file=sys.stderr)
        return 3
    cmd = [PYTHON, str(CONSOLIDADOR), "--semana", str(args.semana), "--json"]
    if args.salida_dir:
        cmd.extend(["--salida", args.salida_dir])
    if args.curso:
        cmd.extend(["--curso", args.curso])
    if args.listas_dir:
        listas = sorted(Path(args.listas_dir).glob("grupo_*.csv"))
        if not listas:
            print(f"FALLA (3): no hay grupo_*.csv en {args.listas_dir}", file=sys.stderr)
            return 3
        for lista in listas:
            cmd.extend(["--lista", str(lista)])
    try:
        proc = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"FALLA (1): no se pudo ejecutar el consolidador: {exc}", file=sys.stderr)
        return 1
    try:
        resultado = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(f"FALLA ({proc.returncode or 1}): {(proc.stdout or proc.stderr)[-800:]}",
              file=sys.stderr)
        return proc.returncode or 1
    codigo = int(resultado.get("code", proc.returncode or 1))

    problemas: list[str] = []
    if codigo == 0:
        ruta_tex = Path(str(resultado.get("acta_tex") or ""))
        if not ruta_tex.is_file() or ruta_tex.stat().st_size < 512:
            problemas.append(f"el .tex no existe o está vacío: {ruta_tex}")
        elif "\\end{document}" not in ruta_tex.read_text(encoding="utf-8", errors="ignore"):
            problemas.append(f"el .tex está truncado (sin \\end{{document}}): {ruta_tex}")
        ruta_pdf = resultado.get("acta_pdf")
        if not ruta_pdf:
            problemas.append("el consolidador no reportó `acta_pdf`")
        elif not Path(ruta_pdf).is_file():
            problemas.append(f"el PDF no existe: {ruta_pdf}")
        elif Path(ruta_pdf).stat().st_size < 2048:
            problemas.append(f"el PDF es sospechosamente pequeño: {ruta_pdf}")
        if not isinstance(resultado.get("entregas"), int) or resultado["entregas"] < 1:
            problemas.append("el consolidador no reportó `entregas`")
        if problemas:
            codigo = 1

    if args.json:
        if problemas:
            resultado["problemas_verificacion"] = problemas
        resultado["diagnostico"] = DIAGNOSTICO.get(codigo, "desconocido")
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    elif codigo == 0:
        print(
            f"Acta de la semana {resultado.get('semana'):02d} — "
            f"{resultado.get('entregas')} entrega(s)"
        )
        print(f"  TEX: {resultado.get('acta_tex')}")
        print(f"  PDF: {resultado.get('acta_pdf')}")
        for grupo, n in (resultado.get("por_grupo") or {}).items():
            print(f"  G{grupo}: {n}")
        faltantes = resultado.get("faltantes") or []
        if faltantes:
            print(f"  sin entrega: {len(faltantes)}")
            for falta in faltantes:
                print(f"    G{falta.get('grupo') or '?'} {falta['cedula']} {falta['nombre']}")
        if resultado.get("a_revisar"):
            print(f"  AVISO: {resultado['a_revisar']} fila(s) marcadas `revisar`.")
        if resultado.get("overfull"):
            print(f"  aviso: {resultado['overfull']} Overfull \\hbox (cosmético)")
    else:
        print(f"FALLA ({codigo}): {resultado.get('message', 'error')}", file=sys.stderr)
        for problema in problemas:
            print(f"  - {problema}", file=sys.stderr)
    return codigo


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Descarga las entregas del cuestionario y genera el acta."
    )
    parser.add_argument("--fuente", default=FUENTE_POR_DEFECTO, help="Markdown del cuestionario.")
    parser.add_argument("--respuestas", default=None, help="Archivo de respuestas (auto por defecto).")
    parser.add_argument("--repo", default=None, help="owner/repo privado de resultados.")
    parser.add_argument("--rama", default="main", help="Rama del repo.")
    parser.add_argument("--cuestionario", default=None, help="Id del cuestionario.")
    parser.add_argument("--lista", default=None, help="Nómina CSV/YAML para detectar faltantes.")
    parser.add_argument("--salida", default=None, help="Ruta del acta CSV.")
    parser.add_argument("--pdf", default=None, help="Ruta del acta PDF.")
    parser.add_argument("--sin-pdf", action="store_true", help="No generar el PDF.")
    parser.add_argument("--fecha", default=None, help="Fecha del acta (por defecto, el último envío).")
    parser.add_argument("--token-env", default=None, help="Variable con el token de lectura.")
    parser.add_argument("--consolidar", action="store_true",
                        help="Une los acta_*.csv de la semana en un solo (tex,pdf).")
    parser.add_argument("--semana", type=int, default=None,
                        help="Semana a consolidar (>= 1); exige --consolidar.")
    parser.add_argument("--listas-dir", default=None,
                        help="Carpeta con grupo_N.csv para listar faltantes.")
    parser.add_argument("--salida-dir", default=None,
                        help="Carpeta destino del acta consolidada.")
    parser.add_argument("--curso", default=None, help="Curso en el acta consolidada.")
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    parser.add_argument("--no-alert", action="store_true", help="Sin alerta audible.")
    args = parser.parse_args()
    if args.consolidar:
        return _consolidar(args)

    run_id = run_state.run_id_de_la_corrida("acta-cuestionario")
    ruta_estado = run_state.ruta_vista(run_id)
    _trazar(
        run_id,
        "flujo/inicio",
        {"fuente": args.fuente, "repo": args.repo, "lista": args.lista, "sin_pdf": args.sin_pdf},
    )

    resultado = _descargar(args)
    codigo = int(resultado.get("code", 1))

    problemas_verificacion: list[str] = []
    if codigo in (0, 5):
        problemas_verificacion = _verificar(resultado, args.sin_pdf)
        if problemas_verificacion:
            codigo = 1
            resultado["status"] = "error"
            resultado["message"] = "; ".join(problemas_verificacion)

    estado = "ok" if codigo == 0 else ("aviso" if codigo == 5 else "error")

    if ruta_estado is not None:
        run_state.escribir_vista(
            ruta_estado,
            {
                "run_id": run_id,
                "current_step": 1,
                "status": estado,
                "exit_code": codigo,
                "entregas": resultado.get("entregas"),
                "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
        )

    _trazar(
        run_id,
        "flujo/fin",
        {
            "status": estado,
            "exit_code": codigo,
            "entregas": resultado.get("entregas"),
            "a_revisar": resultado.get("a_revisar"),
            "verificacion": problemas_verificacion,
        },
    )
    if ruta_estado is not None:
        run_state.retirar_vista(ruta_estado)

    if args.json:
        if problemas_verificacion:
            resultado["problemas_verificacion"] = problemas_verificacion
        resultado["diagnostico"] = DIAGNOSTICO.get(codigo, "desconocido")
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    else:
        if codigo in (0, 5):
            resumen = resultado.get("resumen") or {}
            print(
                f"Acta de {resultado.get('cuestionario')} — "
                f"{resultado.get('entregas')} entrega(s)"
                + (
                    f" · promedio {resumen.get('promedio')}"
                    if resumen.get("promedio") is not None
                    else ""
                )
            )
            print(f"  CSV: {resultado.get('acta_csv')}")
            if resultado.get("acta_pdf"):
                print(f"  PDF: {resultado.get('acta_pdf')}")
            cobertura = resultado.get("cobertura")
            if cobertura:
                print(
                    f"  nómina: {cobertura['recibidos']}/{cobertura['esperados']} entregaron"
                )
                for falta in cobertura["faltantes"]:
                    print(f"    sin entrega: {falta['nombre'] or '(sin nombre)'} {falta['cedula']}")
            for aviso in resultado.get("avisos", []) or []:
                print(f"  ! {aviso}")
            if codigo == 5:
                print("  AVISO: hay filas marcadas `revisar`; revíselas antes de publicar notas.")
        else:
            print(
                f"FALLA ({codigo}): {resultado.get('message', DIAGNOSTICO.get(codigo, 'error'))}",
                file=sys.stderr,
            )
            for problema in problemas_verificacion:
                print(f"  - {problema}", file=sys.stderr)
            for aviso in resultado.get("avisos", []) or []:
                print(f"  ! {aviso}", file=sys.stderr)

    if codigo == 0 and not args.no_alert:
        try:
            subprocess.run(
                [
                    PYTHON,
                    str(ALERTAR),
                    "success",
                    "--message",
                    f"Acta generada: {resultado.get('entregas')} entregas",
                ],
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
