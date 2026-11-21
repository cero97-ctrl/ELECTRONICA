#!/usr/bin/env python3
"""
sincronizar_titulos_practicas.py — Sync determinista de títulos (Layer 3)

Copia el título oficial impreso en `practicas/` (el argumento de `\\bandaTitulo`)
a `semanas[].practica.titulo` de `curso.yaml`. El `.tex` es la fuente de verdad:
el descriptor tenía resúmenes cortos que no coincidían con el título impreso.

Sirve para ambos cursos sin duplicar lógica:
  - Laboratorio II: `practica_NN.tex` para las 10 semanas.
  - Laboratorio I: `taller_NN.tex` en las semanas 1..4 y `practica_NN.tex` en
    las 5..10. La decisión es por existencia de archivo, nunca por adivinanza.

La edición es QUIRÚRGICA: solo sustituye la línea `titulo:` dentro del bloque
`practica:` de cada semana. El resto del YAML (comentarios, anclas, orden,
espaciado, el estilo de citado y los `titulo:` de nivel semana) queda intacto.

Por seguridad, sin `--apply` SOLO reporta. Nunca escribe si no hay cambios.

Arquitectura: directiva sincronizar_titulos_practicas.yaml (L1) →
flujo_sincronizar_titulos_practicas.py (L2) → este script (L3).

Uso:
  python3 execution/sincronizar_titulos_practicas.py --check --json
  python3 execution/sincronizar_titulos_practicas.py --apply --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CURSO_POR_DEFECTO = PROJECT_ROOT / "cursos/LABORATORIO_II_FISICA/curso.yaml"
N_SEMANAS = 10
BANDA_TITULO = re.compile(r"\\bandaTitulo\[[^\]]*\]\{([^}]*)\}")


def ruta_y_prefijo(curso: Path, numero: int) -> tuple[Path, str]:
    """Localiza el .tex de la semana y devuelve su prefijo oficial esperado.

    Laboratorio I nombra talleres las semanas 1..4 y prácticas la 5..10;
    Laboratorio II usa `practica_NN.tex` para las 10. La decisión es pura:
    existe `practica_NN.tex`, o si no `taller_NN.tex`. Nunca se adivina.
    """
    directorio = curso.parent / "practicas"
    practica = directorio / f"practica_{numero:02d}.tex"
    if practica.is_file():
        return practica, f"Práctica {numero:02d}"
    taller = directorio / f"taller_{numero:02d}.tex"
    if taller.is_file():
        return taller, f"Taller {numero:02d}"
    raise ValueError(f"no hay practica_{numero:02d}.tex ni taller_{numero:02d}.tex en {directorio}")


def extraer_titulo_tex(ruta: Path, numero: int, prefijo: str) -> str:
    """Devuelve el título oficial de un taller/práctica, normalizado para Markdown."""
    try:
        texto = ruta.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"no se pudo leer {ruta}: {exc}") from exc
    clase = prefijo.split()[0]
    candidatos = [m for m in BANDA_TITULO.findall(texto) if m.strip().startswith(clase)]
    if not candidatos:
        raise ValueError(f"{ruta} no declara un \\bandaTitulo que empiece por '{clase}'")
    titulo = " ".join(candidatos[0].replace("---", "—").split())
    if not titulo.startswith(prefijo):
        raise ValueError(f"{ruta}: el título '{titulo}' no empieza por '{prefijo}'")
    return titulo


def titulos_oficiales(curso: Path) -> dict[int, str]:
    """Lee los 10 .tex (talleres o prácticas) y devuelve {numero: título oficial}."""
    oficiales: dict[int, str] = {}
    for numero in range(1, N_SEMANAS + 1):
        ruta, prefijo = ruta_y_prefijo(curso, numero)
        oficiales[numero] = extraer_titulo_tex(ruta, numero, prefijo)
    return oficiales


def descomillar(valor: str) -> str:
    """Quita comillas envolventes (simples o dobles) de un scalar YAML."""
    valor = valor.strip()
    if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ("'", '"'):
        return valor[1:-1]
    return valor


def cotizar(nuevo: str, original: str) -> str:
    """Escribe `nuevo` preservando el estilo de citado del valor original.

    Los descriptores mezclan estilos: Lab II usa scalars planos y Lab I comillas
    simples. Además, un título con ': ' (p. ej. 'Taller 02 — Del objeto al
    resultado: propagar sin inventar cifras') NO puede escribirse como scalar
    plano: YAML lo tomaría por un mapeo. Por eso se conserva el citado original
    y, si no había, se añade cuando el valor lo exige.
    """
    original = original.strip()
    if len(original) >= 2 and original[0] == original[-1] == "'":
        return "'" + nuevo.replace("'", "''") + "'"
    if len(original) >= 2 and original[0] == original[-1] == '"':
        return '"' + nuevo.replace("\\", "\\\\").replace('"', '\\"') + '"'
    especial = ": " in nuevo or " #" in nuevo or nuevo.startswith(
        ("-", "?", ":", "[", "{", "&", "*", "!", "|", ">", "%", "@", "`")
    )
    return "'" + nuevo.replace("'", "''") + "'" if especial else nuevo


def titulos_actuales(texto: str) -> dict[int, str]:
    """Extrae `semanas[].practica.titulo` con un escaneo por líneas, sin PyYAML."""
    actuales: dict[int, str] = {}
    numero: int | None = None
    esperando = False
    for linea in texto.splitlines():
        inicio = re.match(r"^  - numero: (\d+)\s*$", linea)
        if inicio:
            numero = int(inicio.group(1))
            esperando = False
            continue
        if numero is None:
            continue
        if re.match(r"^    practica:\s*$", linea):
            esperando = True
            continue
        if esperando:
            titulo = re.match(r"^      titulo:\s*(.+?)\s*$", linea)
            if titulo:
                actuales[numero] = descomillar(titulo.group(1))
                esperando = False
    return actuales


def sustituir_titulos(texto: str, titulos: dict[int, str]) -> tuple[str, list[dict]]:
    """Sustituye solo los `titulo:` del bloque `practica:`. Función pura."""
    salida: list[str] = []
    cambios: list[dict] = []
    numero: int | None = None
    esperando = False
    for linea in texto.splitlines(keepends=True):
        contenido = linea.rstrip("\r\n")
        salto = linea[len(contenido):]
        inicio = re.match(r"^  - numero: (\d+)\s*$", contenido)
        if inicio:
            numero = int(inicio.group(1))
            esperando = False
            salida.append(linea)
            continue
        if numero is not None and re.match(r"^    practica:\s*$", contenido):
            esperando = True
            salida.append(linea)
            continue
        if esperando and numero in titulos:
            titulo = re.match(r"^      titulo:\s*(.+?)\s*$", contenido)
            if titulo:
                anterior_crudo, nuevo = titulo.group(1), titulos[numero]
                if descomillar(anterior_crudo) != nuevo:
                    cambios.append({"numero": numero,
                                    "anterior": descomillar(anterior_crudo), "nuevo": nuevo})
                    salida.append(f"      titulo: {cotizar(nuevo, anterior_crudo)}{salto}")
                else:
                    salida.append(linea)
                esperando = False
                continue
        salida.append(linea)
    return "".join(salida), cambios


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sincroniza los títulos de práctica de curso.yaml desde los .tex."
    )
    parser.add_argument("--curso", type=Path, default=CURSO_POR_DEFECTO)
    parser.add_argument("--check", action="store_true", help="Solo reporta; no escribe nunca.")
    parser.add_argument("--apply", action="store_true", help="Aplica los cambios al YAML.")
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    args = parser.parse_args()

    if args.check and args.apply:
        print("error: --check y --apply son mutuamente excluyentes", file=sys.stderr)
        return 1

    try:
        texto = args.curso.read_text(encoding="utf-8")
        oficiales = titulos_oficiales(args.curso)
        actuales = titulos_actuales(texto)
        faltan = sorted(set(oficiales) - set(actuales))
        if faltan:
            raise ValueError(f"curso.yaml no declara practica.titulo para las semanas {faltan}")
        nuevo_texto, cambios = sustituir_titulos(texto, oficiales)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "code": 2, "message": str(exc)})
              if args.json else f"error: {exc}", file=sys.stderr)
        return 2

    aplicar = args.apply and not args.check
    if aplicar and cambios:
        temporal = args.curso.with_name(args.curso.name + ".tmp")
        temporal.write_text(nuevo_texto, encoding="utf-8", newline="")
        temporal.replace(args.curso)
        # Releer y verificar: la regla se valida contra el archivo real, no en memoria.
        verificado = titulos_actuales(args.curso.read_text(encoding="utf-8"))
        if verificado != oficiales:
            print(json.dumps({"status": "error", "code": 4,
                              "message": "la verificación posterior a la escritura falló"})
                  if args.json else "error: verificación posterior fallida", file=sys.stderr)
            return 4

    informe = {
        "status": "ok",
        "code": 0,
        "curso": str(args.curso),
        "cambios": cambios,
        "n_cambios": len(cambios),
        "sincronizado": not cambios or aplicar,
        "modo": "apply" if aplicar else "check",
    }
    print(json.dumps(informe, ensure_ascii=False, indent=2) if args.json else
          (f"sincronizados {len(cambios)} títulos" if aplicar else
           f"{len(cambios)} títulos por sincronizar" if cambios else "títulos ya sincronizados"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
