#!/usr/bin/env python3
r"""
descargar_resultados.py — Descarga las entregas del repo privado y arma el acta (Layer 3).

Contrato:
  - Entrada: el repositorio donde el Worker archiva las entregas
    (`resultados/<cuestionario>/grupo_<NN>/<cedula>.json`) y la fuente del
    cuestionario, de la que salen la clave vigente y el número de grupos.
  - Salida: un acta CSV (+ PDF opcional) con una fila por estudiante: grupo,
    cédula, nombre, aciertos, nota archivada, nota recalculada con la clave
    vigente, fecha de envío y avisos.
  - La nota archivada NO se toma como verdad: se recalcula con la clave local y
    se compara. Si difieren (porque la clave cambió después del envío, o porque
    alguien editó el JSON a mano) la fila sale marcada `revisar`.
  - Con `--lista` (CSV o YAML con nombre/cédula/grupo) se informa de quién no
    entregó. Sin lista no se puede juzgar la cobertura y el acta lo dice.
  - Determinismo: mismo contenido del repo → mismos bytes. No hay "ahora": la
    fecha del acta es la del último envío (o `--fecha`).

Privacidad:
  - El acta contiene nombres y cédulas, así que solo se escribe en rutas que git
    ignore (se comprueba con `git check-ignore` antes de escribir).

Uso:
    python3 execution/descargar_resultados.py \\
        --fuente cursos/CYBERSEGURIDAD/evaluaciones/web/fuentes/ROL_ROJO_Cuestionario.md
    python3 execution/descargar_resultados.py --fuente <md> --lista estudiantes.csv --json

Códigos de salida:
    0 -> acta generada
    1 -> error de E/S al leer o escribir
    3 -> fuente/clave inválida, uso incorrecto o ruta de salida no ignorada
    4 -> red o credenciales (token ausente, 401/403/404, repo inexistente)
    5 -> hay entregas archivadas inválidas (el acta sale con avisos)
"""

from __future__ import annotations

import argparse
import base64
import binascii
import contextlib
import csv
import io
import json
import os
import re
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "execution"))

import md_a_html  # noqa: E402  (capa 3: formato del cuestionario y su clave)

API = "https://api.github.com"
API_VERSION = "2022-11-28"
# api.github.com no bloquea el UA de urllib, pero Cloudflare sí bloquea el de
# urllib en workers.dev; se usa UA de navegador en ambos por consistencia.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
LETRAS_VALIDAS = ("A", "B", "C", "D", "E")
CEDULA_RE = re.compile(r"^([VEJ])?-?(\d{5,9})$")
RUTA_ARCHIVO = re.compile(
    r"^resultados/(?P<cid>[a-z0-9_]{3,60})/grupo_(?P<grupo>\d{2})/"
    r"(?P<cedula>[VEJ]-\d{5,9})\.json$"
)
CABECERA_CSV = [
    "grupo",
    "cedula",
    "nombre",
    "aciertos",
    "total",
    "nota",
    "nota_recalculada",
    "enviado_en",
    "estado",
    "archivo",
    "avisos",
]

EXIT_OK = 0
EXIT_IO = 1
EXIT_DATOS = 3
EXIT_RED = 4
EXIT_INVALIDOS = 5


# --------------------------------------------------------------------------- #
# Funciones puras (sin red): las prueba execution/test_descargar_resultados.py
# --------------------------------------------------------------------------- #
def normalizar_cedula(valor: Any) -> str | None:
    """Misma regla que `normalizarCedula` del Worker: `v 12.345.678` -> `V-12345678`."""
    if not isinstance(valor, str):
        return None
    texto = valor.strip().upper().replace(".", "").replace(" ", "")
    partes = CEDULA_RE.match(texto)
    if not partes:
        return None
    return f"{partes.group(1) or 'V'}-{partes.group(2)}"


def _es_nombre(texto: str) -> bool:
    """Equivalente de `/^[\\p{L}\\p{M} .'-]+$/u`: letras, marcas, espacio, . ' -."""
    for ch in texto:
        if ch in " .'-":
            continue
        if unicodedata.category(ch)[0] not in ("L", "M"):
            return False
    return True


