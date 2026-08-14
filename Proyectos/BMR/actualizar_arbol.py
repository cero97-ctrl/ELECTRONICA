#!/usr/bin/env python3
"""Actualiza y despliega el árbol genealógico en Cloudflare Pages.

Flujo completo: validar JSON -> regenerar web/index.html -> desplegar con wrangler.

Uso:
    python3 actualizar_arbol.py            # ejecutar todo el flujo
    python3 actualizar_arbol.py --no-deploy  # solo validar y regenerar
    python3 actualizar_arbol.py --check      # solo validar el JSON
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
JSON_PATH = BASE_DIR / "arbol_familia.json"
OUT_DIR = BASE_DIR / "web"
GENERAR_SCRIPT = BASE_DIR / "generar_web.py"
NODE_VERSION = "20"


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    print(f"[CMD] {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, env=env, check=True)


def count_people(node: dict) -> int:
    return 1 + sum(count_people(c) for c in node.get("children", []))


def validate_json() -> int:
    if not JSON_PATH.exists():
        print(f"[ERROR] No se encuentra {JSON_PATH}")
        return 1
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    total = count_people(data)
    print(f"[OK] JSON válido: {total} personas")
    return 0


def generate_web() -> int:
    if not GENERAR_SCRIPT.exists():
        print(f"[ERROR] No se encuentra {GENERAR_SCRIPT}")
        return 1
    run([sys.executable, str(GENERAR_SCRIPT)], cwd=BASE_DIR)
    index = OUT_DIR / "index.html"
    if not index.exists():
        print(f"[ERROR] No se generó {index}")
        return 1
    print(f"[OK] {index.name}: {index.stat().st_size:,} bytes")
    return 0


def deploy() -> int:
    nvm_sh = Path.home() / ".nvm" / "nvm.sh"
    if nvm_sh.exists():
        bash_cmd = (
            f'export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; '
            f'nvm use {NODE_VERSION} >/dev/null 2>&1 || nvm install {NODE_VERSION} >/dev/null; '
            f'npx wrangler pages deploy "{OUT_DIR.name}"'
        )
        print(f"[INFO] Usando Node {NODE_VERSION} vía nvm.")
        result = subprocess.run(["bash", "-c", bash_cmd], cwd=BASE_DIR)
        return result.returncode

    npx = shutil.which("npx")
    if npx is not None:
        print("[INFO] Usando npx del sistema.")
        return run(["npx", "wrangler", "pages", "deploy", OUT_DIR.name], cwd=BASE_DIR).returncode

    print("[ERROR] No se encontró nvm ni npx (Node.js requerido para wrangler).")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Actualiza y despliega el árbol genealógico en Cloudflare Pages.")
    parser.add_argument("--no-deploy", action="store_true", help="Solo validar y regenerar la página web, sin desplegar.")
    parser.add_argument("--check", action="store_true", help="Solo validar el JSON, sin regenerar ni desplegar.")
    args = parser.parse_args()

    if validate_json() != 0:
        return 1

    if args.check:
        return 0

    if generate_web() != 0:
        return 1

    if args.no_deploy:
        print("[OK] Flujo terminado sin desplegar. Ejecuta: python3 actualizar_arbol.py  para desplegar.")
        return 0

    print("[INFO] Desplegando en Cloudflare Pages...")
    code = deploy()
    if code != 0:
        print("[ERROR] Falló el despliegue.")
        return code

    print("[OK] Despliegue completado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
