#!/usr/bin/env python3
"""Orquestador ocr_pdf (Capa 2): transcribir un PDF escaneado sin capa de texto.

Capa 3 (determinista): execution/ocr_pdf_escaneado.py, que extrae las imágenes
nativas, las transcribe con Gemini en lotes y mantiene una caché por página
reanudable. Este orquestador NO reimplementa nada de eso: valida entradas,
lanza el script, valida la salida (marcas de página presentes y completas),
guarda la vista por corrida en .tmp/run_state_<run_id>.json y alerta.

Modos sin coste:
  --check    reporta qué páginas ya están en caché y cuáles faltarían, sin
             llamar a la API (útil antes de gastar cuota y para reanudar).
  --dry-run  imprime el plan y sale.

Retry budget: los reintentos viven DENTRO de la capa 3 (MAX_INTENTOS = 3 por
lote). Aquí no se reintenta en bucle: sería mentir sobre el budget. Una cuota
agotada (código 5) se reporta con la ruta de la caché para reanudar después.

Consumo: usa la cuota free de Gemini (GOOGLE_API_KEY), NO créditos OpenRouter.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
OCR = SCRIPT_DIR / "execution" / "ocr_pdf_escaneado.py"
ALERTAR = SCRIPT_DIR / "execution" / "alert_user.py"

sys.path.insert(0, str(SCRIPT_DIR / "execution"))
import run_state as RS                # noqa: E402  (vista por corrida, capa 3)
import ocr_pdf_escaneado as O         # noqa: E402  (solo funciones puras)


def guardar_vista(ruta: Path, run_id: str, paso: str, exit_code: int, detalle: str) -> None:
    RS.escribir_vista(ruta, {
        "run_id": run_id,
        "flujo": "ocr_pdf",
        "paso": paso,
        "exit_code": exit_code,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "detalle": detalle,
    })


def validar_entrega(archivo: Path, pedidas: list[int]) -> list[str]:
    """Comprueba que el markdown tenga exactamente las páginas pedidas, completas."""
    problemas: list[str] = []
    if not archivo.exists():
        return [f"no existe el entregable: {archivo}"]
    texto = archivo.read_text(encoding="utf-8")
    for numero in pedidas:
        if f"## Página {numero}\n" not in texto:
            problemas.append(f"falta la página {numero} en el markdown")
        elif "[SIN TRANSCRIBIR]" in texto.split(f"## Página {numero}\n", 1)[1].split("## Página ", 1)[0]:
            problemas.append(f"la página {numero} quedó sin transcribir")
    return problemas


def parsear_informe(stdout: str, stderr: str) -> dict | None:
    """El script de capa 3 imprime un único JSON (indentado), por stdout si terminó
    bien y por stderr si no, a veces precedido de líneas de aviso. Se intenta el
    texto completo y, si hay basura delante, el recorte entre la primera '{' y la
    última '}'."""
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="OCR de un PDF escaneado (orchestra execution/ocr_pdf_escaneado.py)")
    ap.add_argument("--pdf", required=True, help="PDF escaneado de entrada")
    ap.add_argument("--salida", default=".tmp/ocr", help="directorio de salida y caché")
    ap.add_argument("--paginas", default=None, help="'1-56', '1,3,5-7' o 'todas' (default todas)")
    ap.add_argument("--lote", type=int, default=4, help="páginas por petición (default 4)")
    ap.add_argument("--ancho", type=int, default=1400, help="ancho de imagen en px (default 1400)")
    ap.add_argument("--modelo", default="gemini-2.5-flash")
    ap.add_argument("--forzar", action="store_true", help="OCR aunque el PDF tenga capa de texto")
    ap.add_argument("--sin-reanudar", action="store_true", help="ignora la caché existente")
    ap.add_argument("--check", action="store_true", help="solo reporta cobertura de caché, sin API")
    ap.add_argument("--dry-run", action="store_true", help="muestra el plan y sale")
    ap.add_argument("--no-alert", action="store_true", help="sin alerta audible")
    args = ap.parse_args(argv)

    pdf = Path(args.pdf)
    if not pdf.is_file():
        print(json.dumps({"status": "error", "code": 1, "message": f"no existe: {pdf}"},
                         ensure_ascii=False), file=sys.stderr)
        return 1

    try:
        total, chars = O._info_pdf(pdf)
        pedidas = O.parse_paginas(args.paginas, total)
    except Exception as exc:
        print(json.dumps({"status": "error", "code": 1, "message": str(exc)},
                         ensure_ascii=False), file=sys.stderr)
        return 1

    sha = O._sha_pdf(pdf)
    cache = Path(args.salida) / ".cache" / sha[:12] / "textos"
    en_cache = sorted(p for p in pedidas if (cache / f"pagina_{p:03d}.txt").exists())

    if args.check:
        print(json.dumps({
            "status": "ok",
            "pdf": str(pdf),
            "paginas_pdf": total,
            "chars_por_pagina": round(chars, 1),
            "pedidas": len(pedidas),
            "en_cache": len(en_cache),
            "faltantes": [p for p in pedidas if p not in en_cache],
            "cache": str(cache),
        }, ensure_ascii=False, indent=2))
        return 0

    cmd = [sys.executable, str(OCR), "--pdf", str(pdf), "--salida", str(args.salida),
           "--lote", str(args.lote), "--ancho", str(args.ancho), "--modelo", args.modelo]
    if args.paginas:
        cmd += ["--paginas", args.paginas]
    if args.forzar:
        cmd.append("--forzar")
    if args.sin_reanudar:
        cmd.append("--sin-reanudar")

    plan = {
        "run_id": "(se fija al ejecutar)",
        "pdf": str(pdf),
        "paginas_pedidas": len(pedidas),
        "ya_en_cache": len(en_cache),
        "peticiones_estimadas": -(-(len(pedidas) - len(en_cache)) // args.lote),
        "comando": " ".join(cmd),
        "creditos_openrouter": "no (cuota free de Gemini, GOOGLE_API_KEY)",
    }
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    run_id = RS.run_id_de_la_corrida("ocr_pdf")
    plan["run_id"] = run_id
    vista = RS.ruta_vista(run_id)

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        guardar_vista(vista, run_id, "1_ocr", 30, "timeout de 1800 s")
        print(json.dumps({"status": "error", "code": 30,
                          "message": "timeout ejecutando el OCR; reanudar con --check y otra corrida"},
                         ensure_ascii=False), file=sys.stderr)
        return 30

    informe = parsear_informe(proc.stdout, proc.stderr)
    if informe is None:
        informe = {"status": "error", "code": 3,
                   "message": ((proc.stdout or "") + (proc.stderr or ""))[:500]}
    codigo = proc.returncode
    guardar_vista(vista, run_id, "1_ocr", codigo, (proc.stdout or proc.stderr or "").strip()[:300])

    if codigo == 0:
        problemas = validar_entrega(Path(informe.get("archivo", "")), pedidas)
        guardar_vista(vista, run_id, "2_validar", 0 if not problemas else 4, "; ".join(problemas)[:300])
        if problemas:
            informe = {"status": "error", "code": 4, "message": "entregable incompleto",
                       "problemas": problemas, "cache": informe.get("cache")}
            codigo = 4
        else:
            informe["validacion"] = "markdown completo: todas las páginas pedidas presentes"

    print(json.dumps(informe, ensure_ascii=False, indent=2))

    if not args.no_alert:
        subprocess.run([sys.executable, str(ALERTAR),
                        "success" if codigo == 0 else "waiting"])
    return codigo


if __name__ == "__main__":
    sys.exit(main())
