#!/usr/bin/env python3
"""Orquestador de la verificacion de corrupcion de texto.

Capa 2 del flujo definido en directives/verificar_texto_corrupto.yaml. No
detecta nada: delega todo el trabajo en execution/verificar_texto.py y se
limita a decidir que significa el codigo de salida y a registrar la pasada.

La decision de cobertura es una funcion pura, sin opinion: un informe sin
ficheros escaneados NO es un informe limpio, es un informe que no comprobo
nada, y por tanto es el peor resultado posible porque parece el mejor.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SCRIPT = PROJECT_ROOT / "execution" / "verificar_texto.py"
TMP = PROJECT_ROOT / ".tmp"
INFORME = TMP / "verificacion_texto.json"
SESION_LOG = PROJECT_ROOT / "execution" / "sesion_log.py"
PYTHON = sys.executable

# La vista de estado vive en `execution/run_state.py` (capa 3): nombre por
# corrida, escritura atomica y validacion del `run_id` en un solo sitio.
sys.path.insert(0, str(PROJECT_ROOT / "execution"))
import run_state as RS  # noqa: E402  (capa 3, resolucion explicita)

CODIGO_OK = 0
CODIGO_HALLAZGOS = 1
CODIGO_SIN_VERIFICAR = 2


def trazar(run_id: str, tipo: str, datos: dict | None = None) -> bool:
    """Trazabilidad append-only. Falla blanda: devuelve False, nunca tumba el flujo."""
    cmd = [PYTHON, str(SESION_LOG), "add", "--run", run_id, "--tipo", tipo]
    if datos:
        try:
            cmd += ["--datos", json.dumps(datos, ensure_ascii=False)]
        except (TypeError, ValueError):
            pass
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def contrastar_cobertura(informe: dict) -> tuple[str, str]:
    """Decision pura sobre si el informe es creible. Sin heuristicas.

    Devuelve (veredicto, motivo). Un veredicto distinto de 'limpio' no es un
    fallo del script: es la advertencia de que el verde no esta soportado por
    ninguna lectura de ficheros.
    """
    if informe.get("estado") == "sin_verificar":
        return "sin_verificar", str(informe.get("motivo", "sin motivo declarado"))

    cobertura = informe.get("cobertura", {})
    ficheros = int(cobertura.get("ficheros_escaneados", 0))
    lineas = int(cobertura.get("lineas_escaneadas", 0))
    hallazgos = informe.get("hallazgos", [])

    motivos = cobertura.get("motivos_omision", {}) or {}
    # Los ficheros meta se excluyen por diseño y están documentados como
    # tales: avisar de ellos convertiría cada pasada en un aviso que hay que
    # aprender a ignorar. Solo preocupan los omissions que nadie decidió.
    meta = int(motivos.get("fichero_meta", 0))
    relevantes = (
        int(motivos.get("ilegible", 0))
        + int(motivos.get("tope_max_ficheros", 0))
    )
    no_texto = int(cobertura.get("ficheros_no_texto", 0))

    if ficheros == 0 or lineas == 0:
        return "sin_verificar", "el informe declara 0 ficheros o 0 lineas"
    if hallazgos:
        return "con_hallazgos", f"{len(hallazgos)} hallazgos en {ficheros} ficheros"
    if relevantes:
        return "limpio_con_omisiones", (
            f"{relevantes} ficheros omitidos sin decision (ilegibles o por tope); "
            "revisarlos antes de dar por buena la pasada"
        )
    detalle = f"{ficheros} ficheros, {lineas} lineas leidas"
    if no_texto:
        detalle += f"; {no_texto} ficheros no textuales no se leen"
    if meta:
        detalle += f"; {meta} ficheros meta excluidos por diseño"
    return "limpio", detalle


def cargar_informe(stdout: str) -> dict:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"estado": "ilegible", "salida_cruda": stdout[:2000], "hallazgos": []}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Verifica corrupcion de prosa antes de que llegue a un commit."
    )
    ap.add_argument("rutas", nargs="*", help="Ficheros o directorios a escanear.")
    ap.add_argument("--diff", metavar="REF", help="Escanea las lineas anadidas tras REF.")
    ap.add_argument("--class", dest="clases", action="append", default=None,
                    choices=["script", "conocido", "camel"])
    ap.add_argument("--known-file", type=Path, help="Detecciones adicionales en JSON.")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--max-ficheros", type=int, default=4000)
    ap.add_argument("--json", action="store_true", help="Propagar la salida en JSON.")
    ap.add_argument("--silencioso", action="store_true", help="No mostrar el informe del script.")
    args = ap.parse_args(argv)

    if not SCRIPT.is_file():
        print(f"No se encuentra el script de ejecucion: {SCRIPT}", file=sys.stderr)
        return CODIGO_SIN_VERIFICAR

    cmd = [sys.executable, str(SCRIPT), *args.rutas,
           "--max-ficheros", str(args.max_ficheros), "--json"]
    if args.diff:
        cmd += ["--diff", args.diff]
    for clase in args.clases or []:
        cmd += ["--class", clase]
    if args.known_file:
        cmd += ["--known-file", str(args.known_file)]
    for ex in args.exclude:
        cmd += ["--exclude", ex]

    run_id = RS.run_id_de_la_corrida("verificar-texto")
    started_at = now_iso()
    trazar(run_id, "flujo/inicio", {"ficheros": len(args.rutas), "diff": args.diff,
                             "clases": args.clases or ["script", "conocido"]})

    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=900)
    if not args.silencioso and proc.stderr:
        print(proc.stderr.rstrip(), file=sys.stderr)

    informe = cargar_informe(proc.stdout) if proc.stdout.strip() else {
        "estado": "sin_salida", "hallazgos": [],
        "motivo": f"el script salio con codigo {proc.returncode} sin emitir informe",
    }

    veredicto, motivo = contrastar_cobertura(informe)
    estado = {
        "flujo": "verificar_texto",
        "veredicto": veredicto,
        "motivo": motivo,
        "script_exit": proc.returncode,
        "informe": informe,
        "finished_at": now_iso(),
    }
    TMP.mkdir(exist_ok=True)
    INFORME.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    state = {
        "run_id": run_id,
        "current_step": 3,
        "status": "terminado" if veredicto == "limpio" else "atencion",
        "flujo": "verificar_texto",
        "veredicto": veredicto,
        "exit_code": proc.returncode,
        "started_at": started_at,
        "updated_at": now_iso(),
    }
    # `run_id` es obligatorio en el estado: sin el, `estado_sesion.py` clasifica
    # la vista como corrupto (no puede casarla con su log append-only). El bug
    # se detecto al auditar con este mismo flujo, no al escribirlo. Con la vista
    # por corrida el `run_id` viaja ademas en el NOMBRE del fichero, que es
    # justo de donde lo saca `estado_sesion.py` para emparejar vista<->log.
    RS.escribir_vista(RS.ruta_vista(run_id), state)
    # Trazabilidad append-only: el log es la fuente de verdad y sobrevive a que
    # otro flujo escriba su propia vista en .tmp/.
    if not trazar(run_id, "flujo/fin", {"veredicto": veredicto, "exit_code": proc.returncode}):
        print("  aviso: no se pudo escribir en el log append-only", file=sys.stderr)

    if args.json:
        print(json.dumps(estado, ensure_ascii=False, indent=2))
    else:
        print(f"== Verificacion de texto: {veredicto} ==")
        print(f"  {motivo}")
        if veredicto == "sin_verificar":
            print("  El flujo NO ha comprobado nada. No tomes este resultado como evidencia de nada.")
        for h in informe.get("hallazgos", [])[:40]:
            print(f"  [{h['clase']}] {h['fichero']}:{h['linea']}:{h['columna']}  {h['detalle']}")
            print(f"      {h['fragmento']}")
        if len(informe.get("hallazgos", [])) > 40:
            print(f"  ... y {len(informe['hallazgos']) - 40} mas (informe completo en {INFORME})")
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
