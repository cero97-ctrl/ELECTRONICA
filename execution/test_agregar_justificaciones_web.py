#!/usr/bin/env python3
"""Contratos del insertador de justificaciones (sin red ni archivos reales)."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "execution"))
import agregar_justificaciones_web as A  # noqa: E402

PRUEBAS = 0


def comprobar(nombre: str, condicion: bool, detalle: str = "") -> None:
    global PRUEBAS
    PRUEBAS += 1
    if not condicion:
        raise AssertionError(f"{nombre}: {detalle}")


FUENTE = """---
curso: CYBERSEGURIDAD
titulo: "Prueba"
grupo: "Rol Rojo"
aviso: "Sin consultar el repo."
---

# Prueba

## Pregunta 1

¿A o B?

- A. Uno.
- B. Dos.

## Pregunta 2

¿Sí o no?

- A. Sí.
- B. No.
"""

RESP = """# Prueba — respuestas

## Pregunta 1

¿A o B?

- A. Uno.
- B. Dos.

**Answer:** A. Uno.

## Pregunta 2

¿Sí o no?

- A. Sí.
- B. No.

**Answer:** B. No.
"""


def main() -> None:
    cabecera, cuerpo = A.dividir_front(FUENTE)
    items = A.numeros_de(cuerpo)
    comprobar("dos preguntas", items == [1, 2], str(items))
    nueva = A.insertar(cuerpo, items, A.INSTRUCCION)
    comprobar("una instrucción por pregunta", nueva.count("**Justificación:**") == 2)
    primera = nueva.split("## Pregunta 2")[0]
    comprobar(
        "va después de la última opción",
        primera.rstrip().endswith(A.INSTRUCCION),
        primera[-200:],
    )
    comprobar(
        "idempotente",
        A.insertar(nueva, items, A.INSTRUCCION).count("**Justificación:**") == 2,
    )
    forzada = A.insertar(nueva, items, "Otra instrucción distinta.", forzar=True)
    comprobar("--forzar reemplaza", forzada.count("Otra instrucción distinta.") == 2)
    cab = A.actualizar_front(cabecera + ["justificacion_items: [9]", "grupos: 1"], items, 4)
    comprobar("sin clave justificacion duplicada", sum(1 for l in cab if l.startswith("justificacion_items:")) == 1)
    comprobar("sin clave grupos duplicada", sum(1 for l in cab if l.startswith("grupos:")) == 1)
    comprobar("grupos correcto", "grupos: 4" in cab, str(cab))

    with tempfile.TemporaryDirectory(dir=RAIZ / ".tmp") as temporal:
        tmp = Path(temporal)
        f = tmp / "ROL_ROJO_CUESTIONARIO_S2.md"
        r = tmp / "ROL_ROJO_CUESTIONARIO_S2_respuestas.md"
        f.write_text(FUENTE, encoding="utf-8")
        r.write_text(RESP, encoding="utf-8")
        limpia, solucionario, recuperados = A.armar(f, A.INSTRUCCION, False)
        f.write_text(limpia, encoding="utf-8")
        r.write_text(solucionario, encoding="utf-8")
        A._validar_en_temporal(limpia, solucionario)
        comprobar("items recuperados", recuperados == [1, 2], str(recuperados))
        comprobar("respuestas espejo", solucionario.count("**Justificación:**") == 2)

    try:
        A.numeros_de("## Pregunta 1\n\n- A. x.\n\n## Pregunta 3\n\n- A. y.\n")
    except A.JustificacionError:
        comprobar("numeración con hueco rechazada", True)
    else:
        comprobar("numeración con hueco rechazada", False)

    print(f"OK: {PRUEBAS} aserciones de justificaciones web")


if __name__ == "__main__":
    main()
