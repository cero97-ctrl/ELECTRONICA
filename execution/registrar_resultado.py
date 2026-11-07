#!/usr/bin/env python3
"""
registrar_resultado.py — Registro de entregas corregidas (Layer 3: Execution)

Deja constancia durable de una entrega corregida: copia el informe corregido a la
carpeta local del grupo y añade una fila al acta acumulada del curso. El acta es la
fuente del cierre de notas, así que la escritura es atómica, la nota se valida
contra la escala del curso y un registro duplicado se rechaza salvo que se pida
reemplazarlo.

Uso:
    python3 execution/registrar_resultado.py --curso cursos/CYBERSEGURIDAD/curso.yaml \\
        --semana 1 --grupo 2 --nota 7.5 \\
        --documento /ruta/informe_corregido.pdf

    python3 execution/registrar_resultado.py ... --no-fiable --observaciones "escala dudosa"
    python3 execution/registrar_resultado.py ... --reemplazar

Salida (stdout, JSON):
    {"status": "ok", "acta": "...", "fila": {...}, "documento": "..."}

Códigos de salida:
    0 — registro escrito y verificado
    1 — argumentos de línea de comandos inválidos
    2 — descriptor ilegible o que no es YAML
    3 — datos inválidos (semana, grupo, nota fuera de escala o documento inexistente)
    4 — la entrega ya estaba registrada (usar --reemplazar para corregirla)
    5 — error de escritura en disco

Por qué existe: una nota se escribe una vez y se lee todo el semestre. Un CSV
editado a mano admite "7,5" en una fila, "0-10" implícito y dos filas del mismo
grupo y semana; el acta entonces miente y nadie lo nota. Aquí la forma de la fila y
el rango de la nota son código, no disciplina.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
RAIZ = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(RAIZ))

CABECERA = [
    "fecha",
    "semana",
    "grupo",
    "rol",
    "documento",
    "nota_sobre_10",
    "nota_fiable",
    "observaciones",
]

EXIT_OK = 0
EXIT_USO = 1
EXIT_DESCRIPTOR = 2
EXIT_INVALIDO = 3
EXIT_DUPLICADO = 4
EXIT_DISCO = 5


def cargar_descriptor(curso: Path) -> dict[str, Any]:
    """Carga el descriptor YAML del curso.

    Args:
        curso: Ruta al `curso.yaml`.

    Returns:
        Descriptor como diccionario.

    Raises:
        ValueError: si el fichero no existe o no es un mapa YAML.
    """
    if not curso.exists():
        raise ValueError(f"no existe el descriptor {curso}")
    try:
        datos = yaml.safe_load(curso.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"el descriptor no es YAML válido: {exc}") from exc
    if not isinstance(datos, dict):
        raise ValueError("el descriptor no es un mapa YAML")
    return datos


def _semana(datos: dict[str, Any], numero: int) -> dict[str, Any]:
    """Devuelve el bloque de la semana pedida.

    Raises:
        ValueError: si la semana no existe.
    """
    for semana in datos.get("semanas") or []:
        if int(semana.get("numero", 0)) == numero:
            return semana
    raise ValueError(f"la semana {numero} no existe en el descriptor")


def rol_del_grupo(datos: dict[str, Any], semana: dict[str, Any], grupo: int) -> str:
    """Rol del grupo esa semana, o 'individual' si la fase no tiene roles.

    Args:
        datos: Descriptor del curso.
        semana: Bloque de la semana.
        grupo: Número de grupo.

    Returns:
        Nombre del rol, o `individual`.
    """
    grupos = datos.get("grupos") or {}
    inicial = grupos.get("asignacion_inicial") or []
    fases_con_roles = [int(f) for f in grupos.get("fase_con_roles") or []]
    if not inicial or int(semana["fase"]) not in fases_con_roles:
        return "individual"
    if not 1 <= grupo <= len(inicial):
        return "individual"
    turno = (int(semana["fase"]) - 1) % len(inicial)
    return inicial[(grupo - 1 + turno) % len(inicial)]


def validar(datos: dict[str, Any], args: argparse.Namespace) -> list[str]:
    """Comprueba semana, grupo, nota y documento antes de escribir nada."""
    problemas: list[str] = []
    meta = datos.get("meta") or {}
    semanas_totales = int(meta.get("semanas") or 0)
    if semanas_totales and not 1 <= args.semana <= semanas_totales:
        problemas.append(f"semana {args.semana} fuera de rango (1..{semanas_totales})")
    else:
        try:
            _semana(datos, args.semana)
        except ValueError as exc:
            problemas.append(str(exc))

    cantidad = int((datos.get("grupos") or {}).get("cantidad") or 0)
    if cantidad and not 1 <= args.grupo <= cantidad:
        problemas.append(f"grupo {args.grupo} fuera de rango (1..{cantidad})")

    if not 0.0 <= args.nota <= 10.0:
        problemas.append(f"nota {args.nota} fuera de la escala 0..10")
    if int((datos.get("evaluacion") or {}).get("escala", 10)) != 10:
        problemas.append(
            "la escala del curso no es 10: revisar evaluacion.escala y el acta"
        )
    if args.documento and not Path(args.documento).exists():
        problemas.append(f"no existe el documento {args.documento}")
    return problemas


def _leer_acta(ruta: Path) -> list[dict[str, str]]:
    """Lee el acta tolerando un fichero todavía inexistente."""
    if not ruta.exists():
        return []
    with ruta.open(newline="", encoding="utf-8") as fh:
        lector = csv.DictReader(fh)
        return [dict(fila) for fila in lector]


def _escribir_acta(ruta: Path, filas: list[dict[str, str]]) -> None:
    """Escribe el acta de forma atómica (temporal + rename)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporal = tempfile.mkstemp(dir=str(ruta.parent), prefix=".actas_", suffix=".csv")
    try:
        with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as fh:
            escritor = csv.DictWriter(fh, fieldnames=CABECERA)
            escritor.writeheader()
            escritor.writerows(filas)
        os.replace(temporal, ruta)
    except BaseException:
        Path(temporal).unlink(missing_ok=True)
        raise


