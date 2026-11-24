#!/usr/bin/env python3
"""Pruebas puras de la guía teórica semanal (`execution/generar_guia_teorica.py`).

Fijan el contrato del workflow de 3 capas sin red y sin compilación: el
descriptor se parsea, la semana sin `teoria:` se rechaza antes de escribir, los
cinco temas de la semana 02 están presentes, el texto es determinista y el
documento es material de estudio (no un examen).

Ejecutar: python3 execution/test_guia_teorica.py
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CURSO = RAIZ / "cursos" / "CYBERSEGURIDAD" / "curso.yaml"
FALLOS: list[str] = []
PRUEBAS = 0


def comprobar(nombre: str, condicion: bool, detalle: str = "") -> None:
    global PRUEBAS
    PRUEBAS += 1
    if not condicion:
        FALLOS.append(f"{nombre}" + (f" — {detalle}" if detalle else ""))


def cargar_modulo():
    ruta = RAIZ / "execution" / "generar_guia_teorica.py"
    espec = importlib.util.spec_from_file_location("generar_guia_teorica", ruta)
    modulo = importlib.util.module_from_spec(espec)
    sys.modules[espec.name] = modulo
    espec.loader.exec_module(modulo)
    return modulo


MOD = cargar_modulo()
DESCRIPTOR = MOD.cargar_descriptor(CURSO)
SEMANA2 = MOD.semana_de(DESCRIPTOR, 2)


def test_parseo_del_descriptor() -> None:
    comprobar("el descriptor carga como mapa", isinstance(DESCRIPTOR, dict))
    comprobar("la semana 02 existe", SEMANA2["numero"] == 2)
    comprobar(
        "el título de la semana coincide con el descriptor",
        SEMANA2["titulo"] == "Criptografía aplicada y gestión de secretos",
        str(SEMANA2.get("titulo")),
    )
    comprobar(
        "el bloque teoria es un mapa",
        isinstance(SEMANA2.get("teoria"), dict),
    )
    comprobar(
        "la semana 99 no existe",
        _sin_excepcion(lambda: MOD.semana_de(DESCRIPTOR, 99)) is False,
    )


def _sin_excepcion(fn) -> bool:
    try:
        fn()
    except (ValueError, KeyError, TypeError):
        return False
    return True


def test_validacion() -> None:
    comprobar(
        "la semana 02 es válida",
        MOD.validar_guia(DESCRIPTOR, 2) == [],
        str(MOD.validar_guia(DESCRIPTOR, 2)),
    )
    sin_teoria = copy.deepcopy(DESCRIPTOR)
    for semana in sin_teoria["semanas"]:
        if semana["numero"] == 2:
            del semana["teoria"]
    problemas = MOD.validar_guia(sin_teoria, 2)
    comprobar(
        "la semana sin teoria se rechaza",
        any("teoria" in p for p in problemas),
        str(problemas),
    )

    inexistente = MOD.validar_guia(DESCRIPTOR, 99)
    comprobar(
        "la semana inexistente se rechaza",
        any("no existe" in p for p in inexistente),
        str(inexistente),
    )

    anchos = copy.deepcopy(DESCRIPTOR)
    tabla = next(s for s in anchos["semanas"] if s["numero"] == 2)["teoria"]["tabla"]
    tabla["anchos"] = [20.0] * len(tabla["columnas"])
    problemas = MOD.validar_guia(anchos, 2)
    comprobar(
        "una tabla que no cabe en el margen se rechaza",
        any("no caben en el margen" in p for p in problemas),
        str(problemas),
    )

    celdas = copy.deepcopy(DESCRIPTOR)
    tabla = next(s for s in celdas["semanas"] if s["numero"] == 2)["teoria"]["tabla"]
    tabla["filas"][0][0] = False
    problemas = MOD.validar_guia(celdas, 2)
    comprobar(
        "una celda booleana se rechaza antes de compilar",
        any("no es texto" in p for p in problemas),
        str(problemas),
    )


def test_determinismo_y_bytes() -> None:
    tex1 = MOD.tex_guia(DESCRIPTOR, 2)
    tex2 = MOD.tex_guia(copy.deepcopy(DESCRIPTOR), 2)
    comprobar("mismo descriptor → mismos bytes del .tex", tex1 == tex2)
    comprobar(
        "el texto no depende de la hora del sistema",
        "datetime" not in tex1 and "time.time" not in tex1,
    )
    comprobar(
        "el sha256 del .tex es estable",
        hashlib.sha256(tex1.encode("utf-8")).hexdigest()
        == hashlib.sha256(tex2.encode("utf-8")).hexdigest(),
    )


def test_los_cinco_temas() -> None:
    temas = SEMANA2["teoria"]["temas"]
    comprobar("la semana 02 declara cinco temas", len(temas) == 5, str(len(temas)))
    esperados = [
        ("GCM", "integridad"),
        ("RSA", "curvas elípticas"),
        ("HMAC", "Argon2"),
        ("TLS 1.3", "certificados"),
        ("secretos", "repositorios"),
    ]
    for indice, (palabra_a, palabra_b) in enumerate(esperados):
        titulo = str(temas[indice]["titulo"])
        comprobar(
            f"el tema {indice + 1} cubre {palabra_a} y {palabra_b}",
            palabra_a.lower() in titulo.lower() and palabra_b.lower() in titulo.lower(),
            titulo,
        )
        for clave in ("explicacion", "puntos", "comandos", "errores"):
            comprobar(
                f"el tema {indice + 1} trae {clave}",
                bool(temas[indice].get(clave)),
            )

    tex = MOD.tex_guia(DESCRIPTOR, 2)
    for numero in range(1, 6):
        comprobar(
            f"el LaTeX emite la sección del tema {numero}",
            f"\\subsection{{{numero}. " in tex,
        )
    comprobar(
        "los cinco bloques de comandos se emiten en lstlisting",
        tex.count(r"\begin{lstlisting}[style=estiloCodigo]") == 5,
        str(tex.count(r"\begin{lstlisting}[style=estiloCodigo]")),
    )


def test_es_material_de_estudio_no_examen() -> None:
    tex = MOD.tex_guia(DESCRIPTOR, 2)
    for marcador in ("**Answer:**", "**Hint:**", "Pregunta", "Respuesta correcta", r"\begin{cajaEjercicio}"):
        comprobar(
            f"la guía no contiene el marcador de examen {marcador!r}",
            marcador not in tex,
        )
    comprobar(
        "la guía dice explícitamente que no es un examen",
        "No es un examen" in tex or "no es un examen" in tex,
    )
    comprobar("la guía trae checklist", "Checklist antes de la práctica" in tex)
    comprobar("la guía trae glosario", "Glosario de la semana" in tex)


def test_preambulo_y_cajas() -> None:
    from estilo_infografia import PREAMBULO_INFOGRAFIA

    tex = MOD.tex_guia(DESCRIPTOR, 2)
    comprobar(
        "usa el preámbulo compartido sin duplicarlo",
        tex.startswith(PREAMBULO_INFOGRAFIA) and tex.count(PREAMBULO_INFOGRAFIA) == 1,
    )
    comprobar("usa la banda de título", r"\bandaTitulo[" in tex)
    comprobar(
        "cajaContenido NO se usa como entorno",
        r"\begin{cajaContenido}" not in tex,
    )
    comprobar(
        "cajaConcepto sí se usa como entorno",
        r"\begin{cajaConcepto}" in tex,
    )


def test_glosario_y_main_sin_compilar() -> None:
    glosario = MOD._glosario(DESCRIPTOR, SEMANA2)
    comprobar("el glosario de la semana se resuelve", len(glosario) == 8, str(len(glosario)))
    comprobar(
        "todas las definiciones del glosario son texto",
        all(isinstance(d, str) and d for _, d in glosario),
    )

    with tempfile.TemporaryDirectory(prefix="guia-teorica-test-") as temporal:
        buf = io.StringIO()
        viejo = sys.argv
        sys.argv = ["generar_guia_teorica.py", "--curso", str(CURSO), "--semana", "2",
                    "--salida", temporal, "--sin-compilar", "--json"]
        try:
            with contextlib.redirect_stdout(buf):
                codigo = MOD.main()
        finally:
            sys.argv = viejo
        salida = json.loads(buf.getvalue())
        comprobar("main --sin-compilar devuelve 0", codigo == 0, str(codigo))
        comprobar("el JSON dice status ok", salida["status"] == "ok")
        comprobar("el JSON no anuncia PDF sin compilar", salida["pdf"] is None)
        comprobar("el JSON trae errores y overfull", "errores" in salida and "overfull" in salida)
        tex_path = Path(salida["tex"])
        comprobar("el .tex se escribió en la salida pedida", tex_path.exists() and tex_path.parent == Path(temporal))
        comprobar(
            "el archivo escrito coincide con tex_guia",
            tex_path.read_text(encoding="utf-8") == MOD.tex_guia(DESCRIPTOR, 2),
        )


def main() -> int:
    test_parseo_del_descriptor()
    test_validacion()
    test_determinismo_y_bytes()
    test_los_cinco_temas()
    test_es_material_de_estudio_no_examen()
    test_preambulo_y_cajas()
    test_glosario_y_main_sin_compilar()

    print()
    if FALLOS:
        print(f"{len(FALLOS)} FALLOS de {PRUEBAS} aserciones")
        for fallo in FALLOS:
            print(f"  - {fallo}")
        return 1
    print(f"OK: {PRUEBAS} aserciones, 0 fallos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
