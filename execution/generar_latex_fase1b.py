#!/usr/bin/env python3
r"""
generar_latex_fase1b.py — Reporte LaTeX infográfico del manual técnico Fase 1b (repo→skill)

Layer 3 (Execution). Determinista, 0 créditos. Importa PREAMBULO_INFOGRAFIA desde
estilo_infografia.py (no duplica preámbulo) y concatena su cabecera específica.

Uso:
    python3 execution/generar_latex_fase1b.py [--salida docs/AGENTE_IA/fase1b_repo_a_skill.tex]
"""

import argparse
import os
import subprocess
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from estilo_infografia import PREAMBULO_INFOGRAFIA

ICONO_BANDA = "code-branch"

DOC_SPECIFIC = r"""
% ── Cabecera específica del documento Fase 1b ─────────────────────────────────
\renewcommand{\iconoBanda}{code-branch}
\fancyhead[L]{\textcolor{grisTexto}{\footnotesize\faIcon{code-branch}~Fase 1b --- Repositorio a Skill de Referencia de Código/API}}
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
"""

BODY = r"""
\bandaTitulo[fondoOscuro]{Fase 1b --- De un Repositorio de Código a un Skill de Referencia (API/Código)}
{Documento de estudio técnico \quad|\quad Complementa la Fase 1 (libro) y la Fase 2 (resolución)}

\begin{tcolorbox}[tarjetaDato, title={\faIcon{info-circle}~Ficha Técnica del Documento}]
  \begin{tabularx}{\linewidth}{>{\bfseries\color{azulNoche}}l X >{\bfseries\color{azulNoche}}l X}
    \faIcon{calendar-check}~Fecha: & Septiembre 2026 & \faIcon{layer-group}~Arquitectura: & 3 Capas Deterministas \\
    \faIcon{code-branch}~Entrada: & Repo GitHub o dir local & \faIcon{code}~Perfil de síntesis: & \texttt{referencia\_codigo} \\
    \faIcon{microchip}~Modelo (default): & Tier \textbf{deepseek} & \faIcon{shield-alt}~Validación: & Prob. de Sistema (0 errores E2E) \\
  \end{tabularx}
\end{tcolorbox}

\tableofcontents
\vspace{4pt}

% ── 1. Qué resuelve ───────────────────────────────────────────────────────────
\section{\iconotexto{bullseye}{Qué Resuelve la Fase 1b}}

Un LLM que ``recuerda'' una librería (\path{~/.config/opencode/skills/<nombre>/README.md}) tiende a
alucinar sus APIs. La \textbf{Fase 1b} transforma un \textbf{repositorio (GitHub o local)} en un
\textbf{skill estructurado de referencia de código/API}:

\begin{lstlisting}
[GitHub URL | dir local] --> extraer_repo_github.py --> texto_completo.txt
                                                              |
                                              [enrutador.py (contexto_masivo)]
                                                              |
                    sintetizar_skill.py --perfil referencia_codigo
                    (destila chunk a chunk --> corpus; ensambla 6 references)
                                                              |
              validar_skill_formulas.py --perfil referencia_codigo (gate)
                                                              |
         generar_latex_skill.py --> reporte PDF | instalar_skill.py --> skills
\end{lstlisting}

\subsection{Diferencia frente a la Fase 1 (libro)}

\begin{table}[h!]
\centering
\small
\begin{tabularx}{\linewidth}{>{\bfseries\color{azulNoche}}l >{\raggedright\arraybackslash}X >{\raggedright\arraybackslash}X}
\toprule
\rowcolor{azulNoche!12}\textbf{Eje} & \textbf{Fase 1 (libro)} & \textbf{Fase 1b (repo)} \\
\midrule
Fuente & PDF de texto & Repositorio (URL GitHub o directorio local) \\
\midrule
Extracción & \texttt{extraer\_libro\_pdf.py} & \texttt{extraer\_repo\_github.py} (clona, filtra, concatena) \\
\midrule
Perfil de síntesis & \texttt{libro} (default) & \texttt{referencia\_codigo} \\
\midrule
Esquema de references & \texttt{formulas.md}, \texttt{metodologias.md}, \texttt{limites\_aplicabilidad.md}, \texttt{tablas.md}\dots & \texttt{api.md}, \texttt{patrones.md}, \texttt{ejemplos.md}, \texttt{configuracion.md}, \texttt{prerrequisitos.md}, \texttt{glosario.md} \\
\midrule
Código en bloques & SymPy autocontenido (se ejecuta en sandbox) & Snippets/ejemplos reales del repo (\texttt{from <paquete> import \dots}) \\
\midrule
Validación & Sintaxis + imports seguros (solo math/sympy/fractions) + ejecución en sandbox & Sintaxis (observación) + bloqueo solo de módulos/funciones de Sistema; NO ejecuta en sandbox \\
\bottomrule
\end{tabularx}
\caption{Comparativa entre la Fase 1 (destilación de libro) y la Fase 1b (destilación de repositorio).}
\end{table}

% ── 2. Arquitectura de 3 capas ────────────────────────────────────────────────
\section{\iconotexto{layer-group}{Arquitectura de 3 Capas (obligatoria)}}

\begin{table}[h!]
\centering
\small
\begin{tabularx}{\linewidth}{>{\bfseries\color{azulNoche}}l >{\ttfamily}p{4.4cm} >{\raggedright\arraybackslash}X}
\toprule
\rowcolor{azulNoche!12}\textbf{Capa} & \textbf{Archivo} & \textbf{Rol} \\
\midrule
\textbf{Directiva} & directives/repo\_a\_skill.yaml & SOP: 8 pasos, 8 edge cases, retry budget \\
\midrule
\textbf{Orquestación} & flujo\_repo\_a\_skill.py & Entrevista, orquesta scripts, gate de instalación \\
\midrule
\textbf{Ejecución} & execution/extraer\_repo\_github.py \newline execution/sintetizar\_skill.py (perfil \texttt{referencia\_codigo}) \newline execution/validar\_skill\_formulas.py (perfil \texttt{referencia\_codigo}) \newline execution/generar\_latex\_skill.py \newline execution/instalar\_skill.py & Trabajo determinista \\
\bottomrule
\end{tabularx}
\caption{Matriz de responsabilidades de la arquitectura de 3 capas en la Fase 1b.}
\end{table}

% ── 3. El orquestador flujo_repo_a_skill.py ───────────────────────────────────
\section{\iconotexto{cogs}{El Orquestador \texttt{flujo\_repo\_a\_skill.py}}}

Pasos (total depende de flags):

\begin{enumerate}[leftmargin=*]
  \item \textbf{Entrevista ligera:} fuente, tema, nombre (snake\_case, default derivado del repo), idioma, filtros de archivos y confirmación de instalación. Se persiste en \path{.tmp/entrevista_skill_<nombre>.json}.
  \item \textbf{Extracción} --- \path{execution/extraer_repo_github.py} (determinista, 0 créditos):
  \begin{itemize}[leftmargin=*]
    \item URL GitHub $\to$ \texttt{git clone --depth 1} a \path{.tmp/repo_clone_<owner>-<repo>/}; ruta local $\to$ usa el dir tal cual.
    \item Filtra por extensión (docs + código fuente) saltando \path{.git/node_modules/vendor/build/venv/__pycache__}.
    \item \texttt{--incluir}/\texttt{--excluir} globs opcionales, \texttt{--max-archivos}/\texttt{--max-bytes}.
    \item Concatena a \path{.tmp/repo_<nombre>_texto/texto_completo.txt} con cabeceras \texttt{=== ARCHIVO: <ruta> ===} y genera \texttt{indice.json} con árbol de estructura.
    \item E2E real: \texttt{pallets/itsdangerous} $\to$ 32 archivos, $\sim$22.5K tokens.
  \end{itemize}
  \item \textbf{Enrutamiento determinista} --- \path{execution/enrutador.py --task contexto_masivo}: mide tokens y decide tier. Para un repo grande $\to$ \textbf{deepseek} (\texttt{deepseek/deepseek-v4.1-flash}).
  \item \textbf{Síntesis (créditos)} --- \path{execution/sintetizar_skill.py --perfil referencia_codigo} $\to$ 7 archivos (SKILL.md + 6 references de API). Prompts adaptados: NO fuerzan SymPy.
  \item \textbf{Validación (0 créditos)} --- \path{execution/validar_skill_formulas.py --perfil referencia_codigo}. Solo bloquea riesgos de Sistema; los snippets de API (firmas incompletas, imports del paquete) se marcan \texttt{ok}/\texttt{observacion}, nunca errores.
  \item \textbf{Reporte LaTeX (0 créditos)} --- \path{execution/generar_latex_skill.py} $\to$ PDF en \path{docs/SKILL/<nombre>/}.
  \item \textbf{Revisión humana} del skill.
  \item \textbf{Instalación (si no es --dry-run)} --- \path{execution/instalar_skill.py} $\to$ copia a \path{~/.config/opencode/skills/<nombre>/}. Recuerda reiniciar opencode.
\end{enumerate}

% ── 4. El perfil referencia_codigo en sintetizar_skill.py ─────────────────────
\section{\iconotexto{microchip}{El Perfil \texttt{referencia\_codigo} en \texttt{sintetizar\_skill.py}}}

\texttt{--perfil} (default \texttt{libro}) cambia dos cosas:

\subsection{Prompts de destilación por chunk}
\texttt{\_prompts\_chunk\_codigo}: en vez de ``fórmulas, metodologías, tablas'', pide
``funciones y clases públicas con firmas, patrones de uso, configuración relevante,
ejemplos de código que el lector pueda copiar''.

\subsection{Esquema de references y normas de contenido}
\texttt{\_normas\_contenido\_codigo}:

\begin{table}[h!]
\centering
\small
\begin{tabularx}{\linewidth}{>{\ttfamily}p{4.2cm} >{\raggedright\arraybackslash}X}
\toprule
\rowcolor{azulNoche!12}\textbf{Archivo} & \textbf{Contenido} \\
\midrule
\texttt{api.md} & Funciones/clases públicas con firma completa (parámetros, retorno) y ejemplo de llamada \\
\midrule
\texttt{patrones.md} & Cómo se combinan funciones/clases para resolver problemas típicos \\
\midrule
\texttt{ejemplos.md} & Código REAL del repo (no inventado), marcado por archivo de origen \\
\midrule
\texttt{configuracion.md} & Opciones, variables de entorno, archivos de config \\
\midrule
\texttt{prerrequisitos.md} & Dependencias, versiones, cómo instalar \\
\midrule
\texttt{glosario.md} & Términos técnicos del proyecto \\
\bottomrule
\end{tabularx}
\caption{Contenido de las 6 referencias en el perfil \texttt{referencia\_codigo}.}
\end{table}

Además: el \textbf{frontmatter} usa el mismo saneo determinista (\texttt{\_normalizar\_frontmatter})
y \texttt{\_find\_balanced\_json} aplica igual (robusto a llaves anidadas).

% ── 5. La validación en el perfil referencia_codigo ───────────────────────────
\section{\iconotexto{shield-alt}{La Validación en el Perfil \texttt{referencia\_codigo}}}

El validador clásico (\texttt{validar\_skill\_formulas.py} perfil \texttt{libro}) exige que cada
bloque \texttt{python} sea un programa SymPy autocontenido (solo \texttt{math}/\texttt{sympy}/%
\texttt{fractions}) y lo ejecuta en sandbox. Eso es \textbf{incorrecto para un skill de API}:
los ejemplos legítimamente hacen \texttt{from <paquete> import \dots}, y el paquete no está
instalado en el sandbox.

Con \texttt{--perfil referencia\_codigo}:

\begin{enumerate}[leftmargin=*]
  \item \textbf{Sintaxis} --- \texttt{ast.parse} de cada bloque. Si falla (firma/documentación incompleta), se marca \texttt{observacion} (NO bloquea): son snippets ilustrativos, no programas.
  \item \textbf{Seguridad} --- \texttt{\_escaneo\_peligro\_sistema}: solo bloquea módulos/funciones de Sistema con riesgo real (\texttt{os}, \texttt{sys}, \texttt{subprocess}, \texttt{socket}, \texttt{ctypes}, \texttt{open}, \texttt{eval}, \texttt{exec}, \texttt{\_\_import\_\_}, \dots). Imports de librería/proyecto (\texttt{itsdangerous}, \texttt{hashlib}) son legítimos. Un bloque con riesgo $\to$ estado \texttt{peligro} (ÚNICO estado que cuenta como error y hace exit 3).
  \item \textbf{NO se ejecuta en sandbox} --- el código depende del paquete del repo.
\end{enumerate}

\begin{cajaAlerta}
\textbf{Decisión de diseño verificada en E2E:} un sandbox que ejecutara los ejemplos de una API
convertiría 74 bloques legítimos (imports del paquete, firmas parciales) en 74 falsos positivos.
El perfil adaptativo reduce eso a \textbf{0 errores} conservando la protección real contra código
peligroso de Sistema.
\end{cajaAlerta}

% ── 6. Costo y créditos ───────────────────────────────────────────────────────
\section{\iconotexto{coins}{Costo y Créditos}}

\begin{itemize}[leftmargin=*]
  \item \textbf{0 créditos}: extracción, enrutador (decisión local), validación, LaTeX, tests.
  \item \textbf{Créditos}: síntesis (\texttt{openrouter\_chat}, default deepseek). Repo pequeño: $\sim$22K tokens de entrada $\approx$ centavos de dólar. Repo grande: avisar antes, acotar con \texttt{--incluir}/\texttt{--excluir}.
  \item Verificación de saldo puntual: \texttt{python3 execution/monitor\_saldo\_openrouter.py}.
\end{itemize}

% ── 7. Comandos de ejemplo ────────────────────────────────────────────────────
\section{\iconotexto{terminal}{Comandos de Ejemplo}}

\begin{tcolorbox}[cajaContenido, title={\faIcon{terminal}~Ejemplos de invocación}]
\begin{lstlisting}[style=estiloBash]
# GitHub publico, disponible para resolver
python3 flujo_repo_a_skill.py --repo https://github.com/pallets/itsdangerous \
    --tema "Firma y autenticacion de datos" --nombre pallets_itsdangerous

# Directorio local acotando a codigo Python
python3 flujo_repo_a_skill.py --repo /ruta/al/repo --nombre midu_skill \
    --incluir "*.py" "*.md" --excluir "tests/*" --dry-run

# Solo extraer (0 creditos, determinista)
python3 execution/extraer_repo_github.py --fuente https://github.com/psf/requests \
    --salida .tmp/repo_requests_texto
\end{lstlisting}
\end{tcolorbox}

% ── 8. Edge cases clave ───────────────────────────────────────────────────────
\section{\iconotexto{exclamation-triangle}{Edge Cases Clave (ver la directiva)}}

\begin{table}[h!]
\centering
\small
\begin{tabularx}{\linewidth}{>{\bfseries\color{azulNoche}}l >{\raggedright\arraybackslash}X}
\toprule
\rowcolor{azulNoche!12}\textbf{Caso} & \textbf{Recuperación} \\
\midrule
Repo privado / 404 & \texttt{git clone} falla; ofrecer ruta local o \texttt{GITHUB\_TOKEN} \\
\midrule
Repo sin código/docs tras filtrar & Código 2; sugerir \texttt{--incluir} \\
\midrule
Repo enorme / costo alto & Avisar tokens medidos; acotar con globs o límites \\
\midrule
Snippets no autocontenidos & \texttt{observacion} (no bloquea instalación) en perfil código \\
\midrule
Bloque con riesgo de Sistema & \texttt{peligro} $\to$ exit 3; con \texttt{--validar-estricto} aborta instalación \\
\bottomrule
\end{tabularx}
\caption{Catálogo de casos límite y protocolo de recuperación (directiva \texttt{repo\_a\_skill.yaml}).}
\end{table}

\begin{cajaRecuerda}
El enfoque neuro-simbólico separa el razonamiento del LLM (probabilístico) de la decisión y la
validación (deterministas). En la Fase 1b esto se concreta en: extracción determinista del repo,
enrutamiento con umbrales en código, validación adaptativa por perfil y coste controlado por globs.
\end{cajaRecuerda}
"""


