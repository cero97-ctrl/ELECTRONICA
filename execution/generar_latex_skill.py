#!/usr/bin/env python3
r"""
generar_latex_skill.py — Reporte LaTeX del skill generado (Layer 3: Execution)

Determinista: convierte SKILL.md + references/*.md a un documento LaTeX con el
estilo infográfico compartido (PREAMBULO_INFOGRAFIA), lo compila con pdflatex
(2 pasadas, ya limpia auxiliares) y deja el .tex y el .pdf en <salida>/.

Uso:
    python3 execution/generar_latex_skill.py \
        --skill .tmp/skill_<nombre> \
        --nombre <nombre> \
        --tema "<tema>" \
        --idioma es \
        --salida docs/SKILL/<nombre>

Exit code:
    0  -> el .tex quedó escrito (compilado puede ser false si el PDF falló)
    1  -> error CLI / archivos faltantes
    2  -> error de conversión

Salida JSON por stdout: {"status","tex","pdf","compilado","archivos"}
"""

import argparse
import contextlib
import io
import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR.parent))

from execution.compile_latex import compile_latex_code      # noqa: E402
from execution.estilo_infografia import (                   # noqa: E402
    PREAMBULO_INFOGRAFIA,
    banda_titulo,
)

ICONO_SKILL = "book"

# ── Marcado inline de Markdown (matemáticas protegidas) ─────────────────────
_MATH_RE = re.compile(r"(\$\$[^$\n]+\$\$|\$[^$\n]+?\$)")
_HEAD_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_RE = re.compile(r"^\s*[-+*]\s+(.*)$")
_NUM_RE = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_FENCE_RE = re.compile(r"^\s*```")
_TABLE_RE = re.compile(r"^\s*\|")
_SEP_RE = re.compile(r"^[\s|:\-]+$")


def _escapa_y_enfatiza(t: str) -> str:
    """Escapa caracteres LaTeX y convierte **negrita*, *cursiva* y `código`."""
    t = t.replace("\\", r"\textbackslash{}")
    t = t.replace("%", r"\%")
    t = t.replace("&", r"\&")
    t = t.replace("#", r"\#")
    t = t.replace("_", r"\_")
    t = t.replace("~", r"\textasciitilde{}")
    t = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", t)
    t = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\\textit{\1}", t)
    t = re.sub(r"`([^`]+)`", r"\\texttt{\1}", t)
    return t


def _inline(text: str) -> str:
    """Convierte una línea en LaTeX seguro.

    Protege primero el math con placeholders opacos (\x01M<n>\x02) para que los
    marcadores de énfasis (**negrita*, *cursiva*, `código`) se puedan convertir
    aunque envuelvan matemáticas (ej. '**Tensión ($V_T$):**'). Luego escapa los
    caracteres especiales del texto y restaura el math intacto.
    """
    stash: list[str] = []

    def _guarda(m: re.Match) -> str:
        stash.append(m.group(1))
        return f"\x01M{len(stash) - 1}\x02"

    t = re.sub(_MATH_RE, _guarda, text)
    t = _escapa_y_enfatiza(t)
    for i, math_original in enumerate(stash):
        t = t.replace(f"\x01M{i}\x02", math_original)
    return t


def _heading(lvl: int, texto: str) -> str:
    comando = {1: "section", 2: "subsection", 3: "subsubsection", 4: "paragraph"}.get(lvl, "subsubsection")
    return f"\\{comando}*{{{texto}}}\n\n"


def _tabla(rows: list[str]) -> str:
    def celdas(row: str) -> list[str]:
        return [c.strip() for c in row.strip().strip("|").split("|")]

    header = celdas(rows[0])
    ncols = len(header)
    data = []
    for r in rows[1:]:
        if _SEP_RE.match(r.strip()):
            continue
        data.append(celdas(r))
    if ncols == 0:
        return ""
    colspec = "l" * ncols
    out = [
        "\\begin{center}",
        "\\begin{tabular}{@{}" + colspec + "@{}}",
        "\\toprule",
        " & ".join(_inline(c) for c in header) + " \\\\",
        "\\midrule",
    ]
    for d in data:
        dd = (d + [""] * ncols)[:ncols]
        out.append(" & ".join(_inline(c) for c in dd) + " \\\\")
    out += ["\\bottomrule", "\\end{tabular}", "\\end{center}", ""]
    return "\n".join(out) + "\n\n"


