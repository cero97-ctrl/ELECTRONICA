#!/usr/bin/env python3
"""Pruebas del acta consolidada por semana (`execution/acta_semana.py`).

Fija el contrato del documento que el profesor archiva cada semana: las actas por
grupo se unen por cédula normalizada (una cédula repetida es un error, no una
fila más), el orden es estable, los faltantes salen de las nóminas y **no** de la
lista de entregas, la fecha es el último envío real, y la tabla LaTeX lleva
exactamente 7 columnas por fila (el bug de «Extra alignment tab» ya ocurrió una
vez y cuesta una compilación entera descubrirlo).

No compila LaTeX ni toca la red: la compilación se verifica aparte con
`execution/verificar_pdf.py`.

Ejecutar: python3 execution/test_acta_semana.py
"""

from __future__ import annotations

import contextlib
import csv
import importlib.util
import io
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FALLOS: list[str] = []
PRUEBAS = 0

CABECERA = [
    "grupo", "cedula", "nombre", "aciertos", "total", "nota", "nota_recalculada",
    "enviado_en", "estado", "archivo", "avisos", "justificaciones", "duracion_s", "pegas",
]


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
        "acta_semana_bajo_test", RAIZ / "execution/acta_semana.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["acta_semana_bajo_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def _fila(grupo, cedula, nombre, enviado="2026-11-16T15:00:00Z",
          estado="ok", justificaciones="ok", aciertos=9, total=10):
    return {
        "grupo": grupo, "cedula": cedula, "nombre": nombre, "aciertos": aciertos,
        "total": total, "nota": "9.00", "nota_recalculada": "9.00",
        "enviado_en": enviado, "estado": estado, "archivo": f"{cedula}.json",
        "avisos": "", "justificaciones": justificaciones, "duracion_s": "900", "pegas": "0",
    }


def _escribir(ruta: Path, filas: list[dict], cabecera: list[str] | None = None) -> Path:
    with ruta.open("w", newline="", encoding="utf-8") as fh:
        escritor = csv.DictWriter(fh, fieldnames=cabecera or CABECERA)
        escritor.writeheader()
        for fila in filas:
            escritor.writerow({c: fila.get(c, "") for c in escritor.fieldnames})
    return ruta


def _lista(ruta: Path, filas: list[tuple[int, str, str]]) -> Path:
    with ruta.open("w", newline="", encoding="utf-8") as fh:
        escritor = csv.writer(fh)
        escritor.writerow(["grupo", "cedula", "nombre"])
        escritor.writerows(filas)
    return ruta


