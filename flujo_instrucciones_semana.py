#!/usr/bin/env python3
"""
flujo_instrucciones_semana.py — Orquestador de las instrucciones semanales (Layer 2)

Ejecuta el pipeline definido en la directiva instrucciones_semana_curso.yaml:
  1. execution/generar_instrucciones_semana.py → valida y redacta el documento
  2. verificación de entrega → .tex y PDF en docs/, sin errores en el .log
  3. execution/alert_user.py → alerta audible (opcional)

Este orquestador NO redacta ni decide roles: eso es capa 3.
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
GENERADOR = SCRIPT_DIR / "execution" / "generar_instrucciones_semana.py"
ALERTAR = SCRIPT_DIR / "execution" / "alert_user.py"

sys.path.insert(0, str(SCRIPT_DIR / "execution"))
import run_state as RS  # noqa: E402

DIAGNOSTICO = {
    1: "argumentos inválidos",
    2: "descriptor ilegible o que no es YAML",
    3: "descriptor o semana inválidos (semana inexistente, práctica incompleta o criterios que no suman 10)",
    4: "error de compilación LaTeX (revisar .tmp/latex_build/semana_<codigo>_<NN>/*.log)",
    5: "error de escritura en disco",
}


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def guardar(state: dict) -> None:
    RS.escribir_vista(RS.ruta_vista(state.get("run_id")), state)


def _verificar(artefacto: dict) -> list[str]:
    problemas: list[str] = []
    if artefacto.get("errores"):
        problemas.append(f"{artefacto['job']}: {artefacto['errores'][0]}")
        return problemas
    ruta_tex = artefacto.get("tex")
    if ruta_tex and not Path(ruta_tex).exists():
        problemas.append(f"{artefacto['job']}: falta el .tex ({ruta_tex})")
    pdf = artefacto.get("pdf")
    if not pdf or not Path(pdf).exists():
        problemas.append(f"{artefacto['job']}: falta el PDF ({pdf})")
    elif Path(pdf).stat().st_size < 2000:
        problemas.append(f"{artefacto['job']}: PDF sospechosamente pequeño ({Path(pdf).stat().st_size} bytes)")
    return problemas


def flujo_instrucciones_semana(
    curso: Path,
    semana: int,
    salida: Path | None,
    compilar: bool,
    alert: bool,
    como_json: bool,
    grupo: int | None = None,
    cierre: bool = False,
) -> int:
    run_id = RS.run_id_de_la_corrida("flujo-instrucciones-semana")
    state = {
        "run_id": run_id,
        "directive": "instrucciones_semana_curso.yaml",
        "started_at": ahora(),
        "last_updated": ahora(),
        "current_step": 0,
        "steps_completed": [],
        "steps_failed": [],
        "context": {"curso": str(curso), "semana": semana, "grupo": grupo, "cierre": cierre, "compilar": compilar},
    }
    guardar(state)

    cmd = [PYTHON, str(GENERADOR), "--curso", str(curso), "--semana", str(semana), "--json"]
    if salida:
        cmd += ["--salida", str(salida)]
    if cierre:
        cmd.append("--cierre")
    elif grupo:
        cmd += ["--grupo", str(grupo)]
    if not compilar:
        cmd.append("--sin-compilar")

    resultado = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    try:
        datos = json.loads(resultado.stdout)
    except json.JSONDecodeError:
        datos = {}

    if resultado.returncode != 0:
        motivo = DIAGNOSTICO.get(resultado.returncode, "fallo no clasificado")
        detalle = datos.get("problemas") or datos.get("errores") or [resultado.stderr.strip()[:400]]
        state["steps_failed"].append(
            {"step": 1, "script": "generar_instrucciones_semana.py", "code": resultado.returncode, "motivo": motivo}
        )
        state["last_updated"] = ahora()
        guardar(state)
        if como_json:
            print(json.dumps({"status": "error", "motivo": motivo, "detalle": detalle}, ensure_ascii=False, indent=2))
        else:
            print(f"\n  Falló la generación (código {resultado.returncode}): {motivo}", file=sys.stderr)
            for linea in detalle:
                print(f"    - {linea}", file=sys.stderr)
        if alert:
            subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return resultado.returncode

    state["current_step"] = 1
    state["steps_completed"].append({"step": 1, "script": "generar_instrucciones_semana.py", "status": "ok"})
    guardar(state)

    if cierre:
        job = f"cierre_{semana:02d}"
    elif grupo:
        job = f"grupo_{grupo}_{semana:02d}"
    else:
        job = f"semana_{semana:02d}"
    artefacto = {
        "job": job,
        "tex": datos.get("tex"),
        "pdf": datos.get("pdf"),
        "errores": datos.get("errores") or [],
    }
    problemas = _verificar(artefacto)
    if problemas:
        state["steps_failed"].append({"step": 2, "script": "verificar_entrega", "problemas": problemas})
        state["last_updated"] = ahora()
        guardar(state)
        if como_json:
            print(json.dumps({"status": "entrega_incompleta", "problemas": problemas}, ensure_ascii=False, indent=2))
        else:
            print("\n  La entrega está incompleta:", file=sys.stderr)
            for problema in problemas:
                print(f"    - {problema}", file=sys.stderr)
        if alert:
            subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return 4
    state["steps_completed"].append({"step": 2, "script": "verificar_entrega", "status": "ok"})
    guardar(state)

    if alert:
        subprocess.run([PYTHON, str(ALERTAR), "success"], capture_output=True)
    state["steps_completed"].append({"step": 3, "script": "alert_user.py", "status": "ok"})
    state["last_updated"] = ahora()
    guardar(state)

    if como_json:
        print(json.dumps({"status": "ok", "semana": datos.get("semana"), "tex": datos.get("tex"), "pdf": datos.get("pdf"), "run_id": run_id}, ensure_ascii=False, indent=2))
    else:
        barra = "═" * 60
        print(f"\n{barra}")
        print(f"  INSTRUCCIONES --- SEMANA {semana:02d}")
        print(barra)
        print(f"  LaTeX : {datos.get('tex')}")
        print(f"  PDF   : {datos.get('pdf')}")
        print(f"  Run ID: {run_id}")
        print(f"{barra}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Orquesta la emisión de las instrucciones de una semana del curso.")
    parser.add_argument("--curso", required=True, help="Ruta al descriptor curso.yaml")
    parser.add_argument("--semana", required=True, type=int, help="Número de semana")
    parser.add_argument(
        "--grupo",
        type=int,
        default=None,
        help="Emite el ejemplo de trabajo de ese grupo (docs/grupo_N_NN.tex) en vez de la semana",
    )
    parser.add_argument(
        "--cierre",
        action="store_true",
        help="Emite el ejemplo único de cierre individual (docs/cierre_NN.tex) en vez de la semana",
    )
    parser.add_argument("--salida", default=None, help="Directorio de salida")
    parser.add_argument("--sin-compilar", action="store_true", help="Escribe solo el .tex")
    parser.add_argument("--json", action="store_true", help="Emite un único objeto JSON")
    parser.add_argument("--no-alert", action="store_true", help="No emitir alerta sonora")
    args = parser.parse_args(argv)
    if args.cierre and args.grupo is not None:
        parser.error("--cierre y --grupo son mutuamente excluyentes")

    return flujo_instrucciones_semana(
        curso=Path(args.curso).resolve(),
        semana=args.semana,
        salida=Path(args.salida).resolve() if args.salida else None,
        compilar=not args.sin_compilar,
        alert=not args.no_alert,
        como_json=args.json,
        grupo=args.grupo,
        cierre=args.cierre,
    )


if __name__ == "__main__":
    sys.exit(main())
