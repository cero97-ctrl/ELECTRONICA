#!/usr/bin/env python3
r"""
generar_doc_scratch.py — Genera la guía infográfica de Scratch en docs/scratch/

Determinista. Importa PREAMBULO_INFOGRAFIA (estilo compartido, sin duplicar
preámbulos) y concatena el cuerpo específico. Produce docs/scratch/scratch.tex
y compila el PDF con pdflatex (2 pasadas) en el mismo directorio.
"""

import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from execution.estilo_infografia import PREAMBULO_INFOGRAFIA  # noqa: E402

OUT_DIR = os.path.join(PROJECT_ROOT, "docs", "scratch")
JOB = "scratch"

# ── Icono de banda y caja de consejos específicos de este documento ───────────
DOC_SPECIFICS = r"""
\renewcommand{\iconoBanda}{cat}

% ── Caja de consejos ─────────────────────────────────────────────────────────
\newtcolorbox{cajaTips}{
    enhanced, breakable,
    arc=6pt, outer arc=6pt,
    colback=amarilloNota!6!white,
    colframe=amarilloNota, boxrule=1pt,
    borderline west={4pt}{0pt}{amarilloNota},
    fonttitle=\bfseries\small\color{fondoOscuro},
    title={\faIcon{lightbulb}~Consejos para enseñar},
    attach boxed title to top left={yshift=-3mm, xshift=6mm},
    boxed title style={colback=amarilloNota, arc=4pt, boxrule=0pt},
    drop fuzzy shadow=amarilloNota!20!white,
    left=10pt, right=10pt, top=8pt, bottom=8pt,
}
"""

