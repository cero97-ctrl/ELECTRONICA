#!/usr/bin/env python3
"""
flujo_imagen_a_kicad.py — Orquestador del flujo Imagen a KiCAD (Layer 2)

Ejecuta el flujo completo definido en la directiva imagen_a_kicad.yaml:
  1. extraer_netlist_imagen.py  → Analiza imagen y obtiene Netlist en JSON
  2. generar_kicad_sch.py       → Convierte el JSON en esquemático .kicad_sch
  3. alert_user.py              → Notifica al usuario con alerta audible

Uso:
    python3 flujo_imagen_a_kicad.py circuito.png
    python3 flujo_imagen_a_kicad.py esquema.jpg --modelo gemini-1.5-pro

El archivo .kicad_sch se guarda en docs/KICAD/ por defecto.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Configuración ──────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent.resolve()
PYTHON       = "/home/cero/anaconda3/bin/python3"
EXTRAER      = SCRIPT_DIR / "execution" / "extraer_netlist_imagen.py"
GENERAR      = SCRIPT_DIR / "execution" / "generar_kicad_sch.py"
GENERAR_LLM  = SCRIPT_DIR / "execution" / "generar_kicad_llm.py"
ALERTAR      = SCRIPT_DIR / "execution" / "alert_user.py"
TMP_DIR      = SCRIPT_DIR / ".tmp"
STATE_FILE   = TMP_DIR / "run_state.json"
DEFAULT_OUT  = SCRIPT_DIR / "docs" / "KICAD"


# ── Utilidades ─────────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def print_step(num: int, total: int, desc: str) -> None:
    bar = "─" * 56
    print(f"\n{bar}")
    print(f"  Paso {num}/{total}  │  {desc}")
    print(f"{bar}")


def print_ok(msg: str) -> None:
    print(f"  ✅  {msg}")


def print_err(msg: str) -> None:
    print(f"  ❌  {msg}", file=sys.stderr)


def save_state(state: dict) -> None:
    TMP_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def run_script(cmd: list[str], capture_json: bool = False) -> tuple[int, dict | str]:
    """Ejecuta un script y retorna (returncode, resultado)."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if capture_json:
        try:
            data = json.loads(result.stdout)
            return result.returncode, data
        except json.JSONDecodeError:
            return result.returncode, {"raw_output": result.stdout, "stderr": result.stderr}
    return result.returncode, result.stdout


# ── Orquestador ────────────────────────────────────────────────────────────────

