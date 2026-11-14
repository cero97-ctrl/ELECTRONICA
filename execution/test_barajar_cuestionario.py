#!/usr/bin/env python3
"""Pruebas de `execution/barajar_cuestionario.py` (capa 3 del barajado).

Fijan el contrato: el barajado es determinista (misma semilla -> mismo texto),
nunca cambia el contenido de una pregunta (solo el orden de sus opciones), la
respuesta correcta sigue apuntando al mismo texto, las viñetas de la
explicación se remapean con la misma permutación, y una clave concentrada se
detecta como degenerada.

Ejecutar: python3 execution/test_barajar_cuestionario.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FALLOS: list[str] = []
PRUEBAS = 0


def comprobar(nombre: str, condicion: bool, detalle: str = "") -> None:
    global PRUEBAS
    PRUEBAS += 1
    if condicion:
        print(f"  ok   {nombre}")
    else:
        print(f"  FALLA {nombre}" + (f" -- {detalle}" if detalle else ""))
        FALLOS.append(nombre)


def _cargar():
    spec = importlib.util.spec_from_file_location(
        "barajar_bajo_test", RAIZ / "execution/barajar_cuestionario.py"
    )
    modulo = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


B = _cargar()
MD = B.md_a_html

CANONICO = """---
titulo: Cuestionario de prueba
curso: CURSO
grupos: 4
justificacion_items: [2]
---

# Cuestionario de prueba

## Pregunta 1

¿Cuál es la salida de `echo $((2+2))`?

- A. 3
- B. 4
- C. 5
- D. 22

**Answer:** B. 4

**Explanation:**
- A ✗ se olvidó de sumar
- B ✓ la suma es 4
- C ✗ sumó de más
- D ✗ concatenó

## Pregunta 2

¿Qué muestra `git status` tras un `git add`?

- A. El archivo en el área de preparación
- B. El archivo sin seguimiento
- C. El commit anterior

**Answer:** A. El archivo en el área de preparación

**Justificación:** Cita la salida de `git status --porcelain` de tu repositorio y el archivo concreto que preparaste, con la ruta y la letra que devolvió.

**Explanation:**
- A ✓ queda en staging
- B ✗ sin seguimiento es `??`
- C ✗ no lista commits

## Pregunta 3

¿Qué hace `chmod 600`?

- A. Lectura y escritura para el dueño
- B. Solo lectura para todos
- C. Ejecución para todos

**Answer:** C. Ejecución para todos

