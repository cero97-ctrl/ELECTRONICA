#!/usr/bin/env python3
"""
flujo_libro_a_skill.py — Orquestador: convertir un libro PDF en un skill global
(Layer 2: Orchestration)

Ejecuta el flujo completo definido en la directiva libro_a_skill.yaml:
  1. Entrevista ligera (tema, nombre, idioma, alcance, objetivo, confirmación).
  2. extraer_libro_pdf.py   → extrae el texto del PDF (determinista).
  3. enrutador.py           → decisión determinista de tier (contexto masivo).
  4. sintetizar_skill.py    → destila SKILL.md + references/ con LLM.
  5. instalar_skill.py      → copia a ~/.config/opencode/skills/<name>/.
  6. alert_user.py          → notifica + aviso de reiniciar opencode.

Uso:
    python3 flujo_libro_a_skill.py --pdf <libro.pdf> [--tema "..."] [--nombre <name>]
        [--idioma es] [--modelo <id>] [--sobrescribir] [--dry-run] [--no-alert]
        [--salida .tmp/skill_<name>/]

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
INSTALAR = SCRIPT_DIR / "execution" / "instalar_skill.py"
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
    r = input(f"{prompt} [{'S/n' if default == 's' else 's/N'}] ").strip().lower()
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
    acotar = confirmar("¿Acotar a capítulos/secciones específicos del libro? (s/N)")
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

    total = 4 + (0 if args.dry_run else 1)

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
        msg = (sint or {}).get("message") or "Fallo en síntesis"
        print(f"  ❌ Síntesis: {msg}", file=sys.stderr)
        state.update(current_step=3, steps_failed=["sintesis"], last_updated=now_iso())
        save_state(state)
        run_script([PYTHON, str(ALERTAR), "error"])
        return 1
    print(f"  ✅ Generados {len(sint['archivos'])} archivos")
    for a in sint["archivos"]:
        print(f"     · {a}")

    if not args.dry_run and datos["instalar_global"]:
        n_pasos_hasta_aqui = 3 + (1 if not args.modelo else 0)
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
            msg = (inst or {}).get("message") or "Fallo en instalación"
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
