#!/usr/bin/env python3
"""
calificaciones_inasistencia.py — Califica ausencias decididas por el docente (Layer 3).

El acta de un cuestionario se arma con lo que el Worker archivó: si un alumno no
envió, aparece solo en la caja de «Sin entrega» y no tiene nota. Cuando el
docente decide dar 0 a quien no presentó y no justificó, esa decisión es parte
del acta, pero **no se escribe a mano en el CSV ni en el PDF**: se describe en un
YAML y este módulo lo convierte en filas con el mismo contrato que las entregas.

La regla vive aquí, no en el chat ni en la directiva: mismo descriptor + mismas
actas + misma nómina → mismas filas, siempre. El módulo no descarga nada, no
compila nada y no decide quién merece 0: solo valida que la decisión sea
coherente con lo que sí pasó.

Uso:
    from execution.calificaciones_inasistencia import incorporar
    registros, meta = incorporar(registros, ausentes, ruta_yaml)

Descriptor (YAML):
    fecha_decision: 2026-11-22
    total_preguntas: 10
    motivo: "Sin entrega; no justificó su ausencia; sin recuperación"
    referencia: Sessions/2026-11-22_cierre_evaluacion_1_ciberseguridad.md
    calificaciones:
      - {cedula: V-90000001, nombre: AUSENTE-1, grupo: 4, nota: 0.0}

Errores: ValueError con el motivo. Nunca se devuelve una fila dudosa.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

import yaml

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from execution.descargar_resultados import ESTADO_SIN_ENTREGA, normalizar_cedula  # noqa: E402

CLAVES_PERMITIDAS = {
    "fecha_decision", "total_preguntas", "motivo", "referencia", "calificaciones",
}
CLAVES_OBLIGATORIAS = {"fecha_decision", "total_preguntas", "motivo", "calificaciones"}
CLAVES_ITEM = {"cedula", "nombre", "grupo", "nota"}


def _entero(valor: object, nombre: str) -> int:
    if isinstance(valor, bool):
        raise ValueError(f"{nombre} debe ser un entero, no un booleano")
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{nombre} debe ser un entero: {valor!r}") from exc


def leer_descriptor(ruta: Path) -> dict:
    """Lee y valida el YAML de decisión sin cruzarlo todavía con las actas."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise ValueError(f"no existe el descriptor de inasistencias: {ruta}")
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"{ruta.name}: YAML inválido ({exc})") from exc
    if not isinstance(datos, dict):
        raise ValueError(f"{ruta.name}: el descriptor debe ser un mapa YAML")

    desconocidas = sorted(set(datos) - CLAVES_PERMITIDAS)
    if desconocidas:
        raise ValueError(f"{ruta.name}: claves desconocidas: {', '.join(desconocidas)}")
    faltan = sorted(CLAVES_OBLIGATORIAS - set(datos))
    if faltan:
        raise ValueError(f"{ruta.name}: faltan claves: {', '.join(faltan)}")

    fecha = str(datos["fecha_decision"]).strip()
    try:
        date.fromisoformat(fecha)
    except ValueError as exc:
        raise ValueError(f"{ruta.name}: fecha_decision debe ser ISO (YYYY-MM-DD)") from exc

    total = _entero(datos["total_preguntas"], "total_preguntas")
    if total < 1:
        raise ValueError(f"{ruta.name}: total_preguntas debe ser >= 1")

    motivo = str(datos["motivo"]).strip()
    if not motivo:
        raise ValueError(f"{ruta.name}: el motivo no puede estar vacío")

    items = datos["calificaciones"]
    if not isinstance(items, list) or not items:
        raise ValueError(f"{ruta.name}: calificaciones debe ser una lista no vacía")
    normalizados = []
    for numero, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"{ruta.name}: calificación {numero} no es un mapa")
        extra = sorted(set(item) - CLAVES_ITEM)
        if extra:
            raise ValueError(f"{ruta.name}: calificación {numero}: claves desconocidas: "
                             + ", ".join(extra))
        falta = sorted(CLAVES_ITEM - set(item))
        if falta:
            raise ValueError(f"{ruta.name}: calificación {numero}: faltan claves: "
                             + ", ".join(falta))
        cedula = normalizar_cedula(item["cedula"])
        if cedula is None:
            raise ValueError(f"{ruta.name}: calificación {numero}: cédula inválida")
        nombre = str(item["nombre"]).strip()
        if not nombre:
            raise ValueError(f"{ruta.name}: calificación {numero}: nombre vacío")
        grupo = _entero(item["grupo"], f"calificación {numero}.grupo")
        if grupo < 1:
            raise ValueError(f"{ruta.name}: calificación {numero}: grupo debe ser >= 1")
        try:
            nota = float(str(item["nota"]).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{ruta.name}: calificación {numero}: nota no numérica") from exc
        if not 0.0 <= nota <= 10.0:
            raise ValueError(f"{ruta.name}: calificación {numero}: nota fuera de 0..10")
        normalizados.append({"cedula": cedula, "nombre": nombre, "grupo": grupo, "nota": nota})

    vistas: set[str] = set()
    for item in normalizados:
        if item["cedula"] in vistas:
            raise ValueError(f"{ruta.name}: cédula repetida en el descriptor: {item['cedula']}")
        vistas.add(item["cedula"])

    return {
        "ruta": str(ruta),
        "fecha_decision": fecha,
        "total_preguntas": total,
        "motivo": motivo,
        "referencia": str(datos.get("referencia") or "").strip(),
        "calificaciones": normalizados,
    }


def filas_para(registros: list[dict], ausentes: list[dict], descriptor: dict) -> list[dict]:
    """Convierte la decisión en filas del acta, cruzándola con entregas y nómina."""
    entregadas = {r["cedula"]: r for r in registros}
    ausentes_por_cedula = {a["cedula"]: a for a in ausentes}
    totales = {int(r["total"]) for r in registros}
    if len(totales) > 1:
        raise ValueError(f"las actas mezclan totales de preguntas: {sorted(totales)}")
    if totales and totales != {descriptor["total_preguntas"]}:
        raise ValueError(
            f"total_preguntas={descriptor['total_preguntas']} no coincide con el de las "
            f"entregas ({sorted(totales)[0]})"
        )

    aviso = descriptor["motivo"] + f" (decisión {descriptor['fecha_decision']}"
    if descriptor["referencia"]:
        aviso += "; " + descriptor["referencia"]
    aviso += ")"

    filas = []
    for item in descriptor["calificaciones"]:
        cedula = item["cedula"]
        if cedula in entregadas:
            raise ValueError(
                f"{cedula} ya entregó el cuestionario; no se puede calificar una ausencia"
            )
        ausente = ausentes_por_cedula.get(cedula)
        if ausente is None:
            raise ValueError(f"{cedula} no figura como faltante en la nómina")
        if ausente.get("grupo") is not None and item["grupo"] != ausente["grupo"]:
            raise ValueError(
                f"{cedula}: el descriptor dice grupo {item['grupo']} y la nómina "
                f"grupo {ausente['grupo']}"
            )
        filas.append(
            {
                "grupo": item["grupo"],
                "cedula": cedula,
                "nombre": item["nombre"],
                "aciertos": 0,
                "total": descriptor["total_preguntas"],
                "nota_recalculada": item["nota"],
                "enviado_en": "",
                "estado": ESTADO_SIN_ENTREGA,
                "justif_estado": "n/a",
                "avisos": aviso,
            }
        )
    return sorted(filas, key=lambda r: (r["grupo"], r["cedula"]))


def incorporar(registros: list[dict], ausentes: list[dict], ruta: Path) -> tuple[list[dict], dict]:
    """Devuelve (registros con las filas nuevas, metadata de la decisión)."""
    descriptor = leer_descriptor(ruta)
    nuevas = filas_para(registros, ausentes, descriptor)
    finales = sorted(list(registros) + nuevas, key=lambda r: (r["grupo"], r["cedula"]))
    meta = {
        "ruta": descriptor["ruta"],
        "fecha_decision": descriptor["fecha_decision"],
        "motivo": descriptor["motivo"],
        "referencia": descriptor["referencia"],
        "total_preguntas": descriptor["total_preguntas"],
        "calificados": nuevas,
    }
    return finales, meta
