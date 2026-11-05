#!/usr/bin/env python3
"""
flujo_asignar_tareas.py — Orquestador de tareas por grupo (Layer 2)

Ejecuta el pipeline definido en la directiva asignar_tareas_curso.yaml:
  1. execution/generar_tareas_curso.py → valida y genera los documentos
  2. verificación de entrega → .tex y PDF por grupo, sin errores en los .log
  3. execution/alert_user.py → alerta audible (opcional)

Este orquestador NO asigna roles ni redacta la tarea: eso es capa 3.
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
GENERADOR = SCRIPT_DIR / "execution" / "generar_tareas_curso.py"
ALERTAR = SCRIPT_DIR / "execution" / "alert_user.py"

sys.path.insert(0, str(SCRIPT_DIR / "execution"))
import run_state as RS  # noqa: E402

DIAGNOSTICO = {
    1: "argumentos inválidos",
    2: "descriptor ilegible o que no es YAML",
    3: "descriptor o fase inválidos (fase sin roles, rol sin en_la_practica o sin semanas)",
    4: "error de compilación LaTeX (revisar .tmp/latex_build/tareas_<codigo>_fase_<N>/*.log)",
    5: "error de escritura en disco",
}


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def guardar(state: dict) -> None:
    RS.escribir_vista(RS.ruta_vista(state.get("run_id")), state)


def _verificar(artefactos: list[dict]) -> list[str]:
    problemas: list[str] = []
    for artefacto in artefactos:
        job = artefacto.get("job")
        ruta_tex = artefacto.get("tex")
        if artefacto.get("errores"):
            problemas.append(f"{job}: {artefacto['errores'][0]}")
            continue
        if ruta_tex and not Path(ruta_tex).exists():
            problemas.append(f"{job}: falta el .tex ({ruta_tex})")
        if ruta_tex:
            pdf = Path(ruta_tex).with_suffix(".pdf")
            if not pdf.exists():
                problemas.append(f"{job}: falta el PDF ({pdf})")
            elif pdf.stat().st_size < 2000:
                problemas.append(f"{job}: PDF sospechosamente pequeño ({pdf.stat().st_size} bytes)")
    return problemas


def flujo_asignar_tareas(
    curso: Path,
    fase: int,
    salida: Path | None,
    compilar: bool,
    alert: bool,
    como_json: bool,
) -> int:
    run_id = RS.run_id_de_la_corrida("flujo-asignar-tareas")
    state = {
        "run_id": run_id,
        "directive": "asignar_tareas_curso.yaml",
        "started_at": ahora(),
        "last_updated": ahora(),
        "current_step": 0,
        "steps_completed": [],
        "steps_failed": [],
        "context": {"curso": str(curso), "fase": fase, "compilar": compilar},
    }
    guardar(state)

    cmd = [PYTHON, str(GENERADOR), "--curso", str(curso), "--fase", str(fase), "--json"]
    if salida:
        cmd += ["--salida", str(salida)]
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
            {"step": 1, "script": "generar_tareas_curso.py", "code": resultado.returncode, "motivo": motivo}
        )
        state["last_updated"] = ahora()
        guardar(state)
        if como_json:
            print(json.dumps({"status": "error", "motivo": motivo, "detalle": detalle}, ensure_ascii=False, indent=2))
        else:
            print(f"\n  Falló la asignación (código {resultado.returncode}): {motivo}", file=sys.stderr)
            for linea in detalle:
                print(f"    - {linea}", file=sys.stderr)
        if alert:
            subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return resultado.returncode

    artefactos = datos.get("artefactos") or []
    state["current_step"] = 1
    state["steps_completed"].append({"step": 1, "script": "generar_tareas_curso.py", "status": "ok"})
    guardar(state)

    problemas = _verificar(artefactos)
    if problemas:
        state["steps_failed"].append({"step": 2, "script": "verificar_entrega", "problemas": problemas})
        state["last_updated"] = ahora()
        guardar(state)
        if como_json:
            print(json.dumps({"status": "entrega_incompleta", "problemas": problemas, "artefactos": artefactos}, ensure_ascii=False, indent=2))
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
        print(json.dumps({"status": "ok", "fase": datos.get("fase"), "salida": datos.get("salida"), "artefactos": artefactos, "run_id": run_id}, ensure_ascii=False, indent=2))
    else:
        barra = "═" * 60
        print(f"\n{barra}")
        print(f"  TAREAS POR GRUPO --- FASE {datos.get('fase')}")
        print(barra)
        print(f"  Documentos  : {len(artefactos)}")
        print(f"  Salida      : {datos.get('salida')}")
        print(f"  Run ID      : {run_id}")
        print(f"{barra}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Orquesta la asignación de tareas por grupo para una fase del curso.")
    parser.add_argument("--curso", required=True, help="Ruta al descriptor curso.yaml")
    parser.add_argument("--fase", required=True, type=int, help="Número de fase")
    parser.add_argument("--salida", default=None, help="Directorio de salida")
    parser.add_argument("--sin-compilar", action="store_true", help="Escribe solo los .tex")
    parser.add_argument("--json", action="store_true", help="Emite un único objeto JSON")
    parser.add_argument("--no-alert", action="store_true", help="No emitir alerta sonora")
    args = parser.parse_args(argv)

    return flujo_asignar_tareas(
        curso=Path(args.curso).resolve(),
        fase=args.fase,
        salida=Path(args.salida).resolve() if args.salida else None,
        compilar=not args.sin_compilar,
        alert=not args.no_alert,
        como_json=args.json,
    )


if __name__ == "__main__":
    sys.exit(main())
