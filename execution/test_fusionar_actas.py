#!/usr/bin/env python3
"""Pruebas del fusionador de actas (regular + recuperación).

Fija el contrato que evita perder o duplicar una entrega: la fusión es una unión
por cédula normalizada con la regla del Worker, una cédula en las dos actas es
un conflicto (no se elige una en silencio), las cabeceras distintas se rechazan
y la salida solo se escribe donde git la ignora.

Ejecutar: python3 execution/test_fusionar_actas.py
"""

from __future__ import annotations

import contextlib
import csv
import importlib.util
import io
import sys
import tempfile
from pathlib import Path
from unittest import mock

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
        "fusionar_bajo_test", RAIZ / "execution/fusionar_actas.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["fusionar_bajo_test"] = mod
    spec.loader.exec_module(mod)
    return mod


F = _cargar()

CABECERA = [
    "grupo",
    "cedula",
    "nombre",
    "aciertos",
    "total",
    "nota",
    "nota_recalculada",
    "enviado_en",
    "estado",
    "archivo",
    "avisos",
    "justificaciones",
    "duracion_s",
    "pegas",
]


def _fila(cedula: str, grupo: str = "1", nota: str = "7.50") -> dict:
    return {
        "grupo": grupo,
        "cedula": cedula,
        "nombre": "Alumno",
        "aciertos": "8",
        "total": "10",
        "nota": nota,
        "nota_recalculada": nota,
        "enviado_en": "2026-11-16T14:50:00Z",
        "estado": "ok",
        "archivo": "x.json",
        "avisos": "",
        "justificaciones": "",
        "duracion_s": "600",
        "pegas": "0",
    }


def _escribir(ruta: Path, filas: list[dict], cabecera: list[str] = CABECERA) -> None:
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(
            fh, fieldnames=cabecera, lineterminator="\n", extrasaction="ignore"
        )
        escritor.writeheader()
        for fila in filas:
            escritor.writerow(fila)


def _correr(argv: list[str]) -> tuple[int, str, str]:
    salida, error = io.StringIO(), io.StringIO()
    with mock.patch.object(sys, "argv", ["fusionar_actas.py", *argv]):
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(error):
            codigo = F.main()
    return codigo, salida.getvalue(), error.getvalue()