def normalizar_nombre(valor: Any) -> str | None:
    if not isinstance(valor, str):
        return None
    texto = " ".join(valor.split())
    if not (3 <= len(texto) <= 80) or not _es_nombre(texto):
        return None
    return texto


def normalizar_grupo(valor: Any, grupos: int) -> int | None:
    if isinstance(valor, bool):
        return None
    numero = valor if isinstance(valor, int) else _entero(valor)
    if numero is None or not 1 <= numero <= grupos:
        return None
    return numero


def _entero(valor: Any) -> int | None:
    try:
        numero = int(str(valor).strip())
    except (TypeError, ValueError):
        return None
    return numero


def _numero(valor: Any) -> float | None:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def normalizar_respuestas(valor: Any, total: int) -> dict[str, str] | None:
    """Respuestas completas 1..total con letras válidas, o None."""
    if not isinstance(valor, dict):
        return None
    respuestas: dict[str, str] = {}
    for numero in range(1, total + 1):
        letra = valor.get(str(numero))
        if not isinstance(letra, str) or letra not in LETRAS_VALIDAS:
            return None
        respuestas[str(numero)] = letra
    for clave in valor:
        numero = _entero(clave)
        if numero is None or not 1 <= numero <= total:
            return None
    return respuestas


def recalcular(respuestas: dict[str, str], clave: dict[int, str]) -> tuple[int, int, float]:
    """(aciertos, total, nota) con la misma fórmula que `calificar` del Worker."""
    total = len(clave)
    if total == 0:
        return 0, 0, 0.0
    aciertos = sum(1 for n in clave if respuestas.get(str(n)) == clave[n])
    return aciertos, total, round(10 * aciertos * 100 / total) / 100


def validar_registro(
    datos: Any,
    *,
    cuestionario: str,
    total: int,
    grupos: int,
    clave: dict[int, str],
    archivo: str,
) -> tuple[list[str], dict | None]:
    """Valida un JSON archivado contra el contrato del Worker y la clave vigente."""
    if not isinstance(datos, dict):
        return ["el archivo no contiene un objeto JSON"], None

    problemas: list[str] = []
    if datos.get("cuestionario") != cuestionario:
        problemas.append(f"cuestionario inesperado: {datos.get('cuestionario')!r}")

    nombre = normalizar_nombre(datos.get("nombre"))
    if nombre is None:
        problemas.append("nombre inválido")

    cedula = normalizar_cedula(datos.get("cedula"))
    if cedula is None:
        problemas.append("cédula inválida")

    grupo = normalizar_grupo(datos.get("grupo"), grupos)
    if grupo is None:
        problemas.append(f"grupo fuera de 1..{grupos}")

    respuestas = normalizar_respuestas(datos.get("respuestas"), total)
    if respuestas is None:
        problemas.append(f"respuestas incompletas o fuera de 1..{total}")

    # Coherencia con la ruta: el archivo vive en grupo_<NN>/<cedula>.json
    m = RUTA_ARCHIVO.match(archivo)
    if m is None:
        problemas.append(f"la ruta no sigue el patrón del Worker: {archivo}")
    else:
        if cedula is not None and m.group("cedula") != cedula:
            problemas.append(
                f"la cédula del archivo ({m.group('cedula')}) no es la del contenido ({cedula})"
            )
        if grupo is not None and int(m.group("grupo")) != grupo:
            problemas.append(
                f"el grupo del archivo ({int(m.group('grupo'))}) no es el del contenido ({grupo})"
            )

    if problemas:
        return problemas, None

    aciertos, total_clave, nota = recalcular(respuestas, clave)
    nota_archivada = _numero(datos.get("nota"))
    if nota_archivada is None:
        problemas.append("falta `nota` o no es numérica")
    elif abs(nota_archivada - nota) > 0.005:
        problemas.append(
            f"la nota archivada ({nota_archivada:g}) no coincide con la recalculada "
            f"con la clave vigente ({nota:g})"
        )
    aciertos_archivados = _entero(datos.get("aciertos"))
    if aciertos_archivados is None:
        problemas.append("falta `aciertos` o no es numérico")
    elif aciertos_archivados != aciertos:
        problemas.append(
            f"`aciertos` archivado ({aciertos_archivados}) != recalculado ({aciertos})"
        )
    enviado_en = datos.get("enviado_en")
    if not isinstance(enviado_en, str) or not enviado_en:
        problemas.append("falta `enviado_en`")
        enviado_en = ""

    registro = {
        "grupo": grupo,
        "cedula": cedula,
        "nombre": nombre,
        "aciertos": aciertos,
        "total": total_clave,
        "nota": nota_archivada if nota_archivada is not None else nota,
        "nota_recalculada": nota,
        "enviado_en": enviado_en,
        "archivo": archivo,
        "avisos": list(problemas),
        "estado": "revisar" if problemas else "ok",
    }
    return problemas, registro


