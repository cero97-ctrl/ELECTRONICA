#!/usr/bin/env python3
"""Renderiza un archivo Markdown como HTML y lo abre en el navegador."""

import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print(f"Uso: {sys.argv[0]} <archivo.md>", file=sys.stderr)
        sys.exit(1)

    md_file = Path(sys.argv[1])
    if not md_file.is_file():
        print(f"Error: '{md_file}' no existe.", file=sys.stderr)
        sys.exit(1)

    out = Path(tempfile.gettempdir()) / "vista_previa.html"

    result = subprocess.run(
        ["pandoc", str(md_file), "-o", str(out), "--standalone",
         "--metadata", f"title={md_file.stem}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Error pandoc:\n{result.stderr}", file=sys.stderr)
        sys.exit(result.returncode)

    subprocess.Popen(["xdg-open", str(out)])
    print(f"Abierto en navegador: {out}")


if __name__ == "__main__":
    main()