def main() -> int:
    with tempfile.TemporaryDirectory(dir=RAIZ / ".tmp") as crudo:
        tmp = Path(crudo)
        regular = tmp / "regular.csv"
        recup = tmp / "recup.csv"

        print("unión por cédula")
        _escribir(regular, [_fila("12345678"), _fila("23456789")])
        _escribir(recup, [_fila("34567890")])
        _, filas_reg, probs_reg = F.leer_acta(regular)
        _, filas_rec, probs_rec = F.leer_acta(recup)
        comprobar("las dos actas se leen sin problemas", not probs_reg and not probs_rec)
        fusionadas, probs = F.fusionar(filas_reg, [("recup.csv", filas_rec)])
        comprobar("tres entregas, cero conflictos", len(fusionadas) == 3 and not probs)
        origenes = {f["_cedula"]: f["origen"] for f in fusionadas}
        comprobar(
            "las regulares conservan su origen",
            origenes["V-12345678"] == "regular"
            and origenes["V-23456789"] == "regular",
        )
        comprobar(
            "la recuperación se marca como tal",
            origenes["V-34567890"] == "recuperacion",
        )
        comprobar(
            "orden determinista por grupo y cédula",
            [f["_cedula"] for f in fusionadas]
            == ["V-12345678", "V-23456789", "V-34567890"],
        )

        print("conflictos")
        _escribir(recup, [_fila("V-12345678")])
        _, filas_rec, _ = F.leer_acta(recup)
        _, probs = F.fusionar(filas_reg, [("recup.csv", filas_rec)])
        comprobar(
            "la misma cédula en las dos actas es conflicto",
            len(probs) == 1 and "V-12345678" in probs[0] and "dos veces" in probs[0],
            str(probs),
        )

        print("normalización igual que el Worker")
        _escribir(recup, [_fila("v 12.345.678")])
        _, filas_rec, _ = F.leer_acta(recup)
        _, probs = F.fusionar(filas_reg, [("recup.csv", filas_rec)])
        comprobar(
            "«v 12.345.678» colisiona con «V-12345678»",
            len(probs) == 1 and "V-12345678" in probs[0],
            str(probs),
        )

        print("actas inválidas")
        _escribir(recup, [_fila("12345678"), _fila("12345678")])
        _, _, probs = F.leer_acta(recup)
        comprobar("cédula repetida dentro de un acta falla", len(probs) == 1, str(probs))

        _escribir(recup, [_fila("no-es-cedula")])
        _, filas, probs = F.leer_acta(recup)
        comprobar(
            "cédula ilegible falla y no entra en la fusión",
            len(probs) == 1 and not filas,
            str(probs),
        )

        sin_nota = [c for c in CABECERA if c != "nota_recalculada"]
        _escribir(recup, [_fila("12345678")], cabecera=sin_nota)
        _, _, probs = F.leer_acta(recup)
        comprobar(
            "sin nota_recalculada no parece un acta",
            len(probs) == 1 and "nota_recalculada" in probs[0],
            str(probs),
        )

        print("salida")
        texto_a = F.csv_texto(CABECERA, fusionadas)
        texto_b = F.csv_texto(CABECERA, fusionadas)
        comprobar("la misma entrada da los mismos bytes", texto_a == texto_b)
        comprobar(
            "la cabecera termina en origen y no filtra _cedula",
            texto_a.splitlines()[0].endswith(",origen")
            and "_cedula" not in texto_a,
        )

        print("nómina")
        nomina = tmp / "nomina.tsv"
        nomina.write_text(
            "90000003\tAPELLIDO\tNOMBRE\n90000002\tOTRO\tALUMNO\n90000004\tTERCERO\tALUMNO\n",
            encoding="utf-8",
        )
        cedulas, probs = F.leer_nomina(nomina)
        comprobar(
            "lee la exportación TSV sin cabecera",
            cedulas == {"V-90000003", "V-90000002", "V-90000004"} and not probs,
            str(cedulas),
        )
        comprobar(
            "las cédulas se normalizan con el prefijo V",
            "V-90000003" in cedulas,
        )

        print("punto de entrada")
        salida = tmp / "fusion.csv"
        _escribir(regular, [_fila("12345678"), _fila("23456789")])
        _escribir(recup, [_fila("34567890")])
        codigo, stdout, _ = _correr(
            [
                "--acta",
                str(regular),
                "--recuperacion",
                str(recup),
                "--lista",
                str(nomina),
                "--salida",
                str(salida),
                "--json",
            ]
        )
        comprobar("fusiona y sale 0", codigo == 0, f"código {codigo}")
        comprobar("escribe el acta", salida.is_file())
        datos = F.json.loads(stdout)
        comprobar(
            "el resumen cuadra",
            datos["filas"] == 3 and datos["regular"] == 2 and datos["recuperacion"] == 1,
            str(datos),
        )
        comprobar(
            "reporta quién sigue sin entrega",
            datos["faltantes"] == ["V-90000002", "V-90000003", "V-90000004"],
            str(datos["faltantes"]),
        )
        comprobar(
            "avisa de entregas fuera de la nómina",
            any("no están en la nómina" in a for a in datos["avisos"]),
            str(datos["avisos"]),
        )

        _escribir(recup, [_fila("V-12345678")])
        codigo, _, error = _correr(
            ["--acta", str(regular), "--recuperacion", str(recup), "--salida", str(salida)]
        )
        comprobar("un conflicto sale 3", codigo == 3, f"código {codigo}")
        comprobar("el conflicto se explica en stderr", "dos veces" in error, error)

        _escribir(recup, [_fila("34567890")])
        codigo, _, error = _correr(
            [
                "--acta",
                str(regular),
                "--recuperacion",
                str(recup),
                "--salida",
                str(RAIZ / "acta_fusionada_test.csv"),
            ]
        )
        comprobar(
            "una ruta no ignorada por git se rechaza",
            codigo == 3 and "ignorada por git" in error,
            f"código {codigo}: {error}",
        )
        comprobar(
            "no se crea el acta en la raíz del repo",
            not (RAIZ / "acta_fusionada_test.csv").exists(),
        )

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
