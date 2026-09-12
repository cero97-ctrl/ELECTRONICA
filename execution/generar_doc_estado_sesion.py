#!/usr/bin/env python3
r"""
generar_doc_estado_sesion.py — Documento infográfico sobre la higiene de estado
de sesión (run_state huérfano + guards MCP). (Layer 3: Execution)

Determinista y 0 créditos. Importa PREAMBULO_INFOGRAFIA de estilo_infografia.py
(no lo duplica) y genera un .tex + .pdf en docs/AGENTE_IA/.

Uso:
    python3 execution/generar_doc_estado_sesion.py [--output DIR] [--no-compile]

Salida:
    docs/AGENTE_IA/higiene_estado_sesion.tex (.pdf si compila)
"""

import argparse
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
sys.path.append(str(ROOT / "execution"))

try:
    from execution.estilo_infografia import PREAMBULO_INFOGRAFIA
except ImportError:
    from estilo_infografia import PREAMBULO_INFOGRAFIA

try:
    from execution.compile_latex import compile_latex_code
except ImportError:
    from compile_latex import compile_latex_code


FECHA = date.today().strftime("%d/%m/%Y")

CUERPO = r"""
% ── Cabeceras específicas del documento ────────────────────────────────────────
\fancyhead[L]{\small\color{azulNoche}\textbf{ELECTRÓNICA} --- Higiene de Estado de Sesión}
\fancyhead[R]{\small\color{grisTexto}@@FECHA@@}
\renewcommand{\headrulewidth}{0pt}

% ─────────────────────────────────────────────────────────────────────────────
\begin{document}

% ══ PORTADA INFográfica ════════════════════════════════════════════════════════
\renewcommand{\iconoBanda}{shield-alt}
\bandaTitulo[fondoOscuro]{Higiene de Estado de Sesión}{run\_state.json como vista derivada, guards en los servidores MCP y limpieza determinista}

\vspace{4pt}
\begin{tcolorbox}[cajaTitulo, title=Resumen ejecutivo]
\textbf{Problema:} \texttt{run\_state*.json} son \emph{vistas derivadas} de los logs
append-only \texttt{session\_log\_*.jsonl} (la fuente de verdad). Una vista puede
\emph{sobrevivir a su corrida} y quedar huérfana, contaminando las respuestas de los
servidores MCP con el estado de \emph{otra} ejecución.

\textbf{Solución (aprobada por el usuario):} un script determinista de salud
(\texttt{execution/estado\_sesion.py}) con \texttt{check} + \texttt{clean}, una
guardia por mtime en los 5 servidores MCP que leen \texttt{run\_state.json}, el edge
case documentado en la directiva de trazabilidad, y una regla de \emph{state hygiene}
al inicio de cada sesión en \texttt{AGENTS.md}. Todo a \textbf{0 créditos} OpenRouter.
\end{tcolorbox}

% ══ SECCIÓN 1: EL PROBLEMA ═════════════════════════════════════════════════════
\section{\iconotexto{bullseye}{El problema: vistas que sobreviven al run}}

\subsection{Modelo de estado en ELECTRONICA}
El rastreo de flujos multi-paso sigue una separación estricta entre \emph{fuente de
verdad} y \emph{vista}:

\begin{center}
\begin{tabularx}{\linewidth}{>{\raggedright\arraybackslash}p{0.30\linewidth} p{0.30\linewidth} X}
\toprule
\textbf{Artefacto} & \textbf{Rol} & \textbf{Naturaleza} \\
\midrule
\texttt{session\_log\_<run>.jsonl} & Fuente de verdad & Append-only, inmutable \\
\texttt{run\_state.json} & Vista global del último flujo & Sobrescribible \\
\texttt{run\_state\_<run>.json} & Vista de un run concreto & Regenerable \\
\bottomrule
\end{tabularx}
\end{center}

\begin{cajaConcepto}
\faIcon{lightbulb}~\textbf{Concepto clave:} un \texttt{run\_state.json} puede
\emph{quedar huérfano}. Si el flujo termina (evento \texttt{flujo/fin} en su log) pero
la vista no se limpia, el archivo sigue existiendo en \texttt{.tmp/} apuntando a un run
que ya no está activo. Cualquier consumidor que lo lea \emph{sin verificar} reportará
estado de una corrida terminada — o peor, de una corrida distinta.
\end{cajaConcepto}

\subsection{Caso real detectado}
Durante la auditoría de continuidad se encontró exactamente este caso:

\begin{tcolorbox}[cajaMejora, title=Caso de estudio --- vista huérfana de un dry-run]
\begin{itemize}%[leftmargin=*]
  \item \textbf{\texttt{.tmp/run\_state.json}} apuntaba a
        \texttt{flujo-repo-a-skill-2026-09-09T12-29-54} (un dry-run de prueba de
        trazabilidad).
  \item Su log \texttt{session\_log\_...jsonl} tenía \textbf{6 eventos} y terminaba con
        \texttt{flujo/fin}: la corrida \emph{ya había terminado}.
  \item El estado referenciaba \texttt{deepseek/deepseek-v4-pro}, modelo
        \textbf{discontinuado} (sustituido por \texttt{deepseek-v4.1-flash}).
  \item Los servidores MCP leen \texttt{run\_state.json} \emph{global} como
        ``estado del flujo recién lanzado'' → riesgo real de responder con el contexto
        de otra corrida.
\end{itemize}
\end{tcolorbox}

La trazabilidad append-only estaba íntegra: la cadena de hashes del log era válida
(\texttt{integrity} OK). El fallo no era del log, sino de \emph{confiar en la vista sin
cruzar contra la fuente}.

% ══ SECCIÓN 2: LA SOLUCIÓN ═════════════════════════════════════════════════════
\section{\iconotexto{layer-group}{La solución en tres capas}}

Siguiendo la arquitectura determinista, el refuerzo cubrió las tres capas:

\begin{table}[h]
\centering
\begin{tabularx}{\linewidth}{>{\raggedright\arraybackslash}p{0.20\linewidth} p{0.36\linewidth} X}
\toprule
\textbf{Capa} & \textbf{Artefacto} & \textbf{Aporte} \\
\midrule
L3 Ejecución & \texttt{execution/estado\_sesion.py} & Script \texttt{check} (diagnóstico) y \texttt{clean} (purgado certero) \\
L1 Directiva & \texttt{directives/trazabilidad\_sesiones.yaml} & Edge case ``run\_state huérfano'' documentado \\
L2 Orquestación & \texttt{AGENTS.md} + guards en MCP & Regla de higiene al arrancar; los servers no reportan vistas muertas \\
\bottomrule
\end{tabularx}
\end{table}

\subsection{Capa de ejecución: execution/estado\_sesion.py}

\subsubsection{check --- diagnóstico, nunca borra}
Escanea \texttt{run\_state.json} y \texttt{run\_state\_*.json}, cruza cada vista contra
su log y emite un veredicto por artefacto:

\begin{lstlisting}[style=estiloPython]
$ python3 execution/estado_sesion.py check
{
  "checks": [ { "archivo": "..../.tmp/run_state.json",
                "run_id": "flujo-repo-a-skill-...",
                "veredicto": "huerfano",
                "razon": "la corrida termino (flujo/fin); la vista sobrevivio.",
                "modelo_obsoleto": "deepseek-v4-pro" } ],
  "veredicto_global": "atencion", "anomalias": 1
}
\end{lstlisting}

Veredictos posibles y significado:

\begin{center}
\begin{tabularx}{\linewidth}{>{\raggedright\arraybackslash}p{0.14\linewidth} X}
\toprule
\textbf{Veredicto} & \textbf{Significado} \\
\midrule
\texttt{huerfano} & El log existe y su último evento es \texttt{flujo/fin}: la vista sobrevivió a la corrida terminada \\
\texttt{vigente} & Log sin \texttt{flujo/fin}: corrida en curso o reanudable \\
\texttt{no\_verificable} & No hay log (flujo sin trazabilidad): \textbf{no} se borra por falta de certeza \\
\texttt{corrupto} & JSON inválido o sin \texttt{run\_id} (escritura a medias) \\
\bottomrule
\end{tabularx}
\end{center}

Además detecta \textbf{modelos obsoletos} por substring (\texttt{deepseek-v4-pro}) y lo
reporta como \texttt{advertencia} (no justifica borrado por sí solo).

\subsubsection{clean --- borra solo con certeza}
\begin{lstlisting}[style=estiloPython]
$ python3 execution/estado_sesion.py clean            # purga vistas huerfanas
$ python3 execution/estado_sesion.py clean --dry-run  # lista sin borrar
$ python3 execution/estado_sesion.py check --run <id> # acotar a un run
\end{lstlisting}

Regla de oro del \texttt{--clean}: \textbf{borra únicamente} las vistas cuya corrida
terminó con \texttt{flujo/fin} (certeza absoluta). \textbf{Nunca} borra los logs
append-only (fuente de verdad inmutable), y \textbf{no} toca los
\texttt{no\_verificable}.

\begin{cajaRecuerda}
\faIcon{info-circle}~\textbf{Recuerda:} \texttt{check} solo diagnostica. El borrado es
intencional, vía \texttt{clean}, y está restringido a lo que el criterio anterior puede
confirmar. Un flujo sin trazabilidad (\texttt{no\_verificable}) se advierte pero jamás
se purga automáticamente.
\end{cajaRecuerda}

\subsection{Capa de directiva: trazabilidad\_sesiones.yaml}
Se amplió la directiva con un edge case específico (protocolo de recuperación):

\begin{lstlisting}
- case: "run_state.json obsoleto o huerfano al inicio de una sesion/consulta MCP"
  recovery: >
    El log append-only es la fuente de verdad; run_state*.json son vistas derivadas
    que pueden SOBREVIVIR a su corrida (...). Ejecutar execution/estado_sesion.py
    check y purgar con clean si marca huerfano/corrupto.
\end{lstlisting}

\subsection{Capa de orquestación: guards en los MCP y AGENTS.md}

\subsubsection{Guardia por mtime en los 5 servidores MCP}
Los servidores \texttt{mcp\_evaluar}, \texttt{mcp\_diagnostico}, \texttt{mcp\_analizar},
\texttt{mcp\_elaborar} y \texttt{mcp\_docs} siguen el mismo patrón: lanzan el flujo con
\texttt{subprocess.run} y, si termina OK, leen \texttt{run\_state.json} para dar una
respuesta \emph{rica}. La corrección captura el mtime \emph{antes} de lanzar y solo lee
la vista si el archivo fue \textbf{reescrito durante esta corrida}:

\begin{lstlisting}[style=estiloPython]
state_file = os.path.join(project_root, ".tmp", "run_state.json")
mtime_before = (os.path.getmtime(state_file)
                if os.path.exists(state_file) else None)
try:
    resultado = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", cwd=project_root)
    state_data = {}
    if os.path.exists(state_file):
        try:
            if mtime_before is not None and \
               os.path.getmtime(state_file) <= mtime_before:
                pass  # vista de OTRA corrida: no reportar
            else:
                with open(state_file, "r", encoding="utf-8") as f:
                    state_data = json.load(f)
        except Exception:
            state_data = {}
\end{lstlisting}

\begin{cajaRecuerda}
\faIcon{exclamation-triangle}~\textbf{Corrección de diseño importante:} la primera
versión del guard comprobaba \texttt{"flujo/fin"} en el log para descartar la vista.
\textbf{Ese criterio era inválido}: un flujo que corre \emph{bien} también emite
\texttt{flujo/fin}, así que se habría descartado el estado legítimo de la corrida que
acaba de terminar con éxito. El criterio correcto para el MCP es temporal:
``¿el \texttt{run\_state.json} fue reescrito \emph{durante} este lanzamiento?''
→ comparación de mtime. Se corrigió en los 5 servers antes del commit.
\end{cajaRecuerda}

\subsubsection{Regla de arranque en AGENTS.md}
\begin{lstlisting}
- **State hygiene (freshness):** run_state*.json are *derived views* of the
  append-only session_log_*.jsonl; a view can outlive its run (orphan) and poison
  MCP responses. At the start of each session (or before resuming any multi-step
  flow), run `python3 execution/estado_sesion.py check`; purge confirmed orphans
  with `... clean` (never touches the immutable logs).
\end{lstlisting}

% ══ SECCIÓN 3: VERIFICACIÓN ═══════════════════════════════════════════════════
\section{\iconotexto{flask}{Verificación (0 créditos)}}

\subsection{Guardia MCP: dos casos controlados}
Se replicó la lógica exacta del server contra dos escenarios:

\begin{tcolorbox}[cajaFortaleza, title=Caso A --- vista huérfana (no reescrita)]
\begin{lstlisting}[style=estiloPython]
run_state.json escrito hace 1h (mtime viejo).
mtime_before = getmtime()  # la corrida NO reescribe el archivo
resultado: state_data == {}       # << no se reporta estado ajeno
\end{lstlisting}
Resultado: \textbf{se descarta} la vista de otra corrida. \faIcon{check-circle}
\end{tcolorbox}

\begin{tcolorbox}[cajaFortaleza, title=Caso B --- estado reescrito por la corrida]
\begin{lstlisting}[style=estiloPython]
mtime_before = getmtime()
el flujo reescribe run_state.json  # mtime > mtime_before
resultado: state_data == {"run_id": "...", "context": {...}}  # << se usa
\end{lstlisting}
Resultado: \textbf{se conserva} el estado legítimo. \faIcon{check-circle}
\end{tcolorbox}

\subsection{Limpieza real del caso detectado}
\begin{lstlisting}[style=estiloPython]
$ python3 execution/estado_sesion.py check
  # -> veredicto "huerfano" + advertencia deepseek-v4-pro
$ python3 execution/estado_sesion.py clean
  # -> eliminado: .tmp/run_state.json
$ python3 execution/estado_sesion.py check
  # -> checks: []  veredicto_global: ok   (log immutable intacto)
\end{lstlisting}

El log append-only \texttt{session\_log\_flujo-repo-a-skill-2026-09-09T12-29-54.jsonl}
permaneció \textbf{intacto} (fuente de verdad intacta).

% ══ SECCIÓN 4: ALINEACIÓN CON LA ARQUITECTURA ═════════════════════════════════
\section{\iconotexto{sitemap}{Alineación con la arquitectura}}

\begin{itemize}%[leftmargin=*]
  \item \textbf{Determinismo:} mismo estado de \texttt{.tmp/} → mismo veredicto. El
        script no razona ni consume créditos.
  \item \textbf{Separación de responsabilidades:} la decisión de \emph{cuándo} una
        vista es obsoleta vive en código (capas 1 y 3), no en el chat del orquestador.
  \item \textbf{Autocuración:} la guardia de mtime evita que un MCP ``recupere''
        contexto basura tras un flujo que no llegó a escribir estado.
  \item \textbf{Retry budget respetado:} sin reintentos infinitos; el criterio es
        binario y verificable.
\end{itemize}

\begin{cajaEjemplo}
\faIcon{code}~\textbf{Ejemplo de uso cotidiano:} tras el reinicio de una sesión (o
antes de reanudar un flujo multi-paso), basta con
\begin{center}
\texttt{python3 execution/estado\_sesion.py check}
\end{center}
para saber si \texttt{run\_state.json} es fiable. Si reporta \texttt{huerfano}, un
\texttt{clean} lo purga en un paso.
\end{cajaEjemplo}

% ══ SECCIÓN 5: PENDIENTES ═════════════════════════════════════════════════════
\section{\iconotexto{list}{Pendientes y líneas siguientes}}

\begin{itemize}%[leftmargin=*]
  \item Considerar que los flujos emitan su \texttt{run\_id} al final del stdout
        (permitiría validación robusta sin depender de mtime).
  \item Extender \texttt{check} para limpiar \texttt{run\_state\_*.json} \emph{por
        run} de forma aún más agresiva solo si el usuario lo solicita.
  \item El pendiente de \texttt{docs/AGENTE\_IA/orquestador\_repo\_a\_skill.mp4}
        permanece en manos del usuario (fuera del alcance de esta sesión).
\end{itemize}

\end{document}
"""


def generar_latex() -> str:
    """Concatena el preámbulo infográfico con las cabeceras y el cuerpo."""
    return PREAMBULO_INFOGRAFIA + CUERPO.replace("@@FECHA@@", FECHA)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(ROOT / "docs/AGENTE_IA"),
                        help="Directorio destino del .tex (y .pdf si compila).")
    parser.add_argument("--no-compile", action="store_true",
                        help="Solo escribir el .tex, no compilar PDF.")
    args = parser.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    tex_path = out_dir / "higiene_estado_sesion.tex"

    latex = generar_latex()
    tex_path.write_text(latex, encoding="utf-8")
    print(f".tex generado en: {tex_path}")

    if args.no_compile:
        return 0

    res = compile_latex_code(latex, job_name="higiene_estado_sesion",
                             output_dir=str(out_dir))
    if res.get("success"):
        print(f"PDF generado en: {res['pdf_path']}")
        return 0
    print(f"Error de compilación: {res.get('error')}", file=sys.stderr)
    print(res.get("log", "")[-1500:], file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())