def flujo_completo(
    imagenes: str,
    modelo: str,
    api_backend: str,
    output_dir: Path,
    use_llm_gen: bool = False,
) -> int:
    """Ejecuta los pasos del flujo."""

    run_id = f"flujo-kicad-{now_iso()[:19].replace(':', '-')}"
    _partes = [Path(p.strip()).stem for p in imagenes.split(",")]
    nombre_base = f"kicad_{'_'.join(_partes).replace('*', 'glob')}"
    json_tmp    = TMP_DIR / f"{nombre_base}.json"
    output_sch  = output_dir / f"{nombre_base}.kicad_sch"

    state = {
        "run_id": run_id,
        "directive": "imagen_a_kicad.yaml",
        "imagenes": imagenes,
        "started_at": now_iso(),
        "last_updated": now_iso(),
        "current_step": 0,
        "steps_completed": [],
        "steps_failed": [],
        "context": {},
    }
    save_state(state)

    total_pasos = 3

    # ══ PASO 1: Extraer Netlist ════════════════════════════════════════════════
    print_step(1, total_pasos, f"Extrayendo Netlist con {modelo}...")
    
    cmd_extraer = [
        PYTHON, str(EXTRAER),
        imagenes,
        "--modelo", modelo,
        "--api-backend", api_backend,
    ]

    code, analisis = run_script(cmd_extraer, capture_json=True)

    if code != 0 or analisis.get("status") != "ok":
        if api_backend == "groq":
            print_err("Falló Groq. Intentando con Gemini...")
            cmd_fallback = list(cmd_extraer)
            if "--api-backend" in cmd_fallback:
                cmd_fallback[cmd_fallback.index("--api-backend") + 1] = "gemini"
            if "--modelo" in cmd_fallback:
                cmd_fallback[cmd_fallback.index("--modelo") + 1] = "gemini-2.5-flash"
            code, analisis = run_script(cmd_fallback, capture_json=True)
            
        if code != 0 or analisis.get("status") != "ok":
            msg = analisis.get("message", analisis.get("raw_output", "Error desconocido"))
            print_err(f"Falló extraer_netlist_imagen.py (código {code}): {msg}")
            subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
            return code if code != 0 else 1

    TMP_DIR.mkdir(exist_ok=True)
    json_tmp.write_text(json.dumps(analisis, ensure_ascii=False, indent=2), encoding="utf-8")

    comps = analisis.get("analisis", {}).get("components", [])
    conns = analisis.get("analisis", {}).get("connections", [])
    print_ok(f"Netlist extraído — Componentes: {len(comps)} | Conexiones: {len(conns)}")

    state["steps_completed"].append({"step": 1, "script": "extraer_netlist", "status": "ok"})
    save_state(state)

    # ══ PASO 2: Generar KiCAD ═════════════════════════════════════════════════
    if use_llm_gen:
        print_step(2, total_pasos, f"Generando esquemático KiCAD 8.0.9 usando LLM ({modelo})...")
        cmd_generar = [
            PYTHON, str(GENERAR_LLM),
            "--json", str(json_tmp),
            "--output", str(output_sch),
            "--modelo", modelo,
            "--api-backend", api_backend,
        ]
    else:
        print_step(2, total_pasos, "Generando esquemático KiCAD 8.0.9...")
        cmd_generar = [
            PYTHON, str(GENERAR),
            "--json", str(json_tmp),
            "--output", str(output_sch),
        ]

    code, result_kicad = run_script(cmd_generar, capture_json=True)

    if code != 0 or result_kicad.get("status") != "ok":
        msg = result_kicad.get("message", result_kicad.get("raw_output", "Error desconocido"))
        print_err(f"Falló generar_kicad_sch.py (código {code}): {msg}")
        subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return code if code != 0 else 1

    print_ok(f"Esquemático generado: {output_sch}")
    state["steps_completed"].append({"step": 2, "script": "generar_kicad_sch", "status": "ok"})
    save_state(state)

    # ══ PASO 3: Alerta de completado ═══════════════════════════════════════════
    print_step(3, total_pasos, "Notificando al usuario...")
    subprocess.run([PYTHON, str(ALERTAR), "success"], capture_output=True)
    print_ok("Alerta de completado emitida.")

    # ══ RESUMEN FINAL ══════════════════════════════════════════════════════════
    bar = "═" * 56
    print(f"\n{bar}")
    print("  FLUJO COMPLETADO — Imagen a KiCAD")
    print(f"{bar}")
    print(f"  Esquemático KiCAD : {output_sch}")
    print(f"{bar}\n")
    print("  💡 Para visualizarlo, abre el archivo en KiCAD 8.0.9:")
    print(f"     kicad-cli sch export pdf {output_sch} -o {output_sch.with_suffix('.pdf')} && xdg-open {output_sch.with_suffix('.pdf')}\n")

    return 0


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Flujo completo: convierte imagen de circuito a KiCAD 8.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("imagenes", help="Ruta(s) a las imágenes separadas por coma.")
    parser.add_argument("--modelo", default="gemini-2.5-flash")
    parser.add_argument("--api-backend", default="gemini", choices=["gemini", "openrouter", "groq"])
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--use-llm-gen", action="store_true", help="Usa LLM para generar el esquemático (generar_kicad_llm.py) en lugar del script determinista.")
    return parser.parse_args()


def main():
    args = parse_args()
    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUT
    output_dir.mkdir(parents=True, exist_ok=True)

    code = flujo_completo(
        imagenes=args.imagenes,
        modelo=args.modelo,
        api_backend=args.api_backend,
        output_dir=output_dir,
        use_llm_gen=args.use_llm_gen,
    )
    sys.exit(code)

if __name__ == "__main__":
    main()
