#!/usr/bin/env python3
"""
generar_ejercicios_latex.py — Genera documento LaTeX de ejercicios a partir del JSON (Layer 3: Execution)

Lee el JSON producido por elaborar_ejercicios.py y genera una hoja de ejercicios
profesional en formato LaTeX lista para compilar con pdflatex. Opcionalmente genera
también un solucionario separado.

Uso:
    python3 execution/generar_ejercicios_latex.py --json .tmp/ejercicios_Semana4.json --output ejercicios.tex
    python3 execution/generar_ejercicios_latex.py --json <ruta_json> --output <ruta_tex> [--sol-output solucionario.tex]

Salida (stdout, JSON):
    { "status": "ok", "archivos_tex": ["..."], "timestamp": "..." }

Códigos de salida:
    0 — Ejercicios generados correctamente
    1 — Argumento inválido o JSON no encontrado
    4 — JSON de entrada inválido o incompleto
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path


# ── Helpers de escape LaTeX ─────────────────────────────────────────────────────

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

# Patrón para identificar bloques matemáticos: $$...$$ y $...$
_MATH_PATTERN = re.compile(r'(\$\$.*?\$\$|\$.*?\$)', re.DOTALL)


def _fix_math_ascii_greek(math_part: str) -> str:
    """Convierte nombres ASCII de letras griegas a comandos LaTeX dentro de $...$.

    Usa un solo regex por pass (lowercase / uppercase) para evitar que
    reemplazos posteriores actúen dentro de reemplazos anteriores.
    Las minúsculas requieren lookbehind de no-letra para evitar falsos
    positivos dentro de palabras (ej. 'mu' dentro de 'emu').
    Las mayúsculas permiten letras antes (ej. 'kOmega' → 'k\\Omega').
    """
    # Minúsculas: solo precedidas por no-letra (número, espacio, $, puntuación)
    re_lower = re.compile(
        r'(?<!\\)(?<![a-zA-Z])(' + '|'.join([
            'varepsilon', 'vartheta', 'varphi', 'varsigma',
            'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta',
            'eta', 'theta', 'iota', 'kappa', 'lambda', 'mu',
            'nu', 'omicron', 'pi', 'rho', 'sigma', 'tau',
            'upsilon', 'phi', 'chi', 'psi', 'omega',
        ]) + r')(?![a-zA-Z])'
    )
    math_part = re_lower.sub(lambda m: '\\' + m.group(1), math_part)

    # Mayúsculas: permiten prefijo de letra (k, M, G antes de Omega)
    re_upper = re.compile(
        r'(?<!\\)(' + '|'.join([
            'Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon', 'Zeta',
            'Eta', 'Theta', 'Iota', 'Kappa', 'Lambda', 'Mu',
            'Nu', 'Xi', 'Omicron', 'Pi', 'Rho', 'Sigma', 'Tau',
            'Upsilon', 'Phi', 'Chi', 'Psi', 'Omega',
        ]) + r')(?![a-zA-Z])'
    )
    math_part = re_upper.sub(lambda m: '\\' + m.group(1), math_part)

    return math_part


def _fix_math_ascii_commands(math_part: str) -> str:
    """Convierte nombres ASCII de comandos matemáticos comunes a LaTeX dentro de $...$."""
    _MATH_ASCII_CMDS = re.compile(
        r'(?<!\\)(?<![a-zA-Z])(' + '|'.join([
            'approx', 'cdot', 'circ', 'partial', 'nabla', 'infty',
            'propto', 'sim', 'equiv', 'cong', 'neg', 'wedge', 'vee',
            'subset', 'supset', 'subseteq', 'supseteq',
            'rightarrow', 'leftarrow', 'Rightarrow', 'Leftarrow',
            'leftrightarrow', 'Leftrightarrow', 'mapsto', 'longrightarrow',
            'Longrightarrow', 'longmapsto',
            'langle', 'rangle', 'lceil', 'rceil', 'lfloor', 'rfloor',
            'perp', 'top', 'bot',
            'angle', 'measuredangle',
            'triangle', 'triangledown',
            'forall', 'exists', 'nexists',
            'varnothing', 'emptyset',
            'aleph', 'hbar', 'ell', 'imath', 'jmath',
            'Re', 'Im',
            'log', 'ln', 'lg', 'exp', 'sin', 'cos', 'tan', 'cot',
            'sec', 'csc', 'arcsin', 'arccos', 'arctan',
            'sinh', 'cosh', 'tanh', 'coth',
            'max', 'min', 'sup', 'inf', 'lim', 'det', 'arg',
        ]) + r')(?![a-zA-Z])'
    )
    return _MATH_ASCII_CMDS.sub(lambda m: '\\' + m.group(1), math_part)


def tex(s: str) -> str:
    if not s:
        return ""
    # Arreglar errores comunes de los LLMs al querer generar saltos de línea
    s = s.replace("$\\$", "\n\n")
    s = s.replace("$\\\\$", "\n\n")
    # LLMs a veces emiten caracteres de control (tab, form-feed) en lugar de \\
    s = s.replace("\t", "\\")
    s = s.replace("\f", "\\")
    for char, repl in _UNICODE_TO_LATEX:
        s = s.replace(char, repl)
    parts = _MATH_PATTERN.split(s)
    result = []
    for part in parts:
        if part.startswith("$"):
            part = _fix_math_ascii_greek(part)
            part = _fix_math_ascii_commands(part)
            part = part.replace("\\imes", "\\times")
            part = part.replace("\\rac", "\\frac")
            part = part.replace("\\au", "\\tau")
            part = part.replace("\\%", "%").replace("%", "\\%")
            result.append(part)
        else:
            for char, repl in _LATEX_ESCAPE:
                part = part.replace(char, repl)
            result.append(part)
    return "".join(result)


# ── Generador de preguntas (compartido entre ejercicios y solucionario) ─────────

def _pregunta_body(preguntas: list[dict]) -> str:
    """Genera el body LaTeX de los ejercicios (sin soluciones)."""
    cuerpo = []
    for p in preguntas:
        num  = p.get("numero", "?")
        enc  = tex(p.get("enunciado", ""))
        pts  = tex(p.get("puntaje", ""))
        diag = p.get("diagrama_sugerido")
        diag_tex = ""
        if diag:
            diag_tex = (
                "  \\begin{tcolorbox}[colback=gray!5, colframe=gray!40, "
                "fonttitle=\\bfseries, title={Diagrama sugerido}]\n"
                f"    {tex(diag)}\n"
                "  \\end{tcolorbox}\n"
            )
        cuerpo.append(f"""
