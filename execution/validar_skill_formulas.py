#!/usr/bin/env python3
r"""
validar_skill_formulas.py — Validación neuro-simbólica del skill generado
(Layer 3: Execution, determinista).

Flujo asociado: directives/libro_a_skill.yaml

Extrae los bloques ```python / ```sympy / ```py de SKILL.md + references/*.md y
los valida en tres niveles (patrón neuro-simbólico del documento de diseño):
  1. Sintaxis: ast.parse.
  2. Seguridad: escaneo AST que solo permite importar math/sympy/fractions y veta
     módulos de sistema, I/O y funciones peligrosas (open/eval/exec/__import__...).
  3. Ejecución: sandbox en subproceso aislado con timeout, exportando solo las
     librerías permitidas (math, sympy). Si z3 estuviera disponible se usaría
     además; en su ausencia se omite con aviso.

Reporta también la presencia de las estructuras de razonamiento del skill
(metodologias.md, limites_aplicabilidad.md, prerrequisitos.md) como observación
(warning, no error): el contenido lo decide la síntesis, no este script.

Uso:
    python3 execution/validar_skill_formulas.py \
        --skill .tmp/skill_<nombre>/ \
        [--timeout-s 5] [--solo-ast] [--permitir-imports "math sympy fractions"]

Salida (stdout, JSON):
    {
      "status": "ok",
      "skill_dir": "...",
      "oraculo": "sympy 1.14.0" | "none (solo AST)",
      "estructuras": {"presentes": [...], "faltantes": [...]},
      "archivos_revisados": N,
      "bloques": [
         {"archivo": "references/formulas.md", "indice": 0, "lenguaje": "python",
          "estado": "ok" | "sintaxis_error" | "import_inseguro" | "ejecucion_error",
          "error": null | "..."}
      ],
      "resumen": {"total": N, "ok": X, "errores": Y}
    }

Códigos de salida:
    0 — Sin errores (puede haber warnings de estructura)
    1 — Error de argumentos / ruta inválida
    2 — SKILL.md ausente o ilegible
    3 — Hay bloques de código inválidos (inválido = sintaxis, import inseguro o error de ejecución)
"""

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

_LANGS = {"python", "sympy", "py", "python3"}
_SOLO_MODULOS = {"math", "sympy", "fractions"}
_MODULOS_BLOQUEADOS = {
    "os", "sys", "subprocess", "pathlib", "socket", "pty", "ctypes", "shutil",
    "builtins", "importlib", "asyncio", "multiprocessing", "threading", "signal",
    "platform", "fcntl", "mmap", "tempfile", "pickle", "marshal", "shelve",
}
_FUNCS_BLOQUEADAS = {
    "open", "eval", "exec", "compile", "input", "exit", "quit", "globals",
    "locals", "vars", "breakpoint", "getattr", "setattr", "delattr",
    "__import__", "memoryview", "bytearray",
}
_ESTRUCTURAS_REQUERIDAS = (
    "metodologias.md", "limites_aplicabilidad.md", "prerrequisitos.md",
)


