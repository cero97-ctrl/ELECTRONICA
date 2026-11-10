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


def test_evaluacion_final_lista_no_es_repr_de_python() -> None:
    """Una lista de condiciones debe salir como lista, no como `str(lista)`.

    El descriptor de referencia declara `condiciones` como lista. Pasarla por
    `_t()` la convertía en `['Duración...', 'Sin apuntes...']`, que es Python
    impreso en el PDF del alumno; el texto seguía compilando, así que el fallo
    no se veía hasta leer la página.
    """
    datos = descriptor_minimo()
    datos["evaluacion_final"] = {
        "titulo": "Cierre del curso",
        "semana": 2,
        "secciones": [{"nombre": "Sección única", "puntaje": 10}],
        "condiciones": ["Sin apuntes.", "Duración de dos horas."],
    }
    tex = gen.tex_evaluacion_final(datos)
    comprobar(
        "las condiciones se emiten como lista",
        r"\begin{itemize}" in tex,
        "no aparece itemize",
    )
    comprobar("no queda el repr de Python", "['" not in tex, "aparece [' en el LaTeX")
    comprobar(
        "cada condición aparece en el documento",
        "Sin apuntes." in tex and "Duración de dos horas." in tex,
    )


def test_semana_de_teoria_se_rotula_taller() -> None:
    """Una semana de teoría no debe emitirse como "Práctica".

    Un curso de laboratorio puede dedicar las primeras semanas a teoría de
    errores y análisis gráfico. Rotular ese documento como Práctica NN hace creer
    al alumno que va a medir, y además nombra `practica_01.tex` a un taller. El
    tipo es un dato del descriptor y su vocabulario es cerrado: `practica` o
    `teoria`; cualquier otro valor se rechaza antes de escribir nada.
    """
    datos = descriptor_minimo()
    datos["semanas"][0]["tipo"] = "teoria"
    problemas = gen.validar(datos)
    comprobar("tipo=teoria valida el descriptor", problemas == [], str(problemas))

    tex = gen.tex_practica(copy.deepcopy(datos), datos["semanas"][0])
    plan = gen.tex_plan_semanal(copy.deepcopy(datos))
    comprobar("la banda del documento dice 'Taller 01'", "Taller 01" in tex)
    comprobar("la banda no dice 'Práctica 01'", "Práctica 01" not in tex)
    comprobar("el plan semanal rotula 'Taller.'", r"\textbf{Taller.}" in plan)

    datos["semanas"][0]["tipo"] = "taller"
    problemas = gen.validar(datos)
    comprobar(
        "un tipo fuera del vocabulario falla",
        any("no válido" in p for p in problemas),
        str(problemas),
    )


def test_tema_de_control_es_editorial() -> None:
    """La tabla de puntaje usa el tema del descriptor; el automático es respaldo.

    El respaldo tomaba las primeras palabras del enunciado y producía etiquetas
    telegráficas del tipo «reporta longitud Calcule error», que no describen el
    tema evaluado. El descriptor manda.
    """
    datos = descriptor_minimo()
    control = {
        "fase": 1,
        "titulo": "Control de prueba",
        "duracion_min": 45,
        "preguntas": [
            {
                "enunciado": "Calcule el error relativo de una longitud medida.",
                "puntaje": 5.0,
                "tema": "Error relativo y porcentual",
            },
            {
                "enunciado": "Explique la diferencia entre exactitud y precisión.",
                "puntaje": 5.0,
            },
        ],
    }
    tex = gen.tex_control(copy.deepcopy(datos), control)
    comprobar(
        "el tema declarado en el control se imprime tal cual",
        "Error relativo y porcentual" in tex,
    )
    comprobar(
        "sin tema, se deriva una etiqueta del enunciado",
        "Explique diferencia entre exactitud" in tex,
        tex,
    )


