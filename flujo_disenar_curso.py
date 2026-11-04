#!/usr/bin/env python3
"""
flujo_disenar_curso.py — Orquestador del diseño de un curso (Layer 2)

Ejecuta el pipeline definido en la directiva disenar_curso.yaml:
  1. execution/generar_material_curso.py → valida el descriptor y genera el material
  2. verificación de la entrega   → un PDF por documento, cero errores en los .log
  3. execution/alert_user.py      → alerta audible (opcional)

Este orquestador NO valida el descriptor ni escribe LaTeX: eso es capa 3. Su
trabajo es decidir qué se ejecuta, interpretar los códigos de salida y comprobar
que la entrega prometida existe de verdad en disco.

Uso:
    python3 flujo_disenar_curso.py --curso cursos/CYBERSEGURIDAD/curso.yaml
    python3 flujo_disenar_curso.py --curso <yaml> --solo silabo,guia --sin-compilar
    python3 flujo_disenar_curso.py --curso <yaml> --json --no-alert
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
GENERADOR = SCRIPT_DIR / "execution" / "generar_material_curso.py"
ALERTAR = SCRIPT_DIR / "execution" / "alert_user.py"

sys.path.insert(0, str(SCRIPT_DIR / "execution"))
import run_state as RS  # noqa: E402  (capa 3, resolución explícita)

# Códigos del generador → explicación accionable para el humano.
DIAGNOSTICO = {
    1: "artefacto desconocido en --solo",
    2: "descriptor ilegible o que no es YAML",
    3: "descriptor incoherente (semanas, fases o pesos que no cierran)",
    4: "error de compilación LaTeX (revisar .tmp/latex_build/curso_<codigo>/*.log)",
    5: "error de escritura en disco",
}


def ahora() -> str:
    """Marca de tiempo UTC en ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


def guardar(state: dict) -> None:
    """Persiste la vista de estado delegando en `execution/run_state.py`."""
    RS.escribir_vista(RS.ruta_vista(state.get("run_id")), state)


def _verificar_entrega(artefactos: list[dict], compilar: bool) -> list[str]:
    """Comprueba que cada artefacto prometido existe y que no hay errores.

    Args:
        artefactos: Lista emitida por el generador.
        compilar: Si se esperaba un PDF por documento.

    Returns:
        Lista de problemas; vacía si la entrega está completa.
    """
    problemas: list[str] = []
    for artefacto in artefactos:
        job = artefacto.get("job") or artefacto.get("artefacto")
        if artefacto.get("errores"):
            problemas.append(f"{job}: {artefacto['errores'][0]}")
            continue
        ruta_tex = artefacto.get("tex")
        if ruta_tex and not Path(ruta_tex).exists():
            problemas.append(f"{job}: falta el .tex ({ruta_tex})")
        if compilar and ruta_tex:
            pdf = Path(ruta_tex).with_suffix(".pdf")
            if not pdf.exists():
                problemas.append(f"{job}: falta el PDF ({pdf})")
            elif pdf.stat().st_size < 2000:
                problemas.append(f"{job}: PDF sospechosamente pequeño ({pdf.stat().st_size} bytes)")
        if not ruta_tex and artefacto.get("ruta") and not Path(artefacto["ruta"]).exists():
            problemas.append(f"{job}: falta {artefacto['ruta']}")
    return problemas


