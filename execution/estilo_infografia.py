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
\usepackage[top=2.2cm, bottom=2.5cm, left=2.2cm, right=2.2cm, headheight=15pt]{geometry}
\usepackage{setspace}
\setstretch{1.18}
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
\usepackage{graphicx}

% ── Secciones con barra de color (infografía) ────────────────────────────────
\usepackage{titlesec}
\titleformat{\section}
  {\normalfont\LARGE\bfseries\color{azulNoche}}
  {\colorbox{cyanNeon}{\color{fondoOscuro}\thesection}}{0.7em}{}
  [\vspace{2pt}\color{cyanNeon}\rule{\linewidth}{1.8pt}]
\titlespacing*{\section}{0pt}{24pt}{10pt}
\titleformat{\subsection}
  {\normalfont\large\bfseries\color{azulNoche}}
  {\textcolor{cyanNeon}{\thesubsection}}{0.7em}{}
  [\vspace{1pt}\color{grisLinea}\rule{\linewidth}{0.6pt}]
\titlespacing*{\subsection}{0pt}{14pt}{6pt}

% ── Cabeceras y pies de página ────────────────────────────────────────────────
\usepackage{fancyhdr}
\usepackage{lastpage}
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}
\fancyfoot[C]{%
  \begin{minipage}{\linewidth}
    \vspace{2pt}
    \color{cyanNeon}\rule{\linewidth}{1.2pt}\\[2pt]
    \centering\color{grisTexto}\footnotesize
    Página \thepage\ de \pageref{LastPage}
  \end{minipage}%
}

% ── Hiperenlaces ──────────────────────────────────────────────────────────────
\usepackage[colorlinks=true, linkcolor=azulNoche, urlcolor=cyanNeon]{hyperref}
\sloppy
\emergencystretch 3em

% ── Paleta de colores — tecnológico dark-mode ──────────────────────────────────
\definecolor{fondoOscuro}{HTML}{0D1B2A}     % Dark navy — fondo banda título
\definecolor{azulNoche}{HTML}{1B3A6B}       % Midnight blue — secciones, marcos
\definecolor{azulMedio}{HTML}{2A5298}       % Azul medio — variante de acento
\definecolor{cyanNeon}{HTML}{00C8E0}        % Cyan eléctrico — acentos primarios
\definecolor{verdeSignal}{HTML}{00B887}     % Verde señal — fortalezas, éxito
\definecolor{naranjaVivo}{HTML}{FF7043}     % Naranja vivo — mejoras, advertencias
\definecolor{rojoAlerta}{HTML}{E53935}      % Rojo alerta — errores
\definecolor{grisPapel}{HTML}{F4F6FA}       % Fondo tarjetas claras
\definecolor{grisLinea}{HTML}{C8D0E0}       % Bordes sutiles
\definecolor{grisTexto}{HTML}{6B7A99}       % Texto secundario
\definecolor{amarilloNota}{HTML}{FFB300}    % Notas / advertencias doradas

