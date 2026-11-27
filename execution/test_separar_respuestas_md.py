#!/usr/bin/env python3
"""Pruebas del separador de respuestas en español (sin red, sin LLM)."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import md_a_html as M  # noqa: E402
import separar_respuestas_md as S  # noqa: E402

FALLOS: list[str] = []
TOTAL = 0


def comprobar(nombre: str, condicion: bool, detalle: str = "") -> None:
    global TOTAL
    TOTAL += 1
    if condicion:
        print(f"  ok   {nombre}")
    else:
        FALLOS.append(nombre)
        print(f"  FALLA {nombre} {detalle}".rstrip())


CS = """# Demo

> 2 preguntas

---

## Pregunta 1

¿Cuál es la capital de Venezuela?

- A. Caracas
- B. Maracaibo
- C. Valencia
- D. Barquisimeto

**Respuesta:** A. Caracas está en el centro norte del país.

**Pista:** Piensa en la ciudad donde se firmó el acta.

**Explicación:**

- A ✓ Es la capital y sede de los poderes públicos.
- B ✗ Es la segunda ciudad más grande, no la capital.
- C ✗ Fue capital en el siglo XIX, no hoy.
- D ✗ Es la capital del estado Lara.

---

## Pregunta 2

¿Qué protocolo cifra el transporte web?

- A. FTP
- B. HTTPS
- C. SMTP
- D. Telnet

**Respuesta:** B. HTTPS usa TLS por debajo.

**Pista:** Busca el propio en la barra del navegador.

**Explicación:**

- A ✗ Transfiere archivos sin cifrado por defecto.
- B ✓ HTTP sobre TLS.
- C ✗ Es para correo saliente.
- D ✗ Transmite en texto plano.

---
"""


def test_es_separable() -> None:
    print("\n[es_separable]")
    comprobar("detecta marcas en español", S.es_separable(CS))
    comprobar("rechaza marcas en inglés", not S.es_separable(CS.replace("Respuesta", "Answer")))
    comprobar(
        "rechaza una fuente ya limpia",
        not S.es_separable(CS.replace("**Respuesta:** A.", "A.").replace("**Pista:**", "Pista:")),
    )


def test_parseo() -> None:
    print("\n[parseo]")
    cabecera, preguntas = S.parsear(CS)
    comprobar("cabecera conservada", cabecera == ["# Demo", "> 2 preguntas"], str(cabecera))
    comprobar("dos preguntas", len(preguntas) == 2, str(len(preguntas)))
    comprobar("numeración 1,2", [p["numero"] for p in preguntas] == [1, 2])
    comprobar("cuatro opciones", [len(p["opciones"]) for p in preguntas] == [4, 4])
    comprobar(
        "respuestas leídas",
        [p["respuesta"] for p in preguntas] == ["A", "B"],
        str([p["respuesta"] for p in preguntas]),
    )
    comprobar("pistas leídas", all(p["pista"] for p in preguntas))
    comprobar("explicaciones leídas", [len(p["explicacion"]) for p in preguntas] == [4, 4])
    comprobar(
        "la explicación no se mezcló con las opciones",
        all(len(p["opciones"]) == 4 for p in preguntas),
    )


CS_TABLA = """# Demo tabla

## Pregunta 1

Considere:

```
+----+----+
| A  | B  |
+----+----+
```

¿Cuál fila?

- A. La primera.
- B. La segunda.

**Respuesta:** A. La primera.

**Pista:** Mire la tabla.

**Explicación:**

