#!/usr/bin/env python3
"""
acta_semana.py — Consolida las actas por grupo de una semana (Layer 3: Execution).

Lee los CSV que `flujo_acta_cuestionario.py` dejó en `evaluaciones/resultados/`
(uno por rol/grupo), los une, y emite **un solo** `.tex` + `.pdf` con el resumen
de la semana y una tabla donde cada fila lleva su grupo.

Uso:
    python3 execution/acta_semana.py --semana 1 \
        [--actas-dir cursos/CYBERSEGURIDAD/evaluaciones/resultados] \
        [--lista .tmp/grupo_1.csv --lista .tmp/grupo_2.csv ...] \
        [--salida DIR] [--curso NOMBRE] [--sin-pdf] [--json]

Salida (stdout, JSON):
    { "status": "ok", "code": 0, "semana": 1, "acta_tex": "...", "acta_pdf": "...",
      "entregas": 9, "grupos": 4, "por_grupo": {...}, "faltantes": [...],
      "a_revisar": 3, "overfull": 0 }

Códigos de salida:
    0 — acta generada (los `Overfull \\hbox` se reportan, no fallan)
    1 — no se pudo leer/escribir o pdflatex no produjo un PDF válido
    3 — datos inválidos (CSV sin columnas, cédula duplicada, semana < 1)
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from execution.descargar_resultados import (  # noqa: E402
    _compilar_pdf,
    latex_acta,
    leer_lista,
    normalizar_cedula,
)

RESULTADOS_POR_DEFECTO = RAIZ / "cursos" / "CYBERSEGURIDAD" / "evaluaciones" / "resultados"
COLUMNAS = (
    "grupo",
    "cedula",
    "nombre",
    "aciertos",
    "total",
    "nota_recalculada",
    "enviado_en",
    "estado",
)

EXIT_OK = 0
EXIT_IO = 1
EXIT_DATOS = 3


def slug_semana(semana: int) -> tuple[str, str]:
    """Devuelve (carpeta, nombre_base) para la semana indicada."""
    if not isinstance(semana, int) or isinstance(semana, bool) or semana < 1:
        raise ValueError(f"semana inválida: {semana!r}; debe ser un entero >= 1")
    numero = f"{semana:02d}"
    return f"SEMANA_{numero}", f"acta_semana_{numero}"


def seleccionar_actas(carpeta: Path) -> list[Path]:
    """Los `acta_*.csv` de la carpeta, ordenados; nunca `actas.csv`."""
    if not carpeta.is_dir():
        raise ValueError(f"no existe la carpeta de resultados: {carpeta}")
    rutas = sorted(p for p in carpeta.glob("acta_*.csv") if p.is_file())
    if not rutas:
        raise ValueError(f"no hay actas en {carpeta}")
    return rutas


def leer_acta(ruta: Path) -> list[dict]:
    """Filas del acta con los tipos que espera `latex_acta`."""
    with ruta.open(newline="", encoding="utf-8") as fh:
        lector = csv.DictReader(fh)
        faltan = [c for c in COLUMNAS if c not in (lector.fieldnames or [])]
        if faltan:
            raise ValueError(f"{ruta.name}: faltan columnas {', '.join(faltan)}")
        filas = []
        for numero, fila in enumerate(lector, start=2):
            try:
                grupo = int(str(fila["grupo"]).strip())
                aciertos = int(str(fila["aciertos"]).strip())
                total = int(str(fila["total"]).strip())
                nota = float(str(fila["nota_recalculada"]).strip())
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{ruta.name}:{numero}: valor no numérico ({exc})") from exc
            if grupo < 1 or total < 1 or aciertos < 0 or aciertos > total:
                raise ValueError(f"{ruta.name}:{numero}: grupo/aciertos fuera de rango")
            filas.append(
                {
                    "grupo": grupo,
                    "cedula": normalizar_cedula(str(fila["cedula"])),
                    "nombre": str(fila.get("nombre") or ""),
                    "aciertos": aciertos,
                    "total": total,
                    "nota_recalculada": nota,
                    "enviado_en": str(fila.get("enviado_en") or ""),
                    "estado": str(fila.get("estado") or ""),
                    "justif_estado": str(fila.get("justificaciones") or "n/a"),
                    "avisos": str(fila.get("avisos") or ""),
                }
            )
    return filas


def consolidar(rutas: list[Path]) -> list[dict]:
    """Une las actas, ordena por (grupo, cédula) y rechaza cédulas repetidas."""
    registros: list[dict] = []
    for ruta in rutas:
        registros.extend(leer_acta(ruta))
    vistas: dict[str, str] = {}
    for r in registros:
        if r["cedula"] in vistas:
            raise ValueError(
                f"cédula duplicada {r['cedula']}: aparece en {vistas[r['cedula']]} "
                f"y en otro acta"
            )
        vistas[r["cedula"]] = r["nombre"] or "?"
    return sorted(registros, key=lambda r: (r["grupo"], r["cedula"]))


def faltantes(registros: list[dict], listas: list[Path]) -> tuple[int, list[dict]]:
    """(esperados, faltantes) a partir de las nóminas por grupo, si se pasaron."""
    if not listas:
        return 0, []
    esperados: dict[str, dict] = {}
    for ruta in listas:
        filas, problemas = leer_lista(ruta)
        if problemas:
            raise ValueError(f"{ruta.name}: {'; '.join(problemas)}")
        for fila in filas:
            cedula = normalizar_cedula(fila["cedula"])
            if cedula in esperados:
                raise ValueError(f"cédula duplicada en las nóminas: {cedula}")
            esperados[cedula] = fila
    entregadas = {r["cedula"] for r in registros}
    fuera = [
        {"cedula": c, "nombre": f["nombre"], "grupo": f.get("grupo")}
        for c, f in esperados.items()
        if c not in entregadas
    ]
    return len(esperados), sorted(fuera, key=lambda f: (f.get("grupo") or 0, f["cedula"]))


def curso_desde(carpeta: Path) -> str:
    """`cursos/<X>/evaluaciones/resultados` -> X; si no encaja, `Curso`."""
    partes = carpeta.resolve().parts
    if "cursos" in partes:
        indice = partes.index("cursos")
        if indice + 1 < len(partes):
            return partes[indice + 1]
    return "Curso"


def construir(registros: list[dict], *, curso: str, semana: int, esperados: int,
              ausentes: list[dict]) -> str:
    if not registros:
        raise ValueError("no hay entregas que consolidar")
    cobertura = {"esperados": esperados, "faltantes": ausentes} if esperados else None
    return latex_acta(
        registros,
        titulo=f"Semana {semana:02d} — cuestionarios por rol",
        curso=curso,
        cuestionario=f"semana_{semana:02d}",
        fecha=max(r["enviado_en"] for r in registros),
        grupos=max([r["grupo"] for r in registros] + [f.get("grupo") or 0 for f in ausentes]),
        cobertura=cobertura,
    )


def _contar_overfull(trabajo: str) -> list[str]:
    log = RAIZ / ".tmp" / "latex_build" / trabajo / f"{trabajo}.log"
    if not log.is_file():
        return []
    texto = log.read_text(encoding="utf-8", errors="ignore")
    return [ln.strip() for ln in texto.splitlines() if "Overfull \\hbox" in ln]


def main() -> int:
    parser = argparse.ArgumentParser(description="Consolida las actas de una semana.")
    parser.add_argument("--semana", type=int, required=True, help="Número de semana (>= 1).")
    parser.add_argument("--actas-dir", default=str(RESULTADOS_POR_DEFECTO),
                        help="Carpeta con los acta_*.csv por grupo.")
    parser.add_argument("--lista", action="append", default=[], metavar="CSV",
                        help="Nómina por grupo (repetible) para listar faltantes.")
    parser.add_argument("--salida", default=None,
                        help="Carpeta destino (por defecto <actas-dir>/SEMANA_NN).")
    parser.add_argument("--curso", default=None, help="Nombre del curso en el acta.")
    parser.add_argument("--sin-pdf", action="store_true", help="Solo el .tex.")
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    args = parser.parse_args()

    def fallar(code: int, mensaje: str) -> int:
        salida = {"status": "error", "code": code, "message": mensaje}
        print(json.dumps(salida, ensure_ascii=False) if args.json else f"error: {mensaje}")
        return code

    try:
        carpeta, base = slug_semana(args.semana)
    except ValueError as exc:
        return fallar(EXIT_DATOS, str(exc))

    actas_dir = Path(args.actas_dir)
    if not actas_dir.is_absolute():
        actas_dir = RAIZ / actas_dir
    destino = Path(args.salida) if args.salida else actas_dir / carpeta
    if not destino.is_absolute():
        destino = RAIZ / destino

    try:
        rutas = seleccionar_actas(actas_dir)
        registros = consolidar(rutas)
        esperados, ausentes = faltantes(registros, [Path(p) for p in args.lista])
        curso = args.curso or curso_desde(actas_dir)
        latex = construir(registros, curso=curso, semana=args.semana,
                          esperados=esperados, ausentes=ausentes)
    except ValueError as exc:
        return fallar(EXIT_DATOS, str(exc))

    ruta_tex = destino / f"{base}.tex"
    ruta_pdf = destino / f"{base}.pdf"
    try:
        destino.mkdir(parents=True, exist_ok=True)
        ruta_tex.write_text(latex, encoding="utf-8")
    except OSError as exc:
        return fallar(EXIT_IO, f"no se pudo escribir el .tex: {exc}")

    if not args.sin_pdf:
        ok, error = _compilar_pdf(latex, ruta_pdf, base)
        if not ok:
            return fallar(EXIT_IO, f"pdflatex: {error}")
        if not ruta_pdf.is_file() or ruta_pdf.stat().st_size < 2048:
            return fallar(EXIT_IO, f"el PDF es sospechosamente pequeño: {ruta_pdf}")

    overfull = [] if args.sin_pdf else _contar_overfull(base)
    por_grupo: dict[str, int] = {}
    for r in registros:
        por_grupo[str(r["grupo"])] = por_grupo.get(str(r["grupo"]), 0) + 1
    salida = {
        "status": "ok",
        "code": EXIT_OK,
        "semana": args.semana,
        "acta_tex": str(ruta_tex),
        "acta_pdf": None if args.sin_pdf else str(ruta_pdf),
        "entregas": len(registros),
        "grupos": max(r["grupo"] for r in registros),
        "por_grupo": dict(sorted(por_grupo.items(), key=lambda kv: int(kv[0]))),
        "faltantes": ausentes,
        "a_revisar": sum(1 for r in registros if r["estado"] != "ok"),
        "overfull": len(overfull),
    }
    if args.json:
        print(json.dumps(salida, ensure_ascii=False, indent=2))
    else:
        print(f"Acta de la semana {args.semana:02d} — {len(registros)} entrega(s)")
        print(f"  TEX: {ruta_tex}")
        if salida["acta_pdf"]:
            print(f"  PDF: {ruta_pdf}")
        print("  por grupo: " + " · ".join(f"G{g}:{n}" for g, n in salida["por_grupo"].items()))
        if ausentes:
            print(f"  sin entrega: {len(ausentes)} de {esperados}")
            for f in ausentes:
                print(f"    G{f.get('grupo') or '?'} {f['cedula']} {f['nombre']}")
        if overfull:
            print(f"  aviso: {len(overfull)} Overfull \\hbox (cosmético)")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