def ordenar(registros: list[dict]) -> list[dict]:
    """Orden determinista: grupo, nota recalculada descendente, cédula."""
    return sorted(
        registros,
        key=lambda r: (r["grupo"], -r["nota_recalculada"], r["cedula"]),
    )


def csv_texto(registros: list[dict]) -> str:
    salida = io.StringIO()
    escritor = csv.DictWriter(salida, fieldnames=CABECERA_CSV, lineterminator="\n")
    escritor.writeheader()
    for r in registros:
        escritor.writerow(
            {
                "grupo": r["grupo"],
                "cedula": r["cedula"],
                "nombre": r["nombre"],
                "aciertos": r["aciertos"],
                "total": r["total"],
                "nota": f"{float(r['nota']):.2f}",
                "nota_recalculada": f"{float(r['nota_recalculada']):.2f}",
                "enviado_en": r["enviado_en"],
                "estado": r["estado"],
                "archivo": r["archivo"],
                "avisos": "; ".join(r["avisos"]),
            }
        )
    return salida.getvalue()


def leer_lista(ruta: Path) -> tuple[list[dict], list[str]]:
    """Lee la nómina (CSV con cabecera o YAML) y devuelve filas normalizadas."""
    texto = ruta.read_text(encoding="utf-8")
    crudas: list[dict] = []
    if ruta.suffix.lower() in (".yaml", ".yml"):
        import yaml  # importación perezosa: solo hace falta con --lista YAML

        datos = yaml.safe_load(texto)
        if isinstance(datos, dict):
            datos = datos.get("estudiantes") or datos.get("lista") or []
        if not isinstance(datos, list):
            return [], ["la lista YAML no es una lista de estudiantes"]
        crudas = [d for d in datos if isinstance(d, dict)]
    else:
        lector = csv.DictReader(io.StringIO(texto))
        if lector.fieldnames is None:
            return [], ["el CSV de la lista está vacío"]
        crudas = [dict(f) for f in lector]

    filas: list[dict] = []
    problemas: list[str] = []
    for i, fila in enumerate(crudas, start=2):
        claves = {k.strip().lower(): v for k, v in fila.items() if isinstance(k, str)}
        cedula = normalizar_cedula(
            claves.get("cedula") or claves.get("cédula") or claves.get("ci")
        )
        nombre = normalizar_nombre(claves.get("nombre") or "")
        grupo = _entero(claves.get("grupo"))
        if cedula is None:
            problemas.append(f"fila {i}: sin cédula válida")
            continue
        filas.append({"cedula": cedula, "nombre": nombre or "", "grupo": grupo})
    return filas, problemas


def comparar(lista: list[dict], registros: list[dict]) -> dict:
    """Diferencia entre la nómina y las entregas recibidas."""
    esperados = {f["cedula"]: f for f in lista}
    recibidos = {r["cedula"]: r for r in registros}
    faltantes = sorted(set(esperados) - set(recibidos))
    sobrantes = sorted(set(recibidos) - set(esperados))
    grupo_distinto = sorted(
        c
        for c in set(esperados) & set(recibidos)
        if esperados[c].get("grupo") is not None
        and esperados[c]["grupo"] != recibidos[c]["grupo"]
    )
    return {
        "esperados": len(esperados),
        "recibidos": len(recibidos),
        "faltantes": [
            {"cedula": c, "nombre": esperados[c]["nombre"], "grupo": esperados[c].get("grupo")}
            for c in faltantes
        ],
        "sobrantes": [
            {"cedula": c, "nombre": recibidos[c]["nombre"], "grupo": recibidos[c]["grupo"]}
            for c in sobrantes
        ],
        "grupo_distinto": grupo_distinto,
    }


