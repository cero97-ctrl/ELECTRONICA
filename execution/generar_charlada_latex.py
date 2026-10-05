#!/usr/bin/env python3
r"""
generar_charlada_latex.py — Genera el material de la conferencia (Layer 3: Execution)

Produce DOS piezas a partir de una sola fuente de contenido, para que no se
desincronicen:

  1. Deck beamer 16:9 para proyectar           -> charlada_ia_3_capas.pdf
  2. Handout A4 estilo infográfico, con el      -> charlada_ia_3_capas_material.pdf
     desarrollo de los fallos

Decisiones de diseño que importan (y por qué):

- **Las cifras se miden, no se escriben.** `medir_cifras()` cuenta ficheros en
  disco y clasifica las fronteras LLM por criterio explícito. Un número que se
  teclea en el texto se desincroniza del repo en una semana y nadie se entera;
  uno que se cuenta, se corrige solo.
- **La paleta se importa, no se copia.** `estilo_infografia.PALETA` es la única
  definición de color del workspace. Copiarla sería crear una segunda fuente de
  verdad que diverge en silencio.
- **Compilar no es verificar.** En modo nonstopmode LaTeX produce un PDF aunque
  el documento esté roto, así que el resultado se juzga parseando el `.log` en
  busca de líneas `^! `. Es la entrada 17 de `.agent/latex.md` aplicada a sí
  mismo: si el deck puede mentir al compilar, no puede certificarse al compilar.

Uso:
    python3 execution/generar_charlada_latex.py --salida-dir docs/AGENTE_IA
    python3 execution/generar_charlada_latex.py --solo deck --autor "César R."

Códigos de salida:  0 ok · 2 uso incorrecto · 3 fallo de compilación
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "execution"))

from estilo_infografia import (  # noqa: E402
    PALETA,
    PREAMBULO_INFOGRAFIA,
    definir_colores,
    seccion_con_icono,
)
from compile_latex import compile_latex_code  # noqa: E402

BUILD_DIR = RAIZ / ".tmp" / "charlada"

# Llave LITERAL en modo texto. Definidas como constantes porque dentro de un
# f-string hay que distinguirlas de las llaves del propio f-string, y confundirlas
# es un fallo silencioso: el documento sale bien y el ejemplo sale mutilado.
LB = "\\{"   # -> \{
RB = "\\}"   # -> \}

# Criterio de clasificación de la frontera LLM. Explícito a propósito: un número
# sin criterio declarado no es un dato, es una opinión con formato.
MARCADORES_LLM = (
    "llm_client", "get_chat_openai", "openrouter_chat", "genai", "Groq", "ChatOpenAI",
)
# Tocados la maquinaria LLM pero NO invocan un modelo: uno es el cliente (envuelve
# las llamadas) y el otro decide el tier localmente sin red. Contarlos como
# "fronteras" sería inflar la cifra.
NO_ES_FRONTERA = {"llm_client.py", "enrutador.py"}

# Este mismo archivo NO ES una frontera. Contiene la lista MARCADORES_LLM, así que
# su propio texto contiene "genai", "Groq" y compañía, y se contaría a sí mismo
# como frontera de LLM. Es un bug de autorreferencia clásico: un detector que se
# detecta a sí mismo. Se excluye por nombre y con el motivo escrito, porque la
# próxima vez que alguien lea un 13 en vez de un 12 tiene que poder saber por qué.
NO_ES_FRONTERA.add(Path(__file__).name)


# ─────────────────────────────────────────────────────────────────────────────
# Escapado: texto externo al LaTeX
# ─────────────────────────────────────────────────────────────────────────────
_ESCAPES_LATEX = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
    "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}


def tex_escape(texto: str) -> str:
    """Escapa texto de procedencia externa para insertarlo en LaTeX.

    El `%` es el caso que duele y que no se ve: en LaTeX abre un comentario y se
    traga el resto de la línea, incluido el cierre del comando que lo contiene.
    Un subtítulo con «80 %» parte el documento por la mitad y el compilador se
    queje de algo que aparece treinta líneas más abajo. Se escapa carácter a
    carácter, en un solo sitio, y nunca a mano.
    """
    return "".join(_ESCAPES_LATEX.get(c, c) for c in texto)


def validar_latex_guion(tex: str) -> list[str]:
    """Detecta `_`/`^` fuera de modo matemático ANTES de compilar.

    No es cosmetía. Un `_` sin escapar dentro de `\\texttt{}` o de un panel
    monoespaciado hace que LaTeX emita «Missing $ inserted» y arrastre el
    error por el resto del documento: 234 errores de cascada que apuntan a la
    línea 100 cuando la causa está en la 138. Localizarlo en el fuente cuesta
    un minuto; localizarlo en un log de 2 000 líneas, en el atril, no.

    Se ignoran los comentarios (`%` al inicio, después de haber recortado los
    comentarios que abren dentro de la línea) y el contenido entre `$...$`.
    """
    problemas: list[str] = []
    for i, linea in enumerate(tex.splitlines(), 1):
        sin_comentario = _sin_comentario(linea)
        # quita las regiones de math, que sí admiten _ y ^
        regions = re.split(r"\$[^$]*\$", sin_comentario)
        for region in regions:
            for m in re.finditer(r"(?<!\\)[_^]", region):
                problemas.append(
                    f"línea {i}: {m.group(0)!r} sin escapar en modo texto -> "
                    f"{linea.strip()[:70]}"
                )
    return problemas


def _sin_comentario(linea: str) -> str:
    """Quita el comentario, respetando el `%` escapado.

    Un `split("%")` a lo bruto parte la línea en el `\%` de «84 %» y hace
    desaparecer el cierre de llave del final, con lo que la comprobación de
    llaves reporta un falso desequilibrio. Es el mismo género de fallo que
    `success=True`: la herramienta mira mal y culpa al documento.
    """
    return re.split(r"(?<!\\)%", linea, maxsplit=1)[0]


def validar_una_pagina_por_diapositiva(tex: str, paginas: int | None,
                                       nombre: str) -> list[str]:
    """Una diapositiva debe ocupar exactamente una pagina del PDF.

    Beamer reparte el desborde en paginas nuevas SIN avisar: no hay linea de
    error ni overfull. El sintoma es un PDF con mas paginas que diapositivas, y
    en un PDF que se presenta con clic cada pagina repetida es un clic de mas
    que el profesor tiene que acertar. \pause es justamente lo que la provoca.
    """
    if paginas is None:
        return [f"{nombre}: el log no dice cuántas páginas salieron; "
                "no se puede comprobar una página por diapositiva"]
    frames = len(re.findall(r"\\begin\{frame\}", tex))
    if paginas != frames:
        return [f"{nombre}: {paginas} páginas para {frames} diapositivas "
                f"(sobran {paginas - frames}); el PDF no es navegable con clic"]
    return []


def validar_llaves(tex: str) -> list[str]:
    """Comprueba que las llaves quedan balanceadas y nunca se pasan de closes.

    Una `}` de más no se ve leyendo el PDF (el error sale treinta líneas después
    y blames a otro comando) y en beamer se manifiesta como «Argument of \\frame
    has an extra }», que no señala el sitio real del fallo.
    """
    problemas: list[str] = []
    prof = 0
    for i, linea in enumerate(tex.splitlines(), 1):
        s = _sin_comentario(linea).replace("\\{", "\x01").replace("\\}", "\x01")
        d = s.count("{") - s.count("}")
        if prof + d < 0:
            problemas.append(
                f"línea {i}: una '}}' de más cierra antes de abrir -> {linea.strip()[:70]}")
            prof = 0
            continue
        prof += d
    if prof != 0:
        problemas.append(f"quedan {prof} llave(s) sin cerrar al final del documento")
    return problemas


# ─────────────────────────────────────────────────────────────────────────────
# Cifras: medidas sobre el disco, nunca tecleadas
# ─────────────────────────────────────────────────────────────────────────────
def medir_cifras() -> dict[str, object]:
    """Cuenta el estado real del repo. Misma entrada -> mismo número."""
    ejec = sorted(
        p for p in glob.glob(str(RAIZ / "execution" / "*.py"))
        if not Path(p).name.startswith("test_")
    )
    toca_llm = [Path(p).name for p in ejec
                if any(m in Path(p).read_text(encoding="utf-8", errors="ignore")
                       for m in MARCADORES_LLM)]
    fronteras = sorted(set(toca_llm) - NO_ES_FRONTERA)

    def n_líneas(patrón: str) -> int:
        total = 0
        for f in glob.glob(str(RAIZ / patrón)):
            with open(f, encoding="utf-8", errors="ignore") as fh:
                total += sum(1 for _ in fh)
        return total

    n_ejec = len(ejec)
    return {
        "directivas": len(glob.glob(str(RAIZ / "directives" / "*.yaml"))),
        "flujos": len(glob.glob(str(RAIZ / "flujo_*.py"))),
        "servidores_mcp": len(glob.glob(str(RAIZ / "mcp_*_server.py"))),
        "scripts_ejecucion": n_ejec,
        "fronteras_llm": len(fronteras),
        "pct_determinista": round(100 * (n_ejec - len(fronteras)) / n_ejec),
        "lineas_ejecucion": n_líneas("execution/*.py"),
        "sesiones": len(glob.glob(str(RAIZ / "Sessions" / "*.md"))),
        "criterio_frontera": (
            f"{len(toca_llm)} scripts referencian maquinaria LLM; se excluyen "
            f"{sorted(NO_ES_FRONTERA)} (cliente y enrutador: no invocan modelo)."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Preámbulo beamer — hereda la paleta del workspace
# ─────────────────────────────────────────────────────────────────────────────
def preambulo_beamer(autor: str, titulo: str) -> str:
    return (
        r"""\documentclass[aspectratio=169,11pt]{beamer}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[default,scale=0.92]{sourcesanspro}