def test_enunciado_de_control_con_matematica_no_se_escapa() -> None:
    """Los enunciados se escapaban como texto plano y la matemática salía cruda:
    `$L = 2{,}45 \\pm 0{,}03$ cm` se imprimía como `$L = 2{,}45 \\{}pm 0{,}03$ cm`.
    El enunciado es un campo con matemática (como `pasos` o `escenario`): se
    renderiza con `_tm` y `validar_preguntas` lo custodia. Desde que el descriptor
    es público, el enunciado llega del banco y se valida ya compuesto.
    """
    datos = descriptor_minimo()
    datos["controles"] = [
        {
            "fase": 1,
            "titulo": "Control de prueba",
            "duracion_min": 45,
            "preguntas": [{"puntaje": 10.0}],
        }
    ]
    comprobar(
        "un descriptor público sin enunciados valida",
        gen.validar(datos) == [],
        str(gen.validar(datos)),
    )
    variante = {
        "numero": 1,
        "estado": "utilizable",
        "controles": [
            {
                "fase": 1,
                "preguntas": [
                    {"enunciado": "Se reporta $L = 2{,}45 \\pm 0{,}03$ cm. Calcule el error relativo."}
                ],
            }
        ],
    }
    compuesto = gen.componer_controles(datos, variante)
    tex = gen.tex_control(copy.deepcopy(datos), compuesto[0])
    comprobar(
        "la matemática del enunciado llega intacta al LaTeX",
        r"$L = 2{,}45 \pm 0{,}03$" in tex,
        tex,
    )
    comprobar(
        "no queda ninguna barra escapada en el enunciado",
        "\\{}pm" not in tex and "textbackslash" not in tex,
        tex,
    )
    comprobar(
        "el enunciado compuesto con matemática correcta valida",
        gen.validar_preguntas(compuesto) == [],
        str(gen.validar_preguntas(compuesto)),
    )
    roto = copy.deepcopy(variante)
    roto["controles"][0]["preguntas"][0]["enunciado"] = "Calcule V_C del cilindro."
    problemas = gen.validar_preguntas(gen.componer_controles(datos, roto))
    comprobar(
        "un subíndice fuera de $...$ en el enunciado falla la validación",
        any("pregunta 1.enunciado" in p for p in problemas),
        str(problemas),
    )


def test_roles_por_integrante_independientes_del_numero_de_grupos() -> None:
    """La tabla de rotación traía cuatro columnas fijas «Grupo 1..4» y el
    validador exigía tantos roles como grupos. Los roles rotan DENTRO de cada
    grupo (el propio YAML dice «cada integrante haya ocupado los cuatro
    roles»), así que con dos grupos la tabla y la validación reventaban. Las
    columnas pasan a ser posiciones de integrante y `cantidad` queda libre.
    """
    datos = descriptor_minimo()
    datos["grupos"] = {
        "cantidad": 2,
        "asignacion": "Dos grupos fijos durante el semestre.",
        "roles": [
            {
                "nombre": nombre,
                "descripcion": f"Descripción de {nombre}.",
                "aporta": f"Aporte de {nombre}.",
            }
            for nombre in ("Medición", "Análisis", "Documentación", "Verificación")
        ],
        "asignacion_inicial": ["Medición", "Análisis", "Documentación", "Verificación"],
        "fase_con_roles": [1],
        "rotaciones": ["Semanas 1-2", "Semanas 3-4", "Semanas 5-7", "Semanas 8-10"],
    }
    comprobar(
        "dos grupos con cuatro roles validan sin problemas",
        gen.validar(datos) == [],
        str(gen.validar(datos)),
    )
    guia = gen.tex_guia(copy.deepcopy(datos))
    comprobar(
        "la guía declara el número de grupos del descriptor",
        "El curso trabaja con 2 grupos" in guia,
        guia,
    )
    comprobar(
        "las columnas de la tabla son integrantes, no grupos",
        "Integrante 1" in guia and "Grupo 4" not in guia,
        guia,
    )
    comprobar(
        "las filas de la tabla son las rotaciones del descriptor",
        "Semanas 1-2" in guia and "Semanas 8-10" in guia and guia.count("Semanas ") >= 4,
        guia,
    )
    cortas = copy.deepcopy(datos)
    cortas["grupos"]["rotaciones"] = ["Semanas 1-5", "Semanas 6-10"]
    comprobar(
        "menos rotaciones que roles falla la validación",
        any("grupos.rotaciones" in p for p in gen.validar(cortas)),
        str(gen.validar(cortas)),
    )
    mal = copy.deepcopy(datos)
    mal["grupos"]["cantidad"] = 0
    comprobar(
        "una cantidad de grupos no positiva falla la validación",
        any("grupos.cantidad" in p for p in gen.validar(mal)),
        str(gen.validar(mal)),
    )


