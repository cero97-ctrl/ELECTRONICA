#!/usr/bin/env python3
"""Pruebas del validador de `execution/inspeccionar_entrega.py`.

Por qué este test existe: el validador se escribió porque pasó de verdad. La primera
corrida real (corrección de Física, 1 página escaneada) devolvió un JSON con la forma

    {"text": "<transcripción entera del documento>", "preguntas": [], ...}

es decir, el modelo metió todo el contenido en un campo inventado y no emitió ni
`confianza` ni `tipo_documento`. Sin validación ese JSON habría pasado por un informe
correcto: tiene forma de objeto, se parsea, y dice algo que *parece* una inspección.
Son exactamente las dos cosas que un `json.loads()` no detecta.

La lección que fija este archivo: **`response_format={"type": "json_object"}` no es un
esquema**. Garantiza que la respuesta sea un objeto JSON; no garantiza que tenga las
claves que pediste. La barrera real es la validación en el programa, y por eso se testea
sin red y sin modelo.

Ejecutar: python3 execution/test_inspeccionar_entrega.py
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
        "inspeccionar_entrega_bajo_test", RAIZ / "execution/inspeccionar_entrega.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["inspeccionar_entrega_bajo_test"] = mod
    spec.loader.exec_module(mod)
    return mod


sys.path.insert(0, str(RAIZ / "execution"))
IE = _cargar()
validar = IE.validar


def completo() -> dict:
    return {
        "incluye_enunciado": True,
        "confianza": "alta",
        "tipo_documento": "examen resuelto",
        "asignatura": "Electrónica",
        "tema": "diodos y rectificadores",
        "preguntas": [{"numero": 1, "enunciado_breve": "diode real vs ideal",
                       "respondida": True}],
        "corregido_por": "",
        "observaciones": ["la letra es legible"],
    }


# ---------------------------------------------------------------------------
# 1. La salida que el modelo realmente produjo (el bug, congelado como test).
# ---------------------------------------------------------------------------
def test_el_json_real_del_modelo_se_rechaza():
    """La corrida que motivo este script: el modelo invento la forma del objeto."""
    real = {
        # Nombre y C.I. omitidos a proposito: lo que se congela aqui es la FORMA del
        # objeto (una clave `text` inventada), no la identidad de quien corrigio.
        "text": "Alumno: <apellido omitido> C.I: <omitido> Materia: Lab II de fisica ...",
        "preguntas": [],
        "corregido_por": "",
        "observaciones": [],
    }
    problemas = validar(real)
    comprobar("el JSON real del modelo tiene al menos un problema",
              len(problemas) > 0, f"llegó limpio: {real}")
    unido = " ".join(problemas)
    comprobar("señala que falta confianza", "confianza" in unido, unido)
    comprobar("señala que falta tipo_documento",
              "tipo_documento" in unido, unido)


def test_el_json_real_no_pasa_por_informe_valido():
    """Un objeto parseable NO es un informe. Esta es la asercion que lo defendia."""
    real = {"text": "lo que sea", "preguntas": [], "corregido_por": "",
            "observaciones": []}
    problemas = validar(real)
    # Ni una sola de las dos claves que hacen falta para decidir la vialidad del flujo.
    comprobar("no se puede decidir incluye_enunciado con ese JSON",
              "incluye_enunciado" in " ".join(problemas), str(problemas))


# ---------------------------------------------------------------------------
# 2. El camino feliz y los tres valores legitimos de incluye_enunciado.
# ---------------------------------------------------------------------------
def test_json_completo_pasa():
    comprobar("un JSON bien formado no da problemas", validar(completo()) == [],
              str(validar(completo())))


def test_incluye_enunciado_acepta_los_tres_valores():
    """incluye_enunciado=null es la SALUDABLE: 'no sé' beats inventar."""
    for valor, etiqueta in ((True, "true"), (False, "false"), (None, "null")):
        d = completo()
        d["incluye_enunciado"] = valor
        comprobar(f"incluye_enunciado={etiqueta} es valido",
                  validar(d) == [], str(validar(d)))


def test_incluye_enunciado_ausente_no_pasa():
    """La clave que NO esta, es peor que la clave con null. Se marca como problema."""
    d = completo()
    del d["incluye_enunciado"]
    problemas = validar(d)
    comprobar("incluye_enunciado ausente se reporta",
              any("incluye_enunciado" in p for p in problemas), str(problemas))


def test_confianza_fuera_del_vocabulario_falla():
    for malo in ("Alta", "ALTA", "segura", 3, None, ""):
        d = completo()
        d["confianza"] = malo
        comprobar(f"confianza={malo!r} se rechaza",
                  any("confianza" in p for p in validar(d)), str(validar(d)))


def test_tipo_documento_fuera_del_vocabulario_falla():
    """Vocabulario cerrado a proposito: un tipo libre rompe la agrupacion de casos."""
    for malo in ("examen", "Examen", "solo examen", "tarea", None):
        d = completo()
        d["tipo_documento"] = malo
        comprobar(f"tipo_documento={malo!r} se rechaza",
                  any("tipo_documento" in p for p in validar(d)), str(validar(d)))


def test_tipo_documento_acepta_los_cinco():
    for bueno in ("examen resuelto", "solo respuestas", "informe", "consulta", "otro"):
        d = completo()
        d["tipo_documento"] = bueno
        comprobar(f"tipo_documento={bueno!r} se acepta",
                  validar(d) == [], str(validar(d)))


# ---------------------------------------------------------------------------
# 3. Estructuras mal formadas: el programa debe NORMALIZAR para no reventar al
#    resumir() despues. Validar que detecte no basta: hay que dejar el dict usable.
# ---------------------------------------------------------------------------
def test_normaliza_listas_ausentes():
    d = completo()
    del d["preguntas"]
    del d["observaciones"]
    validar(d)
    comprobar("preguntas ausente -> []", d["preguntas"] == [], repr(d.get("preguntas")))
    comprobar("observaciones ausente -> []", d["observaciones"] == [],
              repr(d.get("observaciones")))


def test_normaliza_preguntas_que_no_son_lista():
    d = completo()
    d["preguntas"] = {"1": "no soy una lista"}
    problemas = validar(d)
    comprobar("preguntas como dict se reporta",
              any("preguntas" in p for p in problemas), str(problemas))
    comprobar("preguntas como dict -> [] (usable por resumir)",
              d["preguntas"] == [], repr(d["preguntas"]))


def test_pregunta_sin_numero_se_reporta_pero_no_se_borra():
    d = completo()
    d["preguntas"] = [{"enunciado_breve": "sin numero", "respondida": True},
                      {"numero": 2, "enunciado_breve": "bien", "respondida": True}]
    problemas = validar(d)
    comprobar("pregunta sin numero se reporta",
              any("numero" in p for p in problemas), str(problemas))
    comprobar("no se pierde ninguna pregunta al validar", len(d["preguntas"]) == 2,
              repr(d["preguntas"]))


def test_normaliza_corregido_por_none():
    """La correccion del profesor es el dato mas valioso; null no puede romper el JSON."""
    d = completo()
    d["corregido_por"] = None
    validar(d)
    comprobar("corregido_por null -> ''", d["corregido_por"] == "",
              repr(d["corregido_por"]))


def test_observaciones_no_lista_se_reporta_y_normaliza():
    d = completo()
    d["observaciones"] = "una sola cadena"
    problemas = validar(d)
    comprobar("observaciones como cadena se reporta",
              any("observaciones" in p for p in problemas), str(problemas))
    comprobar("observaciones como cadena -> []", d["observaciones"] == [],
              repr(d["observaciones"]))


# ---------------------------------------------------------------------------
# 4. Entradas que ni siquiera son objetos.
# ---------------------------------------------------------------------------
def test_una_lista_no_es_un_informe():
    problemas = validar([1, 2, 3])
    comprobar("una lista se rechaza de entrada",
              any("objeto JSON" in p for p in problemas), str(problemas))


def test_un_string_no_es_un_informe():
    comprobar("un string se rechaza de entrada", len(validar("texto")) > 0)


def test_no_rompe_si_faltan_casi_todas_las_claves():
    """Un {} vacio no debe lanzar KeyError: valida, reporta y deja el dict intacto."""
    try:
        problemas = validar({})
        ok = len(problemas) > 0
    except KeyError as e:
        ok = False
        problemas = [f"lanzó KeyError: {e}"]
    comprobar("un objeto vacio se valida sin lanzar", ok, str(problemas))
    comprobar("un objeto vacio reporta todos los problemas",
              len(problemas) >= 3, str(problemas))


# ---------------------------------------------------------------------------
# 5. El resumen legible no puede lanzar con una salida validada pero pobre.
# ---------------------------------------------------------------------------
def test_resumir_no_rompe_con_el_minimo_aceptable():
    d = {"incluye_enunciado": None, "confianza": "baja", "tipo_documento": "otro",
         "asignatura": "desconocido", "tema": "desconocido",
         "preguntas": [], "corregido_por": "", "observaciones": []}
    try:
        texto = IE.resumir(d)
        ok = "desconocido" in texto
    except Exception as e:  # noqa: BLE001
        ok, texto = False, f"lanzó {type(e).__name__}: {e}"
    comprobar("resumir() sobrevive a una inspección pobre", ok, texto)


def test_resumir_destaca_la_correccion_del_profesor():
    """Si el papel viene corregido, eso debe saltar a la vista: es maxima prioridad."""
    d = completo()
    d["corregido_por"] = "el profesor escribió 'mal' en la pregunta 2"
    texto = IE.resumir(d)
    comprobar("resumir() destaca corregido_por",
              "mal" in texto and "CORREGIDO" in texto, texto)


def test_resumir_no_inventa_correccion():
    texto = IE.resumir(completo())
    comprobar("resumir() no muestra CORREGIDO si no hay", "CORREGIDO" not in texto, texto)


def main() -> int:
    print("Pruebas del inspector de entregas")
    print("=" * 60)
    for fn in sorted(
        (f for f in globals() if f.startswith("test_")),
        key=lambda n: list(globals()).index(n),
    ):
        print(f"\n[{fn}]")
        globals()[fn]()
    print("\n" + "=" * 60)
    total = PRUEBAS
    print(f"{total - len(FALLOS)}/{total} aserciones OK")
    if FALLOS:
        print(f"\n{len(FALLOS)} FALLAS:")
        for f in FALLOS:
            print(f"  - {f}")
        return 1
    print("Sin fallos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())