#!/usr/bin/env python3
r"""
generar_latex_orquestador_repo_skill.py — Documento infográfico sobre la utilidad
del orquestador flujo_repo_a_skill.py (Layer 3: Execution, determinista, 0 créditos).

Importa PREAMBULO_INFOGRAFIA desde estilo_infografia.py (nunca duplica el preámbulo)
y concatena la cabecera específica antes de \begin{document}.

Uso:
    python3 execution/generar_latex_orquestador_repo_skill.py [--salida docs/AGENTE_IA/orquestador_repo_a_skill.tex] [--no-compilar]
"""

import argparse
import os
import subprocess
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from estilo_infografia import PREAMBULO_INFOGRAFIA

DOC_SPECIFIC = r"""
% ── Cabecera específica del documento ─────────────────────────────────────────
\renewcommand{\iconoBanda}{cogs}
\fancyhead[L]{\textcolor{grisTexto}{\footnotesize\faIcon{cogs}~El Orquestador \texttt{flujo\_repo\_a\_skill.py} --- Utilidad y Diseño}}
\fancyhead[R]{\textcolor{grisTexto}{\footnotesize\faIcon{calendar-alt}~Septiembre 2026}}

% ── Estilo bash (no incluido en el preámbulo compartido) ─────────────────────
\lstdefinestyle{estiloBash}{
    style=estiloCodigo,
    language=bash,
}

% ── Caja de alerta (no incluida en el preámbulo compartido) ──────────────────
\newtcolorbox{cajaAlerta}{
    enhanced, breakable,
    arc=6pt, outer arc=6pt,
    colback=naranjaVivo!8!white,
    colframe=naranjaVivo, boxrule=1pt,
    borderline west={4pt}{0pt}{naranjaVivo},
    fonttitle=\bfseries\small\color{white},
    title={\faIcon{exclamation-triangle}~Punto crítico de diseño},
    attach boxed title to top left={yshift=-3mm, xshift=6mm},
    boxed title style={colback=naranjaVivo, arc=4pt, boxrule=0pt},
    drop fuzzy shadow=naranjaVivo!20!white,
    left=10pt, right=10pt, top=8pt, bottom=8pt,
}

% ── Caja de fortaleza (no incluida en el preámbulo compartido) ───────────────
\newtcolorbox{cajaFortaleza}{
    enhanced, breakable,
    arc=6pt, outer arc=6pt,
    colback=verdeSignal!8!white,
    colframe=verdeSignal, boxrule=1pt,
    borderline west={4pt}{0pt}{verdeSignal},
    fonttitle=\bfseries\small\color{white},
    title={\faIcon{shield-alt}~Fortaleza de diseño},
    attach boxed title to top left={yshift=-3mm, xshift=6mm},
    boxed title style={colback=verdeSignal!80!black, arc=4pt, boxrule=0pt},
    drop fuzzy shadow=verdeSignal!20!white,
    left=10pt, right=10pt, top=8pt, bottom=8pt,
}
"""

