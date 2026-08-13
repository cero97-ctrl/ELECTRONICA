#!/usr/bin/env python3
"""
flujo_consultar_docs.py — Orquestador del flujo de consulta de documentación (Layer 2)

Ejecuta el flujo completo definido en la directiva consultar_docs_recientes.yaml:
  1. consultar_docs.py   → Obtiene la documentación vigente de una tecnología (Markdown)
  2. (presentación)      → Muestra resumen al usuario
  3. alert_user.py       → Notifica al usuario con alerta audible

Uso:
    python3 flujo_consultar_docs.py nextjs
    python3 flujo_consultar_docs.py nextjs --topic app
    python3 flujo_consultar_docs.py --url https://nextjs.org/docs/app
    python3 flujo_consultar_docs.py --list
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Configuración ──────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent.resolve()
PYTHON       = sys.executable
CONSULTAR    = SCRIPT_DIR / "execution" / "consultar_docs.py"
ALERTAR      = SCRIPT_DIR / "execution" / "alert_user.py"
TMP_DIR      = SCRIPT_DIR / ".tmp"
STATE_FILE   = TMP_DIR / "run_state.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_state(state: dict) -> None:
    TMP_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def run_script(cmd: list[str], capture_json: bool = False) -> tuple[int, dict | str]:
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if capture_json:
        try:
            return result.returncode, json.loads(result.stdout)
        except json.JSONDecodeError:
            return result.returncode, {"raw_output": result.stdout, "stderr": result.stderr}
    return result.returncode, result.stdout


def flujo_consultar(
    tecnologia: str | None,
    url: str | None,
    topic: str | None,
    max_chars: int,
) -> int:
    run_id = f"flujo-docs-{now_iso()[:19].replace(':', '-')}"

    state = {
        "run_id": run_id,
        "directive": "consultar_docs_recientes.yaml",
        "tecnologia": tecnologia,
        "url": url,
        "topic": topic,
        "started_at": now_iso(),
        "last_updated": now_iso(),
        "current_step": 0,
        "steps_completed": [],
        "steps_failed": [],
        "context": {},
    }
    save_state(state)

    total_pasos = 3

    # ══ PASO 1: Consultar documentación ═══════════════════════════════════════
    print(f"\n{'─' * 56}")
    print(f"  Paso 1/{total_pasos}  │  Consultando documentación…")
    print(f"{'─' * 56}")

    cmd = [PYTHON, str(CONSULTAR)]
    if tecnologia:
        cmd += ["--tech", tecnologia]
    if url:
        cmd += ["--url", url]
    if topic:
        cmd += ["--topic", topic]
    cmd += ["--max-chars", str(max_chars)]

    code, resultado = run_script(cmd, capture_json=True)

    if code != 0 or resultado.get("status") != "ok":
        msg = resultado.get("message", resultado.get("raw_output", "Error desconocido"))
        print(f"  ❌  Falló consultar_docs.py (código {code}): {msg}", file=sys.stderr)
        disponibles = resultado.get("disponibles")
        if disponibles:
            print(f"  Tecnologías disponibles: {', '.join(disponibles)}")
        state["steps_failed"].append({
            "step": 1, "script": "consultar_docs.py",
            "code": code, "message": msg,
        })
        state["last_updated"] = now_iso()
        save_state(state)
        subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return code if code != 0 else 1

    archivo = resultado.get("archivo", "")
    title   = resultado.get("title", "")
    chars   = resultado.get("chars", 0)
    cached  = resultado.get("cached", False)
    url_final = resultado.get("url_final", url or tecnologia)

    print(f"  ✅  Documentación obtenida — Título: {title}")
    print(f"  Fuente: {url_final}  |  Caracteres: {chars}  |  Caché: {cached}")
    print(f"  Archivo: {archivo}")

    state["current_step"] = 1
    state["steps_completed"].append({
        "step": 1, "script": "consultar_docs.py", "status": "ok",
        "archivo": archivo, "title": title, "chars": chars,
        "url_final": url_final, "cached": cached,
    })
    state["context"].update({
        "archivo": archivo, "title": title, "chars": chars,
        "url_final": url_final, "cached": cached,
    })
    state["last_updated"] = now_iso()
    save_state(state)

    # ══ PASO 2: Presentar resumen ═════════════════════════════════════════════
    print(f"\n{'─' * 56}")
    print(f"  Paso 2/{total_pasos}  │  Presentando resumen…")
    print(f"{'─' * 56}")
    if archivo and Path(archivo).exists():
        preview = Path(archivo).read_text(encoding="utf-8")[:600]
        print("\n  PRIMERAS LÍNEAS DE LA DOCUMENTACIÓN\n")
        print("\n".join("  " + ln for ln in preview.splitlines()[:15]))
    print("\n  ✅  Resumen presentado.")

    state["current_step"] = 2
    state["steps_completed"].append({"step": 2, "script": "presentación", "status": "ok"})
    state["last_updated"] = now_iso()
    save_state(state)

    # ══ PASO 3: Alerta de completado ═══════════════════════════════════════════
    print(f"\n{'─' * 56}")
    print(f"  Paso 3/{total_pasos}  │  Notificando al usuario…")
    print(f"{'─' * 56}")
    subprocess.run([PYTHON, str(ALERTAR), "success"], capture_output=True)
    print("  ✅  Alerta de completado emitida.")

    state["current_step"] = 3
    state["steps_completed"].append({"step": 3, "script": "alert_user.py", "status": "ok", "tipo": "success"})
    state["last_updated"] = now_iso()
    save_state(state)

    # ══ RESUMEN FINAL ═════════════════════════════════════════════════════════
    bar = "═" * 56
    print(f"\n{bar}")
    print("  FLUJO COMPLETADO — Consulta de documentación")
    print(f"{bar}")
    print(f"  Tecnología   : {tecnologia or url}")
    print(f"  Título       : {title}")
    print(f"  Fuente       : {url_final}")
    print(f"  Caracteres   : {chars}")
    print(f"  Archivo      : {archivo}")
    print(f"{bar}\n")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Flujo completo: consulta la documentación oficial vigente de una tecnología.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 flujo_consultar_docs.py nextjs
  python3 flujo_consultar_docs.py supabase --topic api
  python3 flujo_consultar_docs.py --url https://nextjs.org/docs/app
  python3 flujo_consultar_docs.py --list
        """,
    )
    parser.add_argument("tecnologia", nargs="?", default=None, help="Tecnología a consultar (ver --list).")
    parser.add_argument("--topic", default=None, help="Sub-ruta/tema opcional dentro de la documentación.")
    parser.add_argument("--url", default=None, help="URL directa de documentación (alternativa a tecnología).")
    parser.add_argument("--max-chars", type=int, default=200000, help="Truncar a N caracteres (default: 200000).")
    parser.add_argument("--list", action="store_true", help="Listar tecnologías soportadas y salir.")
    args = parser.parse_args()

    if args.list:
        code, out = run_script([PYTHON, str(CONSULTAR), "--list"], capture_json=True)
        print(", ".join(out.get("tecnologias", [])))
        return code

    if not args.tecnologia and not args.url:
        print("❌  Debe indicarse una tecnología o --url.", file=sys.stderr)
        return 1

    return flujo_consultar(
        tecnologia=args.tecnologia,
        url=args.url,
        topic=args.topic,
        max_chars=args.max_chars,
    )


if __name__ == "__main__":
    sys.exit(main())