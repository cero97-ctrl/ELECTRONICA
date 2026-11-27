#!/usr/bin/env python3
"""Capa 3: añade el recuadro de justificación a un cuestionario ya separado.

La instrucción vive en el Markdown (`**Justificación:** ...`) y la lista de
ítems en el front matter (`justificacion_items`), que es la única fuente de
verdad compartida por el HTML y el Worker. Este script no decide qué preguntas
son: por defecto toma todas las de la fuente y lo hace pasar por el mismo
validador (`md_a_html.cargar_clave`) que usan los dos.

Uso:
    python3 execution/agregar_justificaciones_web.py --fuente A.md --fuente B.md
    python3 execution/agregar_justificaciones_web.py --fuente A.md --check --json

Códigos: 0 ok · 3 fuente inválida · 4 E/S.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "execution"))
import md_a_html as M  # noqa: E402  (validador único de la fuente y la clave)

INSTRUCCION = (
    "Explica con tus propias palabras por qué elegiste esa opción, apoyándote "
    "en el enunciado y en los conceptos vistos en clase."
)
PREGUNTA = re.compile(r"(?m)^## Pregunta (\d+)\s*$")
OPCION = re.compile(r"^- [A-Z]\.\s")
FRONT = re.compile(r"\A---\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
CLAVE_FRONT = re.compile(r"^(justificacion_items|grupos):")
NUEVA = re.compile(r"^\*\*Justificaci[oó]n:\*\*\s*(.*)$")


class JustificacionError(Exception):
    def __init__(self, mensaje: str, code: int = 3):
        super().__init__(mensaje)
        self.code = code


def dividir_front(texto: str, requerido: bool = True) -> tuple[list[str], str]:
    match = FRONT.match(texto)
    if not match:
        if requerido:
            raise JustificacionError("la fuente no tiene front matter YAML válido")
        return [], texto
    return match.group(1).splitlines(), texto[match.end() :]


def numeros_de(cuerpo: str) -> list[int]:
    items = [int(n) for n in PREGUNTA.findall(cuerpo)]
    if not items:
        raise JustificacionError("no hay preguntas `## Pregunta N` en la fuente")
    if sorted(items) != list(range(1, len(items) + 1)):
        raise JustificacionError(f"numeración no consecutiva: {items}")
    return items


def actualizar_front(cabecera: list[str], items: list[int], grupos: int) -> list[str]:
    lineas = [linea for linea in cabecera if not CLAVE_FRONT.match(linea)]
    while lineas and not lineas[-1].strip():
        lineas.pop()
    lista = ", ".join(str(n) for n in items)
    lineas.append(f"justificacion_items: [{lista}]")
    lineas.append(f"grupos: {grupos}")
    return lineas


def insertar(
    cuerpo: str, items: list[int], instruccion: str, forzar: bool = False
) -> str:
    """Inserta/reemplaza la instrucción después de la última opción de cada ítem."""
    partes = PREGUNTA.split(cuerpo)
    if len(partes) < 3:
        raise JustificacionError("no se pudo partir el cuestionario en preguntas")
    salida = [partes[0]]
    objetivo = set(items)
    for indice in range(1, len(partes), 2):
        numero = int(partes[indice])
        bloque = partes[indice + 1]
        lineas = bloque.splitlines(keepends=True)
        encabezado = f"## Pregunta {numero}\n"
        if numero not in objetivo:
            salida.append(encabezado + "".join(lineas))
            continue

        existentes = [i for i, linea in enumerate(lineas) if NUEVA.match(linea)]
        if existentes and not forzar:
            salida.append(encabezado + "".join(lineas))
            continue

        ultima_opcion = None
        for i, linea in enumerate(lineas):
            if OPCION.match(linea):
                ultima_opcion = i
        if ultima_opcion is None:
            raise JustificacionError(
                f"pregunta {numero}: no hay opciones `- X.` donde anclar la instrucción"
            )

        ya_presente = bool(existentes)
        reemplazadas: list[str] = []
        for i, linea in enumerate(lineas):
            if NUEVA.match(linea):
                if i == existentes[0]:
                    salto = "\n" if linea.endswith("\n") else ""
                    reemplazadas.append(f"**Justificación:** {instruccion}{salto}")
                continue
            reemplazadas.append(linea)
            if i == ultima_opcion and not ya_presente:
                reemplazadas.append(f"**Justificación:** {instruccion}\n")
        salida.append(encabezado + "".join(reemplazadas))
    return "".join(salida)


def armar(fuente: Path, instruccion: str, forzar: bool) -> tuple[str, str, list[int]]:
    try:
        texto = fuente.read_text(encoding="utf-8")
    except OSError as exc:
        raise JustificacionError(f"no se pudo leer {fuente}: {exc}", 4) from exc
    respuestas = fuente.with_name(f"{fuente.stem}_respuestas.md")
    try:
        texto_resp = respuestas.read_text(encoding="utf-8")
    except OSError as exc:
        raise JustificacionError(f"no se pudo leer {respuestas}: {exc}", 4) from exc

    cabecera, cuerpo = dividir_front(texto)
    cab_resp, cuerpo_resp = dividir_front(texto_resp, requerido=False)
    items = numeros_de(cuerpo)
    if numeros_de(cuerpo_resp) != items:
        raise JustificacionError("la fuente y el solucionario tienen preguntas distintas")

    nueva_cabecera = "\n".join(actualizar_front(cabecera, items, 4))
    nueva_resp_cabecera = "\n".join(actualizar_front(cab_resp, items, 4))
    limpia = f"---\n{nueva_cabecera}\n---\n" + insertar(cuerpo, items, instruccion, forzar)
    solucionario = (
        f"---\n{nueva_resp_cabecera}\n---\n"
        + insertar(cuerpo_resp, items, instruccion, forzar)
    )
    return limpia, solucionario, items


def _validar_en_temporal(limpia: str, solucionario: str) -> None:
    with tempfile.TemporaryDirectory(dir=RAIZ / ".tmp") as temporal:
        tmp = Path(temporal)
        f = tmp / "fuente.md"
        r = tmp / "fuente_respuestas.md"
        f.write_text(limpia, encoding="utf-8")
        r.write_text(solucionario, encoding="utf-8")
        try:
            datos = M.cargar_clave(f, r)
        except (ValueError, FileNotFoundError) as exc:
            raise JustificacionError(f"el conversor rechazó el resultado: {exc}") from exc
        if datos["justificacion_items"] != numeros_de(limpia.split("---\n", 2)[-1]):
            raise JustificacionError("el conversor no recuperó todos los ítems")


def _escribir_atomico(ruta: Path, contenido: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fd, temporal = tempfile.mkstemp(dir=ruta.parent, prefix=f".{ruta.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as manejador:
            manejador.write(contenido)
        os.replace(temporal, ruta)
    except BaseException:
        if os.path.exists(temporal):
            os.unlink(temporal)
        raise


def procesar(fuente: Path, instruccion: str, forzar: bool, check: bool) -> dict:
    fuente = fuente.resolve()
    limpia, solucionario, items = armar(fuente, instruccion, forzar)
    _validar_en_temporal(limpia, solucionario)
    if not check:
        _escribir_atomico(fuente, limpia)
        _escribir_atomico(
            fuente.with_name(f"{fuente.stem}_respuestas.md"), solucionario
        )
    return {
        "fuente": str(fuente),
        "items": items,
        "instruccion": instruccion,
        "check": check,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fuente", action="append", required=True, help="Markdown a convertir (repetible).")
    parser.add_argument("--instruccion", default=INSTRUCCION, help="Texto de la instrucción.")
    parser.add_argument("--forzar", action="store_true", help="Reemplaza instrucciones previas.")
    parser.add_argument("--check", action="store_true", help="Valida sin escribir.")
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    args = parser.parse_args()

    try:
        informes = [
            procesar(Path(ruta), args.instruccion, args.forzar, args.check)
            for ruta in args.fuente
        ]
    except JustificacionError as exc:
        resultado = {"status": "error", "code": exc.code, "message": str(exc)}
        print(json.dumps(resultado, ensure_ascii=False, indent=2) if args.json else f"FALLA: {exc}", file=sys.stderr)
        return exc.code

    resultado = {"status": "ok", "code": 0, "fuentes": informes}
    print(json.dumps(resultado, ensure_ascii=False, indent=2) if args.json else f"Justificaciones listas en {len(informes)} fuente(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
