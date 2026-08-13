#!/usr/bin/env python3
"""
generar_examen_latex.py — Genera documento LaTeX de examen a partir del JSON (Layer 3: Execution)

Lee el JSON producido por elaborar_examen.py y genera un examen profesional
en formato LaTeX listo para compilar con pdflatex. Opcionalmente genera también
un solucionario separado.

Uso:
    python3 execution/generar_examen_latex.py --json .tmp/examen_Semana4.json --output examen.tex
    python3 execution/generar_examen_latex.py --json <ruta_json> --output <ruta_tex> [--soluciones solucionario.tex]

Salida (stdout, JSON):
    { "status": "ok", "archivo_tex": "...", "timestamp": "..." }

Códigos de salida:
    0 — Examen generado correctamente
    1 — Argumento inválido o JSON no encontrado
    4 — JSON de entrada inválido o incompleto
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
if str(SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR.parent))

from execution.estilo_infografia import PREAMBULO_INFOGRAFIA


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

# Comandos matemáticos que nunca deben quedar dentro de \text{} (ver .agent/latex.md #13)
_TEXT_CMD = re.compile(r'\\text\{([^}]*)\}')

def _fix_text_math(s: str) -> str:
    """Saca comandos matemáticos (\\Omega, \\mu, ...) de dentro de \\text{}.

    El LLM a veces genera `\\text{ k\\Omega}` (contenido matemático dentro de
    modo texto), lo que rompe la compilación con 'Missing $ inserted'
    (ver .agent/latex.md #13). Se reescribe `\\text{ 2.2 k\\Omega}` como
    `\\text{ 2.2 k}\\Omega`.
    """
    def _repl(m: re.Match) -> str:
        content = m.group(1)
        m_math = list(re.finditer(r'\\[a-zA-Z]+', content))
        if not m_math:
            return m.group(0)
        out, pos = [], 0
        def _push_text(chunk: str) -> None:
            if chunk:
                out.append("\\text{" + chunk + "}")
        for cm in m_math:
            _push_text(content[pos:cm.start()])
            out.append(cm.group(0))
            pos = cm.end()
        _push_text(content[pos:])
        return "".join(out)
    return _TEXT_CMD.sub(_repl, s)


def tex(s: str) -> str:
    if not s:
        return ""
    # Arreglar errores comunes de los LLMs al querer generar saltos de línea
    s = s.replace("$\\$", "\n\n")
    s = s.replace("$\\\\$", "\n\n")
    for char, repl in _UNICODE_TO_LATEX:
        s = s.replace(char, repl)
    parts = _MATH_PATTERN.split(s)
    result = []
    for part in parts:
        if part.startswith("$"):
            part = part.replace("\\imes", "\\times")
            part = part.replace("\\rac", "\\frac")
            part = part.replace("\\au", "\\tau")
            part = part.replace("\\%", "%").replace("%", "\\%")
            part = _fix_text_math(part)
            result.append(part)
        else:
            for char, repl in _LATEX_ESCAPE:
                part = part.replace(char, repl)
            result.append(part)
    return "".join(result)


# ── Generador de preguntas (compartido entre examen y solucionario) ─────────

def _pregunta_body(preguntas: list[dict]) -> str:
    """Genera el body LaTeX de las preguntas (sin soluciones)."""
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
% ── Pregunta {num} ──────────────────────────────────────────────────────
\\subsection*{{Pregunta {num} \\normalfont\\normalsize\\textit{{({pts})}}}}
{enc}

{diag_tex}
\\vspace{{2mm}}
\\rule{{\\linewidth}}{{0.2pt}}
\\vspace{{3cm}}  % espacio para respuesta

""")
    return "\n".join(cuerpo)


def _soluciones_body(preguntas: list[dict]) -> str:
    """Genera el body LaTeX de las soluciones."""
    cuerpo = []
    for p in preguntas:
        num       = p.get("numero", "?")
        sol       = tex(p.get("solucion", "Solución no disponible."))
        conceptos = p.get("conceptos_evaluados", [])
        conc_str  = ", ".join(f"\\texttt{{{tex(c)}}}" for c in conceptos) if conceptos else "---"
        cuerpo.append(f"""
% ── Solución Pregunta {num} ─────────────────────────────────────────────────
\\subsection*{{Pregunta {num} \\normalfont\\normalsize\\textit{{--- Solución}}}}
\\textbf{{Conceptos evaluados:}} {conc_str}

{sol}

\\vspace{{4pt}}
\\rule{{\\linewidth}}{{0.2pt}}
\\vspace{{6pt}}

""")
    return "\n".join(cuerpo)


_PREAMBLE_COMMON = PREAMBULO_INFOGRAFIA


