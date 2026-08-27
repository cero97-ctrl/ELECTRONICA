#!/usr/bin/env python3
"""
extraer_libro_pdf.py — Extracción determinista del texto de un libro PDF (Layer 3: Execution).

Flujo asociado: directives/libro_a_skill.yaml

Extrae el texto de un PDF (solo PDFs con texto selectable; NO hace OCR), lo
acumula página a página, detecta si el texto es suficiente, mide tokens y
guarda tanto el texto plano como un índice de páginas. Es función pura: mismo
PDF -> mismo texto.

Uso:
    python3 execution/extraer_libro_pdf.py \
        --pdf <ruta.pdf> \
        --salida .tmp/libro_<name>_texto/

Salida (stdout, JSON):
    {
      "status": "ok",
      "pdf": "...",
      "num_paginas": N,
      "caracteres": N,
      "chars_por_pagina": N,
      "tokens_estimados": N,
      "archivo_texto": "...",
      "archivo_indice": "...",
      "texto_selectable": true
    }

Códigos de salida:
    0 — Extracción exitosa y texto suficiente
    1 — Error de argumentos o PDF inexistente/ilegible
    2 — El PDF no tiene texto selectable (parece escaneado -> requiere OCR, fuera de alcance)
    3 — Error interno del backend de extracción
"""

import argparse
import json
import sys
from pathlib import Path

CHARS_PER_TOKEN = 4
MIN_CHARS_PER_PAGE = 200


class _ArgParserExit1(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(json.dumps({"status": "error", "code": 1, "message": message}), file=sys.stderr)
        sys.exit(1)


def _paginas_pdftotext(pdf: Path) -> list[str]:
    """Extrae texto por página con pdftotext (comando del sistema, robusto)."""
    import subprocess

    paginas: list[str] = []
    total = 0
    with subprocess.Popen(
        ["pdftotext", "-layout", str(pdf), "-"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
    ) as proc:
        out, err = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"pdftotext falló: {err.strip()[:500]}")
    # pdftotext usa form feed (\f) como separador de páginas.
    raw = out.split("\f")
    for chunk in raw:
        chunk = chunk.strip()
        if not chunk:
            continue
        paginas.append(chunk)
        total += len(chunk)
    return paginas


def _paginas_pymupdf(pdf: Path) -> list[str]:
    """Fallback con PyMuPDF (por página)."""
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError(f"PyMuPDF no está disponible: {exc}") from exc

    doc = fitz.open(str(pdf))
    paginas: list[str] = []
    for i in range(doc.page_count):
        pagina = doc[i].get_text("text").strip()
        if pagina:
            paginas.append(pagina)
    doc.close()
    return paginas


def extraer(pdf: Path, salida: Path) -> dict:
    if not pdf.is_file():
        raise FileNotFoundError(f"No existe el PDF: {pdf}")

    paginas: list[str] = []
    backend = None
    errores = []
    for nombre, fn in (
        ("pdftotext", _paginas_pdftotext),
        ("pymupdf", _paginas_pymupdf),
    ):
        try:
            paginas = fn(pdf)
            backend = nombre
            if paginas:
                break
        except Exception as exc:  # noqa: BLE001
            errores.append(f"{nombre}: {exc}")

    if errors_usados := errores:
        pass  # se reportan si falla todo el pipeline

    if not paginas:
        msg = "; ".join(errores) if errores else "No se pudo extraer texto."
        raise RuntimeError(f"No se pudo extraer texto del PDF. {msg}")

    num_paginas = len(paginas)
    caracteres = sum(len(p) for p in paginas)
    chars_por_pagina = round(caracteres / num_paginas)

    # Detección de PDF escaneado: densidad de caracteres muy baja por página.
    if chars_por_pagina < MIN_CHARS_PER_PAGE:
        info = {
            "status": "error",
            "code": 2,
            "message": (
                f"El PDF parece escaneado (solo {chars_por_pagina} chars/pág). "
                f"Requiere OCR, que está fuera del alcance de este flujo (PDF de texto selectable)."
            ),
            "num_paginas": num_paginas,
            "chars_por_pagina": chars_por_pagina,
            "texto_selectable": False,
        }
        raise _PdfEscaneado(info)

    salida.mkdir(parents=True, exist_ok=True)

    texto_completo = "\n\n=== PÁGINA ===\n\n".join(
        f"[p{i + 1}]\n{pagina}" for i, pagina in enumerate(paginas)
    )

    archivo_texto = salida / "texto_completo.txt"
    archivo_texto.write_text(texto_completo, encoding="utf-8")

    indice = {
        "pdf": str(pdf),
        "num_paginas": num_paginas,
        "caracteres": caracteres,
        "chars_por_pagina": chars_por_pagina,
        "tokens_estimados": caracteres // CHARS_PER_TOKEN,
        "backend": backend,
        "texto_selectable": True,
        "paginas": [i + 1 for i in range(num_paginas)],
    }
    archivo_indice = salida / "indice.json"
    archivo_indice.write_text(
        json.dumps(indice, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "status": "ok",
        "pdf": str(pdf),
        "num_paginas": num_paginas,
        "caracteres": caracteres,
        "chars_por_pagina": chars_por_pagina,
        "tokens_estimados": caracteres // CHARS_PER_TOKEN,
        "archivo_texto": str(archivo_texto),
        "archivo_indice": str(archivo_indice),
        "texto_selectable": True,
    }


class _PdfEscaneado(Exception):
    def __init__(self, info: dict):
        self.info = info


def main() -> None:
    parser = _ArgParserExit1(description=__doc__)
    parser.add_argument("--pdf", required=True, help="Ruta del PDF del libro.")
    parser.add_argument("--salida", required=True, help="Directorio de salida (.tmp/...).")

    args = parser.parse_args()

    try:
        resultado = extraer(Path(args.pdf), Path(args.salida))
    except _PdfEscaneado as exc:
        print(json.dumps(exc.info, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
    except FileNotFoundError as exc:
        print(json.dumps({"status": "error", "code": 1, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "error", "code": 3, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(3)

    print(json.dumps(resultado, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