# ── Banco privado de preguntas ────────────────────────────────────────────────


def banco_minimo() -> dict:
    """Banco de prueba: una variante utilizable, una comprometida y un borrador."""
    return {
        "meta": {"curso": "CURSO_TEST", "escala": 10},
        "variantes": [
            {
                "numero": 1,
                "estado": "utilizable",
                "creada": "2026-11-08",
                "controles": [
                    {
                        "fase": 1,
                        "preguntas": [
                            {"enunciado": "Pregunta uno del banco."},
                            {"enunciado": "Pregunta dos del banco."},
                        ],
                    }
                ],
            },
            {
                "numero": 2,
                "estado": "comprometida",
                "creada": "2026-11-08",
                "controles": [
                    {
                        "fase": 1,
                        "preguntas": [
                            {"enunciado": "Otra pregunta uno."},
                            {"enunciado": "Otra pregunta dos."},
                        ],
                    }
                ],
            },
            {"numero": 3, "estado": "borrador", "creada": "2026-11-08", "controles": []},
        ],
    }


def descriptor_con_control_publico() -> dict:
    """Descriptor con un control de dos posiciones y sin enunciados."""
    datos = descriptor_minimo()
    datos["controles"] = [
        {
            "fase": 1,
            "titulo": "Control de prueba",
            "duracion_min": 45,
            "preguntas": [
                {"puntaje": 5.0, "tema": "Tema uno"},
                {"puntaje": 5.0},
            ],
        }
    ]
    return datos


def test_descriptor_publico_rechaza_enunciado() -> None:
    """El descriptor viaja en un repo público: un `enunciado` ahí es una fuga.

    Antes de este contrato el enunciado vivía en `curso.yaml`, que está
    versionado: cualquiera con el enlace leía el examen. El validador lo rechaza
    para que la fuga no pueda volver por descuido.
    """
    datos = descriptor_con_control_publico()
    comprobar(
        "un control público (sin enunciado) valida",
        gen.validar(datos) == [],
        str(gen.validar(datos)),
    )
    fugado = copy.deepcopy(datos)
    fugado["controles"][0]["preguntas"][0]["enunciado"] = "Pregunta filtrada."
    problemas = gen.validar(fugado)
    comprobar(
        "un enunciado en el descriptor público falla la validación",
        any("no lleva 'enunciado'" in p for p in problemas),
        str(problemas),
    )
    sin_puntaje = copy.deepcopy(datos)
    del sin_puntaje["controles"][0]["preguntas"][0]["puntaje"]
    comprobar(
        "una posición sin puntaje falla la validación",
        any("falta 'puntaje'" in p for p in gen.validar(sin_puntaje)),
        str(gen.validar(sin_puntaje)),
    )


def test_banco_elige_la_unica_utilizable() -> None:
    """Sin `--variante` la elección es determinista: la única `utilizable`.

    Elegir «la primera» o «la última» haría que dos corridas del mismo comando
    pudieran emitir exámenes distintos. Si no hay exactamente una utilizable, el
    programa se detiene en vez de adivinar.
    """
    banco = banco_minimo()
    elegida = gen.seleccionar_variante(banco)
    comprobar("sin número se elige la única utilizable", elegida["numero"] == 1)
    comprobar(
        "la elección es la misma en llamadas repetidas",
        gen.seleccionar_variante(banco)["numero"] == 1,
    )
    comprobar(
        "una variante comprometida exige confirmación explícita",
        "comprometida" in _error_de(gen.seleccionar_variante, banco, 2),
    )
    comprobar(
        "con permiso explícito la comprometida se aplica",
        gen.seleccionar_variante(banco, 2, permitir_comprometida=True)["numero"] == 2,
    )
    comprobar(
        "una variante en borrador nunca se aplica",
        "borrador" in _error_de(gen.seleccionar_variante, banco, 3, True),
    )
    mensaje = _error_de(gen.seleccionar_variante, banco, 9)
    comprobar(
        "una variante inexistente lista las disponibles",
        "no existe" in mensaje and "1, 2, 3" in mensaje,
        mensaje,
    )


