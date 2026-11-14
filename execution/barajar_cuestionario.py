#!/usr/bin/env python3
"""Capa 3: baraja las opciones de un cuestionario de forma determinista.

Motivo: dos de los cuatro cuestionarios salieron con la clave degenerada (Legal
`A A A A A A A A A A`, Púrpura `A B A A A A A A A A`). Un alumno que marque
siempre «A» saca 10/10 sin leer el examen, y ninguna validación lo detecta
porque la clave es formalmente válida. Barajar reparte la respuesta correcta
entre las cuatro letras sin cambiar ni una sola pregunta.

Determinista: la permutación de cada pregunta sale de
`random.Random(f"{semilla}:{numero}")`, con la semilla por defecto tomada del
nombre del archivo. El mismo archivo y la misma semilla producen siempre el
mismo resultado; no es una decisión del orquestador.

No reescribe el examen desde cero (eso perdería los `**Explanation:**`): opera
sobre las líneas del canónico y remapea también la letra de cada viñeta
`- A ✓` / `- B ✗`, porque si no, la variante docente explicaría la opción
equivocada. Se valida antes de escribir:

  - el conjunto de textos de opción de cada pregunta no cambia;
  - el texto de la respuesta correcta no cambia;
  - cada viñeta de explicación sigue apuntando al texto que explicaba.

Uso:
    python3 execution/barajar_cuestionario.py --canonico X_respuestas.md --dry-run --json
    python3 execution/barajar_cuestionario.py --canonico X_respuestas.md --forzar
    python3 execution/barajar_cuestionario.py --canonico X.md --semilla otra --salida Y.md

Códigos de salida: 0 ok · 1 error de E/S · 3 canónico inválido.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

EJECUCION = Path(__file__).resolve().parent
sys.path.insert(0, str(EJECUCION))
import md_a_html  # noqa: E402  (capa 3: el parser es la única definición del formato)

BLOQUE = re.compile(r"(?im)^##\s+(?:Question|Pregunta)\s+(\d+)\s*$")
VINETA = re.compile(r"^-\s+([A-Z])\s+([✓✗])")
LETRAS = "ABCDEFGH"


def _permutacion(semilla: str, numero: int, n: int) -> list[int]:
    """Permutación determinista de `n` posiciones para la pregunta `numero`."""
    rng = random.Random(f"{semilla}:{numero}")
    perm = list(range(n))
    rng.shuffle(perm)
    return perm


def _clave_degenerada(clave: dict[int, str]) -> bool:
    """True si una letra concentra más de la mitad de las respuestas."""
    if not clave:
        return False
    cuenta: dict[str, int] = {}
    for letra in clave.values():
        cuenta[letra] = cuenta.get(letra, 0) + 1
    return max(cuenta.values()) * 2 > len(clave)


def barajar(texto: str, semilla: str) -> tuple[str, dict]:
    """Devuelve `(texto_barajado, informe)`; no escribe en disco."""
    lineas = texto.splitlines()
    cabeceras = [(i, int(m.group(1))) for i, l in enumerate(lineas) if (m := BLOQUE.match(l))]
    if not cabeceras:
        raise ValueError("el canónico no tiene preguntas `## Question N` / `## Pregunta N`")

    original = md_a_html._parsear_respuestas(texto)
    if not original:
        raise ValueError("no se pudo parsear ninguna pregunta del canónico")

    cambios = 0
    for pos, (inicio, numero) in enumerate(cabeceras):
        fin = cabeceras[pos + 1][0] if pos + 1 < len(cabeceras) else len(lineas)
        opciones = []
        respuesta_idx = None
        respuesta_letra = None
        for i in range(inicio + 1, fin):
            if respuesta_idx is None:
                m = md_a_html.OPCION.match(lineas[i])
                if m:
                    opciones.append((i, m.group(1).upper(), m.group(2).strip()))
                    continue
                m = md_a_html.RESPUESTA.match(lineas[i])
                if m:
                    respuesta_idx = i
                    respuesta_letra = m.group(1).upper()
                    continue
        if len(opciones) < 2:
            raise ValueError(f"pregunta {numero}: menos de dos opciones")
        if respuesta_idx is None or respuesta_letra is None:
            raise ValueError(f"pregunta {numero}: no trae `**Answer:**`")

        letras = [o[1] for o in opciones]
        textos = [o[2] for o in opciones]
        if respuesta_letra not in letras:
            raise ValueError(
                f"pregunta {numero}: la respuesta {respuesta_letra} no es una opción"
            )
        i_ans = letras.index(respuesta_letra)
        perm = _permutacion(semilla, numero, len(opciones))
        nuevas_letras = list(LETRAS[: len(opciones)])

        for j, (indice, _, _) in enumerate(opciones):
            lineas[indice] = f"- {nuevas_letras[j]}. {textos[perm[j]]}"
        nueva_ans = nuevas_letras[perm.index(i_ans)]
        lineas[respuesta_idx] = f"**Answer:** {nueva_ans}. {textos[i_ans]}"

        for i in range(respuesta_idx + 1, fin):
            m = VINETA.match(lineas[i])
            if not m or m.group(1) not in letras:
                continue
            i_vineta = letras.index(m.group(1))
            nueva = nuevas_letras[perm.index(i_vineta)]
            lineas[i] = f"- {nueva} {m.group(2)}" + lineas[i][m.end():]
        cambios += 1

    barajado = "\n".join(lineas)
    if texto.endswith("\n"):
        barajado += "\n"

    _verificar(original, barajado, semilla)
    return barajado, {
        "preguntas_barajadas": cambios,
        "semilla": semilla,
        "clave_antes": _clave(original),
        "clave_despues": _clave(md_a_html._parsear_respuestas(barajado)),
    }


def _clave(preguntas: list[dict]) -> dict[int, str]:
    return {p["numero"]: p["respuesta"] for p in preguntas if p.get("respuesta")}


def _verificar(original: list[dict], barajado: str, semilla: str) -> None:
    """El barajado no puede cambiar preguntas: solo el orden de sus opciones."""
    nuevo = md_a_html._parsear_respuestas(barajado)
    if len(nuevo) != len(original):
        raise ValueError(
            f"el barajado cambió el número de preguntas: {len(original)} -> {len(nuevo)}"
        )
    for antes, despues in zip(original, nuevo):
        numero = antes["numero"]
        if antes["numero"] != despues["numero"]:
            raise ValueError(f"se perdió la numeración: {antes['numero']} -> {despues['numero']}")
        if md_a_html._normalizar_texto(antes["enunciado"]) != md_a_html._normalizar_texto(
            despues["enunciado"]
        ):
            raise ValueError(f"pregunta {numero}: el enunciado cambió al barajar")
        if sorted(md_a_html._normalizar_texto(o["texto"]) for o in antes["opciones"]) != sorted(
            md_a_html._normalizar_texto(o["texto"]) for o in despues["opciones"]
        ):
            raise ValueError(f"pregunta {numero}: el conjunto de opciones cambió")
        texto_antes = next(
            (o["texto"] for o in antes["opciones"] if o["letra"] == antes["respuesta"]), None
        )
        texto_despues = next(
            (o["texto"] for o in despues["opciones"] if o["letra"] == despues["respuesta"]), None
        )
        if texto_antes != texto_despues:
            raise ValueError(
                f"pregunta {numero}: la respuesta correcta apunta a otro texto "
                f"({texto_antes!r} -> {texto_despues!r})"
            )
        if md_a_html._normalizar_texto(antes.get("justificacion", "")) != md_a_html._normalizar_texto(
            despues.get("justificacion", "")
        ):
            raise ValueError(f"pregunta {numero}: la justificación cambió al barajar")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Baraja opciones de un cuestionario canónico de forma determinista."
    )
    parser.add_argument("--canonico", required=True, help="Markdown con `**Answer:**`.")
    parser.add_argument("--salida", default=None, help="Destino (por defecto, in-place).")
    parser.add_argument("--semilla", default=None, help="Semilla (por defecto, el nombre del archivo).")
    parser.add_argument("--forzar", action="store_true", help="Sobrescribe la salida existente.")
    parser.add_argument("--dry-run", action="store_true", help="Valida sin escribir.")
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    args = parser.parse_args()

    ruta = Path(args.canonico).resolve()
    destino = Path(args.salida).resolve() if args.salida else ruta
    semilla = args.semilla or ruta.stem

    try:
        texto = ruta.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        barajado, informe = barajar(texto, semilla)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    if destino != ruta and destino.exists() and not args.forzar:
        print(f"error: {destino} existe; usar --forzar", file=sys.stderr)
        return 3

    if not args.dry_run:
        try:
            destino.write_text(barajado, encoding="utf-8")
        except OSError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    resumen = {
        "canonico": str(ruta),
        "salida": str(destino),
        "dry_run": args.dry_run,
        **informe,
        "clave_antes_degenerada": _clave_degenerada(informe["clave_antes"]),
        "clave_despues_degenerada": _clave_degenerada(informe["clave_despues"]),
    }
    if args.json:
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
    else:
        antes = " ".join(informe["clave_antes"].values())
        despues = " ".join(informe["clave_despues"].values())
        print(f"semilla: {semilla}")
        print(f"clave antes:   {antes}")
        print(f"clave después: {despues}")
        if resumen["clave_despues_degenerada"]:
            print("aviso: la clave sigue concentrada; probar otra semilla", file=sys.stderr)
        print(("(dry-run) " if args.dry_run else "") + f"escrito: {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
