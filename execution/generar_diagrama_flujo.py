#!/usr/bin/env python3
"""
generar_diagrama_flujo.py — Generador determinista de diagramas de flujo ISO 5807
(Layer 3: Execution)

Lee un descriptor JSON con nodos y conexiones, genera un .tex con estilos TiKZ
ISO 5807 canónicos (terminador/proceso/decision/almacenamiento/entradasalida/
documento/nota/etiqueta), compila 2 pasadas, verifica el PDF y publica.

Arquitectura: directiva diagrama_flujo.yaml (L1) → orquestador (L2) → este script (L3).

Uso:
  python3 execution/generar_diagrama_flujo.py --descriptor .tmp/descriptor_flujo.json
  python3 execution/generar_diagrama_flujo.py --descriptor ... --output docs/TEMA/proceso_flujo
  python3 execution/generar_diagrama_flujo.py --dry-run   # solo genera .tex sin compilar
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

# ─── Constantes ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = PROJECT_ROOT / ".tmp" / "latex_build"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TIPOS_VALIDOS = frozenset({
    "terminador", "proceso", "decision", "almacenamiento",
    "entradasalida", "documento", "nota",
})

COL_SPACING_CM = 3.5
FILA_SPACING_CM = 2.0

# ─── Estilos TiKZ ISO 5807 / ANSI X3.5 (constante, no depende de external files) ──
TIKZ_ESTILOS_ISO = r"""
  % ── Estilos de flujo (ISO 5807 / ANSI X3.5) ─────────────────────────────
  \tikzset{
    flujo/.style={
      >=Stealth,
      font=\footnotesize\sffamily,
    },
    terminador/.style={
      draw=azulNoche, fill=azulNoche!8!white, rounded corners=3pt,
      text width=2.2cm, align=center, inner sep=2mm,
      font=\footnotesize\sffamily,
    },
    proceso/.style={
      draw=azulNoche, fill=cyanNeon!10!white,
      text width=2.2cm, align=center, inner sep=2mm,
      font=\footnotesize\sffamily,
    },
    entradasalida/.style={
      draw=azulNoche, fill=verdeSignal!10!white,
      trapezium, trapezium left angle=75, trapezium right angle=105,
      text width=2.2cm, align=center, inner sep=2mm,
      font=\footnotesize\sffamily,
    },
    decision/.style={
      draw=azulNoche, fill=amarilloNota!20!white,
      diamond, aspect=1.6, text width=2.0cm, align=center, inner sep=1pt,
      font=\footnotesize\sffamily,
    },
    almacenamiento/.style={
      draw=azulNoche, fill=grisPapel,
      cylinder, shape border rotate=90, aspect=0.3,
      text width=2.2cm, align=center, inner sep=2mm,
      font=\footnotesize\sffamily,
    },
    documento/.style={
      draw=azulNoche, fill=azulMedio!8!white,
      text width=2.2cm, align=center, inner sep=2mm,
      font=\footnotesize\sffamily,
    },
    nota/.style={
      draw=grisLinea, dashed, fill=grisPapel,
      text width=2.4cm, align=center, inner sep=2mm,
      font=\scriptsize\sffamily,
    },
    etiqueta/.style={
      font=\scriptsize\sffamily, fill=white,
      fill opacity=0.75, text opacity=1, inner sep=1pt,
    },
  }