% ── Ejercicio {num} ──────────────────────────────────────────────────────
\\subsection*{{Ejercicio {num} \\normalfont\\normalsize\\textit{{({pts})}}}}
{enc}

{diag_tex}
\\vspace{{2mm}}
\\rule{{\\linewidth}}{{0.2pt}}
\\vspace{{3cm}}  % espacio para respuesta

""")
    return "\n".join(cuerpo)


def _soluciones_body(preguntas: list[dict]) -> str:
    """Genera el body LaTeX de las soluciones (incluyendo enunciados)."""
    cuerpo = []
    for p in preguntas:
        num       = p.get("numero", "?")
        enc       = tex(p.get("enunciado", ""))
        pts       = tex(p.get("puntaje", ""))
        diag      = p.get("diagrama_sugerido")
        sol       = tex(p.get("solucion", "Solución no disponible."))
        conceptos = p.get("conceptos_evaluados", [])
        conc_str  = ", ".join(f"\\texttt{{{tex(c)}}}" for c in conceptos) if conceptos else "---"
        
        diag_tex = ""
        if diag:
            diag_tex = (
                "  \\begin{tcolorbox}[colback=gray!5, colframe=gray!40, "
                "fonttitle=\\bfseries, title={Diagrama sugerido}]\n"
                f"    {tex(diag)}\n"
                "  \\end{tcolorbox}\n"
            )

        cuerpo.append(f"""
