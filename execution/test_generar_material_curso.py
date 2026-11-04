#!/usr/bin/env python3
"""Pruebas de regresión del generador de material de cursos.

Por qué existe este fichero: `generar_material_curso.py` nació acoplado a un
curso de ciberseguridad (icono `shield-alt`, entregas por GitHub, contrato de
datos de escaneo, rúbrica de cinco criterios fija). Al reutilizarlo para un
curso de laboratorio de física, ese acoplamiento no rompe: simplemente emite
texto del dominio equivocado, que es la forma más silenciosa de fallar.

Los objetivos, cada uno fijando una clase de fallo:

1. Los campos nuevos del descriptor (`meta.icono`, `textos.*`, `entregas.carpeta`,
   `evaluacion.rubrica`, `practica.fundamento_tex|materiales|tabla_datos|analisis`,
   `apendices`) se reflejan en el LaTeX y NO se inventan cuando faltan.
2. La rúbrica es dato, no constante: se genera desde el descriptor y se valida.
3. Las tablas de datos se validan (filas alineadas con la cabecera) y se emiten
   con LaTeX crudo, sin escapar unidades ni matemática.
4. Un descriptor de física no arrastra el vocabulario de ciberseguridad.
5. La generación es determinista (mismo descriptor, mismo LaTeX).

Ejecutar: python3 execution/test_generar_material_curso.py
Salida:  0 si todas pasan, 1 si alguna falla.

Ningún test compila LaTeX: se importa el módulo y se comprueba el texto que
emite. La compilación la cubre el flujo, no esta prueba.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - el entorno del repo trae PyYAML
    yaml = None

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "execution"))

import generar_material_curso as gen  # noqa: E402

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


def descriptor_minimo() -> dict:
    """Descriptor válido y mínimo: dos semanas, una fase, todo lo obligatorio."""
    return {
        "meta": {
            "codigo": "CURSO_TEST",
            "titulo": "Curso de prueba",
            "subtitulo": "Descriptor mínimo para pruebas",
            "autor": "Prof. Prueba",
            "institucion": "ELECTRONICA",
            "fecha": "2 de noviembre de 2026",
            "fecha_iso": "2026-11-02",
            "semanas": 2,
            "icono": "atom",
        },
        "fases": [
            {
                "id": 1,
                "nombre": "Fase única",
                "semanas": [1, 2],
                "enfoque": "Medición y análisis.",
            }
        ],
        "semanas": [
            {
                "numero": numero,
                "fase": 1,
                "titulo": f"Semana {numero}",
                "objetivo": "Objetivo de la semana.",
                "contenidos": ["Contenido"],
                "herramientas": ["Herramienta"],
                "evaluacion": "practica",
                "practica": {
                    "titulo": f"Práctica {numero}",
                    "escenario": "Escenario de laboratorio.",
                    "pasos": ["Paso uno"],
                    "entregable": "Informe de laboratorio.",
                    "criterios": [{"criterio": "datos", "peso": 10.0}],
                },
            }
            for numero in (1, 2)
        ],
        "evaluacion": {
            "pesos": [{"concepto": "Prácticas", "peso": 100.0}],
            "escala": 10,
            "nota_minima": 5,
        },
        "politicas": ["Política de seguridad."],
        "bibliografia": [{"autor": "Autor", "titulo": "Título"}],
        "objetivo_general": "Objetivo general del curso.",
        "resultados_aprendizaje": [{"id": "RA1", "texto": "Resultado uno."}],
        "entregas": {
            "plataforma": "GitHub",
            "modalidad": "Repositorio privado por grupo.",
            "cadencia": "Una entrega por semana.",
            "corte": "Al cierre de la sesión.",
            "carpeta": "semana_{n:02d}",
            "estructura": ["informe/", "datos/"],
            "reglas": ["Entregar antes del corte."],
        },
        "laboratorio": {
            "red": "labfisica",
            "caracter": "Laboratorio físico con equipos de medición.",
            "recursos": "Multímetro, fuente, resistencias.",
            "reglas": ["No energizar sin revisar el montaje."],
        },
    }


# ── Validación ────────────────────────────────────────────────────────────────


def test_descriptor_minimo_valido() -> None:
    comprobar(
        "descriptor mínimo válido no reporta problemas",
        gen.validar(descriptor_minimo()) == [],
        str(gen.validar(descriptor_minimo())),
    )


def test_resultados_de_aprendizaje_mal_formados_fallan() -> None:
    """Un RA escrito como texto plano pasaba `validar` y reventaba el sílabo.

    El fallo real: `tex_silabo` hace `r["id"]` sobre cada resultado, así que una
    lista de strings llega hasta la generación y muere con `TypeError: string
    indices must be integers`, ya con el flujo corriendo. Validar la forma cuesta
    una línea y devuelve un código 3 con el índice del elemento.
    """
    datos = descriptor_minimo()
    datos["resultados_aprendizaje"] = ["Resultado redactado como texto plano."]
    problemas = gen.validar(datos)
    comprobar(
        "resultado de aprendizaje sin 'id'/'texto' se rechaza",
        any("resultados_aprendizaje[1]" in p for p in problemas),
        str(problemas),
    )

    vacio = descriptor_minimo()
    vacio["resultados_aprendizaje"] = []
    comprobar(
        "lista vacía de resultados de aprendizaje se rechaza",
        any("resultados_aprendizaje" in p for p in gen.validar(vacio)),
        str(gen.validar(vacio)),
    )


def test_unicode_en_latex_crudo_falla() -> None:
    """Un Ω suelto en una celda de tabla revienta pdflatex, no la validación.

    Las celdas y los campos ``*_tex`` son LaTeX crudo a propósito (llevan
    ``$V$``, ``\\si{\\ohm}``), así que no pasan por ``_t()`` y su mapa
    ``_UNICODE`` no los traduce. Sin este chequeo el error aparece tras una
    compilación completa: "Unicode character Ω (U+03A9) not set up for use with
    LaTeX". Los acentos del español sí los resuelve ``inputenc`` y no se avisan.
    """
    datos = descriptor_minimo()
    datos["semanas"][0]["practica"]["tabla_datos"] = {
        "columnas": ["Magnitud", "Valor"],
        "filas": [["Resistencia", "100 Ω"]],
    }
    problemas = gen.validar(datos)
    comprobar(
        "Ω en una celda de tabla se rechaza con la corrección sugerida",
        any("U+03A9" in p and r"$\Omega$" in p for p in problemas),
        str(problemas),
    )

    tex = descriptor_minimo()
    tex["semanas"][0]["practica"]["fundamento_tex"] = r"La constante es $\tau = R C$ con C en μF."
    comprobar(
        "μ en fundamento_tex se rechaza",
        any("U+03BC" in p for p in gen.validar(tex)),
        str(gen.validar(tex)),
    )

    acentos = descriptor_minimo()
    acentos["semanas"][0]["practica"]["tabla_datos"] = {
        "columnas": ["Magnitud", "Valor"],
        "filas": [["Tensión", "5,00 V"]],
    }
    acentos["semanas"][0]["practica"]["fundamento_tex"] = r"El diámetro del núcleo es $\varnothing$."
    comprobar(
        "acentos y LaTeX puro no generan falsos positivos",
        gen.validar(acentos) == [],
        str(gen.validar(acentos)),
    )

    porcentaje = descriptor_minimo()
    porcentaje["semanas"][0]["practica"]["tabla_datos"] = {
        "columnas": ["Magnitud", "Desvío (%)"],
        "filas": [["Tensión", r"0,5 \%"]],
    }
    problemas = gen.validar(porcentaje)
    comprobar(
        "'%' sin escapar en una celda se rechaza",
        any("sin escapar" in p for p in problemas),
        str(problemas),
    )
    comprobar(
        "'\\%' escapado no se avisa",
        not any("fila 1" in p for p in problemas),
        str(problemas),
    )


def test_rubrica_que_no_suma_falla() -> None:
    datos = descriptor_minimo()
    datos["evaluacion"]["rubrica"] = [
        {"criterio": "fundamento", "peso": 5.0, "descripcion": "d"},
        {"criterio": "datos", "peso": 4.0, "descripcion": "d"},
    ]
    problemas = gen.validar(datos)
    comprobar(
        "rúbrica que no suma 10 se rechaza",
        any("evaluacion.rubrica" in p and "suman 9" in p for p in problemas),
        str(problemas),
    )


def test_rubrica_con_clave_invalida_falla() -> None:
    datos = descriptor_minimo()
    datos["evaluacion"]["rubrica"] = [
        {"criterio": "Fundamento Teórico", "peso": 10.0, "descripcion": "d"},
    ]
    problemas = gen.validar(datos)
    comprobar(
        "rúbrica con clave no ASCII se rechaza",
        any("identificador ASCII" in p for p in problemas),
        str(problemas),
    )


def test_tabla_desalineada_falla() -> None:
    datos = descriptor_minimo()
    datos["semanas"][0]["practica"]["tabla_datos"] = {
        "columnas": ["V", "I"],
        "filas": [["0", "0"], ["1"]],
    }
    problemas = gen.validar(datos)
    comprobar(
        "tabla con fila incompleta se rechaza",
        any("fila 2" in p and "2" in p for p in problemas),
        str(problemas),
    )


def test_apendice_sin_contenido_falla() -> None:
    datos = descriptor_minimo()
    datos["apendices"] = [{"titulo": "Anexo vacío"}]
    problemas = gen.validar(datos)
    comprobar(
        "apéndice sin texto ni tabla se rechaza",
        any("necesita 'texto' o 'tabla'" in p for p in problemas),
        str(problemas),
    )


# ── Contenido emitido ─────────────────────────────────────────────────────────


def test_rubrica_desde_descriptor() -> None:
    datos = descriptor_minimo()
    datos["evaluacion"]["rubrica"] = [
        {"criterio": "fundamento", "peso": 6.0, "descripcion": "Explica el modelo."},
        {"criterio": "datos", "peso": 4.0, "descripcion": "Tabula: crudo y procesado."},
    ]
    texto = gen.yaml_rubrica(datos)
    cargado = yaml.safe_load(texto) if yaml else {}
    criterios = cargado.get("criterios") or {}
    comprobar(
        "yaml_rubrica usa los criterios del descriptor",
        set(criterios) == {"fundamento", "datos"},
        str(criterios),
    )
    comprobar(
        "yaml_rubrica conserva los pesos declarados",
        abs(sum(float(c["peso"]) for c in criterios.values()) - 10.0) < 0.01,
        str(criterios),
    )
    comprobar(
        "yaml_rubrica sobrevive a descripciones con dos puntos",
        criterios.get("datos", {}).get("descripcion", "").startswith("Tabula"),
        str(criterios.get("datos")),
    )


def test_secciones_de_practica() -> None:
    datos = descriptor_minimo()
    practica = datos["semanas"][0]["practica"]
    practica["fundamento_tex"] = r"La ley de Ohm es $V = IR$."
    practica["figura_tex"] = r"\begin{circuitikz}\draw (0,0) to[R] (2,0);\end{circuitikz}"
    practica["figura_caption"] = "Circuito de prueba"
    practica["materiales"] = ["Multímetro", "Fuente"]
    practica["tabla_datos"] = {
        "caption": "Datos medidos",
        "columnas": ["$V$ (V)", "$I$ (mA)"],
        "filas": [["0,0", "0,0"], ["1,0", "10,2"]],
        "nota": "Valores crudos.",
    }
    practica["analisis"] = ["Graficar $V$ contra $I$."]
    practica["ampliacion"] = ["Repetir el montaje con el diodo Zener."]
    texto = gen.tex_practica(datos, datos["semanas"][0])
    for seccion in (
        "Fundamento teórico",
        "circuitikz",
        "Circuito de prueba",
        "Materiales y equipos",
        "Tabla de datos",
        "Datos medidos",
        "Análisis y tratamiento de datos",
        "Ampliación (opcional)",
        "Repetir el montaje con el diodo Zener.",
    ):
        comprobar(f"la práctica emite «{seccion}»", seccion in texto)
    comprobar(
        "la tabla no escapa la matemática del descriptor",
        "$V$ (V) & $I$ (mA)" in texto,
    )
    comprobar(
        "la tabla alinea tantas columnas como declara",
        r"{@{}cc@{}}" in texto,
    )


def test_practica_sin_secciones_no_inventa() -> None:
    datos = descriptor_minimo()
    texto = gen.tex_practica(datos, datos["semanas"][0])
    for seccion in (
        "Fundamento teórico",
        "Materiales y equipos",
        "Tabla de datos",
        "Ampliación (opcional)",
    ):
        comprobar(f"sin datos no aparece «{seccion}»", seccion not in texto)


def test_dominio_no_se_cuela() -> None:
    datos = descriptor_minimo()
    datos["textos"] = {
        "titulo_entregas": "Entregas del laboratorio",
        "titulo_estructura": "Estructura de la entrega",
        "aviso_practica": "Verifica el montaje antes de energizar.",
        "aviso_entrega": "Entrega los datos crudos sin editar.",
        "contrato_datos": False,
    }
    practica = datos["semanas"][0]["practica"]
    practica["requiere_codigo"] = True
    silabo = gen.tex_silabo(datos)
    guia = gen.tex_guia(datos)
    texto = gen.tex_practica(datos, datos["semanas"][0])
    comprobar("el sílabo usa el icono del descriptor", r"\faIcon{atom}" in silabo)
    comprobar(
        "la guía no habla de contenedores ni de ciberseguridad",
        "contenedor del laboratorio" not in guia and "Contrato de datos" not in guia,
    )
    comprobar(
        "la práctica no arrastra el aviso de ciberseguridad",
        "sistema con autorización escrita" not in texto,
    )
    comprobar(
        "la práctica usa el aviso declarado",
        "Verifica el montaje antes de energizar" in texto,
    )
    comprobar("la entrega usa el título declarado", "Entregas del laboratorio" in guia)


def test_apendices_en_guia() -> None:
    datos = descriptor_minimo()
    datos["apendices"] = [
        {
            "titulo": "Tabla de resistencias",
            "texto": "Valores comerciales.",
            "tabla": {
                "columnas": ["Serie", "Valor"],
                "filas": [["E12", "10"]],
            },
        }
    ]
    guia = gen.tex_guia(datos)
    comprobar("la guía incluye el apéndice", "Tabla de resistencias" in guia)
    comprobar("la guía incluye la tabla del apéndice", "E12 & 10" in guia)


def test_laboratorio_sin_imagenes() -> None:
    datos = descriptor_minimo()
    silabo = gen.tex_silabo(datos)
    readme = gen.md_laboratorio(datos)
    comprobar(
        "sin imágenes no se emite tabla de contenedores",
        "Contenedor & Imagen" not in silabo,
    )
    comprobar(
        "el README del laboratorio degrada a laboratorio físico",
        "no usa contenedores" in readme,
    )


def test_carpeta_y_unicode() -> None:
    datos = descriptor_minimo()
    comprobar(
        "la carpeta de entrega usa la plantilla",
        gen._carpeta_entrega(datos, 3) == "semana_03",
        gen._carpeta_entrega(datos, 3),
    )
    datos["entregas"]["carpeta"] = "practica-{n}"
    comprobar(
        "la carpeta admite otra plantilla",
        gen._carpeta_entrega(datos, 3) == "practica-3",
        gen._carpeta_entrega(datos, 3),
    )
    escapado = gen._t("τ = RC y Ω")
    comprobar(
        "las griegas de la prosa se convierten en matemática",
        r"$\tau$" in escapado and r"$\Omega$" in escapado,
        escapado,
    )


def test_matematica_en_prosa() -> None:
    """Un subíndice en el procedimiento no puede degradarse a dólares literales.

    ``_t()`` escapa ``$`` y ``_`` porque su contrato es texto plano, así que
    ``"$V_C$"`` se imprimía como "$V_C$" con los dólares visibles y el subíndice
    partido. Los campos de prosa pasan por ``_tm()``, que conserva la notación
    pero sigue escapando lo que rompería el documento aun dentro de matemática.
    """
    escapado = gen._tm(r"$V_C$ y 50 % de $1/\\sqrt{2}$")
    comprobar(
        "la matemática en línea se conserva en los campos de prosa",
        r"$V_C$" in escapado and r"$1/\\sqrt{2}$" in escapado,
        escapado,
    )
    comprobar(
        "el porcentaje se sigue escapando dentro de la prosa",
        r"50 \%" in escapado,
        escapado,
    )
    idempotente = gen._tm(r"$E_{\%}$")
    comprobar(
        "un '\\%' ya escapado no se convierte en '\\\\%'",
        idempotente == r"$E_{\%}$",
        idempotente,
    )
    lista = gen._lista(["Medir $V_C$ y $I$"], math=True)
    comprobar(
        "la lista con matemática no introduce dólares escapados",
        r"\$V_C\$" not in lista and "$V_C$" in lista,
        lista,
    )
    comprobar(
        "un subíndice suelto se detecta antes de compilar",
        gen._validar_matematica("Medir V_C", "pasos[0]") != [],
        str(gen._validar_matematica("Medir V_C", "pasos[0]")),
    )
    comprobar(
        "un '$' sin cerrar se detecta",
        any("impar" in p for p in gen._validar_matematica("Medir $V_C", "pasos[0]")),
        str(gen._validar_matematica("Medir $V_C", "pasos[0]")),
    )

    bien = descriptor_minimo()
    bien["semanas"][0]["practica"]["pasos"] = [r"Medir $V_C$ con el osciloscopio"]
    comprobar(
        "un descriptor con matemática en prosa valida",
        gen.validar(bien) == [],
        str(gen.validar(bien)),
    )
    mal = descriptor_minimo()
    mal["semanas"][0]["practica"]["pasos"] = ["Medir V_C con el osciloscopio"]
    comprobar(
        "un descriptor con subíndice suelto no valida",
        any("fuera de $...$" in p for p in gen.validar(mal)),
        str(gen.validar(mal)),
    )
    tex = gen.tex_practica(copy.deepcopy(bien), bien["semanas"][0])
    comprobar(
        "el LaTeX emitido lleva el subíndice, no el escape",
        r"$V_C$" in tex and r"\$V_C\$" not in tex,
    )


def test_determinismo() -> None:
    datos = descriptor_minimo()
    practica = datos["semanas"][0]["practica"]
    practica["fundamento_tex"] = "$V = IR$"
    practica["tabla_datos"] = {
        "columnas": ["V", "I"],
        "filas": [["0", "0"]],
    }
    primero = gen.tex_practica(copy.deepcopy(datos), datos["semanas"][0])
    segundo = gen.tex_practica(copy.deepcopy(datos), datos["semanas"][0])
    comprobar("la misma entrada produce el mismo LaTeX", primero == segundo)


def main() -> int:
    print("Pruebas del generador de material de cursos")
    test_descriptor_minimo_valido()
    test_resultados_de_aprendizaje_mal_formados_fallan()
    test_unicode_en_latex_crudo_falla()
    test_rubrica_que_no_suma_falla()
    test_rubrica_con_clave_invalida_falla()
    test_tabla_desalineada_falla()
    test_apendice_sin_contenido_falla()
    test_rubrica_desde_descriptor()
    test_secciones_de_practica()
    test_practica_sin_secciones_no_inventa()
    test_dominio_no_se_cuela()
    test_apendices_en_guia()
    test_laboratorio_sin_imagenes()
    test_carpeta_y_unicode()
    test_matematica_en_prosa()
    test_determinismo()

    print()
    if FALLOS:
        print(f"FALLOS: {len(FALLOS)}/{PRUEBAS}")
        for fallo in FALLOS:
            print(f"  - {fallo}")
        return 1
    print(f"Aserciones OK: {PRUEBAS}   Fallos: 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