"""

# ─── Validación ────────────────────────────────────────────────────────────────
def _validar_descriptor(d: dict) -> None:
    """Lanza ValueError si el descriptor tiene errores estructurales."""
    if not isinstance(d, dict):
        raise ValueError("El descriptor debe ser un objeto JSON (dict).")
    for campo in ("titulo", "subtitulo", "secciones"):
        if campo not in d:
            raise ValueError(f"Falta campo obligatorio '{campo}'.")
    if not isinstance(d["secciones"], list) or len(d["secciones"]) == 0:
        raise ValueError("'secciones' debe ser una lista no vacía.")
    ids_vistos: set[str] = set()
    for i, sec in enumerate(d["secciones"]):
        if "nombre" not in sec or "nodos" not in sec:
            raise ValueError(f"Sección {i}: faltan 'nombre' o 'nodos'.")
        for nodo in sec["nodos"]:
            nid = nodo.get("id", "")
            if not nid:
                raise ValueError(f"Sección {i}: nodo sin 'id'.")
            if nid in ids_vistos:
                raise ValueError(f"Sección {i}: id duplicado '{nid}'.")
            ids_vistos.add(nid)
            tipo = nodo.get("tipo", "")
            if tipo not in TIPOS_VALIDOS:
                raise ValueError(
                    f"Sección {i}, nodo '{nid}': tipo '{tipo}' inválido. "
                    f"Válidos: {', '.join(sorted(TIPOS_VALIDOS))}."
                )
            if "col" not in nodo or "fila" not in nodo:
                raise ValueError(
                    f"Sección {i}, nodo '{nid}': faltan 'col' y/o 'fila'."
                )
        for j, conn in enumerate(sec.get("conexiones", [])):
            for campo in ("from", "to"):
                if campo not in conn:
                    raise ValueError(f"Sección {i}, conexión {j}: falta '{campo}'.")
            if conn["from"] not in ids_vistos:
                raise ValueError(
                    f"Sección {i}, conexión {j}: '{conn['from']}' no existe."
                )
            if conn["to"] not in ids_vistos:
                raise ValueError(
                    f"Sección {i}, conexión {j}: '{conn['to']}' no existe."
                )


# ─── Generación LaTeX ──────────────────────────────────────────────────────────
def _nodo_a_coordenada(nodo: dict) -> tuple[float, float]:
    col = nodo["col"]
    fila = nodo["fila"]
    x = col * COL_SPACING_CM
    y = -fila * FILA_SPACING_CM
    return round(x, 1), round(y, 1)


def _escape_tex(texto: str) -> str:
    """Escapa caracteres especiales de LaTeX fuera de modo matemático."""
    for orig, repl in [("&", r"\&"), ("%", r"\%"), ("#", r"\#"),
                       ("$", r"\$"), ("_", r"\_"), ("{", r"\{"),
                       ("}", r"\}"), ("~", r"\textasciitilde{}"),
                       ("^", r"\textasciicircum{}")]:
        texto = texto.replace(orig, repl)
    return texto


def _generar_nodos_latex(nodos: list[dict]) -> str:
    lineas = []
    for nodo in nodos:
        nid = nodo["id"]
        tipo = nodo["tipo"]
        texto = _escape_tex(nodo.get("texto", nid))
        x, y = _nodo_a_coordenada(nodo)
        lineas.append(
            f"  \\node[{tipo}] ({nid}) at ({x},{y}) {{{texto}}};"
        )
    return "\n".join(lineas)


def _generar_conexiones_latex(conexiones: list[dict], mapa_nodos: dict) -> str:
    lineas = []
    for conn in conexiones:
        a = conn["from"]
        b = conn["to"]
        etiqueta = conn.get("etiqueta", "")
        col_a = mapa_nodos[a]["col"]
        col_b = mapa_nodos[b]["col"]
        fila_a = mapa_nodos[a]["fila"]
        fila_b = mapa_nodos[b]["fila"]
        # Determinar ancla y ruta según posición relativa
        if col_b == col_a and fila_b > fila_a:
            # Misma columna, va hacia abajo
            ancla_a = "south"
            ancla_b = "north"
            path = f"({a}.{ancla_a}) -- ({b}.{ancla_b})"
        elif col_b > col_a:
            # Va a la derecha
            ancla_a = "east"
            ancla_b = "west"
            if fila_a == fila_b:
                path = f"({a}.{ancla_a}) -- ({b}.{ancla_b})"
            else:
                path = f"({a}.{ancla_a}) -- ({b}.{ancla_b})"
        else:
            # Va a la izquierda
            ancla_a = "west"
            ancla_b = "east"
            path = f"({a}.{ancla_a}) -- ({b}.{ancla_b})"
        if etiqueta:
            lbl = _escape_tex(etiqueta)
            # Posición de etiqueta: sobre la flecha para horizontal, a la izq para vertical
            if abs(col_b - col_a) > 0:
                pos_lbl = ", above"
            else:
                pos_lbl = ", left"
            lineas.append(
                f"  \\draw[->] {path} node[etiqueta{pos_lbl}]{{{lbl}}};"
            )
        else:
            lineas.append(f"  \\draw[->] {path};")
    return "\n".join(lineas)


def _generar_tikzpicture(seccion: dict) -> str:
    nodos = seccion["nodos"]
    conexiones = seccion.get("conexiones", [])
    mapa = {n["id"]: n for n in nodos}
    nodos_latex = _generar_nodos_latex(nodos)
    conex_latex = _generar_conexiones_latex(conexiones, mapa)
    # Calcular límites para fondo
    xs = [_nodo_a_coordenada(n)[0] for n in nodos]
    ys = [_nodo_a_coordenada(n)[1] for n in nodos]
    x_min = min(xs) - 2.0
    x_max = max(xs) + 2.0
    y_min = min(ys) - 2.0
    y_max = max(ys) + 1.5
    ancho = round(x_max - x_min, 1)
    alto = round(y_max - y_min, 1)
    return rf"""\begin{{center}}
