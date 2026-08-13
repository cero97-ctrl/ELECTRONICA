#!/usr/bin/env python3
"""
generar_informe.py — Genera informe LaTeX a partir del JSON de evaluación (Layer 3: Execution)

Lee el JSON producido por evaluar_examen.py y genera un informe académico
profesional en formato LaTeX listo para compilar con pdflatex o xelatex.

Uso:
    python3 execution/generar_informe.py --json .tmp/evaluacion_Ana_Alcala.json --output examenes/01/examen_estudiantes/informe_Ana_Alcala.tex
    python3 execution/generar_informe.py --json <ruta_json> --output <ruta_tex>
    # También acepta stdin:
    cat .tmp/evaluacion.json | python3 execution/generar_informe.py --output informe.tex

Salida (stdout, JSON):
    { "status": "ok", "archivo_tex": "...", "timestamp": "..." }

Códigos de salida:
    0 — Informe generado correctamente
    1 — Argumento inválido o JSON no encontrado
    4 — JSON de entrada inválido o incompleto
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
if str(SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR.parent))

from execution.estilo_infografia import PREAMBULO_INFOGRAFIA


# ── Helpers de escape LaTeX ────────────────────────────────────────────────────

# Paso 1: Unicode → LaTeX ANTES de escapar (para que $…$ no se rompa)
_UNICODE_TO_LATEX = [
    # Letras griegas (muy comunes en física)
    ("π", "$\\pi$"), ("Π", "$\\Pi$"),
    ("α", "$\\alpha$"), ("β", "$\\beta$"),
    ("γ", "$\\gamma$"), ("Γ", "$\\Gamma$"),
    ("δ", "$\\delta$"), ("Δ", "$\\Delta$"),
    ("θ", "$\\theta$"), ("Θ", "$\\Theta$"),
    ("λ", "$\\lambda$"), ("Λ", "$\\Lambda$"),
    ("μ", "$\\mu$"),  ("µ", "$\\mu$"),  # U+03BC y U+00B5
    ("ν", "$\\nu$"),  ("ρ", "$\\rho$"),
    ("σ", "$\\sigma$"), ("Σ", "$\\Sigma$"),
    ("τ", "$\\tau$"),
    ("φ", "$\\varphi$"), ("ψ", "$\\psi$"),
    ("ω", "$\\omega$"), ("Ω", "$\\Omega$"),
    # Operadores y símbolos matemáticos
    ("≤", "$\\leq$"), ("≥", "$\\geq$"),
    ("≠", "$\\neq$"), ("≈", "$\\approx$"),
    ("±", "$\\pm$"),  ("×", "$\\times$"),
    ("÷", "$\\div$"), ("∞", "$\\infty$"),
    ("√", "$\\surd$"), ("∑", "$\\sum$"),
    ("∫", "$\\int$"), ("∂", "$\\partial$"),
    ("→", "$\\rightarrow$"), ("←", "$\\leftarrow$"),
    ("↔", "$\\leftrightarrow$"),
    ("·", "$\\cdot$"),
    # Superíndices Unicode frecuentes en física
    ("⁻", "$^{-}$"), ("⁰", "$^{0}$"),
    ("¹", "$^{1}$"), ("²", "$^{2}$"), ("³", "$^{3}$"),
    ("⁴", "$^{4}$"), ("⁵", "$^{5}$"), ("⁶", "$^{6}$"),
    # Subíndices
    ("₀", "$_{0}$"), ("₁", "$_{1}$"), ("₂", "$_{2}$"),
    ("₃", "$_{3}$"),
    # Grado
    ("°", "$^{\\circ}$"),
    # Símbolos tipográficos
    ("✓", "$\\checkmark$"), ("✗", "$\\times$"),
    ("•", "\\textbullet{}"),
    ("–", "--"), ("—", "---"),
    ("\u201c", "``"), ("\u201d", "''"),
    ("\u2018", "`"),  ("\u2019", "'"),
]

# Paso 2: Escapar chars especiales de LaTeX en texto plano
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
    """
    Convierte texto plano en texto seguro para pdflatex.
    Paso 1 — sustituye símbolos Unicode por comandos LaTeX.
    Paso 2 — escapa caracteres especiales SOLO en segmentos de texto plano
              (los bloques $…$ se dejan intactos para no romper las matemáticas).
    """
    if not s:
        return ""
    # Arreglar errores comunes de los LLMs al querer generar saltos de línea
    s = s.replace("$\\$", "\n\n")
    s = s.replace("$\\\\$", "\n\n")
    # Paso 1
    for char, repl in _UNICODE_TO_LATEX:
        s = s.replace(char, repl)
    # Paso 2: procesar token a token separando por $
    parts = s.split("$")
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 0:          # segmento de texto plano
            for char, repl in _LATEX_ESCAPE:
                part = part.replace(char, repl)
        else:
            # segmento impar = interior de $…$ → arreglar LLM typos
            part = part.replace("\\imes", "\\times")
            part = part.replace("\\rac", "\\frac")
            part = part.replace("\\au", "\\tau")
            part = part.replace("\\%", "%").replace("%", "\\%")
        result.append(part)
    return "$".join(result)


def nivel_color(nivel: str) -> str:
    """Retorna el nombre de color LaTeX según el nivel de desempeño."""
    colores = {
        "excelente":   "desempeno_excelente",
        "bueno":       "desempeno_bueno",
        "suficiente":  "desempeno_suficiente",
        "deficiente":  "desempeno_deficiente",
        "insuficiente":"desempeno_insuficiente",
    }
    return colores.get(nivel.lower(), "desempeno_bueno")


def lista_items(items: list[str], color: str = "black") -> str:
    """Genera un itemize LaTeX a partir de una lista de strings."""
    if not items:
        return "\\textit{Ninguno identificado.}"
    lines = ["\\begin{itemize}[leftmargin=1.5em, itemsep=2pt]"]
    for item in items:
        lines.append(f"  \\item {tex(item)}")
    lines.append("\\end{itemize}")
    return "\n".join(lines)


# ── Generador principal ────────────────────────────────────────────────────────

def generar_latex(data: dict) -> str:
    """Genera el contenido LaTeX completo del informe de evaluación."""

    ev = data.get("evaluacion", {})
    estudiante     = data.get("estudiante", "Desconocido")
    modelo         = data.get("modelo", "N/A")
    paginas        = data.get("paginas_procesadas", "N/A")
    timestamp      = data.get("timestamp", datetime.utcnow().isoformat() + "Z")
    archivo_pdf    = Path(data.get("archivo", "")).name

    puntaje        = ev.get("puntaje_sugerido", "N/A")
    nivel          = ev.get("nivel_desempeno", "N/A")
    resumen        = ev.get("resumen_general", "")
    fortalezas     = ev.get("fortalezas", [])
    areas          = ev.get("areas_de_mejora", [])
    por_pregunta   = ev.get("observaciones_por_pregunta", [])
    err_concept    = ev.get("errores_conceptuales", [])
    err_proced     = ev.get("errores_procedimentales", [])
    recomendaciones= ev.get("recomendaciones_al_estudiante", "")
    nota_prof      = ev.get("nota_para_el_profesor", "")

    tokens         = data.get("tokens_usados", {})
    tokens_str     = f"{tokens.get('total', 'N/A')} tokens (prompt: {tokens.get('prompt', 'N/A')}, respuesta: {tokens.get('respuesta', 'N/A')})" if tokens else "N/A"

    fecha_str = timestamp[:10]  # YYYY-MM-DD
    nivel_color_name = nivel_color(nivel)

    # ── Tabla de observaciones por pregunta ────────────────────────────────────
    filas_preguntas = []
    for obs in por_pregunta:
        pregunta_tex   = tex(obs.get("pregunta", ""))
        puntaje_p_tex  = tex(obs.get("puntaje_parcial", ""))
        eval_tex       = tex(obs.get("evaluacion", ""))
        errores        = obs.get("errores", [])
        errores_str    = "; ".join(errores) if errores else "---"
        errores_tex    = tex(errores_str)
        filas_preguntas.append(
            f"    \\textbf{{{pregunta_tex}}} & {puntaje_p_tex} & {eval_tex} & \\textit{{{errores_tex}}} \\\\"
            "\n    \\midrule"
        )

    tabla_preguntas_body = "\n".join(filas_preguntas)
    if not tabla_preguntas_body:
        tabla_preguntas_body = "    \\multicolumn{4}{c}{\\textit{No hay observaciones por pregunta.}} \\\\"

    doc = PREAMBULO_INFOGRAFIA + r"""
