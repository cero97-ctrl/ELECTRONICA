#!/usr/bin/env python3
"""Pruebas de `execution/generar_practicas_desde_ocr.py` (capa 3).

Fijan el contrato del flujo OCR → prácticas: las 8 cabeceras irregulares se
detectan, cada práctica conserva sus cinco secciones, los marcadores `[FIGURA]`
(incluso inline), `[ILEGIBLE]` y `[TABLA:]` nunca llegan al LaTeX, la leyenda
`TABLA N` se emite centrada al pie, la matemática `$...$` y `\\[...\\]` sobrevive
al escapado, y el mismo markdown produce siempre el mismo hash. Sin red y sin
compilación: las funciones bajo prueba son puras.

Ejecutar: python3 execution/test_generar_practicas_desde_ocr.py
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "execution" / "generar_practicas_desde_ocr.py"
FALLOS: list[str] = []
PRUEBAS = 0

# Fixture sintética: reproduce las irregularidades reales del OCR (negrita,
# tilde, tabla markdown, figuras inline, display math) en miniatura.
OCR_FIXTURE = """
<!-- pagina 1 -->

## Página 1

PRÁCTICA 1
MANEJO DEL INSTRUMENTAL ELÉCTRICO Y DETERMINACIÓN DE LA CARACTERÍSTICA I-V.
1. OBJETIVOS.
* Aprender a utilizar los instrumentos de medida.
* Obtener la característica $I$-$V$ de un resistor.
2. PARTE TEÓRICA.
La resistencia se define como:
\\[R = \\frac{V}{I}\\]
donde $V$ es la caída de potencial. Ver el montaje. [FIGURA: Circuito con fuente, amperímetro y resistor R.]
3. PARTE EXPERIMENTAL.
3.1 MATERIAL
| N° DE BIENES | RESISTENCIA |
| :----------- | :---------- |
| R-1          | 100 $\\Omega$ |
3.2. PROCEDIMIENTO
1. Montar el circuito de la figura 1.
[FIGURA: Diagrama del circuito con $R_1$ y $R_2$.]
4. ACTIVIDADES
* Graficar los datos de la tabla 1.

11

PRACTICA 2
DETERMINACIÓN DE UNA RESISTENCIA ELÉCTRICA
1. OBJETIVOS
* Conocer los métodos experimentales.
2. PARTE TEÓRICA.
[ILEGIBLE]
3. PARTE EXPERIMENTAL.
3.1 MATERIAL
* Un voltímetro y un amperímetro.
3.2. PROCEDIMIENTO
* Medir corriente y voltaje.
4. ACTIVIDADES
* Calcular la resistencia.

**PRÁCTICA 3**
CIRCUITOS ELÉCTRICOS
1. OBJETIVOS
* Analizar circuitos.
2. PARTE TEÓRICA.
\\[V = I R\\]
3. PARTE EXPERIMENTAL.
3.1 MATERIAL
* Resistencias.
3.2 PROCEDIMIENTO
* Armar el circuito.
4. ACTIVIDADES
* Reportar resultados.

**PRÁCTICA 4**
CIRCUITOS RESONANTES
1. OBJETIVOS
* Estudiar la resonancia.
2. PARTE TEÓRICA.
La frecuencia es $f_0$.
3. PARTE EXPERIMENTAL.
3.1 MATERIAL
* Bobina y capacitor.
3.2 PROCEDIMIENTO
* Barrer frecuencias.
4. ACTIVIDADES
* Graficar la respuesta.

PRÁCTICA 5
ELEMENTOS NO LINEALES. DIODO SEMICONDUCTOR
1. OBJETIVOS
* Determinar el factor de idealidad $n$.
2. PARTE TEÓRICA.
\\[I = I_0 (e^{V/nV_T} - 1)\\]
3. PARTE EXPERIMENTAL.
3.1 MATERIAL
* Un diodo.
3.2 PROCEDIMIENTO
* Medir la curva I-V.
4. ACTIVIDADES
* Ajustar por mínimos cuadrados.

PRÁCTICA 6
RESPUESTA R, L Y C A LA TENSIÓN SENOIDAL
1. OBJETIVOS
* Caracterizar R, L y C.
2. PARTE TEÓRICA.
\\[X_C = \\frac{1}{\\omega C}\\]
3. PARTE EXPERIMENTAL.
3.1 MATERIAL
* Generador de funciones.
3.2 PROCEDIMIENTO
* Medir impedancias.
4. ACTIVIDADES
* Comparar fases.

PRÁCTICA 7
CIRCUITOS RESONANTES
1. OBJETIVOS
* Medir la resonancia.
2. PARTE TEÓRICA.
\\[\\omega_0 = \\frac{1}{\\sqrt{LC}}\\]
3. PARTE EXPERIMENTAL.
3.1 MATERIAL
* Osciloscopio.
3.2 PROCEDIMIENTO
* Trazar la curva.
4. ACTIVIDADES
* Calcular Q.