def test_banco_ambiguo_o_sin_utilizables_falla() -> None:
    """Dos utilizables (o ninguna) es un error de configuración, no un empate."""
    dos = banco_minimo()
    dos["variantes"][2]["estado"] = "utilizable"
    comprobar(
        "dos variantes utilizables exigen --variante",
        "varias variantes" in _error_de(gen.seleccionar_variante, dos),
    )
    ninguna = banco_minimo()
    ninguna["variantes"][0]["estado"] = "borrador"
    comprobar(
        "sin ninguna utilizable el error pide elegir una",
        "ninguna variante" in _error_de(gen.seleccionar_variante, ninguna),
    )


def test_banco_con_estructura_invalida_falla() -> None:
    """El banco es dato privado y no pasa por revisión: se valida al cargarlo."""
    sin_variantes = {"meta": {}, "variantes": []}
    comprobar(
        "un banco sin variantes se rechaza",
        "variantes" in _error_de(gen.variantes_del_banco, sin_variantes),
    )
    repetida = banco_minimo()
    repetida["variantes"][1]["numero"] = 1
    comprobar(
        "dos variantes con el mismo número se rechazan",
        "repetido" in _error_de(gen.variantes_del_banco, repetida),
    )
    sin_numero = banco_minimo()
    del sin_numero["variantes"][0]["numero"]
    comprobar(
        "una variante sin número entero se rechaza",
        "entero" in _error_de(gen.variantes_del_banco, sin_numero),
    )
    estado_raro = banco_minimo()
    estado_raro["variantes"][1]["estado"] = "publicada"
    comprobar(
        "un estado fuera del vocabulario se rechaza",
        "estado" in _error_de(gen.seleccionar_variante, estado_raro, 2, True),
    )
    comprobar(
        "un banco inexistente se reporta con su ruta",
        "no encontrado" in _error_de(
            gen.cargar_banco, RAIZ / ".tmp" / "banco_que_no_existe.yaml"
        ),
    )


def test_componer_controles_empareja_por_orden() -> None:
    """El banco aporta el texto; el descriptor, cuántas preguntas y cuánto valen.

    Un emparejamiento por contenido o por número de pregunta sería frágil; por
    fase y orden es predecible y un desajuste de conteo falla en vez de rellenar.
    """
    datos = descriptor_con_control_publico()
    variante = gen.seleccionar_variante(banco_minimo())
    compuestos = gen.componer_controles(datos, variante)
    preguntas = compuestos[0]["preguntas"]
    comprobar(
        "las preguntas recibidas conservan el orden del banco",
        [p["enunciado"] for p in preguntas]
        == ["Pregunta uno del banco.", "Pregunta dos del banco."],
    )
    comprobar(
        "el puntaje del descriptor sobrevive a la composición",
        [p["puntaje"] for p in preguntas] == [5.0, 5.0],
    )
    comprobar(
        "el tema del descriptor no se pierde",
        preguntas[0]["tema"] == "Tema uno",
    )
    tex = gen.tex_control(copy.deepcopy(datos), compuestos[0])
    comprobar(
        "el control compuesto imprime los enunciados del banco",
        "Pregunta uno del banco." in tex and "Pregunta dos del banco." in tex,
    )
    comprobar(
        "el control compuesto valida",
        gen.validar_preguntas(compuestos) == [],
        str(gen.validar_preguntas(compuestos)),
    )
    faltan = copy.deepcopy(variante)
    faltan["controles"][0]["preguntas"].pop()
    comprobar(
        "un banco con menos preguntas que el descriptor falla",
        "declara 2" in _error_de(gen.componer_controles, datos, faltan),
    )
    otra_fase = copy.deepcopy(variante)
    otra_fase["controles"][0]["fase"] = 2
    mensaje = _error_de(gen.componer_controles, datos, otra_fase)
    comprobar(
        "un banco que no cubre la fase del descriptor falla",
        "no cubre la fase 1" in mensaje,
        mensaje,
    )
    discrepante = copy.deepcopy(variante)
    discrepante["controles"][0]["preguntas"][0]["puntaje"] = 3.0
    comprobar(
        "un puntaje del banco que no coincide con el descriptor falla",
        "debe coincidir" in _error_de(gen.componer_controles, datos, discrepante),
    )


