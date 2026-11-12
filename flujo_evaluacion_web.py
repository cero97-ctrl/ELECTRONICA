#!/usr/bin/env python3
"""Capa 2: genera el HTML de los cuestionarios de examen del curso.

Orquesta `execution/md_a_html.py` sobre una o varias fuentes Markdown privadas.
No convierte nada por su cuenta: el parser, la validación, el escapado y la
barrera de rutas viven en la capa 3. Este flujo solo resuelve fuentes, encadena
el conversor, agrega resultados y deja trazabilidad.

El HTML es material privado: la fuente y la salida viven bajo
`cursos/<CURSO>/evaluaciones/web/`, ignorado por git. La variante `alumno` no
lleva la clave; la `docente` sí y la toma del front matter (`clave:`) o de un
archivo hermano `<fuente>_respuestas.md` con las respuestas (`**Answer:** X.`).
Ese archivo se valida contra la fuente antes de usarse y nunca se convierte
como si fuera un cuestionario.

Uso:
    python3 flujo_evaluacion_web.py --fuente cursos/CYBERSEGURIDAD/evaluaciones/web/fuentes/ROL_ROJO_Cuestionario.md --variantes alumno
    python3 flujo_evaluacion_web.py --variantes alumno,docente
    python3 flujo_evaluacion_web.py --check
    python3 flujo_evaluacion_web.py --dry-run --json

Códigos de salida: 0 ok · 1 error de E/S · 3 fuente inválida o respuestas que no
coinciden · 4 falta la clave · 5 ruta rechazada.
"""

from __future__ import annotations

import argparse
import glob
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
EJECUCION = RAIZ / "execution"
PYTHON = sys.executable
CONVERSOR = EJECUCION / "md_a_html.py"
SESION_LOG = EJECUCION / "sesion_log.py"
ALERTAR = EJECUCION / "alert_user.py"
PATRON_POR_DEFECTO = "cursos/*/evaluaciones/web/fuentes/*.md"

sys.path.insert(0, str(EJECUCION))
import run_state  # noqa: E402  (capa 3: vista por corrida)


def _es_archivo_de_respuestas(ruta: Path) -> bool:
    """Los `<fuente>_respuestas.md` son claves, no cuestionarios."""
    return ruta.name.lower().endswith("_respuestas.md")


def _resolver_fuentes(patrones: list[str]) -> list[Path]:
    encontradas: dict[str, Path] = {}
    for patron in patrones:
        base = patron if Path(patron).is_absolute() else str(RAIZ / patron)
        for ruta in glob.glob(base):
            p = Path(ruta).resolve()
            if (
                p.is_file()
                and p.suffix.lower() == ".md"
                and not _es_archivo_de_respuestas(p)
            ):
                encontradas[str(p)] = p
    return [encontradas[k] for k in sorted(encontradas)]


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


def _convertir(fuente: Path, args: argparse.Namespace) -> dict:
    cmd = [
        PYTHON,
        str(CONVERSOR),
        "--fuente",
        str(fuente),
        "--variantes",
        args.variantes,
        "--json",
    ]
    respuestas = fuente.with_name(f"{fuente.stem}_respuestas.md")
    if respuestas.is_file():
        cmd.extend(["--respuestas", str(respuestas)])
    if args.check:
        cmd.append("--check")
    if args.dry_run:
        cmd.append("--dry-run")
    try:
        proc = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "fuente": str(fuente),
            "status": "error",
            "code": 1,
            "message": f"no se pudo ejecutar el conversor: {exc}",
        }
    try:
        datos = json.loads(proc.stdout)
    except json.JSONDecodeError:
        datos = {
            "status": "error",
            "code": 1,
            "message": (proc.stdout or proc.stderr or "sin salida del conversor")[-800:],
        }
    datos.setdefault("code", proc.returncode)
    datos["fuente"] = str(fuente)
    return datos


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera HTML de cuestionarios desde Markdown privado."
    )
    parser.add_argument(
        "--fuente",
        action="append",
        default=None,
        help="Ruta o glob al .md (repetible). Por defecto, todos los fuentes/*.md.",
    )
    parser.add_argument(
        "--variantes",
        default="alumno,docente",
        help="Variantes a generar: alumno,docente.",
    )
    parser.add_argument("--check", action="store_true", help="Valida sin escribir.")
    parser.add_argument("--dry-run", action="store_true", help="Muestra rutas sin escribir.")
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    parser.add_argument("--no-alert", action="store_true", help="Sin alerta audible.")
    args = parser.parse_args()

    fuentes = _resolver_fuentes(args.fuente or [PATRON_POR_DEFECTO])
    if not fuentes:
        mensaje = "no se encontró ningún .md de origen"
        if args.json:
            print(json.dumps({"status": "error", "code": 3, "message": mensaje}))
        else:
            print(f"error: {mensaje}", file=sys.stderr)
        return 3

    run_id = run_state.run_id_de_la_corrida("evaluacion-web")
    ruta_estado = run_state.ruta_vista(run_id)
    _trazar(
        run_id,
        "flujo/inicio",
        {
            "fuentes": [str(f) for f in fuentes],
            "variantes": args.variantes,
            "check": args.check,
            "dry_run": args.dry_run,
        },
    )

    resultados = [_convertir(fuente, args) for fuente in fuentes]
    codigos = [int(r.get("code", 1)) for r in resultados]
    codigo = 0 if all(c == 0 for c in codigos) else max(codigos)
    estado = "ok" if codigo == 0 else "error"
    if args.check and codigo == 0:
        estado = "check"
    if args.dry_run and codigo == 0:
        estado = "dry-run"

    resumen = {
        "status": estado,
        "code": codigo,
        "run_id": run_id,
        "variantes": args.variantes,
        "fuentes": resultados,
        "resumen": {
            "total": len(resultados),
            "ok": sum(1 for c in codigos if c == 0),
            "error": sum(1 for c in codigos if c != 0),
        },
    }

    if ruta_estado is not None:
        run_state.escribir_vista(
            ruta_estado,
            {
                "run_id": run_id,
                "current_step": 1,
                "status": estado,
                "exit_code": codigo,
                "fuentes": len(fuentes),
                "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
        )

    _trazar(run_id, "flujo/fin", {"status": estado, "exit_code": codigo})
    if ruta_estado is not None:
        run_state.retirar_vista(ruta_estado)

    if args.json:
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
    else:
        print(f"Cuestionarios web — {len(resultados)} fuente(s), variantes: {args.variantes}")
        for resultado in resultados:
            estado_fuente = resultado.get("status", "?")
            fuente = Path(resultado["fuente"]).name
            if resultado.get("code", 1) == 0:
                generados = resultado.get("generados", {})
                detalle = ", ".join(Path(p).name for p in generados.values()) or "validado"
                print(f"  ok    {fuente}: {detalle}")
            else:
                print(f"  FALLA {fuente}: {resultado.get('message', 'error')}")
                for problema in resultado.get("problemas", []):
                    print(f"        - {problema}")
        print(f"Resultado: {resumen['resumen']['ok']}/{len(resultados)} ok")

    if codigo == 0 and not args.no_alert and not args.check and not args.dry_run:
        try:
            subprocess.run(
                [PYTHON, str(ALERTAR), "success", "--message", "Cuestionarios web generados"],
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
