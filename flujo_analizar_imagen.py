#!/usr/bin/env python3
"""
flujo_analizar_imagen.py — Orquestador del flujo de análisis de imágenes (Layer 2)

Ejecuta el flujo completo definido en la directiva analizar_imagen.yaml:
  1. analizar_imagen.py      → Lee las imágenes y obtiene análisis del LLM (JSON)
  2. generar_informe_imagen.py → Convierte el JSON en informe LaTeX (.tex)
  3. (presentación)          → Muestra el resumen del análisis al usuario
  4. alert_user.py           → Notifica al usuario con alerta audible

Uso:
    python3 flujo_analizar_imagen.py foto1.jpg,foto2.jpg
    python3 flujo_analizar_imagen.py "*.jpg" --prompt "Describe este circuito"
    python3 flujo_analizar_imagen.py esquema.png --modelo gemini-1.5-pro

El informe .tex se guarda en docs/IMAGENES/informe_imagen/ por defecto.
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
ANALIZAR     = SCRIPT_DIR / "execution" / "analizar_imagen.py"
GENERAR      = SCRIPT_DIR / "execution" / "generar_informe_imagen.py"
ALERTAR      = SCRIPT_DIR / "execution" / "alert_user.py"
TMP_DIR      = SCRIPT_DIR / ".tmp"
STATE_FILE   = TMP_DIR / "run_state.json"
DEFAULT_OUT  = SCRIPT_DIR / "docs" / "IMAGENES" / "informe_imagen"


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
    imagenes: str,
    modelo: str,
    prompt: str,
    api_backend: str,
    output_dir: Path,
) -> int:
    """
    Ejecuta los 4 pasos del flujo. Retorna 0 si todo salió bien, >0 si hubo error.
    """

    run_id = f"flujo-imagen-{now_iso()[:19].replace(':', '-')}"
    # Usar solo los basenames para evitar rutas absolutas en el nombre del archivo
    _partes = [Path(p.strip()).stem for p in imagenes.split(",")]
    nombre_base = f"analisis_{'_'.join(_partes).replace('*', 'glob')}"
    json_tmp    = TMP_DIR / f"{nombre_base}.json"
    output_tex  = output_dir / f"informe_{nombre_base}.tex"

    state = {
        "run_id": run_id,
        "directive": "analizar_imagen.yaml",
        "imagenes": imagenes,
        "started_at": now_iso(),
        "last_updated": now_iso(),
        "current_step": 0,
        "steps_completed": [],
        "steps_failed": [],
        "context": {},
    }
    save_state(state)

    total_pasos = 5

    # ══ PASO 1: Analizar imágenes con LLM ════════════════════════════════════════
    print_step(1, total_pasos, f"Analizando imágenes con {modelo}...")
    print(f"  Imágenes: {imagenes}")
    if prompt:
        print(f"  Prompt  : {prompt[:120]}{'…' if len(prompt) > 120 else ''}")

    cmd_analizar = [
        PYTHON, str(ANALIZAR),
        imagenes,
        "--modelo", modelo,
        "--prompt", prompt,
        "--api-backend", api_backend,
    ]

    code, analisis = run_script(cmd_analizar, capture_json=True)

    if code != 0 or analisis.get("status") != "ok":
        if api_backend == "groq":
            print_err("Falló Groq. Intentando como respaldo automático con Gemini...")
            cmd_fallback = list(cmd_analizar)
            if "--api-backend" in cmd_fallback:
                cmd_fallback[cmd_fallback.index("--api-backend") + 1] = "gemini"
            if "--modelo" in cmd_fallback:
                cmd_fallback[cmd_fallback.index("--modelo") + 1] = "gemini-2.5-flash"
            code, analisis = run_script(cmd_fallback, capture_json=True)
            
        if code != 0 or analisis.get("status") != "ok":
            print_err("Falló el respaldo. Intentando como último recurso con OpenRouter...")
            cmd_fallback = list(cmd_analizar)
            if "--api-backend" in cmd_fallback:
                cmd_fallback[cmd_fallback.index("--api-backend") + 1] = "openrouter"
            if "--modelo" in cmd_fallback:
                cmd_fallback[cmd_fallback.index("--modelo") + 1] = "google/gemini-2.5-flash"
            code, analisis = run_script(cmd_fallback, capture_json=True)

        if code != 0 or analisis.get("status") != "ok":
            msg = analisis.get("message", analisis.get("raw_output", "Error desconocido"))
            print_err(f"Falló analizar_imagen.py (código {code}): {msg}")
            state["steps_failed"].append({
                "step": 1, "script": "analizar_imagen.py",
                "code": code, "message": msg,
            })
        state["last_updated"] = now_iso()
        save_state(state)
        subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return code if code != 0 else 1

    # Guardar JSON intermedio en .tmp/
    TMP_DIR.mkdir(exist_ok=True)
    json_tmp.write_text(json.dumps(analisis, ensure_ascii=False, indent=2), encoding="utf-8")

    archivos = analisis.get("archivos_procesados", [])
    desc     = analisis.get("analisis", {}).get("descripcion_general", "N/A")
    tokens   = analisis.get("tokens_usados", {}).get("total", "N/A")

    print_ok(f"Análisis completado — Imágenes: {len(archivos)}  |  Tokens: {tokens}")
    print_ok(f"Descripción: {desc[:150]}{'…' if len(desc) > 150 else ''}")
    print_ok(f"JSON guardado en: {json_tmp.name}")

    state["current_step"] = 1
    state["steps_completed"].append({
        "step": 1, "script": "analizar_imagen.py", "status": "ok",
        "archivos": archivos, "descripcion": desc,
        "tokens_total": tokens, "json_tmp": str(json_tmp),
    })
    state["context"].update({"archivos": archivos, "descripcion": desc})
    state["last_updated"] = now_iso()
    save_state(state)

    # ══ PASO 2: Generar informe LaTeX ═════════════════════════════════════════
    print_step(2, total_pasos, "Generando informe LaTeX...")

    cmd_informe = [
        PYTHON, str(GENERAR),
        "--json", str(json_tmp),
        "--output", str(output_tex),
    ]

    code, informe_result = run_script(cmd_informe, capture_json=True)

    if code != 0 or informe_result.get("status") != "ok":
        msg = informe_result.get("message", informe_result.get("raw_output", "Error desconocido"))
        print_err(f"Falló generar_informe_imagen.py (código {code}): {msg}")
        state["steps_failed"].append({
            "step": 2, "script": "generar_informe_imagen.py",
            "code": code, "message": msg,
        })
        state["last_updated"] = now_iso()
        save_state(state)
        subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return code if code != 0 else 1

    print_ok(f"Informe generado: {output_tex}")

    state["current_step"] = 2
    state["steps_completed"].append({
        "step": 2, "script": "generar_informe_imagen.py", "status": "ok",
        "archivo_tex": str(output_tex),
    })
    state["context"]["archivo_tex"] = str(output_tex)
    state["last_updated"] = now_iso()
    save_state(state)

    # ══ PASO 3: Presentar resumen del análisis ═════════════════════════════════
    print_step(3, total_pasos, "Presentando resumen del análisis...")

    analisis_data = analisis.get("analisis", {})
    elementos = analisis_data.get("elementos_detectados", [])
    texto     = analisis_data.get("texto_extraido", "")
    obs       = analisis_data.get("observaciones", "")

    bar = "─" * 56
    print(f"\n{bar}")
    print("  RESUMEN DEL ANÁLISIS")
    print(f"{bar}")
    print(f"  Archivos analizados: {len(archivos)}")
    for a in archivos:
        print(f"    • {Path(a).name}")
    print(f"\n  Descripción general:")
    print(f"    {desc}")
    if elementos:
        print(f"\n  Elementos detectados ({len(elementos)}):")
        for el in elementos:
            nombre = el.get("nombre", "?")
            detalle = el.get("descripcion", "")
            print(f"    • {nombre}: {detalle[:100]}")
    if texto:
        print(f"\n  Texto extraído:")
        print(f"    {texto[:300]}{'…' if len(texto) > 300 else ''}")
    if obs:
        print(f"\n  Observaciones:")
        print(f"    {obs[:300]}{'…' if len(obs) > 300 else ''}")
    print(f"{bar}\n")

    print_ok("Resumen presentado.")

    state["current_step"] = 3
    state["steps_completed"].append({
        "step": 3, "script": "presentación", "status": "ok",
    })
    state["last_updated"] = now_iso()
    save_state(state)

    # ══ PASO 4: Compilar informe LaTeX a PDF ══════════════════════════════════
    print_step(4, total_pasos, "Compilando informe LaTeX a PDF...")
    
    informe_pdf = "N/A"
    try:
        from execution.compile_latex import compile_latex_code
        
        latex_content = output_tex.read_text(encoding="utf-8")
        job_name = output_tex.stem
        output_parent = str(output_tex.parent.resolve())
        
        comp_res = compile_latex_code(latex_content, job_name=job_name, output_dir=output_parent)
        
        if comp_res["success"]:
            informe_pdf = Path(comp_res["pdf_path"])
            print_ok(f"Informe PDF generado: {informe_pdf}")
            
            state["current_step"] = 4
            state["steps_completed"].append({
                "step": 4, "script": "compile_latex.py", "status": "ok",
                "archivo_pdf": str(informe_pdf),
            })
            state["context"]["archivo_pdf"] = str(informe_pdf)
            state["last_updated"] = now_iso()
            save_state(state)
        else:
            err_msg = comp_res.get("error", "Error desconocido en pdflatex")
            print_err(f"Falló la compilación del informe PDF: {err_msg}")
            state["steps_failed"].append({
                "step": 4, "script": "compile_latex.py",
                "code": 1, "message": err_msg
            })
            state["last_updated"] = now_iso()
            save_state(state)
            subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
            return 1
            
    except Exception as e:
        print_err(f"Error crítico al compilar el informe PDF: {str(e)}")
        subprocess.run([PYTHON, str(ALERTAR), "error"], capture_output=True)
        return 1

    # ══ PASO 5: Alerta de completado ═══════════════════════════════════════════
    print_step(5, total_pasos, "Notificando al usuario...")
    subprocess.run([PYTHON, str(ALERTAR), "success"], capture_output=True)
    print_ok("Alerta de completado emitida.")

    state["current_step"] = 5
    state["steps_completed"].append({
        "step": 5, "script": "alert_user.py", "status": "ok",
        "tipo": "success",
    })
    state["last_updated"] = now_iso()
    save_state(state)

    # ══ RESUMEN FINAL ══════════════════════════════════════════════════════════
    bar = "═" * 56
    print(f"\n{bar}")
    print("  FLUJO COMPLETADO — Análisis de imágenes")
    print(f"{bar}")
    print(f"  Imágenes analizadas : {len(archivos)}")
    print(f"  Modelo usado        : {modelo}  |  Tokens: {tokens}")
    print(f"  Informe PDF         : {informe_pdf}")
    print(f"  Informe LaTeX       : {output_tex}")
    print(f"  JSON de análisis    : {json_tmp}")
    print(f"{bar}\n")

    return 0


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Flujo completo: analiza imágenes con LLM multimodal y genera informe LaTeX.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 flujo_analizar_imagen.py foto1.jpg,foto2.jpg
  python3 flujo_analizar_imagen.py "*.jpg" --prompt "Describe este circuito"
  python3 flujo_analizar_imagen.py esquema.png --modelo gemini-1.5-pro
        """,
    )
    parser.add_argument(
        "imagenes",
        help="Ruta(s) a las imágenes separadas por coma, o patrón glob (ej: '*.jpg').",
    )
    parser.add_argument("--modelo", default="gemini-2.5-flash",
                        help="Modelo a usar (default: gemini-2.5-flash).")
    parser.add_argument(
        "--prompt",
        default="Describe detalladamente lo que ves en la(s) imagen(es).",
        help="Instrucción de análisis para el modelo.",
    )
    parser.add_argument("--api-backend", default="gemini",
                        choices=["gemini", "openrouter", "groq"],
                        help="Backend de API: gemini, openrouter o groq. (default: gemini).")
    parser.add_argument(
        "--output-dir",
        default=None,
        help=f"Carpeta de salida del .tex. Por defecto: {DEFAULT_OUT}",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUT
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'═'*56}")
    print("  ELECTRÓNICA — Flujo de Análisis de Imágenes")
    print(f"{'═'*56}")
    print(f"  Directiva : analizar_imagen.yaml")
    print(f"  Imágenes  : {args.imagenes}")
    print(f"  Modelo    : {args.modelo}")
    print(f"  Backend   : {args.api_backend}")
    print(f"  Salida    : {output_dir}")
    print(f"{'═'*56}")

    code = flujo_completo(
        imagenes=args.imagenes,
        modelo=args.modelo,
        prompt=args.prompt,
        api_backend=args.api_backend,
        output_dir=output_dir,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
