#!/usr/bin/env python3
"""Orquestador ocr_a_practicas (Capa 2): convertir el markdown del OCR de
`practicas.pdf` en los ocho enunciados LaTeX de Laboratorio II.

Capa 3 (determinista): execution/generar_practicas_desde_ocr.py, que parsea el
markdown, valida la estructura, renderiza con el estilo infográfico del repo y
compila cada práctica. Este orquestador NO reimplementa nada de eso: valida
entradas, lanza el script, valida la salida (8 `.tex` + 8 `.pdf` con 0 errores
de compilación), guarda la vista por corrida en `.tmp/run_state_<run_id>.json` y
alerta.

El markdown es la fuente de verdad de las prácticas (decisión del usuario,
2026-11-21): contiene los enunciados que la Universidad exige y sustituye a los
`.tex` derivados de `curso.yaml` para las prácticas 1-8.

Sin coste de API: el OCR ya está hecho; aquí solo se parsea y se compila LaTeX.
No se consume OPENROUTER_API_KEY ni cuota de Gemini.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
GENERADOR = SCRIPT_DIR / "execution" / "generar_practicas_desde_ocr.py"
ALERTAR = SCRIPT_DIR / "execution" / "alert_user.py"

sys.path.insert(0, str(SCRIPT_DIR / "execution"))
import run_state as RS                # noqa: E402  (vista por corrida, capa 3)

OCR_POR_DEFECTO = SCRIPT_DIR / ".tmp" / "ocr_practicas" / "practicas_ocr.md"
SALIDA_POR_DEFECTO = SCRIPT_DIR / ".tmp" / "practicas_desde_ocr"


def guardar_vista(ruta: Path, run_id: str, paso: str, exit_code: int, detalle: str) -> None:
    RS.escribir_vista(ruta, {
        "run_id": run_id,
        "flujo": "ocr_a_practicas",
        "paso": paso,
        "exit_code": exit_code,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "detalle": detalle,
    })


def parsear_informe(stdout: str, stderr: str) -> dict | None:
    """El script de capa 3 imprime un único JSON por stdout (o stderr si falló)."""
    for bruto in (stdout, stderr):
        bruto = (bruto or "").strip()
        if not bruto:
            continue
        try:
            return json.loads(bruto)
        except json.JSONDecodeError:
            pass
        ini, fin = bruto.find("{"), bruto.rfind("}")
        if ini != -1 and fin > ini:
            try:
                return json.loads(bruto[ini:fin + 1])
            except json.JSONDecodeError:
                continue
    return None


def validar_entrega(salida: Path, numeros: list[int], compilar: bool) -> list[str]:
    """Comprueba que existan los `.tex` (y `.pdf`) de todas las prácticas pedidas."""
    problemas: list[str] = []
    for numero in numeros:
        tex = salida / f"practica_{numero:02d}.tex"
        if not tex.is_file() or tex.stat().st_size < 1000:
            problemas.append(f"falta o está vacío: {tex.name}")
        if compilar:
            pdf = salida / f"practica_{numero:02d}.pdf"
            if not pdf.is_file() or pdf.stat().st_size < 1000:
                problemas.append(f"falta o está vacío: {pdf.name}")
    return problemas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Genera las 8 prácticas de Lab II desde el markdown del OCR "
                    "(orquesta execution/generar_practicas_desde_ocr.py)"
    )
    ap.add_argument("--ocr", default=str(OCR_POR_DEFECTO), help="markdown del OCR")
    ap.add_argument("--salida", default=str(SALIDA_POR_DEFECTO), help="directorio de salida")
    ap.add_argument("--practicas", default=None, help="'1-8', '1,3,5-7' o 'todas'")
    ap.add_argument("--sin-compilar", action="store_true", help="solo escribir los .tex")
    ap.add_argument("--check", action="store_true", help="solo validar el OCR, sin escribir ni compilar")
    ap.add_argument("--dry-run", action="store_true", help="muestra el plan y sale")
    ap.add_argument("--no-alert", action="store_true", help="sin alerta audible")
    args = ap.parse_args(argv)

    ocr = Path(args.ocr).resolve()
    salida = Path(args.salida).resolve()
    if not ocr.is_file():
        print(json.dumps({"status": "error", "code": 1,
                          "message": f"no existe el markdown del OCR: {ocr}"},
                         ensure_ascii=False), file=sys.stderr)
        return 1

    # Rango por defecto = las 8 prácticas; la capa 3 es la fuente de verdad del
    # parseo, aquí solo se calcula para validar la entrega.
    numeros = list(range(1, 9))
    if args.practicas and args.practicas.strip().lower() != "todas":
        try:
            numeros = []
            for parte in args.practicas.split(","):
                parte = parte.strip()
                if "-" in parte:
                    ini, fin = parte.split("-", 1)
                    numeros.extend(range(int(ini), int(fin) + 1))
                else:
                    numeros.append(int(parte))
            numeros = sorted(set(n for n in numeros if 1 <= n <= 8))
        except ValueError:
            print(json.dumps({"status": "error", "code": 1,
                              "message": "rango de prácticas inválido"},
                             ensure_ascii=False), file=sys.stderr)
            return 1

    cmd = [sys.executable, str(GENERADOR), "--ocr", str(ocr),
           "--salida", str(salida), "--json"]
    if args.practicas:
        cmd += ["--practicas", args.practicas]
    if args.sin_compilar:
        cmd.append("--sin-compilar")
    if args.check:
        cmd.append("--check")

    if args.check or args.dry_run:
        if args.dry_run:
            print(json.dumps({
                "status": "ok",
                "ocr": str(ocr),
                "salida": str(salida),
                "practicas": numeros,
                "compilar": not args.sin_compilar,
                "comando": " ".join(cmd),
                "coste": "ninguno (parseo + compilación local; sin API)",
            }, ensure_ascii=False, indent=2))
            return 0
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        print(proc.stdout or proc.stderr)
        return proc.returncode

    run_id = RS.run_id_de_la_corrida("ocr_a_practicas")
    vista = RS.ruta_vista(run_id)

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        guardar_vista(vista, run_id, "1_generar", 30, "timeout de 1800 s")
        print(json.dumps({"status": "error", "code": 30,
                          "message": "timeout generando/compilando las prácticas"},
                         ensure_ascii=False), file=sys.stderr)
        return 30

    informe = parsear_informe(proc.stdout, proc.stderr)
    if informe is None:
        informe = {"status": "error", "code": 3,
                   "message": ((proc.stdout or "") + (proc.stderr or ""))[:500]}
    codigo = proc.returncode
    guardar_vista(vista, run_id, "1_generar", codigo,
                  (proc.stdout or proc.stderr or "").strip()[:300])

    if codigo == 0:
        problemas = validar_entrega(salida, numeros, compilar=not args.sin_compilar)
        guardar_vista(vista, run_id, "2_validar", 0 if not problemas else 4,
                      "; ".join(problemas)[:300])
        if problemas:
            informe = {"status": "error", "code": 4,
                       "message": "entrega incompleta", "problemas": problemas}
            codigo = 4
        else:
            informe["validacion"] = (
                f"{len(numeros)} prácticas con .tex"
                + (" y .pdf" if not args.sin_compilar else "") + " verificados"
            )

    print(json.dumps(informe, ensure_ascii=False, indent=2))

    if not args.no_alert:
        subprocess.run([sys.executable, str(ALERTAR),
                        "success" if codigo == 0 else "waiting"])
    return codigo


if __name__ == "__main__":
    sys.exit(main())