BODY = r"""
\bandaTitulo[fondoOscuro]{El Orquestador \texttt{flujo\_repo\_a\_skill.py}: Utilidad y Diseño}
{Capítulo 3 de la Fase 1b \quad|\quad Repositorio $\to$ Skill de Referencia de Código/API}

\begin{tcolorbox}[tarjetaDato, title={\faIcon{info-circle}~Ficha Técnica}]
  \begin{tabularx}{\linewidth}{>{\bfseries\color{azulNoche}}l X >{\bfseries\color{azulNoche}}l X}
    \faIcon{layer-group}~Capa: & Orquestación (Layer 2) & \faIcon{project-diagram}~Directiva: & \texttt{directives/repo\_a\_skill.yaml} \\
    \faIcon{terminal}~Invocación: & \texttt{python3 flujo\_repo\_a\_skill.py --repo <url|dir>} & \faIcon{coins}~Créditos: & Paso 3 (síntesis) \texttt{openrouter\_chat} \\
    \faIcon{file-code}~Perfil de salida: & \texttt{referencia\_codigo} & \faIcon{check-double}~Modelo default: & \texttt{deepseek/deepseek-v4-pro} \\
  \end{tabularx}
\end{tcolorbox}

\tableofcontents
\vspace{4pt}

% ── 1. Qué es y para qué sirve ───────────────────────────────────────────────
\section{\iconotexto{bullseye}{¿Qué es el Orquestador y Para Qué Sirve?}}

\texttt{flujo\_repo\_a\_skill.py} es la \textbf{capa de orquestación} de la Fase 1b: el
\emph{middleware} que conecta \textbf{la intención del usuario} (``quiero un skill a partir de
este repositorio'') con \textbf{los scripts deterministas de ejecución} de \path{execution/}.
Convierte un \textbf{repositorio de código} (URL de GitHub o directorio local) en un
\textbf{skill global de referencia de código/API}, instalado en
\path{~/.config/opencode/skills/<nombre>/}.

\begin{cajaConcepto}
\textbf{En una frase:} el orquestador orquesta 5 scripts de ejecución en una secuencia de 8
pasos, mantiene el \textbf{estado en \texttt{.tmp/run\_state.json}}, decide el \textbf{tier LLM de
forma determinista} y aplica las \textbf{políticas de recuperación} ante fallos. No ``razona''
la lógica de negocio: simplemente la \emph{dirige}.
\end{cajaConcepto}

\subsection{Por qué es necesario (el problema que resuelve)}
\begin{itemize}[leftmargin=*]
  \item \textbf{Un LLM alucina las APIs} de una librería si solo ``recuerda'' haberlas visto.
    Un skill formal y verificado ancla la referencia a la fuente real.
  \item \textbf{La fiabilidad compuesta se degrada:} si 5 pasos tienen 90\,\% de acierto cada
    uno, el resultado global cae a $\approx$59\,\%. El orquestador empuja la complejidad a
    scripts deterministas ({}90\,\%+) y mantiene la toma de decisiones ``delgada''.
  \item \textbf{Reproducibilidad:} misma entrada $\to$ misma salida. El flujo se puede
    re-ejecutar sin depender de la memoria del chat; el estado en disco lo permite retomar.
  \item \textbf{Separación de responsabilidades} (arquitectura de 3 capas): la directiva
    documenta \emph{qué} hacer, el orquestador decide \emph{cuándo y cuál} script, y los
    scripts saben \emph{cómo} ejecutar.
\end{itemize}

% ── 2. Arquitectura de 3 capas ────────────────────────────────────────────────
\section{\iconotexto{layer-group}{La Arquitectura de 3 Capas de este Flujo}}

\begin{table}[h!]
\centering
\small
\begin{tabularx}{\linewidth}{>{\bfseries\color{azulNoche}}l >{\ttfamily}p{4.6cm} >{\raggedright\arraybackslash}X}
\toprule
\rowcolor{azulNoche!12}\textbf{Capa} & \textbf{Artefacto} & \textbf{Rol} \\
\midrule
\textbf{Directiva} & directives/repo\_a\_skill.yaml & SOP determinista: goal, 8 pasos, 7 edge cases, política de reintentos y metadata de coste. \\
\midrule
\textbf{Orquestación} & \texttt{flujo\_repo\_a\_skill.py} & Entrevista, orquesta scripts, decide el modelo (enrutador), valida salidas intermedias, gestiona errores y notifica. \\
\midrule
\textbf{Ejecución} & execution/extraer\_repo\_github.py \newline execution/sintetizar\_skill.py \newline execution/validar\_skill\_formulas.py \newline execution/generar\_latex\_skill.py \newline execution/instalar\_skill.py & \texttt{extraer\_repo\_github.py}: clona/filtra/concatena. \texttt{sintetizar\_skill.py}: destila el corpus con el LLM. \texttt{validar\_skill\_formulas.py}: valida bloques Python sin créditos. \texttt{generar\_latex\_skill.py}: reporte PDF. \texttt{instalar\_skill.py}: copia a global. \\
\bottomrule
\end{tabularx}
\caption{Responsabilidades de las 3 capas en la Fase 1b.}
\end{table}

\begin{tcolorbox}[tarjetaIcono, title={\faIcon{magic}~Regla de oro del orquestador}]
\textbf{El orquestador no raspa, no destila, no valida y no instala por sí mismo.} Cada paso
delegado llama a un script de \path{execution/} con CLI estricta; las salidas se validan (JSON,
códigos de salida) antes de avanzar. Esto garantiza que ``el LLM del chat'' no introduzca
lógica arbitraria en el flujo.
\end{tcolorbox}

% ── 3. Entradas, salidas y flags principales ─────────────────────────────────
\section{\iconotexto{keyboard}{Entradas, Salidas y Flags Principales}}

\subsection{Entrada requerida}
\begin{itemize}[leftmargin=*]
  \item \texttt{--repo} (obligatorio): URL de GitHub (\texttt{https://github.com/owner/repo})
    o ruta a un directorio local. Es la \textbf{única entrada indispensable}.
  \item Opcionales: \texttt{--tema}, \texttt{--nombre}, \texttt{--idioma}. Si se omiten, el
    orquestador hace una \textbf{entrevista ligera interactiva} y persiste la respuesta en
    \path{.tmp/entrevista_skill_<nombre>.json}.
\end{itemize}

\subsection{Salidas que produce}
\begin{table}[h!]
\centering
\small
\begin{tabularx}{\linewidth}{>{\bfseries\color{azulNoche}}l X}
\toprule
\rowcolor{azulNoche!12}\textbf{Salida} & \textbf{Dónde} \\
\midrule
Skill global instalado & \path{~/.config/opencode/skills/<nombre>/} (SKILL.md + references/) \\
\midrule
Copia intermedia de revisión & \path{.tmp/skill_<nombre>/} \\
\midrule
Registro de la entrevista & \path{.tmp/entrevista_skill_<nombre>.json} \\
\midrule
Texto extraído del repo & \path{.tmp/repo_<nombre>_texto/texto_completo.txt} + \texttt{indice.json} \\
\midrule
Reporte LaTeX del skill & \path{docs/SKILL/<nombre>/<nombre>.tex} + \t{.pdf} \\
\midrule
Estado de la ejecución & \path{.tmp/run_state.json} \\
\bottomrule
\end{tabularx}
\caption{Artefactos de entrada/salida del flujo.}
\end{table}

\subsection{Flags más útiles}
\begin{table}[h!]
\centering
\small
\begin{tabularx}{\linewidth}{>{\ttfamily}p{4.6cm} >{\raggedright\arraybackslash}c >{\raggedright\arraybackslash}X}
\toprule
\rowcolor{azulNoche!12}\textbf{Flag} & \textbf{¿Créditos?} & \textbf{Qué hace} \\
\midrule
\texttt{--dry-run} & Según paso & Genera y valida el skill sin instalarlo en global. \\
\midrule
\texttt{--modelo <id>} & Sí (openrouter) & Override explícito del tier decidido por el enrutador. \\
\midrule
\texttt{--incluir/--excluir} & No & Globs para acotar qué archivos del repo se destilan. \\
\midrule
\texttt{--reflexion N} & Sí (re-síntesis) & Re-sintetiza hasta $N\le3$ veces si hay bloques inválidos. \\
\midrule
\texttt{--validar-estricto} & No & Aborta la instalación si la validación halla errores. \\
\midrule
\texttt{--estructura-max-tokens N} & No & Presupuesto de salida del ensamblaje (auto: 32768 en deepseek, 8192 resto). \\
\midrule
\texttt{--no-latex} & No & Omite el reporte LaTeX del skill. \\
\midrule
\texttt{--no-alert} & No & Omite la alerta audible final. \\
\bottomrule
\end{tabularx}
\caption{Catálogo de flags del orquestador y efectos.}
\end{table}

% ── 4. Los 8 pasos del flujo ─────────────────────────────────────────────────
\section{\iconotexto{list-ol}{Los 8 Pasos del Flujo}}

\begin{table}[h!]
\centering
\small
\begin{tabularx}{\linewidth}{>{\bfseries\color{azulNoche}}r >{\raggedright\arraybackslash}p{4.4cm} >{\ttfamily}p{4.2cm} >{\raggedright\arraybackslash}X}
\toprule
\rowcolor{azulNoche!12}\textbf{\#} & \textbf{Qué hace} & \textbf{Script} & \textbf{Créditos / Notas} \\
\midrule
1 & Entrevista ligera + validación de fuente & orquestador & 0 créditos; persiste entrevista. \\
\midrule
2 & Extracción: clona/filtra/concatena & \texttt{extraer\_repo\_github.py} & 0; determinista; genera \texttt{texto\_completo.txt} + \texttt{indice.json}. \\
\midrule
3 & Decisión determinista de tier & \texttt{enrutador.py --task contexto\_masivo} & 0; mide tokens y elige modelo en código. \\
\midrule
4 & Destilación LLM del skill & \texttt{sintetizar\_skill.py --perfil referencia\_codigo} & \textbf{Sí}; genera SKILL.md + 6 references de API. \\
\midrule
5 & Validación neuro-simbólica & \texttt{validar\_skill\_formulas.py --perfil referencia\_codigo} & 0; sólo riesgo de Sistema bloquea; reflexión opcional. \\
\midrule
6 & Reporte LaTeX infográfico & \texttt{generar\_latex\_skill.py} & 0; PDF en \path{docs/SKILL/<nombre>/}. \\
\midrule
7 & Revisión humana & orquestador + usuario & 0; aprueba o re-sintetiza ($\le$3). \\
\midrule
8 & Instalación global + aviso & \texttt{instalar\_skill.py} + \texttt{alert\_user.py} & 0; recuerda reiniciar opencode. \\
\bottomrule
\end{tabularx}
\caption{Secuencia de 8 pasos del orquestador \texttt{flujo\_repo\_a\_skill.py}.}
\end{table}

\begin{cajaFortaleza}
\textbf{¿Por qué solo el Paso 4 consume créditos?} Siguiendo el principio
\emph{``orquestación gratis, ejecución medida''}, la extracción, el enrutamiento (decisión
100\,\% local), la validación, el reporte y la instalación son deterministas y no llaman a
ninguna API de pago. La única fase probabilística necesaria (la destilación por LLM) queda
acotada a un único script con \texttt{--modelo} y \texttt{--estructura-max-tokens} auditable.
\end{cajaFortaleza}

% ── 5. Estado, errores y recuperación ─────────────────────────────────────────
\section{\iconotexto{first-aid}{Trazabilidad, Errores y Recuperación}}

\subsection{Estado persistente: \texttt{.tmp/run\_state.json}}
Tras cada paso exitoso el orquestador guarda: \texttt{run\_id}, \texttt{directive},
\texttt{fuente}, \texttt{nombre}, \texttt{perfil}, \texttt{tier/modelo}, \texttt{dry\_run},
\texttt{current\_step}, \texttt{steps\_completed}, \texttt{steps\_failed} y marca temporal.
Esto permite saber \textbf{en qué paso quedó} un run y diagnosticar fallos sin re-ejecutar a
ciegas.

\subsection{Códigos de salida y política de reintentos}
\begin{itemize}[leftmargin=*]
  \item \texttt{0} $\to$ flujo completado (con \texttt{--dry-run} también es 0).
  \item \texttt{1} $\to$ fallo fatal en extracción, síntesis o instalación (se aborta y alerta).
  \item \texttt{3} $\to$ bloques inválidos (vía validador), relevante con \texttt{--validar-estricto}.
\end{itemize}

\begin{cajaAlerta}
\textbf{Retry budget:} máximo \textbf{3 reintentos} por tarea (lo impone el validador y el
bucle \texttt{--reflexion}). Si se agotan, el flujo \textbf{escala al usuario} en lugar de seguir
intentando a ciegas. Un fallo de API o de JSON se diagnostica, se corrige la causa y se
reintenta; nunca se "fuerza" la salida.
\end{cajaAlerta}

\subsection{Casos límite gestionados (extracto de la directiva)}
\begin{table}[h!]
\centering
\small
\begin{tabularx}{\linewidth}{>{\bfseries\color{azulNoche}}l >{\raggedright\arraybackslash}X}
\toprule
\rowcolor{azulNoche!12}\textbf{Caso} & \textbf{Recuperación} \\
\midrule
Repo privado o 404 & \texttt{git clone} falla; ofrecer ruta local o \texttt{GITHUB\_TOKEN}. \\
\midrule
Repo sin código/docs tras filtrar & Código 2 del extractor; sugerir \texttt{--incluir}. \\
\midrule
Repo enorme / coste alto & Antes de la síntesis se muestran tokens medidos; proponer acotar con globs. \\
\midrule
Bloques Python inválidos & Avisar; \texttt{--validar-estricto} aborta; \texttt{--reflexion} re-sintetiza (créditos). \\
\midrule
El repo cambia o la ruta desaparece & Cada corrida re-clona; si la ruta local no existe, código 1 y fin. \\
\bottomrule
\end{tabularx}
\caption{Casos límite y su protocolo de recuperación.}
\end{table}

% ── 6. Ejemplo real de uso ────────────────────────────────────────────────────
\section{\iconotexto{flask}{Ejemplo Real: \texttt{pallets/itsdangerous}}}

La primera prueba E2E del orquestador se ejecutó sobre el repositorio público
\path{https://github.com/pallets/itsdangerous} (librería de firma de datos del proyecto
Pallets, ~32 archivos de código y documentación):

\begin{tcolorbox}[tarjetaDato, title={\faIcon{check-circle}~Resultados de la ejecución real}]
  \begin{tabularx}{\linewidth}{>{\bfseries\color{azulNoche}}l X}
    Volumen de entrada: & 32 archivos incluidos / 8 excluidos, 91\,396 caracteres, $\sim$22.5K tokens \\
    Tier enrutado (determinista): & \textbf{deepseek} (\texttt{deepseek/deepseek-v4-pro}) \\
    Chunks destilados: & 2 \\
    Validación neuro-simbólica: & \textbf{0 errores} (74 bloques; 0 \texttt{peligro}, el resto \texttt{ok}/\texttt{observacion}) \\
    Estructuras de referencia: & 6/6 presentes (api, patrones, ejemplos, configuracion, prerrequisitos, glosario) \\
    Reporte LaTeX: & \path{docs/SKILL/pallets_itsdangerous/} (.tex + .pdf) \\
    Coste de la fase: & $\sim$\$0.01 USD \\
    Instalación: & Opcional (con confirmación del usuario; ya instalado en global) \\
  \end{tabularx}
\end{tcolorbox}

\begin{cajaFortaleza}
El \textbf{gate de instalación}: el orquestador solo instala en global si la validación del
paso 5 no arroja bloques peligrosos. Con \texttt{--dry-run} genera y valida sin tocar el
entorno de producción, y \texttt{--reflexion} permite corregir iterativamente antes de
instalar. RAS: reproducibilidad, auditabilidad y seguridad en cada ejecución.
\end{cajaFortaleza}

% ── 7. Invocación práctica ────────────────────────────────────────────────────
\section{\iconotexto{terminal}{Guía de Invocación Rápida}}

\begin{tcolorbox}[cajaContenido, title={\faIcon{terminal}~Ejemplos de uso del orquestador}]
\begin{lstlisting}[style=estiloBash]
# 1. Flujo completo (entrevista interactiva si faltan datos)
python3 flujo_repo_a_skill.py --repo https://github.com/pallets/itsdangerous \
    --tema "Firma y autenticacion de datos" --nombre pallets_itsdangerous

# 2. Modo dry-run: genera y valida sin instalar en global
python3 flujo_repo_a_skill.py --repo /ruta/al/repo --nombre mi_skill --dry-run

# 3. Acotar el alcance del repo con globs (controla coste)
python3 flujo_repo_a_skill.py --repo https://github.com/usuario/repo \
    --incluir "src/**" "*.py" --excluir "**/tests/*" --nombre mi_skill

# 4. Todo explicito, sin instalacion (para revisar antes de publicar)
python3 flujo_repo_a_skill.py --repo /ruta --nombre mi_skill --tema "API de ejemplo" \
    --idioma es --dry-run --validar-estricto --reflexion 1
\end{lstlisting}
\end{tcolorbox}

\begin{cajaRecuerda}
Tras instalar un skill, \textbf{reinicia opencode}: la configuración no se recarga en
caliente y el skill no será detectable hasta el reinicio. El orquestador ya recuerda este
aviso en su último paso (alerta \texttt{success}).
\end{cajaRecuerda}
"""