def test_descriptores_reales_sin_enunciados() -> None:
    """Los tres cursos del repo deben quedar públicos: cero enunciados.

    Este test es la puerta contra la regresión real: el generador sigue
    aceptando un `enunciado` inline para poder renderizar el control compuesto,
    así que nada impediría que un `curso.yaml` volviera a llevarlo salvo este
    chequeo sobre los ficheros que están en git.
    """
    for nombre in ("CYBERSEGURIDAD", "LABORATORIO_I_FISICA", "LABORATORIO_II_FISICA"):
        ruta = RAIZ / "cursos" / nombre / "curso.yaml"
        if not ruta.exists():
            comprobar(f"{nombre}: el descriptor existe", False, str(ruta))
            continue
        datos = gen.cargar_descriptor(ruta)
        problemas = gen.validar(datos)
        comprobar(f"{nombre}: descriptor público válido", problemas == [], str(problemas))
        fugas = [
            (control.get("fase"), i)
            for control in datos.get("controles") or []
            for i, pregunta in enumerate(control.get("preguntas") or [], 1)
            if "enunciado" in pregunta
        ]
        comprobar(f"{nombre}: ningún control lleva enunciado", fugas == [], str(fugas))


# ── Evaluación teórica del trabajo de grupo ─────────────────────────────────


def descriptor_con_teoricas() -> dict:
    """Descriptor de dos semanas con grupos, roles y calendario teórico."""
    datos = descriptor_minimo()
    datos["grupos"] = {
        "cantidad": 2,
        "asignacion_inicial": ["Rojo", "Azul"],
        "roles": [
            {"nombre": "Rojo", "en_la_practica": ["Lectura del entregable"]},
            {"nombre": "Azul", "en_la_practica": ["Revisión de la evidencia"]},
        ],
        "fase_con_roles": [1],
    }
    datos["evaluacion"]["teorica_semanas"] = [1, 2]
    for numero in (1, 2):
        datos["semanas"][numero - 1]["ejemplos"] = [
            {
                "grupo": grupo,
                "titulo": f"Tarea de la semana {numero}, grupo {grupo}",
                "entregable": f"semana_{numero:02d}/informe.md",
            }
            for grupo in (1, 2)
        ]
    return datos


def banco_con_teoricas() -> dict:
    """Banco con una variante teórica completa: 2 semanas x 2 grupos."""
    examenes = [
        {
            "semana": semana,
            "grupo": grupo,
            "preguntas": [
                {"puntaje": 2.5, "enunciado": f"Pregunta {i} de {semana}/{grupo}."}
                for i in range(1, 5)
            ],
        }
        for semana in (1, 2)
        for grupo in (1, 2)
    ]
    return {
        "meta": {"curso": "CURSO_TEST", "escala": 10},
        "teoricas": [
            {
                "numero": 1,
                "estado": "utilizable",
                "creada": "2026-11-09",
                "examenes": examenes,
            }
        ],
    }