% ── Cabeceras específicas del informe ──────────────────────────────────────────
\fancyhead[L]{\small\color{azulNoche}\textbf{Informe de Evaluación} --- Electrónica}
\fancyhead[R]{\small """ + tex(estudiante) + r"""}
\renewcommand{\headrulewidth}{0pt}

% ── Colores de desempeño (evaluación) ─────────────────────────────────────────
\definecolor{desempeno_excelente}{HTML}{1A6B2F}
\definecolor{desempeno_bueno}{HTML}{2E5A9C}
\definecolor{desempeno_suficiente}{HTML}{8B6914}
\definecolor{desempeno_deficiente}{HTML}{C0392B}
\definecolor{desempeno_insuficiente}{HTML}{7B241C}

% ─────────────────────────────────────────────────────────────────────────────
\begin{document}

% ══ PORTADA INFográfica ════════════════════════════════════════════════════════
\bandaTitulo{ELECTRÓNICA --- Evaluación de Exámenes}{Informe de Evaluación Preliminar}

\begin{center}
  {\LARGE\bfseries\color{azulNoche} """ + tex(estudiante) + r"""}
\end{center}

% ══ FICHA TÉCNICA ════════════════════════════════════════════════════════════
\vspace{4pt}
\begin{tcolorbox}[cajaTitulo, title=Datos del informe]
\begin{tabular}{@{}llll@{}}
  \textbf{Estudiante:}  & """ + tex(estudiante) + r"""  &
  \textbf{Fecha:}       & """ + tex(fecha_str) + r""" \\[4pt]
  \textbf{Archivo PDF:} & \texttt{""" + tex(archivo_pdf) + r"""}  &
  \textbf{Páginas:}     & """ + tex(str(paginas)) + r""" \\