def generar_tex() -> str:
    """Concatena preámbulo compartido + cabecera específica + cuerpo."""
    return PREAMBULO_INFOGRAFIA + DOC_SPECIFIC + "\n\\begin{document}\n" + BODY + "\n\\end{document}\n"


def compilar(tex_path: str, job_dir: str = None) -> None:
    """Compila con pdflatex (2 pasadas) y limpia auxiliares, manteniendo .tex y .pdf."""
    base = os.path.splitext(tex_path)[0]
    cmd = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
           f"-jobname={os.path.basename(base)}", tex_path]
    for _ in range(2):
        proc = subprocess.run(cmd, capture_output=True, cwd=os.path.dirname(tex_path) or ".")
        if proc.returncode != 0:
            # Reintenta sin -halt-on-error para diagnosticar en el log
            subprocess.run(["pdflatex", "-interaction=nonstopmode",
                            f"-jobname={os.path.basename(base)}", tex_path],
                           capture_output=True, cwd=os.path.dirname(tex_path) or ".")
            log_path = base + ".log"
            if os.path.exists(log_path):
                with open(log_path, "r", errors="ignore") as f:
                    errores = [l.strip() for l in f if l.startswith("!")][:8]
                raise RuntimeError("Fallo de compilación LaTeX:\n" + "\n".join(errores))
            raise RuntimeError(f"pdflatex salió con código {proc.returncode}")
    for ext in ["aux", "log", "out", "toc"]:
        aux = base + "." + ext
        if os.path.exists(aux):
            os.remove(aux)
    if not os.path.exists(base + ".pdf"):
        raise RuntimeError("No se generó el PDF.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera el reporte LaTeX infográfico Fase 1b.")
    parser.add_argument("--salida", default="docs/AGENTE_IA/fase1b_repo_a_skill.tex",
                        help="Ruta del .tex de salida (el PDF se genera al lado).")
    parser.add_argument("--no-compilar", action="store_true",
                        help="Solo escribir el .tex sin compilar.")
    args = parser.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    salida = args.salida if os.path.isabs(args.salida) else os.path.join(root, args.salida)
    tex = generar_tex()
    os.makedirs(os.path.dirname(salida), exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        f.write(tex)
    print(f"[ok] .tex escrito: {salida}")

    if not args.no_compilar:
        compilar(salida)
        print(f"[ok] PDF generado: {os.path.splitext(salida)[0]}.pdf")


if __name__ == "__main__":
    main()