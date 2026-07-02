#!/usr/bin/env python3
"""
flujo_elaborar_ejercicios.py — Orquestador del flujo de elaboración de ejercicios (Layer 2)

Ejecuta el flujo completo definido en la directiva elaborar_ejercicios.yaml:
  1. elaborar_ejercicios.py        → Genera ejercicios con LLM (JSON)
  2. generar_ejercicios_latex.py   → Convierte el JSON en ejercicios LaTeX (.tex)
  3. alert_user.py                 → Notifica al usuario con alerta audible

Uso:
    python3 flujo_elaborar_ejercicios.py --tema "Semana 4: Condensadores" --path ejercicios/Semana4
    python3 flujo_elaborar_ejercicios.py --tema "Transistor BJT" --path ejercicios/BJT --nivel avanzada

Los archivos .tex (ejercicios.tex y sol_ejercicios.tex) se guardarán en la ruta especificada por --path.
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
ELABORAR     = SCRIPT_DIR / "execution" / "elaborar_ejercicios.py"
GENERAR_TEX  = SCRIPT_DIR / "execution" / "generar_ejercicios_latex.py"
ALERTAR      = SCRIPT_DIR / "execution" / "alert_user.py"
TMP_DIR      = SCRIPT_DIR / ".tmp"
STATE_FILE   = TMP_DIR / "run_state.json"


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
    tema: str,
    nivel: str,
    modelo: str,
    api_backend: str,
    output_dir: Path,
) -> int:
    run_id = f"flujo-ejercicios-{now_iso()[:19].replace(':', '-')}"
    nombre_base = tema.lower().replace(" ", "_").replace(":", "")[:40]
    json_tmp = TMP_DIR / f"ejercicios_{nombre_base}.json"

    state = {
        "run_id": run_id,
        "directive": "elaborar_ejercicios.yaml",
        "tema": tema,
        "started_at": now_iso(),
        "last_updated": now_iso(),
        "current_step": 0,
        "steps_completed": [],
        "steps_failed": [],
        "context": {},
    }
    save_state(state)

    total_pasos = 3

    # ══ PASO 1: Generar ejercicios con LLM ═════════════════════════════════════════
    print_step(1, total_pasos, f"Generando ejercicios con {modelo}...")
    print(f"  Tema  : {tema}")
    print(f"  Nivel : {nivel}")
    print(f"  Backend: {api_backend}")

    cmd_elaborar = [
        PYTHON, str(ELABORAR),
        "--tema", tema,
        "--nivel", nivel,
        "--modelo", modelo,
        "--api-backend", api_backend,
    ]

    code, ejercicios_data = run_script(cmd_elaborar, capture_json=True)

    if code != 0 or ejercicios_data.get("status") != "ok":
        if api_backend == "groq":
            print_err("Falló Groq. Intentando como respaldo automático con Gemini...")
            cmd_fallback = list(cmd_elaborar)
            if "--api-backend" in cmd_fallback:
                cmd_fallback[cmd_fallback.index("--api-backend") + 1] = "gemini"
            if "--modelo" in cmd_fallback:
                cmd_fallback[cmd_fallback.index("--modelo") + 1] = "gemini-pro"
            code, ejercicios_data = run_script(cmd_fallback, capture_json=True)
            
        if code != 0 or ejercicios_data.get("status") != "ok":
            print_err("Falló el respaldo. Intentando como último recurso con OpenRouter...")
            cmd_fallback = list(cmd_elaborar)
            if "--api-backend" in cmd_fallback:
                cmd_fallback[cmd_fallback.index("--api-backend") + 1] = "openrouter"
            if "--modelo" in cmd_fallback:
                cmd_fallback[cmd_fallback.index("--modelo") + 1] = "meta-llama/llama-3.3-70b-instruct:free"
            code, ejercicios_data = run_script(cmd_fallback, capture_json=True)

        if code != 0 or ejercicios_data.get("status") != "ok":
            msg = ejercicios_data.get("message", ejercicios_data.get("raw_output", "Error desconocido"))
            print_err(f"Falló elaborar_ejercicios.py (código {code}): {msg}")
            state["steps_failed"].append({"step": 1, "script": "elaborar_ejercicios.py",
                                      "code": code, "message": msg})
        state["last_updated"] = now_iso()
        save_state(state)
        subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return code if code != 0 else 1

    # Guardar JSON intermedio
    TMP_DIR.mkdir(exist_ok=True)
    json_tmp.write_text(json.dumps(ejercicios_data, ensure_ascii=False, indent=2), encoding="utf-8")

    ejer_data = ejercicios_data.get("ejercicios", ejercicios_data.get("examen", {})) # Fallback a examen si usa esa clave por error
    titulo    = ejer_data.get("titulo", "N/A")
    preguntas = ejer_data.get("preguntas", ejer_data.get("ejercicios", []))
    n_preg    = len(preguntas)
    duracion  = ejer_data.get("duracion_sugerida", "N/A")
    tokens    = ejercicios_data.get("tokens_usados", {}).get("total", "N/A")

    print_ok(f"Ejercicios generados — {n_preg} preguntas  |  Tokens: {tokens}")
    print_ok(f"Título: {titulo}")
    print_ok(f"Duración sugerida: {duracion}")
    print_ok(f"JSON guardado en: {json_tmp.name}")

    state["current_step"] = 1
    state["steps_completed"].append({
        "step": 1, "script": "elaborar_ejercicios.py", "status": "ok",
        "titulo": titulo, "n_preguntas": n_preg,
        "tokens_total": tokens, "json_tmp": str(json_tmp),
    })
    state["context"].update({"titulo": titulo, "n_preguntas": n_preg})
    state["last_updated"] = now_iso()
    save_state(state)

    # ══ PASO 2: Generar LaTeX ══════════════════════════════════════════════════
    print_step(2, total_pasos, "Generando documentos LaTeX...")

    output_tex = output_dir / f"ejercicios_{nombre_base}.tex"
    sol_output = output_dir / f"sol_ejercicios_{nombre_base}.tex"

    cmd_latex = [
        PYTHON, str(GENERAR_TEX),
        "--json", str(json_tmp),
        "--output", str(output_tex),
        "--sol-output", str(sol_output),
    ]

    code, tex_result = run_script(cmd_latex, capture_json=True)

    if code != 0 or tex_result.get("status") != "ok":
        msg = tex_result.get("message", tex_result.get("raw_output", "Error desconocido"))
        print_err(f"Falló generar_ejercicios_latex.py (código {code}): {msg}")
        state["steps_failed"].append({"step": 2, "script": "generar_ejercicios_latex.py",
                                      "code": code, "message": msg})
        state["last_updated"] = now_iso()
        save_state(state)
        subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return code if code != 0 else 1

    archivos_tex = tex_result.get("archivos_tex", [])
    print_ok(f"Ejercicios LaTeX generados: {output_tex}")
    print_ok(f"Solucionario LaTeX generado: {sol_output}")

    state["current_step"] = 2
    state["steps_completed"].append({
        "step": 2, "script": "generar_ejercicios_latex.py", "status": "ok",
        "archivos_tex": archivos_tex,
    })
    state["context"]["archivos_tex"] = archivos_tex
    state["last_updated"] = now_iso()
    save_state(state)

    # ══ PASO 3: Alerta de completado ═══════════════════════════════════════════
    print_step(3, total_pasos, "Notificando al usuario...")
    subprocess.run([PYTHON, str(ALERTAR), "success"], capture_output=True)
    print_ok("Alerta de completado emitida.")

    state["current_step"] = 3
    state["steps_completed"].append({
        "step": 3, "script": "alert_user.py", "status": "ok",
        "tipo": "success",
    })
    state["last_updated"] = now_iso()
    save_state(state)

    # ══ RESUMEN FINAL ══════════════════════════════════════════════════════════
    bar = "═" * 56
    print(f"\n{bar}")
    print("  FLUJO COMPLETADO — Ejercicios generados")
    print(f"{bar}")
    print(f"  Tema              : {tema}")
    print(f"  Título            : {titulo}")
    print(f"  Ejercicios        : {n_preg}")
    print(f"  Duración sugerida : {duracion}")
    print(f"  Dificultad        : {nivel}")
    print(f"  Modelo usado      : {modelo}  |  Tokens: {tokens}")
    print(f"  Ejercicios LaTeX  : {output_tex}")
    print(f"  Solucionario LaTeX: {sol_output}")
    print(f"  JSON generado     : {json_tmp}")
    print(f"{bar}\n")
    print("  💡 Para compilar los PDFs:")
    print(f"     pdflatex {output_tex}  &&  pdflatex {sol_output}\n")

    return 0


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Flujo completo: genera ejercicios de razonamiento y cálculo sobre un tema de Electrónica.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 flujo_elaborar_ejercicios.py --tema "Semana 4: Condensadores" --path ejercicios/Semana4
  python3 flujo_elaborar_ejercicios.py --tema "Transistor BJT" --path ejercicios/BJT --nivel avanzada
  python3 flujo_elaborar_ejercicios.py --tema "A.O." --path ejercicios/AO --modelo gemini-1.5-pro
        """,
    )
    parser.add_argument("--tema", required=True,
                        help="Tema del plan de estudios sobre el que generar los ejercicios.")
    parser.add_argument("--path", required=True,
                        help="Ruta del directorio donde se guardarán los .tex (ej. ejercicios_{tema}.tex).")
    parser.add_argument("--nivel", default="intermedia",
                        choices=["basica", "intermedia", "avanzada"],
                        help="Nivel de dificultad (default: intermedia).")
    parser.add_argument("--modelo", default="qwen/qwen3.6-27b",
                        help="Modelo a usar (default: qwen/qwen3.6-27b).")
    parser.add_argument("--api-backend", default="groq",
                        choices=["gemini", "openrouter", "groq"],
                        help="Backend de API: gemini, openrouter o groq. (default: groq).")
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.tema.strip():
        print_err("El tema no puede estar vacío.")
        sys.exit(1)

    output_dir = Path(args.path)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'═'*56}")
    print("  ELECTRÓNICA — Flujo de Elaboración de Ejercicios")
    print(f"{'═'*56}")
    print(f"  Directiva : elaborar_ejercicios.yaml")
    print(f"  Tema      : {args.tema}")
    print(f"  Nivel     : {args.nivel}")
    print(f"  Modelo    : {args.modelo}")
    print(f"  Backend   : {args.api_backend}")
    print(f"  Salida    : {output_dir}/")
    print(f"{'═'*56}")

    code = flujo_completo(
        tema=args.tema,
        nivel=args.nivel,
        modelo=args.modelo,
        api_backend=args.api_backend,
        output_dir=output_dir,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