def _fence(lines: list[str]) -> str:
    return "\\begin{lstlisting}\n" + "\n".join(lines) + "\n\\end{lstlisting}\n\n"


def _lista(tipo: str, items: list[str]) -> str:
    env = "enumerate" if tipo == "enumerate" else "itemize"
    cuerpo = "".join(f"  \\item {it}\n" for it in items)
    return f"\\begin{{{env}}}[leftmargin=*,topsep=2pt,itemsep=1pt]\n{cuerpo}\\end{{{env}}}\n\n"


def _cuerpo(md: str) -> list[str]:
    """Convierte el markdown en bloques LaTeX."""
    lines = md.splitlines()
    out = []
    i, n = 0, len(lines)
    while i < n:
        linea = lines[i].strip()
        if not linea:
            i += 1
            continue
        if _FENCE_RE.match(linea):
            j = i + 1
            buf = []
            while j < n and not _FENCE_RE.match(lines[j].strip()):
                buf.append(lines[j])
                j += 1
            out.append(_fence(buf))
            i = j + 1
            continue
        if _TABLE_RE.match(linea):
            j = i
            tbl = []
            while j < n and _TABLE_RE.match(lines[j]):
                tbl.append(lines[j].strip())
                j += 1
            out.append(_tabla(tbl))
            i = j
            continue
        m = _HEAD_RE.match(linea)
        if m:
            out.append(_heading(len(m.group(1)), _inline(m.group(2).strip())))
            i += 1
            continue
        b = _BULLET_RE.match(linea)
        num = _NUM_RE.match(linea)
        if b or num:
            tipo = "itemize"
            items = []
            while i < n:
                s = lines[i].strip()
                if not s:
                    break
                bi = _BULLET_RE.match(s)
                ni = _NUM_RE.match(s)
                if bi:
                    items.append(_inline(bi.group(1)))
                elif ni:
                    tipo = "enumerate"
                    items.append(_inline(ni.group(1)))
                else:
                    break
                i += 1
            out.append(_lista(tipo, items))
            continue
        par = []
        while i < n:
            s = lines[i].strip()
            if (not s or _HEAD_RE.match(s) or _BULLET_RE.match(s) or _NUM_RE.match(s)
                    or _TABLE_RE.match(s) or _FENCE_RE.match(s)):
                break
            par.append(_inline(s))
            i += 1
        if par:
            out.append(" ".join(par) + "\n\n")
    return out


# ── Ensamblaje del documento ─────────────────────────────────────────────────

def _frontmatter(texto: str) -> tuple[dict, str]:
    if texto.startswith("---"):
        fin = texto.find("---", 3)
        if fin != -1:
            meta = {}
            for linea in texto[3:fin].splitlines():
                if ":" in linea:
                    k, v = linea.split(":", 1)
                    meta[k.strip()] = v.strip()
            return meta, texto[fin + 3:].lstrip("\n")
    return {}, texto