% ── Solución Ejercicio {num} ─────────────────────────────────────────────────
\\subsection*{{Ejercicio {num} \\normalfont\\normalsize\\textit{{({pts}) --- Solución}}}}
\\textbf{{Enunciado:}}
{enc}

{diag_tex}
\\vspace{{2mm}}
\\textbf{{Conceptos evaluados:}} {conc_str}

\\vspace{{2mm}}
\\textbf{{Solución:}}
{sol}

\\vspace{{4pt}}
\\rule{{\\linewidth}}{{0.2pt}}
\\vspace{{6pt}}

""")
    return "\n".join(cuerpo)


_PREAMBLE_COMMON = r"""\documentclass[11pt,a4paper]{article}

% ── Codificación y fuentes ────────────────────────────────────────────────────
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[spanish,es-noshorthands]{babel}

% ── Geometría y espaciado ─────────────────────────────────────────────────────
\usepackage[top=2.5cm, bottom=2.5cm, left=2.8cm, right=2.8cm]{geometry}
\usepackage{setspace}
\setstretch{1.10}
\usepackage{parskip}

% ── Matemáticas ───────────────────────────────────────────────────────────────
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{siunitx}

% ── Circuitos ────────────────────────────────────────────────────────────────
\usepackage[european, straightvoltages]{circuitikz}

% ── Tablas ────────────────────────────────────────────────────────────────────
\usepackage{booktabs}
\usepackage{array}
\usepackage{enumitem}

% ── Colores y cajas ───────────────────────────────────────────────────────────
\usepackage[dvipsnames]{xcolor}
\usepackage{tcolorbox}
\tcbuselibrary{skins, breakable}

% ── Cabeceras y pies ──────────────────────────────────────────────────────────
\usepackage{fancyhdr}
\usepackage{lastpage}
\pagestyle{fancy}
\fancyhf{}
"""


def generar_ejercicios_latex(data: dict) -> str:
    """Genera el documento LaTeX de los ejercicios (sin soluciones)."""
    ejercicios = data.get("ejercicios", {})
    modelo     = data.get("modelo", "N/A")
    timestamp  = data.get("timestamp", datetime.utcnow().isoformat() + "Z")
    fecha_str  = timestamp[:10]

    titulo      = ejercicios.get("titulo", "Ejercicios de Electrónica")
    dificultad  = ejercicios.get("dificultad", "intermedia")
    duracion    = ejercicios.get("duracion_sugerida", "90 minutos")
    instrucciones = ejercicios.get("instrucciones", "")
    material    = ejercicios.get("material_permitido", "Calculadora científica.")
    preguntas   = ejercicios.get("preguntas", [])

    preguntas_str = _pregunta_body(preguntas)

    head = f"""
\\fancyhead[L]{{\\small\\textbf{{ELECTRÓNICA}} --- Ejercicios}}
\\fancyhead[R]{{\\small\\itshape {tex(titulo[:60])}}}
\\fancyfoot[C]{{\\small Página \\thepage\\ de \\pageref{{LastPage}}}}
\\renewcommand{{\\headrulewidth}}{{0.4pt}}

% ── Hiperenlaces ──────────────────────────────────────────────────────────────
\\usepackage[colorlinks=true, linkcolor=NavyBlue, urlcolor=NavyBlue]{{hyperref}}

% ── Colores personalizados ────────────────────────────────────────────────────
\\definecolor{{azulTitulo}}{{HTML}}{{1B2A6B}}
\\definecolor{{grisFondo}}{{HTML}}{{F5F5F5}}
\\definecolor{{verdePuntaje}}{{HTML}}{{1A6B2F}}

% ── Estilos de cajas ─────────────────────────────────────────────────────────
\\tcbset{{
  cajaInstrucciones/.style={{
    enhanced, breakable,
    colback=grisFondo, colframe=gray!50,
    fonttitle=\\bfseries, coltitle=black,
    top=6pt, bottom=6pt, left=8pt, right=8pt,
  }},
}}

