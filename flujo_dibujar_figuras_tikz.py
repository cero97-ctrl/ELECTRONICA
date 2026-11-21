#!/usr/bin/env python3
"""Orquestador dibujar_figuras_tikz (Capa 2): dibuja las figuras del OCR en TikZ
y regenera las prácticas con los dibujos ya validados.

No reimplementa lógica de negocio:
  * El MODELO lo decide `execution/enrutador.py --task diseño` (regla pura).
  * Las figuras las genera y valida `execution/generar_figuras_tikz.py`, que
    compila cada bloque de forma aislada y cachea solo lo que da 0 líneas `!`.
  * Las prácticas las renderiza `execution/generar_practicas_desde_ocr.py`
    pasándole el manifest con `--figuras`.

Este orquestador valida entradas, encadena los scripts, valida las salidas,
guarda la vista por corrida en `.tmp/run_state_<run_id>.json` y alerta.

Coste: SÍ consume créditos OpenRouter la primera vez (el router elige opus para
`diseño`). Con el manifest ya generado, las repeticiones no llaman a la API.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ENRUTADOR = SCRIPT_DIR / "execution" / "enrutador.py"
FIGURAS = SCRIPT_DIR / "execution" / "generar_figuras_tikz.py"
PRACTICAS = SCRIPT_DIR / "execution" / "generar_practicas_desde_ocr.py"
ALERTAR = SCRIPT_DIR / "execution" / "alert_user.py"

sys.path.insert(0, str(SCRIPT_DIR / "execution"))
import run_state as RS                # noqa: E402  (vista por corrida, capa 3)

OCR_POR_DEFECTO = SCRIPT_DIR / ".tmp" / "ocr_practicas" / "practicas_ocr.md"
FIGURAS_POR_DEFECTO = SCRIPT_DIR / ".tmp" / "figuras_tikz"
PRACTICAS_POR_DEFECTO = SCRIPT_DIR / ".tmp" / "practicas_desde_ocr"


def guardar_vista(ruta: Path, run_id: str, paso: str, exit_code: int, detalle: str) -> None:
    RS.escribir_vista(ruta, {
        "run_id": run_id,
        "flujo": "dibujar_figuras_tikz",
        "paso": paso,
        "exit_code": exit_code,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "detalle": detalle,
    })


def parsear_informe(stdout: str, stderr: str) -> dict | None:
    """Los scripts de capa 3 imprimen un único JSON por stdout (o stderr)."""
    for bruto in (stdout, stderr):
        bruto = (bruto or "").strip()
        if not bruto:
            continue
        try:
            return json.loads(bruto)
        except json.JSONDecodeError:
            pass
        ini, fin = bruto.find("{"), bruto.rfind("}")
        if ini != -1 and fin > ini:
            try:
                return json.loads(bruto[ini:fin + 1])
            except json.JSONDecodeError:
                continue
    return None


def decidir_modelo(ocr: Path, modelo_explicito: str | None) -> tuple[str, dict]:
    """El tier lo decide el enrutador con el OCR medido, nunca el chat."""
    cmd = [sys.executable, str(ENRUTADOR), "--task", "diseño",
           "--archivos", str(ocr), "--critico", "--no-log"]
    if modelo_explicito:
        cmd += ["--modelo-explicito", modelo_explicito]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    decision = parsear_informe(proc.stdout, proc.stderr) or {}
    if decision.get("status") != "ok" or not decision.get("model"):
        raise RuntimeError(f"enrutador: {(proc.stdout or proc.stderr).strip()[:300]}")
    return decision["model"], decision


def validar_manifest(ruta: Path, esperadas: int) -> tuple[list[str], dict]:
    """Exige status ok y un bloque no vacío por cada figura esperada."""
    if not ruta.is_file():
        return [f"no existe el manifest: {ruta.name}"], {}
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"manifest ilegible: {exc}"], {}
    problemas: list[str] = []
    if datos.get("status") != "ok":
        problemas.append("el manifest no está completo")
    figuras = datos.get("figuras", {})
    if len(figuras) < esperadas:
        problemas.append(f"el manifest tiene {len(figuras)} de {esperadas} figuras")
    for fid, info in figuras.items():
        if not info.get("codigo") or not info.get("sha_codigo"):
            problemas.append(f"figura {fid} sin código validado")
    return problemas, datos


def validar_entrega(salida: Path, numeros: list[int]) -> list[str]:
    """Comprueba que existan los `.tex` y `.pdf` de todas las prácticas pedidas."""
    problemas: list[str] = []
    for numero in numeros:
        for extension in ("tex", "pdf"):
            ruta = salida / f"practica_{numero:02d}.{extension}"
            if not ruta.is_file() or ruta.stat().st_size < 1000:
                problemas.append(f"falta o está vacío: {ruta.name}")
    return problemas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Dibuja las figuras del OCR en TikZ y regenera las prácticas"
    )
    ap.add_argument("--ocr", default=str(OCR_POR_DEFECTO), help="markdown del OCR")
    ap.add_argument("--salida-figuras", default=str(FIGURAS_POR_DEFECTO),
                    help="directorio del manifest de figuras")
    ap.add_argument("--salida-practicas", default=str(PRACTICAS_POR_DEFECTO),
                    help="directorio de las prácticas regeneradas")
    ap.add_argument("--practicas", default=None, help="'1-8', '1,3,5-7' o 'todas'")
    ap.add_argument("--modelo-explicito", default=None,
                    help="override del modelo (se pasa al enrutador)")
    ap.add_argument("--limite", type=int, default=None, help="solo las primeras N figuras (prueba)")
    ap.add_argument("--forzar", action="store_true", help="regenerar figuras cacheadas")
    ap.add_argument("--check", action="store_true", help="validar OCR y manifest sin llamar a la API")
    ap.add_argument("--dry-run", action="store_true", help="mostrar el plan y salir")
    ap.add_argument("--no-alert", action="store_true", help="sin alerta audible")
    args = ap.parse_args(argv)

    ocr = Path(args.ocr).resolve()
    salida_figuras = Path(args.salida_figuras).resolve()
    salida_practicas = Path(args.salida_practicas).resolve()
    if not ocr.is_file():
        print(json.dumps({"status": "error", "code": 1,
                          "message": f"no existe el markdown del OCR: {ocr}"},
                         ensure_ascii=False), file=sys.stderr)
        return 1

    numeros = list(range(1, 9))
    if args.practicas and args.practicas.strip().lower() != "todas":
        try:
            numeros = []
            for parte in args.practicas.split(","):
                parte = parte.strip()
                if "-" in parte:
                    ini, fin = parte.split("-", 1)
                    numeros.extend(range(int(ini), int(fin) + 1))
                else:
                    numeros.append(int(parte))
            numeros = sorted(set(n for n in numeros if 1 <= n <= 8))
        except ValueError:
            print(json.dumps({"status": "error", "code": 1,
                              "message": "rango de prácticas inválido"},
                             ensure_ascii=False), file=sys.stderr)
            return 1

    manifest = salida_figuras / "figuras.json"
    if args.check:
        cmd = [sys.executable, str(FIGURAS), "--ocr", str(ocr), "--check"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        print(proc.stdout or proc.stderr)
        return proc.returncode

    try:
        modelo, decision = decidir_modelo(ocr, args.modelo_explicito)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "error", "code": 2,
                          "message": f"no se pudo decidir el modelo: {exc}"},
                         ensure_ascii=False), file=sys.stderr)
        return 2

    cmd_figuras = [
        sys.executable, str(FIGURAS), "--ocr", str(ocr),
        "--salida", str(salida_figuras), "--modelo", modelo, "--json",
    ]
    if args.practicas:
        cmd_figuras += ["--practicas", args.practicas]
    if args.limite is not None:
        cmd_figuras += ["--limite", str(args.limite)]
    if args.forzar:
        cmd_figuras.append("--forzar")

    cmd_practicas = [
        sys.executable, str(PRACTICAS), "--ocr", str(ocr),
        "--salida", str(salida_practicas), "--figuras", str(manifest), "--json",
    ]
    if args.practicas:
        cmd_practicas += ["--practicas", args.practicas]

    if args.dry_run:
        print(json.dumps({
            "status": "ok",
            "modelo_decidido_por": "execution/enrutador.py (task=diseño, --archivos OCR, --critico)",
            "modelo": modelo,
            "decision": decision,
            "figuras": " ".join(cmd_figuras),
            "practicas": " ".join(cmd_practicas),
            "coste": "créditos OpenRouter solo si el manifest aún no existe",
        }, ensure_ascii=False, indent=2))
        return 0

    run_id = RS.run_id_de_la_corrida("dibujar_figuras_tikz")
    vista = RS.ruta_vista(run_id)
    codigo = 0
    informe: dict = {"status": "ok", "modelo": modelo}

    try:
        proc = subprocess.run(cmd_figuras, capture_output=True, text=True, timeout=3600)
    except subprocess.TimeoutExpired:
        guardar_vista(vista, run_id, "1_figuras", 30, "timeout de 3600 s")
        print(json.dumps({"status": "error", "code": 30,
                          "message": "timeout generando las figuras"},
                         ensure_ascii=False), file=sys.stderr)
        return 30

    figuras_informe = parsear_informe(proc.stdout, proc.stderr) or {}
    guardar_vista(vista, run_id, "1_figuras", proc.returncode,
                  (proc.stdout or proc.stderr or "").strip()[:300])
    if proc.returncode != 0:
        codigo = proc.returncode
        informe = figuras_informe or {"status": "error", "code": codigo,
                                       "message": "falló la generación de figuras"}
    else:
        problemas, datos = validar_manifest(manifest, esperadas=figuras_informe.get("figuras", 34))
        guardar_vista(vista, run_id, "2_validar_manifest", 0 if not problemas else 4,
                      "; ".join(problemas)[:300])
        if problemas:
            codigo = 4
            informe = {"status": "error", "code": 4,
                       "message": "manifest incompleto", "problemas": problemas}
        else:
            informe["figuras"] = datos.get("figuras") and len(datos["figuras"])
            informe["sha_figuras"] = figuras_informe.get("sha_conjunto")

            # Las figuras ya están validadas; regenerar las prácticas con ellas
            # no vuelve a llamar a la API (el manifest se reutiliza).
            if args.limite is None:
                try:
                    proc2 = subprocess.run(cmd_practicas, capture_output=True,
                                           text=True, timeout=1800)
                except subprocess.TimeoutExpired:
                    guardar_vista(vista, run_id, "3_practicas", 30, "timeout de 1800 s")
                    return 30
                practicas_informe = parsear_informe(proc2.stdout, proc2.stderr) or {}
                guardar_vista(vista, run_id, "3_practicas", proc2.returncode,
                              (proc2.stdout or proc2.stderr or "").strip()[:300])
                if proc2.returncode != 0:
                    codigo = proc2.returncode
                    informe = practicas_informe or {"status": "error", "code": codigo,
                                                    "message": "falló la regeneración"}
                else:
                    problemas = validar_entrega(salida_practicas, numeros)
                    guardar_vista(vista, run_id, "4_validar_entrega",
                                  0 if not problemas else 5, "; ".join(problemas)[:300])
                    if problemas:
                        codigo = 5
                        informe = {"status": "error", "code": 5,
                                   "message": "entrega incompleta", "problemas": problemas}
                    else:
                        informe["practicas"] = {
                            "salida": str(salida_practicas),
                            "cantidad": len(numeros),
                            "sha_conjunto": practicas_informe.get("sha_conjunto"),
                        }
            else:
                informe["nota"] = ("--limite activo: no se regeneraron las prácticas "
                                   "para no mezclar figuras reales con descripciones")

    informe["code"] = codigo
    print(json.dumps(informe, ensure_ascii=False, indent=2))
    if not args.no_alert:
        subprocess.run([sys.executable, str(ALERTAR),
                        "success" if codigo == 0 else "waiting"])
    return codigo


if __name__ == "__main__":
    sys.exit(main())