\begin{{tikzpicture}}[flujo, >=Stealth, x=1cm, y=1cm]
  % Fondo decorativo
  \fill[azulNoche!3!white, rounded corners=4pt]
    ({round(x_min - 0.3,1)},{round(y_max + 0.3,1)}) rectangle ({round(x_max + 0.3,1)},{round(y_min - 0.3,1)});
{nodos_latex}

{conex_latex}
\end{{tikzpicture}}
\end{{center}}"""


def _generar_tabla_leyenda(nodos: list[dict]) -> str:
    """Genera tabla de leyenda de etiquetas (tipo | etiqueta | significado)."""
    tipos_map = {
        "terminador": "Óvalo (terminador)",
        "proceso": "Rectángulo (proceso)",
        "decision": "Rombo (decisión)",
        "almacenamiento": "Cilindro (almacenamiento)",
        "entradasalida": "Paralelogramo (entrada/salida)",
        "documento": "Rectángulo + onda (documento)",
        "nota": "Rectángulo punteado (nota)",
    }
    filas = []
    for n in sorted(nodos, key=lambda x: x["id"]):
        tipo_largo = tipos_map.get(n["tipo"], n["tipo"])
        sig = _escape_tex(n.get("significado", n.get("texto", "")))
        filas.append(f"{n['id']} & {tipo_largo} & {sig} \\\\")
    filas_str = "\n".join(filas)
    return rf"""\begin{{tcolorbox}}[cajaContenido, title={{\faIcon{{tags}}~Leyenda de etiquetas}}]
\small
\begin{{tabularx}}{{\linewidth}}{{@{{}}llX@{{}}}}
\toprule
\textbf{{Etiqueta}} & \textbf{{Símbolo}} & \textbf{{Significado}} \\
\midrule
{filas_str}
\bottomrule
\end{{tabularx}}
\end{{tcolorbox}}"""


def _generar_doc_latex(descriptor: dict) -> str:
    """Genera el .tex completo a partir del descriptor JSON."""
    titulo = _escape_tex(descriptor["titulo"])
    subtitulo = _escape_tex(descriptor.get("subtitulo", ""))
    cabecera_izq = _escape_tex(descriptor.get("cabecera_izq", "ELECTRÓNICA"))
    cabecera_der = _escape_tex(descriptor.get("cabecera_der", ""))
    icono = descriptor.get("icono_banda", "sitemap")
    if cabecera_der:
        fancyhead_der = f"\\fancyhead[R]{{\\small\\color{{grisTexto}}{cabecera_der}}}"
    else:
        fancyhead_der = ""

    # Cuerpo: secciones con tikzpicture + leyenda
    bloques = []
    for sec in descriptor["secciones"]:
        nombre_sec = _escape_tex(sec["nombre"])
        icono_sec = sec.get("icono", "cogs")
        tikz = _generar_tikzpicture(sec)
        nodos = sec.get("nodos", [])
        leyenda = _generar_tabla_leyenda(nodos) if nodos else ""
        seccion_latex = (
            rf"\section{{\iconotexto{{{icono_sec}}}{{{nombre_sec}}}}}" + "\n\n"
            + tikz
        )
        if leyenda:
            seccion_latex += "\n\n" + leyenda
        bloques.append(seccion_latex)

    cuerpo_secciones = "\n\n".join(bloques)

    # Notas explicativas del script (si las hay)
    notas_tex = ""
    if descriptor.get("notas"):
        notas_items = "\n".join(
            rf"\item {_escape_tex(n)}" for n in descriptor["notas"]
        )
        notas_tex = rf"""