def _captura(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        valor = fn(*a, **k)
    return valor, buf.getvalue()


def main() -> int:
    mod = _cargar()

    print("slug_semana")
    comprobar("1 -> SEMANA_01", mod.slug_semana(1) == ("SEMANA_01", "acta_semana_01"))
    comprobar("12 -> SEMANA_12", mod.slug_semana(12) == ("SEMANA_12", "acta_semana_12"))
    for malo in (0, -3, True, "1", 1.5):
        try:
            mod.slug_semana(malo)
            comprobar(f"{malo!r} se rechaza", False, "no lanzó ValueError")
        except ValueError:
            comprobar(f"{malo!r} se rechaza", True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        actas = tmp / "resultados"
        actas.mkdir()

        print("seleccionar_actas")
        try:
            mod.seleccionar_actas(actas)
            comprobar("carpeta vacía se rechaza", False)
        except ValueError:
            comprobar("carpeta vacía se rechaza", True)
        try:
            mod.seleccionar_actas(tmp / "no-existe")
            comprobar("carpeta inexistente se rechaza", False)
        except ValueError:
            comprobar("carpeta inexistente se rechaza", True)

        _escribir(actas / "acta_rol_b_cuestionario.csv", [_fila(2, "V-22222222", "B, Alumno")])
        _escribir(actas / "acta_rol_a_cuestionario.csv", [_fila(1, "V-11111111", "A, Alumno")])
        _escribir(actas / "actas.csv", [_fila(9, "V-99999999", "NO VA")])
        rutas = mod.seleccionar_actas(actas)
        nombres = [p.name for p in rutas]
        comprobar("solo acta_*.csv", nombres == ["acta_rol_a_cuestionario.csv",
                                                 "acta_rol_b_cuestionario.csv"], str(nombres))
        comprobar("actas.csv queda fuera", "actas.csv" not in nombres)

        print("leer_acta")
        filas = mod.leer_acta(actas / "acta_rol_a_cuestionario.csv")
        comprobar("una fila", len(filas) == 1)
        comprobar("grupo entero", filas[0]["grupo"] == 1 and isinstance(filas[0]["grupo"], int))
        comprobar("nota flotante", filas[0]["nota_recalculada"] == 9.0)
        comprobar("justif_estado desde justificaciones", filas[0]["justif_estado"] == "ok")
        sin_just = _escribir(
            tmp / "sin_just.csv", [_fila(1, "V-11111111", "A", justificaciones="")]
        )
        fila = mod.leer_acta(sin_just)[0]
        comprobar("sin columna justificaciones -> n/a", fila["justif_estado"] == "n/a")

        truncada = tmp / "truncada.csv"
        truncada.write_text("grupo,cedula\n1,V-1\n", encoding="utf-8")
        try:
            mod.leer_acta(truncada)
            comprobar("cabecera incompleta se rechaza", False)
        except ValueError as exc:
            comprobar("cabecera incompleta se rechaza", "faltan columnas" in str(exc), str(exc))

        mala = _escribir(tmp / "mala.csv", [_fila(1, "V-11111111", "A", aciertos="nueve")])
        try:
            mod.leer_acta(mala)
            comprobar("aciertos no numéricos se rechazan", False)
        except ValueError:
            comprobar("aciertos no numéricos se rechazan", True)

        rango = _escribir(tmp / "rango.csv", [_fila(1, "V-11111111", "A", aciertos=12)])
        try:
            mod.leer_acta(rango)
            comprobar("aciertos > total se rechazan", False)
        except ValueError:
            comprobar("aciertos > total se rechazan", True)

        print("consolidar")
        registros = mod.consolidar(rutas)
        comprobar("une las dos actas", len(registros) == 2)
        comprobar("orden por (grupo, cédula)",
                  [(r["grupo"], r["cedula"]) for r in registros]
                  == [(1, "V-11111111"), (2, "V-22222222")])

        duplicada = _escribir(tmp / "dup.csv", [_fila(1, "V-11111111", "Otra vez")])
        try:
            mod.consolidar([actas / "acta_rol_a_cuestionario.csv", duplicada])
            comprobar("cédula repetida entre actas se rechaza", False)
        except ValueError as exc:
            comprobar("cédula repetida entre actas se rechaza", "duplicada" in str(exc), str(exc))

        print("faltantes")
        comprobar("sin nómina no inventa faltantes", mod.faltantes(registros, []) == (0, []))
        l1 = _lista(tmp / "grupo_1.csv", [(1, "11111111", "A, Alumno")])
        l2 = _lista(tmp / "grupo_2.csv", [(2, "22222222", "B ALUMNO"),
                                          (2, "33333333", "C ALUMNO")])
        esperados, ausentes = mod.faltantes(registros, [l1, l2])
        comprobar("esperados = nómina", esperados == 3)
        comprobar("detecta al que no entregó",
                  [f["cedula"] for f in ausentes] == ["V-33333333"], str(ausentes))
        comprobar("el ausente conserva grupo y nombre",
                  ausentes[0]["grupo"] == 2 and "C ALUMNO" in ausentes[0]["nombre"])
        l_dup = _lista(tmp / "grupo_1b.csv", [(1, "V-11111111", "A, Alumno")])
        try:
            mod.faltantes(registros, [l1, l_dup])
            comprobar("cédula repetida en las nóminas se rechaza", False)
        except ValueError:
            comprobar("cédula repetida en las nóminas se rechaza", True)
        _, todos = mod.faltantes([], [l1, l2])
        comprobar("sin entregas, todos son faltantes", len(todos) == 3)

        print("curso_desde")
        comprobar("deriva el curso de la ruta",
                  mod.curso_desde(Path("cursos/CYBERSEGURIDAD/evaluaciones/resultados"))
                  == "CYBERSEGURIDAD")
        comprobar("ruta ajena -> Curso", mod.curso_desde(Path("/tmp/x")) == "Curso")

        print("construir")
        latex = mod.construir(
            registros, curso="CYBERSEGURIDAD", semana=1,
            esperados=esperados, ausentes=ausentes,
        )
        comprobar("documento cerrado", latex.rstrip().endswith(r"\end{document}"))
        comprobar("una longtable", latex.count(r"\begin{longtable}") == 1)
        comprobar("lista las cédulas", "V-11111111" in latex and "V-22222222" in latex)
        comprobar("usa la fecha del último envío", "2026-11-16T15:00:00Z" in latex)
        comprobar("cobertura con faltante", "Sin entrega" in latex and "V-33333333" in latex)
        comprobar("declara los 4 grupos cuando la nómina los tiene",
                  r"Grupos declarados: 2" in latex)
        completo = mod.construir(registros, curso="X", semana=2, esperados=2, ausentes=[])
        comprobar("cobertura completa", "Cobertura completa" in completo)
        sin_nomina = mod.construir(registros, curso="X", semana=3, esperados=0, ausentes=[])
        comprobar("sin nómina avisa que no es verificable",
                  "Cobertura no verificable" in sin_nomina)

        escapado = mod.construir(
            [{"grupo": 1, "cedula": "V-11111111", "nombre": "PEREZ & CIA_S.A.",
              "aciertos": 10, "total": 10, "nota_recalculada": 10.0,
              "enviado_en": "2026-11-16T15:00:00Z", "estado": "revisar",
              "justif_estado": "copiada"}],
            curso="X", semana=4, esperados=0, ausentes=[],
        )
        comprobar("escapa & y _ del nombre", r"PEREZ \& CIA\_S.A." in escapado)

        print("caja A revisar a mano")
        comprobar("sin filas revisables no hay caja", r"title={A revisar a mano}" not in latex)
        comprobar("el pie ya no afirma que solo difieren de la nota",
                  "no son publicables" in latex
                  and "difieren de la nota que" not in latex)
        comprobar("sin revisables el pie no remite a una caja inexistente",
                  "A revisar a mano" not in latex)

        revisable = dict(registros[0])
        revisable["estado"] = "revisar"
        revisable["avisos"] = "la justificación de la pregunta 10 es casi idéntica a la de V-22222222"
        con_caja = mod.construir([revisable], curso="X", semana=5, esperados=0, ausentes=[])
        comprobar("la caja aparece con una fila revisable",
                  r"title={A revisar a mano}" in con_caja)
        comprobar("la caja dice cuántas filas son", "1 fila(s) no publicables" in con_caja)
        comprobar("con revisables el pie remite a la caja",
                  "está en la caja «A revisar a mano»" in con_caja)
        comprobar("la caja trae el motivo y la cédula",
                  "V-11111111" in con_caja and "pregunta 10" in con_caja)
        comprobar("el aviso se une con ; y no rompe el LaTeX",
                  con_caja.count("\\item") >= 1)

        varios = dict(revisable)
        varios["avisos"] = ["primer motivo", "segundo motivo"]
        con_dos = mod.construir([varios], curso="X", semana=6, esperados=0, ausentes=[])
        comprobar("avisos en lista se unen", "primer motivo; segundo motivo" in con_dos)

        sin_aviso = dict(registros[0])
        sin_aviso["estado"] = "revisar"
        sin_aviso["avisos"] = ""
        sin_aviso["justif_estado"] = "copiada"
        con_fallback = mod.construir([sin_aviso], curso="X", semana=7, esperados=0, ausentes=[])
        comprobar("sin aviso el motivo sale de justif_estado",
                  "justificación marcada como copiada" in con_fallback)

        filas_tabla = [
            ln for ln in latex.splitlines()
            if ln.endswith(r"\\") and "longtable" not in ln and r"\midrule" not in ln
        ]
        comprobar("7 columnas por fila (6 &)",
                  bool(filas_tabla) and all(ln.count("&") == 6 for ln in filas_tabla),
                  str([ln.count("&") for ln in filas_tabla]))

        print("main (sin PDF)")
        salida = tmp / "SEMANA_09"
        argv = ["acta_semana.py", "--semana", "9", "--actas-dir", str(actas),
                "--salida", str(salida), "--sin-pdf", "--json",
                "--lista", str(l1), "--lista", str(l2)]
        with contextlib.redirect_stdout(io.StringIO()):
            viejo = sys.argv
            sys.argv = argv
            try:
                code = mod.main()
            finally:
                sys.argv = viejo
        comprobar("main devuelve 0", code == 0, str(code))
        comprobar("escribe acta_semana_09.tex", (salida / "acta_semana_09.tex").is_file())
        comprobar("--sin-pdf no deja PDF", not (salida / "acta_semana_09.pdf").exists())
        comprobar("no deja basura en la raíz del repo",
                  not (RAIZ / "acta_semana_09.tex").exists())

    print()
    if FALLOS:
        print(f"{len(FALLOS)} FALLOS de {PRUEBAS} aserciones")
        for fallo in FALLOS:
            print(f"  - {fallo}")
        return 1
    print(f"{PRUEBAS}/{PRUEBAS} aserciones OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
