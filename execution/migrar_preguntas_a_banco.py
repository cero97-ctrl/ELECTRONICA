#!/usr/bin/env python3
"""
migrar_preguntas_a_banco.py — Saca los enunciados de los controles a un banco privado

Los descriptores `cursos/*/curso.yaml` están versionados en un repo público. Un
`enunciado` ahí es una fuga: cualquiera con el enlace lee el examen antes de
rendirlo. Este script mueve los enunciados de `controles[].preguntas[]` a
`evaluaciones/banco_preguntas.yaml` (ignorado por git) y deja en el descriptor
solo la posición: fase, puntaje y, si existe, el tema.

La migración es textual, no un round-trip de YAML: los descriptores tienen
comentarios que `yaml.safe_dump` perdería. Se localiza el bloque `controles:` y
se borran las líneas del escalar `enunciado` (en línea, plegado `>-` o en bloque),
sean del tipo `- enunciado: ...` o de la clave `enunciado:` dentro de un item que
empieza con otra clave (`- tema: ...`).

La verificación es la que importa: tras la cirugía se compone de nuevo el
descriptor público con la variante recién creada y el resultado debe ser
IDÉNTICO al original, pregunta por pregunta. Así el script no puede "migrar"
perdiendo texto o emparejando enunciados con puntajes equivocados: falla.

Garantías:
  · Idempotente: si el descriptor ya no tiene enunciados, no hace nada.
  · No sobrescribe un banco existente sin `--forzar`.
  · `--dry-run` no escribe nada y muestra el plan.

Uso:
    python3 execution/migrar_preguntas_a_banco.py --curso cursos/CYBERSEGURIDAD/curso.yaml --dry-run
    python3 execution/migrar_preguntas_a_banco.py --curso cursos/LABORATORIO_I_FISICA/curso.yaml \\
        --curso cursos/LABORATORIO_II_FISICA/curso.yaml

Códigos de salida:
    0 — migrado (o ya estaba migrado)
    1 — argumentos inválidos
    2 — descriptor ilegible
    3 — la verificación falló (no se escribió nada)
    4 — el banco ya existe y falta --forzar
    5 — error de escritura en disco
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import generar_material_curso as gen  # noqa: E402

# `controles:` como clave de primer nivel y el inicio de la siguiente clave.
_RE_INICIO_CONTROLES = re.compile(r"^controles:\s*(?:#.*)?$")
_RE_CLAVE_RAIZ = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*:")
# `enunciado` con o sin guion de item delante: `- enunciado:` o `enunciado:`.
_RE_ENUNCIADO = re.compile(r"^(\s*)(- )?enunciado:")


def _indentacion(linea: str) -> int:
    """Número de espacios iniciales de una línea."""
    return len(linea) - len(linea.lstrip(" "))


def _bloque_controles(lineas: list[str]) -> tuple[int, int]:
    """Devuelve el rango ``[inicio, fin)`` de líneas del bloque ``controles:``.

    Args:
        lineas: Contenido del descriptor partido por líneas.

    Returns:
        Índices de la línea de la clave y de la primera clave raíz posterior.

    Raises:
        ValueError: Si el descriptor no declara `controles:` o lo declara vacío
            de forma ambigua.
    """
    inicio = next(
        (i for i, linea in enumerate(lineas) if _RE_INICIO_CONTROLES.match(linea)),
        None,
    )
    if inicio is None:
        raise ValueError("el descriptor no declara 'controles:' como clave de primer nivel")
    fin = next(
        (
            j
            for j in range(inicio + 1, len(lineas))
            if _RE_CLAVE_RAIZ.match(lineas[j])
        ),
        len(lineas),
    )
    return inicio, fin


def _rangos_enunciado(lineas: list[str], inicio: int, fin: int) -> list[dict[str, Any]]:
    """Localiza las líneas ocupadas por cada escalar ``enunciado``.

    Un escalar puede ocupar una línea (`enunciado: texto`) o varias (plegado o
    literal): las continuaciones están indentadas más que la clave y terminan en
    la primera línea con indentación menor o igual, que es donde empieza la
    siguiente clave del mismo mapa.

    Hay dos formas de item y se tratan distinto al borrar:

    · ``- enunciado: ...`` — el guion vive en la misma línea que la clave. Si se
      borra la línea entera desaparece el item y su mapa se fusiona con el
      anterior (el YAML sigue siendo válido y silenciosamente pierde preguntas).
      Por eso el guion se transfiere a la primera clave hermana.
    · ``enunciado: ...`` dentro de un item que empezó con ``- tema: ...`` — la
      línea se borra entera.

    Args:
        lineas: Contenido del descriptor partido por líneas.
        inicio: Índice de la línea ``controles:``.
        fin: Índice de la primera clave raíz posterior.

    Returns:
        Lista de planes con ``primera``, ``ultima``, ``guion_indent``,
        ``clave_indent`` y ``tiene_guion``, en orden de aparición.
    """
    planes: list[dict[str, Any]] = []
    i = inicio + 1
    while i < fin:
        coincidencia = _RE_ENUNCIADO.match(lineas[i])
        if not coincidencia:
            i += 1
            continue
        tiene_guion = coincidencia.group(2) is not None
        clave_indent = len(coincidencia.group(1)) + (2 if tiene_guion else 0)
        j = i + 1
        while j < fin:
            if lineas[j].strip() and _indentacion(lineas[j]) <= clave_indent:
                break
            j += 1
        planes.append(
            {
                "primera": i,
                "ultima": j,
                "guion_indent": len(coincidencia.group(1)),
                "clave_indent": clave_indent,
                "tiene_guion": tiene_guion,
            }
        )
        i = j
    return planes


def _descriptor_de_banco(datos: dict[str, Any], fecha: str) -> dict[str, Any]:
    """Construye la variante 1 del banco a partir de los controles actuales.

    Los enunciados ya se publicaron (están en el historial de git), así que la
    variante nace `comprometida`: aplicarla exige una confirmación explícita. El
    docente crea después una variante nueva y la marca `utilizable`.

    Args:
        datos: Descriptor con los enunciados todavía dentro.
        fecha: Fecha de creación de la variante (ISO).

    Returns:
        Banco con `meta` y una única variante.
    """
    controles = []
    for control in datos.get("controles") or []:
        preguntas = []
        for pregunta in control.get("preguntas") or []:
            fuente = {"enunciado": pregunta["enunciado"]}
            if pregunta.get("criterio"):
                fuente["criterio"] = pregunta["criterio"]
            preguntas.append(fuente)
        controles.append({"fase": control.get("fase"), "preguntas": preguntas})
    return {
        "meta": {
            "curso": datos["meta"]["codigo"],
            "escala": (datos.get("evaluacion") or {}).get("escala", 10),
            "aviso": (
                "BANCO PRIVADO — no versionar. Los enunciados de los controles viven "
                "aquí y en ningún otro fichero del repo. La variante 1 está "
                "'comprometida' (se publicó antes de esta migración); crear una "
                "variante nueva y marcarla 'utilizable' antes de aplicar un control."
            ),
        },
        "variantes": [
            {
                "numero": 1,
                "estado": "comprometida",
                "creada": fecha,
                "origen": "curso.yaml (enunciados publicados antes de la migración)",
                "controles": controles,
            }
        ],
    }


def _volcar_banco(banco: dict[str, Any]) -> str:
    """Serializa el banco con cabecera de advertencia y sin alterar el texto."""
    cabecera = (
        "# BANCO PRIVADO DE PREGUNTAS — NO VERSIONAR\n"
        "# Este fichero está en .gitignore a propósito: contiene los enunciados de\n"
        "# los controles. `curso.yaml` es público y solo declara fase, puntaje y tema.\n"
        "# Generado por execution/migrar_preguntas_a_banco.py; editarlo a mano es\n"
        "# correcto (es el sitio donde se escriben las variantes nuevas).\n"
        "#\n"
        "# estados: utilizable | borrador | comprometida\n"
    )
    cuerpo = yaml.safe_dump(
        banco,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=1000,
    )
    vuelta = yaml.safe_load(cuerpo)
    if vuelta != banco:
        raise ValueError("el YAML serializado no reproduce el banco (revisar el volcado)")
    return cabecera + cuerpo


def migrar(ruta: Path, ruta_banco: Path, dry_run: bool, forzar: bool, fecha: str) -> dict[str, Any]:
    """Migra un descriptor a su banco privado, verificando la equivalencia.

    Args:
        ruta: Ruta al `curso.yaml`.
        ruta_banco: Ruta destino del `banco_preguntas.yaml`.
        dry_run: Si es True no escribe nada.
        forzar: Sobrescribe un banco existente.
        fecha: Fecha ISO de creación de la variante.

    Returns:
        Informe con el resultado de la migración.

    Raises:
        ValueError: Si el banco existe sin `--forzar` o si la verificación falla.
        OSError: Si no se puede leer o escribir.
    """
    texto = ruta.read_text(encoding="utf-8")
    datos = gen.cargar_descriptor(ruta)
    lineas = texto.splitlines(keepends=True)
    inicio, fin = _bloque_controles(lineas)
    rangos = _rangos_enunciado(lineas, inicio, fin)

    originales = [
        pregunta
        for control in datos.get("controles") or []
        for pregunta in control.get("preguntas") or []
    ]
    if not rangos:
        return {"curso": datos["meta"]["codigo"], "estado": "ya_migrado", "enunciados": 0}
    if len(rangos) != len(originales):
        raise ValueError(
            f"{ruta}: se localizaron {len(rangos)} líneas 'enunciado' y el YAML declaró "
            f"{len(originales)} preguntas; la cirugía textual no es segura"
        )

    banco = _descriptor_de_banco(datos, fecha)
    variante = banco["variantes"][0]

    nuevas = list(lineas)
    for plan in reversed(rangos):
        if plan["tiene_guion"]:
            destino = plan["ultima"]
            if destino >= fin or not nuevas[destino].strip() or _indentacion(nuevas[destino]) != plan["clave_indent"]:
                raise ValueError(
                    f"{ruta}: la pregunta de la línea {plan['primera'] + 1} no tiene "
                    "ninguna clave hermana a la que transferir el guion del item"
                )
            nuevas[destino] = " " * plan["guion_indent"] + "- " + nuevas[destino][plan["clave_indent"]:]
        del nuevas[plan["primera"]:plan["ultima"]]
    texto_nuevo = "".join(nuevas)

    # Verificación fuerte: recomponer el descriptor migrado con la variante
    # recién creada debe devolver exactamente los controles originales.
    datos_migrados = yaml.safe_load(texto_nuevo)
    if not isinstance(datos_migrados, dict):
        raise ValueError(f"{ruta}: el descriptor migrado no es un mapa YAML")
    recompuestos = gen.componer_controles(datos_migrados, variante)
    if recompuestos != datos.get("controles"):
        raise ValueError(
            f"{ruta}: los controles recompuestos no coinciden con los originales "
            "(la cirugía textual movió texto de sitio); no se escribió nada"
        )
    problemas = gen.validar(datos_migrados) + gen.validar_preguntas(recompuestos)
    if problemas:
        raise ValueError(f"{ruta}: el descriptor migrado no valida: {'; '.join(problemas)}")
    fugas = [
        i
        for control in datos_migrados.get("controles") or []
        for i, pregunta in enumerate(control.get("preguntas") or [], 1)
        if "enunciado" in pregunta
    ]
    if fugas:
        raise ValueError(f"{ruta}: quedaron enunciados en el descriptor (preguntas {fugas})")

    if dry_run:
        return {
            "curso": datos["meta"]["codigo"],
            "estado": "planificado",
            "enunciados": len(rangos),
            "banco": str(ruta_banco),
            "lineas_eliminadas": sum(p["ultima"] - p["primera"] for p in rangos),
        }
    if ruta_banco.exists() and not forzar:
        raise ValueError(
            f"{ruta_banco} ya existe; no se sobrescribe un banco de preguntas sin --forzar"
        )

    ruta_banco.parent.mkdir(parents=True, exist_ok=True)
    ruta_banco.write_text(_volcar_banco(banco), encoding="utf-8")
    ruta.write_text(texto_nuevo, encoding="utf-8")
    return {
        "curso": datos["meta"]["codigo"],
        "estado": "migrado",
        "enunciados": len(rangos),
        "banco": str(ruta_banco),
        "variante": variante["numero"],
    }


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada de la migración."""
    parser = argparse.ArgumentParser(
        description="Mueve los enunciados de los controles a un banco privado ignorado por git."
    )
    parser.add_argument("--curso", action="append", required=True,
                        help="Ruta a un curso.yaml (repetible)")
    parser.add_argument("--banco", default=None,
                        help="Ruta del banco (solo con un --curso; por defecto "
                             "evaluaciones/banco_preguntas.yaml junto al descriptor)")
    parser.add_argument("--dry-run", action="store_true", help="No escribe nada")
    parser.add_argument("--forzar", action="store_true", help="Sobrescribe un banco existente")
    parser.add_argument("--fecha", default=date.today().isoformat(),
                        help="Fecha de creación de la variante (ISO; por defecto, hoy)")
    parser.add_argument("--json", action="store_true", help="Emite un único objeto JSON")
    args = parser.parse_args(argv)

    if args.banco and len(args.curso) > 1:
        print("[error] --banco solo se admite con un único --curso", file=sys.stderr)
        return 1

    informes = []
    for curso in args.curso:
        ruta = Path(curso).resolve()
        ruta_banco = (
            Path(args.banco).resolve()
            if args.banco
            else ruta.parent / "evaluaciones" / gen.BANCO_PREGUNTAS
        )
        try:
            informes.append(migrar(ruta, ruta_banco, args.dry_run, args.forzar, args.fecha))
        except FileNotFoundError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 2
        except ValueError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 3 if "ya existe" not in str(exc) else 4
        except yaml.YAMLError as exc:
            print(f"[error] YAML inválido en {ruta}: {exc}", file=sys.stderr)
            return 2
        except OSError as exc:
            print(f"[error] escritura: {exc}", file=sys.stderr)
            return 5

    if args.json:
        print(json.dumps({"status": "ok", "cursos": informes}, ensure_ascii=False, indent=2))
    else:
        for informe in informes:
            print(
                f"  [{informe['estado']}] {informe['curso']}: "
                f"{informe['enunciados']} enunciados -> {informe['banco']}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