\section{{\iconotexto{{sticky-note}}{{Notas}}}}
\begin{{itemize}}
{notas_items}
\end{{itemize}}"""

    return rf"""% ======================================================================
% Diagrama de flujo — generado automáticamente por generar_diagrama_flujo.py
% NO EDITAR MANUALMENTE; regenerar desde el descriptor JSON.
% ======================================================================
\documentclass[11pt,a4paper]{{article}}

% ── Codificación, fuentes y lenguaje ───────────────────────────────────────────
\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage[default,scale=0.95]{{sourcesanspro}}
\renewcommand{{\familydefault}}{{\sfdefault}}
\usepackage[spanish,es-noshorthands,es-tabla]{{babel}}

% ── Geometría y espaciado ─────────────────────────────────────────────────────
\usepackage[top=2.2cm, bottom=2.5cm, left=2.2cm, right=2.2cm, headheight=15pt]{{geometry}}
\usepackage{{setspace}}
\setstretch{{1.18}}
\usepackage{{parskip}}

% ── TikZ (simbolos ISO 5807 / ANSI X3.5) ──────────────────────────────────────
\usepackage{{tikz}}
\usetikzlibrary{{babel, arrows.meta, positioning, shapes.geometric,
                shapes.symbols, decorations.pathmorphing, calc}}

% ── Tablas y listas ───────────────────────────────────────────────────────────
\usepackage{{booktabs}}
\usepackage{{tabularx}}
\usepackage{{array}}
\usepackage{{enumitem}}

% ── Colores, cajas e iconos ───────────────────────────────────────────────────
\usepackage[dvipsnames]{{xcolor}}
\usepackage{{tcolorbox}}
\tcbuselibrary{{skins, breakable}}
\usepackage{{fontawesome5}}

% ── Secciones con barra de color (infografía) ─────────────────────────────────
\usepackage{{titlesec}}
\titleformat{{\section}}
  {{\normalfont\LARGE\bfseries\color{{azulNoche}}}}
  {{\colorbox{{cyanNeon}}{{\color{{fondoOscuro}}\thesection}}}}{{0.7em}}{{}}
  [\vspace{{2pt}}\color{{cyanNeon}}\rule{{\linewidth}}{{1.8pt}}]
\titlespacing*{{\section}}{{0pt}}{{24pt}}{{10pt}}
\titleformat{{\subsection}}
  {{\normalfont\large\bfseries\color{{azulNoche}}}}
  {{\textcolor{{cyanNeon}}{{\thesubsection}}}}{{0.7em}}{{}}
  [\vspace{{1pt}}\color{{grisLinea}}\rule{{\linewidth}}{{0.6pt}}]
\titlespacing*{{\subsection}}{{0pt}}{{14pt}}{{6pt}}

% ── Cabeceras y pies de página ────────────────────────────────────────────────
\usepackage{{fancyhdr}}
\usepackage{{lastpage}}
\pagestyle{{fancy}}
\fancyhf{{}}
\renewcommand{{\headrulewidth}}{{0pt}}
\renewcommand{{\footrulewidth}}{{0pt}}
\fancyfoot[C]{{%
  \begin{{minipage}}{{\linewidth}}
    \vspace{{2pt}}
    \color{{cyanNeon}}\rule{{\linewidth}}{{1.2pt}}\\[2pt]
    \centering\color{{grisTexto}}\footnotesize
    Página \thepage\ de \pageref{{LastPage}}
  \end{{minipage}}%
}}