def resumen(registros: list[dict]) -> dict:
    notas = [float(r["nota_recalculada"]) for r in registros]
    por_grupo: dict[int, int] = {}
    for r in registros:
        por_grupo[r["grupo"]] = por_grupo.get(r["grupo"], 0) + 1
    return {
        "entregas": len(registros),
        "promedio": round(sum(notas) / len(notas), 2) if notas else None,
        "mejor": max(notas) if notas else None,
        "peor": min(notas) if notas else None,
        "por_grupo": {g: por_grupo[g] for g in sorted(por_grupo)},
        "ultimo_envio": max((r["enviado_en"] for r in registros), default=None),
        "a_revisar": sum(1 for r in registros if r["estado"] != "ok"),
    }


# --------------------------------------------------------------------------- #
# Red
# --------------------------------------------------------------------------- #
def _token(nombre_env: str) -> str | None:
    valor = os.environ.get(nombre_env, "").strip()
    if valor:
        return valor
    ruta = RAIZ / ".env"
    if ruta.is_file():
        for linea in ruta.read_text(encoding="utf-8", errors="ignore").splitlines():
            linea = linea.strip()
            if linea.startswith(f"{nombre_env}="):
                candidato = linea.split("=", 1)[1].strip().strip('"').strip("'")
                if candidato:
                    return candidato
    return None


def _get(url: str, token: str, timeout: int = 40) -> bytes:
    peticion = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": API_VERSION,
        },
    )
    with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
        return respuesta.read()


def listar_rutas(repo: str, rama: str, token: str, cuestionario: str) -> list[str]:
    url = f"{API}/repos/{repo}/git/trees/{urllib.parse.quote(rama)}?recursive=1"
    datos = json.loads(_get(url, token).decode("utf-8"))
    if datos.get("truncated"):
        raise ValueError("el árbol del repo llegó truncado; el acta estaría incompleta")
    prefijo = f"resultados/{cuestionario}/"
    rutas = [
        item["path"]
        for item in datos.get("tree", [])
        if item.get("type") == "blob" and str(item.get("path", "")).startswith(prefijo)
    ]
    return sorted(rutas)


def descargar(repo: str, ruta: str, rama: str, token: str) -> Any:
    url = (
        f"{API}/repos/{repo}/contents/{urllib.parse.quote(ruta)}"
        f"?ref={urllib.parse.quote(rama)}"
    )
    datos = json.loads(_get(url, token).decode("utf-8"))
    contenido = datos.get("content")
    if not isinstance(contenido, str):
        raise ValueError(f"{ruta}: la respuesta no trae `content`")
    try:
        crudo = base64.b64decode(contenido).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise ValueError(f"{ruta}: contenido ilegible ({exc})") from exc
    return json.loads(crudo)


# --------------------------------------------------------------------------- #
# Salida
# --------------------------------------------------------------------------- #
def _tex(texto: Any) -> str:
    crudo = "" if texto is None else str(texto)
    for a, b in (
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ):
        crudo = crudo.replace(a, b)
    return crudo