% ── Banda de título: portada infográfica ──────────────────────────────────────
%   Diseño en 2 capas: fondo oscuro + franja de acento cyan abajo
\newcommand{\bandaTitulo}[2]{%
  \begin{tcolorbox}[
    enhanced, sharp corners,
    colback=fondoOscuro, colframe=fondoOscuro,
    boxrule=0pt, arc=0pt, outer arc=0pt,
    width=\linewidth,
    top=18pt, bottom=6pt, left=14pt, right=14pt,
    borderline south={3.5pt}{0pt}{cyanNeon},
  ]
    \begin{minipage}[c]{0.07\linewidth}
      \centering
      \textcolor{cyanNeon}{\fontsize{30}{30}\selectfont\faIcon{microchip}}
    \end{minipage}%
    \hspace{8pt}%
    \begin{minipage}[c]{0.88\linewidth}
      {\fontsize{20}{24}\selectfont\bfseries\color{white}#1}\par\vspace{5pt}%
      \textcolor{cyanNeon!80!white}{\small\faIcon{angle-right}~#2}%
    \end{minipage}
    \vspace{4pt}
  \end{tcolorbox}%
  \vspace{8pt}%
}

% ── Tarjetas de datos (infografía) ────────────────────────────────────────────
\tcbset{
  tarjetaDato/.style={
    enhanced, breakable,
    arc=6pt, outer arc=6pt,
    colback=grisPapel, colframe=azulNoche,
    boxrule=1pt,
    fonttitle=\bfseries\small, coltitle=white,
    attach boxed title to top left={yshift=-3mm, xshift=6mm},
    boxed title style={
      colback=azulNoche, colframe=azulNoche,
      arc=4pt, boxrule=0pt,
    },
    drop fuzzy shadow=azulNoche!30!white,
    top=8pt, bottom=8pt, left=10pt, right=10pt,
  },
  tarjetaIcono/.style={
    enhanced, breakable,
    arc=6pt, outer arc=6pt,
    colback=white, colframe=grisLinea, boxrule=0.8pt,
    fonttitle=\bfseries\small, coltitle=azulNoche,
    borderline west={3pt}{0pt}{cyanNeon},
    drop fuzzy shadow=azulNoche!25!white,
    top=6pt, bottom=6pt, left=10pt, right=10pt,
  },
  cajaTitulo/.style={
    enhanced, breakable,
    arc=6pt, outer arc=6pt,
    colback=azulNoche!10!grisPapel, colframe=azulNoche,
    boxrule=1pt,
    fonttitle=\bfseries, coltitle=white,
    attach boxed title to top left={yshift=-3mm, xshift=6mm},
    boxed title style={
      colback=azulNoche, colframe=azulNoche,
      arc=4pt, boxrule=0pt,
    },
    drop fuzzy shadow=azulNoche!25!white,
    top=8pt, bottom=8pt, left=10pt, right=10pt,
  },
  cajaContenido/.style={
    enhanced, breakable,
    arc=5pt, outer arc=5pt,
    colback=grisPapel, colframe=grisLinea,
    boxrule=0.8pt,
    fonttitle=\bfseries\small, coltitle=azulNoche,
    top=6pt, bottom=6pt, left=10pt, right=10pt,
  },
  cajaFortaleza/.style={
    enhanced, breakable,
    arc=6pt, outer arc=6pt,
    colback=verdeSignal!8!white, colframe=verdeSignal,
    boxrule=1pt,
    borderline west={4pt}{0pt}{verdeSignal},
    fonttitle=\bfseries\small, coltitle=verdeSignal!70!black,
    drop fuzzy shadow=verdeSignal!20!white,
    top=6pt, bottom=6pt, left=10pt, right=10pt,
  },
  cajaMejora/.style={
    enhanced, breakable,
    arc=6pt, outer arc=6pt,
    colback=naranjaVivo!8!white, colframe=naranjaVivo,
    boxrule=1pt,
    borderline west={4pt}{0pt}{naranjaVivo},
    fonttitle=\bfseries\small, coltitle=naranjaVivo!80!black,
    drop fuzzy shadow=naranjaVivo!20!white,
    top=6pt, bottom=6pt, left=10pt, right=10pt,
  },
  cajaRecomendacion/.style={
    enhanced, breakable,
    arc=6pt, outer arc=6pt,
    colback=cyanNeon!6!white, colframe=cyanNeon!60!azulNoche,
    boxrule=1pt,
    borderline west={4pt}{0pt}{cyanNeon},
    fonttitle=\bfseries\small, coltitle=azulNoche,
    drop fuzzy shadow=azulNoche!20!white,
    top=6pt, bottom=6pt, left=10pt, right=10pt,
  },
}

% ── Ícono + texto (encabezados de sección y elementos) ────────────────────────
\newcommand{\iconotexto}[2]{\textcolor{cyanNeon}{\faIcon{#1}}~#2}

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