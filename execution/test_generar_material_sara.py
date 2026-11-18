#!/usr/bin/env python3
"""Pruebas de `execution/generar_material_sara.py`.

Qué se fija aquí y por qué:
  - El contenido inválido falla ANTES de escribir. Un tema a medias en una
    página para estudiar es peor que no publicarlo: la estudiante no puede
    distinguir un error de edición de un error de la materia.
  - El sitio es offline de verdad: cero `http`, cero `src`, cero `<link>`.
    Una página que depende de la red falla justo cuando se necesita.
  - Los ejercicios son accesibles: `fieldset`/`legend`, radios con `label`,
    aviso con `aria-live` y ninguna nota que dependa solo del color.
  - La navegación entre temas es simétrica: el tema del medio tiene anterior
    y siguiente; el primero y el último, solo uno.
  - La salida es determinista y solo escribe dentro de `SARA/`.

Ejecutar: python3 execution/test_generar_material_sara.py
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path

import yaml

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
        "generar_material_sara_bajo_test",
        RAIZ / "execution/generar_material_sara.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["generar_material_sara_bajo_test"] = mod
    spec.loader.exec_module(mod)
    return mod


GEN = _cargar()


def leccion(materia: str = "matematicas", titulo: str = "Tema de prueba", orden: int = 1, **extra) -> dict:
    datos = {
        "materia": materia,
        "titulo": titulo,
        "orden": orden,
        "objetivo": "Reconocer la idea principal.",
        "idea_clave": "Una idea que se puede repetir.",
        "pasos": ["Primer paso.", "Segundo paso."],
        "ejemplo": {
            "titulo": "Ejemplo",
            "pasos": ["Dato uno.", "Dato dos."],
            "resultado": "Resultado correcto.",
        },
        "esquema": {
            "tipo": "tabla",
            "titulo": "Tabla de apoyo",
            "columnas": ["A", "B"],
            "filas": [["1", "2"]],
        },
        "practica": [
            {
                "pregunta": "¿Cuál es la respuesta?",
                "opciones": ["Correcta", "Incorrecta"],
                "correcta": 0,
                "explicacion": "Porque es la correcta.",
            }
        ],
        "recordar": ["Recuerda esto."],
    }
    datos.update(extra)
    return datos


def escribir(tmp: str, nombre: str, datos: dict) -> None:
    ruta = Path(tmp) / nombre
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(
        yaml.safe_dump(datos, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def tres_materias(tmp: str) -> None:
    escribir(tmp, "matematicas/01-tema.yaml", leccion("matematicas", "Tema de mate", 1))
    escribir(tmp, "fisica/01-tema.yaml", leccion("fisica", "Tema de física", 1))
    escribir(tmp, "quimica/01-tema.yaml", leccion("quimica", "Tema de química", 1))


def test_construye_las_paginas() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tres_materias(tmp)
        paginas, resumen = GEN.construir(tmp)
        comprobar("existe la portada", "index.html" in paginas)
        comprobar("existe la página de matemáticas", "matematicas/index.html" in paginas)
        comprobar("existe la página de física", "fisica/index.html" in paginas)
        comprobar("existe la página de química", "quimica/index.html" in paginas)
        comprobar("se generan 7 páginas", resumen["paginas"] == 7, str(resumen))
        comprobar("se cuentan 3 temas", resumen["temas"] == 3, str(resumen))


def test_es_determinista() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tres_materias(tmp)
        primera, _ = GEN.construir(tmp)
        segunda, _ = GEN.construir(tmp)
        comprobar("dos construcciones dan los mismos bytes", primera == segunda)


def test_sin_recursos_externos() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tres_materias(tmp)
        paginas, _ = GEN.construir(tmp)
        todo = "\n".join(paginas.values())
        comprobar("no hay http://", "http://" not in todo)
        comprobar("no hay https://", "https://" not in todo)
        comprobar("no hay <link>", "<link" not in todo)
        comprobar("no hay src=", "src=" not in todo)
        comprobar("no hay @import", "@import" not in todo)
        comprobar("cada página trae su CSS inline", todo.count("<style>") == len(paginas))
        comprobar("cada página trae su JS inline", todo.count("localStorage") >= len(paginas))


def test_escapa_el_texto() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        escribir(
            tmp,
            "matematicas/01-tema.yaml",
            leccion(titulo="Ecuación <b>cuadrática</b>"),
        )
        paginas, _ = GEN.construir(tmp)
        html = paginas["matematicas/01-ecuacion-bcuadratica-b.html"]
        comprobar("el título se escapa", "&lt;b&gt;" in html)
        comprobar("no se inyecta HTML del contenido", "<b>cuadrática</b>" not in html)


def test_slug_estable_con_tildes() -> None:
    comprobar(
        "una tilde no cambia el nombre del archivo",
        GEN._slug("Ecuación cuadrática") == "ecuacion-cuadratica",
        GEN._slug("Ecuación cuadrática"),
    )
    comprobar(
        "los espacios se convierten en guiones",
        GEN._slug("Mol y estequiometría") == "mol-y-estequiometria",
        GEN._slug("Mol y estequiometría"),
    )


def test_orden_duplicado_falla() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        escribir(tmp, "matematicas/a.yaml", leccion(titulo="Uno", orden=1))
        escribir(tmp, "matematicas/b.yaml", leccion(titulo="Dos", orden=1))
        try:
            GEN.construir(tmp)
        except GEN.ContenidoInvalido as exc:
            comprobar("el orden duplicado se rechaza", any("ya lo usa" in p for p in exc.problemas))
        else:
            comprobar("el orden duplicado se rechaza", False, "no lanzó ContenidoInvalido")


def test_titulo_duplicado_falla() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        escribir(tmp, "matematicas/a.yaml", leccion(titulo="Mismo", orden=1))
        escribir(tmp, "matematicas/b.yaml", leccion(titulo="Mismo", orden=2))
        try:
            GEN.construir(tmp)
        except GEN.ContenidoInvalido as exc:
            comprobar("el título duplicado se rechaza", any("mismo nombre" in p for p in exc.problemas))
        else:
            comprobar("el título duplicado se rechaza", False, "no lanzó ContenidoInvalido")


def test_correcta_fuera_de_rango_falla() -> None:
    datos = leccion(practica=[{
        "pregunta": "?",
        "opciones": ["a", "b"],
        "correcta": 5,
        "explicacion": "e",
    }])
    problemas = GEN.validar_leccion(datos)
    comprobar("correcta fuera de rango se rechaza", any("correcta debe estar" in p for p in problemas))


def test_esquema_invalido_falla() -> None:
    datos = leccion(esquema={"tipo": "grafico", "titulo": "x"})
    problemas = GEN.validar_leccion(datos)
    comprobar("un tipo de esquema inventado se rechaza", any("tabla, flujo o lista" in p for p in problemas))


def test_opciones_insuficientes_fallan() -> None:
    datos = leccion(practica=[{
        "pregunta": "?",
        "opciones": ["única"],
        "correcta": 0,
        "explicacion": "e",
    }])
    problemas = GEN.validar_leccion(datos)
    comprobar("una sola opción se rechaza", any("entre 2 y 6" in p for p in problemas))


def test_campo_faltante_falla() -> None:
    datos = leccion()
    del datos["idea_clave"]
    problemas = GEN.validar_leccion(datos)
    comprobar("falta idea_clave y se avisa", any("idea_clave" in p for p in problemas))


def test_tabla_descuadrada_falla() -> None:
    datos = leccion(esquema={
        "tipo": "tabla",
        "titulo": "Tabla",
        "columnas": ["A", "B"],
        "filas": [["1"]],
    })
    problemas = GEN.validar_leccion(datos)
    comprobar("una fila con menos celdas se rechaza", any("debe tener 2 celdas" in p for p in problemas))


def test_enlace_externo_falla() -> None:
    datos = leccion(nota="Ampliar en https://ejemplo.com")
    problemas = GEN.validar_leccion(datos)
    comprobar("un enlace externo se rechaza", any("sin internet" in p for p in problemas))


def test_navegacion_simetrica() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        escribir(tmp, "matematicas/a.yaml", leccion(titulo="Tema uno", orden=1))
        escribir(tmp, "matematicas/b.yaml", leccion(titulo="Tema dos", orden=2))
        escribir(tmp, "matematicas/c.yaml", leccion(titulo="Tema tres", orden=3))
        paginas, _ = GEN.construir(tmp)
        claves = sorted(k for k in paginas if k.startswith("matematicas/0"))
        primero = paginas[claves[0]]
        medio = paginas[claves[1]]
        ultimo = paginas[claves[2]]
        comprobar("el primero no tiene anterior", 'rel="prev"' not in primero)
        comprobar("el primero tiene siguiente", 'rel="next"' in primero)
        comprobar("el del medio tiene anterior", 'rel="prev"' in medio)
        comprobar("el del medio tiene siguiente", 'rel="next"' in medio)
        comprobar("el último tiene anterior", 'rel="prev"' in ultimo)
        comprobar("el último no tiene siguiente", 'rel="next"' not in ultimo)


def test_ejercicio_accesible() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        escribir(tmp, "matematicas/a.yaml", leccion())
        paginas, _ = GEN.construir(tmp)
        html = paginas["matematicas/01-tema-de-prueba.html"]
        comprobar("usa fieldset", '<fieldset class="ejercicio"' in html)
        comprobar("usa legend", "<legend>" in html)
        comprobar("los radios tienen label", '<input type="radio"' in html and "<label>" in html)
        comprobar("el aviso es aria-live", 'role="status" aria-live="polite"' in html)
        comprobar("la explicación está oculta hasta comprobar", 'class="explicacion" hidden' in html)
        comprobar("no hay puntaje ni cronómetro", "puntaje" not in html.lower() and "cronómetro" not in html.lower())


def test_portada_cuenta_los_temas() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        escribir(tmp, "matematicas/a.yaml", leccion(titulo="Uno", orden=1))
        escribir(tmp, "matematicas/b.yaml", leccion(titulo="Dos", orden=2))
        escribir(tmp, "matematicas/c.yaml", leccion(titulo="Tres", orden=3))
        paginas, _ = GEN.construir(tmp)
        comprobar("la portada muestra 3 temas", "3 temas" in paginas["index.html"])


def test_estructura_de_cada_pagina() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tres_materias(tmp)
        paginas, _ = GEN.construir(tmp)
        for nombre, html in paginas.items():
            comprobar(
                f"{nombre} declara español",
                '<html lang="es">' in html,
            )
            comprobar(
                f"{nombre} tiene un solo h1",
                html.count("<h1>") == 1,
                f"h1={html.count('<h1>')}",
            )
            comprobar(
                f"{nombre} tiene enlace para saltar",
                'class="saltar"' in html,
            )


def test_barrera_de_salida() -> None:
    comprobar("SARA/ es una salida permitida", GEN._salida_permitida(RAIZ / "SARA"))
    comprobar(
        "una subcarpeta de SARA/ es permitida",
        GEN._salida_permitida(RAIZ / "SARA" / "sub"),
    )
    comprobar(
        "docs/ no es una salida permitida",
        not GEN._salida_permitida(RAIZ / "docs"),
    )


def test_solo_escribe_html() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        try:
            GEN.escribir({"index.txt": "x"}, tmp)
        except ValueError:
            comprobar("una extensión distinta de .html se rechaza", True)
        else:
            comprobar("una extensión distinta de .html se rechaza", False)


def test_check_en_json() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tres_materias(tmp)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            codigo = GEN.ejecutar(contenido=tmp, check=True, json_out=True)
        salida = json.loads(buffer.getvalue())
        comprobar("--check devuelve 0", codigo == 0)
        comprobar("--check informa status ok", salida.get("status") == "ok")
        comprobar("--check cuenta 3 temas", salida.get("temas") == 3, str(salida))


def main() -> int:
    print("Pruebas del generador del material de Sara")
    print("=" * 60)
    for fn in sorted(
        (f for f in globals() if f.startswith("test_")),
        key=lambda n: list(globals()).index(n),
    ):
        print(f"\n[{fn}]")
        globals()[fn]()
    print("\n" + "=" * 60)
    print(f"{PRUEBAS - len(FALLOS)}/{PRUEBAS} aserciones OK")
    if FALLOS:
        print(f"\n{len(FALLOS)} FALLAS:")
        for fallo in FALLOS:
            print(f"  - {fallo}")
        return 1
    print("Sin fallos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