% ── Hiperenlaces ──────────────────────────────────────────────────────────────
\usepackage[colorlinks=true, linkcolor=azulNoche, urlcolor=cyanNeon]{{hyperref}}
\sloppy
\emergencystretch 3em

% ── Paleta de colores ─────────────────────────────────────────────────────────
\definecolor{{fondoOscuro}}{{HTML}}{{0D1B2A}}
\definecolor{{verdeTurquesa}}{{HTML}}{{004D40}}
\definecolor{{azulNoche}}{{HTML}}{{1B3A6B}}
\definecolor{{azulMedio}}{{HTML}}{{2A5298}}
\definecolor{{cyanNeon}}{{HTML}}{{00C8E0}}
\definecolor{{verdeSignal}}{{HTML}}{{00B887}}
\definecolor{{naranjaVivo}}{{HTML}}{{FF7043}}
\definecolor{{rojoAlerta}}{{HTML}}{{E53935}}
\definecolor{{grisPapel}}{{HTML}}{{F4F6FA}}
\definecolor{{grisLinea}}{{HTML}}{{C8D0E0}}
\definecolor{{grisTexto}}{{HTML}}{{6B7A99}}
\definecolor{{amarilloNota}}{{HTML}}{{FFB300}}

% ── Tarjetas ──────────────────────────────────────────────────────────────────
\tcbset{{
  cajaContenido/.style={{
    enhanced, breakable,
    arc=5pt, outer arc=5pt,
    colback=grisPapel, colframe=grisLinea,
    boxrule=0.8pt,
    fonttitle=\bfseries\small, coltitle=azulNoche,
    top=6pt, bottom=6pt, left=10pt, right=10pt,
  }},
}}