BODY = r"""
\begin{document}

% ══════════════════════════════════════════════════════════════════════════════
% PORTADA — Banda de título
% ══════════════════════════════════════════════════════════════════════════════
\bandaTituloScratch

\begin{center}
{\large\textcolor{grisTexto}{
  Guía completa para empezar a programar en \textbf{\textcolor{azulNoche}{Scratch}}
  con una adolescente de 14 años en \textbf{\textcolor{azulNoche}{GNU/Linux Mint}}.}}
\end{center}

% ══════════════════════════════════════════════════════════════════════════════
\section{\iconotexto{puzzle-piece}{¿Qué es Scratch?}}

\textbf{Scratch} es un lenguaje de programación \textbf{visual} desarrollado por el
\textbf{MIT Media Lab} (dirigido por Mitchel Resnick). En lugar de escribir código
textual, los programas se construyen encajando \textbf{bloques visuales} como piezas
de un rompecabezas.

\begin{cajaConcepto}
\textbf{Programar en Scratch es encajar bloques.} Cada bloque representa una
instrucción (mover, sonar, repetir, decidir). Te enseñan la \textbf{lógica de
programación} sin la barrera de la sintaxis, ideal para aprender pensamiento
computacional y creatividad digital.
\end{cajaConcepto}

Principales capacidades:
\begin{itemize}
  \item Crear \textbf{juegos}, animaciones e historias interactivas.
  \item Incorporar \textbf{sonidos}, \textbf{sprites} (personajes) y fondos personalizados.
  \item \textbf{Comunidad online} para compartir proyectos (como GitHub, pero para Scratch).
  \item Extensible con extensiones: \texttt{micro:bit}, Makey Makey, LEGO, etc.
\end{itemize}

Uso recomendado:
\begin{itemize}
  \item Enseñar \textbf{lógica y estructura de programación} sin sintaxis.
  \item Prototipos rápidos de interacción y animación.
  \item Educación STEM en escuelas y aprendizaje en casa.
\end{itemize}

% ══════════════════════════════════════════════════════════════════════════════
\section{\iconotexto{layer-group}{Versiones y plataformas}}

\begin{center}
\begin{tabularx}{\linewidth}{l l X}
\toprule
\textbf{Versión} & \textbf{Público} & \textbf{Plataformas} \\
\midrule
\textbf{ScratchJr}   & Niños 5--7 años        & Tablets (iOS, Android, Chromebook) \\
\textbf{Scratch 3.0} & 8--16+ años            & Navegador web, Windows, macOS, \textbf{Linux} \\
\bottomrule
\end{tabularx}
\end{center}

Nota: la \textbf{aplicación de escritorio} para GNU/Linux es \textbf{Scratch
Desktop}. También está disponible \textbf{Scratch 4.x} en versión de escritorio.

% ══════════════════════════════════════════════════════════════════════════════
\section{\iconotexto{wrench}{Instalación en GNU/Linux Mint}}

Opciones disponibles (ya instalada en nuestro equipo):

\begin{center}
\begin{tabularx}{\linewidth}{l X X}
\toprule
\textbf{Método} & \textbf{Ventaja} & \textbf{Desventaja} \\
\midrule
\textbf{AppImage} & Portátil, no modifica el sistema, funciona siempre &
Tan solo hay que descargarlo manualmente \\
\textbf{Flatpak}  & Se integra con el Gestor de Software de Mint &
Descarga algo pesada (runtime \SI{300}{\mega\byte}) \\
\textbf{Scratch online} & Sin instalar nada, listo para usar &
Requiere conexión y un navegador (Firefox/Chromium) \\
\bottomrule
\end{tabularx}
\end{center}

\begin{tcolorbox}[cajaRecomendacion, title={\faIcon{thumbs-up}~Recomendación: AppImage}]
Es el método más limpio para GNU/Linux Mint: no
depende de Snap (problemático en Mint) ni de Flatpak. Pasos rápidos:
\begin{enumerate}
  \item Descargar desde \url{https://scratch.mit.edu/download}.
  \item Darle permisos de ejecución con \texttt{chmod +x Scratch-*.AppImage}.
  \item Ejecutarlo con doble clic o desde terminal con `./Scratch-*.AppImage`.
\end{enumerate}
\end{tcolorbox}

% ══════════════════════════════════════════════════════════════════════════════
\section{\iconotexto{gamepad}{Plan de aprendizaje por fases}}

\subsection{Fase 1: Familiarización (semanas 1--2)}

\begin{center}
\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\linewidth}{l X c}
\toprule
\textbf{Proyecto} & \textbf{Qué aprende} & \textbf{Dificultad} \\
\midrule
Hola Mundo            & Bloques de movimiento, apariencia y sonido       & \facil \\
Animación básica      & Secuencias, bucles \texttt{repeat}, \texttt{esperar} & \facil \\
El gato bailarín      & Bucle \texttt{forever}, eventos al hacer clic en la bandera verde & \facil \\
\bottomrule
\end{tabularx}
\end{center}

\subsection{Fase 2: Interactividad (semanas 3--4)}

\begin{center}
\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\linewidth}{l X c}
\toprule
\textbf{Proyecto} & \textbf{Qué aprende} & \textbf{Dificultad} \\
\midrule
Pong clásico          & Teclado, colisiones, variables (puntos)          & \intermedio \\
Historia interactiva  & Condicionales \texttt{si/si-no}, diálogos         & \intermedio \\
Quiz / Trivia         & Lógica, comparaciones y retroalimentación         & \intermedio \\
\bottomrule
\end{tabularx}
\end{center}

\subsection{Fase 3: Juegos (semanas 5--8)}

\begin{center}
\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\linewidth}{l X c}
\toprule
\textbf{Proyecto} & \textbf{Qué aprende} & \textbf{Dificultad} \\
\midrule
Laberinto saltarín       & Detección de bordes, coordenadas X/Y             & \dificil \\
Plataformas              & Física básica, gravedad y clonación              & \dificil \\
Space Invaders           & Clonación masiva y dificultad progresiva         & \dificil \\
\bottomrule
\end{tabularx}
\end{center}

% ══════════════════════════════════════════════════════════════════════════════
\section{\iconotexto{book}{Recursos recomendados}}

\subsection{Scratch 3 Programming Playground — libro gratuito online}

\textbf{Al Sweigart} (No Starch Press). Gratis para leer en línea bajo licencia
Creative Commons, con proyectos completos y progresivos:
\url{https://inventwithscratch.com/book3}.

\begin{center}
\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\linewidth}{c X}
\toprule
\textbf{Capítulo} & \textbf{Proyecto / contenido} \\
\midrule
0 & Introducción y conceptos básicos \\
1 & Primeros pasos: interfaz, movimiento y eventos \\
2 & Líneas Arcoíris: bucles, colores y lápiz \\
3 & \textbf{Laberinto}: colisiones, coordenadas y condiciones \\
4 & \textbf{Baloncesto con gravedad}: física, variables y teclado \\
5 & \textbf{Brick Breaker pulido}: clonación, puntuación y niveles \\
6 & \textbf{Asteroides en el espacio}: enemigos múltiples y dificultad \\
7 & \textbf{Plataformas avanzado}: gravedad, saltos y \textit{scrolling} \\
\bottomrule
\end{tabularx}
\end{center}

\begin{itemize}
  \item Incluye \textbf{descargables} de sprites y fondos:
        \url{https://inventwithscratch.com/ScratchPlayground3_resources.zip}.
  \item Ejercicios al final de cada capítulo con retos de personalización.
  \item Proyectos en orden creciente de dificultad, ideales para 14 años.
\end{itemize}

\subsection{Curso gratuito en Udemy}

\textit{Scratch Game Programming}, también de \textbf{Al Sweigart}, sigue los
primeros 6 proyectos del libro: \url{https://www.udemy.com/scratch-game-programming/}.

\subsection{Manual para padres y profesores}

\textit{Scratch Class Handbook} (PDF gratuito, actualizado oct 2020):
\url{https://inventwithscratch.com/Scratch_Class_Handbook_v3.pdf}.
Contiene estrategias para conducir la sesión, tiempos y evaluación.

\subsection{Tutoriales oficiales de Scratch}

\begin{itemize}
  \item Tutoriales paso a paso: \url{https://scratch.mit.edu/tutorials}.
  \item Proyectos de la comunidad para inspirarse: \url{https://scratch.mit.edu/explore}.
  \item Información para padres: \url{https://scratch.mit.edu/parents}.
\end{itemize}

% ══════════════════════════════════════════════════════════════════════════════
\section{\iconotexto{calendar-alt}{Plan de estudio detallado (8 semanas)}}

\subsection{Semanas 1--2: Fundamentos}

\begin{center}
\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\linewidth}{c l X}
\toprule
\textbf{Día} & \textbf{Actividad (30 min)} & \textbf{Referencia} \\
\midrule
L & Interfaz de Scratch y crear cuenta        & Capítulo 1 \\
M & Primer sprite: movimiento con teclado     & Capítulo 1 \\
X & Añadir sonido y fondo                     & Capítulo 1 \\
J & Proyecto: ``Mi primer dibujo'' (lápiz)    & Capítulo 2 \\
V & Líneas arcoíris                           & Capítulo 2 \\
\bottomrule
\end{tabularx}
\end{center}

\subsection{Semana 3: Condicionales}

\begin{center}
\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\linewidth}{c l X}
\toprule
\textbf{Día} & \textbf{Actividad} & \textbf{Referencia} \\
\midrule
L & Colisiones básicas              & Capítulo 3 \\
M & Laberinto (parte 1: movimiento) & Capítulo 3 \\
X & Laberinto (parte 2: paredes)    & Capítulo 3 \\
J & Laberinto (parte 3: meta)       & Capítulo 3 \\
V & Personalizar el laberinto       & Capítulo 3 \\
\bottomrule
\end{tabularx}
\end{center}

\subsection{Semana 4: Variables y puntuación}

\begin{center}
\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\linewidth}{c l X}
\toprule
\textbf{Día} & \textbf{Actividad} & \textbf{Referencia} \\
\midrule
L & Concepto de variables              & Capítulo 4 \\
M & Baloncesto (parte 1: la pelota)    & Capítulo 4 \\
X & Baloncesto (parte 2: la canasta)   & Capítulo 4 \\
J & Baloncesto (parte 3: gravedad)     & Capítulo 4 \\
V & Baloncesto (parte 4: puntuación)   & Capítulo 4 \\
\bottomrule
\end{tabularx}
\end{center}

\subsection{Semana 5: Clonación}

\begin{center}
\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\linewidth}{c l X}
\toprule
\textbf{Día} & \textbf{Actividad} & \textbf{Referencia} \\
\midrule
L & Concepto de clones                  & Capítulo 5 \\
M & Brick Breaker (parte 1: la pelota)  & Capítulo 5 \\
X & Brick Breaker (parte 2: ladrillos)  & Capítulo 5 \\
J & Brick Breaker (parte 3: niveles)    & Capítulo 5 \\
V & Brick Breaker (parte 4: pulir)      & Capítulo 5 \\
\bottomrule
\end{tabularx}
\end{center}

\subsection{Semanas 6--7: Juegos avanzados}

\begin{center}
\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\linewidth}{l l X}
\toprule
\textbf{Semana} & \textbf{Proyecto} & \textbf{Referencia} \\
\midrule
6 & Asteroides en el espacio     & Capítulo 6 \\
7 & Plataformas saltarinas       & Capítulo 7 \\
\bottomrule
\end{tabularx}
\end{center}

\subsection{Semana 8: Proyecto libre}

\begin{center}
\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\linewidth}{X X}
\toprule
\textbf{Actividad} \\
\midrule
La alumna elige un juego o animación que le guste y lo completa \\
Se publica en la comunidad Scratch (\url{https://scratch.mit.edu}) \\
\bottomrule
\end{tabularx}
\end{center}

% ══════════════════════════════════════════════════════════════════════════════
\section{\iconotexto{youtube}{Canales de YouTube en español}}

\begin{center}
\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\linewidth}{l X}
\toprule
\textbf{Canal} & \textbf{Tipo de contenido} \\
\midrule
Scratch en Español            & Tutoriales paso a paso desde cero \\
Programación para Niños       & Juegos y animaciones guiados \\
CodeaKids                     & Proyectos creativos y lúdicos \\
Profesor Sheldon              & Cursos completos en español \\
\bottomrule
\end{tabularx}
\end{center}

% ══════════════════════════════════════════════════════════════════════════════
\section{\iconotexto{lightbulb}{Consejos para enseñar (14 años)}}

\begin{cajaTips}
\begin{enumerate}
  \item \textbf{Empieza con proyectos que ella elija}: ¿juegos, animaciones, música?
  \item No intentes ``enseñar programación'' directamente: deja que ella descubra
        cómo lograr lo que quiere.
  \item Sesiones de \textbf{30--45 minutos} máximo; la atención se pierde rápido.
  \item Usa proyectos de la comunidad como \textbf{punto de partida} (fork).
  \item \textbf{Celebra cada logro}: el primer sprite que se mueve es motivador.
  \item Alterna práctica y teoría corta: 10 minutos de concepto, 20 de construir.
\end{enumerate}
\end{cajaTips}

% ══════════════════════════════════════════════════════════════════════════════
\section{\iconotexto{clipboard-check}{Lista de verificación para empezar}}

\begin{center}
\renewcommand{\arraystretch}{1.3}
\begin{tabularx}{\linewidth}{l X}
\toprule
\textbf{Estado} & \textbf{Paso} \\
\midrule
\faCheckSquare & Scratch instalado en GNU/Linux Mint \\
$\square$      & Crear cuenta en \url{https://scratch.mit.edu} (guardar proyectos) \\
$\square$      & Abrir el libro gratuito: \url{https://inventwithscratch.com/book3} \\
$\square$      & Descargar recursos: \url{https://inventwithscratch.com/ScratchPlayground3_resources.zip} \\
$\square$      & Empezar el Capítulo 1 \\
\bottomrule
\end{tabularx}
\end{center}

% ══════════════════════════════════════════════════════════════════════════════
\section*{\iconotexto{link}{Referencias}}
\addcontentsline{toc}{section}{Referencias}

\begin{itemize}
  \item Scratch (sitio oficial): \url{https://scratch.mit.edu}
  \item Invent with Scratch (Al Sweigart): \url{https://inventwithscratch.com}
  \item Scratch 3 Programming Playground (libro online): \url{https://inventwithscratch.com/book3}
  \item Curso Audiovisual en Udemy: \url{https://www.udemy.com/scratch-game-programming/}
  \item Scratch Class Handbook (PDF): \url{https://inventwithscratch.com/Scratch_Class_Handbook_v3.pdf}
\end{itemize}

\end{document}
"""


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    tex = PREAMBULO_INFOGRAFIA + DOC_SPECIFICS + r"""
% ── Banda de título personalizada para Scratch ───────────────────────────────
\newcommand{\bandaTituloScratch}{%
  \bandaTitulo[verdeTurquesa]{Scratch}{Programa. Juega. Aprende.}%
}
""" + BODY

    tex_path = os.path.join(OUT_DIR, f"{JOB}.tex")
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex)

    cmd = [
        "pdflatex",
        "-interaction=nonstopmode",
        f"-jobname={JOB}",
        f"-output-directory={OUT_DIR}",
        tex_path,
    ]
    for _ in range(2):
        subprocess.run(cmd, check=False)

    pdf_path = os.path.join(OUT_DIR, f"{JOB}.pdf")
    log_path = os.path.join(OUT_DIR, f"{JOB}.log")
    if not os.path.exists(pdf_path):
        sys.exit("FALLO compilación — revisa el log")

    errors = []
    if os.path.exists(log_path):
        errors = [ln for ln in open(log_path, errors="ignore") if ln.startswith("!")]
    if errors:
        print("AVISO errores en log:")
        print("".join(errors[:5]))
        sys.exit(1)

    # Limpiar artefactos auxiliares (convención: solo el .tex y .pdf quedan)
    for ext in (".aux", ".log", ".out"):
        aux = os.path.join(OUT_DIR, JOB + ext)
        if os.path.exists(aux):
            os.remove(aux)

    print(f"OK  PDF: {pdf_path}")
    sys.exit(0)


if __name__ == "__main__":
    main()