#!/usr/bin/env python3
"""
generar_practicas_desde_ocr.py — Capa 3: convierte el markdown del OCR de
`practicas.pdf` en los ocho enunciados LaTeX de las prácticas de Laboratorio II.

El markdown es la fuente de verdad de las prácticas (decisión del usuario,
2026-11-21): contiene los enunciados que la Universidad exige. Este script NO
razona: parsea, valida y renderiza con reglas puras. El mismo markdown SIEMPRE
produce los mismos `.tex` (mismo contenido → mismo hash).

No reimplementa el estilo infográfico ni el escapado de matemática: importa
`estilo_infografia` y los helpers ya probados de `generar_material_curso.py`.

Uso:
    python3 execution/generar_practicas_desde_ocr.py --check
    python3 execution/generar_practicas_desde_ocr.py --salida .tmp/practicas_desde_ocr --json
    python3 execution/generar_practicas_desde_ocr.py --salida cursos/LABORATORIO_II_FISICA/practicas --json

Códigos de salida:
    0 — prácticas generadas y verificadas
    1 — argumentos inválidos
    2 — markdown de entrada ilegible
    3 — estructura del OCR inválida (prácticas/secciones ausentes)
    4 — error de compilación LaTeX
    5 — error de escritura
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
RAIZ = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(RAIZ))

from compile_latex import compile_latex_code  # noqa: E402
from estilo_infografia import (  # noqa: E402
    PREAMBULO_INFOGRAFIA,
    banda_titulo,
    seccion_con_icono,
)
from generar_material_curso import (  # noqa: E402
    _lista,
    _tm,
)

OCR_POR_DEFECTO = RAIZ / ".tmp" / "ocr_practicas" / "practicas_ocr.md"
SALIDA_POR_DEFECTO = RAIZ / ".tmp" / "practicas_desde_ocr"
TITULO_DOCUMENTO = "Laboratorio II de Física"
SUBTITULO_DOCUMENTO = "Prácticas según el programa de la Universidad de Oriente"
AUTORIA = (
    "Prof. César Rodríguez \\textbar{} Universidad de Oriente, Núcleo de Sucre, "
    "Departamento de Física \\textbar{} Cumaná, abril de 2011"
)

# Orden canónico de las secciones que debe tener TODA práctica del documento.
SECCIONES_OBLIGATORIAS = ("objetivos", "teoria", "materiales", "procedimiento", "actividades")
# `experimental` es el contenedor «3. PARTE EXPERIMENTAL»: en el OCR algunas
# prácticas cuelgan de él contenido y figuras antes de 3.1/3.2, así que se
# renderiza también (entre teoría y materiales) aunque no es obligatoria.
ORDEN_SECCIONES = ("objetivos", "teoria", "experimental", "materiales", "procedimiento", "actividades")

ICONOS_SECCION = {
    "objetivos": "bullseye",
    "teoria": "book-open",
    "experimental": "flask",
    "materiales": "box-open",
    "procedimiento": "list-ol",
    "actividades": "calculator",
}
ETIQUETAS_SECCION = {
    "objetivos": "Objetivos",
    "teoria": "Fundamento teórico",
    "experimental": "Desarrollo experimental",
    "materiales": "Materiales y equipos",
    "procedimiento": "Procedimiento",
    "actividades": "Actividades",
}

RE_PRACTICA = re.compile(r"^\s*\*{0,2}PR[ÁA]CTICA\s+(\d+)\*{0,2}\s*$", re.I)
RE_ENCABEZADO = re.compile(r"^\s*\*{0,2}(\d+(?:\.\d+)*\.?)\s+(.+?)\s*$")
RE_PAGINA_HTML = re.compile(r"^<!--\s*pagina\s+\d+\s*-->\s*$", re.I)
RE_PAGINA_MD = re.compile(r"^##\s+Página\s+\d+\s*$", re.I)
RE_SOLO_NUMERO = re.compile(r"^\d{1,3}$")
RE_APENDICE = re.compile(r"^TABLAS?\s+(?:2|3)\b", re.I)
RE_SEPARADOR_TABLA = re.compile(r"^\s*:?-{2,}:?\s*$")
RE_BULLET = re.compile(r"^\s*(?:\*|•|-)\s+(.*)$")
RE_MARCA_SUB = re.compile(r"^@@SUB@@(.+)$")
RE_FIGURA_INLINE = re.compile(r"\[FIGURA:\s*(.+?)\]", re.I | re.S)


# ── Funciones puras de parseo ─────────────────────────────────────────────────


def limpiar_markdown(texto: str) -> str:
    """Quita las marcas de página y los números sueltos del OCR.

    Los números de página aparecen como líneas de uno a tres dígitos; los
    encabezados `## Página N` y `<!-- pagina N -->` son insertados por el OCR.
    Los ítems numerados (`1. En el instante...`) NO se tocan porque llevan
    punto y texto.
    """
    limpias: list[str] = []
    for linea in texto.splitlines():
        if RE_PAGINA_HTML.match(linea) or RE_PAGINA_MD.match(linea):
            continue
        if RE_SOLO_NUMERO.match(linea.strip()):
            continue
        limpias.append(linea.rstrip())
    return "\n".join(limpias).strip()


def seccion_canonica(titulo: str) -> str | None:
    """Mapea un encabezado del OCR a una sección canónica por su TITULO.

    Se mira el texto y no el número: el OCR numera de forma irregular (la
    práctica 4 usa 4./5. y la práctica 8 reinicia en 1.) y a veces pone el
    título en negrita dentro del número (`1. **PARTE EXPERIMENTAL**`).
    """
    t = titulo.replace("*", "").strip().rstrip(":.").upper()
    if not t:
        return None
    if "OBJETIVO" in t:
        return "objetivos"
    if "PARTE TEÓRICA" in t or "PARTE TEORICA" in t or t.startswith("TEOR"):
        return "teoria"
    if "PARTE EXPERIMENTAL" in t:
        return "experimental"
    if "MATERIAL" in t:
        return "materiales"
    if "PROCEDIMIENTO" in t or "MÉTODO" in t or "METODO" in t:
        return "procedimiento"
    if "ACTIVIDAD" in t:
        return "actividades"
    return None


def _es_titulo_encabezado(titulo: str) -> bool:
    """Un encabezado real va en MAYÚSCULAS; un ítem numerado no."""
    sin_math = re.sub(r"\$[^$]*\$", "", titulo)
    letras = [c for c in sin_math if c.isalpha()]
    return bool(letras) and all(c == c.upper() for c in letras)


def extraer_practicas(texto: str) -> dict[int, dict[str, Any]]:
    """Divide el markdown en las ocho prácticas y extrae título y secciones.

    El final de la práctica 8 se recorta donde empiezan las tablas de
    inventario (`TABLAS 2 y 3`), que no son parte de ningún enunciado.
    """
    lineas = limpiar_markdown(texto).splitlines()
    inicios = [
        (i, int(m.group(1)))
        for i, linea in enumerate(lineas)
        if (m := RE_PRACTICA.match(linea))
    ]
    if not inicios:
        return {}

    practicas: dict[int, dict[str, Any]] = {}
    for indice, (inicio, numero) in enumerate(inicios):
        fin = inicios[indice + 1][0] if indice + 1 < len(inicios) else len(lineas)
        cuerpo = lineas[inicio + 1 : fin]
        if numero == inicios[-1][1]:
            for desplazamiento, linea in enumerate(cuerpo):
                if RE_APENDICE.match(linea.strip()):
                    cuerpo = cuerpo[:desplazamiento]
                    break

        titulo_partes: list[str] = []
        claves_todas = set(SECCIONES_OBLIGATORIAS) | {"experimental"}
        secciones: dict[str, list[str]] = {k: [] for k in claves_todas}
        actual: str | None = None
        for linea in cuerpo:
            m = RE_ENCABEZADO.match(linea)
            if m and _es_titulo_encabezado(m.group(2)):
                canonica = seccion_canonica(m.group(2))
                if canonica:
                    actual = canonica
                    continue
                if actual:
                    secciones[actual].append("@@SUB@@" + m.group(2).replace("*", "").strip())
                    continue
            if actual is None:
                titulo_partes.append(linea.replace("*", "").strip())
            else:
                secciones[actual].append(linea)

        titulo = " ".join(p for p in titulo_partes if p)
        titulo = re.sub(r"\s+", " ", titulo).strip().rstrip(".")
        practicas[numero] = {"numero": numero, "titulo": titulo, "secciones": secciones}
    return practicas


# ── Funciones puras de renderizado ────────────────────────────────────────────


def _celda_tabla(valor: str) -> str:
    """Escapa una celda markdown conservando la matemática que traiga."""
    return _tm(valor.strip())


def _tabla_markdown(lineas: list[str], inicio: int) -> tuple[str, int]:
    """Convierte un bloque de filas `| ... |` en un `tabular` de LaTeX."""
    filas: list[list[str]] = []
    i = inicio
    while i < len(lineas) and lineas[i].strip().startswith("|"):
        cruda = lineas[i].strip().strip("|")
        celdas = [c.strip() for c in cruda.split("|")]
        if not all(RE_SEPARADOR_TABLA.match(c) for c in celdas):
            filas.append(celdas)
        i += 1
    if not filas:
        return "", i
    ancho = max(len(f) for f in filas)
    filas = [f + [""] * (ancho - len(f)) for f in filas]
    cabecera, *cuerpo = filas
    alineacion = "{" + "l" * ancho + "}"
    partes = [
        "\\begin{center}\\small",
        "\\begin{tabular}" + alineacion,
        "\\toprule",
        " & ".join(_celda_tabla(c) for c in cabecera) + r" \\",
        "\\midrule",
    ]
    partes.extend(" & ".join(_celda_tabla(c) for c in f) + r" \\" for f in cuerpo)
    partes.extend(["\\bottomrule", "\\end{tabular}", "\\end{center}"])
    return "\n".join(partes), i


def _separar_figuras_inline(texto: str) -> tuple[str, list[str]]:
    """Extrae marcadores `[FIGURA: ...]` incrustados en un párrafo.

    El OCR sometimes pega la descripción de una figura al final de un párrafo
    de prosa. Se devuelve el texto sin los marcadores y la lista de
    descripciones, para emitir cada una como caja y no perder la prosa.
    """
    descripciones = [m.group(1).strip() for m in RE_FIGURA_INLINE.finditer(texto)]
    limpio = RE_FIGURA_INLINE.sub("", texto)
    limpio = re.sub(r"\s+", " ", limpio).strip()
    return limpio, descripciones


def _caja_figura(descripcion: str) -> str:
    return (
        "\\begin{tcolorbox}[cajaContenido]"
        "\\textbf{Figura del original:} " + _tm(descripcion) +
        "\n\\end{tcolorbox}"
    )


def convertir_bloques(lineas: list[str]) -> str:
    """Convierte el cuerpo de una sección en bloques LaTeX.

    Reglas: viñetas → `itemize`; filas `|` → `tabular`; `[FIGURA: ...]` y
    `[ILEGIBLE]` → cajas de aviso;SUB → subencabezado; el resto → párrafos
    escapados con `_tm` (que conserva `$...$` y `\\[...\\]`).
    """
    bloques: list[str] = []
    i = 0
    while i < len(lineas):
        linea = lineas[i]
        texto = linea.strip()

        if not texto:
            i += 1
            continue

        if texto.startswith("|"):
            tabla, i = _tabla_markdown(lineas, i)
            if tabla:
                bloques.append(tabla)
            continue

        m_sub = RE_MARCA_SUB.match(texto)
        if m_sub:
            bloques.append(r"\subsection*{" + _tm(m_sub.group(1)) + "}")
            i += 1
            continue

        m_figura = re.fullmatch(r"\[FIGURA:\s*(.+)\]", texto, re.I | re.S)
        if m_figura:
            bloques.append(_caja_figura(m_figura.group(1)))
            i += 1
            continue

        if "[ILEGIBLE]" in texto:
            bloques.append(
                "\\begin{tcolorbox}[cajaMejora]"
                "\\textbf{Texto ilegible en el escaneo:} ver el PDF original."
                "\n\\end{tcolorbox}"
            )
            i += 1
            continue

        m_bullet = RE_BULLET.match(linea)
        if m_bullet:
            elementos: list[str] = []
            while i < len(lineas) and (mb := RE_BULLET.match(lineas[i])):
                elementos.append(mb.group(1).strip())
                i += 1
            bloques.append(_lista(elementos, entorno="itemize", math=True))
            continue

        parrafo = [texto]
        i += 1
        while i < len(lineas):
            siguiente = lineas[i].strip()
            if (not siguiente or siguiente.startswith("|") or RE_BULLET.match(lineas[i])
                    or RE_MARCA_SUB.match(siguiente)):
                break
            parrafo.append(siguiente)
            i += 1

        # El OCR pega a veces la descripción de una figura al final de un
        # párrafo; se extrae y se emite como caja sin perder la prosa.
        limpio, figs = _separar_figuras_inline(" ".join(parrafo))
        if limpio:
            bloques.append(_tm(limpio))
        bloques.extend(_caja_figura(f) for f in figs)

    return "\n\n".join(bloques)


def _documento(titulo: str, cuerpo: str) -> str:
    """Arma el LaTeX completo con el preámbulo infográfico canónico."""
    extra = [
        r"\renewcommand{\iconoBanda}{flask}",
        r"\fancyhead[L]{\footnotesize\color{grisTexto}\faIcon{flask}~" + TITULO_DOCUMENTO + "}",
        r"\fancyhead[R]{\footnotesize\color{grisTexto}" + titulo + "}",
        r"\hypersetup{pdftitle={" + titulo + "},pdfauthor={" + AUTORIA + "}}",
        "",
    ]
    return (
        PREAMBULO_INFOGRAFIA
        + "\n".join(extra)
        + "\n\\begin{document}\n"
        + banda_titulo(titulo, SUBTITULO_DOCUMENTO)
        + "\n\n"
        + r"\begin{center}\small\color{grisTexto}" + AUTORIA + r"\end{center}"
        + "\n\n"
        + cuerpo
        + "\n\\end{document}\n"
    )


def render_practica(practica: dict[str, Any]) -> str:
    """Renderiza una práctica parseada a LaTeX completo y determinista."""
    numero = practica["numero"]
    titulo = _tm(practica["titulo"])
    encabezado = f"Práctica {numero:02d} --- {titulo}"
    partes = [
        "\\begin{tcolorbox}[cajaContenido]"
        "\\textbf{Fuente:} enunciado del PDF original "
        "(Universidad de Oriente, Núcleo de Sucre, Departamento de Física, 2011)."
        "\n\\end{tcolorbox}"
    ]
    for clave in ORDEN_SECCIONES:
        cuerpo = convertir_bloques(practica["secciones"].get(clave, []))
        if not cuerpo:
            continue
        partes.append(seccion_con_icono(ICONOS_SECCION[clave], ETIQUETAS_SECCION[clave]))
        partes.append(cuerpo)
    return _documento(encabezado, "\n\n".join(partes))


# ── Validación ────────────────────────────────────────────────────────────────


def validar_matematica_ocr(texto: str, donde: str) -> list[str]:
    """Valida la matemática del OCR, consciente de display math `\\[...\\]`.

    `_validar_matematica` de `generar_material_curso.py` solo entiende `$...$`,
    pero el OCR escribe las ecuaciones largas como `\\[ ... \\]`: sus `_`/`^`
    son legítimos dentro de la barra invertida y no deben reportarse. Aquí se
    enmascaran primero los bloques `\\[...\\]` y luego los `$...$`, y solo se
    revisa lo que queda en modo texto.
    """
    problemas: list[str] = []
    s = str(texto)
    if s.count("$") % 2:
        problemas.append(f"{donde}: número impar de '$'")
        return problemas
    if s.count(r"\[") != s.count(r"\]"):
        problemas.append(f"{donde}: delimitadores `\\[ ... \\]` desbalanceados")

    enmascarado = re.sub(r"\\\[.*?\\\]", "", s, flags=re.S)
    enmascarado = re.sub(r"\$[^$]*\$", "", enmascarado)
    for i, seg in enumerate(enmascarado.split("$")):
        if seg.count("{") != seg.count("}"):
            problemas.append(f"{donde}: llaves desbalanceadas en «{seg[:40]}»")
    if re.search(r"[_^]", enmascarado):
        problemas.append(f"{donde}: '_' o '^' fuera de matemática en modo texto")
    return problemas


def validar_practicas(practicas: dict[int, dict[str, Any]], esperadas: list[int]) -> list[str]:
    """Valida cobertura, secciones y seguridad LaTeX sin compilar."""
    problemas: list[str] = []
    for numero in esperadas:
        if numero not in practicas:
            problemas.append(f"falta la práctica {numero} en el OCR")
            continue
        p = practicas[numero]
        if len(p["titulo"]) < 5:
            problemas.append(f"práctica {numero} sin título reconocible")
        for clave in SECCIONES_OBLIGATORIAS:
            if not any(l.strip() for l in p["secciones"].get(clave, [])):
                problemas.append(f"práctica {numero} sin sección {clave}")
        for clave, lineas in p["secciones"].items():
            for problema in validar_matematica_ocr("\n".join(lineas), f"P{numero}.{clave}"):
                problemas.append(problema)

    for numero, p in practicas.items():
        latex = render_practica(p)
        if "<!-- pagina" in latex or "## Página" in latex:
            problemas.append(f"práctica {numero} conserva marcas de página del OCR")
        if "[FIGURA" in latex or "[ILEGIBLE]" in latex:
            problemas.append(f"práctica {numero} conserva marcadores del OCR sin convertir")
        if latex.count(r"\begin{") != latex.count(r"\end{"):
            problemas.append(f"práctica {numero} tiene entornos LaTeX desbalanceados")
    return problemas


# ── Orquestación de la capa 3 ─────────────────────────────────────────────────


def parsear_rango(especificacion: str | None, total: int = 8) -> list[int]:
    """Convierte '1-8', '1,3,5-7' o None en una lista de números."""
    if not especificacion or especificacion.strip().lower() == "todas":
        return list(range(1, total + 1))
    numeros: set[int] = set()
    for parte in especificacion.split(","):
        parte = parte.strip()
        if not parte:
            continue
        if "-" in parte:
            ini, fin = parte.split("-", 1)
            numeros.update(range(int(ini), int(fin) + 1))
        else:
            numeros.add(int(parte))
    return sorted(n for n in numeros if 1 <= n <= total)


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def generar(
    ruta_ocr: Path,
    salida: Path,
    esperadas: list[int],
    compilar: bool = True,
) -> dict[str, Any]:
    """Genera, valida, escribe y (opcionalmente) compila las prácticas."""
    try:
        texto = ruta_ocr.read_text(encoding="utf-8")
    except OSError as exc:
        return {"status": "error", "code": 2, "message": f"no se pudo leer el OCR: {exc}"}

    practicas = extraer_practicas(texto)
    problemas = validar_practicas(practicas, esperadas)
    if problemas:
        return {
            "status": "error",
            "code": 3,
            "message": "estructura del OCR inválida",
            "problemas": problemas,
            "encontradas": sorted(practicas),
        }

    documentos = {n: render_practica(practicas[n]) for n in esperadas}
    salida.mkdir(parents=True, exist_ok=True)
    build = salida / ".build"
    artefactos: list[dict[str, Any]] = []
    errores: list[str] = []

    for numero in esperadas:
        contenido = documentos[numero]
        destino = salida / f"practica_{numero:02d}.tex"
        try:
            destino.write_text(contenido, encoding="utf-8")
        except OSError as exc:
            return {"status": "error", "code": 5, "message": f"no se pudo escribir {destino}: {exc}"}
        item: dict[str, Any] = {
            "numero": numero,
            "titulo": practicas[numero]["titulo"],
            "tex": str(destino),
            "sha256_16": _sha(contenido),
        }
        if compilar:
            with contextlib.redirect_stdout(io.StringIO()):
                resultado = compile_latex_code(
                    contenido, job_name=f"practica_{numero:02d}",
                    output_dir=str(build), clean=False,
                )
            log = build / f"practica_{numero:02d}.log"
            fallos = (
                re.findall(r"^! (.+)$", log.read_text(encoding="utf-8", errors="ignore"), re.M)
                if log.exists() else []
            )
            if not fallos and not resultado.get("success"):
                fallos = [resultado.get("error", "compilación fallida sin detalle")]
            pdf = build / f"practica_{numero:02d}.pdf"
            if not fallos and pdf.exists():
                (salida / f"practica_{numero:02d}.pdf").write_bytes(pdf.read_bytes())
                item["pdf"] = str(salida / f"practica_{numero:02d}.pdf")
            else:
                errores.append(f"P{numero}: " + "; ".join(fallos)[:200])
        artefactos.append(item)

    if errores:
        return {
            "status": "error",
            "code": 4,
            "message": "falló la compilación de una o más prácticas",
            "errores": errores,
            "artefactos": artefactos,
        }
    return {
        "status": "ok",
        "code": 0,
        "ocr": str(ruta_ocr),
        "salida": str(salida),
        "practicas": len(esperadas),
        "compiladas": compilar,
        "artefactos": artefactos,
        "sha_conjunto": _sha("".join(documentos[n] for n in esperadas)),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Genera las 8 prácticas de Lab II desde el markdown del OCR"
    )
    ap.add_argument("--ocr", default=str(OCR_POR_DEFECTO), help="markdown del OCR")
    ap.add_argument("--salida", default=str(SALIDA_POR_DEFECTO), help="directorio de salida")
    ap.add_argument("--practicas", default=None, help="'1-8', '1,3,5-7' o 'todas'")
    ap.add_argument("--sin-compilar", action="store_true", help="solo escribir los .tex")
    ap.add_argument("--check", action="store_true", help="solo validar el OCR, sin escribir")
    ap.add_argument("--json", action="store_true", help="emitir informe JSON")
    args = ap.parse_args(argv)

    ruta_ocr = Path(args.ocr).resolve()
    salida = Path(args.salida).resolve()
    try:
        esperadas = parsear_rango(args.practicas)
    except ValueError:
        print("rango de prácticas inválido", file=sys.stderr)
        return 1

    texto = ruta_ocr.read_text(encoding="utf-8") if ruta_ocr.is_file() else ""
    if not texto:
        print(json.dumps({"status": "error", "code": 2,
                          "message": f"no existe o está vacío: {ruta_ocr}"},
                         ensure_ascii=False), file=sys.stderr)
        return 2

    if args.check:
        encontradas = extraer_practicas(texto)
        problemas = validar_practicas(encontradas, esperadas)
        informe = {
            "status": "ok" if not problemas else "error",
            "ocr": str(ruta_ocr),
            "encontradas": sorted(encontradas),
            "problemas": problemas,
        }
        print(json.dumps(informe, ensure_ascii=False, indent=2))
        return 0 if not problemas else 3

    informe = generar(ruta_ocr, salida, esperadas, compilar=not args.sin_compilar)
    if args.json:
        print(json.dumps(informe, ensure_ascii=False, indent=2))
    else:
        if informe.get("status") == "ok":
            print(f"OK: {informe['practicas']} prácticas en {informe['salida']} "
                  f"(sha {informe['sha_conjunto']})")
        else:
            print(informe.get("message", "error"), file=sys.stderr)
            for detalle in informe.get("problemas", []) + informe.get("errores", []):
                print(" - " + detalle, file=sys.stderr)
    return int(informe.get("code", 1))


if __name__ == "__main__":
    sys.exit(main())
