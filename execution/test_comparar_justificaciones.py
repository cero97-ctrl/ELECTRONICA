#!/usr/bin/env python3
"""Contratos de la tabla comparativa (sin red y sin compilar)."""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "execution"))
import comparar_justificaciones as C  # noqa: E402

PRUEBAS = 0


def comprobar(nombre: str, condicion: bool, detalle: str = "") -> None:
    global PRUEBAS
    PRUEBAS += 1
    if not condicion:
        raise AssertionError(f"{nombre}: {detalle}")


ORIGINAL = """# Prueba

## Pregunta 1

¿Uno o dos?

- A. Uno.

**Respuesta:** A. Uno.

**Explicación:**

- A ✓ Es la definición correcta.
- B ✗ No corresponde.

## Pregunta 2

¿Sí o no?

- A. Sí.

**Respuesta:** A. Sí.

**Explicación:**

- A ✓ Coincide con el enunciado.
- B ✗ Contradice el enunciado.
"""


def cuestionario_falso() -> dict:
    referencias = C.extraer_referencias(ORIGINAL)
    return {
        "id": "rol_prueba_s2",
        "titulo": "Prueba",
        "items": [1, 2],
        "referencias": referencias,
        "registros": [
            {
                "grupo": 1,
                "cedula": "V-12345678",
                "nombre": "Pérez, Ana",
                "nota_recalculada": 10.0,
                "archivo": "resultados/rol_prueba_s2/grupo_01/V-12345678.json",
                "justificaciones": {
                    "1": "Porque la definición coincide | y el otro no.",
                    "2": "",
                },
                "avisos": [],
            },
            {
                "grupo": 2,
                "cedula": "V-87654321",
                "nombre": "López, Luis",
                "nota_recalculada": 8.0,
                "archivo": "resultados/rol_prueba_s2/grupo_02/V-87654321.json",
                "justificaciones": {"1": "Otra explicación.", "2": "También."},
                "avisos": ["la justificación de la pregunta 2 es casi idéntica a la de V-12345678"],
            },
        ],
        "respuestas_por_archivo": {
            "resultados/rol_prueba_s2/grupo_01/V-12345678.json": {"1": "A", "2": "B"},
            "resultados/rol_prueba_s2/grupo_02/V-87654321.json": {"1": "A", "2": "A"},
        },
    }


def main() -> None:
    referencias = C.extraer_referencias(ORIGINAL)
    comprobar("dos referencias", sorted(referencias) == [1, 2], str(sorted(referencias)))
    comprobar(
        "respuesta literal",
        referencias[1]["respuesta"] == "A. Uno.",
        referencias[1]["respuesta"],
    )
    comprobar(
        "razones con marca",
        [r["correcta"] for r in referencias[1]["razones"]] == [True, False],
        str(referencias[1]["razones"]),
    )

    for nombre, texto in (
        ("sin respuestas", ORIGINAL.replace("**Respuesta:** A. Uno.", "nada")),
        ("sin explicación", ORIGINAL.replace("**Explicación:**", "Sin explicación:")),
        ("sin razones", ORIGINAL.replace("- A ✓ Es la definición correcta.", "").replace("- B ✗ No corresponde.", "")),
        ("numeración con hueco", ORIGINAL.replace("## Pregunta 2", "## Pregunta 3")),
    ):
        try:
            C.extraer_referencias(texto)
        except C.ComparacionError:
            comprobar(f"{nombre} rechazado", True)
        else:
            comprobar(f"{nombre} rechazado", False)

    for archivo in sorted(
        (RAIZ / "cursos/CYBERSEGURIDAD/evaluaciones/web/SEMANA_02/fuentes").glob(
            "ROL_*_original_con_respuestas.md"
        )
    ):
        reales = C.extraer_referencias(archivo.read_text(encoding="utf-8"))
        comprobar(
            f"{archivo.name}: 10 referencias",
            sorted(reales) == list(range(1, 11)),
            str(sorted(reales)),
        )
        comprobar(
            f"{archivo.name}: razones en todas",
            all(r["razones"] for r in reales.values()),
        )

    comprobar(
        "celda Markdown sin saltos y con pipe escapado",
        C.celda_md("a|b\nc") == r"a\|b c",
        C.celda_md("a|b\nc"),
    )
    tex = C.celda_tex("50% & x_y ✓ `code`")
    for esperado in (r"\%", r"\&", r"\_", "(correcta)"):
        comprobar(f"escape LaTeX {esperado}", esperado in tex, tex)
    comprobar("sin backticks en LaTeX", "`" not in tex, tex)
    referencia_md = C.referencia_md(referencias[1])
    comprobar(
        "referencia legible",
        "Respuesta: A. Uno." in referencia_md and "✓" in referencia_md,
        referencia_md,
    )

    cuestionario = cuestionario_falso()
    filas = C.armar_filas([cuestionario])
    comprobar("una fila por alumno y pregunta", len(filas) == 4, str(len(filas)))
    primera = filas[0]
    comprobar("texto del alumno", "definición coincide" in primera["justificacion"])
    comprobar("respuesta del alumno", primera["respuesta"] == "A")
    comprobar("sin texto marcado", filas[1]["estado"] == "sin texto", filas[1]["estado"])
    comprobar("copiada marcada", filas[3]["estado"] == "copiada", filas[3]["estado"])
    comprobar(
        "determinismo de filas", C.armar_filas([cuestionario]) == filas
    )

    md = C.markdown_tabla(filas, [cuestionario])
    comprobar("resumen de filas", "> filas: 4" in md)
    comprobar("pipe escapado en tabla", r"a\|b" not in md and "definición coincide \\|" in md)
    comprobar("columna de veredicto vacía", "Veredicto docente |" in md)
    comprobar("markdown determinista", C.markdown_tabla(filas, [cuestionario]) == md)

    tex_completo = C.latex_tabla(filas, [cuestionario])
    comprobar("documento cerrado", tex_completo.rstrip().endswith(r"\end{document}"))
    comprobar("longtable", r"\begin{longtable}" in tex_completo)
    comprobar("sin unicode ✓/✗ en LaTeX", "✓" not in tex_completo and "✗" not in tex_completo)
    comprobar("veredicto en blanco", r"\underline{\hspace{0.9cm}}" in tex_completo)
    comprobar("markdown no califica", "No califica" in md)

    comprobar(
        "salida temporal permitida",
        C.D._git_ignorado(RAIZ / ".tmp" / "comparativa.md"),
    )
    comprobar(
        "salida pública rechazada",
        not C.D._git_ignorado(RAIZ / "README.md"),
    )

    print(f"OK: {PRUEBAS} aserciones de comparativa de justificaciones")


if __name__ == "__main__":
    main()
