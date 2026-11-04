#!/usr/bin/env python3
"""
test_ocr_pdf_escaneado.py — Regresión de las funciones puras del OCR
(Layer 3: Execution; NO toca la red ni un PDF real).

Por qué existe: `ocr_pdf_escaneado.py` decide qué páginas pedir, cómo partir la
respuesta del modelo y cuándo una transcripción es aceptable. Esas tres
decisiones son las que convierten una cuota agotada en trabajo perdido o una
página ilegible en dato bueno, y las tres son funciones puras: se pueden fijar
con pruebas sin invocar a Gemini ni abrir un PDF.

Lo que se congela aquí, cada bloque contra una clase de fallo real:

  1. `parse_paginas` — un rango mal escrito no debe pedir páginas de otro
     documento ni caer en silencio: '5-2' se ordena, '1,1-3' no duplica, y una
     página fuera del PDF es ValueError, no una petición de más.
  2. `dividir_lotes` — el tamaño de lote es el presupuesto de tokens por
     petición; partir mal significa respuestas truncadas a mitad de marca.
  3. `dividir_respuesta` — el modelo a veces numera mal u omite marcas; una
     página que no se pidió NUNCA debe colarse en el resultado, y un lote de una
     sola página sin marca se acepta (el modelo obedece a medias).
  4. `validar_pagina` — el umbral de aceptabilidad: una página de dos líneas no
     es una transcripción, y una página dominada por [ILEGIBLE] tampoco.
  5. El retry budget y la detección de cuota: máx 3 intentos (la política del
     framework) y 429/RESOURCE_EXHAUSTED/QUOTA son cuota, no bug de transporte.

Uso:  python3 execution/test_ocr_pdf_escaneado.py
Salida: 0 = todas las aserciones pasan; 1 = hay regresión.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ocr_pdf_escaneado as O  # noqa: E402

fallos: list[str] = []
ok = 0


def comprobar(condicion: bool, mensaje: str) -> None:
    global ok
    if condicion:
        ok += 1
    else:
        fallos.append(mensaje)


# ── 1. parse_paginas ──────────────────────────────────────────────────────────
def test_parse_paginas() -> None:
    comprobar(O.parse_paginas("1-3", 10) == [1, 2, 3], "rango simple")
    comprobar(O.parse_paginas("3,1-2", 10) == [1, 2, 3], "lista y rango se fusionan sin duplicar")
    comprobar(O.parse_paginas("5-2", 10) == [2, 3, 4, 5], "rango invertido se ordena")
    comprobar(O.parse_paginas(None, 4) == [1, 2, 3, 4], "sin spec son todas las páginas")
    comprobar(O.parse_paginas("todas", 3) == [1, 2, 3], "'todas' es sinónimo de None")
    comprobar(O.parse_paginas(" 4 , 6 ", 6) == [4, 6], "espacios alrededor se toleran")

    for spec in ("57", "1-57", "0", "-3"):
        try:
            O.parse_paginas(spec, 56)
            comprobar(False, f"fuera de rango debe fallar: {spec!r}")
        except ValueError:
            comprobar(True, "")
    comprobar(
        all(_falla(lambda s=spec: O.parse_paginas(s, 56)) for spec in ("a", "1-", "uno-dos")),
        "spec no numérica es ValueError, no petición ciega",
    )


def _falla(fn) -> bool:
    try:
        fn()
        return False
    except ValueError:
        return True


# ── 2. dividir_lotes ──────────────────────────────────────────────────────────
def test_dividir_lotes() -> None:
    comprobar(O.dividir_lotes([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]], "el último lote puede ser menor")
    comprobar(O.dividir_lotes([], 4) == [], "sin páginas no hay lotes")
    comprobar(O.dividir_lotes([7], 4) == [[7]], "una página es un lote de una")
    try:
        O.dividir_lotes([1, 2], 0)
        comprobar(False, "lote 0 debe fallar")
    except ValueError:
        comprobar(True, "")


# ── 3. dividir_respuesta ──────────────────────────────────────────────────────
def test_dividir_respuesta() -> None:
    texto = (
        "@@@PAGINA: 3@@@\nley de ohm\n\n"
        "@@@PAGINA: 4@@@\npuente de wheatstone\n"
    )
    partes = O.dividir_respuesta(texto, [3, 4])
    comprobar(partes.get(3) == "ley de ohm", "el texto cae bajo su marca")
    comprobar(partes.get(4) == "puente de wheatstone", "la última marca llega al final del texto")

    colada = O.dividir_respuesta(texto + "@@@PAGINA: 9@@@\npágina que nadie pidió\n", [3, 4])
    comprobar(9 not in colada, "una página no pedida no se cuela en el resultado")

    sin_marcas = O.dividir_respuesta("texto suelto de una sola página", [7])
    comprobar(sin_marcas.get(7) == "texto suelto de una sola página", "lote de una página sin marca se acepta")

    sin_marcas_multi = O.dividir_respuesta("texto sin marcas", [7, 8])
    comprobar(sin_marcas_multi == {}, "lote multi-página sin marcas no se reparte a ciegas")

    mayusculas = O.dividir_respuesta("@@@pagina: 2@@@\ncache\n", [2])
    comprobar(mayusculas.get(2) == "cache", "la marca es insensible a mayúsculas")


# ── 4. validar_pagina ─────────────────────────────────────────────────────────
def test_validar_pagina() -> None:
    comprobar(O.validar_pagina("") == (True, True), "página vacía es válida y se marca vacía")
    comprobar(O.validar_pagina("[PAGINA VACIA]") == (True, True), "marca de vacía explícita")
    comprobar(O.validar_pagina("corto") == (False, False), "página de dos líneas no es transcripción")
    buena = "texto suficiente " * 10
    comprobar(O.validar_pagina(buena) == (True, False), "página normal es aceptable")
    ilegible = "[ILEGIBLE] " * 20
    comprobar(O.validar_pagina(ilegible) == (False, False), "página dominada por [ILEGIBLE] se rechaza")
    mixta = "[ILEGIBLE] " + "texto legible que compensa " * 10
    comprobar(O.validar_pagina(mixta) == (True, False), "un tramo ilegible acotado no tumba la página")


# ── 5. Retry budget y detección de cuota ──────────────────────────────────────
def test_budget_y_cuota() -> None:
    comprobar(O.MAX_INTENTOS == 3, "el retry budget del OCR es el del framework: máx 3")
    for marca in ("429 RESOURCE_EXHAUSTED", "quota exceeded for model", "HTTP 429: Too Many Requests"):
        comprobar(O._es_limite_cuota(Exception(marca)), f"cuota detectada: {marca!r}")
    for otra in ("Connection reset by peer", "invalid api key", "timeout"):
        comprobar(not O._es_limite_cuota(Exception(otra)), f"no es cuota: {otra!r}")


def main() -> int:
    print("Pruebas del OCR de PDF escaneado (funciones puras)")
    test_parse_paginas()
    test_dividir_lotes()
    test_dividir_respuesta()
    test_validar_pagina()
    test_budget_y_cuota()

    print()
    if fallos:
        print(f"FALLOS: {len(fallos)}/{ok + len(fallos)}")
        for fallo in fallos:
            print(f"  - {fallo}")
        return 1
    print(f"Aserciones OK: {ok}   Fallos: 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