% ──────────────────────────────────────────────────────────────────────────────
\\begin{{document}}

% ══ PORTADA / ENCABEZADO ═══════════════════════════════════════════════════════
\\begin{{center}}
  {{\\Large\\bfseries\\color{{azulTitulo}} ELECTRÓNICA}}\\\\[4pt]
  {{\\large Hoja de Ejercicios de Razonamiento y Cálculo}}\\\\[8pt]
  \\rule{{\\linewidth}}{{1.2pt}}\\\\[6pt]
  {{\\LARGE\\bfseries {tex(titulo)}}}\\\\[6pt]
  \\rule{{\\linewidth}}{{0.6pt}}\\\\[6pt]
  {{\\large \\textbf{{Dificultad:}} {tex(dificultad.capitalize())} \\hfill
   \\textbf{{Duración:}} {tex(duracion)}}} \\\\[4pt]
  {{\\large \\textbf{{Fecha:}} \\rule{{4cm}}{{0.2pt}} \\hfill
   \\textbf{{Estudiante:}} \\rule{{6cm}}{{0.2pt}}}} \\\\[6pt]
  \\rule{{\\linewidth}}{{0.2pt}}
\\end{{center}}

% ══ DATOS DE LOS EJERCICIOS ════════════════════════════════════════════════════
\\vspace{{4pt}}
\\begin{{tcolorbox}}[cajaInstrucciones, title={{Instrucciones}}]
{tex(instrucciones)}
\\medskip
\\textbf{{Material permitido:}} {tex(material)}
\\end{{tcolorbox}}

% ══ INDICACIÓN DE PUNTAJE ═════════════════════════════════════════════════════
\\vspace{{4pt}}
\\begin{{center}}
  \\begin{{tcolorbox}}[
    enhanced,
    colback=white, colframe=azulTitulo,
    width=0.6\\linewidth,
    boxrule=1.5pt,
    halign=center, valign=center,
    top=4pt, bottom=4pt,
  ]
    \\centering
    \\textbf{{Puntaje total: 10.0 puntos}} \\\\
    \\small\\textit{{Responda cada ejercicio en el espacio provisto. \\\\
    Debe mostrar todo el desarrollo matemático para obtener puntaje completo.}}
  \\end{{tcolorbox}}
\\end{{center}}

% ══ EJERCICIOS ═════════════════════════════════════════════════════════════════
\\section*{{Ejercicios}}

{preguntas_str}

% ══ FIN DE LOS EJERCICIOS ══════════════════════════════════════════════════════
\\vspace{{12pt}}
\\begin{{center}}
  \\rule{{0.6\\linewidth}}{{0.4pt}} \\\\[6pt]
  \\textbf{{--- Fin de la hoja de ejercicios ---}}
\\end{{center}}

\\vfill
\\begin{{center}}
  \\footnotesize\\color{{gray}}
  Ejercicios generados automáticamente por el sistema de inteligencia artificial ({tex(modelo)}) \\\\
  ELECTRÓNICA --- Sistema de Evaluación Académica \\\\
  Generado el {tex(fecha_str)}
\\end{{center}}

\\end{{document}}
"""
    return _PREAMBLE_COMMON + head


def generar_solucionario_latex(data: dict) -> str:
    """Genera el documento LaTeX del solucionario como documento independiente."""
    ejercicios = data.get("ejercicios", {})
    modelo    = data.get("modelo", "N/A")
    timestamp = data.get("timestamp", datetime.utcnow().isoformat() + "Z")
    fecha_str = timestamp[:10]
    titulo    = ejercicios.get("titulo", "Ejercicios de Electrónica")
    preguntas = ejercicios.get("preguntas", [])

    soluciones_str = _soluciones_body(preguntas)

    head = f"""
\\fancyhead[L]{{\\small\\textbf{{ELECTRÓNICA}} --- Solucionario}}
\\fancyhead[R]{{\\small\\itshape {tex(titulo[:60])}}}
\\fancyfoot[C]{{\\small Página \\thepage\\ de \\pageref{{LastPage}}}}
\\renewcommand{{\\headrulewidth}}{{0.4pt}}