PRÁCTICA 8
CARGA Y DESCARGA DE UN CAPACITOR
1. OBJETIVOS
* Visualizar la carga y descarga.
2. PARTE TEÓRICA.
\\[\\tau = R C\\]
3. PARTE EXPERIMENTAL.
[FIGURA: Circuito RC con interruptor.]
3.1 MATERIAL
* Un capacitor de $C = 1$ $\\mu$F.
3.2 PROCEDIMIENTO
* Cargar y descargar.
4. ACTIVIDADES
* Determinar $\\tau$.

TABLAS 2 y 3: VALORES DE LAS INDUCTANCIAS.
| N° BIENES | TIPO |
| :-------- | :--- |
| L-1       | 10 mH |
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
    spec = importlib.util.spec_from_file_location("practicas_ocr_bajo_test", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modulo)
    return modulo


def main() -> int:
    m = _cargar()

    # ── Limpieza del markdown ────────────────────────────────────────────────
    limpio = m.limpiar_markdown(OCR_FIXTURE)
    comprobar("quita marcas de página HTML", "<!-- pagina" not in limpio)
    comprobar("quita encabezados de página", "## Página" not in limpio)
    comprobar("conserva ítems numerados", "1. Montar el circuito" in limpio)
    comprobar("conserva ecuaciones display", r"\[R = \frac{V}{I}\]" in limpio)

    # ── Detección de cabeceras irregulares ───────────────────────────────────
    ps = m.extraer_practicas(OCR_FIXTURE)
    comprobar("detecta las 8 prácticas", sorted(ps) == list(range(1, 9)), str(sorted(ps)))
    comprobar("título P1 en mayúsculas completo",
              "MANEJO DEL INSTRUMENTAL" in ps[1]["titulo"], ps[1]["titulo"])
    comprobar("P3 con negrita se detecta", 3 in ps)
    comprobar("P6 con tilde se detecta", 6 in ps)

    # ── Secciones canónicas ──────────────────────────────────────────────────
    for n in range(1, 9):
        for clave in m.SECCIONES_OBLIGATORIAS:
            comprobar(f"P{n} tiene sección {clave}",
                      any(l.strip() for l in ps[n]["secciones"].get(clave, [])))
    comprobar("P8 captura la sección experimental (figura antes de 3.1)",
              any(l.strip() for l in ps[8]["secciones"].get("experimental", [])))
    comprobar("TABLAS 2 y 3 se recortan de P8",
              "TABLAS 2 y 3" not in "\n".join(ps[8]["secciones"].get("actividades", [])))

    # ── Extracción de figuras inline ─────────────────────────────────────────
    texto = "La resistencia depende de la geometría. [FIGURA: Conductor cilíndrico con $l$ y A.]"
    limpio2, figs = m._separar_figuras_inline(texto)
    comprobar("figura inline se extrae", len(figs) == 1 and "Conductor cilíndrico" in figs[0])
    comprobar("prosa alrededor se conserva",
              "La resistencia depende de la geometría." in limpio2 and "[FIGURA" not in limpio2)

    # ── Renderizado ──────────────────────────────────────────────────────────
    latex = m.render_practica(ps[1])
    comprobar("display math preservado", r"\[R = \frac{V}{I}\]" in latex)
    comprobar("matemática inline preservada", "$I$-$V$" in latex)
    comprobar("figura inline → caja", "Figura del original" in latex and "[FIGURA" not in latex)
    comprobar("tabla markdown → tabular", r"\begin{tabular}{ll}" in latex)
    comprobar("sección experimental renderizada (P8)",
              "Desarrollo experimental" in m.render_practica(ps[8]))
    comprobar("entornos balanceados", latex.count(r"\begin{") == latex.count(r"\end{"))
    comprobar("sin marcas de página en LaTeX",
              "<!-- pagina" not in latex and "## Página" not in latex)

    latex2 = m.render_practica(ps[2])
    comprobar("[ILEGIBLE] → aviso, sin marcador",
              "Texto ilegible en el escaneo" in latex2 and "[ILEGIBLE]" not in latex2)

    # ── Numeración e inyección de figuras (mismo orden para el generador
    #    TikZ y para el inyector; aquí se fija que no se emparejen de más) ────
    descriptores = m.figuras_de_practica(ps[1])
    comprobar("P1 tiene dos descriptores de figura", len(descriptores) == 2,
              str([d["id"] for d in descriptores]))
    comprobar("IDs de figura estables y ordenados",
              [d["id"] for d in descriptores] == ["p01_f01", "p01_f02"])
    comprobar("descriptor lleva el sha de su descripción",
              all(len(d["sha256_16"]) == 16 for d in descriptores))
    tikZ = r"\begin{center}\begin{circuitikz}\draw (0,0) to[R] (2,0);\end{circuitikz}\end{center}"
    inyectado = m.render_practica(ps[1], figuras={"p01_f02": tikZ})
    comprobar("figura con manifest se inyecta", tikZ in inyectado)
    comprobar("figura sin manifest sigue siendo caja",
              "Figura del original" in inyectado)
    comprobar("inyección no deja marcadores OCR", "[FIGURA" not in inyectado)
    comprobar("inyección mantiene entornos balanceados",
              inyectado.count(r"\begin{") == inyectado.count(r"\end{"))
    comprobar("sin manifest, comportamiento heredado",
              m.render_practica(ps[1]).count("Figura del original") == 2)

    # ── Validador de matemática consciente de display math ───────────────────
    comprobar("display math no reporta subíndices",
              m.validar_matematica_ocr(r"\[I_m = i_v + i\]", "P5") == [])
    comprobar("dólares impares se rechazan",
              any("impar" in p for p in m.validar_matematica_ocr("La $V y I", "P1")))
    comprobar("display desbalanceado se rechaza",
              any("desbalanceados" in p for p in m.validar_matematica_ocr(r"\[V = I R", "P1")))
    comprobar("subíndice suelto se rechaza",
              any("'_'" in p for p in m.validar_matematica_ocr("La V_C mide", "P1")))

    # ── Validación de cobertura ──────────────────────────────────────────────
    comprobar("fixture válida pasa validación", m.validar_practicas(ps, list(range(1, 9))) == [],
              "; ".join(m.validar_practicas(ps, list(range(1, 9)))))
    incompleto = dict(ps)
    incompleto.pop(8)
    problemas = m.validar_practicas(incompleto, list(range(1, 9)))
    comprobar("práctica faltante se reporta", any("falta la práctica 8" in p for p in problemas))

    # ── Rangos y determinismo ────────────────────────────────────────────────
    comprobar("rango 'todas'", m.parsear_rango(None) == list(range(1, 9)))
    comprobar("rango '1,3,5-7'", m.parsear_rango("1,3,5-7") == [1, 3, 5, 6, 7])
    comprobar("rango fuera de límites se descarta", m.parsear_rango("7-10") == [7, 8])
    comprobar("mismo markdown → mismo hash",
              m._sha("abc") == m._sha("abc") and m._sha("abc") != m._sha("abd"))

    # ── Marcadores [TABLA:] y leyenda centrada (caso P1, 21-nov-2026) ─────────
    # El escaneo dejaba `[TABLA:` / `]` alrededor de las tablas de P1: el PDF
    # mostraba el marcador y la leyenda `] TABLA 1` sin centrar. Se congela aquí
    # para que una re-extracción no reintroduzca el ruido.
    con_marcadores = (
        "esto es:\n[TABLA:\n| A | B |\n|---|---|\n| 1 | 2 |\n]\n(9)\n"
        "resistores:\n[TABLA:\n| TIPO |\n|---|\n| CARBÓN |\n]\nTABLA 1\n"
    )
    sin_marcadores = m.limpiar_markdown(con_marcadores)
    comprobar("marcador [TABLA: se elimina", "[TABLA:" not in sin_marcadores)
    comprobar("corchete ] suelto se elimina",
              not any(linea.strip() == "]" for linea in sin_marcadores.splitlines()))
    comprobar("leyenda TABLA 1 se conserva", "TABLA 1" in sin_marcadores)
    comprobar("filas de la tabla se conservan", "| CARBÓN |" in sin_marcadores)
    bloques = m.convertir_bloques(sin_marcadores.splitlines())
    comprobar("leyenda TABLA 1 centrada al pie",
              r"\begin{center}\small\textbf{TABLA 1}\end{center}" in bloques)
    comprobar("sin marcadores [TABLA: en el LaTeX", "[TABLA:" not in bloques)
    comprobar("TABLAS 2 y 3 no se confunde con leyenda",
              m.RE_LEYENDA_TABLA.match("TABLAS 2 y 3: VALORES DE LAS INDUCTANCIAS.") is None)
    con_marca = {
        n: {
            "numero": p["numero"],
            "titulo": p["titulo"],
            "secciones": {k: list(v) for k, v in p["secciones"].items()},
        }
        for n, p in ps.items()
    }
    con_marca[1]["secciones"]["teoria"].append("[TABLA:")
    problemas_marca = m.validar_practicas(con_marca, list(range(1, 9)))
    comprobar("marcador reintroducido se reporta en validación",
              any("[TABLA:" in x for x in problemas_marca))
    ruta_real = RAIZ / "cursos" / "LABORATORIO_II_FISICA" / "docs" / "practicas_ocr_completo.md"
    if ruta_real.is_file():
        comprobar("OCR real sin marcadores [TABLA:",
                  "[TABLA:" not in ruta_real.read_text(encoding="utf-8"))

    print(f"\n{PRUEBAS} aserciones, {len(FALLOS)} fallos")
    return 1 if FALLOS else 0


if __name__ == "__main__":
    raise SystemExit(main())
