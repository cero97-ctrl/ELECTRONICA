#!/usr/bin/env python3
"""Pruebas de `execution/descargar_resultados.py` (capa 3 del acta).

Fijan el contrato sin tocar la red: la normalización de cédula y nombre es la
misma que la del Worker, la nota se recalcula con la clave vigente (una nota
archivada que no cuadra se marca `revisar`, no se cree), el orden del acta es
determinista, la nómina produce faltantes/sobrantes, y el LaTeX no usa
entornos inexistentes.

Ejecutar: python3 execution/test_descargar_resultados.py
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
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
        "descargar_bajo_test", RAIZ / "execution/descargar_resultados.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["descargar_bajo_test"] = mod
    spec.loader.exec_module(mod)
    return mod


D = _cargar()

CLAVE = {i: letra for i, letra in enumerate("ABBBB AABBB".replace(" ", ""), start=1)}
TOTAL = len(CLAVE)
GRUPOS = 4


def registro_base(**cambios) -> dict:
    datos = {
        "cuestionario": "rol_rojo_cuestionario",
        "nombre": "Ana Pérez",
        "cedula": "V-12345678",
        "grupo": 1,
        "respuestas": {str(n): CLAVE[n] for n in CLAVE},
        "aciertos": TOTAL,
        "total": TOTAL,
        "nota": 10,
        "enviado_en": "2026-11-11T15:35:27.535Z",
    }
    datos.update(cambios)
    return datos


RUTA_OK = "resultados/rol_rojo_cuestionario/grupo_01/V-12345678.json"


def test_cedula() -> None:
    print("\n-- Cédula: la misma regla que el Worker")
    casos = [
        ("V-12345678", "V-12345678"),
        ("12345678", "V-12345678"),
        ("v 12.345.678", "V-12345678"),
        ("E-1234567", "E-1234567"),
        ("J1234567", "J-1234567"),
        ("abc", None),
        ("1234", None),
        ("V-1234567890", None),
        (12345678, None),
        (None, None),
    ]
    for entrada, esperada in casos:
        obtenida = D.normalizar_cedula(entrada)
        comprobar(
            f"normalizar_cedula({entrada!r}) == {esperada!r}",
            obtenida == esperada,
            f"obtenida {obtenida!r}",
        )


def test_nombre() -> None:
    print("\n-- Nombre")
    comprobar(
        "colapsa espacios y recorta",
        D.normalizar_nombre("  ana   Pérez ") == "ana Pérez",
    )
    comprobar("mínimo 3 caracteres", D.normalizar_nombre("Jo") is None)
    comprobar("sin dígitos", D.normalizar_nombre("Ana1") is None)
    comprobar(
        "apóstrofo y guión permitidos",
        D.normalizar_nombre("O'Brien-Smith") == "O'Brien-Smith",
    )
    comprobar("no string -> None", D.normalizar_nombre(7) is None)
    comprobar("máximo 80 caracteres", D.normalizar_nombre("A" * 81) is None)


def test_grupo() -> None:
    print("\n-- Grupo")
    comprobar("string numérico", D.normalizar_grupo("3", GRUPOS) == 3)
    comprobar("int", D.normalizar_grupo(3, GRUPOS) == 3)
    comprobar("fuera de rango", D.normalizar_grupo(5, GRUPOS) is None)
    comprobar("cero", D.normalizar_grupo(0, GRUPOS) is None)
    comprobar("bool no es número", D.normalizar_grupo(True, GRUPOS) is None)
    comprobar("no numérico", D.normalizar_grupo("x", GRUPOS) is None)


def test_respuestas() -> None:
    print("\n-- Respuestas")
    buenas = {str(n): "A" for n in range(1, TOTAL + 1)}
    comprobar("completas", D.normalizar_respuestas(buenas, TOTAL) == buenas)
    incompletas = dict(buenas)
    incompletas.pop("3")
    comprobar("incompletas -> None", D.normalizar_respuestas(incompletas, TOTAL) is None)
    comprobar(
        "letra inválida -> None",
        D.normalizar_respuestas({**buenas, "3": "F"}, TOTAL) is None,
    )
    comprobar(
        "clave sobrante -> None",
        D.normalizar_respuestas({**buenas, str(TOTAL + 1): "A"}, TOTAL) is None,
    )
    comprobar("no dict -> None", D.normalizar_respuestas([1, 2], TOTAL) is None)


def test_recalcular() -> None:
    print("\n-- Recálculo de la nota")
    aciertos, total, nota = D.recalcular({str(n): CLAVE[n] for n in CLAVE}, CLAVE)
    comprobar("todo correcto", (aciertos, total, nota) == (TOTAL, TOTAL, 10.0), str((aciertos, total, nota)))
    falladas = {str(n): ("A" if CLAVE[n] != "A" else "B") for n in (1, 2)}
    parciales = {**{str(n): CLAVE[n] for n in CLAVE}, **falladas}
    a2, _, n2 = D.recalcular(parciales, CLAVE)
    comprobar("dos fallos", (a2, n2) == (TOTAL - 2, 8.0), str((a2, n2)))
    comprobar(
        "redondeo a 2 decimales",
        D.recalcular({"1": "A"}, {1: "A", 2: "B", 3: "C"})[2] == 3.33,
    )
    comprobar("clave vacía", D.recalcular({}, {}) == (0, 0, 0.0))


def test_validar_registro() -> None:
    print("\n-- Validación del archivo archivado")
    problemas, reg = D.validar_registro(
        registro_base(),
        cuestionario="rol_rojo_cuestionario",
        total=TOTAL,
        grupos=GRUPOS,
        clave=CLAVE,
        archivo=RUTA_OK,
    )
    comprobar("registro sano", problemas == [] and reg is not None, str(problemas))
    comprobar("estado ok", reg and reg["estado"] == "ok")
    comprobar("nota recalculada", reg and reg["nota_recalculada"] == 10.0)

    problemas, reg = D.validar_registro(
        registro_base(nota=9),
        cuestionario="rol_rojo_cuestionario",
        total=TOTAL,
        grupos=GRUPOS,
        clave=CLAVE,
        archivo=RUTA_OK,
    )
    comprobar(
        "nota archivada que no cuadra se marca",
        reg is not None and reg["estado"] == "revisar",
        str(problemas),
    )
    comprobar(
        "el aviso menciona las dos notas",
        any("9" in p and "10" in p for p in problemas),
        str(problemas),
    )

    problemas, reg = D.validar_registro(
        registro_base(cedula="V-99999999"),
        cuestionario="rol_rojo_cuestionario",
        total=TOTAL,
        grupos=GRUPOS,
        clave=CLAVE,
        archivo=RUTA_OK,
    )
    comprobar(
        "cédula del contenido != cédula del archivo",
        reg is None and any("cédula del archivo" in p for p in problemas),
        str(problemas),
    )

    problemas, reg = D.validar_registro(
        registro_base(grupo=2),
        cuestionario="rol_rojo_cuestionario",
        total=TOTAL,
        grupos=GRUPOS,
        clave=CLAVE,
        archivo=RUTA_OK,
    )
    comprobar(
        "grupo del contenido != grupo del archivo",
        reg is None and any("grupo del archivo" in p for p in problemas),
        str(problemas),
    )

    problemas, reg = D.validar_registro(
        registro_base(cuestionario="otro"),
        cuestionario="rol_rojo_cuestionario",
        total=TOTAL,
        grupos=GRUPOS,
        clave=CLAVE,
        archivo=RUTA_OK,
    )
    comprobar("cuestionario ajeno se rechaza", reg is None, str(problemas))

    problemas, reg = D.validar_registro(
        registro_base(respuestas={"1": "A"}),
        cuestionario="rol_rojo_cuestionario",
        total=TOTAL,
        grupos=GRUPOS,
        clave=CLAVE,
        archivo=RUTA_OK,
    )
    comprobar("respuestas incompletas se rechazan", reg is None, str(problemas))

    problemas, reg = D.validar_registro(
        "no soy un objeto",
        cuestionario="rol_rojo_cuestionario",
        total=TOTAL,
        grupos=GRUPOS,
        clave=CLAVE,
        archivo=RUTA_OK,
    )
    comprobar("JSON que no es objeto", reg is None and problemas, str(problemas))

    problemas, reg = D.validar_registro(
        registro_base(),
        cuestionario="rol_rojo_cuestionario",
        total=TOTAL,
        grupos=GRUPOS,
        clave=CLAVE,
        archivo="resultados/otro.json",
    )
    comprobar(
        "ruta que no sigue el patrón del Worker",
        reg is None and any("patrón" in p for p in problemas),
        str(problemas),
    )


def test_orden_y_csv() -> None:
    print("\n-- Orden determinista y CSV")
    registros = [
        {"grupo": 2, "cedula": "V-2", "nombre": "B", "aciertos": 5, "total": 10,
         "nota": 5.0, "nota_recalculada": 5.0, "enviado_en": "z", "archivo": "f2",
         "avisos": [], "estado": "ok"},
        {"grupo": 1, "cedula": "V-9", "nombre": "A", "aciertos": 3, "total": 10,
         "nota": 3.0, "nota_recalculada": 3.0, "enviado_en": "a", "archivo": "f3",
         "avisos": ["algo"], "estado": "revisar"},
        {"grupo": 1, "cedula": "V-1", "nombre": "C", "aciertos": 8, "total": 10,
         "nota": 8.0, "nota_recalculada": 8.0, "enviado_en": "b", "archivo": "f1",
         "avisos": [], "estado": "ok"},
    ]
    orden = D.ordenar(registros)
    comprobar(
        "grupo, luego nota descendente, luego cédula",
        [(r["grupo"], r["cedula"]) for r in orden] == [(1, "V-1"), (1, "V-9"), (2, "V-2")],
        str([(r["grupo"], r["cedula"]) for r in orden]),
    )
    comprobar("misma entrada -> misma salida", D.ordenar(registros) == orden)

    csv_texto = D.csv_texto(orden)
    lineas = csv_texto.splitlines()
    comprobar("cabecera exacta", lineas[0] == ",".join(D.CABECERA_CSV), lineas[0])
    comprobar("una fila por registro", len(lineas) == 4, str(len(lineas)))
    comprobar("nota con 2 decimales", ",8.00,8.00," in lineas[1], lineas[1])
    comprobar("avisos unidos con punto y coma", "algo" in lineas[2], lineas[2])
    comprobar("sin salto de línea final doble", csv_texto.endswith("\n") and not csv_texto.endswith("\n\n"))


def test_cobertura() -> None:
    print("\n-- Nómina vs entregas")
    nomina = [
        {"cedula": "V-1", "nombre": "A", "grupo": 1},
        {"cedula": "V-2", "nombre": "B", "grupo": 1},
        {"cedula": "V-3", "nombre": "C", "grupo": 2},
    ]
    recibidos = [
        {"cedula": "V-1", "nombre": "A", "grupo": 2},
        {"cedula": "V-9", "nombre": "X", "grupo": 1},
    ]
    diff = D.comparar(nomina, recibidos)
    comprobar("esperados", diff["esperados"] == 3)
    comprobar("recibidos", diff["recibidos"] == 2)
    comprobar("faltantes", [f["cedula"] for f in diff["faltantes"]] == ["V-2", "V-3"])
    comprobar("sobrantes", [s["cedula"] for s in diff["sobrantes"]] == ["V-9"])
    comprobar("grupo distinto al declarado", diff["grupo_distinto"] == ["V-1"])

    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "lista.csv"
        ruta.write_text(
            "nombre,cedula,grupo\nAna Pérez,v 12.345.678,1\n,sin-cedula,2\n",
            encoding="utf-8",
        )
        filas, problemas = D.leer_lista(ruta)
        comprobar("CSV: cédula normalizada", filas == [{"cedula": "V-12345678", "nombre": "Ana Pérez", "grupo": 1}], str(filas))
        comprobar("CSV: fila inválida avisada", len(problemas) == 1, str(problemas))

        ruta_yaml = Path(tmp) / "lista.yaml"
        ruta_yaml.write_text(
            "estudiantes:\n  - nombre: Luis Díaz\n    cedula: E-1234567\n    grupo: 3\n",
            encoding="utf-8",
        )
        filas_yaml, problemas_yaml = D.leer_lista(ruta_yaml)
        comprobar(
            "YAML: lee la lista",
            filas_yaml == [{"cedula": "E-1234567", "nombre": "Luis Díaz", "grupo": 3}],
            str(filas_yaml),
        )
        comprobar("YAML: sin problemas", problemas_yaml == [])


def test_resumen() -> None:
    print("\n-- Resumen")
    registros = [
        {"grupo": 1, "nota_recalculada": 10.0, "enviado_en": "2026-11-11T10:00:00Z", "estado": "ok"},
        {"grupo": 1, "nota_recalculada": 6.0, "enviado_en": "2026-11-11T11:00:00Z", "estado": "revisar"},
        {"grupo": 2, "nota_recalculada": 8.0, "enviado_en": "2026-11-11T09:00:00Z", "estado": "ok"},
    ]
    r = D.resumen(registros)
    comprobar("entregas", r["entregas"] == 3)
    comprobar("promedio", r["promedio"] == 8.0, str(r["promedio"]))
    comprobar("mejor/peor", (r["mejor"], r["peor"]) == (10.0, 6.0))
    comprobar("por grupo", r["por_grupo"] == {1: 2, 2: 1})
    comprobar("a revisar", r["a_revisar"] == 1)
    comprobar("último envío", r["ultimo_envio"] == "2026-11-11T11:00:00Z")
    vacio = D.resumen([])
    comprobar("sin entregas", vacio["entregas"] == 0 and vacio["promedio"] is None)


def test_tex_y_latex() -> None:
    print("\n-- LaTeX del acta")
    comprobar("escapa & % _ #", D._tex("A&B%C_D#E") == r"A\&B\%C\_D\#E")
    comprobar("conserva tildes", D._tex("José Ángel") == "José Ángel")
    comprobar("escapa llaves", D._tex("{x}") == r"\{x\}")

    registros = [
        {
            "grupo": 1, "cedula": "V-12345678", "nombre": "Ana & Co",
            "aciertos": 9, "total": 10, "nota": 9.0, "nota_recalculada": 9.0,
            "enviado_en": "2026-11-11T10:00:00Z", "archivo": "f", "avisos": [],
            "estado": "ok",
        }
    ]
    tex = D.latex_acta(
        registros,
        titulo="Rol Rojo",
        curso="CYBERSEGURIDAD",
        cuestionario="rol_rojo_cuestionario",
        fecha="2026-11-11T10:00:00Z",
        grupos=4,
        cobertura=None,
    )
    comprobar("usa longtable", r"\begin{longtable}" in tex)
    comprobar(
        "no invoca entornos con argumento que no lo tienen",
        r"\begin{cajaRecuerda}{" not in tex and r"\begin{cajaReto}{" not in tex,
    )
    comprobar("estilo como opción", r"\begin{tcolorbox}[cajaContenido" in tex)
    comprobar("nombre escapado", r"Ana \& Co" in tex)
    comprobar("no usa columna X de tabularx", "{@{}c l X" not in tex)

    tex_vacio = D.latex_acta(
        [],
        titulo="Rol Rojo",
        curso="CYBERSEGURIDAD",
        cuestionario="rol_rojo_cuestionario",
        fecha="",
        grupos=4,
        cobertura={"esperados": 2, "faltantes": [
            {"cedula": "V-1", "nombre": "Ana", "grupo": 1},
            {"cedula": "V-2", "nombre": "Luis", "grupo": 2},
        ], "sobrantes": [], "grupo_distinto": []},
    )
    comprobar("sin entregas lo dice", "Sin entregas" in tex_vacio)
    comprobar("lista a los faltantes", "V-1" in tex_vacio and "V-2" in tex_vacio)
    comprobar("fecha ausente -> guiones", "--" in tex_vacio)

    # Invariante de tabla: cabecera, filas y la fila vacía deben tener las mismas
    # columnas. Con 5 declaradas y 6 celdas por fila, pdflatex revienta con
    # "Extra alignment tab" y el PDF no se genera (pasó de verdad).
    def separadores(linea: str) -> int:
        """Cuenta `&` de separación, no los escapados (`Ana \& Co` es una celda)."""
        return len(re.findall(r"(?<!\\)&", linea))

    linea_cab = next(l for l in tex.splitlines() if r"\textbf{Cédula}" in l)
    linea_dat = next(l for l in tex.splitlines() if "V-12345678" in l)
    columnas = separadores(linea_cab)
    comprobar(
        "cabecera y filas tienen las mismas columnas",
        columnas == separadores(linea_dat),
        f"cabecera {columnas} vs fila {separadores(linea_dat)}",
    )
    linea_vacia = next(l for l in tex_vacio.splitlines() if "Sin entregas" in l)
    declaradas = int(re.search(r"\\multicolumn\{(\d+)\}", linea_vacia).group(1))
    comprobar(
        "la fila de tabla vacía ocupa todas las columnas",
        declaradas == columnas + 1,
        f"multicolumn {declaradas} vs {columnas + 1}",
    )
    spec = re.search(r"\\begin\{longtable\}\{@\{\}([^@]*)@\{\}\}", tex).group(1)
    columnas_spec = len(re.findall(r"[clr]|p\{[^}]*\}", spec))
    comprobar(
        "la especificación de columnas declara las mismas",
        columnas_spec == columnas + 1,
        f"{spec!r} -> {columnas_spec} vs {columnas + 1}",
    )


def test_repo_por_defecto() -> None:
    print("\n-- Repo de resultados")
    repo = D._repo_por_defecto()
    comprobar(
        "sale de wrangler.jsonc",
        repo == "cero97-ctrl/cuestionarios-resultados",
        str(repo),
    )


def test_guarda_de_privacidad() -> None:
    print("\n-- El acta no se escribe fuera de una ruta ignorada")
    fuente = RAIZ / "cursos/CYBERSEGURIDAD/evaluaciones/web/fuentes/ROL_ROJO_Cuestionario.md"
    if not fuente.is_file():
        comprobar("fuente de ejemplo presente", False, str(fuente))
        return
    with tempfile.TemporaryDirectory() as tmp:
        destino = Path(tmp) / "acta.csv"
        proc = subprocess.run(
            [sys.executable, str(RAIZ / "execution/descargar_resultados.py"),
             "--fuente", str(fuente), "--salida", str(destino), "--json", "--sin-pdf"],
            capture_output=True, text=True, timeout=120, cwd=RAIZ,
        )
        comprobar("sale con código 3", proc.returncode == 3, f"rc={proc.returncode} {proc.stderr[-300:]}")
        try:
            datos = json.loads(proc.stdout)
        except json.JSONDecodeError:
            datos = {}
        comprobar("explica que es por datos personales", "cédulas" in datos.get("message", ""), datos.get("message", ""))
        comprobar("no escribió nada", not destino.exists())


def main() -> int:
    print("Pruebas de execution/descargar_resultados.py")
    test_cedula()
    test_nombre()
    test_grupo()
    test_respuestas()
    test_recalcular()
    test_validar_registro()
    test_orden_y_csv()
    test_cobertura()
    test_resumen()
    test_tex_y_latex()
    test_repo_por_defecto()
    test_guarda_de_privacidad()
    print(f"\n{PRUEBAS - len(FALLOS)}/{PRUEBAS} aserciones OK")
    if FALLOS:
        print("FALLOS:")
        for f in FALLOS:
            print(f"  - {f}")
        return 1
    print("Sin fallos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