def flujo_disenar_curso(
    curso: Path,
    salida: Path | None,
    solo: str,
    compilar: bool,
    alert: bool,
    como_json: bool,
) -> int:
    """Orquesta la generación del material de un curso.

    Args:
        curso: Ruta al descriptor `curso.yaml`.
        salida: Directorio del curso; por defecto, el del descriptor.
        solo: Artefactos a generar, separados por coma (vacío = todos).
        compilar: Si es False, se escriben solo los `.tex`.
        alert: Si es True, emite alerta audible al terminar.
        como_json: Si es True, imprime un único objeto JSON.

    Returns:
        Código de salida del flujo: 0 ok, si no el del generador.
    """
    run_id = RS.run_id_de_la_corrida("flujo-disenar-curso")
    state: dict = {
        "run_id": run_id,
        "directive": "disenar_curso.yaml",
        "started_at": ahora(),
        "last_updated": ahora(),
        "current_step": 0,
        "steps_completed": [],
        "steps_failed": [],
        "context": {
            "curso": str(curso),
            "solo": solo,
            "compilar": compilar,
        },
    }
    guardar(state)

    cmd = [PYTHON, str(GENERADOR), "--curso", str(curso), "--json"]
    if salida:
        cmd += ["--salida", str(salida)]
    if solo:
        cmd += ["--solo", solo]
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
            {"step": 1, "script": "generar_material_curso.py",
             "code": resultado.returncode, "motivo": motivo}
        )
        state["last_updated"] = ahora()
        guardar(state)
        if como_json:
            print(json.dumps({"status": "error", "motivo": motivo, "detalle": detalle},
                             ensure_ascii=False, indent=2))
        else:
            print(f"\n  Falló la generación (código {resultado.returncode}): {motivo}", file=sys.stderr)
            for linea in detalle:
                print(f"    - {linea}", file=sys.stderr)
        if alert:
            subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return resultado.returncode

    artefactos = datos.get("artefactos") or []
    state["current_step"] = 1
    state["steps_completed"].append(
        {"step": 1, "script": "generar_material_curso.py", "status": "ok",
         "tex": datos.get("tex_escritos"), "pdf": datos.get("compilados")}
    )
    guardar(state)

    problemas = _verificar_entrega(artefactos, compilar)
    state["current_step"] = 2
    if problemas:
        state["steps_failed"].append({"step": 2, "script": "verificar_entrega", "problemas": problemas})
        state["last_updated"] = ahora()
        guardar(state)
        if como_json:
            print(json.dumps({"status": "entrega_incompleta", "problemas": problemas,
                              "artefactos": artefactos}, ensure_ascii=False, indent=2))
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
    state["current_step"] = 3
    state["steps_completed"].append(
        {"step": 3, "script": "alert_user.py", "status": "ok",
         "tipo": "success" if alert else "none"}
    )
    state["last_updated"] = ahora()
    guardar(state)

    if como_json:
        print(json.dumps(
            {"status": "ok", "curso": datos.get("curso"), "salida": datos.get("salida"),
             "tex_escritos": datos.get("tex_escritos"), "compilados": datos.get("compilados"),
             "artefactos": artefactos, "run_id": run_id},
            ensure_ascii=False, indent=2))
    else:
        barra = "═" * 60
        print(f"\n{barra}")
        print(f"  CURSO GENERADO — {datos.get('curso')}")
        print(barra)
        print(f"  Documentos LaTeX : {datos.get('tex_escritos')}")
        print(f"  PDF compilados   : {datos.get('compilados')}")
        print(f"  Salida           : {datos.get('salida')}")
        print(f"  Run ID           : {run_id}")
        print(f"{barra}\n")

    return 0


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada del flujo.

    Args:
        argv: Argumentos de línea de comandos (por defecto, sys.argv[1:]).

    Returns:
        Código de salida del proceso.
    """
    parser = argparse.ArgumentParser(
        description="Diseña y genera el material completo de un curso desde su descriptor YAML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--curso", required=True, help="Ruta al descriptor curso.yaml")
    parser.add_argument("--salida", default=None, help="Directorio del curso (por defecto, el del descriptor)")
    parser.add_argument("--solo", default="",
                        help="Artefactos separados por coma: silabo, plan_semanal, guia, practicas, "
                             "controles, final, rubrica, laboratorio, readme")
    parser.add_argument("--sin-compilar", action="store_true", help="Escribe los .tex sin invocar pdflatex")
    parser.add_argument("--json", action="store_true", help="Emite un único objeto JSON")
    parser.add_argument("--no-alert", action="store_true", help="No emitir alerta sonora")
    args = parser.parse_args(argv)

    return flujo_disenar_curso(
        curso=Path(args.curso).resolve(),
        salida=Path(args.salida).resolve() if args.salida else None,
        solo=args.solo,
        compilar=not args.sin_compilar,
        alert=not args.no_alert,
        como_json=args.json,
    )


if __name__ == "__main__":
    sys.exit(main())
