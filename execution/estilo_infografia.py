#!/usr/bin/env python3
r"""
estilo_infografia.py — Estilo de infografía compartido para LaTeX (Layer 3: Execution)

Módulo determinista que provee el preámbulo y macros de estilo infográfico
(moderno: bandas de color, tarjetas de datos, iconos FontAwesome, secciones con
barra de color y fuente sans-serif) para TODOS los generadores LaTeX del workspace.

Los generadores importan PREAMBULO_INFOGRAFIA y lo concatenan a su cuerpo,
evitando duplicar preámbulos en cada script.

Elementos provistos:
  - PREAMBULO_INFOGRAFIA : preámbulo completo listo para \begin{document}
  - banda_titulo()       : Apertura con banda de color y subtítulo (portada infográfica)
  - seccion_con_icono()  : Sección con rótulo/icono (usa \section + icono FontAwesome)
"""

# ── Preámbulo LaTeX compartido ─────────────────────────────────────────────────
# No incluye \begin{document}: el generador lo añade tras su cabecera específica.
PREAMBULO_INFOGRAFIA = r"""\documentclass[11pt,a4paper]{article}

% ── Codificación, fuentes y lenguaje ───────────────────────────────────────────
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[default,scale=0.95]{sourcesanspro}
\renewcommand{\familydefault}{\sfdefault}
\usepackage[spanish,es-noshorthands]{babel}

% ── Geometría y espaciado ─────────────────────────────────────────────────────
\usepackage[top=2.2cm, bottom=2.2cm, left=2.2cm, right=2.2cm]{geometry}
\usepackage{setspace}
\setstretch{1.15}
\usepackage{parskip}

% ── Matemáticas y unidades ────────────────────────────────────────────────────
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{siunitx}

% ── Circuitos ─────────────────────────────────────────────────────────────────
\usepackage[european, straightvoltages]{circuitikz}

% ── Tablas ────────────────────────────────────────────────────────────────────
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{array}
\usepackage{longtable}
\usepackage{colortbl}
\usepackage{enumitem}

% ── Colores, cajas e iconos ───────────────────────────────────────────────────
\usepackage[dvipsnames]{xcolor}
\usepackage{tcolorbox}
\tcbuselibrary{skins, breakable}
\usepackage{fontawesome5}

% ── Secciones con barra de color (infografía) ───────────────────────────────
\usepackage{titlesec}
\titleformat{\section}
  {\normalfont\LARGE\bfseries\color{azulTitulo}}
  {\thesection}{1em}{}
  [\color{bandaAzul}\rule{\linewidth}{1.6pt}]
\titlespacing*{\section}{0pt}{22pt}{10pt}
\titleformat{\subsection}
  {\normalfont\large\bfseries\color{azulTitulo}}
  {\thesubsection}{1em}{}
\titlespacing*{\subsection}{0pt}{14pt}{6pt}

% ── Cabeceras y pies de página ────────────────────────────────────────────────
\usepackage{fancyhdr}
\usepackage{lastpage}
\pagestyle{fancy}
\fancyhf{}

% ── Hiperenlaces ──────────────────────────────────────────────────────────────
\usepackage[colorlinks=true, linkcolor=azulTitulo, urlcolor=azulTitulo]{hyperref}
\sloppy
\emergencystretch 3em

% ── Paleta de colores de la marca ─────────────────────────────────────────────
\definecolor{azulTitulo}{HTML}{1B2A6B}
\definecolor{bandaAzul}{HTML}{1F3A93}
\definecolor{azulClaro}{HTML}{2E5A9C}
\definecolor{cyanAcento}{HTML}{0E7C86}
\definecolor{naranjaAcento}{HTML}{E07B39}
\definecolor{verdeAcento}{HTML}{1A6B2F}
\definecolor{rojoAcento}{HTML}{C0392B}
\definecolor{grisFondo}{HTML}{F5F6FA}
\definecolor{grisBorde}{HTML}{C9CFE0}

% ── Tarjetas de datos (infografía) ────────────────────────────────────────────
\tcbset{
  tarjetaDato/.style={
    enhanced, breakable,
    colback=azulClaro!6, colframe=azulClaro,
    fonttitle=\bfseries, coltitle=white,
    attach boxed title to top left={yshift=-2mm, xshift=4mm},
    boxed title style={colback=azulClaro, sharp corners},
    top=6pt, bottom=6pt, left=8pt, right=8pt,
  },
  tarjetaIcono/.style={
    enhanced, breakable, sharp corners,
    colback=white, colframe=azulClaro, boxrule=0.8pt,
    fonttitle=\bfseries, coltitle=azulTitulo,
    top=4pt, bottom=4pt, left=8pt, right=8pt,
  },
  cajaTitulo/.style={enhanced, breakable,
    colback=azulTitulo!8, colframe=azulTitulo,
    fonttitle=\bfseries\large, coltitle=white,
    attach boxed title to top left={yshift=-2mm, xshift=4mm},
    boxed title style={colback=azulTitulo},
    top=6pt, bottom=6pt, left=8pt, right=8pt},
  cajaContenido/.style={enhanced, breakable,
    colback=grisFondo, colframe=grisBorde,
    fonttitle=\bfseries, coltitle=azulTitulo,
    top=4pt, bottom=4pt, left=8pt, right=8pt},
  cajaFortaleza/.style={enhanced, breakable,
    colback=verdeAcento!8, colframe=verdeAcento,
    fonttitle=\bfseries, coltitle=verdeAcento,
    top=4pt, bottom=4pt, left=8pt, right=8pt},
  cajaMejora/.style={enhanced, breakable,
    colback=naranjaAcento!8, colframe=naranjaAcento,
    fonttitle=\bfseries, coltitle=naranjaAcento,
    top=4pt, bottom=4pt, left=8pt, right=8pt},
  cajaRecomendacion/.style={enhanced, breakable,
    colback=grisFondo, colframe=grisBorde,
    fonttitle=\bfseries, coltitle=azulTitulo,
    top=4pt, bottom=4pt, left=8pt, right=8pt},
}

% ── Banda de título: apertura de documento tipo infografía ─────────────────────
\newcommand{\bandaTitulo}[2]{%
  \begin{tcolorbox}[enhanced, colback=bandaAzul, colframe=bandaAzul,
    boxrule=0pt, arc=0pt, outer arc=0pt, width=\linewidth,
    halign=center, valign=center,
    top=14pt, bottom=14pt, left=10pt, right=10pt]
    {\LARGE\bfseries\color{white}#1}\par\vspace{4pt}%
    {\small\color{white!78!black}#2}%
  \end{tcolorbox}\vspace{8pt}}

% ── Ícono + texto (encabezados de sección y elementos) ────────────────────────
\newcommand{\iconotexto}[2]{\textcolor{azulTitulo}{\faIcon{#1}}~#2}

% ─────────────────────────────────────────────────────────────────────────────
"""


def banda_titulo(titulo: str, subtitulo: str) -> str:
    """Apertura infográfica con banda de color, título y subtítulo."""
    return r"\bandaTitulo{" + titulo + "}{" + subtitulo + "}"


def seccion_con_icono(icono: str, texto: str) -> str:
    """Sección titulada con un icono FontAwesome delante."""
    nombre_icono = _sanitizar_icono(icono)
    return (
        r"\section{\iconotexto{" + nombre_icono + r"}{" + texto + r"}}"
    )


def _sanitizar_icono(icono: str) -> str:
    """Normaliza el nombre del icono FontAwesome (fa-xxx / xxx → xxx)."""
    icono = (icono or "").strip().lower()
    if icono.startswith("fa-"):
        icono = icono[3:]
    if icono.startswith("fa"):
        icono = icono[2:]
    return icono or "file-alt"


if __name__ == "__main__":
    print("Módulo de estilo infográfico (importar, no ejecutar).")
    print(f"Longitud del preámbulo: {len(PREAMBULO_INFOGRAFIA)} caracteres.")