#!/usr/bin/env python3
"""
extraer_repo_github.py — Extrae archivos de un repositorio GitHub o directorio local,
filtra por relevancia y concatena en texto_completo.txt (Layer 3: Execution).

Flujo asociado: directives/repo_a_skill.yaml

Acepta una URL de GitHub (clona con --depth 1) o una ruta local, filtra
archivos por extensiones permitidas (docs + código fuente) excluyendo
binarios/vendor/build/.git/node_modules, y produce:
  - texto_completo.txt  (concatenación con cabeceras === ARCHIVO: ... ===)
  - indice.json         (archivos incluidos + excluidos + árbol de estructura)

Contrato de salida idéntico a extraer_libro_pdf.py para ser consumido
por sintetizar_skill.py sin cambios.

Uso:
    python3 execution/extraer_repo_github.py \
        --fuente <url-o-ruta-local> \
        --salida .tmp/repo_<nombre>_texto/ \
        [--rama main] \
        [--incluir "*.py" "*.md"] \
        [--excluir "tests/*" "docs/*"] \
        [--max-archivos 200] \
        [--max-bytes 5000000]

Salida (stdout, JSON):
    {
      "status": "ok",
      "num_archivos": N,
      "num_excluidos": M,
      "caracteres": 12345,
      "tokens_estimados": 3086,
      "archivo_texto": ".tmp/repo_foo_texto/texto_completo.txt",
      "fuente": "https://github.com/..."
    }

Códigos de salida:
    0 — Extracción exitosa
    1 — Error de argumentos / archivos ilegibles
    2 — Repo vacío / sin archivos tras filtrado
"""

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

CHARS_PER_TOKEN = 4

# Extensiones permitidas por defecto: docs + código fuente
_EXTENSIONES_DEFAULT = {
    # Código
    ".py", ".js", ".ts", ".jsx", ".tsx", ".c", ".cpp", ".h", ".hpp", ".rs",
    ".go", ".java", ".kt", ".scala", ".rb", ".php", ".sh", ".bash", ".zsh",
    ".verilog", ".v", ".sv", ".vhd", ".vhdl", ".tcl",
    # Config / datos
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".xml", ".csv",
    # Docs
    ".md", ".rst", ".txt", ".tex",
    # Build / config de proyecto
    "Makefile", "CMakeLists.txt", "Dockerfile", "docker-compose.yml",
    "setup.py", "setup.cfg", "pyproject.toml", "package.json",
    "Cargo.toml", "go.mod", "wrangler.toml",
    # Templates / HTML
    ".html", ".htm", ".css", ".scss", ".less", ".jinja", ".jinja2",
    # Notebooks
    ".ipynb",
}

# Directorios siempre excluidos
_DIRS_EXCLUIR = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", "target", "vendor", ".next", ".nuxt",
    "egg-info", ".eggs",
}


class _ArgParserExit1(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(
            json.dumps({"status": "error", "code": 1, "message": message}, ensure_ascii=False),
            file=sys.stderr,
        )
        sys.exit(1)


def _es_url_github(fuente: str) -> bool:
    """Detecta si la fuente es una URL de GitHub (https o ssh)."""
    return bool(re.match(r"^https?://.*github\.com/", fuente) or
                re.match(r"^git@github\.com:", fuente))


def _nombre_repo_de_url(url: str) -> str:
    """Extrae owner/repo de una URL de GitHub."""
    # https://github.com/owner/repo → owner-repo
    # git@github.com:owner/repo.git → owner-repo
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    if m:
        return m.group(1).replace("/", "-")
    return "repo"


def _clonar_repo(url: str, destino: Path, rama: str | None = None) -> None:
    """Clona un repo de GitHub en destino (--depth 1)."""
    cmd = ["git", "clone", "--depth", "1"]
    if rama:
        cmd.extend(["-b", rama])
    cmd.extend([url, str(destino)])
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=120, encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"No se pudo clonar {url}: {proc.stderr.strip() or 'error desconocido'}"
        )


