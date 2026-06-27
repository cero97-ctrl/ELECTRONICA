#!/usr/bin/env python3
"""
generar_informe_imagen.py — Genera informe LaTeX del análisis de imágenes (Layer 3: Execution)

Lee el JSON producido por analizar_imagen.py y genera un informe profesional
en formato LaTeX listo para compilar con pdflatex o xelatex.

Uso:
    python3 execution/generar_informe_imagen.py --json .tmp/analisis_*.json --output docs/IMAGENES/informe_imagen/informe.tex
    python3 execution/generar_informe_imagen.py --json <ruta_json> --output <ruta_tex>

Salida (stdout, JSON):
    { "status": "ok", "archivo_tex": "...", "timestamp": "..." }

Códigos de salida:
    0 — Informe generado correctamente
    1 — Argumento inválido o JSON no encontrado
    4 — JSON de entrada inválido o incompleto
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


# ── Helpers de escape LaTeX ────────────────────────────────────────────────────

_UNICODE_TO_LATEX = [
    ("π", "$\\pi$"), ("Π", "$\\Pi$"),
    ("α", "$\\alpha$"), ("β", "$\\beta$"),
    ("γ", "$\\gamma$"), ("Γ", "$\\Gamma$"),
    ("δ", "$\\delta$"), ("Δ", "$\\Delta$"),
    ("θ", "$\\theta$"), ("Θ", "$\\Theta$"),
    ("λ", "$\\lambda$"), ("Λ", "$\\Lambda$"),
    ("μ", "$\\mu$"),  ("µ", "$\\mu$"),
    ("ν", "$\\nu$"),  ("ρ", "$\\rho$"),
    ("σ", "$\\sigma$"), ("Σ", "$\\Sigma$"),
    ("τ", "$\\tau$"),
    ("φ", "$\\varphi$"), ("ψ", "$\\psi$"),
    ("ω", "$\\omega$"), ("Ω", "$\\Omega$"),
    ("≤", "$\\leq$"), ("≥", "$\\geq$"),
    ("≠", "$\\neq$"), ("≈", "$\\approx$"),
    ("±", "$\\pm$"),  ("×", "$\\times$"),
    ("÷", "$\\div$"), ("∞", "$\\infty$"),
    ("√", "$\\surd$"), ("∑", "$\\sum$"),
    ("∫", "$\\int$"), ("∂", "$\\partial$"),
    ("→", "$\\rightarrow$"), ("←", "$\\leftarrow$"),
    ("↔", "$\\leftrightarrow$"),
    ("·", "$\\cdot$"),
    ("⁻", "$^{-}$"), ("⁰", "$^{0}$"),
    ("¹", "$^{1}$"), ("²", "$^{2}$"), ("³", "$^{3}$"),
    ("⁴", "$^{4}$"), ("⁵", "$^{5}$"), ("⁶", "$^{6}$"),
    ("₀", "$_{0}$"), ("₁", "$_{1}$"), ("₂", "$_{2}$"),
    ("₃", "$_{3}$"),
    ("°", "$^{\\circ}$"),
    ("✓", "$\\checkmark$"), ("✗", "$\\times$"),
    ("•", "\\textbullet{}"),
    ("–", "--"), ("—", "---"),
    ("\u201c", "``"), ("\u201d", "''"),
    ("\u2018", "`"),  ("\u2019", "'"),
]

_LATEX_ESCAPE = [
    ("\\", "\\textbackslash{}"),
    ("&",  "\\&"),
    ("%",  "\\%"),
    ("$",  "\\$"),
    ("#",  "\\#"),
    ("_",  "\\_"),
    ("{",  "\\{"),
    ("}",  "\\}"),
    ("~",  "\\textasciitilde{}"),
    ("^",  "\\textasciicircum{}"),
    ("<",  "\\textless{}"),
    (">",  "\\textgreater{}"),
]


def tex(s: str) -> str:
    if not s:
        return ""
    for char, repl in _UNICODE_TO_LATEX:
        s = s.replace(char, repl)
    parts = s.split("$")
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            for char, repl in _LATEX_ESCAPE:
                part = part.replace(char, repl)
        result.append(part)
    return "$".join(result)


def lista_items(items: list[dict] | list[str], clave: str | None = None) -> str:
    if not items:
        return "\\textit{Ninguno identificado.}"
    lines = ["\\begin{itemize}[leftmargin=1.5em, itemsep=2pt]"]
    for item in items:
        if isinstance(item, dict) and clave:
            nombre = item.get("nombre", "?")
            desc   = item.get("descripcion", "")
            lines.append(f"  \\item \\textbf{{{tex(nombre)}}}: {tex(desc)}")
        else:
            lines.append(f"  \\item {tex(str(item))}")
    lines.append("\\end{itemize}")
    return "\n".join(lines)


# ── Generador principal ────────────────────────────────────────────────────────

def generar_latex(data: dict) -> str:
    analisis = data.get("analisis", {})
    archivos = data.get("archivos_procesados", [])
    modelo   = data.get("modelo", "N/A")
    timestamp = data.get("timestamp", datetime.now(timezone.utc).isoformat())

    descripcion = analisis.get("descripcion_general", "")
    elementos   = analisis.get("elementos_detectados", [])
    texto       = analisis.get("texto_extraido", "")
    observaciones = analisis.get("observaciones", "")
    sugerencias   = analisis.get("sugerencias", "")

    tokens = data.get("tokens_usados", {})
    tokens_str = (
        f"{tokens.get('total', 'N/A')} tokens "
        f"(prompt: {tokens.get('prompt', 'N/A')}, "
        f"respuesta: {tokens.get('respuesta', 'N/A')})"
    ) if tokens else "N/A"

    fecha_str = timestamp[:10]

    archivos_items = ", ".join(
        f"\\texttt{{{tex(Path(a).name)}}}" for a in archivos
    )

    doc = r"""\documentclass[11pt,a4paper]{article}