def test_teoricas_cubren_semanas_por_grupo() -> None:
    """La cobertura es el producto exacto: una prueba por semana y por grupo."""
    datos = descriptor_con_teoricas()
    variante = gen.seleccionar_variante_teoricas(banco_con_teoricas())
    examenes = gen.componer_teoricas(datos, variante)
    comprobar(
        "2 semanas x 2 grupos producen 4 exámenes",
        len(examenes) == 4,
        str(len(examenes)),
    )
    comprobar(
        "los exámenes salen ordenados por semana y grupo",
        [(e["semana"], e["grupo"]) for e in examenes] == [(1, 1), (1, 2), (2, 1), (2, 2)],
        str([(e["semana"], e["grupo"]) for e in examenes]),
    )
    comprobar(
        "el rol se deriva de la misma rotación que la instrucción de la semana",
        [e["rol"] for e in examenes] == ["Rojo", "Azul", "Rojo", "Azul"],
        str([e["rol"] for e in examenes]),
    )
    comprobar(
        "el título del examen es el trabajo entregado por ese grupo",
        examenes[0]["titulo"] == "Tarea de la semana 1, grupo 1",
        examenes[0]["titulo"],
    )


def test_teoricas_faltante_o_sobrante_falla() -> None:
    """Un hueco no se rellena con una prueba genérica: se nombra el par ausente."""
    datos = descriptor_con_teoricas()
    banco = banco_con_teoricas()
    banco["teoricas"][0]["examenes"].pop()
    mensaje = _error_de(
        gen.componer_teoricas, datos, gen.seleccionar_variante_teoricas(banco)
    )
    comprobar(
        "falta un examen y el error nombra semana y grupo",
        "semana 2 grupo 2" in mensaje,
        mensaje,
    )

    datos_uno = descriptor_con_teoricas()
    datos_uno["evaluacion"]["teorica_semanas"] = [1]
    mensaje = _error_de(
        gen.componer_teoricas, datos_uno, gen.seleccionar_variante_teoricas(banco_con_teoricas())
    )
    comprobar(
        "un examen fuera del calendario se rechaza en vez de emitirse",
        "fuera del calendario" in mensaje,
        mensaje,
    )


def test_teoricas_puntajes_y_forma_fallan_ruidosamente() -> None:
    datos = descriptor_con_teoricas()
    banco = banco_con_teoricas()
    banco["teoricas"][0]["examenes"][0]["preguntas"][0]["puntaje"] = 3.0
    mensaje = _error_de(
        gen.componer_teoricas, datos, gen.seleccionar_variante_teoricas(banco)
    )
    comprobar(
        "puntajes que no cierran en la escala se rechazan con la suma",
        "suman 10.50" in mensaje,
        mensaje,
    )

    datos = descriptor_con_teoricas()
    banco = banco_con_teoricas()
    banco["teoricas"][0]["examenes"][0]["preguntas"].pop()
    mensaje = _error_de(
        gen.componer_teoricas, datos, gen.seleccionar_variante_teoricas(banco)
    )
    comprobar(
        "un examen con menos de 4 preguntas se rechaza",
        "debe traer 4 preguntas" in mensaje,
        mensaje,
    )

    datos = descriptor_con_teoricas()
    del datos["semanas"][0]["ejemplos"][0]["entregable"]
    mensaje = _error_de(
        gen.componer_teoricas, datos, gen.seleccionar_variante_teoricas(banco_con_teoricas())
    )
    comprobar(
        "un ejemplo sin entregable no genera prueba",
        "no declara 'entregable'" in mensaje,
        mensaje,
    )


def test_teoricas_calendario_publico_se_valida() -> None:
    datos = descriptor_con_teoricas()
    comprobar(
        "un calendario teórico completo valida",
        gen.validar(datos) == [],
        str(gen.validar(datos)),
    )
    repetido = copy.deepcopy(datos)
    repetido["evaluacion"]["teorica_semanas"] = [1, 1]
    comprobar(
        "una semana repetida en el calendario falla",
        any("está repetida" in p for p in gen.validar(repetido)),
        str(gen.validar(repetido)),
    )
    inexistente = copy.deepcopy(datos)
    inexistente["evaluacion"]["teorica_semanas"] = [9]
    comprobar(
        "una semana inexistente en el calendario falla",
        any("no existe" in p for p in gen.validar(inexistente)),
        str(gen.validar(inexistente)),
    )
    sin_tarea = copy.deepcopy(datos)
    sin_tarea["semanas"][0]["ejemplos"] = sin_tarea["semanas"][0]["ejemplos"][:1]
    comprobar(
        "una semana sin tarea para todos los grupos falla",
        any("no tiene tarea para el grupo 2" in p for p in gen.validar(sin_tarea)),
        str(gen.validar(sin_tarea)),
    )