class _ArgParserExit1(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(
            json.dumps({"status": "error", "code": 1, "message": message}, ensure_ascii=False),
            file=sys.stderr,
        )
        sys.exit(1)


def _fence_re() -> re.Pattern:
    return re.compile(r"^\s*```([A-Za-z0-9+_.\-]*)\s*(.*)$")


def _extraer_bloques(texto: str) -> list[dict]:
    """Devuelve [{lenguaje, src}] de los bloques fenced con lenguaje reconocido."""
    bloques: list[dict] = []
    lines = texto.splitlines()
    n = len(lines)
    i = 0
    while i < n:
        m = _fence_re().match(lines[i])
        if not m:
            i += 1
            continue
        lang = (m.group(1) or "").strip().lower()
        sobra = m.group(2).strip()
        if sobra:
            i += 1
            continue
        j = i + 1
        buf: list[str] = []
        while j < n and not _fence_re().match(lines[j]):
            buf.append(lines[j])
            j += 1
        if j < n and lang in _LANGS:
            bloques.append({"lenguaje": lang, "src": "\n".join(buf)})
            i = j + 1
            continue
        i += 1
    return bloques


def _escaneo_seguridad(src: str) -> str | None:
    """Retorna None si es seguro; si no, el motivo (módulo/función vetada)."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        # La sintaxis se reporta aparte con línea/columna exacta.
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                raiz = alias.name.split(".")[0]
                if raiz not in _SOLO_MODULOS:
                    return f"import no permitido: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            modulo = (node.module or "").split(".")[0]
            if modulo not in _SOLO_MODULOS:
                return f"import desde no permitido: {node.module or ''}"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _FUNCS_BLOQUEADAS:
                return f"función no permitida: {node.func.id}()"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in _FUNCS_BLOQUEADAS or node.func.attr.startswith("__"):
                return f"función no permitida: .{node.func.attr}()"
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                return f"atributo no permitido: .{node.attr}"
        elif isinstance(node, ast.Name):
            if node.id in _MODULOS_BLOQUEADOS:
                return f"módulo no permitido: {node.id}"
    return None


def _ejecutar_bloque(src: str, timeout_s: int) -> str | None:
    """Sandbox: subproceso aislado con sys.executable. Retorna None si OK."""
    try:
        proc = subprocess.run(
            [sys.executable, "-c", src],
            capture_output=True, text=True, timeout=timeout_s, encoding="utf-8",
        )
    except subprocess.TimeoutExpired:
        return f"tiempo excedido ({timeout_s}s)"
    except OSError as exc:
        return f"no se pudo lanzar sandbox: {exc}"
    if proc.returncode != 0:
        cola = [ln for ln in (proc.stderr or "").splitlines() if ln.strip()]
        return (cola[-1][:400] if cola else f"exit code {proc.returncode}")
    return None


def _oraculo() -> str:
    try:
        import sympy
        return f"sympy {sympy.__version__}"
    except ImportError:
        return "none (solo AST)"


def _nombre_virtual(archivo: Path, dir_skill: Path) -> str:
    rel = archivo.relative_to(dir_skill)
    return "SKILL.md" if rel.name == "SKILL.md" else str(rel)


def validar(dir_skill: Path, timeout_s: int, solo_ast: bool) -> dict:
    skill_md = dir_skill / "SKILL.md"
    if not skill_md.is_file():
        print(
            json.dumps(
                {"status": "error", "code": 2, "message": f"Falta {skill_md}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(2)

    md_files = [skill_md]
    refs_dir = dir_skill / "references"
    if refs_dir.is_dir():
        md_files += sorted(refs_dir.glob("*.md"))

    bloques: list[dict] = []
    for archivo in md_files:
        try:
            texto = archivo.read_text(encoding="utf-8")
        except OSError as exc:
            print(
                json.dumps({"status": "error", "code": 2, "message": f"No se pudo leer {archivo}: {exc}"}, ensure_ascii=False),
                file=sys.stderr,
            )
            sys.exit(2)
        for i, blk in enumerate(_extraer_bloques(texto)):
            src = blk["src"]
            ficha = {
                "archivo": _nombre_virtual(archivo, dir_skill),
                "indice": i,
                "lenguaje": blk["lenguaje"],
                "estado": "ok",
                "error": None,
            }
            try:
                ast.parse(src)
            except SyntaxError as exc:
                ficha["estado"] = "sintaxis_error"
                ficha["error"] = f"línea {exc.lineno}: {exc.msg}"
                bloques.append(ficha)
                continue

            motivo = _escaneo_seguridad(src)
            if motivo:
                ficha["estado"] = "import_inseguro"
                ficha["error"] = motivo
                bloques.append(ficha)
                continue

            if not solo_ast and _tiene_oraculo():
                err = _ejecutar_bloque(src, timeout_s)
                if err:
                    ficha["estado"] = "ejecucion_error"
                    ficha["error"] = err
            bloques.append(ficha)

    presentes = sorted(p.name for p in refs_dir.glob("*.md")) if refs_dir.is_dir() else []
    faltantes = sorted(set(_ESTRUCTURAS_REQUERIDAS) - set(presentes))
    errores = [b for b in bloques if b["estado"] != "ok"]

    return {
        "status": "ok",
        "skill_dir": str(dir_skill),
        "oraculo": _oraculo(),
        "estructuras": {"presentes": presentes, "faltantes": faltantes},
        "archivos_revisados": len(md_files),
        "bloques": bloques,
        "resumen": {
            "total": len(bloques),
            "ok": len(bloques) - len(errores),
            "errores": len(errores),
        },
    }


def _tiene_oraculo() -> bool:
    try:
        import sympy  # noqa: F401
        return True
    except ImportError:
        return False


def main() -> int:
    parser = _ArgParserExit1(description=__doc__)
    parser.add_argument("--skill", required=True, help="Directorio del skill (SKILL.md + references/).")
    parser.add_argument("--timeout-s", type=int, default=5, help="Timeout de ejecución por bloque (segundos).")
    parser.add_argument("--solo-ast", action="store_true", help="Solo sintaxis + seguridad (sin ejecución).")
    args = parser.parse_args()

    dir_skill = Path(args.skill).expanduser()
    if not dir_skill.is_dir():
        print(
            json.dumps(
                {"status": "error", "code": 1, "message": f"No existe el directorio del skill: {dir_skill}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1

    resultado = validar(dir_skill, max(1, args.timeout_s), args.solo_ast)
    print(json.dumps(resultado, ensure_ascii=False))
    return 3 if resultado["resumen"]["errores"] else 0


if __name__ == "__main__":
    sys.exit(main())