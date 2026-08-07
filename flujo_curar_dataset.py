#!/usr/bin/env python3
"""
flujo_curar_dataset.py — Orquestador del flujo de curado de datasets (Layer 2)

Ejecuta el pipeline definido en la directiva curar_dataset.yaml:
  1. curar_datasets.py   → cura, deduplica y particiona datasets/ → datasets/curated/
  2. alert_user.py        → notifica al usuario con alerta audible (éxito/error)

Uso:
    python3 flujo_curar_dataset.py                     # cura con defaults (quality≥0.7, 80-10-10)
    python3 flujo_curar_dataset.py --min-quality 0.8
    python3 flujo_curar_dataset.py --dry-run           # solo reportar, sin escribir
    python3 flujo_curar_dataset.py --no-alert          # sin alerta audible

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
CURAR      = SCRIPT_DIR / "execution" / "curar_datasets.py"
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

def flujo_curar(
    min_quality: float,
    split: str,
    seed: int,
    dry_run: bool,
    alert: bool,
) -> int:
    run_id = f"flujo-curar-{now_iso()[:19].replace(':', '-')}"
    state = {
        "run_id": run_id,
        "directive": "curar_dataset.yaml",
        "started_at": now_iso(),
        "last_updated": now_iso(),
        "current_step": 0,
        "steps_completed": [],
        "steps_failed": [],
        "context": {"min_quality": min_quality, "split": split, "seed": seed, "dry_run": dry_run},
    }
    save_state(state)

    # ══ PASO 1: Curado ═══════════════════════════════════════════════════════
    bar = "─" * 56
    print(f"\n{bar}")
    print(f"  Paso 1/2  │  Curando datasets (min_quality={min_quality}, split={split})")
    print(f"{bar}")

    cmd = [
        PYTHON, str(CURAR),
        "--min-quality", str(min_quality),
        "--split", split,
        "--seed", str(seed),
    ]
    if dry_run:
        cmd.append("--dry-run")

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    code = result.returncode

    if code != 0:
        # Estado conocido de curar_datasets.py: 1 sin datos, 2 configuración.
        tail = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "Sin salida"
        print(f"  ❌  Falló curar_datasets.py (código {code}): {tail}", file=sys.stderr)
        if result.stderr.strip():
            print(f"      stderr: {result.stderr.strip()[:300]}", file=sys.stderr)
        state["steps_failed"].append({"step": 1, "script": "curar_datasets.py", "code": code})
        state["last_updated"] = now_iso()
        save_state(state)
        if alert:
            subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return code

    # Parsear el JSON de resultados
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        data = {"curados": "N/A", "rechazados": {}, "splits": {}, "por_dataset": {}}

    print(f"  ✅  Curado completado — crudos: {data.get('crudos', '?')} | curados: {data.get('curados', '?')}")
    print(f"      Rechazados: {json.dumps(data.get('rechazados', {}), ensure_ascii=False)}")
    print(f"      Splits (train/val/test): {data.get('splits', {})}")

    state["current_step"] = 1
    state["steps_completed"].append({"step": 1, "script": "curar_datasets.py", "status": "ok", **data})
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
    state["steps_completed"].append({"step": 2, "script": "alert_user.py", "status": "ok", "tipo": "success" if alert else "none"})
    state["last_updated"] = now_iso()
    save_state(state)

    # ══ RESUMEN FINAL ══════════════════════════════════════════════════════════
    print(f"\n{'═' * 56}")
    print("  FLUJO COMPLETADO — Curado de datasets")
    print(f"{'═' * 56}")
    print(f"  Crudos      : {data.get('crudos', '?')}")
    print(f"  Curados     : {data.get('curados', '?')}")
    print(f"  Salida      : {data.get('salida', 'datasets/curated/')}")
    print(f"  Dry Run     : {dry_run}")
    print(f"{'═' * 56}\n")

    return 0


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Flujo completo: cura y particiona los datasets capturados, y notifica.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--min-quality", type=float, default=0.7,
                        help="Cota mínima de quality_score (default: 0.7).")
    parser.add_argument("--split", default="80-10-10",
                        help="Proporción train-val-test (default: 80-10-10).")
    parser.add_argument("--seed", type=int, default=42, help="Semilla aleatoria (default: 42).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo reportar el resultado sin escribir archivos curados.")
    parser.add_argument("--no-alert", action="store_true",
                        help="No emitir alerta sonora al terminar.")
    args = parser.parse_args()

    return flujo_curar(
        min_quality=args.min_quality,
        split=args.split,
        seed=args.seed,
        dry_run=args.dry_run,
        alert=not args.no_alert,
    )


if __name__ == "__main__":
    sys.exit(main())