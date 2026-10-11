#!/usr/bin/env python3
"""Orquestador research_topic (Capa 2): investigar un tema en la web y
guardar el resultado en un archivo de texto reutilizable.

Capa 3 (determinista): execution/web_search.py (buscar) y
execution/process_search_results.py (raspar + sintetizar). La decision de
modelo la toma execution/enrutador.py (regla pura), NUNCA este chat.

Retry budget: los scripts de capa 3 llevan sus reintentos acotados (<=3 de
transporte). Un fallo de busqueda no se reintenta aqui en bucle (seria mentir
sobre el budget): se reporta y se escala al usuario. Estado por corrida en
.tmp/run_state_<run_id>.json. ---
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
RAIZ = SCRIPT_DIR
WEB_SEARCH      = SCRIPT_DIR / "execution" / "web_search.py"
PROCESAR        = SCRIPT_DIR / "execution" / "process_search_results.py"
ENRUTADOR       = SCRIPT_DIR / "execution" / "enrutador.py"
ALERTAR         = SCRIPT_DIR / "execution" / "alert_user.py"
TMP_DIR         = SCRIPT_DIR / ".tmp"
OUTPUT_DEFAULT  = SCRIPT_DIR / "docs" / "INVESTIGACIONES"

sys.path.insert(0, str(SCRIPT_DIR / "execution"))
import run_state as RS            # noqa: E402  (vista por corrida, capa 3)
from process_search_results import slugify  # noqa: E402


def correr(desc: str, cmd: list[str]) -> tuple[int, str]:
    """Ejecuta un comando de capa 3; devuelve (code, stdout)."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return 30, f"timeout al ejecutar: {' '.join(cmd)}"
    out = (proc.stdout or "").strip()
    if proc.returncode != 0:
        err = (proc.stderr or "").strip()
        return proc.returncode, (out + "\n" + err).strip()
    return 0, out


def decide_modelo(tema: str) -> str:
    """Modelo por regla pura (enrutador.py). Devuelve el nombre del tier."""
    code, out = correr("enrutador", [sys.executable, str(ENRUTADOR),
                                     "--task", "destilacion", "--no-log"])
    if code != 0:
        return "flash"
    try:
        data = json.loads(out)
        return data.get("model", "flash")
    except json.JSONDecodeError:
        return "flash"


def guardar_vista(ruta, run_id: str, paso: str, exit_code: int, detalle: str) -> None:
    RS.escribir_vista(ruta, {
        "run_id": run_id,
        "flujo": "research_topic",
        "paso": paso,
        "exit_code": exit_code,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "detalle": detalle,
    })


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Investiga un tema en la web y guarda el resultado")
    ap.add_argument("--tema", required=True, help="Tema a investigar")
    ap.add_argument("--output", default=str(OUTPUT_DEFAULT), help="Carpeta del entregable")
    ap.add_argument("--max-results", type=int, default=8, help="Resultados de búsqueda (default 8)")
    ap.add_argument("--max-pages", type=int, default=4, help="Páginas a raspar (default 4)")
    ap.add_argument("--modelo", default="", help="Override explícito de modelo (tier o ID)")
    ap.add_argument("--no-llm", action="store_true", help="Evitar créditos: informe en bruto")
    ap.add_argument("--dry-run", action="store_true", help="Mostrar plan y salir")
    ap.add_argument("--no-alert", action="store_true", help="Sin alerta audible")
    args = ap.parse_args(argv)

    slug = slugify(args.tema)
    salida = Path(args.output)
    search_json = TMP_DIR / f"research_search_{slug}.json"
    entregable = salida / f"{slug}.md"

    plan = {
        "run_id": "(se fija al ejecutar)",
        "tema": args.tema,
        "pasos": [
            f"{sys.executable} {WEB_SEARCH} --query <tema> --max-results {args.max_results}",
            "enrutador.py --task destilacion (regla pura) o --modelo override",
            f"{sys.executable} {PROCESAR} --search {search_json} --output {salida} "
            f"--modelo <tier> --max-pages {args.max_pages}"
            + (" --no-llm" if args.no_llm else ""),
        ],
        "entregable": str(entregable),
        "creditos_openrouter": ("no" if args.no_llm else "sí, en el paso de síntesis"),
    }
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    run_id = RS.run_id_de_la_corrida("research_topic")
    plan["run_id"] = run_id
    vista = RS.ruta_vista(run_id)

    TMP_DIR.mkdir(exist_ok=True)

    code, out = correr(
        "web_search",
        [sys.executable, str(WEB_SEARCH), "--query", args.tema,
         "--max-results", str(args.max_results)],
    )
    guardar_vista(vista, run_id, "1_buscar", code, out[:200])
    if code != 0:
        print(json.dumps({"status": "error", "paso": "buscar", "code": code,
                          "detalle": out}, ensure_ascii=False, indent=2))
        return code
    search_json.write_text(out, encoding="utf-8")

    modelo = args.modelo or decide_modelo(args.tema)
    code, out = correr(
        "procesar",
        [sys.executable, str(PROCESAR),
         "--search", str(search_json),
         "--tema", args.tema,
         "--output", str(salida),
         "--modelo", modelo,
         "--max-pages", str(args.max_pages),
         ] + (["--no-llm"] if args.no_llm else []),
    )
    guardar_vista(vista, run_id, "2_procesar", code, out[:300])
    print(out)
    if code != 0:
        return code

    if not args.no_alert:
        subprocess.run([sys.executable, str(ALERTAR), "success"])
    return 0


if __name__ == "__main__":
    sys.exit(main())