def generar_tex() -> str:
    return PREAMBULO_INFOGRAFIA + DOC_SPECIFIC + "\n\\begin{document}\n" + BODY + "\n\\end{document}\n"


def compilar(tex_path: str) -> str:
    base = os.path.splitext(tex_path)[0]
    for _ in range(2):
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
             f"-jobname={os.path.basename(base)}", tex_path],
            capture_output=True, cwd=os.path.dirname(tex_path) or ".",
        )
    log_path = base + ".log"
    errores = []
    if os.path.exists(log_path):
        with open(log_path, "r", errors="ignore") as f:
            errores = [l.strip() for l in f if l.startswith("!")]
    for ext in ["aux", "log", "out", "toc"]:
        aux = base + "." + ext
        if os.path.exists(aux):
            os.remove(aux)
    pdf = base + ".pdf"
    if not os.path.exists(pdf):
        raise RuntimeError("No se generó el PDF.\n" + "\n".join(errores[:8]))
    if errores:
        raise RuntimeError("Compilación con errores:\n" + "\n".join(errores[:8]))
    return pdf


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera el documento infográfico del orquestador.")
    parser.add_argument("--salida", default="docs/AGENTE_IA/orquestador_repo_a_skill.tex")
    parser.add_argument("--no-compilar", action="store_true")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    salida = args.salida if os.path.isabs(args.salida) else os.path.join(base_dir, args.salida)
    os.makedirs(os.path.dirname(salida), exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        f.write(generar_tex())
    print(f"[ok] .tex escrito: {salida}")

    if not args.no_compilar:
        pdf = compilar(salida)
        print(f"[ok] PDF generado: {pdf}")


if __name__ == "__main__":
    main()