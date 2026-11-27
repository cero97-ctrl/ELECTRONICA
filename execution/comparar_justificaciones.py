#!/usr/bin/env python3
r"""
comparar_justificaciones.py — Capa 3: tabla privada de apoyo a la revisión docente.

Propósito deliberadamente limitado: poner frente a frente, para CADA pregunta y
CADA estudiante, el texto que escribió el alumno y la explicación de referencia
que ya existe en el `*_original_con_respuestas.md`. La tabla **no decide** si la
justificación está bien o mal, **no calcula nota** y **no publica nada**: deja una
columna en blanco para que el profesor escriba su veredicto.

Reutiliza, sin duplicarlas, las reglas ya existentes:
  - `descargar_resultados`: descarga/lectura del repo privado, validación del
    archivo contra la clave vigente, detección de copias, orden y escape LaTeX.
  - `md_a_html`: lectura de la fuente, su clave y la lista de ítems exigidos.

La salida lleva nombres, cédulas y la clave, así que sólo se escribe en rutas
ignoradas por git (la misma barrera que el acta). Sin fechas ni "ahora": el mismo
contenido de entregas produce los mismos bytes.

Uso:
    python3 execution/comparar_justificaciones.py --check
    python3 execution/comparar_justificaciones.py --json
    python3 execution/comparar_justificaciones.py --local .tmp/resultados --sin-pdf

Códigos: 0 ok · 1 E/S · 3 fuente/ruta inválida · 4 red/credenciales ·
5 hubo entregas archivadas inválidas (se omiten de la tabla y se informa).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import sys
import urllib.error
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "execution"))

import descargar_resultados as D  # noqa: E402  (barrera, validación y descarga)
import md_a_html as M  # noqa: E402  (única lectura de la fuente y su clave)

EXIT_OK = 0
EXIT_IO = 1
EXIT_DATOS = 3
EXIT_RED = 4
EXIT_INVALIDOS = 5

PREGUNTA_RE = re.compile(r"(?m)^## Pregunta (\d+)\s*$")
RESPUESTA_RE = re.compile(r"(?m)^\*\*Respuesta:\*\*\s*(.*)$")
EXPLICACION_RE = re.compile(r"^\*\*Explicación:\*\*\s*$")
OPCION_EXP_RE = re.compile(r"^-\s*([A-E])\s*([✓✗])\s*(.*)$")
SEMANA = "SEMANA_02"


class ComparacionError(Exception):
    def __init__(self, mensaje: str, code: int = EXIT_DATOS):
        super().__init__(mensaje)
        self.code = code


# --------------------------------------------------------------------------- #
# Funciones puras (sin red): las prueba execution/test_comparar_justificaciones.py
# --------------------------------------------------------------------------- #
def extraer_referencias(texto: str) -> dict[int, dict]:
    """Extrae `Respuesta` y las razones ✓/✗ de cada pregunta del original privado."""
    partes = PREGUNTA_RE.split(texto)
    if len(partes) < 3:
        raise ComparacionError("no hay preguntas `## Pregunta N` en el original")
    referencias: dict[int, dict] = {}
    for indice in range(1, len(partes), 2):
        numero = int(partes[indice])
        bloque = partes[indice + 1]
        respuesta = RESPUESTA_RE.search(bloque)
        if respuesta is None:
            raise ComparacionError(f"pregunta {numero}: falta `**Respuesta:**`")
        razones: list[dict] = []
        dentro = False
        for linea in bloque.splitlines():
            if EXPLICACION_RE.match(linea.strip()):
                dentro = True
                continue
            if not dentro:
                continue
            opcion = OPCION_EXP_RE.match(linea.strip())
            if opcion:
                razones.append(
                    {
                        "letra": opcion.group(1),
                        "correcta": opcion.group(2) == "✓",
                        "texto": opcion.group(3).strip(),
                    }
                )
            elif razones and not linea.strip():
                continue
        if not razones:
            raise ComparacionError(
                f"pregunta {numero}: falta la `**Explicación:**` con razones `- X ✓/✗`"
            )
        referencias[numero] = {
            "respuesta": respuesta.group(1).strip(),
            "razones": razones,
        }
    numeros = sorted(referencias)
    if numeros != list(range(1, len(numeros) + 1)):
        raise ComparacionError(f"numeración no consecutiva en el original: {numeros}")
    return referencias


def _plano(texto: Any) -> str:
    """Una sola línea, sin backticks: celdas de tabla deterministas."""
    return " ".join(("" if texto is None else str(texto)).replace("`", "").split())


def celda_md(texto: Any) -> str:
    return _plano(texto).replace("|", r"\|")


def celda_tex(texto: Any) -> str:
    crudo = _plano(texto).replace("✓", "(correcta)").replace("✗", "(descartada)")
    return D._tex(crudo)


def referencia_md(referencia: dict) -> str:
    razones = " · ".join(
        f"{r['letra']} {'✓' if r['correcta'] else '✗'} {r['texto']}"
        for r in referencia["razones"]
    )
    return f"Respuesta: {referencia['respuesta']} — {razones}"


def referencia_tex(referencia: dict) -> str:
    razones = r"\newline".join(
        f"\\textbf{{{r['letra']}}} "
        + (
            r"\textcolor{verdeSignal}{\faIcon{check}} "
            if r["correcta"]
            else r"\textcolor{rojoAlerta}{\faIcon{times}} "
        )
        + celda_tex(r["texto"])
        for r in referencia["razones"]
    )
    return r"\textbf{Respuesta:} " + celda_tex(referencia["respuesta"]) + r"\newline" + razones


def armar_filas(cuestionarios: list[dict]) -> list[dict]:
    """Una fila por (cuestionario, estudiante, pregunta exigida). Sin juicios."""
    filas: list[dict] = []
    for cuestionario in sorted(cuestionarios, key=lambda c: c["id"]):
        items = sorted(cuestionario["items"])
        referencias = cuestionario["referencias"]
        for numero in items:
            if numero not in referencias:
                raise ComparacionError(
                    f"{cuestionario['id']}: la pregunta {numero} no tiene explicación "
                    "de referencia; no se puede comparar a ciegas"
                )
        for registro in D.ordenar(cuestionario["registros"]):
            justificaciones = registro.get("justificaciones") or {}
            respuestas = cuestionario["respuestas_por_archivo"].get(
                registro["archivo"], {}
            )
            avisos = registro.get("avisos") or []
            for numero in items:
                texto = justificaciones.get(str(numero), "")
                estado = "ok" if texto else "sin texto"
                if any(
                    f"pregunta {numero}" in str(a) and "idéntica" in str(a)
                    for a in avisos
                ):
                    estado = "copiada"
                filas.append(
                    {
                        "cuestionario": cuestionario["id"],
                        "titulo": cuestionario["titulo"],
                        "grupo": registro["grupo"],
                        "cedula": registro["cedula"],
                        "nombre": registro["nombre"],
                        "pregunta": numero,
                        "respuesta": respuestas.get(str(numero), ""),
                        "justificacion": texto,
                        "referencia": referencias[numero],
                        "estado": estado,
                    }
                )
    return filas


def markdown_tabla(filas: list[dict], cuestionarios: list[dict]) -> str:
    lineas = [
        "# Comparativa de justificaciones — uso docente, privado",
        "",
        "> No califica ni decide: muestra el texto del estudiante frente a la "
        "explicación de referencia. El veredicto lo escribe el profesor.",
        f"> filas: {len(filas)}",
        "",
    ]
    for cuestionario in sorted(cuestionarios, key=lambda c: c["id"]):
        propias = [f for f in filas if f["cuestionario"] == cuestionario["id"]]
        lineas += [
            f"## {celda_md(cuestionario['titulo'])} — `{cuestionario['id']}`",
            "",
        ]
        if not propias:
            lineas += ["Sin entregas archivadas.", ""]
            continue
        lineas += [
            "| Estudiante | Cédula | P | Respuesta | Justificación del estudiante | Referencia (clave y porqué) | Estado | Veredicto docente |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for f in propias:
            lineas.append(
                "| "
                + " | ".join(
                    [
                        celda_md(f["nombre"]),
                        celda_md(f["cedula"]),
                        str(f["pregunta"]),
                        celda_md(f["respuesta"]) or "—",
                        celda_md(f["justificacion"]) or "—",
                        celda_md(referencia_md(f["referencia"])),
                        f["estado"],
                        "",
                    ]
                )
                + " |"
            )
        lineas.append("")
    return "\n".join(lineas).rstrip() + "\n"


def latex_tabla(filas: list[dict], cuestionarios: list[dict]) -> str:
    from execution.estilo_infografia import PREAMBULO_INFOGRAFIA

    secciones: list[str] = []
    for cuestionario in sorted(cuestionarios, key=lambda c: c["id"]):
        propias = [f for f in filas if f["cuestionario"] == cuestionario["id"]]
        filas_tex: list[str] = []
        for f in propias:
            celdas = [
                celda_tex(f["nombre"]),
                celda_tex(f["cedula"]),
                str(f["pregunta"]),
                celda_tex(f["respuesta"]) or "--",
                celda_tex(f["justificacion"]) or "--",
                referencia_tex(f["referencia"]),
                f["estado"],
                r"\underline{\hspace{0.9cm}}",
            ]
            filas_tex.append(" & ".join(celdas) + r" \\")
        tabla = "\n".join(filas_tex) if filas_tex else (
            r"\multicolumn{8}{c}{\textit{Sin entregas archivadas}} \\"
        )
        secciones.append(
            r"\section*{" + celda_tex(cuestionario["titulo"]) + "}"
            "\n"
            r"{\footnotesize \texttt{" + celda_tex(cuestionario["id"]) + r"}}"
            "\n"
            r"\begin{longtable}{@{}p{2.2cm} c c c p{4.6cm} p{4.7cm} c c@{}}"
            "\n\\toprule\n"
            r"\textbf{Estudiante} & \textbf{Cédula} & \textbf{P} & \textbf{R} "
            r"& \textbf{Justificación del estudiante} & \textbf{Referencia (clave y porqué)} "
            r"& \textbf{Edo} & \textbf{V} \\"
            "\n\\midrule\n\\endhead\n"
            + tabla
            + "\n\\bottomrule\n\\end{longtable}\n"
        )

    total = len(filas)
    return (
        PREAMBULO_INFOGRAFIA
        + r"""
