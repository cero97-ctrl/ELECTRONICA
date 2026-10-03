#!/usr/bin/env python3
"""Genera el examen de estudiante que sirve de fixture para la prueba real de
`flujo_evaluar_examen.py --tipo examen`.

Por qué un examen FABRICADO y no uno real del repo: la prueba solo vale si sabemos
la verdad. Este documento lleva errores deliberados y documentados en
`ERRORES_DELIBERADOS`; si el evaluador los detecta, la evidencia es inequívoca.
Con un examen real de 6 páginas no sabríamos si acertó o se inventó.

Por qué vive en `execution/` y no en `.tmp/` como el fixture de laboratorio: este
generador es lógica determinista repetible, y `.tmp/` es gitignored y se purga con
`flujo_disco.py`. Un fixture que solo existe hasta la próxima limpieza no es un
fixture reproducible: nadie puede volver a correr la prueba.

El examen NO lleva rúbrica a propósito (el camino `--tipo examen` es justamente el
que no la tiene). Declara en el enunciado una escala de 6 puntos (3 preguntas de 2),
que NO suma 10: es el caso donde sumar los parciales en crudo reprobaba al alumno que
respondía bien, y donde el programa tiene que normalizar a 10 y avisar.

Salida: .tmp/fixture_examen.pdf (intermedio; .tmp/ es gitignored).
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "execution"))
sys.path.insert(0, str(RAIZ))

from estilo_infografia import PREAMBULO_INFOGRAFIA  # noqa: E402
from compile_latex import compile_latex_code  # noqa: E402

# La verdad sobre este examen. El evaluador NO ve esta lista.
ERRORES_DELIBERADOS = [
    "P1 (procedimental): el divisor de tension mal resuelto (470/570 en vez de 100/570)",
    "P1 (conceptual): afirma que la tension se reparte 'a partes iguales' sin mirar los valores",
    "P2 (conceptual): dice que el condensador 'se descarga solo al quitar la fuente', cuando "
    "lo hace a traves de la resistencia de descarga",
    "P2 (procedimental): invierte la constante de tiempo (C/R en lugar de R*C)",
    "P3 (conceptual): monta el diodo en polaridad inversa y no lo advierte",
    "P3 (procedimental): da la corriente sin usar la ley de Ohm ni unidades",
    "general: no usa unidades SI en la mayoria de las magnitudes",
]

ENUNCIADO = r"""
\bandaTitulo{Examen Parcial 02}{Circuitos de Corriente Continua --- Electronica}

\noindent\textbf{Instrucciones:} cada pregunta se valora con \textbf{2 puntos};
total del examen \textbf{6 puntos}. Defienda su respuesta con la ley o el principio
que(use. Se acepta notacion sin unidades.

\section*{Pregunta 1 (2 puntos)}

Dos resistencias $R_1 = 470\,\Omega$ y $R_2 = 100\,\Omega$ estan conectadas en
serie sobre una fuente de $12\,\text{V}$. Calcule la tension que cae en $R_2$.

\section*{Pregunta 2 (2 puntos)}

Un condensador de $10\,\mu\text{F}$ se carga a traves de una resistencia de
$2.2\,\text{k}\Omega$. Explique que ocurre con el condensador en el instante en que
se retira la fuente de alimentacion y calcule el tiempo necesario para que se
descargue.

\section*{Pregunta 3 (2 puntos)}

Un diodo de silicio conduce con una caida de $0.7\,\text{V}$. Calcule la corriente
que atraviesa el diodo y la resistencia de $330\,\Omega$ conectadas en serie con
una fuente de $5\,\text{V}$, cuando el diodo se coloca con el anodigo hacia el
positivo de la fuente.

\newpage
\bandaTitulo{Examen Parcial 02}{Respuestas del estudiante}

\section*{Pregunta 1}

Las dos resistencias se conectan en serie, entonces el voltage se reparte a partes
iguales entre las dos. Como $12/2 = 6$, cada una tiene $6\,\text{V}$. En $R_2$ hay
$p = 470/570 = 0.82$ de los $12$, asi que en $R_2$ hay $12 * 0.82 = 9.9$.

\section*{Pregunta 2}

El condensador se descarga solo cuando se quita la fuente. La constante de tiempo
es $\tau = C/R = 10\,\mu\text{F} / 2.2\,\text{k}\Omega$, y el condensador se descarga
cuando pasan cinco constantes de tiempo.

\section*{Pregunta 3}

Puse el diodo con la banda hacia el positivo de la fuente, que es la forma correcta
de conectarlo en el dibujo. La corriente es $I = 5/330$, asi que la corriente que
pasa por el diodo es ese valor. No me acuerdo de las unidades.

\vfill
\noindent\fbox{Estudiante: Prueba Fixture --- INDICE 03}
"""

TEMPLATE = (PREAMBULO_INFOGRAFIA + "\n" + r"\begin{document}" + ENUNCIADO
            + r"\end{document}")


def main() -> int:
    destino = RAIZ / ".tmp"
    destino.mkdir(exist_ok=True)
    res = compile_latex_code(TEMPLATE, job_name="fixture_examen")
    if not res.get("success"):
        print("FALLO:", res.get("error", ""))
        return 1
    pdf = Path(res["pdf_path"])
    final = destino / "fixture_examen.pdf"
    final.write_bytes(pdf.read_bytes())
    print(f"PDF listo: {final}  ({final.stat().st_size} bytes)")
    print("Escala declarada en el enunciado: 6 puntos (3 preguntas de 2), NO suma 10")
    print(f"Errores deliberados insertados: {len(ERRORES_DELIBERADOS)}")
    for e in ERRORES_DELIBERADOS:
        print(f"  - {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
