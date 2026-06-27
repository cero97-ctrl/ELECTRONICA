#!/usr/bin/env python3
"""
evaluar_examen.py — Orquestador del flujo de evaluación de exámenes (Layer 2)

Ejecuta el flujo completo definido en la directiva evaluar_examen_estudiante.yaml:
  1. evaluar_examen.py  → Lee el PDF y obtiene evaluación de Gemini (JSON)
  2. generar_informe.py → Convierte el JSON en informe LaTeX (.tex)
  3. alert_user.py      → Notifica al usuario con alerta audible

Uso:
    python3 evaluar_examen.py --pdf examenes/01/examen_estudiantes/Ana_Alcala.pdf
    python3 evaluar_examen.py --pdf <ruta> [--modelo gemini-2.5-flash] [--dpi 250]
    python3 evaluar_examen.py --pdf <ruta> [--output-dir <carpeta>] [--rubrica <yaml>]

El informe .tex se guarda en ../informe_examen/ por defecto.
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
EVALUAR      = SCRIPT_DIR / "execution" / "evaluar_examen.py"
GENERAR      = SCRIPT_DIR / "execution" / "generar_informe.py"
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
    """
    Ejecuta un script y retorna (returncode, resultado).
    Si capture_json=True, parsea stdout como JSON.
    """
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
    pdf_path: Path,
    modelo: str,
    dpi: int,
    rubrica: str | None,
    output_dir: Path,
    api_backend: str = "gemini",
) -> int:
    """
    Ejecuta los 3 pasos del flujo. Retorna 0 si todo salió bien, >0 si hubo error.
    Sigue la regla de Layer 2: guardar estado en run_state.json tras cada paso exitoso.
    """

    run_id = f"flujo-{pdf_path.stem}-{now_iso()[:19].replace(':', '-')}"
    nombre = pdf_path.stem.replace("examen_", "").replace("evaluacion_", "").replace("_", " ")
    output_tex = output_dir / f"informe_{pdf_path.stem}.tex"
    json_tmp   = TMP_DIR / f"evaluacion_{pdf_path.stem}.json"

    state = {
        "run_id": run_id,
        "directive": "evaluar_examen_estudiante.yaml",
        "estudiante": nombre,
        "pdf": str(pdf_path.resolve()),
        "started_at": now_iso(),
        "last_updated": now_iso(),
        "current_step": 0,
        "steps_completed": [],
        "steps_failed": [],
        "context": {},
    }
    save_state(state)

    total_pasos = 3

    # ══ PASO 1: Evaluar examen con LLM ═══════════════════════════════════════════
    print_step(1, total_pasos, f"Evaluando examen con {modelo}...")
    print(f"  PDF: {pdf_path}")

    cmd_evaluar = [PYTHON, str(EVALUAR), "--pdf", str(pdf_path),
                   "--modelo", modelo, "--dpi", str(dpi), "--api-backend", api_backend]
    if rubrica:
        cmd_evaluar += ["--rubrica", rubrica]

    code, evaluacion = run_script(cmd_evaluar, capture_json=True)

    if code != 0 or evaluacion.get("status") != "ok":
        if api_backend == "groq":
            print_err("Falló Groq. Intentando como respaldo automático con Gemini...")
            cmd_fallback = list(cmd_evaluar)
            if "--api-backend" in cmd_fallback:
                cmd_fallback[cmd_fallback.index("--api-backend") + 1] = "gemini"
            if "--modelo" in cmd_fallback:
                cmd_fallback[cmd_fallback.index("--modelo") + 1] = "gemini-1.5-flash"
            code, evaluacion = run_script(cmd_fallback, capture_json=True)
            
        if code != 0 or evaluacion.get("status") != "ok":
            print_err("Falló el respaldo. Intentando como último recurso con OpenRouter...")
            cmd_fallback = list(cmd_evaluar)
            if "--api-backend" in cmd_fallback:
                cmd_fallback[cmd_fallback.index("--api-backend") + 1] = "openrouter"
            if "--modelo" in cmd_fallback:
                cmd_fallback[cmd_fallback.index("--modelo") + 1] = "qwen/qwen-2.5-vl-72b-instruct:free"
            code, evaluacion = run_script(cmd_fallback, capture_json=True)

        if code != 0 or evaluacion.get("status") != "ok":
            msg = evaluacion.get("message", evaluacion.get("raw_output", "Error desconocido"))
            print_err(f"Falló evaluar_examen.py (código {code}): {msg}")
            state["steps_failed"].append({"step": 1, "script": "evaluar_examen.py",
                                      "code": code, "message": msg})
        state["last_updated"] = now_iso()
        save_state(state)
        subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return code if code != 0 else 1

    # Guardar JSON intermedio en .tmp/
    TMP_DIR.mkdir(exist_ok=True)
    json_tmp.write_text(json.dumps(evaluacion, ensure_ascii=False, indent=2), encoding="utf-8")

    puntaje = evaluacion.get("evaluacion", {}).get("puntaje_sugerido", "N/A")
    nivel   = evaluacion.get("evaluacion", {}).get("nivel_desempeno", "N/A")
    tokens  = evaluacion.get("tokens_usados", {}).get("total", "N/A")
    paginas = evaluacion.get("paginas_procesadas", "N/A")

    print_ok(f"Evaluación completada — Puntaje: {puntaje}  |  Nivel: {nivel}")
    print_ok(f"Páginas procesadas: {paginas}  |  Tokens totales: {tokens}")
    print_ok(f"JSON guardado en: {json_tmp.name}")

    state["current_step"] = 1
    state["steps_completed"].append({
        "step": 1, "script": "evaluar_examen.py", "status": "ok",
        "puntaje_sugerido": puntaje, "nivel_desempeno": nivel,
        "tokens_total": tokens, "json_tmp": str(json_tmp),
    })
    state["context"].update({"puntaje": puntaje, "nivel": nivel})
    state["last_updated"] = now_iso()
    save_state(state)

    # ══ PASO 2: Generar informe LaTeX ══════════════════════════════════════════
    print_step(2, total_pasos, "Generando informe LaTeX...")

    cmd_informe = [PYTHON, str(GENERAR),
                   "--json", str(json_tmp),
                   "--output", str(output_tex)]

    code, informe_result = run_script(cmd_informe, capture_json=True)

    if code != 0 or informe_result.get("status") != "ok":
        msg = informe_result.get("message", informe_result.get("raw_output", "Error desconocido"))
        print_err(f"Falló generar_informe.py (código {code}): {msg}")
        state["steps_failed"].append({"step": 2, "script": "generar_informe.py",
                                      "code": code, "message": msg})
        state["last_updated"] = now_iso()
        save_state(state)
        subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return code if code != 0 else 1

    print_ok(f"Informe generado: {output_tex}")

    state["current_step"] = 2
    state["steps_completed"].append({
        "step": 2, "script": "generar_informe.py", "status": "ok",
        "archivo_tex": str(output_tex),
    })
    state["context"]["archivo_tex"] = str(output_tex)
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
    print(f"  FLUJO COMPLETADO — {nombre}")
    print(f"{bar}")
    print(f"  Puntaje sugerido : {puntaje}")
    print(f"  Nivel            : {nivel}")
    print(f"  Informe LaTeX    : {output_tex}")
    print(f"  JSON de evaluac. : {json_tmp}")
    print(f"  Modelo usado     : {modelo}  |  Tokens: {tokens}")
    print(f"{bar}\n")
    print("  💡 Para compilar el PDF:")
    print(f"     cd {output_tex.parent}")
    print(f"     pdflatex {output_tex.name}\n")

    return 0


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Flujo completo: evalúa un examen en PDF y genera el informe LaTeX.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 evaluar_examen.py --pdf examenes/01/examen_estudiantes/Ana_Alcala.pdf
  python3 evaluar_examen.py --pdf examenes/02/examen_estudiantes/Juan_Perez.pdf --modelo gemini-1.5-pro
  python3 evaluar_examen.py --pdf <ruta> --dpi 300 --output-dir informes/
        """,
    )
    parser.add_argument("--pdf", required=True,
                        help="Ruta al PDF del examen del estudiante.")
    parser.add_argument("--modelo", default="llama-3.2-90b-vision-preview",
                        help="Modelo a usar (default: llama-3.2-90b-vision-preview).")
    parser.add_argument("--api-backend", default="groq",
                        choices=["gemini", "openrouter", "groq"],
                        help="Backend de API: gemini, openrouter o groq. (default: groq).")
    parser.add_argument("--dpi", type=int, default=250,
                        help="DPI de renderizado del PDF (default: 250).")
    parser.add_argument("--rubrica", default=None,
                        help="(Opcional) Ruta a la rúbrica YAML del examen.")
    parser.add_argument("--output-dir", default=None,
                        help="Carpeta de salida del .tex. Por defecto: misma carpeta del PDF.")
    return parser.parse_args()


def main():
    args = parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print_err(f"PDF no encontrado: {args.pdf}")
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else pdf_path.parent.parent / "informe_examen"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'═'*56}")
    print(f"  ELECTRÓNICA — Flujo de Evaluación de Exámenes")
    print(f"{'═'*56}")
    print(f"  Directiva : evaluar_examen_estudiante.yaml")
    print(f"  Estudiante: {pdf_path.stem.replace('_', ' ')}")
    print(f"  Modelo    : {args.modelo}")
    print(f"  Backend   : {args.api_backend}  |  DPI: {args.dpi}")
    print(f"{'═'*56}")

    code = flujo_completo(
        pdf_path=pdf_path,
        modelo=args.modelo,
        dpi=args.dpi,
        rubrica=args.rubrica,
        output_dir=output_dir,
        api_backend=args.api_backend,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