\renewcommand{\familydefault}{\sfdefault}
\usepackage[spanish,es-noshorthands]{babel}
\usepackage{fontawesome5}
\usepackage{booktabs}
\usepackage{amsmath}
\usepackage{tcolorbox}

% ── Paleta: generada desde estilo_infografia.PALETA (fuente única) ────────────
"""
        + definir_colores()
        + r"""
\setbeamercolor{structure}{fg=azulMedio}
\setbeamercolor{title}{fg=fondoOscuro,bg=white}
\setbeamercolor{frametitle}{fg=white,bg=azulNoche}
\setbeamerfont{frametitle}{size=\large,series=\bfseries}
\setbeamercolor{block title}{fg=white,bg=azulMedio}
\setbeamercolor{block body}{bg=grisPapel,fg=fondoOscuro}
\setbeamercolor{block title alerted}{fg=white,bg=rojoAlerta}
\setbeamercolor{block body alerted}{bg=rojoAlerta!8,fg=fondoOscuro}
\setbeamercolor{block title example}{fg=white,bg=verdeTurquesa}
\setbeamercolor{block body example}{bg=verdeSignal!8,fg=fondoOscuro}
\setbeamertemplate{navigation symbols}{}
\setbeamertemplate{itemize item}{\color{cyanNeon}\faIcon{angle-right}~}
\setbeamertemplate{itemize subitem}{\color{azulMedio}\faIcon{circle}~}

