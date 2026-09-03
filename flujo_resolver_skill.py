#!/usr/bin/env python3
"""
flujo_resolver_skill.py — Orquestador: resuelve un problema usando un skill (Layer 2)

Ejecuta el flujo definido en la directiva resolver_skill.yaml:
  1. Validación de entradas (problema no vacío, skill válido)
  2. Enrutador LLM (decisión 100% determinista) → tier/modelo vía execution/enrutador.py
  3. resolver_skill.py → retrieval + formulador + oráculo SymPy + reflexión
  4. Estado en .tmp/run_state.json y alerta al usuario

Uso:
    python3 flujo_resolver_skill.py --problema "..." --skill <dir>
    python3 flujo_resolver_skill.py --problema "..." --skill <dir> --critico --max-reflexion 3
    python3 flujo_resolver_skill.py --problema "..." --skill <dir> --modelo z-ai/glm-5.2

El resultado JSON se guarda en .tmp/resolucion_<fecha>.json (o --salida).
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
PYTHON = sys.executable
ENRUTAR = SCRIPT_DIR / "execution" / "enrutador.py"
RESOLVER = SCRIPT_DIR / "execution" / "resolver_skill.py"
ALERTAR = SCRIPT_DIR / "execution" / "alert_user.py"
TMP_DIR = SCRIPT_DIR / ".tmp"
STATE_FILE = TMP_DIR / "run_state.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def print_step(num: int, total: int, desc: str) -> None:
    bar = "─" * 56
    print(f"\n{bar}\n  Paso {num}/{total}  │  {desc}\n{bar}")


def print_ok(msg: str) -> None:
    print(f"  ✅  {msg}")


def print_err(msg: str) -> None:
    print(f"  ❌  {msg}", file=sys.stderr)


def run_script(args, capture_json=False) -> tuple[int, str | dict | None]:
    proc = subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", timeout=600,
    )
    out = proc.stdout.strip()
    if capture_json:
        try:
            return proc.returncode, json.loads(out)
        except json.JSONDecodeError:
            return proc.returncode, None
    return proc.returncode, out


def load_state() -> dict:
    if not STATE_FILE.is_file():
        return {"steps_completed": [], "steps_failed": []}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"steps_completed": [], "steps_failed": []}


def save_state(state: dict) -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def estado_ok(state: dict, paso: int) -> None:
    state["current_step"] = paso
    state["steps_completed"] = sorted(set(state["steps_completed"] + [paso]))
    state["last_updated"] = now_iso()
    save_state(state)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--problema", required=True, help="Enunciado del problema a resolver.")
    parser.add_argument("--skill", required=True, help="Directorio del skill (SKILL.md + references/).")
    parser.add_argument("--task", default="calculo_formal",
                        help="Tipo de tarea para el enrutador (vocabulario controlado). Default calculo_formal.")
    parser.add_argument("--critico", action="store_true", help="Escalar el tier si la tarea es de alto impacto.")
    parser.add_argument("--tokens", type=int, default=None,
                        help="Tokens medidos del contexto (default: len(problema)//4).")
    parser.add_argument("--modelo", default=None,
                        help="Override del modelo (salta el enrutador).")
    parser.add_argument("--max-reflexion", type=int, default=3, help="Rondas máx de reflexión (≤3).")
    parser.add_argument("--top-k", type=int, default=6, help="Secciones a recuperar por embeddings.")
    parser.add_argument("--min-score", type=float, default=0.05, help="Score mínimo de similitud.")
    parser.add_argument("--alerta-score", type=float, default=None,
                        help="Umbral de confianza débil del retrieval (default 0.35).")
    parser.add_argument("--abortar-debil", action="store_true",
                        help="Abortar (exit 3) si el retrieval tiene confianza baja.")
    parser.add_argument("--timeout-s", type=int, default=30, help="Timeout del sandbox SymPy (s).")
    parser.add_argument("--salida", default=None, help="Ruta del JSON de resultado (default .tmp/resolucion_<ts>.json).")
    parser.add_argument("--no-alert", action="store_true", help="No emitir alerta audible.")
    args = parser.parse_args()

    # ── Paso 1: validación de entradas ──
    state = load_state()
    print_step(1, 3, "Validación de entradas")
    problema = (args.problema or "").strip()
    if not problema:
        print_err("El problema no puede estar vacío.")
        return 1
    skill_dir = Path(args.skill).expanduser()
    if not (skill_dir / "SKILL.md").is_file():
        print_err(f"No es un skill válido (falta SKILL.md): {skill_dir}")
        return 1
    max_reflexion = max(0, min(args.max_reflexion, 3))
    print_ok(f"Problema ({len(problema)} chars) → skill {skill_dir}")
    estado_ok(state, 1)

    # ── Paso 2: enrutamiento determinista del modelo ──
    print_step(2, 3, "Enrutamiento LLM (decisión determinista)")
    modelo = args.modelo
    info_enrutador = None
    if not modelo:
        tokens = args.tokens if args.tokens is not None else len(problema) // 4
        cmd = [PYTHON, str(ENRUTAR), "--task", args.task, "--tokens", str(tokens)]
        if args.critico:
            cmd.append("--critico")
        code, info_enrutador = run_script(cmd, capture_json=True)
        if code != 0 or not isinstance(info_enrutador, dict) or not info_enrutador.get("model"):
            print_err(f"Enrutador falló (código {code}): {info_enrutador}")
            return 1
        modelo = info_enrutador["model"]
        print_ok(f"Tier {info_enrutador.get('tier')} → modelo {modelo} ({info_enrutador.get('reason', '')})")
    else:
        print_ok(f"Modelo explícito del usuario: {modelo} (sin enrutar)")
    estado_ok(state, 2)

    # ── Paso 3: resolver_skill.py ──
    print_step(3, 3, "Resolución con skill (retrieval → formulador → oráculo → reflexión)")
    cmd = [PYTHON, str(RESOLVER),
           "--skill", str(skill_dir),
           "--problema", problema,
           "--modelo", modelo,
           "--max-reflexion", str(max_reflexion),
           "--top-k", str(args.top_k),
           "--min-score", str(args.min_score),
           "--timeout-s", str(args.timeout_s)]
    if args.alerta_score is not None:
        cmd += ["--alerta-score", str(args.alerta_score)]
    if args.abortar_debil:
        cmd += ["--abortar-debil"]
    code, res = run_script(cmd, capture_json=True)
    if not isinstance(res, dict):
        print_err("resolver_skill.py no devolvió JSON válido.")
        return 1

    res["enrutamiento"] = info_enrutador
    res["resuelto"] = res.get("status") == "ok"

    confianza = res.get("confianza_retrieval") or {}
    nivel_conf = confianza.get("nivel")
    if nivel_conf == "baja":
        print(f"\n  ⚠  Confianza del retrieval BAJA (mejor score {confianza.get('mejor_score')})")
        if confianza.get("alerta"):
            print(f"     {confianza['alerta']}")
    elif nivel_conf == "media":
        print(f"\n  ℹ  Confianza del retrieval media (mejor score {confianza.get('mejor_score')})")

    salida = Path(args.salida) if args.salida else TMP_DIR / f"resolucion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print_ok(f"Resultado guardado en {salida}")

    if res["resuelto"]:
        print("\n  ── Resolución final del oráculo sympy ──")
        print(f"  {res.get('resultado_final', '')}")
        if res.get("reflexiones_usadas"):
            print(f"  (con {res['reflexiones_usadas']} ronda(s) de reflexión)")
        estado_ok(state, 3)
        if not args.no_alert:
            run_script([PYTHON, str(ALERTAR), "success"])
        print("\n  ✅ Flujo completado.")
        return 0

    print("\n  ❌ No se llegó a una solución verificada por el oráculo.")
    print("     Revisa .tmp/resolucion_*.json y el error devuelto por la reflexión.")
    state["steps_failed"] = sorted(set(state.get("steps_failed", []) + [3]))
    save_state(state)
    if not args.no_alert:
        run_script([PYTHON, str(ALERTAR), "error"])
    return 3


if __name__ == "__main__":
    sys.exit(main())