% ── Codificación y fuentes ────────────────────────────────────────────────────
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[spanish]{babel}

% ── Geometría y espaciado ─────────────────────────────────────────────────────
\usepackage[top=2.5cm, bottom=2.5cm, left=2.8cm, right=2.8cm]{geometry}
\usepackage{setspace}
\setstretch{1.15}
\usepackage{parskip}

% ── Tablas ────────────────────────────────────────────────────────────────────
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{array}
\usepackage{enumitem}

% ── Colores y cajas ───────────────────────────────────────────────────────────
\usepackage[dvipsnames]{xcolor}
\usepackage{tcolorbox}
\tcbuselibrary{skins, breakable}

% ── Cabeceras y pies de página ────────────────────────────────────────────────
\usepackage{fancyhdr}
\usepackage{lastpage}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small\textbf{Informe de Análisis} --- Imágenes}
\fancyhead[R]{\small """ + fecha_str + r"""}
\fancyfoot[C]{\small Página \thepage\ de \pageref{LastPage}}
\renewcommand{\headrulewidth}{0.4pt}

% ── Hiperenlaces y URLs ──────────────────────────────────────────────────────
\usepackage[colorlinks=true, linkcolor=NavyBlue, urlcolor=NavyBlue]{hyperref}
\usepackage{url}
\def\path#1{\url{#1}}

% ── Permitir saltos de línea más flexibles ───────────────────────────────────
\sloppy
\emergencystretch 3em

% ── Colores personalizados ────────────────────────────────────────────────────
\definecolor{azulTitulo}{HTML}{1B2A6B}
\definecolor{grisFondo}{HTML}{F5F5F5}

% ── Estilos de cajas ─────────────────────────────────────────────────────────
\tcbset{
  cajaTitulo/.style={
    enhanced, breakable,
    colback=azulTitulo!8, colframe=azulTitulo,
    fonttitle=\bfseries\large, coltitle=white,
    attach boxed title to top left={yshift=-2mm, xshift=4mm},
    boxed title style={colback=azulTitulo},
    top=6pt, bottom=6pt, left=8pt, right=8pt,
  },
  cajaContenido/.style={
    enhanced, breakable,
    colback=grisFondo, colframe=gray!50,
    fonttitle=\bfseries, coltitle=black,
    top=4pt, bottom=4pt, left=8pt, right=8pt,
  },
}

