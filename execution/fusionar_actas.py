#!/usr/bin/env python3
"""fusionar_actas.py — Capa 3: une el acta del examen regular con las de recuperación.

Por qué es una **unión** y no un reemplazo de filas: el acta solo contiene
entregas. Quien no entregó no es una fila, es una ausencia en la cobertura; por
eso el acta regular de los alumnos que sí presentaron no tiene fila para el
afectado, y el acta de recuperación sí. Fusionar es unir por cédula normalizada.

Reglas:
- Cada fila conserva todas sus columnas y gana `origen` (`regular` o
  `recuperacion`).
- Una misma cédula en las dos actas es un conflicto (entregó dos veces o hay un
  archivo cruzado): se falla con código 3, no se elige una en silencio.
- Las cédulas se normalizan con `normalizar_cedula` de `descargar_resultados.py`,
  que es la misma regla del Worker; no se reimplementa.
- La salida lleva nombres y cédulas, así que solo se escribe en rutas que git
  ignora (`.tmp/` o `cursos/<CURSO>/evaluaciones/resultados/`), con la misma
  comprobación que el acta.

Uso:
    python3 execution/fusionar_actas.py --acta .tmp/acta_regular.csv \
        --recuperacion .tmp/acta_recup_azul.csv \
        --recuperacion .tmp/acta_recup_purpura.csv \
        --lista cursos/CYBERSEGURIDAD/evaluaciones/alumnos_cyberseguridad.csv \
        --salida .tmp/acta_fusionada.csv --json

Códigos de salida: 0 ok · 1 E/S · 3 datos inconsistentes o uso incorrecto.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

EJECUCION = Path(__file__).resolve().parent
RAIZ = EJECUCION.parent
sys.path.insert(0, str(EJECUCION))

import descargar_resultados as acta  # noqa: E402  (capa 3: normalización y acta)

EXIT_OK = 0
EXIT_IO = 1
EXIT_DATOS = 3

CABECERA_MINIMA = ("grupo", "cedula", "nombre", "nota_recalculada")
ORIGEN_REGULAR = "regular"
ORIGEN_RECUPERACION = "recuperacion"


def leer_acta(ruta: Path) -> tuple[list[str], list[dict], list[str]]:
    """Devuelve (cabecera, filas, problemas). Cada fila lleva `_cedula` normalizada."""
    try:
        texto = ruta.read_text(encoding="utf-8")
    except OSError as exc:
        return [], [], [f"no se pudo leer {ruta}: {exc}"]
    lector = csv.DictReader(io.StringIO(texto))
    cabecera = list(lector.fieldnames or [])
    faltan = [c for c in CABECERA_MINIMA if c not in cabecera]
    if faltan:
        return cabecera, [], [
            f"{ruta.name}: faltan columnas {', '.join(faltan)}; no parece un acta"
        ]
    filas: list[dict] = []
    problemas: list[str] = []
    vistos: dict[str, int] = {}
    for i, fila in enumerate(lector, start=2):
        cedula = acta.normalizar_cedula(fila.get("cedula"))
        if cedula is None:
            problemas.append(
                f"{ruta.name} fila {i}: cédula inválida {fila.get('cedula')!r}"
            )
            continue
        if cedula in vistos:
            problemas.append(
                f"{ruta.name}: cédula {cedula} repetida (filas {vistos[cedula]} y {i})"
            )
            continue
        vistos[cedula] = i
        fila["_cedula"] = cedula
        filas.append(fila)
    return cabecera, filas, problemas


def leer_nomina(ruta: Path) -> tuple[set[str], list[str]]:
    """Cédulas normalizadas de la nómina.

    Acepta la exportación de la universidad (TSV sin cabecera), CSV con cabecera
    o una cédula por línea: se toma la primera columna de cada línea y se
    normaliza con la regla del Worker. Las líneas sin cédula legible se ignoran.
    """
    try:
        texto = ruta.read_text(encoding="utf-8")
    except OSError as exc:
        return set(), [f"no se pudo leer la nómina {ruta}: {exc}"]
    cedulas: set[str] = set()
    problemas: list[str] = []
    for i, linea in enumerate(texto.splitlines(), start=1):
        if not linea.strip():
            continue
        campo = linea.replace("\t", ",").replace(";", ",").split(",")[0].strip()
        cedula = acta.normalizar_cedula(campo)
        if cedula is None:
            continue
        if cedula in cedulas:
            problemas.append(f"nómina fila {i}: cédula {cedula} repetida")
            continue
        cedulas.add(cedula)
    if not cedulas:
        problemas.append(f"la nómina no tiene cédulas legibles ({ruta})")
    return cedulas, problemas


def fusionar(
    regular: list[dict], recuperaciones: list[tuple[str, list[dict]]]
) -> tuple[list[dict], list[str]]:
    """Unión por cédula. Devuelve (filas con `origen`, problemas)."""
    problemas: list[str] = []
    por_cedula: dict[str, tuple[dict, str]] = {}
    for fila in regular:
        por_cedula[fila["_cedula"]] = (fila, ORIGEN_REGULAR)
    for nombre, filas in recuperaciones:
        for fila in filas:
            cedula = fila["_cedula"]
            if cedula in por_cedula:
                _, origen = por_cedula[cedula]
                problemas.append(
                    f"cédula {cedula} aparece en el acta {origen} y en {nombre}: "
                    "o entregó dos veces o hay un archivo cruzado; "
                    "resolver a mano antes de fusionar"
                )
                continue
            por_cedula[cedula] = (fila, ORIGEN_RECUPERACION)
    filas = [dict(fila, origen=origen) for fila, origen in por_cedula.values()]
    filas.sort(key=_clave_orden)
    return filas, problemas


def _clave_orden(fila: dict) -> tuple[int, str]:
    grupo = str(fila.get("grupo", "")).strip()
    try:
        numero = int(grupo)
    except ValueError:
        numero = 0
    return numero, fila["_cedula"]


def csv_texto(cabecera: list[str], filas: list[dict]) -> str:
    campos = list(cabecera) + ["origen"]
    salida = io.StringIO()
    escritor = csv.DictWriter(
        salida, fieldnames=campos, lineterminator="\n", extrasaction="ignore"
    )
    escritor.writeheader()
    for fila in filas:
        escritor.writerow({campo: fila.get(campo, "") for campo in campos})
    return salida.getvalue()


def _resultado(status: str, code: int, **extra) -> dict:
    return {"status": status, "code": code, **extra}


def _imprimir(datos: dict, como_json: bool) -> None:
    if como_json:
        print(json.dumps(datos, ensure_ascii=False, indent=2))
        return
    if datos["status"] == "ok":
        print(
            f"acta fusionada: {datos['filas']} filas "
            f"({datos['regular']} regular + {datos['recuperacion']} recuperación) "
            f"-> {datos['acta']}"
        )
        if datos.get("faltantes"):
            print(f"  sin entrega: {', '.join(datos['faltantes'])}")
        for aviso in datos.get("avisos", []):
            print(f"  aviso: {aviso}")
    else:
        mensaje = datos.get("message")
        if mensaje:
            print(f"error: {mensaje}", file=sys.stderr)
        for problema in datos.get("problemas", []):
            print(f"  - {problema}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fusiona el acta regular con las actas de recuperación."
    )
    parser.add_argument("--acta", required=True, help="Acta CSV del examen regular.")
    parser.add_argument(
        "--recuperacion",
        action="append",
        default=[],
        required=True,
        help="Acta CSV de recuperación (repetible, una por grupo).",
    )
    parser.add_argument(
        "--lista",
        default=None,
        help="Nómina para reportar quién sigue sin entrega (TSV/CSV, cédula primero).",
    )
    parser.add_argument(
        "--salida",
        default=".tmp/acta_fusionada.csv",
        help="CSV de salida (debe estar ignorado por git).",
    )
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    args = parser.parse_args()

    acta_regular = Path(args.acta).resolve()
    if not acta_regular.is_file():
        datos = _resultado("error", EXIT_DATOS, message=f"no existe {acta_regular}")
        _imprimir(datos, args.json)
        return EXIT_DATOS

    cabecera, regular, problemas = leer_acta(acta_regular)
    if problemas:
        datos = _resultado("error", EXIT_DATOS, problemas=problemas)
        _imprimir(datos, args.json)
        return EXIT_DATOS

    recuperaciones: list[tuple[str, list[dict]]] = []
    for ruta_cruda in args.recuperacion:
        ruta = Path(ruta_cruda).resolve()
        if not ruta.is_file():
            problemas.append(f"no existe {ruta}")
            continue
        cab, filas, probs = leer_acta(ruta)
        problemas.extend(probs)
        if cab != cabecera:
            problemas.append(
                f"{ruta.name}: cabecera distinta del acta regular "
                "(¿actas de versiones distintas?)"
            )
            continue
        recuperaciones.append((ruta.name, filas))
    if problemas:
        datos = _resultado("error", EXIT_DATOS, problemas=problemas)
        _imprimir(datos, args.json)
        return EXIT_DATOS

    filas, problemas = fusionar(regular, recuperaciones)
    if problemas:
        datos = _resultado("error", EXIT_DATOS, problemas=problemas)
        _imprimir(datos, args.json)
        return EXIT_DATOS
    if not filas:
        datos = _resultado(
            "error", EXIT_DATOS, problemas=["no hay ninguna entrega que fusionar"]
        )
        _imprimir(datos, args.json)
        return EXIT_DATOS

    salida = Path(args.salida).resolve()
    if not acta._git_ignorado(salida):
        datos = _resultado(
            "error",
            EXIT_DATOS,
            message=(
                f"{salida} no está ignorada por git y el acta lleva nombres y "
                "cédulas: elegir una ruta dentro de .tmp/ o de "
                "cursos/<CURSO>/evaluaciones/resultados/"
            ),
        )
        _imprimir(datos, args.json)
        return EXIT_DATOS

    try:
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text(csv_texto(cabecera, filas), encoding="utf-8")
    except OSError as exc:
        datos = _resultado("error", EXIT_IO, message=f"no se pudo escribir {salida}: {exc}")
        _imprimir(datos, args.json)
        return EXIT_IO

    faltantes: list[str] = []
    sobrantes: list[str] = []
    avisos: list[str] = []
    if args.lista:
        esperados, avisos_nomina = leer_nomina(Path(args.lista).resolve())
        avisos.extend(avisos_nomina)
        fusionadas = {fila["_cedula"] for fila in filas}
        faltantes = sorted(esperados - fusionadas)
        sobrantes = sorted(fusionadas - esperados)
        if sobrantes:
            avisos.append(
                "entregas de cédulas que no están en la nómina: "
                + ", ".join(sobrantes)
            )

    datos = _resultado(
        "ok",
        EXIT_OK,
        acta=str(salida),
        filas=len(filas),
        regular=len(regular),
        recuperacion=sum(len(filas_r) for _, filas_r in recuperaciones),
        faltantes=faltantes,
        sobrantes=sobrantes,
        avisos=avisos,
    )
    _imprimir(datos, args.json)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