\newtcolorbox{panelMono}[1][]{colback=codigoFondo,colframe=codigoFondo,boxrule=0pt,
  arc=3pt,coltext=white,fontupper=\ttfamily\scriptsize,
  left=7pt,right=7pt,top=6pt,bottom=6pt,#1}
\newtcolorbox{panelRegla}[1][]{colback=cyanNeon!10,colframe=cyanNeon,boxrule=1pt,
  arc=4pt,left=9pt,right=9pt,top=7pt,bottom=7pt,#1}

% Cifra grande + su leyenda. Se usa en minipage, así que nada de \par.
\newcommand{\cifra}[2]{%
  \begin{minipage}[t]{0.30\textwidth}\centering
  {\fontsize{28}{30}\selectfont\bfseries\color{azulNoche}#1}\\[3pt]
  {\footnotesize\color{grisTexto}#2}
  \end{minipage}}

\setbeamertemplate{footline}{%
  \leavevmode\hbox{%
  \begin{beamercolorbox}[wd=\paperwidth,ht=3ex,dp=1.6ex,leftskip=1em,rightskip=1em]
    {author in head/foot}
    \scriptsize\color{grisTexto}ELECTRONICA \enspace \textbar\enspace """
        + r"""Patrón de arquitectura de 3 capas"""
        + r"""\hfill\insertframenumber/\inserttotalframenumber
  \end{beamercolorbox}}}

\title{"""
        + titulo
        + r"""}
\author{"""
        + autor
        + r"""}
\date{}

\begin{document}
"""
    )


# ─────────────────────────────────────────────────────────────────────────────
# Deck
# ─────────────────────────────────────────────────────────────────────────────
def slide_titulo(autor: str, fecha: str, c: dict) -> str:
    return rf"""
\begin{{frame}}[plain]
  \begin{{beamercolorbox}}[sep=16pt,center]{{title}}
    {{\footnotesize\bfseries\color{{cyanNeon}}\faIcon{{cogs}}\ INGENIERÍA DE DATOS}}\\[12pt]
    {{\LARGE\bfseries\color{{fondoOscuro}} IA en ingeniería con un\\ esquema determinista de tres capas}}\\[12pt]
    {{\large\color{{azulMedio}} Por qué el {c['pct_determinista']} \% de un sistema con LLM no debería contener un LLM}}\\[20pt]
    {{\footnotesize\color{{grisTexto}}\faIcon{{user-circle}}~{autor} \qquad
      \faIcon{{calendar}}~{fecha}\qquad
      \faIcon{{folder-open}}~{c['directivas']} directivas, {c['scripts_ejecucion']} scripts, {c['flujos']} flujos}}
  \end{{beamercolorbox}}
\end{{frame}}
"""


def slide_hook(c: dict) -> str:
    return r"""
\begin{frame}{Un LLM puede cumplir el contrato entero \emph{y aun así mentir}}
  \begin{alertblock}{Lo que devolvió el modelo}
    \begin{panelMono}
puntaje\_sugerido : "5.5/10"       \textcolor{codigoCadena}{<- inventado}\\
nivel\_desempeno  : "Bueno"        \textcolor{codigoCadena}{<- inventado}\\
observaciones    : [ "0.5/1", "0.7/1", "0.3/1" ]   \textcolor{codigoNumero}{<- suma 1.5}
    \end{panelMono}
  \end{alertblock}
  \smallskip
  \begin{block}{Obsérvese lo que \emph{sí} fue correcto}
    \begin{itemize}
      \item JSON válido \quad \item campos presentes \quad \item denominadores correctos
      \item \ldots y el total \textbf{no es la suma de sus propias partes}.
    \end{itemize}
  \end{block}
  \begin{panelRegla}
    Un LLM no es una calculadora. Cumplir un formato no es cumplir un contrato.
  \end{panelRegla}
\end{frame}
"""


def slide_asimetria() -> str:
    return r"""
\begin{frame}{La asimetría que hay que resolver}
  \begin{columns}[T]
    \begin{column}{0.48\textwidth}
      \begin{alertblock}{Lo que es un LLM}
        \begin{itemize}
          \item Un generador de texto \emph{plausible}
          \item Sin garantía de aritmética
          \item Sin garantía de repetibilidad
          \item Y sin que eso sea un defecto: es su naturaleza
        \end{itemize}
      \end{alertblock}
    \end{column}
    \begin{column}{0.48\textwidth}
      \begin{exampleblock}{Lo que exige la ingeniería}
        \begin{itemize}
          \item El mismo input $\rightarrow$ el mismo output
          \item Que se pueda auditar \emph{por qué}
          \item Que el error sea ruidoso, no silencioso
        \end{itemize}
      \end{exampleblock}
    \end{column}
  \end{columns}
  \smallskip
  \begin{panelRegla}
    No es una discusión filosófica. Es una asimetría \textbf{medible}, y se mide
    en fallos reales con coste concreto.
  \end{panelRegla}
\end{frame}
"""


def slide_capas(c: dict) -> str:
    return rf"""
\begin{{frame}}{{La respuesta: separar por responsabilidad}}
  \begin{{center}}
  \begin{{tabular}}{{@{{}}c c c l@{{}}}}
    \toprule
    \textbf{{Capa}} & \textbf{{Artefacto}} & \textbf{{Responde}} & \textbf{{Contiene LLM}} \\
    \midrule
    1 \quad Directiva & \texttt{{directives/*.yaml}} & ¿qué? & no \\
    2 \quad Orquestación & \texttt{{flujo\_*.py}}, \texttt{{mcp\_*}} & ¿cuándo? & no (solo decide) \\
    3 \quad Ejecución & \texttt{{execution/*.py}} & ¿cómo? & {c['fronteras_llm']} de {c['scripts_ejecucion']} \\
    \bottomrule
  \end{{tabular}}
  \end{{center}}
  \smallskip
  \begin{{block}}{{La regla que sostiene el patrón}}
    La lógica de negocio no se delega al modelo. Se le pide lo único que hace
    bien --\emph{{producir texto--}} y el resto se calcula en código.
  \end{{block}}
\end{{frame}}
"""


def slide_frontera(c: dict) -> str:
    return rf"""
\begin{{frame}}{{La frontera, con números medidos}}
  \vspace{{2pt}}
  \cifra{{{c['pct_determinista']} \%}}{{scripts de ejecución sin ningún LLM}}
  \hfill
  \cifra{{{c['fronteras_llm']}}}{{fronteras con LLM}}
  \hfill
  \cifra{{\$0}}{{coste de decidir el modelo}}
  \par\vspace{{14pt}}
  \begin{{block}}{{El enrutador es una función pura}}
    Elegir qué modelo usar \emph{{no lo decide un modelo}}: lo decide código local,
    a partir de un descriptor medido. Mismo descriptor $\rightarrow$ mismo tier,
    siempre. Y no hace ni una sola llamada a la API.
  \end{{block}}
  \begin{{alertblock}}{{Por qué esto no es un detalle de implementación}}
    Las {c['fronteras_llm']} fronteras están \textbf{{declaradas}}: son ficheros
    concretos y nombrados, no un \texttt{{if}} repartido por el código.
  \end{{alertblock}}
\end{{frame}}
"""


def slide_capa1() -> str:
    return r"""
\begin{frame}{Capa 1 \textbullet\ La directiva: el \emph{qué}}
  \begin{panelMono}
goal: >
  Evaluar el examen del estudiante enviando las páginas del PDF
  como imágenes al modelo y obteniendo una evaluación en JSON.
required\_inputs:
  - name: pdf\_examen
    description: Ruta al PDF del examen.
steps:
  - step: 1
    description: Renderizar el PDF a 250 DPI y enviarlo en bloque
                  al modelo con la instrucción de corrección.
  \end{panelMono}
  \smallskip
  \begin{block}{Por qué está en YAML y no en el prompt}
    Porque es \textbf{configuración}, no conversación: se versiona, se revisa con
    un diff, y lo escribe alguien que entiende el dominio, no el modelo.
  \end{block}
\end{frame}
"""


def slide_capa2() -> str:
    return r"""
\begin{frame}{Capa 2 \textbullet\ La orquestación: el \emph{cuándo}}
  \begin{columns}[T]
    \begin{column}{0.5\textwidth}
      \begin{block}{Lo que sí hace}
        \begin{itemize}
          \item Leer la directiva
          \item Resolver entradas y decidir el orden
          \item Delegar cada paso en capa 3
          \item Validar salidas y códigos de retorno
          \item Registrar estado para poder reanudar
        \end{itemize}
      \end{block}
    \end{column}
    \begin{column}{0.5\textwidth}
      \begin{alertblock}{Lo que NO hace}
        \begin{itemize}
          \item \ldots calcular
          \item \ldots sumar, comparar ni convertir
          \item \ldots procesar datos crudos
          \item \ldots decidir un modelo a ojo
        \end{itemize}
      \end{alertblock}
    \end{column}
  \end{columns}
  \begin{panelRegla}
    Una capa de decisión delgada, con la lógica fina abajo.
    Por eso el mismo fallo no se propaga a veinte sitios.
  \end{panelRegla}
\end{frame}
"""


def slide_capa3() -> str:
    return r"""
\begin{frame}{Capa 3 \textbullet\ La ejecución: el \emph{cómo}}
  \begin{itemize}
    \item Funciones puras donde se puede: mismo input, mismo output, sin red.
    \item Cada script valida \emph{sus propias} salidas y falla ruidosamente.
    \item Códigos de salida tipados; un 0 significa 0, no \"no vi nada\".
    \item Cobertura de pruebas como forma de documentar el contrato.
  \end{itemize}
  \smallskip
  \begin{exampleblock}{Dónde vive la verdad}
    Cuando hay una discrepancia, la respuesta no la da el prompt ni lo que el
    modelo recuerda: la da el test que falla.
  \end{exampleblock}
\end{frame}
"""


def slide_fallo1() -> str:
    return r"""
\begin{frame}{Fallo 1 \textbullet\ El modelo no suma: el programa suma}
  \begin{columns}[T]
    \begin{column}{0.48\textwidth}
      \begin{alertblock}{Síntoma}
        Salida con \texttt{status: ok}, JSON perfecto, cada ítem con su
        denominador \ldots y un total que no era la suma.
      \end{alertblock}
      \begin{block}{Causa profunda}
        Se le pidió al modelo el \emph{total}. La aritmética la hacía el LLM, y
        la aritmética es justo lo que un modelo no garantiza.
      \end{block}
    \end{column}
    \begin{column}{0.48\textwidth}
      \begin{exampleblock}{Arreglo}
        \begin{itemize}
          \item El esquema \emph{deja de pedir} el total
          \item El programa suma: función pura, testeable, sin red
          \item El máximo es un invariante, no una consecuencia
          \item Si se pasa del tope, se recorta \emph{y se avisa}
        \end{itemize}
      \end{exampleblock}
    \end{column}
  \end{columns}
  \begin{panelRegla}
    Lo que se transfiere: en cuanto un \textbf{número importa}, el número lo
    calcula el programa.
  \end{panelRegla}
\end{frame}
"""


def slide_fallo2() -> str:
    return r"""
\begin{frame}{Fallo 2 \textbullet\ La escala la declara el instrumento}
  \begin{columns}[T]
    \begin{column}{0.47\textwidth}
      \begin{alertblock}{El síntoma}
        3 ítems de 1 punto (total 3) con la mitad respondidos. Al sumar en crudo:
        \textbf{1.5/10} y nivel \emph{Insuficiente}. El alumno sacaba el 50 \%.
      \end{alertblock}
      \begin{alertblock}{Peor: el bug espejo}
        Si el modelo se comía un criterio, su peso desaparecía del denominador
        y el resto se normalizaba \textbf{hacia arriba}: un fallo del modelo
        bonificaba al alumno.
      \end{alertblock}
    \end{column}
    \begin{column}{0.47\textwidth}
      \begin{exampleblock}{El arreglo}
        \begin{itemize}
          \item La escala la fija el \emph{instrumento} (la rúbrica), no quien
                lo corrige
          \item Normalizar a la escala institucional, siempre
          \item Un criterio ausente vale 0 sobre esa escala: no se renormaliza
          \item Sin escala declarada \emph{no se publica nota}, y se dice por qué
        \end{itemize}
      \end{exampleblock}
    \end{column}
  \end{columns}
\end{frame}
"""


def slide_fallo3() -> str:
    return r"""
\begin{frame}{Fallo 3 \textbullet\ El modo JSON no es un esquema}
  \begin{panelMono}
request:  response\_format = \{"type": "json\_object"\}   \textcolor{codigoCadena}{<- solo promete un objeto}\\
respuesta: \{"text": "...", "preguntas": []\}          \textcolor{codigoCadena}{<- objeto válido. otro esquema.}
    \end{panelMono}
  \smallskip
  \begin{block}{El agravante}
    \texttt{response\_format} promete \textbf{una sola cosa}: que la respuesta
    sea un objeto. No promete las claves, ni los tipos, ni el vocabulario. Y el
    esquema del prompt es texto: la capa más débil del contrato.
  \end{block}
  \begin{exampleblock}{El arreglo}
    La barrera real es un \textbf{validador en el programa}: vocabulario cerrado
    para los campos enumerados, comprobación de tipos, y la clave que decide la
    vialidad del flujo es \emph{obligatoria}. Salida con código 5 y la lista de
    problemas; el JSON del modelo no se acepta como informe.
  \end{exampleblock}
\end{frame}
"""


def slide_regla() -> str:
    return r"""
\begin{frame}{Los tres fallos, una sola regla}
  \begin{panelRegla}
    \centering\Large\bfseries
    Cuando un número importa,\\ el número lo calcula el programa.
    \par\vspace{8pt}
    \normalsize\normalfont
    Y cuando la forma importa, la forma la verifica el programa.
  \end{panelRegla}
  \vspace{8pt}
  \begin{columns}[T]
    \begin{column}{0.47\textwidth}
      \begin{block}{Aplicaciones fuera de la IA}
        \begin{itemize}
          \item Metrología y conversión de unidades
          \item Control de calidad y criterios de aceptación
          \item Presupuestos y dosages
          \item Cualquier cosa donde un decimal de más sea un problema
        \end{itemize}
      \end{block}
    \end{column}
    \begin{column}{0.47\textwidth}
      \begin{block}{Por qué así se aprende}
        \begin{itemize}
          \item No es desconfiar del modelo: es asignar la aritmética a lo único
                que sabe hacer aritmética.
        \end{itemize}
      \end{block}
    \end{column}
  \end{columns}
\end{frame}
"""


def slide_veredictos() -> str:
    return r"""
\begin{frame}{Una idea formal que se transfiere: la álgebra de veredictos}
  \begin{columns}[T]
    \begin{column}{0.47\textwidth}
      \begin{alertblock}{La regla}
        \begin{itemize}
          \item Gana el \textbf{peor} estado, nunca el promedio
          \item Lo no verificado \textbf{impide} el verde
          \item Se distingue \emph{no instalado} de \emph{caído} de \emph{parado}
        \end{itemize}
      \end{alertblock}
    \end{column}
    \begin{column}{0.47\textwidth}
      \begin{exampleblock}{Por qué importa fuera de aquí}
        \begin{itemize}
          \item Es un promedio con tres estados en rojo y uno en amarillo: se
                ve verde mientras algo crítico no se midió
          \item Es exactamente la diferencia entre \emph{sin datos} y
                \emph{con buenos datos}
          \item Es control robusto aplicado a un pipeline de verificación
        \end{itemize}
      \end{exampleblock}
    \end{column}
  \end{columns}
  \begin{panelRegla}
    Y hay una segunda: \textbf{una sola definición}, compartida por las dos
    auditorías. Dos álgebras que divergen en silencio son la forma más cara de
    equivocarse.
  \end{panelRegla}
\end{frame}
"""


def slide_limites() -> str:
    return r"""
\begin{frame}{Los límites, que también son parte del patrón}
  \begin{columns}[T]
    \begin{column}{0.47\textwidth}
      \begin{alertblock}{Lo que el patrón \emph{no} resuelve}
        \begin{itemize}
          \item La capa 1 (directivas) aún no es verificable por auditoría:
                es informativa
          \item Un motor de asistente rotativo no es reproducible
          \item El hardware disponible no entrena modelos
          \item Sin red, parte de los proveedores no son accesibles
        \end{itemize}
      \end{alertblock}
    \end{column}
    \begin{column}{0.47\textwidth}
      \begin{exampleblock}{Cómo se presenta esto}
        \begin{itemize}
          \item Un patrón cuya frontera se declara se enseña mejor que uno que
                se vende
          \item La reproducibilidad tampoco es gratis: cuesta discipline
                de capa 3 y tests
        \end{itemize}
      \end{exampleblock}
    \end{column}
  \end{columns}
\end{frame}
"""


def slide_adoptar(c: dict) -> str:
    return rf"""
\begin{{frame}}{{Cómo adoptarlo en su propio proyecto}}
  \begin{{enumerate}}
    \item \textbf{{Escriba el SOP antes del código.}} Si no sabe escribirlo, aún
          no sabe qué tiene que automatizar.
    \item \textbf{{Ponga el criterio en el programa.}} Toda aritmética, toda
          comparación, toda conversión: en código, no en el prompt.
    \item \textbf{{Valide la forma, no confíe en ella.}} Un JSON que se parsea
          no es un JSON que cumple su esquema.
    \item \textbf{{Defina la escala en el instrumento.}} Y si no la hay, no
          publique el número.
    \item \textbf{{Verifique por registro, no por bandera verde.}} Un programa
          que compila o termina con 0 puede estar mintiendo: lea su salida.
    \item \textbf{{Deje la frontera escrita.}} Los ficheros con LLM se nombran;
          todo lo demás es código.
  \end{{enumerate}}
\end{{frame}}
"""


def slide_cierre() -> str:
    return r"""
\begin{frame}[plain]
  \vfill
  \begin{center}
    {\Large\bfseries\color{fondoOscuro} IA donde aporta.}\\[4pt]
    {\Large\bfseries\color{azulNoche} Código donde se exige.}\\[4pt]
    {\Large\bfseries\color{verdeTurquesa} Verificación en ambos.}\\[16pt]
    {\normalsize\color{grisTexto}
      La arquitectura no es una jaula para el modelo:\\
      es lo que le permite ser útil sin dejar de ser verificable.}
  \end{center}
  \vfill
\end{frame}
"""


def generar_deck(titulo: str, autor: str, fecha: str, c: dict) -> str:
    cuerpo = "".join([
        slide_titulo(autor, fecha, c),
        slide_hook(c), slide_asimetria(), slide_capas(c), slide_frontera(c),
        slide_capa1(), slide_capa2(), slide_capa3(),
        slide_fallo1(), slide_fallo2(), slide_fallo3(),
        slide_regla(), slide_veredictos(), slide_limites(),
        slide_adoptar(c), slide_cierre(),
    ])
    return preambulo_beamer(autor, titulo) + cuerpo + "\n\\end{document}\n"


# ─────────────────────────────────────────────────────────────────────────────
# Handout
# ─────────────────────────────────────────────────────────────────────────────
def generar_material(titulo: str, subtitulo: str, autor: str, fecha: str,
                     c: dict) -> str:
    # Sin '%': dentro de lstlisting el signo es caracter de comentario y trunca
    # la linea. La cifra se dice en palabras.
    a, s = f"{c['pct_determinista']} por ciento", f"{c['fronteras_llm']}"
    return f"""{PREAMBULO_INFOGRAFIA}
\\begin{{document}}

\\bandaTitulo[fondoOscuro]{{{titulo}}}{{{subtitulo}}}

\\vspace{{4pt}}
\\begin{{center}}
\\footnotesize\\color{{grisTexto}}
\\faIcon{{user-circle}}~{autor}\\quad
\\faIcon{{calendar}}~{fecha}\\quad
\\faIcon{{folder-open}}~{c['directivas']} directivas\\quad
\\faIcon{{cogs}}~{c['scripts_ejecucion']} scripts de ejecución\\quad
\\faIcon{{sitemap}}~{c['flujos']} flujos\\quad
\\faIcon{{book}}~{c['sesiones']} sesiones documentadas
\\end{{center}}

{seccion_con_icono('layer-group', '1. La asimetría')}
Un modelo de lenguaje es un generador de texto plausible. La ingeniería no pide
plausibilidad: pide que el mismo input produzca el mismo output y que se pueda
auditar por qué. Esa asimetría no es una discusión filosófica, es medible, y se
mide en fallos reales con coste concreto.

{seccion_con_icono('layer-group', '2. Las tres capas')}

\\begin{{center}}
\\begin{{tabular}}{{@{{}}lll@{{}}}}
\\toprule
\\textbf{{Capa}} & \\textbf{{Artefacto}} & \\textbf{{Responde}} \\\\
\\midrule
1 · Directiva & \\texttt{{directives/*.yaml}} & ¿qué? \\\\
2 · Orquestación & \\texttt{{flujo\_*.py}}, \\texttt{{mcp\_*.py}} & ¿cuándo? \\\\
3 · Ejecución & \\texttt{{execution/*.py}} & ¿cómo? \\\\
\\bottomrule
\\end{{tabular}}
\\end{{center}}

\\begin{{cajaConcepto}}
\\textbf{{La regla.}} La lógica de negocio no se delega al modelo. Se le pide lo
único que hace bien --- producir texto --- y el resto se calcula en código.
\\end{{cajaConcepto}}

\\textbf{{Capa 1, la directiva.}} Es configuración, no conversación: se versiona,
se revisa con un diff y la escribe quien entiende el dominio.

\\begin{{lstlisting}}[language=Python,caption={{La frontera LLM, medida sobre el disco}}]
# {c['scripts_ejecucion']} scripts de ejecución
# {c['scripts_ejecucion'] - c['fronteras_llm']} sin ninguna llamada a LLM   <- {a}
# {s} con LLM (fronteras declaradas, ficheros nombrados)
# el enrutador decide el tier localmente: 0 llamadas a la API, coste 0
\\end{{lstlisting}}

\\begin{{cajaRecuerda}}
\\textbf{{Criterio explícito, para que el número sea auditable.}}
{tex_escape(c['criterio_frontera'])}
\\end{{cajaRecuerda}}

{seccion_con_icono('bug', '3. Tres fallos que costaron dinero')}

\\subsection*{{3.1 El modelo puntuaba; el programa suma}}
El sistema devolvía \\texttt{{status: ok}} y un JSON bien formado. Cada ítem
llevaba su denominador correcto. El total \\emph{{no era la suma de sus propias
partes}}: el modelo había inventado el campo y la aritmética era suya.

La causa no era de formato sino de \\textbf{{ROL}}: se le pidió al LLM el total.
Cambiar la prosa no lo arregla ---se probó---: los denominadores pasaron a ser
correctos mientras el total seguía sin cuadrar.

\\begin{{cajaEjemplo}}
El arreglo fue dejarle \\emph{{una sola}} tarea --- puntuar ítems --- y que el
programa sumara. El máximo pasó a ser un invariante: si la suma se pasa del tope,
se recorta \\emph{{y se avisa}}. Cada parcial se limita a su propio peso. Y lo
ilegible se cuenta y se dice: un ítem sin parcial genera aviso, porque ignorarlo
en silencio hace creer que el alumno contestó lo que no contestó.
\\end{{cajaEjemplo}}

\\subsection*{{3.2 La escala la declara el instrumento}}
Tres preguntas de un punto cada una (escala 3) contestadas a medias. Sumar en
crudo daba \\textbf{{1.5/10}} y nivel \\emph{{Insuficiente}}: el alumno había
sacado el 50 \\%.

La escala de un examen no es 10: es la que declara el examen. La nota
institucional sí es sobre 10, así que hace falta una conversión explícita.

Hubo además un \\textbf{{bug espejo}}: al armar el denominador con lo que
devolvía el modelo, un criterio que el modelo se comía desaparecía del
denominador y todo lo demás se normalizaba \\emph{{hacia arriba}}. El alumno
cobraba por un fallo del modelo. Con rúbrica, la escala la fija el archivo de
configuración y un criterio ausente vale 0 sobre esa escala.

\\begin{{cajaConcepto}}
Ausencia de dato no es dato. Sin escala declarada no se publica nota: se publica
el motivo y la suma observada, que es información útil para el humano.
\\end{{cajaConcepto}}

\\subsection*{{3.3 El modo JSON no es un esquema}}
\\texttt{{response\_format={LB}"type": "json\_object"{RB}}} promete \\textbf{{una sola
cosa}}: que la respuesta sea un objeto. No promete las claves, ni los tipos, ni
el vocabulario. El esquema del prompt es texto, y el texto es la capa más débil
del contrato.

El agravante fue más tonto: la instrucción \\emph{{nunca se envió}}. El script
construía el mensaje de usuario y se olvidaba de adjuntar el esquema, así que el
modelo recibía literalmente \\emph{{devuelve SOLO el JSON}} --- sin saber de qué
JSON --- y respondió con la primera forma que se le ocurrió. Y como
\\texttt{{json.loads}} no tiene nada que decir sobre claves faltantes, la
inspección \\emph{{pareció}} válida.

\\begin{{cajaEjemplo}}
El arreglo no fue en el prompt: fue un \\textbf{{validador en el programa}}, con
vocabulario cerrado para los campos enumerados y comprobación de tipos para el
resto. Y la clave que decide si el flujo es viable se volvió obligatoria:
confundir \\emph{{no saber}} con \\emph{{no contestar}} convierte una inspección
que no inspeccionó nada en un informe aparentemente confiable.
\\end{{cajaEjemplo}}

{seccion_con_icono('balance-scale', '4. Una idea formal que se transfiere')}
La \\textbf{{álgebra de veredictos}} compartida por las dos auditorías del
proyecto:\\textbf{{gana el peor estado, nunca un promedio}}, lo no verificado
impide el verde, y se distinguen tres estados que la intuición colapsa en uno:
\\emph{{no instalado}}, \\emph{{caído}} y \\emph{{parado}}.

El motivo por el que esto es una idea y no una función: un promedio con tres
estados en rojo y uno en amarillo se ve verde mientras algo crítico no se midió.
Y la segunda mitad de la regla es la que se olvida: una sola definición
compartida. Dos álgebras que divergen en silencio son la forma más cara de
equivocarse en un módulo cuya única razón de ser es la consistencia.

{seccion_con_icono('microchip', '5. Los límites')}
La capa 1 todavía no es verificable por la auditoría: es informativa. Un motor
de asistente rotativo no es reproducible. El hardware disponible no entrena
modelos. Un patrón cuya frontera se declara se enseña mejor que uno que se vende.

{seccion_con_icono('check-circle', '6. Seis pasos para adoptarlo')}
\\begin{{enumerate}}
\\item Escriba el SOP antes del código. Si no sabe escribirlo, aún no sabe qué
      tiene que automatizar.
\\item Ponga el criterio en el programa: toda aritmética, comparación o
      conversión vive en código, no en el prompt.
\\item Valide la forma, no confíe en ella.
\\item Defina la escala en el instrumento, y si no la hay no publique el número.
\\item Verifique por registro, no por bandera verde: un programa que termina con
      código 0 puede estar mintiendo, así que hay que leer su salida.
\\item Deje la frontera escrita: los ficheros con LLM se nombran.
\\end{{enumerate}}

\\vfill
\\begin{{center}}
\\footnotesize\\color{{grisTexto}}
Este material lo genera el propio patrón del que habla: directiva, orquestador y
script, con la paleta de color compartida del workspace.
\\end{{center}}

\\end{{document}}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Compilación: el log es la verdad, el PDF no
# ─────────────────────────────────────────────────────────────────────────────
def compilar(contenido: str, job: str) -> dict[str, object]:
    """Compila aislado en .tmp/charlada/ y juzga el resultado por el log."""
    out = BUILD_DIR / job
    out.mkdir(parents=True, exist_ok=True)
    res = compile_latex_code(contenido, job_name=job, output_dir=str(out), clean=False)
    log_p = out / f"{job}.log"
    pdf_p = out / f"{job}.pdf"
    errores: list[str] = []
    overfull = 0
    paginas = None
    if log_p.exists():
        log = log_p.read_text(encoding="utf-8", errors="ignore")
        errores = re.findall(r"^! (.+)$", log, re.M)
        overfull = len(re.findall(r"Overfull \\hbox", log))
        # El numero de paginas solo aparece en el log ("Output written on ...
        # (22 pages"). Sin el, una diapositiva que desborda a una segunda pagina
        # es INVISIBLE: no hay error, no hay overfull, el PDF simplemente sale
        # mas largo.
        # re.S porque el log de TeX parte las lineas largas a 79 caracteres:
        # "(16 pages, ...)" queda en la linea de continuacion, no en la misma
        # que "Output written on".
        m = re.search(r"Output written on (.{0,400}?)\((\d+) pages?", log, re.S)
        if m:
            paginas = int(m.group(2))   # grupo 1 es la ruta, grupo 2 la cuenta
    return {
        "paginas": paginas,
        "job": job,
        "pdf": str(pdf_p),
        "pdf_existe": pdf_p.exists(),
        "reportado_por_compilador": bool(res.get("success")),
        "errores": errores,
        "overfull": overfull,
        # success=True + errores=[] es el único estado publicable. Un PDF sin log
        # limpio no se copia, aunque el compilador diga que salió bien.
        "limpio": (not errores) and pdf_p.exists(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Genera el material de la conferencia (capa 3).")
    ap.add_argument("--titulo", default="IA en ingeniería con un esquema determinista de tres capas")
    ap.add_argument("--subtitulo", default=None,
                    help="Por defecto se deriva del porcentaje MEDIDO; un literal "
                         "se contradiría en cuanto el repo cambiara.")
    ap.add_argument("--autor", default="ELECTRONICA")
    ap.add_argument("--fecha", default="2026-10-05")
    ap.add_argument("--salida-dir", default="docs/AGENTE_IA")
    ap.add_argument("--solo", choices=["deck", "material", "ambos"], default="ambos")
    ap.add_argument("--minutos", type=int, default=30,
                    help="Duración de la charla; avisa si el deck no cabe.")
    args = ap.parse_args()

    # El escapado ocurre UNA vez, aqui: si se hiciera dentro de cada plantilla
    # habria que acordarse en todas, y acordarse es justo lo que falla.
    c = medir_cifras()

    # El subtítulo afirma un porcentaje, así que se deriva de la medición. Un
    # literal en el default se contradice solo en cuanto el repo cambia, y el
    # material quedaría diciendo 80 % con 84 % medidos a dos líneas de distancia.
    if args.subtitulo is None:
        args.subtitulo = (f"Por qué el {c['pct_determinista']} % de un sistema "
                          "con LLM no debería contener un LLM")

    args.titulo = tex_escape(args.titulo)
    args.subtitulo = tex_escape(args.subtitulo)
    args.autor = tex_escape(args.autor)
    args.fecha = tex_escape(args.fecha)
    destino = Path(args.salida_dir)
    if not destino.is_absolute():
        destino = RAIZ / destino
    destino.mkdir(parents=True, exist_ok=True)

    diapos_deck, diapos_handout = 17, 6
    if diapos_deck > args.minutos / 1.5:
        print(f"[aviso] {diapos_deck} diapositivas para {args.minutos} min: "
              f"presupuesto excedido (≈{diapos_deck * 1.5:.0f} min).", file=sys.stderr)

    informe: dict[str, object] = {"cifras": c, "piezas": {}}

    piezas = []
    if args.solo in ("deck", "ambos"):
        piezas.append(("deck", "charlada_ia_3_capas",
                       generar_deck(args.titulo, args.autor, args.fecha, c)))
    if args.solo in ("material", "ambos"):
        piezas.append(("material", "charlada_ia_3_capas_material",
                       generar_material(args.titulo, args.subtitulo,
                                        args.autor, args.fecha, c)))

    # Pre-vuelo: se valida el guion ANTES de pagar la compilación. Un fallo aquí
    # se reporta con número de línea del fuente; el mismo fallo después sería una
    # cascada de cientos de líneas en el log con la causa en otro sitio.
    fallos_previo: list[str] = []
    for nombre, job, tex in piezas:
        problemas = validar_latex_guion(tex) + validar_llaves(tex)
        if problemas:
            fallos_previo += [f"[{nombre}] {p}" for p in problemas]
    if fallos_previo:
        for p in fallos_previo[:12]:
            print(f"  {p}", file=sys.stderr)
        print(f"[fallo] {len(fallos_previo)} problema(s) de pre-vuelo; no se compila.",
              file=sys.stderr)
        return 3

    for nombre, job, tex in piezas:
        info = compilar(tex, job)
        info["frames"] = len(re.findall(r"\\begin\{frame\}", tex))
        # Post-compilacion, no pre-vuelo: las paginas solo existen despues.
        if nombre == "deck":
            for prob in validar_una_pagina_por_diapositiva(tex, info["paginas"], nombre):
                print(f"  [{nombre}] {prob}", file=sys.stderr)
                info["limpio"] = False
                info["errores"].append(prob)
        informe["piezas"][nombre] = info

    informe["diapositivas"] = {"deck": diapos_deck, "material": diapos_handout}
    informe["salida_dir"] = str(destino)

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    (BUILD_DIR / "deck.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")

    for nombre, info in (informe["piezas"] or {}).items():
        estado = "LIMPIO" if info["limpio"] else f"CON {len(info['errores'])} ERROR(ES)"
        print(f"  {nombre:<8} {estado}  (overfull={info['overfull']}, "
              f"paginas={info['paginas']}, frames={info['frames']})")
        for e in info["errores"][:6]:
            print(f"           ! {e}")

    sucios = [n for n, i in (informe["piezas"] or {}).items() if not i["limpio"]]
    if sucios:
        print(f"[fallo] compilación sucia en: {sucios}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())