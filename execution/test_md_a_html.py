#!/usr/bin/env python3
"""Pruebas del conversor `execution/md_a_html.py`.

Fija el contrato que hace que un examen pueda publicarse sin filtrar la clave:
la variante alumno no debe contener la clave, la docente sí, y el HTML no debe
depender de la red **salvo MathJax**, que es la única URL externa permitida
(sin él la matemática de los cuestionarios de física se lee en crudo).
También fija el determinismo (mismo .md -> mismos bytes) y la barrera de rutas
(nunca fuera de `cursos/<CURSO>/evaluaciones/web/`).

Ejecutar: python3 execution/test_md_a_html.py
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
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
        "md_a_html_bajo_test", RAIZ / "execution/md_a_html.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["md_a_html_bajo_test"] = mod
    spec.loader.exec_module(mod)
    return mod


M = _cargar()

CDN_MATHJAX = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"


def _red_externa(html: str) -> list[str]:
    """URLs externas del HTML salvo el CDN de MathJax (única excepción)."""
    return [
        linea.strip()
        for linea in html.splitlines()
        if ("http://" in linea or "https://" in linea) and CDN_MATHJAX not in linea
    ]

FUENTE = """# Cuestionario de prueba

## Question 1

¿Cuál es la respuesta correcta?

- A. Incorrecta.
- B. Correcta con `código`.
- C. Otra incorrecta.
- D. La última.

## Pregunta 2

Segunda pregunta.

- A. Sí.
- B. No.
"""

META = {
    "curso": "CYBERSEGURIDAD",
    "tipo": "cuestionario",
    "titulo": "Cuestionario de prueba",
    "puntaje_total": 2,
    "clave": {1: "B", 2: "A"},
}

RESPUESTAS = """# Cuestionario de prueba

> 2 preguntas

## pregunta 1

¿Cuál es la respuesta correcta?

- A. Incorrecta.
- B. Correcta con `código`.
- C. Otra incorrecta.
- D. La última.

**Answer:** B. Correcta con `código`.

**Hint:** Piensa en el código.

**Explanation:**

- A ✗ No.
- B ✓ Sí.

## pregunta 2

Segunda pregunta.

- A. Sí.
- B. No.

**Answer:** A. Sí.
"""

FUENTE_JUST = """---
curso: CYBERSEGURIDAD
tipo: cuestionario
titulo: Cuestionario de prueba
puntaje_total: 2
clave:
  1: B
  2: A
justificacion_items: [1]
---

# Cuestionario de prueba

## Pregunta 1

¿Cuál es la respuesta correcta?

- A. Incorrecta.
- B. Correcta con `código`.
- C. Otra incorrecta.
- D. La última.

**Justificación:** Cita el archivo y la línea de tu repositorio que demuestran la respuesta, con la salida del comando que ejecutaste.

## Pregunta 2

Segunda pregunta.

- A. Sí.
- B. No.
"""

META_JUST = {**META, "justificacion_items": [1]}

RESPUESTAS_JUST = """# Cuestionario de prueba

## pregunta 1

¿Cuál es la respuesta correcta?

- A. Incorrecta.
- B. Correcta con `código`.
- C. Otra incorrecta.
- D. La última.

**Answer:** B. Correcta con `código`.

**Justificación:** Cita el archivo y la línea de tu repositorio que demuestran la respuesta, con la salida del comando que ejecutaste.

**Explanation:**

- A ✗ No.
- B ✓ Sí.

## pregunta 2

Segunda pregunta.

- A. Sí.
- B. No.

