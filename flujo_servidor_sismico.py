#!/usr/bin/env python3
"""
flujo_servidor_sismico.py — Orquestador del servidor MCP sismológico (Layer 2)

Capa de decisión/validación del flujo definido en directives/servidor_sismico.yaml:
  1. generar   -> crea el catálogo sismico sintético determinista en docs/SISMOLOGIA_MCP/
  2. iniciar   -> valida cátalogo y lanza execution/servidor_sismico.py (stdio o streamable-http)
  3. estado    -> muestra el estado del último lanzamiento (.tmp/run_state_sismico.json)

La lógica de datos vive en execution/servidor_sismico.py; este script NO raspea ni
genera catálogos por sí mismo: solo decide y valida.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
TMP_DIR = SCRIPT_DIR / ".tmp"
STATE_FILE = TMP_DIR / "run_state_sismico.json"
SCRIPT_3 = SCRIPT_DIR / "execution" / "servidor_sismico.py"
DEFAULT_CATALOGO_DIR = SCRIPT_DIR / "docs" / "SISMOLOGIA_MCP"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_state(state: dict) -> None:
    TMP_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def leer_estado() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def print_paso(titulo: str) -> None:
    bar = "─" * 56
    print(f"\n{bar}\n  {titulo}\n{bar}")


def cmd_generar(output_dir: str | None, force: bool) -> int:
    out = Path(output_dir) if output_dir else DEFAULT_CATALOGO_DIR
    out.mkdir(parents=True, exist_ok=True)
    destino = out / "catalogo_sismico.json"
    if destino.exists() and not force:
        print(f"El catálogo ya existe en {destino}. Usa --force para sobrescribirlo.")
        return 0

    print_paso("Paso 1/2  │  Generando catálogo sismico sintético (determinista)")
    res = subprocess.run(
        [sys.executable, str(SCRIPT_3), "--generar-sintetico", str(out)],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
        save_state({"accion": "generar", "exit_code": res.returncode, "timestamp": now_iso()})
        return res.returncode

    try:
        salida = json.loads(res.stdout)
    except json.JSONDecodeError:
        print("Salida inesperada del script de generación.", file=sys.stderr)
        return 4

    total = salida.get("total_eventos", 0)
    print(f"  ✅  Catálogo generado: {salida.get('generado')} ({total} eventos)")
    save_state({
        "accion": "generar", "exit_code": 0, "timestamp": now_iso(),
        "catalogo": str(salida.get("generado")), "total_eventos": total, "sintetico": True,
    })
    print_paso("Paso 2/2  │  Validando catálogo (leídos, no duplicados)")
    _, n_ids = _validar_catalogo(Path(salida["generado"]))
    print(f"  ✅  Catálogo válido: {n_ids} ids únicos")
    return 0


def _validar_catalogo(ruta: Path):
    """Devuelve (lista_eventos, n_ids_unicos). Sale con código 1 si es inválido."""
    if not ruta.exists():
        print(f"ERROR: catálogo no encontrado: {ruta}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(ruta.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        print("ERROR: catálogo vacío o con formato inválido.", file=sys.stderr)
        sys.exit(1)
    ids = [e.get("id") for e in data if e.get("id")]
    if len(ids) != len(set(ids)):
        print("ERROR: hay ids duplicados en el catálogo.", file=sys.stderr)
        sys.exit(1)
    return data, len(ids)


def cmd_iniciar(transporte: str, host: str, port: int, catalogo: str | None) -> int:
    catalogo_arg = catalogo
    if catalogo_arg is None:
        # Por defecto, usar el sintético ya generado si existe; si no, el script genera en memoria.
        generado = DEFAULT_CATALOGO_DIR / "catalogo_sismico.json"
        if generado.exists():
            catalogo_arg = str(generado)
        else:
            print("AVISO: no hay catálogo generado; el servidor usará el sintético en memoria.")

    print_paso("Paso 1/2  │  Validando entradas y catálogo")
    if catalogo_arg:
        _validar_catalogo(Path(catalogo_arg))
        print(f"  ✅  Catálogo válido: {catalogo_arg}")
    else:
        print("  ℹ️   Catálogo sintético en memoria (provisional hasta prime impacto)")

    print_paso("Paso 2/2  │  Lanzando execution/servidor_sismico.py")
    save_state({
        "accion": "iniciar", "exit_code": None, "timestamp": now_iso(),
        "transporte": transporte, "host": host, "port": port,
        "catalogo": catalogo_arg, "proceso": "lanzado",
    })

    cmd = [sys.executable, str(SCRIPT_3),
           "--transporte", transporte, "--host", host, "--port", str(port)]
    if catalogo_arg:
        cmd += ["--catalogo", catalogo_arg]

    print("  🚀  " + " ".join(cmd))
    print("      (Ctrl+C para detener)")
    try:
        proc = subprocess.run(cmd)
        save_state({
            "accion": "iniciar", "exit_code": proc.returncode, "timestamp": now_iso(),
            "transporte": transporte, "host": host, "port": port,
            "catalogo": catalogo_arg, "proceso": "terminado",
        })
        return proc.returncode
    except KeyboardInterrupt:
        save_state({
            "accion": "iniciar", "exit_code": 130, "timestamp": now_iso(),
            "transporte": transporte, "host": host, "port": port,
            "catalogo": catalogo_arg, "proceso": "interrumpido",
        })
        return 130


def cmd_estado() -> int:
    estado = leer_estado()
    if not estado:
        print("No hay estado registrado todavía.")
        return 0
    print(json.dumps(estado, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Orquestador del servidor MCP sismológico.")
    sub = parser.add_subparsers(dest="accion", required=True)

    p_gen = sub.add_parser("generar", help="Generar el catálogo sismico sintético.")
    p_gen.add_argument("--output", default=None, help="Directorio destino (default docs/SISMOLOGIA_MCP).")
    p_gen.add_argument("--force", action="store_true", help="Sobrescribir si ya existe.")

    p_ini = sub.add_parser("iniciar", help="Lanzar el servidor MCP.")
    p_ini.add_argument("--transporte", choices=["stdio", "streamable-http"], default="stdio")
    p_ini.add_argument("--host", default="127.0.0.1")
    p_ini.add_argument("--port", type=int, default=8000)
    p_ini.add_argument("--catalogo", default=None, help="Catálogo real (JSON/CSV).")

    sub.add_parser("estado", help="Mostrar el último estado registrado.")

    args = parser.parse_args()

    if args.accion == "generar":
        return cmd_generar(args.output, args.force)
    if args.accion == "iniciar":
        return cmd_iniciar(args.transporte, args.host, args.port, args.catalogo)
    if args.accion == "estado":
        return cmd_estado()
    return 2


if __name__ == "__main__":
    sys.exit(main())