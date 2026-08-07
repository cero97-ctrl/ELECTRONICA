#!/usr/bin/env python3
"""
flujo_publicar_hf.py — Orquestador del flujo de publicación en HF Hub (Layer 2)

Ejecuta el pipeline definido en la directiva publicar_hf.yaml:
  1. publicar_hf.py → sube datasets/paquetes/<dataset> a Hugging Face Hub
  2. alert_user.py   → notifica al usuario con alerta audible (éxito/error)

Requiere HF_TOKEN en .env o exportado en el entorno.

Uso:
    python3 flujo_publicar_hf.py rag_conversaciones --repo gideal/gideal-rag-v1
    python3 flujo_publicar_hf.py eda_imagen_circuito --private --dry-run --no-alert

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
PUBLICAR   = SCRIPT_DIR / "execution" / "publicar_hf.py"
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

def flujo_publicar(
    dataset: str,
    repo_id: str,
    private: bool,
    dry_run: bool,
    alert: bool,
) -> int:
    run_id = f"flujo-publicar-{now_iso()[:19].replace(':', '-')}"
    state = {
        "run_id": run_id,
        "directive": "publicar_hf.yaml",
        "started_at": now_iso(),
        "last_updated": now_iso(),
        "current_step": 0,
        "steps_completed": [],
        "steps_failed": [],
        "context": {"dataset": dataset, "repo_id": repo_id, "private": private, "dry_run": dry_run},
    }
    save_state(state)

    # ══ PASO 1: Publicación ═══════════════════════════════════════════════════
    bar = "─" * 56
    print(f"\n{bar}")
    print(f"  Paso 1/2  │  Publicando '{dataset}' en Hugging Face Hub")
    print(f"{bar}")

    cmd = [PYTHON, str(PUBLICAR), dataset, "--repo", repo_id]
    if private:
        cmd.append("--private")
    if dry_run:
        cmd.append("--dry-run")

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    code = result.returncode

    if code != 0:
        try:
            msg = json.loads(result.stdout).get("message", "Error desconocido")
        except json.JSONDecodeError:
            msg = result.stdout.strip()[:200] or "Error desconocido"
        print(f"  ❌  Falló publicar_hf.py (código {code}): {msg}", file=sys.stderr)
        if result.stderr.strip():
            print(f"      stderr: {result.stderr.strip()[:300]}", file=sys.stderr)
        state["steps_failed"].append({"step": 1, "script": "publicar_hf.py", "code": code, "message": msg})
        state["last_updated"] = now_iso()
        save_state(state)
        if alert:
            subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return code

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        data = {}

    url = data.get("url", f"https://huggingface.co/datasets/{repo_id}")
    print(f"  ✅  Publicación completada: {url}")
    print(f"      Archivos: {', '.join(data.get('archivos', []))} | Licencia: {data.get('licencia', '?')}")

    state["current_step"] = 1
    state["steps_completed"].append({"step": 1, "script": "publicar_hf.py", "status": "ok", **data})
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
    print("  FLUJO COMPLETADO — Publicación en Hugging Face Hub")
    print(f"{'═' * 56}")
    print(f"  Dataset     : {dataset}")
    print(f"  Repositorio : {repo_id}")
    print(f"  Privado     : {private}")
    print(f"  URL         : {url}")
    print(f"  Dry Run     : {dry_run}")
    print(f"{'═' * 56}\n")

    return 0


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Flujo completo: publica un dataset empaquetado en HF Hub y notifica.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("dataset", help="Nombre del paquete en datasets/paquetes/.")
    parser.add_argument("--repo", dest="repo_id", default=None,
                        help="repo_id del Hub (default: <usuario>/gideal-<dataset>).")
    parser.add_argument("--private", action="store_true",
                        help="Crea el repositorio como privado (default: público).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula la publicación sin conectarse al Hub.")
    parser.add_argument("--no-alert", action="store_true",
                        help="No emitir alerta sonora al terminar.")
    args = parser.parse_args()

    repo_id = args.repo_id or f"gideal-{args.dataset}"

    return flujo_publicar(
        dataset=args.dataset,
        repo_id=repo_id,
        private=args.private,
        dry_run=args.dry_run,
        alert=not args.no_alert,
    )


if __name__ == "__main__":
    sys.exit(main())