- A ✓ Correcta.
- B ✗ Incorrecta.
"""


def test_tabla_en_bloque() -> None:
    print("\n[tabla en bloque]")
    cabecera, preguntas = S.parsear(CS_TABLA)
    filas = "+----+----+\n| A  | B  |\n+----+----+"
    comprobar("el separador conserva las filas", filas in preguntas[0]["enunciado"])
    limpia = S.armar_fuente(cabecera, preguntas)
    solucionario = S.armar_respuestas(cabecera, preguntas)
    comprobar("la fuente conserva el bloque", filas in limpia)
    comprobar("el solucionario conserva el bloque", filas in solucionario)
    problemas, _ = M._cruzar(
        M._parsear_cuestionario(limpia), M._parsear_respuestas(solucionario)
    )
    comprobar("fuente y solucionario siguen cruzando", not problemas, str(problemas))


def test_salidas() -> None:
    print("\n[salidas]")
    cabecera, preguntas = S.parsear(CS)
    limpia = S.armar_fuente(cabecera, preguntas)
    respuestas = S.armar_respuestas(cabecera, preguntas)
    for marca in ["**Respuesta:**", "**Pista:**", "**Explicación:**", "✓", "✗"]:
        comprobar(f"la fuente limpia no contiene {marca}", marca not in limpia)
    comprobar("la fuente conserva el título", limpia.startswith("# Demo"))
    comprobar("la fuente conserva el enunciado", "¿Cuál es la capital de Venezuela?" in limpia)
    for marca in ["**Answer:**", "**Hint:**", "**Explanation:**", "✓", "✗"]:
        comprobar(f"el solucionario contiene {marca}", marca in respuestas)
    comprobar(
        "la respuesta mantiene el texto original",
        "Caracas está en el centro norte del país." in respuestas,
    )
    comprobar("mismo input, misma fuente", limpia == S.armar_fuente(cabecera, preguntas))
    comprobar("mismo input, mismo solucionario", respuestas == S.armar_respuestas(cabecera, preguntas))


def test_cruce_con_el_conversor() -> None:
    print("\n[cruce con el conversor]")
    cabecera, preguntas = S.parsear(CS)
    with tempfile.TemporaryDirectory(dir=RAIZ / ".tmp") as temporal:
        tmp = Path(temporal)
        f = tmp / "fuente.md"
        r = tmp / "respuestas.md"
        f.write_text(S.armar_fuente(cabecera, preguntas), encoding="utf-8")
        r.write_text(S.armar_respuestas(cabecera, preguntas), encoding="utf-8")
        datos = M.cargar_clave(f, r)
        comprobar("el conversor acepta la pareja", datos["n_preguntas"] == 2)
        comprobar("recupera las dos claves", datos["clave"] == {1: "A", 2: "B"}, str(datos["clave"]))
        comprobar("sin clave en el front matter de la fuente", "clave:" not in f.read_text())


def test_validacion() -> None:
    print("\n[validación]")
    cabecera, preguntas = S.parsear(CS)
    comprobar("el caso bueno no tiene problemas", S.validar(preguntas) == [], str(S.validar(preguntas)))
    mal = [dict(p) for p in preguntas]
    mal[0]["respuesta"] = "F"
    comprobar(
        "rechaza respuesta fuera de las opciones",
        any("no está entre las opciones" in x for x in S.validar(mal)),
    )
    mal = [dict(p) for p in preguntas]
    mal[1]["numero"] = 7
    comprobar(
        "rechaza numeración rota",
        any("numeración no consecutiva" in x for x in S.validar(mal)),
    )
    mal = [dict(p) for p in preguntas]
    mal[0]["explicacion"] = []
    comprobar(
        "rechaza explicación ausente",
        any("falta **Explicación:**" in x for x in S.validar(mal)),
    )
    comprobar("rechaza entrada vacía", bool(S.validar([])))


def test_extremo_a_extremo_con_archivo_separable() -> None:
    """Funciona antes y después de separar el archivo real del curso."""
    print("\n[extremo a extremo: archivo con respuestas en español]")
    real = RAIZ / "cursos/CYBERSEGURIDAD/evaluaciones/web/SEMANA_02/fuentes/ROL_ROJO_CUESTIONARIO_S2.md"
    respaldo = real.with_name("ROL_ROJO_CUESTIONARIO_S2_original_con_respuestas.md")
    if respaldo.is_file():
        origen, esperadas = respaldo, 10
    elif real.is_file() and S.es_separable(real.read_text(encoding="utf-8")):
        origen, esperadas = real, 10
    else:
        origen, esperadas = None, 2

    with tempfile.TemporaryDirectory(dir=RAIZ / ".tmp") as temporal:
        copia = Path(temporal) / "ROL_ROJO_CUESTIONARIO_S2.md"
        if origen is not None:
            shutil.copy2(origen, copia)
        else:
            copia.write_text(CS, encoding="utf-8")
        antes = copia.read_bytes()
        informe = S.separar(copia)
        comprobar("código 0", informe["code"] == 0, str(informe))
        comprobar(f"{esperadas} preguntas", informe["preguntas"] == esperadas, str(informe["preguntas"]))
        backup = copia.with_name(f"{copia.stem}_original_con_respuestas.md")
        comprobar("el respaldo es byte-idéntico al original", backup.read_bytes() == antes)
        limpia = copia.read_text(encoding="utf-8")
        comprobar("la fuente separada no filtra la clave", "**Respuesta:**" not in limpia)
        comprobar("la fuente separada no filtra la explicación", "**Explicación:**" not in limpia)
        solucionario = copia.with_name(f"{copia.stem}_respuestas.md").read_text(encoding="utf-8")
        comprobar("el solucionario usa Answer", solucionario.count("**Answer:**") == esperadas)
        datos = M.cargar_clave(copia, copia.with_name(f"{copia.stem}_respuestas.md"))
        comprobar("el conversor valida la pareja", datos["n_preguntas"] == esperadas)
        comprobar("todas las claves se recuperan", len(datos["clave"]) == esperadas)

        try:
            S.separar(copia)
            codigo = 0
        except S.SeparacionError as exc:
            codigo = exc.codigo
        comprobar("una segunda pasada se rechaza (código 4)", codigo == 4, str(codigo))


def main() -> int:
    print("Pruebas del separador de respuestas en español")
    print("=" * 54)
    test_es_separable()
    test_parseo()
    test_tabla_en_bloque()
    test_salidas()
    test_cruce_con_el_conversor()
    test_validacion()
    test_extremo_a_extremo_con_archivo_separable()
    print(f"\n{TOTAL - len(FALLOS)}/{TOTAL} aserciones OK")
    for fallo in FALLOS:
        print(f"  FALLA: {fallo}")
    return 1 if FALLOS else 0


if __name__ == "__main__":
    sys.exit(main())