% ─────────────────────────────────────────────────────────────────────────────
\begin{document}

% ══ PORTADA ══════════════════════════════════════════════════════════════════
\begin{center}
  {\Large\bfseries\color{azulTitulo} ELECTRÓNICA --- Análisis de Imágenes}\\[4pt]
  {\large Informe de Análisis}\\[12pt]
  \rule{\linewidth}{1.2pt}\\[6pt]
  \rule{\linewidth}{0.6pt}
\end{center}

% ══ FICHA TÉCNICA ════════════════════════════════════════════════════════════
\vspace{4pt}
\begin{tcolorbox}[cajaTitulo, title=Datos del análisis]
\begin{tabular}{@{}llll@{}}
  \textbf{Fecha:}       & """ + tex(fecha_str) + r"""  &
  \textbf{Modelo usado:} & """ + tex(modelo) + r""" \\[4pt]
  \textbf{Archivos:}    & \multicolumn{3}{l}{""" + archivos_items + r"""} \\
\end{tabular}
\end{tcolorbox}

% ══ DESCRIPCIÓN GENERAL ══════════════════════════════════════════════════════
\section*{Descripción general}
""" + tex(descripcion) + r"""

% ══ ELEMENTOS DETECTADOS ═════════════════════════════════════════════════════
\section*{Elementos detectados}
""" + lista_items(elementos, clave="nombre") + r"""

% ══ TEXTO EXTRAÍDO ═══════════════════════════════════════════════════════════
\section*{Texto extraído}
""" + (tex(texto) if texto else "\\textit{No se detectó texto legible en las imágenes.}") + r"""

% ══ OBSERVACIONES ════════════════════════════════════════════════════════════
\section*{Observaciones}
""" + (tex(observaciones) if observaciones else "\\textit{Sin observaciones adicionales.}") + r"""

% ══ SUGERENCIAS ═════════════════════════════════════════════════════════════
""" + (r"\section*{Sugerencias}" + "\n" + tex(sugerencias) if sugerencias else "") + r"""

% ══ PIE DE INFORME ════════════════════════════════════════════════════════════
\vspace{12pt}
\begin{center}
  \footnotesize\color{gray}
  Informe generado automáticamente por el sistema de análisis con IA (""" + tex(modelo) + r""") y soporte LaTeX. \\
  Generado el """ + tex(fecha_str) + r""" \textbullet\ ELECTRÓNICA --- Sistema de Análisis de Imágenes.
\end{center}

\end{document}
"""
    return doc


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Genera un informe LaTeX a partir del JSON de análisis de analizar_imagen.py.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 execution/generar_informe_imagen.py --json .tmp/analisis_*.json --output docs/IMAGENES/informe_imagen/informe.tex
        """,
    )
    parser.add_argument(
        "--json",
        required=True,
        help="Ruta al JSON de análisis generado por analizar_imagen.py.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Ruta del archivo .tex de salida.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # ── Leer JSON ──────────────────────────────────────────────────────────────
    json_path = Path(args.json)
    if not json_path.exists():
        print(json.dumps({
            "status": "error", "code": 1,
            "message": f"JSON no encontrado: {args.json}"
        }))
        sys.exit(1)

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(json.dumps({
            "status": "error", "code": 4,
            "message": f"JSON de entrada inválido: {e}"
        }))
        sys.exit(4)

    if "analisis" not in data:
        print(json.dumps({
            "status": "error", "code": 4,
            "message": "El JSON no contiene el campo 'analisis'. ¿Es un output de analizar_imagen.py?"
        }))
        sys.exit(4)

    # ── Generar LaTeX ──────────────────────────────────────────────────────────
    latex_content = generar_latex(data)

    # ── Escribir archivo .tex ─────────────────────────────────────────────────
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(latex_content, encoding="utf-8")

    result = {
        "status": "ok",
        "archivo_tex": str(output_path.resolve()),
        "archivos_analizados": data.get("archivos_procesados", []),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
