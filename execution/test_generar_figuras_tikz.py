#!/usr/bin/env python3
"""Pruebas puras de `execution/generar_figuras_tikz.py` (capa 3).

Fijan el contrato del generador de figuras SIN red y SIN compilación: extracción
de descriptores desde el OCR, parseo de bloques delimitados, validación
determinista (prohibidos, entornos balanceados, presence de center/tikz),
armado del prompt por lote y caché atómica/reanudable del manifest.

La compilación real de cada figura se comprueba en la corrida del flujo, no aquí.

Ejecutar: python3 execution/test_generar_figuras_tikz.py
"""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "execution" / "generar_figuras_tikz.py"
FALLOS: list[str] = []
PRUEBAS = 0

OCR_MINIMO = """
PRÁCTICA 1
TITULO DE PRUEBA
1. OBJETIVOS
* Un objetivo.
2. PARTE TEÓRICA.
Texto. [FIGURA: Conductor cilíndrico con longitud $l$ y sección A.]
3. PARTE EXPERIMENTAL.
3.1 MATERIAL
* Resistor.
3.2. PROCEDIMIENTO
* Medir. [FIGURA: Circuito con fuente, amperímetro y resistor R.]
4. ACTIVIDADES
* Graficar.
"""


def comprobar(nombre: str, condicion: bool, detalle: str = "") -> None:
    global PRUEBAS
    PRUEBAS += 1
    if condicion:
        print(f"  ok   {nombre}")
    else:
        print(f"  FALLA {nombre}" + (f" -- {detalle}" if detalle else ""))
        FALLOS.append(nombre)