% ── Hiperenlaces ──────────────────────────────────────────────────────────────
\\usepackage[colorlinks=true, linkcolor=NavyBlue, urlcolor=NavyBlue]{{hyperref}}

% ── Colores personalizados ────────────────────────────────────────────────────
\\definecolor{{azulTitulo}}{{HTML}}{{1B2A6B}}
\\definecolor{{grisFondo}}{{HTML}}{{F5F5F5}}

% ──────────────────────────────────────────────────────────────────────────────
\\begin{{document}}

% ══ PORTADA ═════════════════════════════════════════════════════════════════════
\\begin{{center}}
  {{\\Large\\bfseries\\color{{azulTitulo}} ELECTRÓNICA}}\\\\[4pt]
  {{\\large Solucionario de Ejercicios}}\\\\[8pt]
  \\rule{{\\linewidth}}{{1.2pt}}\\\\[6pt]
  {{\\LARGE\\bfseries {tex(titulo)}}}\\\\[6pt]
  \\rule{{\\linewidth}}{{0.6pt}}
\\end{{center}}

\\vspace{{4pt}}
\\noindent\\textit{{Las siguientes soluciones son una guía de referencia para el profesor.}}
\\textit{{Los estudiantes pueden presentar desarrollos equivalentes.}}
\\vspace{{8pt}}

{soluciones_str}

% ══ FIN DEL SOLUCIONARIO ═══════════════════════════════════════════════════════
\\vspace{{12pt}}
\\begin{{center}}
  \\rule{{0.6\\linewidth}}{{0.4pt}} \\\\[6pt]
  \\textbf{{--- Fin del solucionario ---}}
\\end{{center}}

\\vfill
\\begin{{center}}
  \\footnotesize\\color{{gray}}
  Solucionario generado automáticamente por el sistema de inteligencia artificial ({tex(modelo)}) \\\\
  ELECTRÓNICA --- Sistema de Evaluación Académica \\\\
  Generado el {tex(fecha_str)}
\\end{{center}}

\\end{{document}}
"""
    return _PREAMBLE_COMMON + head


# ── CLI ──────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Genera documentos LaTeX de ejercicios a partir del JSON de elaborar_ejercicios.py.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 execution/generar_ejercicios_latex.py --json .tmp/ejercicios.json --output ejercicios.tex
  python3 execution/generar_ejercicios_latex.py --json .tmp/ejercicios.json --output ejercicios.tex --sol-output sol_ejercicios.tex
        """,
    )
    parser.add_argument(
        "--json", default=None,
        help="Ruta al JSON de los ejercicios. Si no se especifica, lee desde stdin.",
    )
    parser.add_argument(
        "--output", required=True,
        help="Ruta del archivo .tex de los ejercicios (sin soluciones).",
    )
    parser.add_argument(
        "--sol-output", default=None,
        help="Ruta del archivo .tex del solucionario separado. Si se omite, no se genera solucionario.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

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

    if "ejercicios" not in data:
        print(json.dumps({"status": "error", "code": 4,
                          "message": "El JSON no contiene el campo 'ejercicios'. ¿Es un output de elaborar_ejercicios.py?"}))
        sys.exit(4)

    # Generar los ejercicios (nunca incluye soluciones)
    ejercicios_latex = generar_ejercicios_latex(data)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(ejercicios_latex, encoding="utf-8")

    archivos_generados = [str(output_path.resolve())]

    # Generar solucionario separado si se solicitó
    if args.sol_output:
        sol_latex = generar_solucionario_latex(data)
        sol_path = Path(args.sol_output)
        sol_path.parent.mkdir(parents=True, exist_ok=True)
        sol_path.write_text(sol_latex, encoding="utf-8")
        archivos_generados.append(str(sol_path.resolve()))

    result = {
        "status": "ok",
        "archivos_tex": archivos_generados,
        "tema": data.get("tema", "N/A"),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