def generar_examen_latex(data: dict) -> str:
    """Genera el documento LaTeX del examen (sin soluciones)."""
    examen = data.get("examen", {})
    modelo     = data.get("modelo", "N/A")
    from datetime import timezone
    timestamp  = data.get("timestamp", datetime.now(timezone.utc).isoformat() + "Z")
    fecha_str  = timestamp[:10]

    titulo      = examen.get("titulo", "Examen de Electrónica")
    dificultad  = examen.get("dificultad", "intermedia")
    duracion    = examen.get("duracion_sugerida", "90 minutos")
    instrucciones = examen.get("instrucciones", "")
    material    = examen.get("material_permitido", "Calculadora científica.")
    preguntas   = examen.get("preguntas", [])

    preguntas_str = _pregunta_body(preguntas)

    head = f"""
\\fancyhead[L]{{\\small\\color{{azulTitulo}}\\textbf{{ELECTRÓNICA}} --- Examen}}
\\fancyhead[R]{{\\small\\itshape {tex(titulo[:60])}}}
\\fancyfoot[C]{{\\small Página \\thepage\\ de \\pageref{{LastPage}}}}
\\renewcommand{{\\headrulewidth}}{{0.4pt}}

% ── Colores y estilos específicos del examen ───────────────────────────────────
\\definecolor{{verdePuntaje}}{{HTML}}{{1A6B2F}}

\\tcbset{{
  cajaInstrucciones/.style={{
    enhanced, breakable,
    colback=grisFondo, colframe=grisBorde,
    fonttitle=\\bfseries, coltitle=azulTitulo,
    top=6pt, bottom=6pt, left=8pt, right=8pt,
  }},
}}

% ──────────────────────────────────────────────────────────────────────────────
\\begin{{document}}

% ══ PORTADA / ENCABEZADO INFográfico ════════════════════════════════════════════
\\bandaTitulo{{ELECTRÓNICA}}{{{tex(titulo)}}}

\\begin{{center}}
  \\vspace{{2pt}}
  {{\\large \\textbf{{Dificultad:}} {tex(dificultad.capitalize())} \\hfill
   \\textbf{{Duración:}} {tex(duracion)}}} \\\\[4pt]
  {{\\large \\textbf{{Fecha:}} \\rule{{4cm}}{{0.2pt}} \\hfill
   \\textbf{{Estudiante:}} \\rule{{6cm}}{{0.2pt}}}} \\\\[6pt]
  \\rule{{\\linewidth}}{{0.2pt}}
\\end{{center}}

% ══ DATOS DEL EXAMEN ═══════════════════════════════════════════════════════════
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
    \\small\\textit{{Responda cada pregunta en el espacio provisto. \\\\
    Debe mostrar todo el desarrollo matemático para obtener puntaje completo.}}
  \\end{{tcolorbox}}
\\end{{center}}

% ══ PREGUNTAS ══════════════════════════════════════════════════════════════════
\\section*{{Preguntas}}

{preguntas_str}

% ══ FIN DEL EXAMEN ═════════════════════════════════════════════════════════════
\\vspace{{12pt}}
\\begin{{center}}
  \\rule{{0.6\\linewidth}}{{0.4pt}} \\\\[6pt]
  \\textbf{{--- Fin del examen ---}}
\\end{{center}}

\\vfill
\\begin{{center}}
  \\footnotesize\\color{{gray}}
  Examen generado automáticamente por el sistema de inteligencia artificial ({tex(modelo)}) \\\\
  ELECTRÓNICA --- Sistema de Evaluación Académica \\\\
  Generado el {tex(fecha_str)}
\\end{{center}}

\\end{{document}}
"""
    return _PREAMBLE_COMMON + head


def generar_solucionario_latex(data: dict) -> str:
    """Genera el documento LaTeX del solucionario como documento independiente."""
    examen    = data.get("examen", {})
    modelo    = data.get("modelo", "N/A")
    from datetime import timezone
    timestamp = data.get("timestamp", datetime.now(timezone.utc).isoformat() + "Z")
    fecha_str = timestamp[:10]
    titulo    = examen.get("titulo", "Examen de Electrónica")
    preguntas = examen.get("preguntas", [])

    soluciones_str = _soluciones_body(preguntas)

    head = f"""
\\fancyhead[L]{{\\small\\color{{azulTitulo}}\\textbf{{ELECTRÓNICA}} --- Solucionario}}
\\fancyhead[R]{{\\small\\itshape {tex(titulo[:60])}}}
\\fancyfoot[C]{{\\small Página \\thepage\\ de \\pageref{{LastPage}}}}
\\renewcommand{{\\headrulewidth}}{{0.4pt}}

% ──────────────────────────────────────────────────────────────────────────────
\\begin{{document}}

% ══ PORTADA INFográfica ════════════════════════════════════════════════════════
\\bandaTitulo{{ELECTRÓNICA --- Solucionario}}{{{tex(titulo)}}}

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
        description="Genera documentos LaTeX de examen a partir del JSON de elaborar_examen.py.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 execution/generar_examen_latex.py --json .tmp/examen.json --output examen.tex
  python3 execution/generar_examen_latex.py --json .tmp/examen.json --output examen.tex --sol-output sol_examen.tex
        """,
    )
    parser.add_argument(
        "--json", default=None,
        help="Ruta al JSON del examen. Si no se especifica, lee desde stdin.",
    )
    parser.add_argument(
        "--output", required=True,
        help="Ruta del archivo .tex del examen (sin soluciones).",
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

    if "examen" not in data:
        print(json.dumps({"status": "error", "code": 4,
                          "message": "El JSON no contiene el campo 'examen'. ¿Es un output de elaborar_examen.py?"}))
        sys.exit(4)

    # Generar el examen (nunca incluye soluciones)
    examen_latex = generar_examen_latex(data)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(examen_latex, encoding="utf-8")

    archivos_generados = [str(output_path.resolve())]

    # Generar solucionario separado si se solicitó
    if args.sol_output:
        sol_latex = generar_solucionario_latex(data)
        sol_path = Path(args.sol_output)
        sol_path.parent.mkdir(parents=True, exist_ok=True)
        sol_path.write_text(sol_latex, encoding="utf-8")
        archivos_generados.append(str(sol_path.resolve()))

    from datetime import timezone
    result = {
        "status": "ok",
        "archivos_tex": archivos_generados,
        "tema": data.get("tema", "N/A"),
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
