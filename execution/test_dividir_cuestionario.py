#!/usr/bin/env python3
"""Pruebas de `execution/dividir_cuestionario.py` (capa 3).

Fijan el contrato que evita la fuga y la desincronización: la fuente generada no
puede llevar `**Answer:**` (el conversor la rechazaría y, peor, `_parsear_cuestionario`
pegaría pistas y explicaciones al texto de la última opción), las respuestas se
conservan íntegras, y la ida y vuelta (fuente + respuestas → clave) reproduce el
canónico. También que un canónico roto falle antes de escribir nada.

Ejecutar: python3 execution/test_dividir_cuestionario.py
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "execution/dividir_cuestionario.py"
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
    spec = importlib.util.spec_from_file_location("dividir_bajo_test", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


dividir_mod = _cargar()

CANONICO = """# ROL PRUEBA Cuestionario

> 2 preguntas

---

## pregunta 1

¿Cuál es la correcta?

- A. Primera opción.
- B. Segunda opción
  con continuación.

**Answer:** A. Primera opción.

**Hint:** Una pista que no debe filtrarse.

**Explanation:**

- A ✓ bien.
- B ✗ mal.

---

## pregunta 2

¿Y esta otra?

- A. Alfa.
- B. Beta.
- C. Gamma.

**Answer:** C. Gamma.

**Hint:** Otra pista.

**Explanation:**

