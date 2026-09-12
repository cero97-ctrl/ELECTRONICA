#!/usr/bin/env python3
"""
flujo_sync_faq_flujo.py — Orquestador: mantiene faq_higiene_estado_sesion_flujo.{tex,pdf}
sincronizados con faq_higiene_estado_sesion.md (Layer 2)

Detecta cambios por hash SHA-256 del .md (estado en .tmp/faq_flujo_sync.json) y, si detecta
uno, encadena:
  1. execution/regenerar_faq_flujo.py   → actualiza el .tex (campos deterministas + LLM solo
                                          si el cambio es estructural; avisa de consumo de créditos)
  2. execution/compile_latex.py           → compila 2 pasadas a .tmp/latex_build
  3. copia del PDF a docs/AGENTE_IA/      → entregable actualizado
  4. execution/verificar_pdf.py           → guardrail determinista (errores, Overfull, solapes bbox)
  5. estado + snapshot del .md            → para detectar el próximo cambio

Uso:
    python3 flujo_sync_faq_flujo.py                        # sincronización puntual (--once implícito)
    python3 flujo_sync_faq_flujo.py --watch [--interval 60] # bucle en segundo plano (polling hash)
    python3 flujo_sync_faq_flujo.py --force                 # ignorar el hash (re-sincronizar sí o sí)
    python3 flujo_sync_faq_flujo.py --no-llm                # solo parte determinista (aborta si hay cambios estructurales)
    python3 flujo_sync_faq_flujo.py --dry-run               # muestra qué haría, sin escribir ni compilar

Salida (stdout):
    JSON por corrida. Códigos de salida: 0 ok / sin cambios, 1 error, 3 cambio estructural bloqueado por --no-llm.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
PYTHON = sys.executable
REGENERAR = SCRIPT_DIR / "execution" / "regenerar_faq_flujo.py"
VERIFICAR = SCRIPT_DIR / "execution" / "verificar_pdf.py"
ALERTAR = SCRIPT_DIR / "execution" / "alert_user.py"
DOCS_DIR = SCRIPT_DIR / "docs" / "AGENTE_IA"
TMP_DIR = SCRIPT_DIR / ".tmp"
STATE_FILE = TMP_DIR / "faq_flujo_sync.json"
SNAPSHOT_FILE = TMP_DIR / "faq_flujo_md_snapshot.md"
LOG_FILE = TMP_DIR / "faq_flujo_sync.log"
BUILD_DIR = TMP_DIR / "latex_build"

MD_DEFAULT = DOCS_DIR / "faq_higiene_estado_sesion.md"
TEX_DEFAULT = DOCS_DIR / "faq_higiene_estado_sesion_flujo.tex"
PDF_DEFAULT = DOCS_DIR / "faq_higiene_estado_sesion_flujo.pdf"
JOB_NAME = "faq_higiene_estado_sesion_flujo"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _leer_estado() -> dict:
    if STATE_FILE.is_file():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _guardar_estado(state: dict) -> None:
    TMP_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _log(line: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    TMP_DIR.mkdir(exist_ok=True)
    LOG_FILE.open("a", encoding="utf-8").write(f"[{ts}] {line}\n")
    print(f"[sync] {line}", flush=True)


def _alerta(tipo: str, msg: str = "") -> None:
    try:
        subprocess.run([PYTHON, str(ALERTAR), tipo, "--message", msg], capture_output=True, timeout=10)
    except Exception:
        pass


def sync_once(args) -> dict:
    md, tex, pdf = Path(args.md), Path(args.tex), Path(args.pdf or (DOCS_DIR / f"{JOB_NAME}.pdf"))
    for p, nombre in ((md, "md"), (tex, "tex")):
        if not p.is_file():
            _log(f"[ERROR] Falta el archivo {nombre}: {p}")
            _alerta("error", f"sync_faq: falta {nombre}")
            return {"status": "error", "message": f"Falta {p}"}

    estado = _leer_estado()
    md_sha = _sha256(md)
    if not args.force and estado.get("md_sha256") == md_sha:
        return {"status": "ok", "cambio": False, "message": "Sin cambios en el markdown (hash idéntico)."}

    _log("Cambio detectado en el .md — iniciando sincronización.")

    # ── Plan: ¿hará falta LLM? (aviso de créditos antes de consumir) ─────────────
    plan_cmd = [PYTHON, str(REGENERAR), "--md", str(md), "--tex", str(tex),
                "--snapshot", str(SNAPSHOT_FILE), "--plan"]
    plan_code = subprocess.run(plan_cmd, capture_output=True, text=True, encoding="utf-8").returncode
    try:
        plan = json.loads(subprocess.run(plan_cmd, capture_output=True, text=True, encoding="utf-8").stdout)
    except json.JSONDecodeError:
        plan = {}

    if plan.get("llm_necesario"):
        if args.no_llm:
            _log("[WARN] Cambio estructural detectado pero --no-llm: la sincronización fallará por diseño.")
        else:
            _log("[AVISO] Cambio estructural -> se usará el LLM vía OpenRouter (consume créditos). "
                 "Si no quieres, cancela ahora o relanza con --no-llm.")

    if args.dry_run:
        extra = {k: v for k, v in plan.items() if k in ("cambios", "llm_necesario", "known_fields")}
        resultado = {"status": "ok", "cambio": True, "dry_run": True,
                     "message": "Plan simulado (sin escribir ni compilar).", **extra}
        _log(f"[DRY-RUN] {json.dumps(extra, ensure_ascii=False)}")
        return resultado

    # ── Paso 1: regenerar el .tex ────────────────────────────────────────────────
    regen_cmd = [PYTHON, str(REGENERAR), "--md", str(md), "--tex", str(tex),
                 "--snapshot", str(SNAPSHOT_FILE)]
    if args.no_llm:
        regen_cmd.append("--no-llm")
    if args.critico:
        regen_cmd.append("--critico")
    proc = subprocess.run(regen_cmd, capture_output=True, text=True, encoding="utf-8")
    try:
        regen = json.loads(proc.stdout)
    except json.JSONDecodeError:
        regen = {"status": "error", "message": proc.stdout + proc.stderr}

    if regen.get("status") != "ok":
        _log(f"[ERROR] regenerar_faq_flujo.py (código {proc.returncode}): {regen.get('message', '')}")
        _alerta("error", f"sync_faq: fallo la regeneración ({proc.returncode})")
        return {"status": "error", "code": proc.returncode if proc.returncode else 1, **regen}

    tex_sha = _sha256(tex)

    # ── Paso 2+3: compilar y copiar (solo si cambió el .tex) ────────────────────
    verificacion = {"paginas": None, "errores": [], "overfull": [], "solapes_total": None}
    if regen.get("tex_cambiado"):
        _log("Regenerando PDF (2 pasadas pdflatex)...")
        try:
            sys.path.insert(0, str(SCRIPT_DIR))
            from execution.compile_latex import compile_latex_code, clean_latex_aux_files
            contenido = tex.read_text(encoding="utf-8")
            res = compile_latex_code(contenido, job_name=JOB_NAME, output_dir=str(BUILD_DIR), clean=False)
        except Exception as e:
            res = {"success": False, "error": str(e)}
        if not res.get("success"):
            _log(f"[ERROR] Compilación LaTeX falló: {res.get('error', 'desconocido')}")
            _alerta("error", "sync_faq: falló la compilación LaTeX")
            return {"status": "error", "code": 1, "message": res.get("error")}

        pdf_build = BUILD_DIR / f"{JOB_NAME}.pdf"
        if pdf_build.is_file():
            shutil.copyfile(pdf_build, pdf)

        # ── Paso 4: verificación determinista (log conservado por clean=False) ───
        ver_cmd = [PYTHON, str(VERIFICAR), "--pdf", str(pdf_build), "--log", str(BUILD_DIR / f"{JOB_NAME}.log")]
        try:
            verificacion = json.loads(subprocess.run(ver_cmd, capture_output=True, text=True, encoding="utf-8").stdout)
        except (json.JSONDecodeError, subprocess.SubprocessError):
            verificacion = {"status": "error", "message": "verificar_pdf.py no devolvió JSON"}
        clean_latex_aux_files(str(BUILD_DIR))
        if verificacion.get("errores"):
            _log(f"[WARN] Compilación con errores '!': {verificacion['errores']}")
        if verificacion.get("solapes_total"):
            _log(f"[WARN] {verificacion['solapes_total']} solapes de texto detectados por bbox.")
        _log(f"PDF verificado: {verificacion.get('paginas', '?')} páginas, "
             f"{verificacion.get('overfull', []).__len__()} Overfull, "
             f"{verificacion.get('solapes_total', 0)} solapes.")

    else:
        _log("El .md cambió pero no impacta el .tex (metadatos/campos ya sincronizados): sin recompilar.")

    # ── Paso 5: estado + snapshot ────────────────────────────────────────────────
    estado = {
        "md_sha256": md_sha,
        "tex_sha256": tex_sha,
        "ultimo_sync": datetime.now(timezone.utc).isoformat(),
        "via": regen.get("via"),
        "secciones": [c for c in regen.get("cambios", [])],
        "known_fields": regen.get("known_fields", {}),
        "edits": regen.get("edits_total", 0),
    }
    _guardar_estado(estado)
    SNAPSHOT_FILE.write_text(md.read_text(encoding="utf-8"), encoding="utf-8")

    _alerta("success", f"sync_faq: {regen.get('via', 'ok')} {'(tex actualizado)' if regen.get('tex_cambiado') else '(sin cambios en tex)'}")
    _log(f"Sincronización completada — vía: {regen.get('via')}, "
         f"tex_cambiado: {regen.get('tex_cambiado')}, edits_LLM: {regen.get('edits_total', 0)}.")

    return {
        "status": "ok",
        "cambio": True,
        "via": regen.get("via"),
        "tex_cambiado": regen.get("tex_cambiado"),
        "secciones": regen.get("cambios", []),
        "edits": regen.get("edits_total", 0),
        "verificacion": verificacion,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sincroniza .tex/.pdf de diagramas con su FAQ markdown.")
    parser.add_argument("--md", default=str(MD_DEFAULT))
    parser.add_argument("--tex", default=str(TEX_DEFAULT))
    parser.add_argument("--pdf", default=None, help="Ruta del PDF destino (default: junto al .tex).")
    parser.add_argument("--watch", action="store_true", help="Bucle continuo (polling por hash).")
    parser.add_argument("--interval", type=int, default=60, help="Segundos entre chequeos en --watch (default 60).")
    parser.add_argument("--force", action="store_true", help="Ignorar el hash y re-sincronizar.")
    parser.add_argument("--no-llm", action="store_true", help="Solo parte determinista; aborta ante cambios estructurales.")
    parser.add_argument("--critico", action="store_true", help="Escala la re-traducción LLM a opus (enrutador).")
    parser.add_argument("--dry-run", action="store_true", help="Muestra el plan sin escribir ni compilar.")
    args = parser.parse_args()

    if not args.watch:
        resultado = sync_once(args)
        print(json.dumps(resultado, ensure_ascii=False))
        return 0 if resultado.get("status") == "ok" else (resultado.get("code", 1) or 1)

    _log(f"[WATCH] Observando {args.md} cada {args.interval}s (Ctrl-C para salir).")
    try:
        while True:
            resultado = sync_once(args)
            if resultado.get("cambio") is False:
                pass  # sin cambios, espera normal
            time.sleep(max(5, args.interval))
    except KeyboardInterrupt:
        _log("[WATCH] Detenido por Ctrl-C.")
        return 0


if __name__ == "__main__":
    sys.exit(main())