\end{tabular}
\end{tcolorbox}

% ══ RESULTADO GLOBAL ═════════════════════════════════════════════════════════
\vspace{6pt}
\begin{center}
  \begin{tcolorbox}[
    enhanced,
    colback=white, colframe=""" + nivel_color_name + r""",
    width=0.62\linewidth,
    boxrule=2pt,
    halign=center, valign=center,
    top=8pt, bottom=8pt,
  ]
    \centering
    {\large\bfseries Puntaje sugerido}\\[6pt]
    {\Huge\bfseries\color{""" + nivel_color_name + r"""} """ + tex(puntaje) + r"""}\\[6pt]
    {\large Nivel de desempeño: \textbf{\color{""" + nivel_color_name + r"""} """ + tex(nivel) + r"""}}
  \end{tcolorbox}
\end{center}

% ══ RESUMEN GENERAL ══════════════════════════════════════════════════════════
\section*{Resumen general}
""" + tex(resumen) + r"""

% ══ FORTALEZAS Y ÁREAS DE MEJORA ════════════════════════════════════════════
\vspace{4pt}
\begin{minipage}[t]{0.48\linewidth}
  \begin{tcolorbox}[cajaFortaleza, title={Fortalezas}]
""" + lista_items(fortalezas) + r"""
  \end{tcolorbox}
\end{minipage}
\hfill
\begin{minipage}[t]{0.48\linewidth}
  \begin{tcolorbox}[cajaMejora, title={Areas de mejora}]
""" + lista_items(areas) + r"""
  \end{tcolorbox}
\end{minipage}