- C ✓ bien.
"""


def _correr(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_division_basica() -> None:
    r = dividir_mod.dividir(CANONICO, "CYBERSEGURIDAD", 4)
    comprobar("cuenta las preguntas", r["n_preguntas"] == 2, str(r["n_preguntas"]))
    comprobar("extrae el título", r["titulo"] == "ROL PRUEBA Cuestionario", r["titulo"])
    comprobar("clave 1..N", r["clave"] == {1: "A", 2: "C"}, str(r["clave"]))
    fuente = r["fuente"]
    comprobar("la fuente no lleva **Answer:**", "**Answer:**" not in fuente)
    comprobar("la fuente no lleva **Hint:**", "**Hint:**" not in fuente)
    comprobar("la fuente no lleva **Explanation:**", "**Explanation:**" not in fuente)
    comprobar("la fuente no lleva pistas", "pista que no debe filtrarse" not in fuente)
    comprobar("usa `## Question N`", "## Question 1" in fuente and "## Question 2" in fuente)
    comprobar("la fuente trae las 4 marcas de opción de la pregunta 2", "- C. Gamma." in fuente)
    comprobar("front matter con titulo", 'titulo: "ROL PRUEBA Cuestionario"' in fuente)
    comprobar("front matter con grupos", "grupos: 4" in fuente)
    comprobar("front matter con curso", "curso: CYBERSEGURIDAD" in fuente)
    comprobar("front matter con tipo", "tipo: cuestionario" in fuente)
    comprobar(
        "las respuestas son el canónico íntegro",
        r["respuestas"].strip() == CANONICO.strip(),
    )
    comprobar(
        "las respuestas conservan pistas y explicaciones",
        "**Hint:**" in r["respuestas"] and "✓" in r["respuestas"],
    )


def test_ida_y_vuelta() -> None:
    r = dividir_mod.dividir(CANONICO, "CYBERSEGURIDAD", 4)
    try:
        dividir_mod._verificar(r["fuente"], r["respuestas"], r["clave"])
        ok, detalle = True, ""
    except ValueError as exc:
        ok, detalle = False, str(exc)
    comprobar("la ida y vuelta valida", ok, detalle)

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        fuente = base / "ROL_PRUEBA_Cuestionario.md"
        respuestas = base / "ROL_PRUEBA_Cuestionario_respuestas.md"
        fuente.write_text(r["fuente"], encoding="utf-8")
        respuestas.write_text(r["respuestas"], encoding="utf-8")
        datos = dividir_mod.md_a_html.cargar_clave(fuente, respuestas)
        comprobar("cargar_clave acepta lo generado", datos["clave"] == {1: "A", 2: "C"}, str(datos["clave"]))
        comprobar("cargar_clave cuenta 2 preguntas", datos["n_preguntas"] == 2)
        comprobar("cargar_clave lee grupos", datos["grupos"] == 4, str(datos["grupos"]))
        # La continuación de una opción se une en una sola línea, sin perder texto.
        comprobar(
            "une la continuación de opción",
            "Segunda opción con continuación." in fuente.read_text(encoding="utf-8"),
        )


def test_canonicos_invalidos() -> None:
    casos = {
        "sin Answer en una pregunta": CANONICO.replace("**Answer:** C. Gamma.\n", ""),
        "Answer que no es una opción": CANONICO.replace("**Answer:** C. Gamma.", "**Answer:** D. Gamma."),
        "numeración con hueco": CANONICO.replace("## pregunta 2", "## pregunta 3"),
        "letras de opción repetidas": CANONICO.replace("- C. Gamma.", "- B. Gamma."),
        "opción vacía": CANONICO.replace("- C. Gamma.", "- C."),
        "sin título": CANONICO.replace("# ROL PRUEBA Cuestionario\n", ""),
        "sin preguntas": "# Solo título\n",
    }
    for nombre, texto in casos.items():
        try:
            dividir_mod.dividir(texto, "CYBERSEGURIDAD", 4)
            fallo = False
        except ValueError:
            fallo = True
        comprobar(f"rechaza {nombre}", fallo)


def test_ya_dividido() -> None:
    fuente = dividir_mod.dividir(CANONICO, "CYBERSEGURIDAD", 4)["fuente"]
    try:
        dividir_mod.dividir(fuente, "CYBERSEGURIDAD", 4)
        fallo = False
        mensaje = ""
    except ValueError as exc:
        fallo = True
        mensaje = str(exc)
    comprobar("rechaza una fuente ya dividida", fallo)
    comprobar("explica por qué no la sobrescribe", "ya está dividido" in mensaje, mensaje)


def test_titulo_con_caracteres_especiales() -> None:
    texto = CANONICO.replace("# ROL PRUEBA Cuestionario", '# ROL "PRUEBA": cuestionario')
    r = dividir_mod.dividir(texto, "CYBERSEGURIDAD", 2)
    meta, _ = dividir_mod.md_a_html._leer_front_matter(r["fuente"])
    comprobar(
        "el título con comillas y dos puntos sobrevive al YAML",
        meta.get("titulo") == 'ROL "PRUEBA": cuestionario',
        str(meta.get("titulo")),
    )


def test_normalizacion_ancho_completo() -> None:
    """U+FF1B rompe `verificar_texto.py`; el divisor lo pasa a ASCII y lo cuenta."""
    texto = CANONICO.replace(
        "Primera opción.",
        "Primera opción\uff1bsegunda parte.",
    )
    r = dividir_mod.dividir(texto, "CYBERSEGURIDAD", 2)
    comprobar(
        "cuenta los signos de ancho completo sustituidos (opción y respuesta)",
        r["normalizaciones"] == 2,
        str(r["normalizaciones"]),
    )
    comprobar(
        "la fuente no conserva U+FF1B",
        "\uff1b" not in r["fuente"],
    )
    comprobar(
        "la fuente lleva el equivalente ASCII",
        "Primera opción; segunda parte." in r["fuente"],
    )
    comprobar(
        "las respuestas tampoco conservan U+FF1B",
        "\uff1b" not in r["respuestas"],
    )
    comprobar(
        "el texto normalizado sigue casando en la ida y vuelta",
        r["clave"] == {1: "A", 2: "C"},
        str(r["clave"]),
    )
    limpio = dividir_mod.dividir(CANONICO, "CYBERSEGURIDAD", 2)
    comprobar(
        "un canónico limpio reporta 0 normalizaciones",
        limpio["normalizaciones"] == 0,
        str(limpio["normalizaciones"]),
    )


def test_cli() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        canonico = base / "ROL_PRUEBA_Cuestionario.md"
        canonico.write_text(CANONICO, encoding="utf-8")

        proc = _correr(["--canonico", str(canonico), "--dry-run", "--json"])
        comprobar("--dry-run sale 0", proc.returncode == 0, proc.stderr[-300:])
        comprobar("--dry-run no escribe la fuente", canonico.read_text(encoding="utf-8") == CANONICO)
        comprobar(
            "--dry-run no escribe respuestas",
            not (base / "ROL_PRUEBA_Cuestionario_respuestas.md").exists(),
        )
        if proc.returncode == 0:
            datos = json.loads(proc.stdout)
            comprobar("el JSON trae la clave", datos.get("clave") == "A C", str(datos.get("clave")))
            comprobar("el JSON marca dry_run", datos.get("dry_run") is True)
            comprobar(
                "el JSON reporta las normalizaciones",
                datos.get("normalizaciones") == 0,
                str(datos.get("normalizaciones")),
            )

        proc = _correr(["--canonico", str(canonico), "--json"])
        comprobar("escribe en sitio y sale 0", proc.returncode == 0, proc.stderr[-300:])
        comprobar(
            "la fuente en disco queda sin clave",
            "**Answer:**" not in canonico.read_text(encoding="utf-8"),
        )
        respuestas = base / "ROL_PRUEBA_Cuestionario_respuestas.md"
        comprobar("crea el hermano de respuestas", respuestas.exists())
        comprobar(
            "el hermano es el canónico íntegro",
            respuestas.read_text(encoding="utf-8").strip() == CANONICO.strip(),
        )
        if proc.returncode == 0:
            datos = json.loads(proc.stdout)
            comprobar(
                "verifica con cargar_clave al escribir",
                datos.get("cargar_clave", {}).get("clave") == "A C",
                str(datos.get("cargar_clave")),
            )

        # Segunda pasada: la fuente ya está dividida, debe negarse.
        proc = _correr(["--canonico", str(canonico)])
        comprobar("una segunda pasada sale 3", proc.returncode == 3, str(proc.returncode))

        # Hermano con otro contenido y sin --forzar: no se pisa.
        respuestas.write_text("# otro\n", encoding="utf-8")
        proc = _correr(["--canonico", str(respuestas), "--respuestas", str(respuestas)])
        comprobar("fuente y respuestas iguales sale 3", proc.returncode == 3, str(proc.returncode))

        proc = _correr(["--canonico", str(canonico), "--grupos", "0"])
        comprobar("--grupos fuera de rango sale 3", proc.returncode == 3, str(proc.returncode))


def main() -> int:
    print("test_dividir_cuestionario")
    test_division_basica()
    test_ida_y_vuelta()
    test_canonicos_invalidos()
    test_ya_dividido()
    test_titulo_con_caracteres_especiales()
    test_normalizacion_ancho_completo()
    test_cli()
    print(f"\n{PRUEBAS - len(FALLOS)}/{PRUEBAS} aserciones OK")
    if FALLOS:
        print("FALLOS: " + ", ".join(FALLOS))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
