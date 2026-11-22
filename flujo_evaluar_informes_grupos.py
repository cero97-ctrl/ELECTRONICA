#!/usr/bin/env python3
"""Capa 2: evaluación de informes semanales de los grupos de Ciberseguridad.

Orquesta `execution/evaluar_informes_grupos.py`: valida el descriptor, exige
cobertura exacta, compila el acta en un directorio aislado, verifica el PDF y
deja trazabilidad por run_id. Aquí no se decide la nota: la calcula la capa 3.

Uso:
    python3 flujo_evaluar_informes_grupos.py --descriptor <yaml> [--json]

Códigos de salida: 0 ok · 1 E/S o verificación · 3 configuración ·
4 red/credenciales · 5 JSON del modelo inválido · 6 cobertura incompleta.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
EJECUCION = RAIZ / "execution"
PYTHON = sys.executable
SCRIPT = EJECUCION / "evaluar_informes_grupos.py"
SESION_LOG = EJECUCION / "sesion_log.py"
VERIFICADOR = EJECUCION / "verificar_pdf.py"
ALERTA = EJECUCION / "alert_user.py"

sys.path.insert(0, str(EJECUCION))
import run_state  # noqa: E402

DESCRIPCION = {
    0: "evaluación completada",
    1: "error de E/S o verificación del PDF",
    3: "descriptor/rúbrica inválidos",
    4: "red o credenciales",
    5: "JSON del modelo inválido",
    6: "cobertura incompleta de grupos",
}


def _trazar(run_id: str, tipo: str, datos: dict) -> None:
    try:
        subprocess.run(
            [PYTHON, str(SESION_LOG), "add", "--run", run_id, "--tipo", tipo,
             "--datos", json.dumps(datos, ensure_ascii=False)],
            cwd=RAIZ, capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        pass  # la traza es un andamio; no tumba el flujo


def _ejecutar_script(args: argparse.Namespace, acta_tex: Path) -> tuple[int, dict]:
    cmd = [
        PYTHON, str(SCRIPT), "--descriptor", str(args.descriptor),
        "--salida-json", str(args.salida_json), "--acta-tex", str(acta_tex), "--json",
    ]
    if args.desde_json:
        cmd.append("--desde-json")
    proc = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True)
    lineas = [ln for ln in proc.stdout.splitlines() if ln.strip().startswith("{")]
    resultado: dict = {}
    for linea in reversed(lineas):
        try:
            candidato = json.loads(linea)
        except json.JSONDecodeError:
            continue
        if "status" in candidato:
            resultado = candidato
            break
    if proc.returncode != 0 and not resultado:
        resultado = {
            "status": "error", "code": proc.returncode,
            "message": (proc.stderr or proc.stdout).strip()[:600],
        }
    return proc.returncode, resultado


def _verificar(resultado: dict, args: argparse.Namespace, acta_tex: Path) -> list[str]:
    """Verificación de las cosas que el script dijo haber escrito."""
    problemas: list[str] = []
    ruta_json = Path(resultado.get("salida_json", args.salida_json))
    if not ruta_json.is_file():
        return [f"No existe el JSON de evaluación: {ruta_json}"]
    datos = json.loads(ruta_json.read_text(encoding="utf-8"))
    grupos = datos.get("grupos", [])
    esperados = set()
    try:
        import yaml
        desc = yaml.safe_load(Path(args.descriptor).read_text(encoding="utf-8"))
        esperados = set(desc.get("grupos_esperados", []))
    except (OSError, ValueError) as exc:
        problemas.append(f"No se pudo releer el descriptor: {exc}")
    encontrados = {g.get("grupo") for g in grupos}
    if esperados and encontrados != esperados:
        problemas.append(
            f"Cobertura {sorted(encontrados)} != esperada {sorted(esperados)}"
        )
    if len(grupos) != len(encontrados):
        problemas.append("Hay grupos repetidos en el JSON")
    for g in grupos:
        if not g.get("nota", {}).get("nota_fiable"):
            problemas.append(f"G{g.get('grupo')} sin nota fiable")
        if not g.get("items"):
            problemas.append(f"G{g.get('grupo')} sin ítems evaluados")
    if not acta_tex.is_file():
        problemas.append(f"No existe el acta LaTeX: {acta_tex}")
    return problemas


def _compilar(acta_tex: Path, semana: int) -> tuple[Path | None, dict]:
    """Compila aislado y valida el .log: en nonstopmode el PDF puede mentir."""
    sys.path.insert(0, str(EJECUCION))
    from compile_latex import compile_latex_code

    job = f"informes_grupos_semana_{semana:02d}"
    build = RAIZ / ".tmp" / "latex_build" / job
    res = compile_latex_code(
        acta_tex.read_text(encoding="utf-8"), job_name=job,
        output_dir=str(build), clean=False,
    )
    if not res.get("success"):
        return None, {"status": "error", "motivo": str(res.get("error", "pdflatex falló"))}
    pdf = build / f"{job}.pdf"
    log = build / f"{job}.log"
    proc = subprocess.run(
        [PYTHON, str(VERIFICADOR), "--pdf", str(pdf), "--log", str(log)],
        cwd=RAIZ, capture_output=True, text=True,
    )
    try:
        informe = json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        informe = {"status": "error", "message": proc.stdout[-300:]}
    return (pdf, informe) if informe.get("status") == "ok" else (None, informe)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--descriptor", required=True, help="YAML privado de los 4 grupos")
    parser.add_argument("--salida-json",
                        default=".tmp/evaluacion_informes_grupos/evaluacion.json")
    parser.add_argument("--salida-dir", default=None,
                        help="Carpeta del acta (default: resultados/SEMANA_NN)")
    parser.add_argument("--desde-json", action="store_true",
                        help="Regenera el acta desde el JSON existente, sin llamar al modelo")
    parser.add_argument("--json", action="store_true", help="Salida final en JSON")
    parser.add_argument("--no-alert", action="store_true")
    args = parser.parse_args(argv)

    descriptor = Path(args.descriptor)
    if not descriptor.is_file():
        print(json.dumps({"status": "error", "code": 3,
                          "message": f"Descriptor no encontrado: {descriptor}"}))
        return 3
    try:
        import yaml
        desc = yaml.safe_load(descriptor.read_text(encoding="utf-8"))
        semana = int(desc["semana"])
    except (KeyError, ValueError, OSError) as exc:
        print(json.dumps({"status": "error", "code": 3,
                          "message": f"Descriptor inválido: {exc}"}))
        return 3

    salida_dir = Path(args.salida_dir) if args.salida_dir else (
        RAIZ / "cursos" / desc.get("curso", "CIBERSEGURIDAD") / "evaluaciones"
        / "resultados" / f"SEMANA_{semana:02d}"
    )
    acta_tex = salida_dir / "informes_grupos.tex"
    acta_pdf = salida_dir / "informes_grupos.pdf"

    run_id = run_state.run_id_de_la_corrida("evaluar-informes")
    ruta_estado = run_state.ruta_vista(run_id)
    _trazar(run_id, "flujo/inicio", {"descriptor": str(descriptor), "semana": semana})

    codigo, resultado = _ejecutar_script(args, acta_tex)
    problemas: list[str] = []
    if codigo == 0:
        problemas = _verificar(resultado, args, acta_tex)
        if problemas:
            codigo = 1
    if codigo == 0:
        pdf, informe_pdf = _compilar(acta_tex, semana)
        if pdf is None:
            codigo = 1
            problemas.append(f"PDF no verificado: {informe_pdf}")
        else:
            shutil.copy2(pdf, acta_pdf)

    estado = "ok" if codigo == 0 else "error"
    if ruta_estado is not None:
        run_state.escribir_vista(ruta_estado, {
            "run_id": run_id,
            "current_step": 4 if codigo == 0 else 3,
            "status": estado,
            "exit_code": codigo,
            "semana": semana,
            "problemas": problemas,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
    _trazar(run_id, "flujo/fin", {
        "status": estado, "exit_code": codigo, "problemas": problemas,
        "acta": str(acta_pdf) if codigo == 0 else None,
    })
    if codigo == 0 and not args.no_alert:
        subprocess.run([PYTHON, str(ALERTA), "success"], cwd=RAIZ,
                       capture_output=True, text=True)

    salida = {
        "status": "ok" if codigo == 0 else "error",
        "code": codigo,
        "descripcion": DESCRIPCION.get(codigo, "estado desconocido"),
        "run_id": run_id,
        "acta_tex": str(acta_tex),
        "acta_pdf": str(acta_pdf) if codigo == 0 else None,
        "problemas": problemas,
    }
    print(json.dumps(salida, ensure_ascii=False, indent=2 if args.json else None))
    return codigo


if __name__ == "__main__":
    sys.exit(main())