% ══ OBSERVACIONES POR PREGUNTA ═══════════════════════════════════════════════
\section*{Observaciones por pregunta}

\begin{longtable}{>{\bfseries}p{2.8cm} p{1.6cm} p{7.0cm} p{2.8cm}}
  \toprule
  \textbf{Pregunta} & \textbf{Puntaje} & \textbf{Evaluación} & \textbf{Errores detectados} \\
  \midrule
  \endhead
  \bottomrule
  \endfoot
""" + tabla_preguntas_body + r"""
\end{longtable}

% ══ ERRORES DETECTADOS ═══════════════════════════════════════════════════════
\section*{Análisis de errores}

\subsection*{Errores conceptuales}
""" + lista_items(err_concept) + r"""

\subsection*{Errores procedimentales}
""" + lista_items(err_proced) + r"""

% ══ RECOMENDACIONES AL ESTUDIANTE ════════════════════════════════════════════
\section*{Retroalimentación para el estudiante}
\begin{tcolorbox}[cajaRecomendacion, title={Dirigido a: """ + tex(estudiante) + r"""}]
""" + tex(recomendaciones) + r"""
\end{tcolorbox}

% ══ NOTA PARA EL PROFESOR ════════════════════════════════════════════════════
\section*{Nota para el profesor}
\begin{tcolorbox}[
  enhanced, breakable,
  colback=yellow!8, colframe=yellow!60!black,
  fonttitle=\bfseries, coltitle=black,
  title={Observaciones para revisión manual},
  top=4pt, bottom=4pt, left=8pt, right=8pt,
]
""" + tex(nota_prof) + r"""
\end{tcolorbox}

% ══ PIE DE INFORME ════════════════════════════════════════════════════════════
\vspace{12pt}
\begin{center}
  \footnotesize\color{gray}
  Informe generado automáticamente por el sistema de evaluación con IA (""" + tex(modelo) + r""") y soporte LaTex. \\
  Este documento es una evaluación \textbf{preliminar} para ser revisado por el profesor antes de ser entregado al 
  estudiante. \\
  Generado el """ + tex(fecha_str) + r""" \textbullet\ ELECTRÓNICA --- Sistema de Evaluación Académica.
  \end{center}

\end{document}
"""
    return doc


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Genera un informe LaTeX a partir del JSON de evaluación de evaluar_examen.py.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 execution/generar_informe.py --json .tmp/evaluacion_Ana_Alcala.json --output examenes/01/examen_estudiantes/informe_Ana_Alcala.tex
  evaluar_examen --pdf ... | python3 execution/generar_informe.py --output informe.tex
        """,
    )
    parser.add_argument(
        "--json",
        default=None,
        help="Ruta al JSON de evaluación. Si no se especifica, lee desde stdin.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Ruta del archivo .tex de salida.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # ── Leer JSON de entrada ───────────────────────────────────────────────────
    try:
        if args.json:
            json_path = Path(args.json)
            if not json_path.exists():
                print(json.dumps({"status": "error", "code": 1,
                                  "message": f"JSON no encontrado: {args.json}"}))
                sys.exit(1)
            data = json.loads(json_path.read_text(encoding="utf-8"))
        else:
            data = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        print(json.dumps({"status": "error", "code": 4,
                          "message": f"JSON de entrada inválido: {e}"}))
        sys.exit(4)

    if "evaluacion" not in data:
        print(json.dumps({"status": "error", "code": 4,
                          "message": "El JSON no contiene el campo 'evaluacion'. ¿Es un output de evaluar_examen.py?"}))
        sys.exit(4)

    # ── Generar LaTeX ──────────────────────────────────────────────────────────
    latex_content = generar_latex(data)

    # ── Escribir archivo .tex ──────────────────────────────────────────────────
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(latex_content, encoding="utf-8")

    result = {
        "status": "ok",
        "archivo_tex": str(output_path.resolve()),
        "estudiante": data.get("estudiante", "N/A"),
        "puntaje": data.get("evaluacion", {}).get("puntaje_sugerido", "N/A"),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
