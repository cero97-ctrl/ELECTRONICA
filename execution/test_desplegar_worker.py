#!/usr/bin/env python3
"""Pruebas de la resolución del token de resultados en `flujo_desplegar_worker_cuestionarios.py`.

Lo que este test protege, y por qué importa:

  **El token equivocado no falla al desplegar: falla en la primera entrega.**
  Cada curso archiva en su propio repo de resultados y su PAT fine-grained suele
  estar scoped a él. Si el flujo sube a `lab2` el token de `lab1`, wrangler acepta
  el secreto sin chistar, `/salud` responde `ok` y el Worker solo revienta cuando
  el primer alumno envía (502, `no se pudo registrar la entrega`). Por eso la
  precedencia `GITHUB_TOKEN_RESULTADOS_<ENTORNO>` → `GITHUB_TOKEN_RESULTADOS` se
  comprueba aquí y no en producción.

También se fija que `main()` pase el entorno a la resolución: sin `args.env` la
función siempre devolvería el token genérico y la precedencia sería decorativa.

Ejecutar: python3 execution/test_desplegar_worker.py
Salida: 0 si todas las aserciones pasan, 1 si alguna falla.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "flujo_desplegar_worker_cuestionarios.py"
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
    spec = importlib.util.spec_from_file_location("desplegar_bajo_test", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_precedencia(mod) -> None:
    print("precedencia del token")
    entorno = {
        "GITHUB_TOKEN_RESULTADOS": "generico",
        "GITHUB_TOKEN_RESULTADOS_LAB2": "especifico",
        "GITHUB_TOKEN_RESULTADOS_LAB_2": "con-guion",
        "GITHUB_TOKEN": "general-no-usar",
    }
    mod._entorno = lambda: dict(entorno)

    comprobar(
        "el token del entorno gana al generico",
        mod._token_resultados("lab2") == "especifico",
    )
    comprobar(
        "sin --env se usa el generico",
        mod._token_resultados(None) == "generico",
    )
    comprobar(
        "un entorno sin token propio cae al generico (lab1)",
        mod._token_resultados("lab1") == "generico",
    )
    comprobar(
        "el GITHUB_TOKEN general nunca se usa como token de resultados",
        mod._token_resultados("azul") == "generico",
    )
    comprobar(
        "el nombre del entorno se normaliza a mayusculas y guion bajo",
        mod._token_resultados("lab-2") == "con-guion",
    )
    comprobar(
        "un --env ya en mayusculas resuelve igual",
        mod._token_resultados("LAB2") == "especifico",
    )


def test_fallbacks(mod) -> None:
    print("ausencias y valores vacios")
    mod._entorno = lambda: {"GITHUB_TOKEN_RESULTADOS": "generico"}
    comprobar(
        "sin el especifico, cae al generico",
        mod._token_resultados("lab2") == "generico",
    )

    mod._entorno = lambda: {
        "GITHUB_TOKEN_RESULTADOS": "generico",
        "GITHUB_TOKEN_RESULTADOS_LAB2": "   ",
    }
    comprobar(
        "un especifico en blanco no cuenta como token",
        mod._token_resultados("lab2") == "generico",
    )

    mod._entorno = lambda: {}
    comprobar("sin ningun token devuelve None", mod._token_resultados("lab2") is None)
    comprobar("sin ningun token y sin env devuelve None", mod._token_resultados(None) is None)


def test_main_pasa_el_entorno(mod) -> None:
    print("integracion con main()")
    texto = SCRIPT.read_text(encoding="utf-8")
    comprobar(
        "main() resuelve el token con args.env",
        "_token_resultados(args.env)" in texto,
        "sin args.env la precedencia por entorno nunca se aplicaria",
    )
    comprobar(
        "el flujo no resuelve el token sin entorno",
        "_token_resultados()" not in texto,
    )
    comprobar(
        "el mensaje de error nombra la convencion por entorno",
        "GITHUB_TOKEN_RESULTADOS_<ENTORNO>" in texto,
    )


def main() -> int:
    mod = _cargar()
    test_precedencia(mod)
    test_fallbacks(mod)
    test_main_pasa_el_entorno(mod)
    print(f"\n{PRUEBAS - len(FALLOS)}/{PRUEBAS} aserciones OK")
    if FALLOS:
        print("FALLOS: " + ", ".join(FALLOS))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