def registrar(
    datos: dict[str, Any],
    resultados: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    """Copia el documento y añade o reemplaza la fila del acta.

    Args:
        datos: Descriptor validado.
        resultados: Carpeta `resultados/` del curso.
        args: Argumentos ya validados.

    Returns:
        Diccionario con la ruta del acta y la fila escrita.

    Raises:
        FileExistsError: si la entrega ya estaba registrada y no se pidió reemplazo.
    """
    semana = _semana(datos, args.semana)
    rol = rol_del_grupo(datos, semana, args.grupo)
    destino_dir = resultados / f"semana_{args.semana:02d}" / f"grupo_{args.grupo}"
    destino_doc = ""
    if args.documento:
        destino_dir.mkdir(parents=True, exist_ok=True)
        origen = Path(args.documento)
        destino = destino_dir / origen.name
        shutil.copy2(origen, destino)
        destino_doc = str(destino)

    fila = {
        "fecha": args.fecha or date.today().isoformat(),
        "semana": f"{args.semana:02d}",
        "grupo": str(args.grupo),
        "rol": rol,
        "documento": destino_doc or (args.documento or ""),
        "nota_sobre_10": f"{args.nota:.2f}",
        "nota_fiable": "false" if args.no_fiable else "true",
        "observaciones": args.observaciones or "",
    }

    acta = resultados / "actas.csv"
    filas = _leer_acta(acta)
    indice = next(
        (
            i
            for i, existente in enumerate(filas)
            if existente.get("semana") == fila["semana"]
            and existente.get("grupo") == fila["grupo"]
        ),
        None,
    )
    if indice is not None and not args.reemplazar:
        raise FileExistsError(
            f"la semana {fila['semana']} del grupo {fila['grupo']} ya está registrada "
            f"(nota {filas[indice].get('nota_sobre_10')}); usar --reemplazar para corregirla"
        )
    if indice is not None:
        anterior = filas[indice]
        if not args.documento and anterior.get("documento"):
            fila["documento"] = anterior["documento"]
            fila["observaciones"] = fila["observaciones"] or anterior.get("observaciones", "")
        filas[indice] = fila
    else:
        filas.append(fila)
    _escribir_acta(acta, filas)
    return {"acta": str(acta), "fila": fila, "documento": destino_doc}


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada del registro."""
    parser = argparse.ArgumentParser(
        description="Registra una entrega corregida en el acta local del curso."
    )
    parser.add_argument("--curso", required=True, help="Ruta al descriptor curso.yaml")
    parser.add_argument("--semana", required=True, type=int, help="Número de semana")
    parser.add_argument("--grupo", required=True, type=int, help="Número de grupo")
    parser.add_argument("--nota", required=True, type=float, help="Nota sobre 10")
    parser.add_argument("--documento", default=None, help="Informe corregido a archivar (PDF)")
    parser.add_argument("--no-fiable", action="store_true",
                        help="Marcar la nota como no fiable (requiere revisión a mano)")
    parser.add_argument("--observaciones", default=None, help="Nota breve para el acta")
    parser.add_argument("--fecha", default=None, help="Fecha ISO del registro (por defecto, hoy)")
    parser.add_argument("--reemplazar", action="store_true",
                        help="Reemplaza la fila si ya existe semana+grupo")
    parser.add_argument("--salida", default=None, help="Carpeta resultados/ (por defecto <curso>/evaluaciones/resultados)")
    parser.add_argument("--json", action="store_true", help="Emite un único objeto JSON")
    args = parser.parse_args(argv)

    curso = Path(args.curso).resolve()
    try:
        datos = cargar_descriptor(curso)
    except ValueError as exc:
        print(json.dumps({"status": "error", "problemas": [str(exc)]}, ensure_ascii=False), file=sys.stderr)
        return EXIT_DESCRIPTOR

    problemas = validar(datos, args)
    if problemas:
        print(json.dumps({"status": "invalido", "problemas": problemas}, ensure_ascii=False, indent=2))
        return EXIT_INVALIDO

    resultados = Path(args.salida).resolve() if args.salida else curso.parent / "evaluaciones" / "resultados"
    try:
        salida = registrar(datos, resultados, args)
    except FileExistsError as exc:
        print(json.dumps({"status": "duplicado", "problemas": [str(exc)]}, ensure_ascii=False, indent=2))
        return EXIT_DUPLICADO
    except OSError as exc:
        print(json.dumps({"status": "error", "problemas": [str(exc)]}, ensure_ascii=False), file=sys.stderr)
        return EXIT_DISCO

    salida_json = {"status": "ok", **salida}
    print(json.dumps(salida_json, ensure_ascii=False, indent=2))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