def _documento(nombre: str, tema: str, descripcion: str, cuerpo: list[str]) -> str:
    cabecera = []
    cabecera.append(PREAMBULO_INFOGRAFIA.rstrip())
    cabecera.append("")
    cabecera.append("% ── Cabecera específica del reporte del skill ──")
    cabecera.append(rf"\renewcommand{{\iconoBanda}}{{{ICONO_SKILL}}}")
    cabecera.append(r"\fancyhead[L]{\color{azulNoche}\small\bfseries "
                    r"\faIcon{" + ICONO_SKILL + r"}~\textcolor{cyanNeon}{" + _inline(nombre) + r"}}")
    cabecera.append(r"\fancyhead[R]{\color{grisTexto}\small" + _inline(tema) + "}")
    cabecera.append("")
    cabecera.append("\\begin{document}")
    cabecera.append(banda_titulo(
        _inline(f"Skill: {nombre}"),
        _inline(descripcion[:220]),
    ))
    cabecera.append("")
    pie = ["\\end{document}"]
    return "\n".join(cabecera) + "\n" + "\n".join(cuerpo) + "\n" + "\n".join(pie) + "\n"


def _archivos_md(dir_skill: Path) -> list[Path]:
    md_files = [dir_skill / "SKILL.md"]
    refs = sorted((dir_skill / "references").glob("*.md")) if (dir_skill / "references").is_dir() else []
    md_files += refs
    faltantes = [p for p in md_files if not p.is_file()]
    if faltantes:
        raise FileNotFoundError("Faltan archivos: " + ", ".join(str(p) for p in faltantes))
    return md_files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", required=True, help="Directorio del skill (SKILL.md + references/).")
    parser.add_argument("--nombre", default=None, help="Nombre del skill (default: el del frontmatter).")
    parser.add_argument("--tema", default="Referencia técnica", help="Tema/dominio para la cabecera.")
    parser.add_argument("--idioma", default="es", help="Idioma (reservado; es es el soportado).")
    parser.add_argument("--salida", default=None, help="Directorio destino (.tex + .pdf); default docs/SKILL/<nombre>/.")
    args = parser.parse_args()

    dir_skill = Path(args.skill).expanduser()
    if not dir_skill.is_dir():
        print(json.dumps({"status": "error", "message": f"No existe el directorio del skill: {dir_skill}"}, ensure_ascii=False))
        return 1

    try:
        md_files = _archivos_md(dir_skill)
    except FileNotFoundError as e:
        print(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))
        return 1

    nombre = args.nombre or dir_skill.name.lstrip("skill_").replace("_", "_") or "skill"
    cuerpo: list[str] = []
    descripcion = "Referencia rápida generada automáticamente desde un libro."
    for md in md_files:
        texto = md.read_text(encoding="utf-8")
        meta, resto = _frontmatter(texto) if md.name == "SKILL.md" else ({}, texto)
        if md.name == "SKILL.md":
            nombre = args.nombre or meta.get("name", nombre)
            descripcion = meta.get("description", descripcion)
        if resto.strip():
            cuerpo.extend(_cuerpo(resto))
            if md.name != "SKILL.md" and (dir_skill / "references").name in str(md.parent):
                cuerpo.append(r"\vspace{10pt}" + "\n")

    salida = Path(args.salida).expanduser() if args.salida else (
        SCRIPT_DIR.parent / "docs" / "SKILL" / nombre
    )
    salida.mkdir(parents=True, exist_ok=True)

    doc = _documento(nombre, args.tema, descripcion, cuerpo)

    tex_path = salida / f"{nombre}.tex"
    try:
        tex_path.write_text(doc, encoding="utf-8")
    except OSError as e:
        print(json.dumps({"status": "error", "message": f"No se pudo escribir el .tex: {e}"}, ensure_ascii=False))
        return 1

    # Compila (2 pasadas + limpieza de auxiliares). Se silencia su stdout para
    # mantener el JSON limpio; ante fallo el .tex ya quedó guardado.
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        res = compile_latex_code(doc, job_name=nombre, output_dir=str(salida))

    compilado = bool(res.get("success"))
    pdf_path = salida / f"{nombre}.pdf"
    archivos = sorted([str(p) for p in salida.iterdir()])

    print(json.dumps({
        "status": "ok",
        "tex": str(tex_path),
        "pdf": str(pdf_path) if pdf_path.is_file() else None,
        "compilado": compilado,
        "archivos": archivos,
        "detalle_error": res.get("error") if not compilado else None,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())