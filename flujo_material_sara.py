#!/usr/bin/env python3
"""Orquestador del material didáctico de Sara (Layer 2).

Decide qué hacer con la petición del usuario y delega la ejecución
determinista en `execution/generar_material_sara.py`:

  - validar el contenido sin escribir (`--check`)
  - mostrar las rutas sin escribir (`--dry-run`)
  - generar el sitio completo en `SARA/`

La lógica de renderizado, la accesibilidad y la barrera de salida viven en
la capa 3. Este archivo no compone HTML ni decide contenido: solo conecta la
intención (`--materia`, `--check`, etc.) con el script especializado.

Uso:
    python3 flujo_material_sara.py --check
    python3 flujo_material_sara.py --dry-run --json
    python3 flujo_material_sara.py

SOP: directives/material_didactico_sara.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / "execution"))

import generar_material_sara as gen  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Genera el sitio de estudio de Sara a partir de contenido YAML."
    )
    ap.add_argument(
        "--contenido",
        default=str(gen.CONTENIDO_POR_DEFECTO),
        help="carpeta con los temas en YAML (por defecto SARA/contenido/)",
    )
    ap.add_argument(
        "--salida",
        default=str(gen.SARA_DIR),
        help="carpeta del sitio (debe estar dentro de SARA/)",
    )
    ap.add_argument("--check", action="store_true", help="valida el contenido sin escribir")
    ap.add_argument("--dry-run", action="store_true", help="muestra las páginas sin escribir")
    ap.add_argument("--json", action="store_true", help="salida JSON")
    args = ap.parse_args()

    codigo = gen.ejecutar(
        contenido=args.contenido,
        salida=args.salida,
        check=args.check,
        dry_run=args.dry_run,
        json_out=args.json,
    )
    if codigo == 3:
        print(
            "El contenido no se publicó. Corrige los problemas y vuelve a ejecutar.",
            file=sys.stderr,
        )
    return codigo


if __name__ == "__main__":
    sys.exit(main())
