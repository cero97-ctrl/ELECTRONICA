#!/usr/bin/env python3
r"""
generar_guia_teorica.py — Guía teórica de una semana (Layer 3: Execution)

Emite material de ESTUDIO para una semana del curso: objetivo y contenidos del
descriptor, desarrollo de los temas declarados en `semanas[N].teoria` (cada uno
con explicación, ideas clave, comandos de ejemplo y errores frecuentes), un mapa
rápido de primitivas, checklist y el glosario de la semana. No emite preguntas:
las evaluaciones teóricas viven en `evaluaciones/teorica_semana_NN_grupo_N.*`.

Uso:
    python3 execution/generar_guia_teorica.py --curso cursos/CYBERSEGURIDAD/curso.yaml --semana 2
    python3 execution/generar_guia_teorica.py --curso <yaml> --semana 2 --sin-compilar
    python3 execution/generar_guia_teorica.py --curso <yaml> --semana 2 --json

Salida (stdout, JSON):
    {"status": "ok", "semana": 2, "tex": "...", "pdf": "...", "errores": [], "overfull": 0}

Códigos de salida:
    0 — guía generada y verificada
    1 — argumentos de línea de comandos inválidos
    2 — descriptor ilegible o que no es YAML
    3 — semana inexistente o sin `teoria:` completa
    4 — error de compilación LaTeX (se conserva el .log)
    5 — error de escritura en disco

Determinismo: el contenido depende solo del descriptor. La fecha del PDF se fija
con `meta.fecha_iso` (SOURCE_DATE_EPOCH); no se usa `datetime.now()` en el
documento. Mismo descriptor → mismos bytes del `.tex` y del `.pdf`.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

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
    FUENTE_FECHA,
    _epoch,
    _lista,
    _metadatos_curso,
    _n,
    _slug,
    _t,
    _tabla_datos,
)

EXIT_OK = 0
EXIT_USO = 1
EXIT_DESCRIPTOR = 2
EXIT_INVALIDO = 3
EXIT_LATEX = 4
EXIT_DISCO = 5

# Un `tabcolsep` a cada lado por columna: misma cuenta que usan los generadores
# de material del curso para decidir si una tabla cabe en el margen.
TABCOSEP_CM = 0.45
ANCHO_UTIL_CM = 16.6


def cargar_descriptor(curso: Path) -> dict[str, Any]:
    """Carga el descriptor YAML del curso.

    Args:
        curso: Ruta al `curso.yaml`.

    Returns:
        Descriptor como diccionario.

    Raises:
        ValueError: si el fichero no existe o no es un mapa YAML.
    """
    if not curso.exists():
        raise ValueError(f"no existe el descriptor {curso}")
    try:
        datos = yaml.safe_load(curso.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"el descriptor no es YAML válido: {exc}") from exc
    if not isinstance(datos, dict):
        raise ValueError("el descriptor no es un mapa YAML")
    return datos


def semana_de(datos: dict[str, Any], numero: int) -> dict[str, Any]:
    """Devuelve el bloque de la semana pedida.

    Args:
        datos: Descriptor del curso.
        numero: Número de semana.

    Returns:
        Bloque de la semana.

    Raises:
        ValueError: si la semana no existe.
    """
    for semana in datos.get("semanas") or []:
        if isinstance(semana, dict) and int(semana.get("numero", 0)) == numero:
            return semana
    raise ValueError(f"la semana {numero} no existe en el descriptor")


def _textos_validos(valor: Any) -> bool:
    """Comprueba que una lista declarada en YAML sea de texto, no de mapas."""
    return isinstance(valor, list) and all(isinstance(item, str) and item.strip() for item in valor)


def validar_guia(datos: dict[str, Any], numero: int) -> list[str]:
    """Comprueba que la semana tenga todo lo que la guía afirma.

    Args:
        datos: Descriptor del curso.
        numero: Número de semana.

    Returns:
        Lista de problemas; vacía si la guía es emitible.
    """
    problemas: list[str] = []
    meta = datos.get("meta") or {}
    for clave in ("codigo", "titulo", "autor", "fecha", "fecha_iso"):
        if not meta.get(clave):
            problemas.append(f"meta.{clave} es obligatorio para emitir la guía")

    try:
        semana = semana_de(datos, numero)
    except ValueError as exc:
        return problemas + [str(exc)]

    for clave in ("titulo", "objetivo"):
        if not semana.get(clave):
            problemas.append(f"semana {numero}: falta {clave}")
    if not _textos_validos(semana.get("contenidos")):
        problemas.append(f"semana {numero}: contenidos debe ser una lista de textos no vacíos")

    teoria = semana.get("teoria")
    if not isinstance(teoria, dict):
        problemas.append(
            f"semana {numero}: falta el bloque teoria: con introduccion, temas y checklist"
        )
        return problemas

    if not isinstance(teoria.get("introduccion"), str) or not teoria["introduccion"].strip():
        problemas.append(f"semana {numero}: falta teoria.introduccion")
    if not _textos_validos(teoria.get("checklist")):
        problemas.append(f"semana {numero}: teoria.checklist debe ser una lista de textos")
    if teoria.get("cierre") is not None and not isinstance(teoria["cierre"], str):
        problemas.append(f"semana {numero}: teoria.cierre debe ser texto")

    temas = teoria.get("temas")
    if not isinstance(temas, list) or not temas:
        problemas.append(f"semana {numero}: teoria.temas debe ser una lista no vacía")
    else:
        for indice, tema in enumerate(temas, 1):
            if not isinstance(tema, dict):
                problemas.append(f"semana {numero}: el tema {indice} no es un mapa")
                continue
            for clave in ("titulo", "explicacion"):
                if not isinstance(tema.get(clave), str) or not tema[clave].strip():
                    problemas.append(f"semana {numero}: falta teoria.temas[{indice}].{clave}")
            for clave in ("puntos", "errores"):
                if not _textos_validos(tema.get(clave)):
                    problemas.append(
                        f"semana {numero}: teoria.temas[{indice}].{clave} debe ser una lista de textos"
                    )
            if tema.get("comandos") is not None and not isinstance(tema["comandos"], str):
                problemas.append(
                    f"semana {numero}: teoria.temas[{indice}].comandos debe ser texto (bloque | de YAML)"
                )

    tabla = teoria.get("tabla")
    if tabla is not None:
        if not isinstance(tabla, dict):
            problemas.append(f"semana {numero}: teoria.tabla debe ser un mapa")
        else:
            columnas = tabla.get("columnas") or []
            if not _textos_validos(columnas):
                problemas.append(f"semana {numero}: teoria.tabla.columnas debe ser una lista de textos")
            anchos = tabla.get("anchos") or []
            if len(anchos) != len(columnas):
                problemas.append(
                    f"semana {numero}: teoria.tabla declara {len(anchos)} anchos "
                    f"para {len(columnas)} columnas"
                )
            else:
                try:
                    total = sum(float(a) for a in anchos) + TABCOSEP_CM * len(columnas)
                    if total > ANCHO_UTIL_CM:
                        problemas.append(
                            f"semana {numero}: los anchos de teoria.tabla suman "
                            f"{total:.2f} cm y no caben en el margen"
                        )
                except (TypeError, ValueError):
                    problemas.append(f"semana {numero}: teoria.tabla.anchos debe ser numérico")
            filas = tabla.get("filas") or []
            if not isinstance(filas, list) or not filas:
                problemas.append(f"semana {numero}: teoria.tabla.filas debe ser una lista no vacía")
            else:
                for fila in filas:
                    if not isinstance(fila, list) or len(fila) != len(columnas):
                        problemas.append(
                            f"semana {numero}: una fila de teoria.tabla no tiene "
                            f"{len(columnas)} celdas"
                        )
                    elif not all(isinstance(celda, str) for celda in fila):
                        problemas.append(
                            f"semana {numero}: una celda de teoria.tabla no es texto "
                            "(falta entrecomillar 'No', 'Sí', 'On' u 'Off')"
                        )

    catalogo: dict[str, str] = {}
    for entrada in datos.get("glosario") or []:
        if not isinstance(entrada, dict):
            problemas.append(f"glosario: una entrada no es un mapa ({entrada!r})")
            continue
        termino = str(entrada.get("termino", "")).strip()
        definicion = str(entrada.get("definicion", "")).strip()
        if not termino or not definicion:
            problemas.append(f"glosario: entrada incompleta ({entrada!r})")
            continue
        if termino in catalogo:
            problemas.append(f"glosario: el término {termino!r} está repetido")
        catalogo[termino] = definicion

    elegidos = semana.get("glosario") or []
    if not isinstance(elegidos, list):
        problemas.append(f"semana {numero}: glosario debe ser una lista de términos")
    else:
        for termino in elegidos:
            if not isinstance(termino, str):
                problemas.append(f"semana {numero}: término de glosario no textual ({termino!r})")
            elif termino not in catalogo:
                problemas.append(
                    f"semana {numero}: el término {termino!r} no está en el glosario del curso"
                )
    return problemas


def _glosario(datos: dict[str, Any], semana: dict[str, Any]) -> list[tuple[str, str]]:
    """Resuelve los términos de la semana contra el glosario del curso."""
    catalogo = {
        str(entrada.get("termino", "")).strip(): str(entrada.get("definicion", "")).strip()
        for entrada in datos.get("glosario") or []
        if isinstance(entrada, dict)
    }
    return [
        (nombre, catalogo[nombre])
        for nombre in semana.get("glosario") or []
        if isinstance(nombre, str) and nombre in catalogo
    ]


def _bloque_comandos(comandos: str) -> str:
    """Bloque de comandos en el estilo de código del repo."""
    return (
        "\\begin{lstlisting}[style=estiloCodigo]\n"
        + comandos.strip("\n")
        + "\n\\end{lstlisting}"
    )


def _tabla_primitivas(tabla: dict[str, Any]) -> str:
    """Tabla comparativa con anchos fijos, en `\footnotesize`."""
    columnas = [_t(str(c)) for c in tabla.get("columnas") or []]
    if not columnas:
        return ""
    anchos = [float(a) for a in tabla.get("anchos") or []]
    if len(anchos) != len(columnas):
        ancho = max(1.0, (16.0 - TABCOSEP_CM * len(columnas)) / len(columnas))
        anchos = [ancho for _ in columnas]
    especificacion = "".join(
        r">{\raggedright\arraybackslash}p{" + f"{a:.2f}" + "cm}" for a in anchos
    )
    cuerpo = "\n".join(
        " & ".join(_t(str(celda)) for celda in fila) + r" \\"
        for fila in tabla.get("filas") or []
    )
    partes = [
        r"\begin{center}",
        r"\begin{minipage}{\linewidth}",
        r"\centering",
        r"{\footnotesize",
    ]
    if tabla.get("titulo"):
        partes.append(r"\textbf{" + _t(str(tabla["titulo"])) + r"}\par\smallskip")
    partes.extend(
        [
            r"\begin{tabular}{@{}" + especificacion + "@{}}",
            r"\toprule",
            " & ".join(r"\textbf{" + c + "}" for c in columnas) + r" \\",
            r"\midrule",
            cuerpo,
            r"\bottomrule",
            r"\end{tabular}",
            "}",
        ]
    )
    if tabla.get("nota"):
        partes.append(r"\par\smallskip{\footnotesize " + _t(str(tabla["nota"])) + "}")
    partes.extend([r"\end{minipage}", r"\end{center}"])
    return "\n".join(partes)


def documento_guia(meta: dict[str, Any], cuerpo: str) -> str:
    """Envuelve el cuerpo con EL preámbulo compartido del repo.

    El preámbulo no se duplica: viene de `estilo_infografia.py`. La cabecera y
    los metadatos del PDF se derivan de `meta`, nunca de la hora del sistema.
    """
    titulo = _t(meta["titulo"])
    icono = re.sub(r"[^a-z0-9-]", "", str(meta.get("icono") or "shield-alt").lower()) or "shield-alt"
    extra = "\n".join(
        [
            r"\renewcommand{\iconoBanda}{" + icono + "}",
            r"\fancyhead[L]{\footnotesize\color{grisTexto}\faIcon{" + icono + "}~" + _t(meta["codigo"]) + "}",
            r"\fancyhead[R]{\footnotesize\color{grisTexto}Guía teórica}",
            r"\hypersetup{pdftitle={" + titulo + "},pdfauthor={" + _t(meta["autor"]) + "}",
            r"  pdfsubject={" + _t(meta["codigo"]) + "}}",
            "",
        ]
    )
    return (
        PREAMBULO_INFOGRAFIA
        + extra
        + "\n\\begin{document}\n"
        + cuerpo
        + "\n\\end{document}\n"
    )


def tex_guia(datos: dict[str, Any], numero: int) -> str:
    """Compone la guía teórica de una semana desde el descriptor validado."""
    meta = datos["meta"]
    semana = semana_de(datos, numero)
    teoria = semana["teoria"]

    partes: list[str] = [
        banda_titulo(
            _t(f"Guía teórica --- Semana {numero:02d}"),
            _t(f"{semana['titulo']} --- material de estudio"),
        ),
        _metadatos_curso(meta),
        _tabla_datos(
            [
                ("Curso", _t(f"{meta['codigo']} --- {meta['titulo']}")),
                ("Semana", _t(f"{numero:02d} de {meta.get('semanas', '')}")),
                ("Dedicación", _t(str(meta.get("dedicacion_semanal", "")))),
                ("Propósito", _t("Estudio y comprensión; la evaluación es aparte")),
            ]
        ),
        seccion_con_icono("book-open", "Cómo usar esta guía"),
        _t(teoria["introduccion"]),
        "\\begin{cajaConcepto}"
        + r"\textbf{No es un examen.} "
        + _t(
            "Aquí se explica el porqué de cada decisión. Las evaluaciones teóricas "
            "por grupo se emiten por separado; esta guía es el material para "
            "prepararlas y para entender la práctica de la semana."
        )
        + "\n\\end{cajaConcepto}",
        seccion_con_icono("bullseye", "Objetivo de la semana"),
        _t(semana["objetivo"]),
        seccion_con_icono("clipboard-list", "Contenidos que se estudian"),
        _lista([str(c) for c in semana["contenidos"]]),
        seccion_con_icono("brain", "Desarrollo de los temas"),
    ]

    for indice, tema in enumerate(teoria["temas"], 1):
        partes.append("\\needspace{6\\baselineskip}")
        partes.append("\\subsection{" + _t(f"{indice}. {tema['titulo']}") + "}")
        partes.append(_t(tema["explicacion"]))
        partes.append(r"\textbf{Ideas clave}")
        partes.append(_lista([str(p) for p in tema["puntos"]]))
        if tema.get("comandos"):
            partes.append(r"\textbf{Comandos de ejemplo}")
            partes.append(_bloque_comandos(str(tema["comandos"])))
        partes.append(r"\textbf{Errores frecuentes}")
        partes.append(_lista([str(e) for e in tema["errores"]]))

    if teoria.get("tabla"):
        partes.append("\\needspace{8\\baselineskip}")
        partes.append(seccion_con_icono("table", "Mapa rápido"))
        partes.append(_tabla_primitivas(teoria["tabla"]))

    partes.append(seccion_con_icono("clipboard-check", "Checklist antes de la práctica"))
    partes.append(_lista([str(c) for c in teoria["checklist"]]))

    glosario = _glosario(datos, semana)
    if glosario:
        partes.append("\\clearpage")
        partes.append(seccion_con_icono("book", "Glosario de la semana"))
        partes.append(
            "\\small\n"
            "\\begin{longtable}{@{}>{\\raggedright\\arraybackslash}p{4.2cm}"
            ">{\\raggedright\\arraybackslash}p{\\dimexpr\\linewidth-4.2cm-12pt\\relax}@{}}\n"
            "\\toprule\n\\textbf{Término} & \\textbf{Definición}\\\\\n"
            "\\midrule\n\\endhead\n\\bottomrule\n\\endlastfoot\n"
            + "\n".join(f"\\textbf{{{_t(t)}}} & {_t(d)}\\\\" for t, d in glosario)
            + "\n\\end{longtable}"
        )

    if teoria.get("cierre"):
        partes.append(
            "\\begin{cajaRecuerda}"
            + _t(teoria["cierre"])
            + "\n\\end{cajaRecuerda}"
        )

    return documento_guia(meta, "\n\n".join(partes))


def compilar_guia(
    contenido: str, job: str, build: Path, destino: Path
) -> dict[str, Any]:
    """Compila aislado, lee el `.log` y copia el PDF junto al `.tex`.

    Args:
        contenido: Documento LaTeX completo.
        job: Nombre del job (sin extensión).
        build: Directorio aislado `.tmp/latex_build/<job>/`.
        destino: Ruta del `.tex` final; su hermano `.pdf` es el destino del PDF.

    Returns:
        Diccionario con `pdf`, `errores` (`^! ` del log) y `overfull`.
    """
    build.mkdir(parents=True, exist_ok=True)
    with contextlib.redirect_stdout(io.StringIO()):
        salida = compile_latex_code(
            contenido, job_name=job, output_dir=str(build), clean=False
        )

    log_path = build / f"{job}.log"
    log = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
    errores = re.findall(r"^! (.+)$", log, re.M)
    overfull = len(re.findall(r"Overfull \\hbox", log))

    resultado: dict[str, Any] = {"pdf": None, "errores": errores, "overfull": overfull}
    pdf = build / f"{job}.pdf"
    if salida.get("success") and pdf.exists() and not errores:
        shutil.copy2(pdf, destino.with_suffix(".pdf"))
        resultado["pdf"] = str(destino.with_suffix(".pdf"))
    elif not errores:
        resultado["errores"] = [salida.get("error", "compilación fallida sin detalle")]
    return resultado


def generar(
    datos: dict[str, Any], numero: int, salida: Path, compilar: bool
) -> tuple[Path, dict[str, Any]]:
    """Escribe y, si se pide, compila la guía de una semana."""
    meta = datos["meta"]
    _slug(meta["codigo"])  # validado por el generador de material; se mantiene la interfaz
    job = f"teoria_{numero:02d}"
    salida.mkdir(parents=True, exist_ok=True)
    build = RAIZ / ".tmp" / "latex_build" / job
    os.environ[FUENTE_FECHA] = str(_epoch(meta))

    contenido = tex_guia(datos, numero)
    tex = salida / f"{job}.tex"
    tex.write_text(contenido, encoding="utf-8")
    artefacto: dict[str, Any] = {
        "job": job,
        "tex": str(tex),
        "pdf": None,
        "errores": [],
        "overfull": 0,
    }
    if compilar:
        artefacto.update(compilar_guia(contenido, job, build, tex))
    return tex, artefacto


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada del generador."""
    parser = argparse.ArgumentParser(
        description="Genera la guía teórica de estudio de una semana del curso."
    )
    parser.add_argument("--curso", required=True, help="Ruta al descriptor curso.yaml")
    parser.add_argument("--semana", required=True, type=int, help="Número de semana")
    parser.add_argument("--salida", default=None, help="Directorio de salida (por defecto <curso>/docs)")
    parser.add_argument("--sin-compilar", action="store_true", help="Escribe el .tex sin invocar pdflatex")
    parser.add_argument("--json", action="store_true", help="Emite un único objeto JSON")
    args = parser.parse_args(argv)

    curso = Path(args.curso).resolve()
    try:
        datos = cargar_descriptor(curso)
    except ValueError as exc:
        print(json.dumps({"status": "error", "problemas": [str(exc)]}, ensure_ascii=False), file=sys.stderr)
        return EXIT_DESCRIPTOR

    problemas = validar_guia(datos, args.semana)
    if problemas:
        print(json.dumps({"status": "invalido", "problemas": problemas}, ensure_ascii=False, indent=2))
        return EXIT_INVALIDO

    salida = Path(args.salida).resolve() if args.salida else curso.parent / "docs"
    try:
        _, artefacto = generar(datos, args.semana, salida, not args.sin_compilar)
    except OSError as exc:
        print(json.dumps({"status": "error", "problemas": [str(exc)]}, ensure_ascii=False), file=sys.stderr)
        return EXIT_DISCO

    salida_json = {
        "status": "ok",
        "semana": args.semana,
        "tex": artefacto["tex"],
        "pdf": artefacto["pdf"],
        "errores": artefacto["errores"],
        "overfull": artefacto["overfull"],
    }
    print(json.dumps(salida_json, ensure_ascii=False, indent=2))
    return EXIT_LATEX if artefacto["errores"] else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