def _archivos_en_directorio(directorio: Path) -> list[Path]:
    """Lista recursivamente todos los archivos en directorio (sin seguir symlinks)."""
    archivos: list[Path] = []
    for root, dirs, files in os.walk(directorio, followlinks=False):
        # Filtrar directorios excluidos IN-PLACE para que os.walk no los recorra
        dirs[:] = [
            d for d in dirs
            if d not in _DIRS_EXCLUIR and not d.startswith(".")
        ]
        for fname in files:
            fpath = Path(root) / fname
            if fpath.is_file() and not fpath.is_symlink():
                archivos.append(fpath)
    return sorted(archivos)


def _deberia_incluir(
    archivo: Path,
    extensiones: set[str],
    incluir_globs: list[str] | None,
    excluir_globs: list[str] | None,
    repo_root: Path,
) -> tuple[bool, str]:
    """Decide si un archivo debe incluirse. Retorna (incluir, razon)."""
    rel = str(archivo.relative_to(repo_root))

    # Si hay globs explícitos --incluir, solo incluir los que matcheen
    if incluir_globs:
        for patron in incluir_globs:
            if fnmatch.fnmatch(rel, patron) or fnmatch.fnmatch(archivo.name, patron):
                break
        else:
            return False, f"no match incluir: {rel}"

    # Verificar --excluir
    if excluir_globs:
        for patron in excluir_globs:
            if fnmatch.fnmatch(rel, patron) or fnmatch.fnmatch(archivo.name, patron):
                return False, f"excluido: {rel} ({patron})"

    # Verificar extensión
    if archivo.suffix.lower() in extensiones:
        return True, "ok"

    # Verificar nombres exactos (Makefile, Dockerfile, etc.)
    if archivo.name in extensiones:
        return True, "ok"

    return False, f"extensión no permitida: {archivo.suffix}"


def _concatenar_archivos(
    archivos: list[Path], repo_root: Path, max_bytes: int,
) -> tuple[str, int, list[dict]]:
    """Concatena archivos con cabeceras. Retorna (texto, bytes_total, detalle)."""
    partes: list[str] = []
    bytes_total = 0
    detalle: list[dict] = []

    for archivo in archivos:
        try:
            contenido = archivo.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError) as exc:
            detalle.append({
                "archivo": str(archivo.relative_to(repo_root)),
                "incluir": False,
                "razon": f"ilegible: {exc}",
            })
            continue

        bytes_archivo = len(contenido.encode("utf-8"))
        if bytes_total + bytes_archivo > max_bytes:
            detalle.append({
                "archivo": str(archivo.relative_to(repo_root)),
                "incluir": False,
                "razon": f"excedería max_bytes ({bytes_archivo} bytes)",
            })
            continue

        rel = str(archivo.relative_to(repo_root))
        partes.append(f"=== ARCHIVO: {rel} ===\n{contenido}")
        bytes_total += bytes_archivo
        detalle.append({
            "archivo": rel,
            "incluir": True,
            "razon": "ok",
            "bytes": bytes_archivo,
        })

    return "\n\n".join(partes), bytes_total, detalle


def _arbol_estructura(archivos: list[Path], repo_root: Path) -> str:
    """Genera un árbol ASCII simple de la estructura del repo."""
    lineas: list[str] = []
    for archivo in archivos:
        rel = archivo.relative_to(repo_root)
        profundidad = len(rel.parts) - 1
        indent = "  " * profundidad
        lineas.append(f"{indent}├── {rel.name}" if profundidad > 0 else str(rel.name))
    return "\n".join(lineas)


