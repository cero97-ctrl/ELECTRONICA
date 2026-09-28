#!/usr/bin/env python3
"""Auditoria de entornos conda: cuales estan frios y cuanto ocupan de verdad.

Responde a la pregunta que la dimension `disco` no puede responder. Esa declara
"39,2 MB recuperables" con la certeza de su whitelist, y acierta: la whitelist
es correcta. Lo que no tiene es un termino de comparacion, porque los
entornos conda de la maquina eran 4 GB y no aparecen en ningun catalogo.

Por que los `.pyc` y no `conda-meta/history`. Un entorno se ejecuta mucho sin
instalar nada, y ejecutar un modulo compila su `.pyc`; instalar un paquete
reescribe `conda-meta/history`. Son dos relojes distintos y se confunden
facilmente:

  - `conda-meta/history` solo fecha la ultima operacion de paquetes. `IA` tiene
    la suya en 2025-10-25 y eso NO dice que este sin usar, dice que no se le
    instalo nada desde entonces.
  - el mtime del directorio del entorno tampoco cambia al ejecutar.
  - `.bash_history` aqui tiene 846 lineas, 12,9 KB y **sin timestamps**, y puede
    estar truncado. Sirve para confirmar un positivo, nunca para probar un
    negativo: "no aparece" ahi no significa "no se uso".

El `.pyc` lo crea la ejecucion. Cero `.pyc` generados en la ventana es la senal
fuerte, y es la que se usa.

Por que las referencias se buscan con patrones y no con nombres sueltos. Un
`grep -w` del nombre `IA` en el workspace devuelve 226 Lineas, y ninguna es una
activacion de conda: es "IA" como palabra ("inteligencia artificial", "la IA").
Un nombre de entorno no se busca como palabra, se busca como lo que es: algo
que un script le dice a conda. De ahi los anclajes de `PATRONES_REFERENCIA`.

Por que el peso es `bytes_exclusivos` y no `du`. Ver `catalogo_disco.bytes_exclusivos`.
Resumen: conda hardlinkea los entornos contra `pkgs`, asi que el tamano aparente de
un arbol lleno de enlaces no es lo que se recupera al borrarlo. Medido hoy: `pkgs`
declara 6,81 GB y tiene 2,00 GB exclusivos.

La dimension es de SOLO LECTURA yJamAS borra: clasifica y reporta. Borrar
entornos es decision del operador, con recipe de por medio.

Ejecutar: python3 execution/auditar_envs_conda.py [--json] [--dias 90] [--sin-refs]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "execution"))

from catalogo_disco import bytes_exclusivos  # noqa: E402

# Politica del usuario, documentada en docs/ENTORNOS_CONDA/README.md.
# `IA` es frio segun el criterio y aun asi se conserva: es el unico TensorFlow
# funcional de la maquina. Un entorno frio no es un entorno que se pueda borrar,
# y esta constante es la razon por la que la medicion no decide sola.
PROTEGIDOS_POR_POLITICA: tuple[str, ...] = ("elect_env", "IA")

# La ventana del criterio. 90 dias es lo que se aplico el 2026-09-28, cuando
# separo 12 entornos frios de 2 vivos y no se equivocaba en ninguno.
DIAS_POR_DEFECTO = 90

# Extensiones donde un nombre de entorno puede aparecer como instruccion real.
# Sin este filtro el escaneo tardaba 2 minutos en vez de 1,3 s, porque grep se
#aba por binarios (.git, chroma_db, .pio, node_modules).
EXTENSIONES: tuple[str, ...] = (
    "*.py", "*.sh", "*.md", "*.yaml", "*.yml", "*.json",
    "*.ipynb", "*.js", "*.ts", "*.toml", "*.ini", "*.cfg", "*.bash",
)

DIRECTORIOS_EXCLUIDOS: tuple[str, ...] = (
    ".git", "node_modules", "chroma_db", ".venv", "venv", ".pio",
    "__pycache__", ".tmp", "site-packages", ".mypy_cache", ".pytest_cache",
)


class _Parser(argparse.ArgumentParser):
    """Codigo 3 para uso incorrecto.

    argparse usa 2, y en una dimension de auditoria 2 significaria "no
    verificado", que es una lectura falsa y grave: invita a reintentar la
    medicion cuando el problema era el comando. Mismo remapeo que
    `flujo_auditar_repo._Parser` y `auditar_repo._Parser`.
    """

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(3)


# ---------------------------------------------------------------------------
# Descubrimiento
# ---------------------------------------------------------------------------

def descubrir_entornos(raiz_envs: Path) -> tuple[list[Path], str | None]:
    """(directorios de entorno, motivo si no se pudo listar).

    Se listan los directorios en vez de preguntar a `conda env list --json` a
    proposito: un directorio sin `conda-meta/history` no es un entorno, es una
    carpeta que alguien dejo a medias, y contarla inflaria el total. Y
    listarlo no puede fallar por un binario de conda roto.
    """
    if not raiz_envs.is_dir():
        return [], f"no existe el directorio de entornos: {raiz_envs}"
    encontrados: list[Path] = []
    try:
        for entrada in os.scandir(raiz_envs):
            if not entrada.is_dir(follow_symlinks=False):
                continue
            if not (Path(entrada.path) / "conda-meta" / "history").is_file():
                continue
            encontrados.append(Path(entrada.path))
    except OSError as exc:
        return [], f"no se pudo leer {raiz_envs}: {exc}"
    if not encontrados:
        return [], f"{raiz_envs} no contiene ningun entorno (falta conda-meta/history)"
    return sorted(encontrados), None


# ---------------------------------------------------------------------------
# Criterio 1: ejecucion reciente
# ---------------------------------------------------------------------------

def _find(args: list[str], timeout: int) -> tuple[int, str]:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return -1, ""
    except OSError as exc:
        return -1, str(exc)
    return proc.returncode, proc.stdout or ""


def pyc_en_ventana(env_dir: Path, corte: float, timeout: int) -> tuple[bool | None, str]:
    """(True si hay .pyc reciente, True si la medicion fallo, detalle).

    `find -newermt @<epoch> -quit` abandona en la primera coincidencia, asi que
    para un entorno vivo es instantaneo: no se recorre entero. Para uno frio si
    hay que recorrerlo entero, y ahi es cuando importa que sea en C y no un
    `stat()` por inodo en Python.
    """
    rc, salida = _find([
        "find", str(env_dir), "-xdev", "-name", "*.pyc",
        "-newermt", f"@{corte:.0f}", "-print", "-quit",
    ], timeout)
    if rc == -1:
        return None, "timeout al buscar .pyc"
    if rc != 0:
        return None, f"find devolvio {rc}"
    return bool(salida.strip()), ""


def ultimo_pyc(env_dir: Path, timeout: int) -> str | None:
    """Fecha del .pyc mas reciente, o None si no hay ninguno.

    Recorre entero, asi que solo se pide para entornos frios: si esta vivo, la
    pregunta ya la respondio `pyc_en_ventana` y la fecha es adorno.
    """
    rc, salida = _find([
        "bash", "-c",
        f"find {env_dir!s} -xdev -name '*.pyc' -printf '%TY-%Tm-%Td\\n' 2>/dev/null "
        f"| sort -r | head -1",
    ], timeout)
    if rc != 0:
        return None
    lineas = salida.strip().splitlines()
    return lineas[0] if lineas else None


# ---------------------------------------------------------------------------
# Criterio 2: referencias externas
# ---------------------------------------------------------------------------

def _patrones_referencia(nombres: list[str]) -> str:
    """Alternativa ERE con los anclajes de uso real de conda.

    Un entorno se referencia de cinco formas que importan, y ninguna es
    "aparecer la palabra":

        conda activate <n>        cond activate / envs/<n>/bin/python
        ENV_NAME="<n>"            conda create -n <n> / env create -n <n>

    Un quinto anclaje (`-n <n>` a secas) se deja fuera a proposito: aparece en
    cualquier `conda` de otra cosa y con 16 entornos genera ruido, no senal.
    """
    partes: list[str] = []
    for n in nombres:
        e = re.escape(n)
        # El flag del entorno va en sus dos formas: `conda create -n x` y
        # `conda create --name x`. Cubrir solo `-n` dejaba invisible justo el
        # `setup.sh` mas legible, que es el que la gente copia al crear uno.
        flag = rf"(-n|--name)[= ]+[\"']?{e}\b"
        partes += [
            rf"conda activate[= ]+[\"']?{e}\b",
            rf"envs/{e}/",
            rf"ENV_NAME\s*=\s*[\"']?{e}\b",
            rf"conda (env )?create[^\n]*{flag}",
            rf"conda (env )?(export|remove|update|clone|rename)[^\n]*{flag}",
        ]
    return "|".join(partes)


def buscar_referencias(workspace: Path, nombres: list[str], timeout: int) -> dict[str, Any]:
    """(mapa nombre -> rutas, nota). Un solo grep para todos los entornos.

    Un `grep` por entorno seria 16 recorridos del workspace. Con una sola
    alternativa ERE es un recorrido, y con las extensiones filtradas tarda
    ~1,3 s en vez de ~2 min.

    Sin la flag `-l`, a proposito: `-l` imprime solo el nombre del fichero, y
    con el nombre del fichero no se puede saber QUE entorno nombra. La
    atribucion necesita el contenido de la linea, y el contenido es lo que
    distingue "este fichero menciona pcb_env" de "este fichero menciona IA como
    palabra". Con `-l` la funcion devolvia siempre vacio sin dar ningun error:
    el tipo de fallo que parece un "no hay nada que limpiar" cuando en
    realidad no se midio nada.
    """
    if not nombres:
        return {}, ""
    if not workspace.is_dir():
        return {}, f"no existe el workspace: {workspace}"
    args = ["grep", "-rInE", _patrones_referencia(nombres), str(workspace)]
    for ext in EXTENSIONES:
        args += [f"--include={ext}"]
    for d in DIRECTORIOS_EXCLUIDOS:
        args += [f"--exclude-dir={d}"]
    rc, salida = _find(args, timeout)
    # grep sale 1 cuando no encuentra nada, y eso NO es un fallo del escaneo.
    if rc == -1:
        return {}, f"timeout a los {timeout}s escaneando {workspace}"
    if rc not in (0, 1):
        return {}, f"grep devolvio {rc}"

    # Atribucion con la MISMA funcion que genero el patron de busqueda: si el
    # patron de un solo nombre casa con esa linea, ese es el entorno que nombra.
    por_nombre = {n: re.compile(_patrones_referencia([n])) for n in nombres}
    mapa: dict[str, list[str]] = {n: [] for n in nombres}
    for linea in salida.splitlines():
        for n, rx in por_nombre.items():
            if not rx.search(linea):
                continue
            # `grep -n` imprime ruta:linea:contenido, y el contenido puede
            # traer sus propios dos puntos. Partir por los dos ultimos deja el
            # numero de linea pegado a la ruta, asi que se ancla en `:<d>:`.
            enc = re.match(r"^(.+?):(\d+):", linea)
            ruta = enc.group(1) if enc else linea
            try:
                ruta = str(Path(ruta).relative_to(workspace))
            except ValueError:
                pass
            if ruta not in mapa[n] and len(mapa[n]) < 5:
                mapa[n].append(ruta)
            break
    return {n: v for n, v in mapa.items() if v}, ""


# ---------------------------------------------------------------------------
# Clasificacion
# ---------------------------------------------------------------------------

def clasificar(
    raiz_envs: Path,
    workspace: Path,
    dias: int,
    proteger: tuple[str, ...],
    con_refs: bool,
    timeout: int,
) -> dict[str, Any]:
    """Hechos por entorno. No decide: clasifica y reporta."""
    corte = time.time() - dias * 86400
    dirs, motivo = descubrir_entornos(raiz_envs)
    if not dirs:
        return {"no_verificado": motivo, "entornos": []}

    nombres = [d.name for d in dirs]
    if con_refs:
        refs, nota_refs = buscar_referencias(workspace, nombres, timeout)
        if nota_refs:
            return {"no_verificado": nota_refs, "entornos": []}
    else:
        refs, nota_refs = {}, "escaneo de referencias desactivado con --sin-refs"

    filas: list[dict[str, Any]] = []
    for d in dirs:
        nombre = d.name
        reciente, fallo = pyc_en_ventana(d, corte, timeout)
        if reciente is None:
            return {"no_verificado": f"{nombre}: {fallo}", "entornos": []}
        fila: dict[str, Any] = {
            "entorno": nombre,
            "ejecutado_en_ventana": reciente,
            "referencias": refs.get(nombre, []),
        }
        if not reciente:
            fila["ultimo_pyc"] = ultimo_pyc(d, timeout)
        bytes_exc, entradas = bytes_exclusivos(d)
        fila["bytes_exclusivos"] = bytes_exc
        fila["bytes_aparentes"] = d.stat().st_size if d.is_file() else bytes_exc
        fila["entradas"] = entradas
        if reciente:
            fila["clase"] = "en_uso"
        elif nombre in proteger:
            fila["clase"] = "protegido"
        elif fila["referencias"]:
            fila["clase"] = "referenciado"
        else:
            fila["clase"] = "frio"
        filas.append(fila)
    return {"no_verificado": None, "entornos": filas, "nota_refs": nota_refs}


def construir_resultado(corte_datos: dict[str, Any], dias: int) -> dict[str, Any]:
    """Traduce hechos a la dimension. Aqui vive el veredicto, no la medicion."""
    if corte_datos.get("no_verificado"):
        return {
            "dimension": "entornos",
            "estado": "no_verificado",
            "resumen": f"NO SE PUDO COMPROBAR: {corte_datos['no_verificado']}",
            "evidencia": {"motivo": corte_datos["no_verificado"]},
            "accion": "No tomes esto como evidencia. Arregla la comprobacion y vuelve a medir.",
        }

    filas = corte_datos["entornos"]
    frios = [f for f in filas if f["clase"] == "frio"]
    protegidos = [f for f in filas if f["clase"] == "protegido"]
    referenciados = [f for f in filas if f["clase"] == "referenciado"]
    en_uso = [f for f in filas if f["clase"] == "en_uso"]
    recuperable = sum(f["bytes_exclusivos"] for f in frios)
    aparente = sum(f.get("bytes_aparentes", 0) for f in frios)

    return {
        "dimension": "entornos",
        "estado": "aviso" if frios else "ok",
        "resumen": (
            f"{len(frios)} de {len(filas)} entornos frios, "
            f"{recuperable / 1e9:.2f} GB de bloques exclusivos"
            if frios else
            f"los {len(filas)} entornos estan en uso o protegidos por politica"
        ),
        "evidencia": {
            "criterio": {
                "ventana_dias": dias,
                "senal": "cero .pyc generados en la ventana (los crea la ejecucion, "
                         "no la instalacion de paquetes)",
                "referencias": "anclajes de uso real de conda, no el nombre suelto "
                               "(`IA` como palabra da 226 falsos positivos)",
            },
            "entornos_medidos": len(filas),
            "reparto": {
                "en_uso": [f["entorno"] for f in en_uso],
                "protegido": [f["entorno"] for f in protegidos],
                "referenciado": [f["entorno"] for f in referenciados],
                "frio": [f["entorno"] for f in frios],
            },
            "recuperable_bytes_exclusivos": recuperable,
            "peso_aparente_frios": aparente,
            "detalle_frios": [
                {
                    "entorno": f["entorno"],
                    "bytes_exclusivos": f["bytes_exclusivos"],
                    "ultimo_pyc": f.get("ultimo_pyc"),
                    "entradas": f["entradas"],
                }
                for f in frios
            ],
            "nota_referencias": corte_datos.get("nota_refs", ""),
        },
        "accion": (
            "Hay entornos frios con peso real. Cada uno necesita un recipe "
            "(`conda env export`) committed ANTES de borrarlo, y decidir uno por "
            "uno. Esta dimension no borra nada."
            if frios else
            "No hay entornos frios. Si esto parece improbable despues de una "
            "limpieza, comprueba que el umbral de dias no se haya movido."
        ),
    }


def construir_parser() -> _Parser:
    p = _Parser(
        description="Audita entornos conda frios y su peso en bloques exclusivos (solo lectura).",
    )
    p.add_argument("--envs-root", default="~/anaconda3/envs",
                   help="directorio de entornos (default: ~/anaconda3/envs)")
    p.add_argument("--workspace", default="~/MEGA/VS_CODE_WORKSPACE",
                   help="raiz donde se buscan referencias (default: ~/MEGA/VS_CODE_WORKSPACE)")
    p.add_argument("--dias", type=int, default=DIAS_POR_DEFECTO,
                   help=f"ventana de ejecucion en dias (default: {DIAS_POR_DEFECTO})")
    p.add_argument("--timeout", type=int, default=120,
                   help="segundos por cada find/grep (default: 120)")
    p.add_argument("--proteger", default=",".join(PROTEGIDOS_POR_POLITICA),
                   help="entornos que se conservan aunque esten frios "
                        f"(default: {','.join(PROTEGIDOS_POR_POLITICA)})")
    p.add_argument("--sin-refs", action="store_true",
                   help="no escanear referencias (mas rapido, pero clasifica como "
                        "frio un entorno que otro proyecto pueda nombrar)")
    p.add_argument("--json", action="store_true", help="imprime solo el JSON")
    return p


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    if args.dias < 1:
        print("error: --dias debe ser >= 1", file=sys.stderr)
        return 3
    if args.timeout < 1:
        print("error: --timeout debe ser >= 1", file=sys.stderr)
        return 3
    proteger = tuple(x.strip() for x in args.proteger.split(",") if x.strip())
    corte = clasificar(
        Path(args.envs_root).expanduser(),
        Path(args.workspace).expanduser(),
        args.dias, proteger, not args.sin_refs, args.timeout,
    )
    resultado = construir_resultado(corte, args.dias)

    if not args.json:
        ev = resultado["evidencia"]
        print(f"  {resultado['estado'].upper():<13} {resultado['resumen']}")
        if ev.get("reparto"):
            for clase, lista in ev["reparto"].items():
                if lista:
                    print(f"                 {clase:<12} {', '.join(lista)}")
            if ev.get("recuperable_bytes_exclusivos"):
                print(f"                 exclusivo {ev['recuperable_bytes_exclusivos'] / 1e9:.2f} GB"
                      f"  (aparente {ev.get('peso_aparente_frios', 0) / 1e9:.2f} GB)")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