def latex_acta(
    registros: list[dict],
    *,
    titulo: str,
    curso: str,
    cuestionario: str,
    fecha: str,
    grupos: int,
    cobertura: dict | None,
) -> str:
    from execution.estilo_infografia import PREAMBULO_INFOGRAFIA

    datos = resumen(registros)
    filas = []
    for r in registros:
        estado = (
            r"\textcolor{verdeSignal}{\faIcon{check}}"
            if r["estado"] == "ok"
            else r"\textcolor{rojoAlerta}{\faIcon{exclamation-triangle}}"
        )
        filas.append(
            " & ".join(
                [
                    str(r["grupo"]),
                    _tex(r["cedula"]),
                    _tex(r["nombre"]),
                    f"{r['aciertos']}/{r['total']}",
                    f"{float(r['nota_recalculada']):.2f}",
                    estado,
                ]
            )
            + r" \\"
        )
    tabla = "\n".join(filas) if filas else r"\multicolumn{6}{c}{\textit{Sin entregas}} \\"

    cobertura_tex = ""
    if cobertura is None:
        cobertura_tex = (
            r"\begin{tcolorbox}[cajaContenido, title={Cobertura no verificable}]"
            "\nNo se pasó una nómina (\\texttt{--lista}), así que este acta lista "
            "solo a quien envió: no dice quién falta.\n\\end{tcolorbox}"
        )
    else:
        faltan = cobertura["faltantes"]
        if faltan:
            items = "\n".join(
                f"\\item {_tex(f['nombre']) or '(sin nombre)'} --- \\texttt{{{_tex(f['cedula'])}}}"
                + (f", grupo {f['grupo']}" if f.get("grupo") else "")
                for f in faltan
            )
            cobertura_tex = (
                r"\begin{tcolorbox}[cajaContenido, title={Sin entrega}]"
                f"\n{len(faltan)} de {cobertura['esperados']} en la nómina:\n"
                f"\\begin{{itemize}}\n{items}\n\\end{{itemize}}\n\\end{{tcolorbox}}"
            )
        else:
            cobertura_tex = (
                r"\begin{tcolorbox}[cajaContenido, title={Cobertura completa}]"
                f"\nEntregaron los {cobertura['esperados']} de la nómina.\n\\end{{tcolorbox}}"
            )

    promedio = "--" if datos["promedio"] is None else f"{datos['promedio']:.2f}"
    mejor = "--" if datos["mejor"] is None else f"{datos['mejor']:.2f}"
    peor = "--" if datos["peor"] is None else f"{datos['peor']:.2f}"

    return (
        PREAMBULO_INFOGRAFIA
        + r"""
\begin{document}
\bandaTitulo{ACTA DE CUESTIONARIO}{"""
        + _tex(titulo)
        + r"""}
\begin{center}
\small """
        + _tex(curso)
        + r""" ~$\cdot$~ \texttt{"""
        + _tex(cuestionario)
        + r"""} ~$\cdot$~ último envío: """
        + _tex(fecha or "--")
        + r"""
\end{center}

\begin{tcolorbox}[tarjetaDato, title={Resumen}]
\textbf{Entregas:} """
        + str(datos["entregas"])
        + r""" ~$\cdot$~ \textbf{Promedio:} """
        + promedio
        + r""" ~$\cdot$~ \textbf{Mejor:} """
        + mejor
        + r""" ~$\cdot$~ \textbf{Peor:} """
        + peor
        + r""" ~$\cdot$~ \textbf{A revisar:} """
        + str(datos["a_revisar"])
        + r"""
\end{tcolorbox}

"""
        + cobertura_tex
        + r"""

\section*{Resultados por grupo}
\begin{longtable}{@{}c l p{5.8cm} r r c@{}}
\toprule
\textbf{G} & \textbf{Cédula} & \textbf{Nombre} & \textbf{Aciertos} & \textbf{Nota} & \textbf{Estado} \\
\midrule
\endhead
"""
        + tabla
        + r"""
\bottomrule
\end{longtable}

\smallskip
{\footnotesize Nota recalculada con la clave vigente en el momento de generar el
acta ($10\cdot\text{aciertos}/\text{preguntas}$). Las filas marcadas con
\textcolor{rojoAlerta}{\faIcon{exclamation-triangle}} difieren de la nota que
devolvió el Worker y hay que revisarlas a mano. Grupos declarados: """
        + str(grupos)
        + r""".}

\end{document}
"""
    )