% ── Macros ────────────────────────────────────────────────────────────────────
\newcommand{{\iconotexto}}[2]{{\textcolor{{cyanNeon}}{{\faIcon{{#1}}}}~#2}}
\newcommand{{\iconoBanda}}{{sitemap}}
\newcommand{{\bandaTitulo}}[3][fondoOscuro]{{%
  \noindent
  \begin{{tcolorbox}}[%
    enhanced, arc=4mm, colback=#1!10!white, colframe=#1, boxrule=0pt,
    borderline west={{6pt}}{{0pt}}{{cyanNeon}},
    top=6pt, bottom=6pt, left=8pt, right=8pt,
  ]
    \noindent
    \begin{{minipage}}[c]{{0.10\linewidth}}
      \centering\color{{cyanNeon}}\faIcon{{{icono}}}
    \end{{minipage}}%
    \hspace{{8pt}}%
    \begin{{minipage}}[c]{{0.88\linewidth}}
      {{\fontsize{{20}}{{24}}\selectfont\bfseries\color{{white}}#2}}\par\vspace{{5pt}}%
      \textcolor{{cyanNeon!80!white}}{{\small\faIcon{{angle-right}}~#3}}%
    \end{{minipage}}
    \vspace{{4pt}}
  \end{{tcolorbox}}%
  \vspace{{8pt}}%
}}

{TIKZ_ESTILOS_ISO}

% ── Cabecera del documento ────────────────────────────────────────────────────
\fancyhead[L]{{\small\color{{azulNoche}}\textbf{{{cabecera_izq}}}}}
{fancyhead_der}
\renewcommand{{\headrulewidth}}{{0pt}}

% ─────────────────────────────────────────────────────────────────────────────
\begin{{document}}

\bandaTitulo{{{titulo}}}{{{subtitulo}}}

\vspace{{4pt}}
\begin{{center}}
\begin{{tcolorbox}}[cajaContenido, title={{\faIcon{{map-signs}}~Leyenda de símbolos---ISO 5807 / ANSI X3.5}}]
\small
Óvalo = \textbf{{terminador}} (inicio/fin) $\cdot$
Rectángulo = \textbf{{proceso}} (acción determinista) $\cdot$
Rombo = \textbf{{decisión}} (ramas Sí/No) $\cdot$
Paralelogramo = \textbf{{entrada/salida}} (lectura/escritura de archivos) $\cdot$
Cilindro = \textbf{{almacenamiento online}} (estado, snapshots) $\cdot$
Rectángulo con base ondulada = \textbf{{documento}} (sesiones, logs) $\cdot$
Rectángulo punteado gris = \textbf{{nota explicativa}} (sin acción).
Flujo: arriba$\rightarrow$abajo, izquierda$\rightarrow$derecha.

\faIcon{{tags}}~Cada símbolo lleva una \textbf{{etiqueta}} (T/P/D/E/A/N + número, según su tipo);
su significado se expande en la tabla \emph{{Leyenda de etiquetas}} bajo cada diagrama.
\end{{tcolorbox}}
\end{{center}}

\vspace{{6pt}}

{cuerpo_secciones}

{notas_tex}

% ─────────────────────────────────────────────────────────────────────────────
\end{{document}}
"""


# ─── Main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generador determinista de diagramas de flujo ISO 5807."
    )
    parser.add_argument(
        "--descriptor", required=True,
        help="Ruta al descriptor JSON del diagrama."
    )
    parser.add_argument(
        "--output", default=None,
        help="Prefijo de salida sin extensión (default: .tmp/latex_build/<nombre>). "
             "Si se da, el PDF se copia a <output>.pdf."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Solo genera .tex sin compilar (útil para debug)."
    )
    args = parser.parse_args()

    # Leer descriptor
    desc_path = Path(args.descriptor)
    if not desc_path.is_file():
        print(json.dumps({"status": "error", "code": 1,
                          "message": f"Descriptor no encontrado: {desc_path}"}))
        return 1
    try:
        descriptor = json.loads(desc_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(json.dumps({"status": "error", "code": 1,
                          "message": f"JSON inválido: {e}"}))
        return 1

    # Validar
    try:
        _validar_descriptor(descriptor)
    except ValueError as e:
        print(json.dumps({"status": "error", "code": 1,
                          "message": f"Descriptor inválido: {e}"}))
        return 1

    # Generar .tex
    latex = _generar_doc_latex(descriptor)
    nombre = Path(args.descriptor).stem.replace("descriptor_", "").replace("_flujo", "")
    job_name = f"diagrama_flujo_{nombre}"
    tex_path = BUILD_DIR / f"{job_name}.tex"
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    tex_path.write_text(latex, encoding="utf-8")
    print(f"generar_diagrama_flujo: .tex generado → {tex_path}")

    if args.dry_run:
        print(json.dumps({"status": "ok", "dry_run": True, "tex": str(tex_path)}))
        return 0

    # Compilar
    from execution.compile_latex import compile_latex_code
    res = compile_latex_code(latex, job_name=job_name, output_dir=str(BUILD_DIR), clean=False)
    pdf_build = BUILD_DIR / f"{job_name}.pdf"
    log_build = BUILD_DIR / f"{job_name}.log"

    if not res.get("success"):
        print(json.dumps({
            "status": "error", "code": 2,
            "message": f"Compilación fallida: {res.get('error', 'desconocido')}",
        }))
        return 2

    # Verificar
    from execution.verificar_pdf import main as verificar_main
    sys.argv = [
        "verificar_pdf.py",
        "--pdf", str(pdf_build),
        "--log", str(log_build),
    ]
    try:
        verificar_main()
    except SystemExit:
        pass
    # Leer resultado del verificador (salida stdout ya se imprimió)

    # Copiar a destino final
    output_prefix = args.output
    if output_prefix:
        out_path = Path(output_prefix)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_final = out_path.with_suffix(".pdf")
        tex_final = out_path.with_suffix(".tex")
        shutil.copy2(pdf_build, pdf_final)
        shutil.copy2(tex_path, tex_final)
        print(f"generar_diagrama_flujo: publicado → {pdf_final}")

    print(json.dumps({
        "status": "ok",
        "tex": str(tex_path),
        "pdf": str(pdf_build if not output_prefix else Path(output_prefix + ".pdf")),
        "paginas": res.get("pages"),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