def main() -> None:
    parser = _ArgParserExit1(description=__doc__)
    parser.add_argument(
        "--fuente", required=True,
        help="URL de GitHub o ruta local al repositorio/directorio.",
    )
    parser.add_argument(
        "--salida", required=True,
        help="Directorio donde escribir texto_completo.txt e indice.json.",
    )
    parser.add_argument("--rama", default=None, help="Rama a clonar (default: rama principal).")
    parser.add_argument(
        "--incluir", nargs="*", default=None,
        help="Globs de archivos a INCLUIR (default: docs+código). E.g.: '*.py' '*.md'",
    )
    parser.add_argument(
        "--excluir", nargs="*", default=None,
        help="Globs de archivos a EXCLUIR. E.g.: 'tests/*' 'docs/*'",
    )
    parser.add_argument("--max-archivos", type=int, default=200, help="Máximo de archivos a procesar.")
    parser.add_argument("--max-bytes", type=int, default=5_000_000, help="Máximo de bytes totales.")

    args = parser.parse_args()

    fuente = args.fuente
    salida = Path(args.salida)
    es_local = not _es_url_github(fuente)

    # Directorio temporal para repos clonados
    if es_local:
        repo_root = Path(fuente).expanduser().resolve()
        if not repo_root.is_dir():
            print(
                json.dumps({"status": "error", "code": 1, "message": f"Directorio local no existe: {repo_root}"},
                           ensure_ascii=False),
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        nombre_repo = _nombre_repo_de_url(fuente)
        clone_dir = Path(".tmp") / f"repo_clone_{nombre_repo}"
        try:
            print(f"Clonando {fuente} en {clone_dir}...", file=sys.stderr)
            _clonar_repo(fuente, clone_dir, args.rama)
        except RuntimeError as exc:
            print(
                json.dumps({"status": "error", "code": 1, "message": str(exc)}, ensure_ascii=False),
                file=sys.stderr,
            )
            sys.exit(1)
        repo_root = clone_dir

    # Listar archivos
    todos = _archivos_en_directorio(repo_root)
    if not todos:
        print(
            json.dumps({"status": "error", "code": 2, "message": "Repo/directorio vacío o sin archivos."},
                       ensure_ascii=False),
            file=sys.stderr,
        )
        sys.exit(2)

    # Filtrar
    extensiones = _EXTENSIONES_DEFAULT.copy()
    incluidos: list[Path] = []
    excluidos: list[dict] = []

    for archivo in todos:
        if len(incluidos) >= args.max_archivos:
            excluidos.append({
                "archivo": str(archivo.relative_to(repo_root)),
                "incluir": False,
                "razon": f"límite max_archivos ({args.max_archivos})",
            })
            continue
        ok, razon = _deberia_incluir(
            archivo, extensiones, args.incluir, args.excluir, repo_root,
        )
        if ok:
            incluidos.append(archivo)
        else:
            excluidos.append({
                "archivo": str(archivo.relative_to(repo_root)),
                "incluir": False,
                "razon": razon,
            })

    if not incluidos:
        print(
            json.dumps({"status": "error", "code": 2, "message": "0 archivos tras filtrado."},
                       ensure_ascii=False),
            file=sys.stderr,
        )
        sys.exit(2)

    # Concatenar
    texto, bytes_total, detalle_concat = _concatenar_archivos(incluidos, repo_root, args.max_bytes)

    # Guardar
    salida.mkdir(parents=True, exist_ok=True)
    archivo_texto = salida / "texto_completo.txt"
    archivo_texto.write_text(texto, encoding="utf-8")

    # Generar índice
    arbol = _arbol_estructura(incluidos, repo_root)
    indice = {
        "fuente": fuente,
        "es_local": es_local,
        "rama": args.rama,
        "num_archivos_incluidos": len(incluidos),
        "num_archivos_excluidos": len(excluidos),
        "bytes_total": bytes_total,
        "tokens_estimados": bytes_total // CHARS_PER_TOKEN,
        "archivos": [d for d in detalle_concat if d.get("incluir")],
        "excluidos": excluidos,
        "arbol": arbol,
    }
    archivo_indice = salida / "indice.json"
    archivo_indice.write_text(json.dumps(indice, ensure_ascii=False, indent=2), encoding="utf-8")

    tokens = bytes_total // CHARS_PER_TOKEN
    resultado = {
        "status": "ok",
        "num_archivos": len(incluidos),
        "num_excluidos": len(excluidos),
        "caracteres": len(texto),
        "tokens_estimados": tokens,
        "archivo_texto": str(archivo_texto),
        "fuente": fuente,
    }
    print(json.dumps(resultado, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