def _git_ignorado(ruta: Path) -> bool:
    proc = subprocess.run(
        ["git", "check-ignore", "-q", str(ruta)],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.returncode == 0


def _escribir(ruta: Path, contenido: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding="utf-8")


def _compilar_pdf(latex: str, destino: Path, trabajo: str) -> tuple[bool, str]:
    from execution.compile_latex import compile_latex_code

    salida = RAIZ / ".tmp" / "latex_build" / trabajo
    # compile_latex_code imprime progreso por stdout; se desvía a stderr para que
    # `--json` siga emitiendo un único JSON parseable por stdout.
    with contextlib.redirect_stdout(sys.stderr):
        resultado = compile_latex_code(
            latex, job_name=trabajo, output_dir=str(salida), clean=False
        )
    generado = salida / f"{trabajo}.pdf"
    if not resultado.get("success") or not generado.is_file():
        return False, str(resultado.get("error") or "pdflatex no produjo el PDF")
    log = (salida / f"{trabajo}.log").read_text(encoding="utf-8", errors="ignore")
    errores = re.findall(r"^! (.+)$", log, re.M)
    if errores:
        return False, "; ".join(errores[:3])
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(generado.read_bytes())
    return True, ""


def _quitar_comentarios(texto: str) -> str:
    """Quita comentarios `//` de un JSONC respetando las cadenas.

    Un `re.sub(r"//.*$", "")` a secas se come las URLs (`https://...`) y deja el
    archivo ilegible: hay que saber si el `//` está dentro de una cadena.
    """
    salida: list[str] = []
    en_cadena = False
    escape = False
    i = 0
    largo = len(texto)
    while i < largo:
        ch = texto[i]
        if en_cadena:
            salida.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                en_cadena = False
            i += 1
            continue
        if ch == '"':
            en_cadena = True
            salida.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < largo and texto[i + 1] == "/":
            while i < largo and texto[i] != "\n":
                i += 1
            continue
        salida.append(ch)
        i += 1
    return "".join(salida)


def _quitar_comentarios(texto: str) -> str:
    """Quita comentarios `//` de un JSONC sin tocar los que van dentro de cadenas.

    Un `re.sub(r"//.*$", ...)` a secas se come las URLs (`"https://..."`) y deja
    el archivo ilegible; por eso se recorre caracter a caracter.
    """
    salida: list[str] = []
    en_cadena = False
    escape = False
    i = 0
    largo = len(texto)
    while i < largo:
        ch = texto[i]
        if en_cadena:
            salida.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                en_cadena = False
            i += 1
            continue
        if ch == '"':
            en_cadena = True
            salida.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < largo and texto[i + 1] == "/":
            while i < largo and texto[i] != "\n":
                i += 1
            continue
        salida.append(ch)
        i += 1
    return "".join(salida)


def _repo_por_defecto() -> str | None:
    config = RAIZ / "Proyectos" / "cuestionarios-worker" / "wrangler.jsonc"
    if not config.is_file():
        return None
    try:
        datos = json.loads(_quitar_comentarios(config.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return None
    repo = datos.get("vars", {}).get("REPO_RESULTADOS")
    return repo if isinstance(repo, str) and repo else None


def _resultado(status: str, code: int, **extra) -> dict:
    return {"status": status, "code": code, **extra}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Descarga las entregas del repo privado y genera el acta."
    )
    parser.add_argument("--fuente", required=True, help="Markdown del cuestionario.")
    parser.add_argument(
        "--respuestas",
        default=None,
        help="Archivo de respuestas (por defecto, <fuente>_respuestas.md si existe).",
    )
    parser.add_argument("--repo", default=None, help="owner/repo privado de resultados.")
    parser.add_argument("--rama", default="main", help="Rama del repo (main).")
    parser.add_argument("--cuestionario", default=None, help="Id del cuestionario (slug de la fuente).")
    parser.add_argument("--lista", default=None, help="Nómina CSV/YAML para detectar faltantes.")
    parser.add_argument("--salida", default=None, help="Ruta del acta CSV.")
    parser.add_argument("--pdf", default=None, help="Ruta del acta PDF.")
    parser.add_argument("--sin-pdf", action="store_true", help="No generar el PDF.")
    parser.add_argument("--fecha", default=None, help="Fecha del acta (por defecto, el último envío).")
    parser.add_argument(
        "--token-env",
        default="GITHUB_TOKEN_RESULTADOS",
        help="Variable de entorno/.env con el token de lectura.",
    )
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    args = parser.parse_args()

    def terminar(resultado: dict, code: int) -> int:
        if args.json:
            print(json.dumps(resultado, ensure_ascii=False, indent=2))
        else:
            estado = resultado.get("status")
            mensaje = resultado.get("message") or ""
            print(f"[{estado}] {mensaje}" if mensaje else f"[{estado}]")
            for clave in ("acta_csv", "acta_pdf", "entregas", "promedio", "a_revisar"):
                if resultado.get(clave) is not None:
                    print(f"  {clave}: {resultado[clave]}")
            for aviso in resultado.get("avisos", []) or []:
                print(f"  ! {aviso}")
        return code

    fuente = Path(args.fuente).resolve()
    respuestas = (
        Path(args.respuestas).resolve()
        if args.respuestas
        else fuente.with_name(fuente.stem + "_respuestas.md")
    )
    try:
        datos_fuente = md_a_html.cargar_clave(fuente, respuestas if respuestas.is_file() else None)
    except (OSError, ValueError) as exc:
        return terminar(_resultado("error", EXIT_DATOS, message=str(exc)), EXIT_DATOS)

    clave = datos_fuente["clave"]
    if not clave:
        return terminar(
            _resultado(
                "error",
                EXIT_DATOS,
                message="la fuente no tiene clave: sin ella no se puede recalcular la nota",
            ),
            EXIT_DATOS,
        )
    total = datos_fuente["n_preguntas"]
    grupos = datos_fuente["grupos"] or 1
    meta = datos_fuente["meta"]
    cuestionario = args.cuestionario or md_a_html._slug(fuente.stem)
    curso = str(meta.get("curso") or "CURSO")
    titulo = str(meta.get("titulo") or cuestionario)

    repo = args.repo or _repo_por_defecto()
    if not repo:
        return terminar(
            _resultado(
                "error",
                EXIT_DATOS,
                message=(
                    "no se pudo determinar el repo de resultados: pasar --repo o "
                    "definir vars.REPO_RESULTADOS en Proyectos/cuestionarios-worker/wrangler.jsonc"
                ),
            ),
            EXIT_DATOS,
        )

    token = _token(args.token_env) or _token("GITHUB_TOKEN")
    if not token:
        return terminar(
            _resultado(
                "error",
                EXIT_RED,
                message=(
                    f"sin token de lectura: añadir {args.token_env}=<PAT> a .env "
                    "(Contents: Read and write sobre el repo de resultados)"
                ),
            ),
            EXIT_RED,
        )

    salida_csv = (
        Path(args.salida).resolve()
        if args.salida
        else RAIZ
        / "cursos"
        / curso
        / "evaluaciones"
        / "resultados"
        / f"acta_{cuestionario}.csv"
    )
    salida_pdf = (
        Path(args.pdf).resolve()
        if args.pdf
        else salida_csv.with_suffix(".pdf")
    )
    for ruta in [salida_csv] + ([] if args.sin_pdf else [salida_pdf]):
        if not _git_ignorado(ruta):
            return terminar(
                _resultado(
                    "error",
                    EXIT_DATOS,
                    message=(
                        f"{ruta} no está ignorada por git y el acta lleva nombres y "
                        "cédulas: elegir una ruta dentro de "
                        "cursos/<CURSO>/evaluaciones/resultados/ o de .tmp/"
                    ),
                ),
                EXIT_DATOS,
            )

    try:
        rutas = listar_rutas(repo, args.rama, token, cuestionario)
    except urllib.error.HTTPError as exc:
        detalle = {
            401: "token inválido",
            403: "sin permiso sobre el repo",
            404: "repo o rama inexistente",
        }.get(exc.code, str(exc.reason))
        return terminar(
            _resultado_red(f"{repo}@{args.rama}: HTTP {exc.code} ({detalle})"), EXIT_RED
        )
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        return terminar(
            _resultado_red(f"no se pudo listar {repo}: {exc}"), EXIT_RED
        )

    registros: list[dict] = []
    invalidos: list[dict] = []
    for ruta in rutas:
        try:
            contenido = descargar(repo, ruta, args.rama, token)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError,
                json.JSONDecodeError) as exc:
            invalidos.append({"archivo": ruta, "avisos": [f"no se pudo descargar: {exc}"]})
            continue
        problemas, registro = validar_registro(
            contenido,
            cuestionario=cuestionario,
            total=total,
            grupos=grupos,
            clave=clave,
            archivo=ruta,
        )
        if registro is None:
            invalidos.append({"archivo": ruta, "avisos": problemas})
            continue
        registros.append(registro)

    registros = ordenar(registros)
    avisos: list[str] = []
    for r in registros:
        avisos.extend(f"{r['archivo']}: {a}" for a in r["avisos"])
    for item in invalidos:
        avisos.extend(f"{item['archivo']}: {a}" for a in item["avisos"])

    cobertura = None
    if args.lista:
        ruta_lista = Path(args.lista).resolve()
        if not ruta_lista.is_file():
            return terminar(
                _resultado("error", EXIT_IO, message=f"no existe la nómina: {ruta_lista}"),
                EXIT_IO,
            )
        try:
            nomina, problemas_lista = leer_lista(ruta_lista)
        except (OSError, ValueError) as exc:
            return terminar(
                _resultado("error", EXIT_IO, message=f"nómina ilegible: {exc}"), EXIT_IO
            )
        avisos.extend(problemas_lista)
        cobertura = comparar(nomina, registros)
        if cobertura["faltantes"]:
            avisos.append(
                f"{len(cobertura['faltantes'])} estudiante(s) de la nómina sin entrega"
            )
        if cobertura["sobrantes"]:
            avisos.append(
                f"{len(cobertura['sobrantes'])} entrega(s) de cédulas que no están en la nómina"
            )
        if cobertura["grupo_distinto"]:
            avisos.append(
                f"grupo declarado en la nómina distinto del envío: {cobertura['grupo_distinto']}"
            )
    else:
        avisos.append(
            "sin --lista no se puede saber quién falta: el acta solo incluye a quien envió"
        )

    datos_resumen = resumen(registros)
    fecha = args.fecha or datos_resumen["ultimo_envio"] or ""

    try:
        _escribir(salida_csv, csv_texto(registros))
    except OSError as exc:
        return terminar(
            _resultado("error", EXIT_IO, message=f"no se pudo escribir el acta: {exc}"),
            EXIT_IO,
        )

    pdf_ok, pdf_error = True, ""
    if not args.sin_pdf:
        latex = latex_acta(
            registros,
            titulo=titulo,
            curso=curso,
            cuestionario=cuestionario,
            fecha=fecha,
            grupos=grupos,
            cobertura=cobertura,
        )
        pdf_ok, pdf_error = _compilar_pdf(
            latex, salida_pdf, f"acta_{cuestionario}"
        )
        if not pdf_ok:
            avisos.append(f"el PDF no se generó: {pdf_error}")

    resultado = {
        "status": "error" if (invalidos or datos_resumen["a_revisar"]) else "ok",
        "code": EXIT_INVALIDOS if (invalidos or datos_resumen["a_revisar"]) else EXIT_OK,
        "repo": repo,
        "rama": args.rama,
        "cuestionario": cuestionario,
        "preguntas": total,
        "grupos": grupos,
        "acta_csv": str(salida_csv),
        "acta_pdf": None if args.sin_pdf else (str(salida_pdf) if pdf_ok else None),
        "entregas": datos_resumen["entregas"],
        "promedio": datos_resumen["promedio"],
        "a_revisar": datos_resumen["a_revisar"],
        "resumen": datos_resumen,
        "cobertura": cobertura,
        "avisos": avisos,
    }
    if not args.json:
        print(f"Acta de {cuestionario}: {datos_resumen['entregas']} entrega(s)")
        if registros:
            ancho = max(len(r["nombre"]) for r in registros)
            for r in registros:
                marca = " " if r["estado"] == "ok" else "!"
                print(
                    f"  {marca} G{r['grupo']} {r['cedula']:<10} "
                    f"{r['nombre']:<{ancho}} {r['aciertos']:>2}/{r['total']:<2} "
                    f"{float(r['nota_recalculada']):>5.2f}"
                )
        print(f"  CSV: {salida_csv}")
        if not args.sin_pdf and pdf_ok:
            print(f"  PDF: {salida_pdf}")
        for aviso in avisos:
            print(f"  ! {aviso}")
        return resultado["code"]

    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return resultado["code"]


def _resultado_red(mensaje: str) -> dict:
    return _resultado("error", EXIT_RED, message=mensaje)


if __name__ == "__main__":
    sys.exit(main())