def _cargar():
    spec = importlib.util.spec_from_file_location("figuras_tikz_bajo_test", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


def main() -> int:
    m = _cargar()

    # ── Extracción desde el OCR (misma numeración que el inyector) ────────────
    with tempfile.TemporaryDirectory() as temporal:
        ruta = Path(temporal) / "ocr.md"
        ruta.write_text(OCR_MINIMO, encoding="utf-8")
        figuras = m.extraer_figuras(ruta, [1])
    comprobar("extrae las dos figuras del OCR mínimo", len(figuras) == 2)
    comprobar("IDs canónicos pNN_fNN",
              list(figuras) == ["p01_f01", "p01_f02"], str(list(figuras)))
    comprobar("descriptor conserva práctica e índice",
              figuras["p01_f02"]["practica"] == 1 and figuras["p01_f02"]["indice"] == 2)
    comprobar("descriptor conserva la descripción literal",
              "Conductor cilíndrico" in figuras["p01_f01"]["descripcion"])

    # ── Parseo de bloques delimitados ────────────────────────────────────────
    respuesta = (
        "texto previo que debe ignorarse\n"
        "<<<FIGURA:p01_f01>>>\n\\begin{center}\n\\begin{circuitikz}\\end{circuitikz}\n\\end{center}\n<<<FIN:p01_f01>>>\n"
        "comentario intermedio\n"
        "<<<FIGURA:p01_f02>>>\n\\begin{center}\\begin{tikzpicture}\\end{tikzpicture}\\end{center}\n<<<FIN:p01_f02>>>\n"
    )
    bloques, problemas = m.parsear_respuesta(respuesta, ["p01_f01", "p01_f02"])
    comprobar("parsea ambos bloques", set(bloques) == {"p01_f01", "p01_f02"})
    comprobar("sin problemas de formato", problemas == [], str(problemas))
    comprobar("no incluye el texto previo", "texto previo" not in bloques["p01_f01"])

    _, incompletos = m.parsear_respuesta(respuesta, ["p01_f01", "p01_f02", "p01_f03"])
    comprobar("reporta ID ausente", any("p01_f03" in p for p in incompletos))

    duplicado = respuesta + "\n<<<FIGURA:p01_f01>>>\nextra\n<<<FIN:p01_f01>>>"
    bloques_dup, problemas_dup = m.parsear_respuesta(duplicado, ["p01_f01", "p01_f02"])
    comprobar("ID repetido no sobrescribe el primero",
              "extra" not in bloques_dup["p01_f01"] and problemas_dup == [])

    _, inesperado = m.parsear_respuesta(
        respuesta + "\n<<<FIGURA:p99_f99>>>\nx\n<<<FIN:p99_f99>>>",
        ["p01_f01", "p01_f02"],
    )
    comprobar("reporta ID inesperado", any("p99_f99" in p for p in inesperado))

    # ── Validación determinista del código propuesto ──────────────────────────
    bueno = (
        "\\begin{center}\\begin{circuitikz}"
        "\\draw (0,0) to[R,l={$V = IR$}] (2,0);"
        "\\end{circuitikz}\\end{center}"
    )
    comprobar("bloque válido pasa", m.validar_codigo(bueno, "p01_f01") == [])
    comprobar("código vacío se rechaza", m.validar_codigo("  ", "p01_f01") != [])
    for patron in (r"\usepackage{pgfplots}", "galvanometer", "full diode bridge",
                   "pC", "[FIGURA:"):
        comprobar(f"rechaza '{patron}'",
                  m.validar_codigo(bueno + "\n" + patron, "p01_f01") != [])
    comprobar("entornos desbalanceados se rechazan",
              m.validar_codigo(bueno + "\\begin{center}", "p01_f01") != [])
    comprobar("sin entorno center se rechaza",
              m.validar_codigo("\\begin{circuitikz}\\end{circuitikz}", "p01_f01") != [])
    comprobar("sin tikz se rechaza",
              m.validar_codigo("\\begin{center}x\\end{center}", "p01_f01") != [])
    comprobar("prosa del OCR dentro del código se rechaza",
              m.validar_codigo(bueno + "\n% cumple con la descripción", "p01_f01") != [])

    # ── Armado del mensaje por lote ──────────────────────────────────────────
    mensaje = m.armar_mensaje([
        {"id": "p01_f01", "descripcion": "Un resistor."},
        {"id": "p01_f02", "descripcion": "Un capacitor."},
    ])
    comprobar("mensaje trae ambos IDs en orden",
              mensaje.index("p01_f01") < mensaje.index("p01_f02"))
    comprobar("mensaje trae ambas descripciones",
              "Un resistor." in mensaje and "Un capacitor." in mensaje)
    comprobar("mensaje pide solo bloques", "SOLO los bloques delimitados" in mensaje)

    # ── Caché atómica y reanudable ───────────────────────────────────────────
    with tempfile.TemporaryDirectory() as temporal:
        ruta = Path(temporal) / "figuras.json"
        vacio = m.cargar_manifest(ruta)
        comprobar("manifest ausente empieza pendiente", vacio["status"] == "pendiente")
        comprobar("manifest ausente tiene estructura", vacio["figuras"] == {} and vacio["fallos"] == [])
        m.guardar_manifest(ruta, {"status": "ok", "figuras": {"p01_f01": {"codigo": "x"}}, "fallos": []})
        comprobar("manifest se guarda", ruta.is_file() and not ruta.with_suffix(".json.tmp").exists())
        leido = m.cargar_manifest(ruta)
        comprobar("manifest se relee", leido["figuras"]["p01_f01"]["codigo"] == "x")
        ruta.write_text("{ roto", encoding="utf-8")
        comprobar("manifest corrupto degrada a pendiente",
                  m.cargar_manifest(ruta)["status"] == "pendiente")

    # ── Hash estable (clave de la caché por descripción) ──────────────────────
    comprobar("sha de descripción determinista",
              m._sha("una descripción") == m._sha("una descripción")
              and m._sha("una descripción") != m._sha("otra descripción"))

    print(f"\n{PRUEBAS} aserciones, {len(FALLOS)} fallos")
    return 1 if FALLOS else 0


if __name__ == "__main__":
    raise SystemExit(main())
