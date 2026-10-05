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
  - \bandaTitulo[color]  : banda parametrizable (esquinas redondeadas, icono redefinible)
  - \cajaRecuerda/\cajaConcepto/\cajaEjemplo/\cajaEjercicio/\cajaReto : cajas temáticas
  - \facil/\intermedio/\dificil : indicadores de dificultad coloreados
  - estiloCodigo/estiloPython : listados de código dark-mode (listings + auto-wrap)
"""

# ── Paleta de colores — fuente única de verdad ───────────────────────────────────
# Se expone como dato de Python (no como \definecolor incrustado en el preámbulo)
# para que otros generadores —beamer, en particular, que no puede usar las macros
# de tcolorbox de este módulo— compartan exactamente los mismos colores sin copiar
# la tabla a mano. Dos paletas que divergen en silencio son la forma más cara de
# errar en un proyecto cuya tesis es el determinismo.
#
# clave -> (hex sin '#', comentario alineado)
PALETA: dict[str, tuple[str, str]] = {
    # Technological dark-mode
    "fondoOscuro": ("0D1B2A", "Dark navy — fondo banda título"),
    "verdeTurquesa": ("004D40", "Verde turquesa — bandas de marca"),
    "azulNoche": ("1B3A6B", "Midnight blue — secciones, marcos"),
    "azulMedio": ("2A5298", "Azul medio — variante de acento"),
    "cyanNeon": ("00C8E0", "Cyan eléctrico — acentos primarios"),
    "verdeSignal": ("00B887", "Verde señal — fortalezas, éxito"),
    "naranjaVivo": ("FF7043", "Naranja vivo — mejoras, advertencias"),
    "rojoAlerta": ("E53935", "Rojo alerta — errores"),
    "grisPapel": ("F4F6FA", "Fondo tarjetas claras"),
    "grisLinea": ("C8D0E0", "Bordes sutiles"),
    "grisTexto": ("6B7A99", "Texto secundario"),
    "amarilloNota": ("FFB300", "Notas / advertencias doradas"),
    # Code blocks (dark-mode)
    "codigoFondo": ("1E2D3D", "Fondo del bloque de código"),
    "codigoComentario": ("7A8FA6", "Comentarios"),
    "codigoCadena": ("FF9D5C", "Cadenas / strings"),
    "codigoKeyword": ("00C8E0", "Palabras clave"),
    "codigoNumero": ("00E5A0", "Números"),
}


def definir_colores(grupos: tuple[str, ...] | None = None) -> str:
    """Genera el bloque `\\definecolor` a partir de PALETA.

    `grupos` filtra por prefijo de clave (p. ej. ``("codigo",)``) para emitir
    solo un subconjunto; por defecto emite la paleta completa.
    """
    lineas = []
    for nombre, (hexval, comentario) in PALETA.items():
        if grupos is not None and not any(nombre.startswith(g) for g in grupos):
            continue
        lineas.append(
            f"\\definecolor{{{nombre}}}{{HTML}}{{{hexval}}}%".ljust(52)
            + f" {comentario}"
        )
    return "\n".join(lineas) + "\n"


# ── Preámbulo LaTeX compartido ─────────────────────────────────────────────────
# No incluye \begin{document}: el generador lo añade tras su cabecera específica.
# El bloque de colores NO está escrito aquí: se inyecta con `definir_colores()`
# para que la paleta tenga una sola definición en todo el workspace.
PREAMBULO_INFOGRAFIA = r"""\documentclass[11pt,a4paper]{article}

% ── Codificación, fuentes y lenguaje ───────────────────────────────────────────
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[default,scale=0.95]{sourcesanspro}
\renewcommand{\familydefault}{\sfdefault}
\usepackage[spanish,es-noshorthands,es-tabla]{babel}

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

% ── Listados de código (dark-mode infográfico) ────────────────────────────────
%   Estilo base: fondo oscuro con números de línea. Los bloques lstlisting se
%   envuelven automáticamente en una caja tcolorbox redondeada.
\usepackage{listings}

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
\titleformat{\subsubsection}
  {\normalfont\normalsize\bfseries\color{azulNoche}}
  {\textcolor{cyanNeon}{\thesubsubsection}}{0.7em}{}