\begin{document}
\bandaTitulo{COMPARATIVA DE JUSTIFICACIONES}{Uso docente privado · la tabla no califica}
\begin{tcolorbox}[cajaContenido, title={Cómo usar esta tabla}]
\textbf{E}: estudiante · \textbf{P}: pregunta · \textbf{R}: respuesta elegida ·
\textbf{Justificación}: texto enviado por el estudiante · \textbf{Referencia}:
respuesta correcta y explicación del original privado · \textbf{Edo}: estado formal
(ok / sin texto / copiada) · \textbf{V}: veredicto, en blanco para que lo escriba
el profesor. La fila \textit{copiada} se marca por similitud con otro estudiante;
no implica que la explicación sea correcta ni incorrecta.
\end{tcolorbox}

Filas: """
        + str(total)
        + r""" (estudiantes $\times$ preguntas exigidas). Fuente: entregas archivadas
y originales con explicación, ambos privados. Sin nota: la nota definitiva la fija
el profesor tras leer cada par.

\small\setlength{\tabcolsep}{3pt}
"""
        + "\n".join(secciones)
        + r"""
\end{document}
"""
    )


# --------------------------------------------------------------------------- #
# Entrada y salida
# --------------------------------------------------------------------------- #
def cargar_cuestionario(fuente: Path) -> dict:
    try:
        datos = M.cargar_clave(
            fuente, fuente.with_name(f"{fuente.stem}_respuestas.md")
        )
    except (OSError, ValueError) as exc:
        raise ComparacionError(f"fuente inválida {fuente}: {exc}", EXIT_DATOS) from exc
    original = fuente.with_name(f"{fuente.stem}_original_con_respuestas.md")
    try:
        referencias = extraer_referencias(original.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ComparacionError(
            f"no se pudo leer el original con explicaciones {original}: {exc}", EXIT_IO
        ) from exc
    items = sorted(datos["justificacion_items"])
    if not items:
        raise ComparacionError(
            f"{fuente.name}: la fuente no declara `justificacion_items`"
        )
    if sorted(referencias) != items:
        raise ComparacionError(
            f"{fuente.name}: los ítems exigidos {items} no coinciden con las "
            f"explicaciones {sorted(referencias)}"
        )
    return {
        "id": M._slug(fuente.stem),
        "titulo": str(datos["meta"].get("titulo") or fuente.stem),
        "clave": datos["clave"],
        "total": datos["n_preguntas"],
        "grupos": datos["grupos"] or 1,
        "min_justificacion": int(datos["meta"].get("min_justificacion") or 40),
        "items": items,
        "referencias": referencias,
        "registros": [],
        "respuestas_por_archivo": {},
    }


def _rutas_locales(base: Path, cuestionario: str) -> list[tuple[str, Path]]:
    encontradas: list[tuple[str, Path]] = []
    for archivo in base.rglob("*.json"):
        relativa = archivo.relative_to(base).as_posix()
        normalizada = relativa if relativa.startswith("resultados/") else f"resultados/{relativa}"
        coincidencia = D.RUTA_ARCHIVO.match(normalizada)
        if coincidencia and coincidencia.group("cid") == cuestionario:
            encontradas.append((normalizada, archivo))
    return sorted(encontradas)


def cargar_entregas(
    cuestionario: dict, *, repo: str, rama: str, token: str | None, local: Path | None
) -> tuple[list[dict], list[str]]:
    """Descarga (o lee en local) y valida las entregas de un cuestionario."""
    descartados: list[str] = []
    if local is not None:
        pares = _rutas_locales(local, cuestionario["id"])
    else:
        try:
            rutas = D.listar_rutas(repo, rama, token or "", cuestionario["id"])
        except urllib.error.HTTPError as exc:
            raise ComparacionError(
                f"{repo}@{rama}: HTTP {exc.code} ({exc.reason})", EXIT_RED
            ) from exc
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
            raise ComparacionError(f"no se pudo listar {repo}: {exc}", EXIT_RED) from exc
        pares = [(ruta, None) for ruta in rutas]

    for ruta, archivo_local in pares:
        try:
            if archivo_local is not None:
                datos = json.loads(archivo_local.read_text(encoding="utf-8"))
            else:
                datos = D.descargar(repo, ruta, rama, token or "")
        except (OSError, ValueError, json.JSONDecodeError, urllib.error.HTTPError) as exc:
            descartados.append(f"{ruta}: {exc}")
            continue
        problemas, registro = D.validar_registro(
            datos,
            cuestionario=cuestionario["id"],
            total=cuestionario["total"],
            grupos=cuestionario["grupos"],
            clave=cuestionario["clave"],
            archivo=ruta,
            justificacion_items=cuestionario["items"],
            min_justificacion=cuestionario["min_justificacion"],
        )
        if registro is None:
            descartados.append(f"{ruta}: {'; '.join(problemas)}")
            continue
        cuestionario["registros"].append(registro)
        cuestionario["respuestas_por_archivo"][ruta] = (
            datos.get("respuestas") if isinstance(datos, dict) else {}
        )
    D.marcar_copias(
        cuestionario["registros"], cuestionario["items"]
    )
    return cuestionario["registros"], descartados


def validar_salidas(rutas: list[Path]) -> None:
    for ruta in rutas:
        if not D._git_ignorado(ruta):
            raise ComparacionError(
                f"{ruta} no está ignorada por git; la tabla lleva nombres, "
                "cédulas y la clave: elegir una ruta bajo evaluaciones/web/ o .tmp/",
                EXIT_DATOS,
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fuente", action="append", default=[], help="Markdown del cuestionario (repetible)."
    )
    parser.add_argument("--repo", default=None, help="owner/repo privado de resultados.")
    parser.add_argument("--rama", default="main", help="Rama del repo de resultados.")
    parser.add_argument(
        "--local", default=None, help="Lee JSON desde esta carpeta en vez de la API."
    )
    parser.add_argument("--token-env", default=None, help="Variable del token de lectura.")
    parser.add_argument("--salida", default=None, help="Ruta del Markdown resultante.")
    parser.add_argument("--pdf", default=None, help="Ruta del PDF resultante.")
    parser.add_argument("--sin-pdf", action="store_true", help="Sólo Markdown.")
    parser.add_argument("--check", action="store_true", help="Valida fuentes sin leer entregas.")
    parser.add_argument("--json", action="store_true", help="Salida JSON por stdout.")
    args = parser.parse_args()

    def terminar(resultado: dict, code: int) -> int:
        if args.json:
            print(json.dumps(resultado, ensure_ascii=False, indent=2))
        else:
            print(f"[{resultado['status']}] {resultado.get('message', '')}".strip())
            for clave in ("filas", "entregas", "md", "pdf"):
                if resultado.get(clave) is not None:
                    print(f"  {clave}: {resultado[clave]}")
            for aviso in resultado.get("descartados", []):
                print(f"  ! {aviso}")
        return code

    if args.fuente:
        fuentes = [Path(f).resolve() for f in args.fuente]
    else:
        carpeta = RAIZ / "cursos/CYBERSEGURIDAD/evaluaciones/web" / SEMANA / "fuentes"
        fuentes = sorted(
            p for p in carpeta.glob("ROL_*_CUESTIONARIO_S2.md") if p.is_file()
        )
    if not fuentes:
        return terminar(
            {"status": "error", "code": EXIT_DATOS, "message": "no hay fuentes"},
            EXIT_DATOS,
        )

    try:
        cuestionarios = [cargar_cuestionario(f) for f in fuentes]
    except ComparacionError as exc:
        return terminar(
            {"status": "error", "code": exc.code, "message": str(exc)}, exc.code
        )
    if args.check:
        return terminar(
            {
                "status": "ok",
                "code": EXIT_OK,
                "check": True,
                "fuentes": len(fuentes),
                "cuestionarios": [
                    {"id": c["id"], "items": c["items"]}
                    for c in cuestionarios
                ],
            },
            EXIT_OK,
        )

    base_salida = fuentes[0].parent.parent / "revision" / "comparativa_justificaciones"
    ruta_md = Path(args.salida).resolve() if args.salida else base_salida.with_suffix(".md")
    ruta_pdf = Path(args.pdf).resolve() if args.pdf else base_salida.with_suffix(".pdf")
    try:
        validar_salidas([ruta_md] + ([] if args.sin_pdf else [ruta_pdf]))
    except ComparacionError as exc:
        return terminar(
            {"status": "error", "code": exc.code, "message": str(exc)}, exc.code
        )

    local = Path(args.local).resolve() if args.local else None
    if local is not None and not local.is_dir():
        return terminar(
            {"status": "error", "code": EXIT_DATOS, "message": f"no existe {local}"},
            EXIT_DATOS,
        )
    repo = args.repo or D._repo_por_defecto()
    token = None
    if local is None:
        if not repo:
            return terminar(
                {
                    "status": "error",
                    "code": EXIT_DATOS,
                    "message": "sin repo de resultados: pasar --repo o --local",
                },
                EXIT_DATOS,
            )
        variable = D._variable_token(repo, args.token_env)
        token = D._token(variable) or D._token("GITHUB_TOKEN")
        if not token:
            return terminar(
                {
                    "status": "error",
                    "code": EXIT_RED,
                    "message": f"sin token de lectura: añadir {variable} a .env",
                },
                EXIT_RED,
            )

    descartados: list[str] = []
    entregas = 0
    for cuestionario in cuestionarios:
        try:
            registros, fallos = cargar_entregas(
                cuestionario, repo=repo or "", rama=args.rama, token=token, local=local
            )
        except ComparacionError as exc:
            return terminar(
                {"status": "error", "code": exc.code, "message": str(exc)}, exc.code
            )
        entregas += len(registros)
        descartados += fallos

    filas = armar_filas(cuestionarios)
    markdown = markdown_tabla(filas, cuestionarios)
    try:
        D._escribir(ruta_md, markdown)
    except OSError as exc:
        return terminar(
            {"status": "error", "code": EXIT_IO, "message": f"no se pudo escribir: {exc}"},
            EXIT_IO,
        )
    ruta_pdf_escrita = None
    if not args.sin_pdf:
        trabajo = "comparativa_justificaciones"
        with contextlib.redirect_stdout(sys.stderr):
            ok, error = D._compilar_pdf(latex_tabla(filas, cuestionarios), ruta_pdf, trabajo)
        if not ok:
            return terminar(
                {
                    "status": "error",
                    "code": EXIT_IO,
                    "message": f"falló el PDF: {error}",
                    "md": str(ruta_md),
                    "filas": len(filas),
                },
                EXIT_IO,
            )
        ruta_pdf_escrita = str(ruta_pdf)

    codigo = EXIT_INVALIDOS if descartados else EXIT_OK
    resultado = {
        "status": "ok" if codigo == EXIT_OK else "con_descartados",
        "code": codigo,
        "filas": len(filas),
        "entregas": entregas,
        "cuestionarios": [c["id"] for c in cuestionarios],
        "descartados": descartados,
        "md": str(ruta_md),
        "pdf": ruta_pdf_escrita,
    }
    if not filas:
        resultado["avisos"] = ["no hay entregas archivadas: la tabla está vacía"]
    return terminar(resultado, codigo)


if __name__ == "__main__":
    raise SystemExit(main())
