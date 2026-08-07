#!/usr/bin/env python3
"""
flujo_empaquetar_dataset.py — Orquestador del flujo de empaquetado (Layer 2)

Ejecuta el pipeline definido en la directiva empaquetar_dataset.yaml:
  1. empaquetar_dataset.py → genera paquetes HF (Parquet + dataset_info + README + LICENSE)
  2. alert_user.py          → notifica al usuario con alerta audible (éxito/error)

Uso:
    python3 flujo_empaquetar_dataset.py                      # parquet, licencia GIDEAL-1.0
    python3 flujo_empaquetar_dataset.py --format jsonl --license apache-2.0
    python3 flujo_empaquetar_dataset.py --pack --dry-run --no-alert

Guarda el progreso en .tmp/run_state.json.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Configuración ──────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.resolve()
PYTHON     = sys.executable
EMPAQUETAR = SCRIPT_DIR / "execution" / "empaquetar_dataset.py"
ALERTAR    = SCRIPT_DIR / "execution" / "alert_user.py"
TMP_DIR    = SCRIPT_DIR / ".tmp"
STATE_FILE = TMP_DIR / "run_state.json"


# ── Utilidades ──────────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_state(state: dict) -> None:
    TMP_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Orquestador ────────────────────────────────────────────────────────────────

def flujo_empaquetar(
    fmt: str,
    licencia: str,
    autor: str,
    version: str,
    pack: bool,
    dry_run: bool,
    alert: bool,
) -> int:
    run_id = f"flujo-empaquetar-{now_iso()[:19].replace(':', '-')}"
    state = {
        "run_id": run_id,
        "directive": "empaquetar_dataset.yaml",
        "started_at": now_iso(),
        "last_updated": now_iso(),
        "current_step": 0,
        "steps_completed": [],
        "steps_failed": [],
        "context": {"formato": fmt, "licencia": licencia, "autor": autor, "version": version,
                    "pack": pack, "dry_run": dry_run},
    }
    save_state(state)

    # ══ PASO 1: Empaquetado ═══════════════════════════════════════════════════
    bar = "─" * 56
    print(f"\n{bar}")
    print(f"  Paso 1/2  │  Empaquetando datasets (formato={fmt}, licencia={licencia})")
    print(f"{bar}")

    cmd = [
        PYTHON, str(EMPAQUETAR),
        "--format", fmt,
        "--license", licencia,
        "--author", autor,
        "--version", version,
    ]
    if pack:
        cmd.append("--pack")
    if dry_run:
        cmd.append("--dry-run")

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    code = result.returncode

    if code != 0:
        tail = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "Sin salida"
        print(f"  ❌  Falló empaquetar_dataset.py (código {code}): {tail}", file=sys.stderr)
        if result.stderr.strip():
            print(f"      stderr: {result.stderr.strip()[:300]}", file=sys.stderr)
        state["steps_failed"].append({"step": 1, "script": "empaquetar_dataset.py", "code": code})
        state["last_updated"] = now_iso()
        save_state(state)
        if alert:
            subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return code

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        data = {}

    paquetes = data.get("paquetes", {})
    print(f"  ✅  Empaquetado completado — {len(paquetes)} paquete(s)")
    for nombre, p in paquetes.items():
        print(f"      • {nombre}: {p['registros']} registros | licencia {p['licencia']} | {p['formato']}")

    state["current_step"] = 1
    state["steps_completed"].append({"step": 1, "script": "empaquetar_dataset.py", "status": "ok", **data})
    state["last_updated"] = now_iso()
    save_state(state)

    # ══ PASO 2: Notificación ═══════════════════════════════════════════════════
    print(f"\n{bar}")
    print("  Paso 2/2  │  Notificando al usuario...")
    print(f"{bar}")
    if alert:
        subprocess.run([PYTHON, str(ALERTAR), "success"], capture_output=True)
        print("  ✅ Alerta de completado emitida.")
    else:
        print("  (alerta desactivada por --no-alert)")

    state["current_step"] = 2
    state["steps_completed"].append({"step": 2, "script": "alert_user.py", "status": "ok",
                                     "tipo": "success" if alert else "none"})
    state["last_updated"] = now_iso()
    save_state(state)

    # ══ RESUMEN FINAL ══════════════════════════════════════════════════════════
    print(f"\n{'═' * 56}")
    print("  FLUJO COMPLETADO — Empaquetado de datasets")
    print(f"{'═' * 56}")
    print(f"  Paquetes    : {len(paquetes)}")
    print(f"  Formato     : {fmt}  |  Licencia: {licencia}")
    print(f"  Salida      : datasets/paquetes/")
    print(f"  Dry Run     : {dry_run}")
    print(f"{'═' * 56}\n")

    return 0


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Flujo completo: empaqueta los datasets curados con licencia y notifica.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--format", dest="fmt", default="parquet", choices=["jsonl", "parquet"],
                        help="Formato de almacenamiento de las muestras (default: parquet).")
    parser.add_argument("--license", default="custom-proprietary",
                        help="Licencia a aplicar (default: custom-proprietary).")
    parser.add_argument("--author", default="GIDEAL — Grupo de Investigación y Desarrollo Electrónico",
                        help="Autor/entidad propietaria.")
    parser.add_argument("--version", default="1.0.0", help="Versión del paquete.")
    parser.add_argument("--pack", action="store_true",
                        help="Además, genera un archivo .tar.gz por dataset.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo reportar el resultado sin escribir archivos.")
    parser.add_argument("--no-alert", action="store_true",
                        help="No emitir alerta sonora al terminar.")
    args = parser.parse_args()

    return flujo_empaquetar(
        fmt=args.fmt,
        licencia=args.license,
        autor=args.author,
        version=args.version,
        pack=args.pack,
        dry_run=args.dry_run,
        alert=not args.no_alert,
    )


if __name__ == "__main__":
    sys.exit(main())