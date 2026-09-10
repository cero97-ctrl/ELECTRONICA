#!/usr/bin/env python3
"""
flujo_repo_a_skill.py — Orquestador: convertir un repositorio de código en un
skill global de referencia de código/API (Layer 2: Orchestration)

Ejecuta el flujo completo definido en la directiva repo_a_skill.yaml:
  1. Entrevista ligera (fuente, tema, nombre, idioma, filtros, confirmación).
  2. extraer_repo_github.py → clona/usa repo local, filtra y concatena (determinista).
  3. enrutador.py           → decisión determinista de tier (contexto masivo).
  4. sintetizar_skill.py --perfil referencia_codigo → destila SKILL.md + references/.
  5. validar_skill_formulas.py --perfil referencia_codigo → valida.
  6. generar_latex_skill.py → reporte LaTeX en docs/SKILL/<name>/.
  7. instalar_skill.py      → copia a ~/.config/opencode/skills/<name>/.
  8. alert_user.py          → notifica + aviso de reiniciar opencode.

Uso:
    python3 flujo_repo_a_skill.py --repo <url-github|ruta-local> [--tema "..."]
        [--nombre <name>] [--idioma es] [--modelo <id>] [--sobrescribir]
        [--dry-run] [--no-alert] [--no-latex] [--validar-estricto]
        [--reflexion N] [--salida .tmp/skill_<name>/] [--incluir glob...] [--excluir glob...]

--repo es requerido. Si no se pasan --tema/--nombre/--idioma, se entrevista al
usuario. Con --dry-run se genera el skill pero NO se instala en global.

Consume créditos OpenRouter en la síntesis (default deepseek). El skill generado
es de perfil referencia_codigo (cómo el repo resuelve problemas y cómo aplicar
su metodología/código en el workspace), NO un libro de fórmulas SymPy.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
PYTHON = sys.executable

EXTRAER = SCRIPT_DIR / "execution" / "extraer_repo_github.py"
ENRUTADOR = SCRIPT_DIR / "execution" / "enrutador.py"
SINTETIZAR = SCRIPT_DIR / "execution" / "sintetizar_skill.py"
VALIDAR_FORMULAS = SCRIPT_DIR / "execution" / "validar_skill_formulas.py"
INSTALAR = SCRIPT_DIR / "execution" / "instalar_skill.py"
GENERAR_LATEX = SCRIPT_DIR / "execution" / "generar_latex_skill.py"
ALERTAR = SCRIPT_DIR / "execution" / "alert_user.py"
SESION_LOG = SCRIPT_DIR / "execution" / "sesion_log.py"

TMP_DIR = SCRIPT_DIR / ".tmp"
STATE_FILE = TMP_DIR / "run_state.json"
DESTINO_GLOBAL = Path.home() / ".config" / "opencode" / "skills"

DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"
PERFIL = "referencia_codigo"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_state(state: dict) -> None:
    TMP_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def registrar_evento(state: dict, tipo: str, datos: dict | None = None) -> None:
    """Trazabilidad append-only (directives/trazabilidad_sesiones.yaml).

    El log JSONL en .tmp/session_log_<run_id>.jsonl es la fuente de verdad; el
    run_state.json derivado (save_state) es una vista. La escritura del evento no
    debe romper el flujo: falla blanda con warning si el helper falla.
    """
    run_id = state.get("run_id")
    if not run_id:
        return
    cmd = [PYTHON, str(SESION_LOG), "add", "--run", run_id, "--tipo", tipo]
    if datos:
        try:
            cmd += ["--datos", json.dumps(datos, ensure_ascii=False)]
        except (TypeError, ValueError):
            pass
    code, out = run_script(cmd, capture_json=True)
    if code != 0:
        msg = out.get("message") if isinstance(out, dict) else "error desconocido"
        print(f"  ⚠  (trazabilidad) no se registró {tipo}: {msg}", file=sys.stderr)


def run_script(cmd: list[str], capture_json: bool = False) -> tuple[int, dict | str]:
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if capture_json:
        try:
            return result.returncode, json.loads(result.stdout)
        except json.JSONDecodeError:
            return result.returncode, {"raw_output": result.stdout, "stderr": result.stderr}
    return result.returncode, result.stdout


def _msg_fallo(d: dict | str, fallback: str) -> str:
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
    return s[:40] or "repo"


def _nombre_default_de_fuente(fuente: str) -> str:
    m = re.search(r"([^/]+?)(?:\.git)?$", fuente.rstrip("/"))
    return slug_name(m.group(1)) if m else "repo"


def confirmar(prompt: str, default="s") -> bool:
    try:
        r = input(f"{prompt} [{'S/n' if default == 's' else 's/N'}] ").strip().lower()
    except EOFError:
        r = ""
    if not r:
        return default == "s"
    return r in ("s", "si", "y", "yes")


# ── Entrevista ligera ─────────────────────────────────────────────────────────

def entrevista(fuente, tema, nombre, idioma, incluir, excluir) -> dict:
    nombre = nombre or preguntar(
        "Nombre del skill (snake_case, ej. cloudflare_workers):",
        _nombre_default_de_fuente(fuente),
    )
    tema = tema or preguntar(
        "¿Qué resuelve o documenta este repo? (dominio, ej. Cloudflare Workers):",
        "Referencia de código/API del repositorio",
    )
    idioma = idioma or "es"

    print("\n── Alcance y filtrado ──")
    print("  El skill será de REFERENCIA DE CÓDIGO/API (funciones, clases, patrones, ejemplos).")
    if not incluir:
        acotar = confirmar("¿Filtrar por extensiones/globs de archivos? (s/N)", default="n")
        if acotar:
            inc = preguntar("Globs a INCLUIR (ej. '*.py' '*.md'; vacío = todos):", "")
            incluir = [g.strip() for g in inc.split() if g.strip()] or None
        else:
            incluir = None
    excluir = excluir or None
    if excluir:
        print(f"  Globs a EXCLUIR: {', '.join(excluir)}")

    print("\n  Objetivo confirmado: Referencia rápida de código/API del repositorio.")

    print("\n── Instalación ──")
    print(f"  Destino global: {DESTINO_GLOBAL / nombre}")
    confirmar_inst = confirmar(
        f"¿Instalar el skill en global (~/.config/opencode/skills/{nombre})?", "s",
    )

    return {
        "nombre": nombre,
        "tema": tema,
        "idioma": idioma,
        "alcance": {"tipo": "completo", "incluir": incluir, "excluir": excluir},
        "objetivo": "Referencia rápida de código/API del repositorio.",
        "instalar_global": confirmar_inst,
        "perfil": PERFIL,
    }


# ── Núcleo del flujo ──────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="URL de GitHub o ruta local al repositorio.")
    parser.add_argument("--tema", default=None, help="Tema/dominio.")
    parser.add_argument("--nombre", default=None, help="Nombre del skill (snake_case).")
    parser.add_argument("--idioma", default=None, help="Idioma del skill (default es).")
    parser.add_argument("--modelo", default=None, help="ID de modelo OpenRouter (override del tier).")
    parser.add_argument("--estimacion-crepus", dest="estimacion", action="store_true", help=argparse.SUPPRESS)
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
    parser.add_argument("--structo-max-tokens", dest="estructura_max_tokens", type=int, default=0,
                        help=argparse.SUPPRESS)
    parser.add_argument("--estructura-max-tokens", type=int, default=0, help=(
        "Presupuesto de tokens de salida para el ensamblaje (SKILL.md + "
        "references en un JSON). 0 = automático: 32768 en tier deepseek "
        "(contexto masivo), 8192 en el resto."))
    parser.add_argument("--incluir", nargs="*", default=None, help="Globs a incluir (ej. '*.py').")
    parser.add_argument("--excluir", nargs="*", default=None, help="Globs a excluir (ej. 'tests/*').")

    args = parser.parse_args()
    fuente = args.repo

    run_id = f"flujo-repo-a-skill-{now_iso()[:19].replace(':', '-')}"

    datos = entrevista(fuente, args.tema, args.nombre, args.idioma, args.incluir, args.excluir)

    nombre = datos["nombre"]
    tema = datos["tema"]
    idioma = datos["idioma"]
    salida_local = Path(args.salida) if args.salida else (TMP_DIR / f"skill_{nombre}")
    dir_texto = TMP_DIR / f"repo_{nombre}_texto"

    state = {
        "run_id": run_id,
        "directive": "repo_a_skill.yaml",
        "fuente": fuente,
        "nombre": nombre,
        "tema": tema,
        "idioma": idioma,
        "perfil": PERFIL,
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
    registrar_evento(state, "flujo/inicio", {
        "flujo": "repo_a_skill", "fuente": fuente, "nombre": nombre,
        "dry_run": args.dry_run, "total_pasos": total,
    })

    # ── Paso 1: extracción ──
    print("\n" + "─" * 56)
    print(f"  Paso 1/{total}  │  Extrayendo repo (clon/filtrado/concatenación, determinista)")
    print("─" * 56)
    cmd_extraer = [PYTHON, str(EXTRAER), "--fuente", fuente, "--salida", str(dir_texto)]
    if args.incluir:
        cmd_extraer += ["--incluir"] + args.incluir
    if args.excluir:
        cmd_extraer += ["--excluir"] + args.excluir
    code, extraccion = run_script(cmd_extraer, capture_json=True)
    if code != 0 or not isinstance(extraccion, dict) or extraccion.get("status") != "ok":
        msg = (extraccion or {}).get("message") or "Fallo en extracción"
        print(f"  ❌ Extracción: {msg}", file=sys.stderr)
        state.update(current_step=1, steps_failed=["extraccion"], last_updated=now_iso())
        save_state(state)
        registrar_evento(state, "flujo/error", {
            "paso": 1, "script": "execution/extraer_repo_github.py", "mensaje": msg,
        })
        return 1
    print(f"  ✅ {extraccion['num_archivos']} archivos, {extraccion['caracteres']} chars, "
          f"~{extraccion['tokens_estimados']} tokens ({extraccion['num_excluidos']} excluidos)")
    estado_ok(state, 1)

    # ── Paso 2: enrutamiento (decisión determinista) ──
    archivo_texto = dir_texto / "texto_completo.txt"
    if args.modelo:
        modelo = args.modelo
        tier = "explicito"
    else:
        code_tier, tier_out = run_script(
            [PYTHON, str(ENRUTADOR), "--task", "contexto_masivo",
             "--archivos", str(archivo_texto if archivo_texto.is_file() else fuente), "--no-log"],
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

    estructura_max_tokens = args.estructura_max_tokens
    if estructura_max_tokens <= 0:
        estructura_max_tokens = 32768 if "deepseek" in str(modelo) else 8192

    # ── Paso 3: síntesis (LLM, consume créditos) ──
    print("\n" + "─" * 56)
    print(f"  Paso 3/{total}  │  Destilando skill con LLM ({modelo}) [perfil: {PERFIL}]")
    print("─" * 56)
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
         "--perfil", PERFIL,
         "--salida", str(salida_local),
         "--estructura-max-tokens", str(estructura_max_tokens)],
        capture_json=True,
    )
    if code_sint != 0 or not isinstance(sint, dict) or sint.get("status") != "ok":
        msg = _msg_fallo(sint, "Fallo en síntesis")
        print(f"  ❌ Síntesis: {msg}", file=sys.stderr)
        state.update(current_step=3, steps_failed=["sintesis"], last_updated=now_iso())
        save_state(state)
        registrar_evento(state, "flujo/error", {
            "paso": 3, "script": "execution/sintetizar_skill.py", "mensaje": msg,
        })
        run_script([PYTHON, str(ALERTAR), "error"])
        return 1
    print(f"  ✅ Generados {len(sint['archivos'])} archivos")
    for a in sint["archivos"]:
        print(f"     · {a}")

    # ── Paso 4: validación neuro-simbólica (determinista, sin créditos) ──
    print("\n" + "─" * 56)
    print(f"  Paso 4/{total}  │  Validación neuro-simbólica (bloques Python)")
    print("─" * 56)
    validacion_ok_flag = True

    def _comando_validador():
        return [PYTHON, str(VALIDAR_FORMULAS), "--skill", str(salida_local),
                "--perfil", PERFIL]

    def _validacion_ok(val):
        return isinstance(val, dict) and val.get("status") == "ok" and val.get("resumen", {}).get("errores", 0) == 0

    code_val, val = run_script(_comando_validador(), capture_json=True)
    if code_val in (1, 2) or not isinstance(val, dict) or val.get("status") != "ok":
        msg = (val or {}).get("message") or f"Fallo en validación neuro-simbólica (código {code_val})"
        print(f"  ⚠  Validación: {msg}", file=sys.stderr)
        state.update(validacion_error=msg, last_updated=now_iso())
        save_state(state)
    else:
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
                 "--perfil", PERFIL,
                 "--salida", str(salida_local),
                 "--feedback", str(feedback_file),
                 "--estructura-max-tokens", str(estructura_max_tokens)],
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
        validacion_ok_flag = _validacion_ok(val)
        r = val.get("resumen", {})
        print(f"  {'✅' if estado == 'OK' else '⚠'} Bloques {r.get('ok', 0)}/{r.get('total', 0)} válidos "
              f"({estado}), oráculo: {val.get('oraculo')}")
        faltantes = val.get("estructuras", {}).get("faltantes", [])
        if faltantes:
            print(f"  ℹ  Estructuras de referencia ausentes: {', '.join(faltantes)} (warning)")
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
            registrar_evento(state, "flujo/error", {
                "paso": 4, "script": "execution/validar_skill_formulas.py",
                "mensaje": "--validar-estricto: bloques inválidos",
            })
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
        if not validacion_ok_flag:
            print("\n" + "─" * 56)
            print(f"  ⚠  Paso {n_pasos_hasta_aqui + 1}/{total}  │  Instalación OMITIDA: validación con bloques inválidos.")
            print("  ℹ  Usa --validar-estricto y revisa la salida del Paso 4, o elimina/edita los bloques rojos antes de instalar.")
            estado_ok(state, n_pasos_hasta_aqui + 1)
        else:
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
                registrar_evento(state, "flujo/error", {
                    "paso": n_pasos_hasta_aqui + 1,
                    "script": "execution/instalar_skill.py", "mensaje": msg,
                })
                run_script([PYTHON, str(ALERTAR), "error"])
                return 1
            print(f"  ✅ Instalado en {inst['destino']}")
            estado_ok(state, n_pasos_hasta_aqui + 1)
    elif args.dry_run:
        print(f"\n  (dry-run) Skill listo en {salida_local}, no instalado en global.")
        estado_ok(state, total)

    registrar_evento(state, "flujo/fin", {"exit_code": 0, "pasos": total})

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
    registrar_evento(state, "flujo/paso", {
        "paso": paso,
        "script": "flujo_repo_a_skill.py",
        "status": "ok",
        "current_step": paso,
    })


def _commit_entrevista(datos: dict) -> Path:
    p = TMP_DIR / f"entrevista_skill_{datos['nombre']}.json"
    TMP_DIR.mkdir(exist_ok=True)
    p.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


if __name__ == "__main__":
    sys.exit(main())
