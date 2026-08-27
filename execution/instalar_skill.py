#!/usr/bin/env python3
"""
instalar_skill.py — Instala un skill generado en el directorio global de opencode
(Layer 3: Execution).

Flujo asociado: directives/libro_a_skill.yaml

Copia el directorio del skill generado (SKILL.md + references/) a
~/.config/opencode/skills/<nombre>/ y valida la estructura antes y después.
Es determinista: mismo origen -> mismo destino (sobrescribiendo si se pide).

Uso:
    python3 execution/instalar_skill.py \
        --origen .tmp/skill_<nombre>/ \
        --nombre <nombre> \
        [--destino ~/.config/opencode/skills/] \
        [--sobrescribir] \
        [--dry-run]

Salida (stdout, JSON):
    { "status": "ok"|"dry_run", "destino": "...", "archivos_copiados": [...],
      "reiniciar_opencode": true }

Códigos de salida:
    0 — Instalado (o dry-run completado)
    1 — Error de argumentos o origen inválido
    3 — Skill destino ya existe sin --sobrescribir
    4 — Estructura inválida en el origen
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import yaml


class _ArgParserExit1(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(json.dumps({"status": "error", "code": 1, "message": message}), file=sys.stderr)
        sys.exit(1)


def _nombre_valido(nombre: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", nombre))


def _validar_origen(origen: Path, nombre: str) -> list[str]:
    errores: list[str] = []
    skill_md = origen / "SKILL.md"
    if not skill_md.is_file():
        return [f"Falta {skill_md} en el origen"]
    try:
        fm_txt = skill_md.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"No se pudo leer SKILL.md: {exc}"]
    m = re.match(r"^---\s*\n(.*?)\n---", fm_txt, re.DOTALL)
    if not m:
        return ["SKILL.md sin frontmatter YAML"]
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:
        return [f"Frontmatter inválido: {exc}"]
    if not isinstance(fm, dict) or not fm.get("name"):
        errores.append("Frontmatter sin 'name'")
    elif nombre and fm["name"] != nombre:
        errores.append(f"'name' ({fm['name']!r}) != carpeta ({nombre!r})")
    if not fm or not isinstance(fm.get("description"), str) or len(fm["description"].strip()) < 20:
        errores.append("'description' ausente o corta")
    return errores


def instalar(origen: Path, nombre: str, destino: Path, sobrescribir: bool, dry_run: bool) -> dict:
    if not _nombre_valido(nombre):
        print(
            json.dumps(
                {
                    "status": "error",
                    "code": 1,
                    "message": f"Nombre de skill inválido: {nombre!r}. Debe ser snake_case [a-z0-9_-].",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    if not origen.is_dir():
        print(
            json.dumps(
                {"status": "error", "code": 1, "message": f"Origen inexistente: {origen}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    errores = _validar_origen(origen, nombre)
    if errores:
        print(
            json.dumps({"status": "error", "code": 4, "message": "; ".join(errores)}, ensure_ascii=False),
            file=sys.stderr,
        )
        sys.exit(4)

    destino_skill = (destino / nombre).resolve()
    destino_skill.parent.mkdir(parents=True, exist_ok=True)

    if destino_skill.exists() and not sobrescribir:
        print(
            json.dumps(
                {
                    "status": "error",
                    "code": 3,
                    "message": (
                        f"Ya existe el skill en {destino_skill}. "
                        f"Usa --sobrescribir para reemplazarlo."
                    ),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(3)

    archivos = sorted(
        str(p.relative_to(origen)) for p in origen.rglob("*") if p.is_file()
    )

    if dry_run:
        return {
            "status": "dry_run",
            "destino": str(destino_skill),
            "archivos_a_copiar": archivos,
            "reiniciar_opencode": True,
            "sobrescribir": sobrescribir,
        }

    if destino_skill.exists():
        shutil.rmtree(destino_skill)
    shutil.copytree(origen, destino_skill)

    return {
        "status": "ok",
        "destino": str(destino_skill),
        "archivos_copiados": archivos,
        "reiniciar_opencode": True,
    }


def main() -> None:
    parser = _ArgParserExit1(description=__doc__)
    parser.add_argument("--origen", required=True, help="Directorio del skill generado.")
    parser.add_argument("--nombre", required=True, help="Nombre del skill (carpeta destino).")
    parser.add_argument(
        "--destino",
        default=str(Path.home() / ".config" / "opencode" / "skills"),
        help="Directorio global de skills (default ~/.config/opencode/skills).",
    )
    parser.add_argument("--sobrescribir", action="store_true")
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    try:
        resultado = instalar(
            Path(args.origen),
            args.nombre,
            Path(args.destino).expanduser(),
            args.sobrescribir,
            args.dry_run,
        )
    except OSError as exc:
        print(json.dumps({"status": "error", "code": 3, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(3)

    print(json.dumps(resultado, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