**Answer:** A. Sí.
"""


def _ejecutar_main(argv: list[str]) -> tuple[int, dict]:
    anterior = sys.argv
    sys.argv = ["md_a_html.py", *argv]
    salida = io.StringIO()
    try:
        with contextlib.redirect_stdout(salida):
            codigo = M.main()
    finally:
        sys.argv = anterior
    return codigo, json.loads(salida.getvalue())


def _preguntas() -> list[dict]:
    return M._parsear_cuestionario(FUENTE)


def test_parser():
    preguntas = _preguntas()
    comprobar("parser encuentra 2 preguntas", len(preguntas) == 2, str(len(preguntas)))
    comprobar("parser conserva el enunciado", "respuesta correcta" in preguntas[0]["enunciado"])
    comprobar("parser encuentra 4 opciones", len(preguntas[0]["opciones"]) == 4)
    comprobar("parser normaliza la letra", preguntas[0]["opciones"][0]["letra"] == "A")
    comprobar("parser acepta 'Pregunta N'", preguntas[1]["numero"] == 2)


def test_validacion_correcta():
    problemas, clave, puntos, total = M.validar(_preguntas(), META)
    comprobar("fuente válida sin problemas", not problemas, str(problemas))
    comprobar("clave normalizada", clave == {1: "B", 2: "A"}, str(clave))
    comprobar("puntaje total respetado", total == 2.0, str(total))
    comprobar("puntos repartidos", puntos == {1: 1.0, 2: 1.0}, str(puntos))


def test_numeracion_con_hueco():
    texto = FUENTE.replace("## Pregunta 2", "## Pregunta 3")
    problemas, _, _, _ = M.validar(M._parsear_cuestionario(texto), META)
    comprobar("numeración con hueco falla", any("1..2" in p for p in problemas), str(problemas))


def test_letras_duplicadas():
    texto = FUENTE.replace("- B. No.", "- A. No.")
    problemas, _, _, _ = M.validar(M._parsear_cuestionario(texto), META)
    comprobar("letras duplicadas fallan", any("duplicadas" in p for p in problemas), str(problemas))


def test_opcion_vacia():
    texto = FUENTE.replace("- A. Sí.", "- A.   ")
    problemas, _, _, _ = M.validar(M._parsear_cuestionario(texto), META)
    comprobar("opción vacía falla", any("vacía" in p for p in problemas), str(problemas))


def test_clave_invalida():
    meta = dict(META, clave={1: "Z", 2: "A"})
    problemas, _, _, _ = M.validar(_preguntas(), meta)
    comprobar("clave con letra inexistente falla", any("no es una opción" in p for p in problemas), str(problemas))


def test_clave_incompleta():
    meta = dict(META, clave={1: "B"})
    problemas, _, _, _ = M.validar(_preguntas(), meta)
    comprobar("clave incompleta falla", any("falta la respuesta" in p for p in problemas), str(problemas))


def test_clave_ausente_no_es_error():
    problemas, clave, _, _ = M.validar(_preguntas(), {"curso": "X"})
    comprobar("sin clave no es un error de formato", not problemas, str(problemas))
    comprobar("sin clave devuelve mapa vacío", clave == {}, str(clave))


def test_puntos_no_suman():
    meta = dict(META, puntos={1: 0.5, 2: 0.5})
    problemas, _, _, _ = M.validar(_preguntas(), meta)
    comprobar("puntos que no suman el total fallan", any("suma de `puntos:`" in p for p in problemas), str(problemas))


def test_grupos_invalidos():
    problemas, _, _, _ = M.validar(_preguntas(), dict(META, grupos=0))
    comprobar("`grupos: 0` falla", any("entre 1 y 20" in p for p in problemas), str(problemas))
    problemas, _, _, _ = M.validar(_preguntas(), dict(META, grupos="muchos"))
    comprobar("`grupos` no entero falla", any("no es un entero" in p for p in problemas), str(problemas))
    problemas, _, _, _ = M.validar(_preguntas(), dict(META, grupos=4))
    comprobar("`grupos: 4` es válido", not problemas, str(problemas))


def test_inline_escapa_html():
    salida = M._inline("<script>alert(1)</script> y `code`")
    comprobar("escapa <script>", "&lt;script&gt;" in salida, salida)
    comprobar("no deja <script> literal", "<script>" not in salida, salida)
    comprobar("renderiza código inline", "<code>code</code>" in salida, salida)


def test_slug():
    comprobar("slug estable", M._slug("ROL_ROJO_Cuestionario") == "rol_rojo_cuestionario")
    comprobar("slug sin acentos", M._slug("Evaluación final") == "evaluacion_final")


def test_alumno_sin_clave_y_determinista():
    preguntas = _preguntas()
    _, _, puntos, _ = M.validar(preguntas, META)
    uno = M._render_alumno("Cuestionario de prueba", META, preguntas, puntos)
    dos = M._render_alumno("Cuestionario de prueba", META, preguntas, puntos)
    comprobar("alumno determinista", uno == dos)
    comprobar("alumno no expone CLAVE", "const CLAVE" not in uno)
    comprobar("alumno no usa red salvo MathJax", not _red_externa(uno), str(_red_externa(uno))[:200])
    comprobar("alumno incluye MathJax", CDN_MATHJAX in uno)
    comprobar("alumno incluye las preguntas", uno.count('class="pregunta"') == 2)
    comprobar("alumno fija la respuesta al primer clic", "i.disabled = true" in uno)
    comprobar("alumno avisa de la respuesta fijada", "Respuesta fijada" in uno)
    comprobar("alumno marca la pregunta bloqueada", "'bloqueada'" in uno)
    comprobar("alumno pide nombre", 'id="estudiante-nombre"' in uno)
    comprobar("alumno pide cédula", 'id="estudiante-cedula"' in uno)
    comprobar("alumno pide grupo", 'id="estudiante-grupo"' in uno)
    comprobar("alumno rotula los datos", "Datos del estudiante" in uno)
    comprobar(
        "alumno sin `grupos` usa campo numérico",
        'type="number" id="estudiante-grupo"' in uno,
    )
    con_grupos = M._render_alumno(
        "Cuestionario de prueba", {**META, "grupos": 3}, preguntas, puntos
    )
    comprobar(
        "alumno con `grupos: 3` ofrece exactamente 3 grupos",
        con_grupos.count("<option value=") == 4
        and 'value="3"' in con_grupos
        and 'value="4"' not in con_grupos,
    )
    comprobar(
        "alumno exige los datos antes de responder",
        "datosCompletos" in uno and 'id="aviso-datos"' in uno,
    )


def test_entrega_remota():
    preguntas = _preguntas()
    _, _, puntos, _ = M.validar(preguntas, META)
    url = "https://cuestionarios-worker.example.workers.dev"
    con = M._render_alumno(
        "Cuestionario de prueba", META, preguntas, puntos, url, "cuestionario_prueba"
    )
    comprobar("entrega: sección presente", 'id="entrega"' in con)
    comprobar("entrega: botón nace deshabilitado", 'id="enviar" disabled' in con)
    comprobar("entrega: URL en el script", url in con)
    comprobar("entrega: id del cuestionario", '"cuestionario_prueba"' in con)
    comprobar("entrega: envía por POST", "'POST'" in con)
    comprobar("entrega: estado accesible", 'role="status"' in con)
    comprobar("entrega: no filtra la clave", "const CLAVE" not in con)
    comprobar(
        "entrega: el botón espera a las 10 respuestas",
        "Object.keys(respuestas()).length === total" in con,
    )
    sin = M._render_alumno("Cuestionario de prueba", META, preguntas, puntos)
    comprobar("sin entrega no hay botón", 'id="enviar"' not in sin)
    comprobar("sin entrega no hay red salvo MathJax", not _red_externa(sin), str(_red_externa(sin))[:200])
    problemas, _, _, _ = M.validar(_preguntas(), dict(META, entrega_url="http://x"))
    comprobar(
        "`entrega_url` http falla",
        any("entrega_url" in p for p in problemas),
        str(problemas),
    )
    problemas, _, _, _ = M.validar(_preguntas(), dict(META, entrega_url="https://x y"))
    comprobar(
        "`entrega_url` con espacios falla",
        any("entrega_url" in p for p in problemas),
        str(problemas),
    )
    problemas, _, _, _ = M.validar(
        _preguntas(), dict(META, entrega_url="https://ok.example/entrega")
    )
    comprobar("`entrega_url` válida no falla", not problemas, str(problemas))


def test_docente_con_clave():
    preguntas = _preguntas()
    _, clave, puntos, total = M.validar(preguntas, META)
    uno = M._render_docente("Cuestionario de prueba", META, preguntas, puntos, total, clave, None)
    comprobar("docente incluye CLAVE", "const CLAVE" in uno)
    comprobar("docente incluye la respuesta", '"1":"B"' in uno, uno[:200])
    comprobar("docente no usa red salvo MathJax", not _red_externa(uno), str(_red_externa(uno))[:200])
    comprobar("docente avisa del modo", "Modo docente" in uno)
    comprobar(
        "docente no fija respuestas (debe poder corregir)",
        "i.disabled = true" not in uno and "Respuesta fijada" not in uno,
    )
    comprobar(
        "docente no pide datos del estudiante",
        'id="estudiante-nombre"' not in uno and "Datos del estudiante" not in uno,
    )


def test_justificaciones_parser():
    preguntas = M._parsear_cuestionario(FUENTE_JUST)
    comprobar(
        "parser captura la instrucción de justificación",
        "Cita el archivo y la línea" in preguntas[0].get("justificacion", ""),
    )
    comprobar(
        "la pregunta sin marcador no tiene justificación",
        not preguntas[1].get("justificacion"),
    )
    parseadas = M._parsear_respuestas(RESPUESTAS_JUST)
    comprobar(
        "respuestas capturan la justificación",
        "Cita el archivo y la línea" in parseadas[0].get("justificacion", ""),
    )
    just = parseadas[0].get("justificacion", "")
    comprobar(
        "la justificación no se come la explicación",
        "✓" not in just and "✗" not in just and "Explanation" not in just,
        just,
    )


def test_justificacion_items_validacion():
    preguntas = M._parsear_cuestionario(FUENTE_JUST)
    problemas, _, _, _ = M.validar(preguntas, META_JUST)
    comprobar("declaración coherente no falla", problemas == [], str(problemas))
    items, _ = M._items_justificacion(META_JUST, preguntas)
    comprobar("la lista declarada se devuelve", items == [1], str(items))

    casos = [
        ("pregunta sin instrucción", {**META_JUST, "justificacion_items": [2]}, "exigen justificación"),
        ("instrucción sin declarar", META, "sin estar en"),
        ("repetida", {**META_JUST, "justificacion_items": [1, 1]}, "repite"),
        ("inexistente", {**META_JUST, "justificacion_items": [9]}, "inexistentes"),
        ("no lista", {**META_JUST, "justificacion_items": "1"}, "lista de números"),
        ("no entero", {**META_JUST, "justificacion_items": ["1"]}, "no entero"),
        ("booleano", {**META_JUST, "justificacion_items": [True]}, "no entero"),
    ]
    for nombre, meta, esperado in casos:
        problemas, _, _, _ = M.validar(preguntas, meta)
        comprobar(
            f"justificacion_items {nombre} falla",
            any(esperado in p for p in problemas),
            str(problemas),
        )

    problemas, _, _, _ = M.validar(preguntas, {**META_JUST, "justificacion_items": []})
    comprobar(
        "declarar lista vacía con instrucción presente falla",
        any("sin estar en" in p for p in problemas),
        str(problemas),
    )


def test_justificacion_evidencia():
    preguntas = M._parsear_cuestionario(FUENTE_JUST)
    meta = {**META_JUST, "justificacion_evidencia": [1]}
    problemas, _, _, _ = M.validar(preguntas, meta)
    comprobar("ítem de evidencia válido no falla", problemas == [], str(problemas))
    items, errs = M._items_evidencia(meta, preguntas, [1])
    comprobar("la evidencia declarada se devuelve", items == [1] and errs == [], str((items, errs)))
    comprobar(
        "sin declarar no hay ítems exentos",
        M._items_evidencia(META_JUST, preguntas, [1])[0] == [],
    )

    casos = [
        ("no lista", "1", "lista de números"),
        ("no entero", ["1"], "no entero"),
        ("booleano", [True], "no entero"),
        ("repetida", [1, 1], "repite"),
        ("inexistente", [9], "inexistentes"),
        ("sin justificación", [2], "no exigen justificación"),
    ]
    for nombre, crudo, esperado in casos:
        problemas, _, _, _ = M.validar(preguntas, {**meta, "justificacion_evidencia": crudo})
        comprobar(
            f"justificacion_evidencia {nombre} falla",
            any(esperado in p for p in problemas),
            str(problemas),
        )

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        fuente = Path(tmp) / "c.md"
        respuestas = Path(tmp) / "c_respuestas.md"
        fuente.write_text(FUENTE_JUST.replace("justificacion_items: [1]", "justificacion_items: [1]\njustificacion_evidencia: [1]"), encoding="utf-8")
        respuestas.write_text(RESPUESTAS_JUST, encoding="utf-8")
        datos = M.cargar_clave(fuente, respuestas)
        comprobar(
            "cargar_clave devuelve justificacion_evidencia",
            datos["justificacion_evidencia"] == [1],
            str(datos["justificacion_evidencia"]),
        )

    titulo = "Cuestionario de prueba"
    puntos = M.validar(preguntas, meta)[2]
    sin = M._render_alumno(titulo, META_JUST, preguntas, puntos)
    con = M._render_alumno(titulo, meta, preguntas, puntos)
    comprobar(
        "la evidencia no se embebe en el HTML del alumno",
        sin == con and "justificacion_evidencia" not in con,
    )


def test_cruce_justificacion():
    preguntas = M._parsear_cuestionario(FUENTE_JUST)
    sin = M._parsear_respuestas(RESPUESTAS_JUST.replace("**Justificación:** Cita el archivo y la línea de tu repositorio que demuestran la respuesta, con la salida del comando que ejecutaste.\n\n", ""))
    problemas, _ = M._cruzar(preguntas, sin)
    comprobar(
        "el cruce detecta la justificación ausente en respuestas",
        any("justificación" in p.lower() for p in problemas),
        str(problemas),
    )
    distinta = M._parsear_respuestas(RESPUESTAS_JUST.replace("Cita el archivo", "Menciona otro archivo"))
    problemas, _ = M._cruzar(preguntas, distinta)
    comprobar(
        "el cruce detecta la justificación distinta",
        any("justificación" in p.lower() for p in problemas),
        str(problemas),
    )
    iguales = M._parsear_respuestas(RESPUESTAS_JUST)
    problemas, _ = M._cruzar(preguntas, iguales)
    comprobar("justificaciones iguales no fallan", problemas == [], str(problemas))


def test_alumno_con_justificacion():
    preguntas = M._parsear_cuestionario(FUENTE_JUST)
    _, _, puntos, _ = M.validar(preguntas, META_JUST)
    html = M._render_alumno(
        "Cuestionario de prueba",
        META_JUST,
        preguntas,
        puntos,
        "https://cuestionarios-worker.example.workers.dev",
        "cuestionario_prueba",
    )
    comprobar("alumno pide la justificación", 'id="j1"' in html)
    comprobar("solo la pregunta declarada", 'id="j2"' not in html)
    comprobar("la lista llega al cliente", "const JUSTIFICAR = [1]" in html)
    comprobar("el mínimo llega al cliente", f"const MIN_JUSTIFICACION = {M.MIN_JUSTIFICACION}" in html)
    comprobar("el textarea exige mínimo", 'minlength="40"' in html)
    comprobar("el textarea exige contenido", "required" in html)
    comprobar("el textarea tiene tope", 'maxlength="1500"' in html)
    comprobar("la instrucción se muestra", "Cita el archivo y la línea" in html)
    comprobar("alumno sigue sin clave", "const CLAVE" not in html)
    sin = M._render_alumno("Cuestionario de prueba", META, M._parsear_cuestionario(FUENTE), puntos)
    comprobar("sin declarar no hay textarea", 'class="justificacion"' not in sin)


def test_cargar_clave_justificacion():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        fuente = Path(tmp) / "c.md"
        respuestas = Path(tmp) / "c_respuestas.md"
        fuente.write_text(FUENTE_JUST, encoding="utf-8")
        respuestas.write_text(RESPUESTAS_JUST, encoding="utf-8")
        datos = M.cargar_clave(fuente, respuestas)
        comprobar("cargar_clave devuelve justificacion_items", datos["justificacion_items"] == [1], str(datos["justificacion_items"]))
        comprobar("cargar_clave sigue dando la clave", datos["clave"] == {1: "B", 2: "A"}, str(datos["clave"]))
        respuestas.write_text(RESPUESTAS_JUST.replace("**Justificación:** Cita el archivo y la línea de tu repositorio que demuestran la respuesta, con la salida del comando que ejecutaste.\n\n", ""), encoding="utf-8")
        try:
            M.cargar_clave(fuente, respuestas)
        except ValueError as exc:
            comprobar("cargar_clave falla si la clave no trae la justificación", "justificación" in str(exc).lower(), str(exc))
        else:
            comprobar("cargar_clave falla si la clave no trae la justificación", False, "no lanzó")


def test_barrera_de_rutas():
    try:
        M._validar_salida(RAIZ / "docs")
        comprobar("rechaza salida en docs/", False)
    except PermissionError:
        comprobar("rechaza salida en docs/", True)
    try:
        M._validar_salida(RAIZ / "cursos/CYBERSEGURIDAD/evaluaciones/web")
        comprobar("acepta la carpeta web ignorada", True)
    except PermissionError as exc:
        comprobar("acepta la carpeta web ignorada", False, str(exc))


def test_formato_punto():
    comprobar("1.0 se muestra como 1", M._formato_punto(1.0) == "1")
    comprobar("1.5 usa coma", M._formato_punto(1.5) == "1,5")


def test_parser_respuestas():
    respuestas = M._parsear_respuestas(RESPUESTAS)
    comprobar("respuestas: 2 preguntas", len(respuestas) == 2, str(len(respuestas)))
    comprobar("respuestas: letra de la 1", respuestas[0]["respuesta"] == "B")
    comprobar("respuestas: letra de la 2", respuestas[1]["respuesta"] == "A")
    comprobar(
        "respuestas: Answer/Hint/Explanation no entran en las opciones",
        all(
            "Answer" not in o["texto"]
            and "Hint" not in o["texto"]
            and "Explanation" not in o["texto"]
            for p in respuestas
            for o in p["opciones"]
        ),
        str(respuestas[0]["opciones"]),
    )
    comprobar("respuestas: conserva las 4 opciones", len(respuestas[0]["opciones"]) == 4)
    comprobar(
        "respuestas: la explicación no contamina el enunciado",
        "✗" not in respuestas[0]["enunciado"] and "Explanation" not in respuestas[0]["enunciado"],
        respuestas[0]["enunciado"],
    )


def test_cruce_correcto():
    problemas, clave = M._cruzar(_preguntas(), M._parsear_respuestas(RESPUESTAS))
    comprobar("cruce sin problemas", not problemas, str(problemas))
    comprobar("cruce deriva la clave", clave == {1: "B", 2: "A"}, str(clave))


def test_cruce_detecta_enunciado_distinto():
    alterado = RESPUESTAS.replace("Segunda pregunta.", "Otra pregunta distinta.")
    problemas, _ = M._cruzar(_preguntas(), M._parsear_respuestas(alterado))
    comprobar(
        "cruce detecta enunciado distinto",
        any("enunciado difiere" in p for p in problemas),
        str(problemas),
    )


def test_cruce_detecta_opciones_distintas():
    alterado = RESPUESTAS.replace("- A. Sí.", "- A. Claro que sí.")
    problemas, _ = M._cruzar(_preguntas(), M._parsear_respuestas(alterado))
    comprobar(
        "cruce detecta opciones distintas",
        any("opciones difieren" in p for p in problemas),
        str(problemas),
    )


def test_cruce_detecta_respuesta_ausente():
    alterado = RESPUESTAS.replace("**Answer:** A. Sí.\n", "")
    problemas, _ = M._cruzar(_preguntas(), M._parsear_respuestas(alterado))
    comprobar(
        "cruce exige **Answer:** en cada pregunta",
        any("no trae" in p for p in problemas),
        str(problemas),
    )


def test_cruce_detecta_letra_inexistente():
    alterado = RESPUESTAS.replace("**Answer:** A. Sí.", "**Answer:** Z. Nada.")
    problemas, _ = M._cruzar(_preguntas(), M._parsear_respuestas(alterado))
    comprobar(
        "cruce exige que la letra sea una opción",
        any("no es una de sus opciones" in p for p in problemas),
        str(problemas),
    )


def test_cruce_detecta_numeracion_distinta():
    alterado = RESPUESTAS.replace("## pregunta 2", "## pregunta 3")
    problemas, _ = M._cruzar(_preguntas(), M._parsear_respuestas(alterado))
    comprobar(
        "cruce exige la misma numeración",
        any("no coinciden" in p for p in problemas),
        str(problemas),
    )


def test_docente_desde_respuestas():
    preguntas = _preguntas()
    problemas_cruce, clave_resp = M._cruzar(preguntas, M._parsear_respuestas(RESPUESTAS))
    meta = {k: v for k, v in META.items() if k != "clave"}
    meta["clave"] = clave_resp
    problemas, clave, puntos, total = M.validar(preguntas, meta)
    comprobar(
        "la clave derivada valida la fuente",
        not problemas_cruce and not problemas,
        str(problemas_cruce + problemas),
    )
    html = M._render_docente(
        "Cuestionario de prueba", meta, preguntas, puntos, total, clave, None
    )
    comprobar("docente derivado incluye la clave", '"1":"B"' in html and '"2":"A"' in html)


def test_main_deriva_clave_de_respuestas():
    with tempfile.TemporaryDirectory() as tmp:
        fuente = Path(tmp) / "cuestionario.md"
        respuestas = Path(tmp) / "cuestionario_respuestas.md"
        fuente.write_text(FUENTE, encoding="utf-8")
        respuestas.write_text(RESPUESTAS, encoding="utf-8")
        codigo, datos = _ejecutar_main(
            ["--fuente", str(fuente), "--respuestas", str(respuestas), "--check"]
        )
        comprobar("--check con respuestas sale 0", codigo == 0, str(datos))
        comprobar("--check con respuestas ve la clave", datos.get("tiene_clave") is True, str(datos))
        comprobar(
            "--check registra el archivo de respuestas",
            datos.get("respuestas") == str(respuestas.resolve()),
            str(datos),
        )


def test_main_rechaza_respuestas_como_fuente():
    with tempfile.TemporaryDirectory() as tmp:
        fuente = Path(tmp) / "cuestionario_respuestas.md"
        fuente.write_text(RESPUESTAS, encoding="utf-8")
        codigo, datos = _ejecutar_main(["--fuente", str(fuente), "--check"])
        comprobar("archivo de respuestas como fuente falla", codigo == 3, str(datos))
        comprobar(
            "el mensaje remite a --respuestas",
            "--respuestas" in datos.get("message", ""),
            str(datos),
        )


def test_main_clave_y_respuestas_en_desacuerdo():
    with tempfile.TemporaryDirectory() as tmp:
        fuente = Path(tmp) / "cuestionario.md"
        respuestas = Path(tmp) / "cuestionario_respuestas.md"
        fuente.write_text(
            "---\ncurso: X\ntipo: cuestionario\nclave: {1: A, 2: A}\n---\n\n" + FUENTE,
            encoding="utf-8",
        )
        respuestas.write_text(RESPUESTAS, encoding="utf-8")
        codigo, datos = _ejecutar_main(
            ["--fuente", str(fuente), "--respuestas", str(respuestas), "--check"]
        )
        comprobar("dos fuentes de verdad en desacuerdo fallan", codigo == 3, str(datos))
        comprobar(
            "el mensaje nombra las dos fuentes",
            "dos fuentes de verdad" in datos.get("message", ""),
            str(datos),
        )


def test_orquestador_ignora_archivos_de_respuestas():
    spec = importlib.util.spec_from_file_location(
        "flujo_web_bajo_test", RAIZ / "flujo_evaluacion_web.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["flujo_web_bajo_test"] = mod
    spec.loader.exec_module(mod)
    comprobar("detecta _respuestas.md", mod._es_archivo_de_respuestas(Path("X_respuestas.md")))
    comprobar("no confunde un cuestionario", not mod._es_archivo_de_respuestas(Path("X.md")))
    fuentes = mod._resolver_fuentes(["cursos/*/evaluaciones/web/fuentes/*.md"])
    nombres = [f.name for f in fuentes]
    comprobar(
        "el glob por defecto no trae el archivo de respuestas",
        not any(n.lower().endswith("_respuestas.md") for n in nombres),
        str(nombres),
    )


def test_aviso_material():
    """El recuadro del examen remoto: solo con `entrega_url`, solo en alumno."""
    preguntas = M._parsear_cuestionario(FUENTE_JUST)
    _, _, puntos, _ = M.validar(preguntas, META_JUST)
    remoto = M._render_alumno(
        "Cuestionario de prueba",
        META_JUST,
        preguntas,
        puntos,
        "https://cuestionarios-worker.example.workers.dev",
        "cuestionario_prueba",
    )
    comprobar("remoto trae el aviso", 'id="aviso-material"' in remoto)
    for frase in (
        "otra pestaña o ventana",
        "incógnito",
        "guarda un borrador",
        "no invalida",
        "se fija al primer clic",
    ):
        comprobar(f"aviso dice «{frase}»", frase in remoto)
    comprobar(
        "el aviso anuncia la caducidad",
        f"{M.BORRADOR_CADUCIDAD_HORAS} horas" in remoto,
    )
    comprobar("hay línea de estado del borrador", 'id="borrador-estado"' in remoto)
    laboratorio = M._render_alumno("Cuestionario de prueba", META, preguntas, puntos)
    comprobar("laboratorio sin aviso", 'id="aviso-material"' not in laboratorio)
    comprobar("laboratorio sin borrador", "localStorage" not in laboratorio)
    docente = M._render_docente(
        "Cuestionario de prueba", META_JUST, preguntas, puntos, 2.0, {1: "B", 2: "A"}, None
    )
    comprobar("docente sin aviso", 'id="aviso-material"' not in docente)
    comprobar(
        "aviso sin marcas prohibidas",
        "**Answer:**" not in remoto and "Modo docente" not in remoto,
    )
    comprobar("aviso no filtra la clave", "const CLAVE" not in remoto)


def test_borrador_autoguardado():
    """El JS del borrador: clave versionada, restauración, envío y degradación."""
    js = M._js_alumno(
        2,
        "https://cuestionarios-worker.example.workers.dev",
        "cuestionario_prueba",
        [1],
        huella="abc123def456",
    )
    comprobar("huella inyectada", 'const HUELLA = "abc123def456";' in js)
    comprobar(
        "versión inyectada", f"const BORRADOR_VERSION = {M.BORRADOR_VERSION};" in js
    )
    comprobar(
        "caducidad inyectada",
        f"const BORRADOR_HORAS = {M.BORRADOR_CADUCIDAD_HORAS};" in js,
    )
    comprobar("la clave se compone con la versión", "'cuestionario.v' + BORRADOR_VERSION" in js)
    comprobar("la clave lleva el cuestionario", "+ CUESTIONARIO +" in js)
    comprobar("la clave lleva la huella", "+ HUELLA;" in js)
    for nombre in (
        "guardar",
        "leerBorrador",
        "restaurar",
        "marcarEntregado",
        "guardarEntregado",
        "hayBorrador",
        "decirBorrador",
        "sinAlmacen",
    ):
        comprobar(f"define {nombre}()", f"function {nombre}(" in js)
    comprobar("escribe el borrador", "localStorage.setItem(BORRADOR_KEY" in js)
    comprobar("lee el borrador", "localStorage.getItem(BORRADOR_KEY)" in js)
    comprobar("avisa antes de salir", "beforeunload" in js)
    comprobar(
        "restaura al cargar", js.rstrip().endswith("restaurar();\nactualizar();"), js[-60:]
    )
    comprobar("la entrega sustituye el borrador", "guardarEntregado();" in js)
    comprobar("compara la huella", "datos.huella !== HUELLA" in js)
    comprobar("compara la caducidad", "BORRADOR_CADUCIDAD_MS" in js)
    comprobar("degrada si no hay almacenamiento", "sinAlmacen()" in js)
    comprobar("el borrador guarda las justificaciones", "justificaciones: justificaciones()," in js)
    comprobar("el borrador guarda el inicio", "inicio: inicio," in js)
    comprobar("el borrador guarda las respuestas", "respuestas: respuestas()," in js)
    entrega = js[js.index("function guardarEntregado()") : js.index("function restaurar()")]
    comprobar("el registro de entrega marca enviado", "enviado: true," in entrega)
    comprobar("el registro de entrega no lleva respuestas", "respuestas:" not in entrega)
    comprobar(
        "el registro de entrega no lleva justificaciones",
        "justificaciones:" not in entrega,
    )
    sin = M._js_alumno(2)
    comprobar("sin entrega_url no hay borrador", "localStorage" not in sin)
    comprobar("sin entrega_url guardar no hace nada", "function guardar(){}" in sin)


def test_huella_determinista():
    """La huella identifica el cuestionario sin revelar la clave."""
    preguntas = M._parsear_cuestionario(FUENTE_JUST)
    una = M._huella_cuestionario(preguntas)
    comprobar(
        "misma fuente -> misma huella",
        una == M._huella_cuestionario(M._parsear_cuestionario(FUENTE_JUST)),
    )
    comprobar(
        "huella de 12 hexadecimales",
        len(una) == 12 and all(c in "0123456789abcdef" for c in una),
        una,
    )
    cambiado = [dict(p) for p in preguntas]
    cambiado[0] = {**cambiado[0], "enunciado": cambiado[0]["enunciado"] + " (v2)"}
    comprobar(
        "enunciado distinto -> huella distinta", M._huella_cuestionario(cambiado) != una
    )
    comprobar(
        "otro orden -> otra huella",
        M._huella_cuestionario([dict(preguntas[1]), dict(preguntas[0])]) != una,
    )
    # El caso real de huella distinta es un re-barajado: cambian las opciones, no
    # el número ni el enunciado. La instrucción de justificación NO entra en la
    # huella a propósito (retocar su redacción no invalida lo ya respondido).
    barajada = [dict(p) for p in preguntas]
    barajada[0] = {**barajada[0], "opciones": list(reversed(barajada[0]["opciones"]))}
    comprobar(
        "opciones barajadas -> otra huella", M._huella_cuestionario(barajada) != una
    )
    import copy

    ajenos = copy.deepcopy(preguntas)
    for pregunta in ajenos:
        pregunta["respuesta"] = "B"
        pregunta["justificacion"] = "texto de justificación irrelevante" * 3
    comprobar(
        "la respuesta y la justificación no cambian la huella",
        M._huella_cuestionario(ajenos) == una,
    )
    _, _, puntos, _ = M.validar(preguntas, META_JUST)
    remoto = M._render_alumno(
        "Cuestionario de prueba",
        META_JUST,
        preguntas,
        puntos,
        "https://cuestionarios-worker.example.workers.dev",
        "cuestionario_prueba",
    )
    comprobar("la huella llega al HTML", f'const HUELLA = "{una}";' in remoto)
    laboratorio = M._render_alumno("Cuestionario de prueba", META, preguntas, puntos)
    comprobar("sin entrega no hay huella", "const HUELLA" not in laboratorio)


def main() -> int:
    print("Pruebas del conversor Markdown -> HTML")
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
