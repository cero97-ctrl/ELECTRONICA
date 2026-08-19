#!/usr/bin/env python3
"""
flujo_elaborar_examen.py — Orquestador del flujo de elaboración de exámenes (Layer 2)

Ejecuta el flujo completo definido en la directiva elaborar_examen.yaml:
  1. elaborar_examen.py        → Genera 5 preguntas con LLM (JSON)
  2. generar_examen_latex.py   → Convierte el JSON en examen LaTeX (.tex)
  3. alert_user.py             → Notifica al usuario con alerta audible

Uso:
    python3 flujo_elaborar_examen.py --tema "Semana 4: Condensadores" --output examenes/
    python3 flujo_elaborar_examen.py --tema "Transistor BJT" --output examenes/ --nivel avanzada
    python3 flujo_elaborar_examen.py --tema "A.O." --output examenes/

--output es un directorio. El nombre del archivo .tex se genera automáticamente a partir del tema.
El solucionario se genera como sol_{nombre_del_examen}.tex en el mismo directorio.
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
PYTHON       = sys.executable
ELABORAR     = SCRIPT_DIR / "execution" / "elaborar_examen.py"
GENERAR_TEX  = SCRIPT_DIR / "execution" / "generar_examen_latex.py"
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
    output_tex: Path,
) -> int:
    run_id = f"flujo-examen-{now_iso()[:19].replace(':', '-')}"
    nombre_base = tema.lower().replace(" ", "_").replace(":", "")[:40]
    json_tmp = TMP_DIR / f"examen_{nombre_base}.json"

    state = {
        "run_id": run_id,
        "directive": "elaborar_examen.yaml",
        "tema": tema,
        "started_at": now_iso(),
        "last_updated": now_iso(),
        "current_step": 0,
        "steps_completed": [],
        "steps_failed": [],
        "context": {},
    }
    save_state(state)

    total_pasos = 4

    # ══ PASO 1: Generar examen con LLM ═════════════════════════════════════════
    print_step(1, total_pasos, f"Generando examen con {modelo}...")
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

    code, examen = run_script(cmd_elaborar, capture_json=True)

    if code != 0 or examen.get("status") != "ok":
        if api_backend == "groq":
            print_err("Falló Groq. Intentando como respaldo automático con Gemini...")
            cmd_fallback = list(cmd_elaborar)
            if "--api-backend" in cmd_fallback:
                cmd_fallback[cmd_fallback.index("--api-backend") + 1] = "gemini"
            if "--modelo" in cmd_fallback:
                cmd_fallback[cmd_fallback.index("--modelo") + 1] = "gemini-pro"
            code, examen = run_script(cmd_fallback, capture_json=True)
            
        if code != 0 or examen.get("status") != "ok":
            print_err("Falló el respaldo. Intentando como último recurso con OpenRouter...")
            cmd_fallback = list(cmd_elaborar)
            if "--api-backend" in cmd_fallback:
                cmd_fallback[cmd_fallback.index("--api-backend") + 1] = "openrouter"
            if "--modelo" in cmd_fallback:
                cmd_fallback[cmd_fallback.index("--modelo") + 1] = "google/gemini-3.7-flash"
            code, examen = run_script(cmd_fallback, capture_json=True)

        if code != 0 or examen.get("status") != "ok":
            msg = examen.get("message", examen.get("raw_output", "Error desconocido"))
            print_err(f"Falló elaborar_examen.py (código {code}): {msg}")
            state["steps_failed"].append({"step": 1, "script": "elaborar_examen.py",
                                      "code": code, "message": msg})
        state["last_updated"] = now_iso()
        save_state(state)
        subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return code if code != 0 else 1

    # Guardar JSON intermedio
    TMP_DIR.mkdir(exist_ok=True)
    json_tmp.write_text(json.dumps(examen, ensure_ascii=False, indent=2), encoding="utf-8")

    exam_data = examen.get("examen", {})
    titulo    = exam_data.get("titulo", "N/A")
    preguntas = exam_data.get("preguntas", [])
    n_preg    = len(preguntas)
    duracion  = exam_data.get("duracion_sugerida", "N/A")
    tokens    = examen.get("tokens_usados", {}).get("total", "N/A")

    print_ok(f"Examen generado — {n_preg} preguntas  |  Tokens: {tokens}")
    print_ok(f"Título: {titulo}")
    print_ok(f"Duración sugerida: {duracion}")
    print_ok(f"JSON guardado en: {json_tmp.name}")

    state["current_step"] = 1
    state["steps_completed"].append({
        "step": 1, "script": "elaborar_examen.py", "status": "ok",
        "titulo": titulo, "n_preguntas": n_preg,
        "tokens_total": tokens, "json_tmp": str(json_tmp),
    })
    state["context"].update({"titulo": titulo, "n_preguntas": n_preg})
    state["last_updated"] = now_iso()
    save_state(state)

    # ══ PASO 2: Generar LaTeX ══════════════════════════════════════════════════
    print_step(2, total_pasos, "Generando documentos LaTeX...")

    # El solucionario se deriva automáticamente del nombre del examen
    sol_output = output_tex.parent / f"sol_{output_tex.name}"

    cmd_latex = [
        PYTHON, str(GENERAR_TEX),
        "--json", str(json_tmp),
        "--output", str(output_tex),
        "--sol-output", str(sol_output),
    ]

    code, tex_result = run_script(cmd_latex, capture_json=True)

    if code != 0 or tex_result.get("status") != "ok":
        msg = tex_result.get("message")
        if not msg:
            msg = tex_result.get("stderr") or tex_result.get("raw_output", "Error desconocido")
        print_err(f"Falló generar_examen_latex.py (código {code}): {msg}")
        state["steps_failed"].append({"step": 2, "script": "generar_examen_latex.py",
                                      "code": code, "message": msg})
        state["last_updated"] = now_iso()
        save_state(state)
        subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return code if code != 0 else 1

    archivos_tex = tex_result.get("archivos_tex", [])
    print_ok(f"Examen LaTeX generado: {output_tex}")
    print_ok(f"Solucionario LaTeX generado: {sol_output}")

    state["current_step"] = 2
    state["steps_completed"].append({
        "step": 2, "script": "generar_examen_latex.py", "status": "ok",
        "archivos_tex": archivos_tex,
    })
    state["context"]["archivos_tex"] = archivos_tex
    state["last_updated"] = now_iso()
    save_state(state)

    # ══ PASO 3: Compilar examen y solucionario LaTeX a PDF ═══════════════════════
    print_step(3, total_pasos, "Compilando examen y solucionario LaTeX a PDF...")
    
    examen_pdf = "N/A"
    solucionario_pdf = "N/A"
    try:
        from execution.compile_latex import compile_latex_code
        
        # 1. Compilar Examen
        latex_content_exam = output_tex.read_text(encoding="utf-8")
        job_name_exam = output_tex.stem
        output_parent = str(output_tex.parent.resolve())
        
        comp_res_exam = compile_latex_code(latex_content_exam, job_name=job_name_exam, output_dir=output_parent)
        
        # 2. Compilar Solucionario
        latex_content_sol = sol_output.read_text(encoding="utf-8")
        job_name_sol = sol_output.stem
        
        comp_res_sol = compile_latex_code(latex_content_sol, job_name=job_name_sol, output_dir=output_parent)
        
        if comp_res_exam["success"] and comp_res_sol["success"]:
            examen_pdf = Path(comp_res_exam["pdf_path"])
            solucionario_pdf = Path(comp_res_sol["pdf_path"])
            print_ok(f"Examen PDF generado: {examen_pdf}")
            print_ok(f"Solucionario PDF generado: {solucionario_pdf}")
            
            state["current_step"] = 3
            state["steps_completed"].append({
                "step": 3, "script": "compile_latex.py", "status": "ok",
                "examen_pdf": str(examen_pdf),
                "solucionario_pdf": str(solucionario_pdf),
            })
            state["context"]["examen_pdf"] = str(examen_pdf)
            state["context"]["solucionario_pdf"] = str(solucionario_pdf)
            state["last_updated"] = now_iso()
            save_state(state)
        else:
            err_msg = ""
            if not comp_res_exam["success"]:
                err_msg += f"Examen: {comp_res_exam.get('error')}. "
            if not comp_res_sol["success"]:
                err_msg += f"Solucionario: {comp_res_sol.get('error')}."
                
            print_err(f"Falló la compilación de PDFs: {err_msg}")
            state["steps_failed"].append({
                "step": 3, "script": "compile_latex.py",
                "code": 1, "message": err_msg
            })
            state["last_updated"] = now_iso()
            save_state(state)
            subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
            return 1
            
    except Exception as e:
        print_err(f"Error crítico al compilar los PDFs: {str(e)}")
        subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return 1

    # ══ PASO 4: Alerta de completado ═══════════════════════════════════════════
    print_step(4, total_pasos, "Notificando al usuario...")
    subprocess.run([PYTHON, str(ALERTAR), "success"], capture_output=True)
    print_ok("Alerta de completado emitida.")

    state["current_step"] = 4
    state["steps_completed"].append({
        "step": 4, "script": "alert_user.py", "status": "ok",
        "tipo": "success",
    })
    state["last_updated"] = now_iso()
    save_state(state)

    # ══ RESUMEN FINAL ══════════════════════════════════════════════════════════
    bar = "═" * 56
    print(f"\n{bar}")
    print("  FLUJO COMPLETADO — Examen generado")
    print(f"{bar}")
    print(f"  Tema              : {tema}")
    print(f"  Título            : {titulo}")
    print(f"  Preguntas         : {n_preg}")
    print(f"  Duración sugerida : {duracion}")
    print(f"  Dificultad        : {nivel}")
    print(f"  Modelo usado      : {modelo}  |  Tokens: {tokens}")
    print(f"  Examen PDF        : {examen_pdf}")
    print(f"  Solucionario PDF  : {solucionario_pdf}")
    print(f"  Examen LaTeX      : {output_tex}")
    print(f"  Solucionario LaTeX: {sol_output}")
    print(f"  JSON del examen   : {json_tmp}")
    print(f"{bar}\n")

    return 0


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Flujo completo: genera un examen de 5 preguntas de razonamiento y cálculo sobre un tema de Electrónica.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 flujo_elaborar_examen.py --tema "Semana 4: Condensadores" --output examenes/
  python3 flujo_elaborar_examen.py --tema "Transistor BJT" --output examenes/ --nivel avanzada
  python3 flujo_elaborar_examen.py --tema "A.O." --output examenes/ --modelo gemini-1.5-pro
  python3 flujo_elaborar_examen.py --tema "Semana 1: Circuitos DC" --output examenes/
        """,
    )
    parser.add_argument("--tema", required=True,
                        help="Tema del plan de estudios sobre el que generar el examen.")
    parser.add_argument("--output", required=True,
                        help="Directorio donde se guardarán examen_{tema}.tex y sol_examen_{tema}.tex.")
    parser.add_argument("--nivel", default="intermedia",
                        choices=["basica", "intermedia", "avanzada"],
                        help="Nivel de dificultad del examen (default: intermedia).")
    parser.add_argument("--modelo", default="anthropic/claude-opus-5",
                        help="Modelo a usar (default: anthropic/claude-opus-5 para tareas complejas).")
    parser.add_argument("--api-backend", default="openrouter",
                        choices=["gemini", "openrouter", "groq"],
                        help="Backend de API: gemini, openrouter o groq. (default: openrouter).")
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.tema.strip():
        print_err("El tema no puede estar vacío.")
        sys.exit(1)

    import re
    out_path = Path(args.output).resolve()
    if out_path.is_dir() or args.output.endswith("/"):
        out_path.mkdir(parents=True, exist_ok=True)
        safe_tema = re.sub(r'[^a-zA-Z0-9]+', '_', args.tema).strip('_').lower()
        output_tex = out_path / f"examen_{safe_tema}.tex"
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.suffix != ".tex":
            output_tex = out_path.with_suffix(".tex")
        else:
            output_tex = out_path

    print(f"\n{'═'*56}")
    print("  ELECTRÓNICA — Flujo de Elaboración de Exámenes")
    print(f"{'═'*56}")
    print(f"  Directiva : elaborar_examen.yaml")
    print(f"  Tema      : {args.tema}")
    print(f"  Nivel     : {args.nivel}")
    print(f"  Modelo    : {args.modelo}")
    print(f"  Backend   : {args.api_backend}")
    print(f"  Salida    : {output_tex}")
    print(f"{'═'*56}")

    code = flujo_completo(
        tema=args.tema,
        nivel=args.nivel,
        modelo=args.modelo,
        api_backend=args.api_backend,
        output_tex=output_tex,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
