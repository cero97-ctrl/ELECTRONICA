#!/usr/bin/env python3
"""
verificar_pdf.py — Validación determinista de un PDF LaTeX (Layer 3: Execution)

Inspección post-compilación que el flujo de sincronización usa como guardrail de
calidad sin necesidad de visión humana:

  1. Errores de compilación: líneas '!' del .log de pdflatex (deben ser 0).
  2. Overfull hbox: líneas "Overfull \\hbox" del .log (se reportan, son cosméticas).
  3. Solapes de texto por página: parsea `pdftotext -bbox` (cajas de cada palabra) y
     detecta pares de palabras cuyos rectángulos se solapan significativamente.

Uso:
    python3 execution/verificar_pdf.py --pdf <archivo.pdf> [--log <archivo.log>]

Salida (stdout, JSON):
    { "status": "ok", "paginas": N, "errores": [...], "overfull": [...],
      "solapes": [{"pagina": 2, "a": "texto", "b": "texto", "area": 0.5}, ...] }

Códigos de salida:
    0 — OK (sin errores; overfull/solapes solo informativos)
    1 — Errores de compilación detectados o PDF irrecuperable
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SOLAPE_FRACCION = 0.35   # fracción del rectángulo menor que debe quedar solapada
_WORD_RE = re.compile(
    r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>'
)


def _solapa(r1, r2) -> float:
    """Área de intersección normalizada por el rectángulo de menor área (0-1)."""
    x1, y1, x2, y2 = r1
    u1, v1, u2, v2 = r2
    dx = min(x2, u2) - max(x1, u1)
    dy = min(y2, v2) - max(y1, v1)
    if dx <= 0 or dy <= 0:
        return 0.0
    inter = dx * dy
    area1 = (x2 - x1) * (y2 - y1)
    area2 = (u2 - u1) * (v2 - v1)
    menor = min(max(area1, 0.0), max(area2, 0.0))
    if menor <= 0:
        return 0.0
    return inter / menor


def _bbox_paginas(pdf: Path) -> list[list[tuple[float, float, float, float, str]]]:
    """Devuelve las cajas de texto de cada página vía pdftotext -bbox."""
    try:
        raw = subprocess.run(
            ["pdftotext", "-bbox", str(pdf), "-"],
            capture_output=True, text=True, timeout=120,
        )
        if raw.returncode != 0:
            raise RuntimeError(raw.stderr or "pdftotext -bbox falló")
    except FileNotFoundError:
        raise RuntimeError("No se encuentra 'pdftotext' en el PATH (paquete poppler-utils).")

    paginas = []
    for m in re.finditer(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', raw.stdout, re.DOTALL):
        words = []
        for w in _WORD_RE.finditer(m.group(3)):
            words.append((
                float(w.group(1)), float(w.group(2)),
                float(w.group(3)), float(w.group(4)),
                w.group(5),
            ))
        paginas.append(words)
    return paginas


def _detectar_solapes(words) -> list[dict]:
    ordenados = sorted(words, key=lambda w: (w[0], w[1]))
    solapes = []
    n = len(ordenados)
    for i in range(n):
        x1, y1, x2, y2, txt_i = ordenados[i]
        j = i + 1
        while j < n and ordenados[j][0] < x2:
            u1, v1, u2, v2, txt_j = ordenados[j]
            frac = _solapa((x1, y1, x2, y2), (u1, v1, u2, v2))
            if frac > SOLAPE_FRACCION:
                solapes.append({"a": txt_i, "b": txt_j, "area": round(frac, 3)})
            j += 1
    return solapes


def main() -> int:
    parser = argparse.ArgumentParser(description="Validación determinista de un PDF LaTeX.")
    parser.add_argument("--pdf", required=True, help="Ruta al PDF a validar.")
    parser.add_argument("--log", default=None, help="Ruta al .log de pdflatex (si existe).")
    args = parser.parse_args()

    pdf = Path(args.pdf)
    if not pdf.is_file():
        print(json.dumps({"status": "error", "code": 1, "message": f"No existe el PDF: {pdf}"}, ensure_ascii=False))
        return 1

    errores = []
    overfull = []
    log_path = Path(args.log) if args.log and Path(args.log).is_file() else None
    if log_path:
        log_text = log_path.read_text(encoding="utf-8", errors="ignore")
        errores = [ln.strip() for ln in log_text.splitlines() if ln.startswith("!")]
        overfull = [ln.strip() for ln in log_text.splitlines() if "Overfull \\hbox" in ln]

    solapes = []
    try:
        paginas = _bbox_paginas(pdf)
        for idx, words in enumerate(paginas, start=1):
            for s in _detectar_solapes(words):
                s = dict(s)
                s["pagina"] = idx
                solapes.append(s)
    except RuntimeError as e:
        print(json.dumps({"status": "error", "code": 1, "message": str(e)}, ensure_ascii=False))
        return 1

    resultado = {
        "status": "ok" if not errores else "error",
        "paginas": len(paginas),
        "errores": errores[:5],
        "overfull": overfull[:10],
        "solapes": solapes[:20],
        "solapes_total": len(solapes),
    }
    print(json.dumps(resultado, ensure_ascii=False))
    return 0 if not errores else 1


if __name__ == "__main__":
    sys.exit(main())