\titlespacing*{\subsubsection}{0pt}{10pt}{4pt}

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
""" + definir_colores() + r"""
% ── Banda de título: portada infográfica ──────────────────────────────────────
%   Diseño en 2 capas: banda de color (por defecto fondo oscuro) + franja de
%   acento cyan abajo. Uso: \bandaTitulo[color]{título}{subtítulo}.
%   El icono se puede cambiar con \renewcommand{\iconoBanda}{...} (FontAwesome).
\newcommand{\iconoBanda}{microchip}
\newcommand{\bandaTitulo}[3][fondoOscuro]{%
  \begin{tcolorbox}[
    enhanced,
    colback=#1, colframe=#1,
    boxrule=0pt, arc=8pt, outer arc=8pt,
    width=\linewidth,
    top=18pt, bottom=6pt, left=14pt, right=14pt,
    borderline south={3.5pt}{0pt}{cyanNeon},
  ]
    \begin{minipage}[c]{0.07\linewidth}
      \centering
      \textcolor{cyanNeon}{\fontsize{30}{30}\selectfont\faIcon{\iconoBanda}}
    \end{minipage}%
    \hspace{8pt}%
    \begin{minipage}[c]{0.88\linewidth}
      {\fontsize{20}{24}\selectfont\bfseries\color{white}#2}\par\vspace{5pt}%
      \textcolor{cyanNeon!80!white}{\small\faIcon{angle-right}~#3}%
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

% ── Listados de código: estilo dark + auto-envoltura ─────────────────────────
\lstdefinestyle{estiloCodigo}{
    backgroundcolor=\color{codigoFondo},
    basicstyle=\ttfamily\small\color{white},
    commentstyle=\color{codigoComentario}\itshape,
    stringstyle=\color{codigoCadena},
    keywordstyle=\color{codigoKeyword}\bfseries,
    numberstyle=\tiny\color{codigoComentario},
    numbers=left,
    numbersep=10pt,
    showstringspaces=false,
    breaklines=true,
    breakatwhitespace=false,
    tabsize=4,
    frame=none,
    captionpos=b,
    aboveskip=6pt,
    belowskip=4pt,
    xleftmargin=14pt,
    framexleftmargin=14pt,
    literate=
      {á}{{\'a}}1 {é}{{\'e}}1 {í}{{\'i}}1 {ó}{{\'o}}1 {ú}{{\'u}}1
      {Á}{{\'A}}1 {É}{{\'E}}1 {Í}{{\'I}}1 {Ó}{{\'O}}1 {Ú}{{\'U}}1
      {ñ}{{\~n}}1 {Ñ}{{\~N}}1 {ü}{{\"u}}1 {Ü}{{\"U}}1
      {¿}{{?`}}1 {¡}{{!`}}1
}
\lstdefinestyle{estiloPython}{
    style=estiloCodigo,
    language=Python,
}
\lstset{style=estiloCodigo}
\BeforeBeginEnvironment{lstlisting}{%
  \begin{tcolorbox}[
    enhanced, breakable,
    arc=6pt, outer arc=6pt,
    colback=codigoFondo, colframe=azulNoche,
    boxrule=1pt,
    drop fuzzy shadow=azulNoche!25!white,
    top=2pt, bottom=2pt, left=0pt, right=0pt,
  ]%
}
\AfterEndEnvironment{lstlisting}{\end{tcolorbox}}

% ── Cajas de contenido temáticas ──────────────────────────────────────────────
\newtcolorbox{cajaRecuerda}{
    enhanced, breakable,
    arc=6pt, outer arc=6pt,
    colback=azulNoche!10!grisPapel,
    colframe=azulNoche, boxrule=1pt,
    borderline west={4pt}{0pt}{cyanNeon},
    fonttitle=\bfseries\small\color{white},
    title={\faIcon{info-circle}~Recuerda},
    attach boxed title to top left={yshift=-3mm, xshift=6mm},
    boxed title style={colback=azulNoche, arc=4pt, boxrule=0pt},
    drop fuzzy shadow=azulNoche!25!white,
    left=10pt, right=10pt, top=8pt, bottom=8pt,
}

\newtcolorbox{cajaConcepto}{
    enhanced, breakable,
    arc=6pt, outer arc=6pt,
    colback=verdeSignal!8!white,
    colframe=verdeSignal, boxrule=1pt,
    borderline west={4pt}{0pt}{verdeSignal},
    fonttitle=\bfseries\small\color{white},
    title={\faIcon{lightbulb}~Concepto clave},
    attach boxed title to top left={yshift=-3mm, xshift=6mm},
    boxed title style={colback=verdeSignal!80!black, arc=4pt, boxrule=0pt},
    drop fuzzy shadow=verdeSignal!20!white,
    left=10pt, right=10pt, top=8pt, bottom=8pt,
}

\newtcolorbox{cajaEjemplo}{
    enhanced, breakable,
    arc=6pt, outer arc=6pt,
    colback=cyanNeon!5!white,
    colframe=cyanNeon!70!azulNoche, boxrule=1pt,
    borderline west={4pt}{0pt}{cyanNeon},
    fonttitle=\bfseries\small\color{fondoOscuro},
    title={\faIcon{code}~Ejemplo},
    attach boxed title to top left={yshift=-3mm, xshift=6mm},
    boxed title style={colback=cyanNeon, arc=4pt, boxrule=0pt},
    drop fuzzy shadow=azulNoche!20!white,
    left=10pt, right=10pt, top=8pt, bottom=8pt,
}

\newtcolorbox{cajaEjercicio}{
    enhanced, breakable,
    arc=6pt, outer arc=6pt,
    colback=azulMedio!7!white,
    colframe=azulMedio, boxrule=1pt,
    borderline west={4pt}{0pt}{azulMedio},
    fonttitle=\bfseries\small\color{white},
    title={\faIcon{pencil-alt}~Ejercicio},
    attach boxed title to top left={yshift=-3mm, xshift=6mm},
    boxed title style={colback=azulMedio, arc=4pt, boxrule=0pt},
    drop fuzzy shadow=azulNoche!20!white,
    left=10pt, right=10pt, top=8pt, bottom=8pt,
}

\newtcolorbox{cajaReto}{
    enhanced, breakable,
    arc=6pt, outer arc=6pt,
    colback=naranjaVivo!6!white,
    colframe=naranjaVivo, boxrule=1pt,
    borderline west={4pt}{0pt}{naranjaVivo},
    fonttitle=\bfseries\small\color{white},
    title={\faIcon{fire}~Reto},
    attach boxed title to top left={yshift=-3mm, xshift=6mm},
    boxed title style={colback=naranjaVivo, arc=4pt, boxrule=0pt},
    drop fuzzy shadow=naranjaVivo!20!white,
    left=10pt, right=10pt, top=8pt, bottom=8pt,
}

% ── Indicadores de dificultad ─────────────────────────────────────────────────
\newcommand{\facil}{\textcolor{verdeSignal}{\faIcon{circle}\,\textbf{Fácil}}}
\newcommand{\intermedio}{\textcolor{naranjaVivo}{\faIcon{circle}\,\textbf{Intermedio}}}
\newcommand{\dificil}{\textcolor{rojoAlerta}{\faIcon{circle}\,\textbf{Difícil}}}

% ─────────────────────────────────────────────────────────────────────────────
"""


def banda_titulo(titulo: str, subtitulo: str, color: str = "fondoOscuro") -> str:
    """Apertura infográfica con banda de color, título y subtítulo.

    color: nombre de color xcolor que pinta el fondo de la banda
           (por defecto 'fondoOscuro'; ej. 'verdeTurquesa').
    """
    return rf"\bandaTitulo[{color}]{{{titulo}}}{{{subtitulo}}}"


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