#!/usr/bin/env python3
"""
flujo_libro_a_skill.py — Orquestador: convertir un libro PDF en un skill global
(Layer 2: Orchestration)

Ejecuta el flujo completo definido en la directiva libro_a_skill.yaml:
  1. Entrevista ligera (tema, nombre, idioma, alcance, objetivo, confirmación).
  2. extraer_libro_pdf.py   → extrae el texto del PDF (determinista).
  3. enrutador.py           → decisión determinista de tier (contexto masivo).
  4. sintetizar_skill.py    → destila SKILL.md + references/ con LLM.
  5. validar_skill_formulas.py → valida bloques Python/SymPy (neuro-simbólico,
     determinista) y, si se pide --reflexion, re-sintetiza con correcciones.
  6. generar_latex_skill.py → reporte LaTeX (SKILL.md + references) en docs/SKILL/<name>/.
  7. instalar_skill.py      → copia a ~/.config/opencode/skills/<name>/.
  8. alert_user.py          → notifica + aviso de reiniciar opencode.

Uso:
    python3 flujo_libro_a_skill.py --pdf <libro.pdf> [--tema "..."] [--nombre <name>]
        [--idioma es] [--modelo <id>] [--sobrescribir] [--dry-run] [--no-alert]
        [--no-latex] [--validar-estricto] [--reflexion N] [--salida .tmp/skill_<name>/]

--pdf es requerido. Si no se pasan --tema/--nombre/--idioma, se entrevista al
usuario. Con --dry-run se genera el skill pero NO se instala en global.

Consume créditos OpenRouter en la síntesis (default deepseek).
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
PYTHON = sys.executable

EXTRAER = SCRIPT_DIR / "execution" / "extraer_libro_pdf.py"
ENRUTADOR = SCRIPT_DIR / "execution" / "enrutador.py"
SINTETIZAR = SCRIPT_DIR / "execution" / "sintetizar_skill.py"
VALIDAR_FORMULAS = SCRIPT_DIR / "execution" / "validar_skill_formulas.py"
INSTALAR = SCRIPT_DIR / "execution" / "instalar_skill.py"
GENERAR_LATEX = SCRIPT_DIR / "execution" / "generar_latex_skill.py"
ALERTAR = SCRIPT_DIR / "execution" / "alert_user.py"

TMP_DIR = SCRIPT_DIR / ".tmp"
STATE_FILE = TMP_DIR / "run_state.json"
DESTINO_GLOBAL = Path.home() / ".config" / "opencode" / "skills"

DEFAULT_MODEL = "deepseek/deepseek-v4-pro"


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


def _msg_fallo(d: dict | str, fallback: str) -> str:
    """Extrae el mejor mensaje de fallo: message JSON, stderr o raw_output."""
    if isinstance(d, dict):
        m = d.get("message")
        if m:
            return str(m)
        err = d.get("stderr")
        if err and str(err).strip():
            return str(err).strip().splitlines()[-1]
        raw = d.get("raw_output")
        if raw and str(raw).strip():
            return str(raw)[:200]
    return fallback


def preguntar(prompt: str, default=None) -> str:
    if default:
        prompt = f"{prompt} [{default}] "
    try:
        r = input(prompt).strip()
    except EOFError:
        r = ""
    return r or (default or "")


def slug_name(texto: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", texto.lower()).strip("_")
    return s[:40] or "libro"


def confirmar(prompt: str, default="s") -> bool:
    try:
        r = input(f"{prompt} [{'S/n' if default == 's' else 's/N'}] ").strip().lower()
    except EOFError:
        r = ""
    if not r:
        return default == "s"
    return r in ("s", "si", "y", "yes")


# ── Entrevista ligera ─────────────────────────────────────────────────────────

def entrevista(pdf: Path, tema, nombre, idioma) -> dict:
    """Recoge los campos no provistos por CLI. Progreso transpirable a JSON."""
    nombre = nombre or preguntar("Nombre del skill (snake_case, ej. electronica_smps):", slug_name(pdf.stem))
    tema_provisto = bool(tema)
    tema = tema or preguntar("¿De qué trata el libro? (dominio, ej. Física, Electrónica):", "Electrónica")
    idioma = idioma or preguntar("Idioma del skill", "es")

    print("\n── Alcance del skill ──")
    print("  El skill será de REFERENCIA RÁPIDA (conceptos, fórmulas, tablas, glosario).")
    acotar = confirmar("¿Acotar a capítulos/secciones específicos del libro? (s/N)", default="n")
    alcance = {"tipo": "completo"}
    if acotar:
        rango = preguntar("Indica rango de páginas o secciones (ej. 1-80):", "all")
        alcance = {"tipo": "parcial", "rango": rango}
    else:
        alcance = {"tipo": "completo"}

    objetivo = "Referencia rápida: conceptos clave, fórmulas, tablas e índices del libro."
    print("\n  Objetivo confirmado: " + objetivo)

    print("\n── Instalación ──")
    print(f"  Destino global: {DESTINO_GLOBAL / nombre}")
    confirmar_inst = confirmar(f"¿Instalar el skill en global (~/.config/opencode/skills/{nombre})?", "s")

    return {
        "nombre": nombre,
        "tema": tema,
        "tema_provisto": tema_provisto,
        "idioma": idioma,
        "alcance": alcance,
        "objetivo": objetivo,
        "instalar_global": confirmar_inst,
    }


# ── Núcleo del flujo ──────────────────────────────────────────────────────────

def check_pdf(pdf: Path) -> None:
    if not pdf.is_file():
        print(f"  ❌ No existe el PDF: {pdf}", file=sys.stderr)
        sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, help="Ruta del libro PDF.")
    parser.add_argument("--tema", default=None, help="Tema/dominio del libro.")
    parser.add_argument("--nombre", default=None, help="Nombre del skill (snake_case).")
    parser.add_argument("--idioma", default=None, help="Idioma del skill (default es).")
    parser.add_argument("--modelo", default=None, help="ID de modelo OpenRouter (override del tier).")
    parser.add_argument("--salida", default=None, help="Dir local del skill generado.")
    parser.add_argument("--sobrescribir", action="store_true", help="Sobrescribir skill global existente.")
    parser.add_argument("--no-latex", action="store_true", help="No generar el reporte LaTeX en docs/SKILL/.")
    parser.add_argument("--validar-estricto", action="store_true", help=(
        "Abortar si la validación neuro-simbólica encuentra bloques de código inválidos."))
    parser.add_argument("--reflexion", type=int, default=0, help=(
        "Re-síntesis con --feedback hasta N veces si la validación encuentra errores "
        "(consumo de créditos; respeta el retry budget máx 3)."))
    parser.add_argument("--dry-run", action="store_true", help="Generar skill sin instalar en global.")
    parser.add_argument("--no-alert", action="store_true", help="No emitir alerta audible al final.")
    parser.add_argument("--destino", default=str(DESTINO_GLOBAL), help="Directorio global de skills.")

    args = parser.parse_args()
    pdf = Path(args.pdf).expanduser()

    run_id = f"flujo-libro-a-skill-{now_iso()[:19].replace(':', '-')}"

    check_pdf(pdf)
    datos = entrevista(pdf, args.tema, args.nombre, args.idioma)

    nombre = datos["nombre"]
    tema = datos["tema"]
    idioma = datos["idioma"]
    salida_local = Path(args.salida) if args.salida else (TMP_DIR / f"skill_{nombre}")
    dir_texto = TMP_DIR / f"libro_{nombre}_texto"

    state = {
        "run_id": run_id,
        "directive": "libro_a_skill.yaml",
        "pdf": str(pdf),
        "nombre": nombre,
        "tema": tema,
        "idioma": idioma,
        "tier": None,
        "modelo": None,
        "dry_run": args.dry_run,
        "started_at": now_iso(),
        "last_updated": now_iso(),
        "current_step": 0,
        "steps_completed": [],
        "steps_failed": [],
    }
    save_state(state)

    total = 5 + (0 if args.no_latex else 1) + (0 if args.dry_run else 1)

    # ── Paso 1: extracción ──
    print("\n" + "─" * 56)
    print(f"  Paso 1/{total}  │  Extrayendo texto del PDF (determinista)")
    print("─" * 56)
    dir_texto = TMP_DIR / f"libro_{nombre}_texto"
    code, extraccion = run_script(
        [PYTHON, str(EXTRAER), "--pdf", str(pdf), "--salida", str(dir_texto)],
        capture_json=True,
    )
    if code != 0 or not isinstance(extraccion, dict) or extraccion.get("status") != "ok":
        msg = (extraccion or {}).get("message") or "Fallo en extracción"
        print(f"  ❌ Extracción: {msg}", file=sys.stderr)
        state.update(current_step=1, steps_failed=["extraccion"], last_updated=now_iso())
        save_state(state)
        return 1
    print(f"  ✅ {extraccion['num_paginas']} páginas, {extraccion['caracteres']} chars, ~{extraccion['tokens_estimados']} tokens")
    estado_ok(state, 1)

    # ── Paso 2: enrutamiento (decisión determinista) ──
    archivo_texto = dir_texto / "texto_completo.txt"
    if args.modelo:
        modelo = args.modelo
        tier = "explicito"
    else:
        # Decisión determinista del tier medido sobre el texto YA extraído
        # (no el PDF binario, que infla la cuenta de tokens).
        code_tier, tier_out = run_script(
            [PYTHON, str(ENRUTADOR), "--task", "contexto_masivo",
             "--archivos", str(archivo_texto if archivo_texto.is_file() else pdf), "--no-log"],
            capture_json=True,
        )
        if code_tier == 0 and isinstance(tier_out, dict) and tier_out.get("model"):
            modelo = tier_out["model"]
            tier = tier_out.get("tier", "deepseek")
        else:
            print(f"  ⚠  Enrutador no respondió; modelo por defecto {DEFAULT_MODEL}")
            modelo = DEFAULT_MODEL
            tier = "deepseek"
    if not args.modelo:
        print("\n" + "─" * 56)
        print(f"  Paso 2/{total}  │  Enrutamiento determinista del tier")
        print("─" * 56)
        print(f"  ✅ tier={tier}, modelo={modelo}")
    else:
        print(f"\n  ✅ Modelo explícito: {modelo}")
    state.update(tier=tier, modelo=modelo, last_updated=now_iso())
    save_state(state)

    # ── Paso 3: síntesis (LLM, consume créditos) ──
    print("\n" + "─" * 56)
    print(f"  Paso 3/{total}  │  Destilando skill con LLM ({modelo})")
    print("─" * 56)
    if not args.dry_run:
        print("  ℹ  Este paso consume créditos OpenRouter.")
    texto = dir_texto / "texto_completo.txt"
    code_sint, sint = run_script(
        [PYTHON, str(SINTETIZAR),
         "--texto", str(texto),
         "--entrevista", str(_commit_entrevista(datos)),
         "--nombre", nombre,
         "--tema", tema,
         "--idioma", idioma,
         "--modelo", modelo,
         "--salida", str(salida_local)],
        capture_json=True,
    )
    if code_sint != 0 or not isinstance(sint, dict) or sint.get("status") != "ok":
        msg = _msg_fallo(sint, "Fallo en síntesis")
        print(f"  ❌ Síntesis: {msg}", file=sys.stderr)
        state.update(current_step=3, steps_failed=["sintesis"], last_updated=now_iso())
        save_state(state)
        run_script([PYTHON, str(ALERTAR), "error"])
        return 1
    print(f"  ✅ Generados {len(sint['archivos'])} archivos")
    for a in sint["archivos"]:
        print(f"     · {a}")

    # ── Paso 4: validación neuro-simbólica (determinista, sin créditos) ──
    print("\n" + "─" * 56)
    print(f"  Paso 4/{total}  │  Validación neuro-simbólica (bloques Python/SymPy)")
    print("─" * 56)
    def _comando_validador() -> list[str]:
        return [PYTHON, str(VALIDAR_FORMULAS), "--skill", str(salida_local)]

    def _validacion_ok(val: dict) -> bool:
        return isinstance(val, dict) and val.get("status") == "ok" and val.get("resumen", {}).get("errores", 0) == 0

    code_val, val = run_script(_comando_validador(), capture_json=True)
    if code_val in (1, 2) or not isinstance(val, dict) or val.get("status") != "ok":
        msg = (val or {}).get("message") or f"Fallo en validación neuro-simbólica (código {code_val})"
        print(f"  ⚠  Validación: {msg}", file=sys.stderr)
        state.update(validacion_error=msg, last_updated=now_iso())
        save_state(state)
    else:
        # ── Bucle de reflexión (opt-in, consume créditos, máx 3) ──
        reflexion_restante = min(args.reflexion, 3)
        while not _validacion_ok(val) and reflexion_restante > 0:
            errores = [b for b in val.get("bloques", []) if b.get("estado") != "ok"]
            feedback_file = TMP_DIR / f"errores_skill_{nombre}.json"
            feedback_file.write_text(
                json.dumps({"bloques": errores}, ensure_ascii=False, indent=2), encoding="utf-8",
            )
            print(f"  ⚠  {len(errores)} bloques inválidos; re-síntesis con correcciones "
                  f"(reflexión {reflexion_restante} restante).")
            print("  ℹ  Este paso consume créditos OpenRouter.")
            code_sint2, sint2 = run_script(
                [PYTHON, str(SINTETIZAR),
                 "--texto", str(texto),
                 "--entrevista", str(_commit_entrevista(datos)),
                 "--nombre", nombre,
                 "--tema", tema,
                 "--idioma", idioma,
                 "--modelo", modelo,
                 "--salida", str(salida_local),
                 "--feedback", str(feedback_file)],
                capture_json=True,
            )
            if code_sint2 != 0 or not isinstance(sint2, dict) or sint2.get("status") != "ok":
                msg2 = _msg_fallo(sint2, "Fallo en re-síntesis con feedback")
                print(f"  ⚠  Re-síntesis: {msg2}", file=sys.stderr)
                break
            print(f"  ✅ Re-síntesis OK ({len(sint2.get('archivos', []))} archivos)")
            reflexion_restante -= 1
            code_val, val = run_script(_comando_validador(), capture_json=True)
            if code_val != 0 or not isinstance(val, dict) or val.get("status") != "ok":
                break

        estado = "OK" if _validacion_ok(val) else "INVÁLIDO"
        r = val.get("resumen", {})
        print(f"  {'✅' if estado == 'OK' else '⚠'} Bloques {r.get('ok', 0)}/{r.get('total', 0)} válidos "
              f"({estado}), oráculo: {val.get('oraculo')}")
        faltantes = val.get("estructuras", {}).get("faltantes", [])
        if faltantes:
            print(f"  ℹ  Estructuras de razonamiento ausentes: {', '.join(faltantes)} (warning)")
        for b in val.get("bloques", []):
            if b.get("estado") != "ok":
                print(f"     ⚠ {b['archivo']} #{b['indice']} [{b['estado']}]: {(b.get('error') or '')[:120]}", file=sys.stderr)
        state.update(validacion_skill={
            "resumen": r,
            "oraculo": val.get("oraculo"),
            "faltantes": faltantes,
            "reflexiones_usadas": args.reflexion - reflexion_restante,
        }, last_updated=now_iso())
        save_state(state)
        if args.validar_estricto and not _validacion_ok(val):
            print("  ❌ --validar-estricto: hay bloques inválidos; se aborta.", file=sys.stderr)
            run_script([PYTHON, str(ALERTAR), "error"])
            return 1
        estado_ok(state, 4)

    # ── Paso 5: reporte LaTeX (determinista, sin créditos) ──
    if not args.no_latex:
        paso_latex = 5
        dir_latex = SCRIPT_DIR / "docs" / "SKILL" / nombre
        print("\n" + "─" * 56)
        print(f"  Paso {paso_latex}/{total}  │  Generando reporte LaTeX del skill")
        print("─" * 56)
        code_lat, lat = run_script(
            [PYTHON, str(GENERAR_LATEX),
             "--skill", str(salida_local),
             "--nombre", nombre,
             "--tema", tema,
             "--idioma", idioma,
             "--salida", str(dir_latex)],
            capture_json=True,
        )
        if code_lat != 0 or not isinstance(lat, dict) or lat.get("status") != "ok":
            msg = _msg_fallo(lat, "Fallo generando el reporte LaTeX")
            print(f"  ⚠  Reporte LaTeX: {msg}", file=sys.stderr)
            state.update(latex_error=msg, last_updated=now_iso())
            save_state(state)
        else:
            if lat.get("compilado"):
                print(f"  ✅ PDF compilado: {lat['pdf']}")
            else:
                print(f"  ⚠  LaTeX generado pero el PDF falló: {(lat.get('detalle_error') or '')[:140]}", file=sys.stderr)
            print(f"  ✅ Reporte en {lat['tex']} (auxiliares limpiados)")
            estado_ok(state, paso_latex)

    if not args.dry_run and datos["instalar_global"]:
        n_pasos_hasta_aqui = 4 + (1 if not args.modelo else 0) + (1 if not args.no_latex else 0)
        # ── Paso de instalación ──
        print("\n" + "─" * 56)
        print(f"  Paso {n_pasos_hasta_aqui + 1}/{total}  │  Instalando en global")
        print("─" * 56)
        code_inst, inst = run_script(
            [PYTHON, str(INSTALAR),
             "--origen", str(salida_local),
             "--nombre", nombre,
             "--destino", args.destino]
            + (["--sobrescribir"] if args.sobrescribir else []),
            capture_json=True,
        )
        if code_inst != 0 or not isinstance(inst, dict) or inst.get("status") != "ok":
            msg = _msg_fallo(inst, "Fallo en instalación")
            print(f"  ❌ Instalación: {msg}", file=sys.stderr)
            state.update(current_step=n_pasos_hasta_aqui + 1, steps_failed=["instalacion"], last_updated=now_iso())
            save_state(state)
            run_script([PYTHON, str(ALERTAR), "error"])
            return 1
        print(f"  ✅ Instalado en {inst['destino']}")
        estado_ok(state, n_pasos_hasta_aqui + 1)
    elif args.dry_run:
        print(f"\n  (dry-run) Skill listo en {salida_local}, no instalado en global.")
        estado_ok(state, total)

    if not args.no_alert:
        run_script([PYTHON, str(ALERTAR), "success"])
        print("\n  ℹ  RECUERDA: reinicia opencode para que el skill cargue (la config no se recarga en caliente).")

    print("\n  ✅ Flujo completado.")
    return 0


def estado_ok(state: dict, paso: int) -> None:
    state["current_step"] = paso
    state["steps_completed"] = sorted(set(state["steps_completed"] + [paso]))
    state["last_updated"] = now_iso()
    save_state(state)


def _commit_entrevista(datos: dict) -> Path:
    """Persiste la entrevista en .tmp para que sintetizar_skill.py la lea."""
    p = TMP_DIR / f"entrevista_skill_{datos['nombre']}.json"
    TMP_DIR.mkdir(exist_ok=True)
    p.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


if __name__ == "__main__":
    sys.exit(main())
