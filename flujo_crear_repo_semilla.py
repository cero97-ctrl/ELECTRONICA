#!/usr/bin/env python3
"""
flujo_crear_repo_semilla.py — Orquestador del repo semilla de grupos (Layer 2)

Ejecuta la directiva crear_repo_semilla_estudiantes.yaml:
  1. execution/generar_repo_semilla.py --check  → valida descriptor y plan
  2. execution/generar_repo_semilla.py          → escribe y verifica byte a byte
  3. comprobación de entrega (archivos clave presentes; la regla fina vive en L3)
  4. execution/alert_user.py                    → alerta audible (opcional)

Este orquestador NO decide títulos, roles ni estructura: todo eso es capa 3.
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
GENERADOR = SCRIPT_DIR / "execution" / "generar_repo_semilla.py"
ALERTAR = SCRIPT_DIR / "execution" / "alert_user.py"
CURSO_POR_DEFECTO = SCRIPT_DIR / "cursos/LABORATORIO_II_FISICA/curso.yaml"
SALIDA_POR_DEFECTO = SCRIPT_DIR / "cursos/LABORATORIO_II_FISICA/plantillas/repo_grupo"
ARCHIVOS_CLAVE = ("README.md", ".gitignore", "semana_01/README.md", "semana_10/README.md",
                  "semana_10/portafolio/.gitkeep")

sys.path.insert(0, str(SCRIPT_DIR / "execution"))
import run_state as RS  # noqa: E402

DIAGNOSTICO = {
    2: "descriptor ilegible o incompleto (faltan semanas, roles o corte)",
    3: "la salida ya tiene archivos generados; hace falta --forzar",
    4: "la verificación de la salida falló",
}


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def guardar(state: dict) -> None:
    RS.escribir_vista(RS.ruta_vista(state.get("run_id")), state)


def _ejecutar(cmd: list[str]) -> tuple[int, dict]:
    resultado = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    try:
        datos = json.loads(resultado.stdout)
    except json.JSONDecodeError:
        datos = {}
    return resultado.returncode, datos


def crear_repo_semilla(curso: Path, salida: Path, forzar: bool, solo_check: bool,
                       alert: bool, como_json: bool) -> int:
    run_id = RS.run_id_de_la_corrida("flujo-crear-repo-semilla")
    state = {
        "run_id": run_id,
        "directive": "crear_repo_semilla_estudiantes.yaml",
        "started_at": ahora(),
        "last_updated": ahora(),
        "current_step": 0,
        "steps_completed": [],
        "steps_failed": [],
        "context": {"curso": str(curso), "salida": str(salida),
                    "forzar": forzar, "check": solo_check},
    }
    guardar(state)

    base = [PYTHON, str(GENERADOR), "--curso", str(curso), "--salida", str(salida), "--json"]

    codigo, datos = _ejecutar(base + ["--check"])
    if codigo != 0:
        motivo = DIAGNOSTICO.get(codigo, "fallo no clasificado")
        state["steps_failed"].append({"step": 1, "script": "generar_repo_semilla.py --check",
                                      "code": codigo, "motivo": motivo})
        guardar(state)
        if alert:
            subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        print(json.dumps({"status": "error", "code": codigo, "motivo": motivo,
                          "detalle": datos.get("message", "")}, ensure_ascii=False, indent=2)
              if como_json else f"error: {motivo}", file=sys.stderr)
        return codigo
    state["current_step"] = 1
    state["steps_completed"].append({"step": 1, "script": "generar_repo_semilla.py --check", "status": "ok"})
    guardar(state)

    if solo_check:
        if alert:
            subprocess.run([PYTHON, str(ALERTAR), "success"], capture_output=True)
        print(json.dumps({"status": "ok", "check": True, "archivos": datos.get("archivos"),
                          "run_id": run_id}, ensure_ascii=False, indent=2) if como_json
              else f"semilla validada: {datos.get('archivos')} archivos (sin escribir)")
        return 0

    cmd = base + (["--forzar"] if forzar else [])
    codigo, datos = _ejecutar(cmd)
    if codigo != 0:
        motivo = DIAGNOSTICO.get(codigo, "fallo no clasificado")
        state["steps_failed"].append({"step": 2, "script": "generar_repo_semilla.py",
                                      "code": codigo, "motivo": motivo})
        guardar(state)
        if alert:
            subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        print(json.dumps({"status": "error", "code": codigo, "motivo": motivo,
                          "detalle": datos.get("message", "")}, ensure_ascii=False, indent=2)
              if como_json else f"error: {motivo}", file=sys.stderr)
        return codigo
    state["current_step"] = 2
    state["steps_completed"].append({"step": 2, "script": "generar_repo_semilla.py", "status": "ok"})
    guardar(state)

    problemas = list(datos.get("problemas") or [])
    for relativa in ARCHIVOS_CLAVE:
        if not (salida / relativa).is_file():
            problemas.append(f"falta el archivo clave {relativa}")
    if problemas:
        state["steps_failed"].append({"step": 3, "script": "verificar_entrega", "problemas": problemas})
        guardar(state)
        if alert:
            subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        print(json.dumps({"status": "entrega_incompleta", "problemas": problemas},
                         ensure_ascii=False, indent=2) if como_json else
              "entrega incompleta: " + "; ".join(problemas), file=sys.stderr)
        return 4
    state["steps_completed"].append({"step": 3, "script": "verificar_entrega", "status": "ok"})
    guardar(state)

    if alert:
        subprocess.run([PYTHON, str(ALERTAR), "success"], capture_output=True)
    state["steps_completed"].append({"step": 4, "script": "alert_user.py", "status": "ok"})
    state["last_updated"] = ahora()
    guardar(state)

    informe = {
        "status": "ok",
        "code": 0,
        "curso": str(curso),
        "salida": str(salida),
        "semanas": datos.get("semanas"),
        "archivos": datos.get("archivos"),
        "run_id": run_id,
    }
    print(json.dumps(informe, ensure_ascii=False, indent=2) if como_json else
          f"repo semilla listo: {datos.get('archivos')} archivos en {salida}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Orquesta la creación del repo semilla de grupos de Laboratorio II."
    )
    parser.add_argument("--curso", default=str(CURSO_POR_DEFECTO), help="Ruta a curso.yaml")
    parser.add_argument("--salida", default=str(SALIDA_POR_DEFECTO), help="Directorio destino")
    parser.add_argument("--forzar", action="store_true", help="Sobrescribe solo los archivos generados")
    parser.add_argument("--check", action="store_true", help="Valida sin escribir")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    parser.add_argument("--no-alert", action="store_true", help="Sin alerta audible")
    args = parser.parse_args(argv)

    return crear_repo_semilla(
        curso=Path(args.curso).resolve(),
        salida=Path(args.salida).resolve(),
        forzar=args.forzar,
        solo_check=args.check,
        alert=not args.no_alert,
        como_json=args.json,
    )


if __name__ == "__main__":
    sys.exit(main())