**Explanation:**
- A ✗ eso es 600 sin ejecución... pero es la correcta del texto
- B ✗ 444
- C ✓ así lo dice el enunciado
"""


def test_permutacion() -> None:
    print("\n-- Permutación determinista")
    a = B._permutacion("sem", 1, 5)
    b = B._permutacion("sem", 1, 5)
    comprobar("misma semilla -> misma permutación", a == b, str((a, b)))
    comprobar("es una permutación", sorted(a) == list(range(5)), str(a))
    comprobar("la semilla incluye la pregunta", B._permutacion("sem", 1, 5) != B._permutacion("sem", 2, 5))
    comprobar("n=1 es trivial", B._permutacion("sem", 9, 1) == [0])


def test_degenerada() -> None:
    print("\n-- Clave degenerada")
    comprobar("10 de 10 iguales", B._clave_degenerada({n: "A" for n in range(1, 11)}))
    comprobar(
        "5 de 10 no es degenerada",
        not B._clave_degenerada({n: "A" if n <= 5 else "B" for n in range(1, 11)}),
    )
    comprobar("6 de 10 sí", B._clave_degenerada({n: "A" if n <= 6 else "B" for n in range(1, 11)}))
    comprobar("clave vacía", not B._clave_degenerada({}))


def test_barajar() -> None:
    print("\n-- Barajado")
    uno, informe1 = B.barajar(CANONICO, "semilla")
    dos, informe2 = B.barajar(CANONICO, "semilla")
    comprobar("determinista", uno == dos)
    comprobar("informe determinista", informe1["clave_despues"] == informe2["clave_despues"])
    comprobar("barajó las tres preguntas", informe1["preguntas_barajadas"] == 3)
    comprobar("no cambia el número de preguntas", len(MD._parsear_respuestas(uno)) == 3)

    original = MD._parsear_respuestas(CANONICO)
    nuevo = MD._parsear_respuestas(uno)
    for antes, despues in zip(original, nuevo):
        n = antes["numero"]
        comprobar(f"pregunta {n}: mismo enunciado", antes["enunciado"] == despues["enunciado"])
        comprobar(
            f"pregunta {n}: mismas opciones (multiconjunto)",
            sorted(o["texto"] for o in antes["opciones"]) == sorted(o["texto"] for o in despues["opciones"]),
        )
        comprobar(
            f"pregunta {n}: misma respuesta correcta",
            next(o["texto"] for o in antes["opciones"] if o["letra"] == antes["respuesta"])
            == next(o["texto"] for o in despues["opciones"] if o["letra"] == despues["respuesta"]),
        )
        comprobar(
            f"pregunta {n}: misma justificación",
            antes.get("justificacion", "") == despues.get("justificacion", ""),
        )
        comprobar(
            f"pregunta {n}: letras consecutivas",
            [o["letra"] for o in despues["opciones"]] == list("ABCD"[: len(despues["opciones"])]),
        )

    comprobar("la justificación sigue en la pregunta 2", "git status --porcelain" in uno)
    comprobar("el front matter sobrevive", uno.startswith("---\ntitulo: Cuestionario de prueba"))
    comprobar("la sección no-pregunta sobrevive", "# Cuestionario de prueba" in uno)
    comprobar(
        "las viñetas de la explicación se remapean",
        _vinetas_coherentes(uno),
    )

    otro, _ = B.barajar(CANONICO, "otra-semilla")
    comprobar("otra semilla cambia al menos una pregunta", otro != uno)

    with_just = [p for p in nuevo if p["numero"] == 2][0]
    comprobar("la pregunta con justificación se detecta", bool(with_just.get("justificacion")))


def _vinetas_coherentes(texto: str) -> bool:
    """Cada `- X ✓` de la explicación apunta a la letra de la respuesta."""
    preguntas = MD._parsear_respuestas(texto)
    for p in preguntas:
        for linea in p.get("explicacion", []):
            marca = B.VINETA.match(linea.strip())
            if marca and marca.group(2) == "✓":
                if marca.group(1) != p["respuesta"]:
                    return False
    return True


def test_errores() -> None:
    print("\n-- Entradas que deben fallar ruidosamente")
    for nombre, texto in [
        ("sin preguntas", "# nada\n"),
        ("sin Answer", CANONICO.replace("**Answer:** B. 4\n", "")),
        (
            "una sola opción",
            CANONICO.replace("- B. 4\n", "")
            .replace("- C. 5\n", "")
            .replace("- D. 22\n", "")
            .replace("**Answer:** B. 4", "**Answer:** A. 3"),
        ),
        ("respuesta fuera de opciones", CANONICO.replace("**Answer:** B. 4", "**Answer:** F. 4")),
    ]:
        try:
            B.barajar(texto, "s")
        except ValueError as exc:
            comprobar(f"{nombre} -> ValueError", True, str(exc))
        else:
            comprobar(f"{nombre} -> ValueError", False, "no lanzó")

    bueno = CANONICO.replace("**Answer:** B. 4", "**Answer:** A. 4")
    try:
        B.barajar(bueno, "s")
    except ValueError:
        comprobar("respuesta con texto incoherente no revienta el parser", False, "lanzó")
    else:
        comprobar("respuesta con texto incoherente no revienta el parser", True)


def main() -> int:
    print("Pruebas de execution/barajar_cuestionario.py")
    test_permutacion()
    test_degenerada()
    test_barajar()
    test_errores()
    print(f"\n{PRUEBAS - len(FALLOS)}/{PRUEBAS} aserciones OK")
    if FALLOS:
        print("FALLOS:")
        for f in FALLOS:
            print(f"  - {f}")
        return 1
    print("Sin fallos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