def test_teoricas_latex_y_rubrica() -> None:
    """El instrumento nombra a su grupo y la rúbrica es pública y cierra a 10."""
    datos = descriptor_con_teoricas()
    examen = gen.componer_teoricas(datos, gen.seleccionar_variante_teoricas(banco_con_teoricas()))[1]
    tex = gen.tex_teorica(datos, datos["semanas"][0], 2, examen)
    comprobar("el instrumento nombra la semana y el grupo", "Semana 01" in tex and "Grupo 2" in tex, "")
    comprobar("el instrumento declara el rol del grupo", "Azul" in tex, "")
    comprobar("el instrumento no filtra preguntas de otro grupo", "de 1/1" not in tex, "")

    rubrica = yaml.safe_load(gen.yaml_rubrica_teorica(datos)) if yaml else {}
    pesos = [c["peso"] for c in (rubrica.get("criterios") or {}).values()]
    comprobar("la rúbrica teórica declara criterios", bool(pesos), str(rubrica))
    comprobar("los pesos de la rúbrica teórica suman 10", abs(sum(pesos) - 10) < 0.001, str(pesos))

    repetido = gen.tex_teorica(datos, datos["semanas"][0], 2, examen)
    comprobar("el instrumento es determinista", tex == repetido)


def test_teoricas_matematica_invalida_falla() -> None:
    """Un `_` crudo fuera de `$...$` rompe pdflatex; la validación lo caza antes."""
    datos = descriptor_con_teoricas()
    banco = banco_con_teoricas()
    banco["teoricas"][0]["examenes"][0]["preguntas"][0]["enunciado"] = (
        "Explique la diferencia entre semana_02 y la carpeta entregada."
    )
    examenes = gen.componer_teoricas(datos, gen.seleccionar_variante_teoricas(banco))
    problemas = gen.validar_teoricas(examenes)
    comprobar(
        "un guion bajo fuera de matemática se rechaza",
        any("semana_02" in p or "_" in p for p in problemas),
        str(problemas),
    )
    comprobar(
        "matemática bien delimitada no genera falsos positivos",
        gen.validar_teoricas(
            gen.componer_teoricas(datos, gen.seleccionar_variante_teoricas(banco_con_teoricas()))
        ) == [],
        "",
    )


def _error_de(funcion, *args, **kwargs) -> str:
    """Devuelve el mensaje del ValueError que lanza `funcion`, o el fallo."""
    try:
        funcion(*args, **kwargs)
    except (ValueError, OSError) as exc:
        return str(exc)
    return f"(no lanzó error: {funcion.__name__})"


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
    test_evaluacion_final_lista_no_es_repr_de_python()
    test_semana_de_teoria_se_rotula_taller()
    test_tema_de_control_es_editorial()
    test_enunciado_de_control_con_matematica_no_se_escapa()
    test_roles_por_integrante_independientes_del_numero_de_grupos()
    test_descriptor_publico_rechaza_enunciado()
    test_banco_elige_la_unica_utilizable()
    test_banco_ambiguo_o_sin_utilizables_falla()
    test_banco_con_estructura_invalida_falla()
    test_componer_controles_empareja_por_orden()
    test_descriptores_reales_sin_enunciados()
    test_teoricas_cubren_semanas_por_grupo()
    test_teoricas_faltante_o_sobrante_falla()
    test_teoricas_puntajes_y_forma_fallan_ruidosamente()
    test_teoricas_calendario_publico_se_valida()
    test_teoricas_latex_y_rubrica()
    test_teoricas_matematica_invalida_falla()
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
