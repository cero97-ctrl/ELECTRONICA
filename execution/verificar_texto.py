#!/usr/bin/env python3
"""Deteccion acotada de corrupcion de texto en prosa del repo.

Este script existe por un fallo repetido y mal detectado: prosa en espanol
generada por el agente se corrompe fusionando palabras funcionales con la
palabra siguiente ("susArréglalo", "seQFUEran") o introduciendo escritura
extranjera (cirilico, CJK, formas de ancho completo). Cinco veces en una
sesion, dos de ellas invisibles a las comprobaciones.

El diseno responde a los tres errores queolitieron al detectarlo:

1. Un validador de "palabras pegadas" devolvio 402 hallazgos, todos falsos
   positivos, porque treating normal markdown as a typo. Aqui las heuristicas
   estan DESACTIVADAS por defecto y hay que pedirlas explicitamente con
   --class. Un detector que marca todo no detecta nada.

2. Un escaneo de repo completo arrastro miles de falsos positivos de un clon
   tercero en chino bajo .tmp/. Por eso el alcance es explicito, se excluyen
   nombres de directorio por defecto y el informe dice QUE se escaneo y QUE se
   salto, con el motivo. Los dos ficheros meta quedan excluidos: el de
   detecciones y este mismo contienen, por definicion, los caracteres y las
   cadenas que se cazan, asi que incluirlos daria falsos positivos
   garantizados.

3. Un "0 anomalias" se acepto sin verificar cobertura: las cadenas concretas
   estaban en un archivo y la corrupcion en otro. Aqui, si no se escanea
   ningun fichero, el script falla con codigo 2 en vez de devolver un verde
   falso. Un cero solo es informacion si viene con su cobertura.

Clases de deteccion:

  script     Cirilico, CJK, japones, coreano y formas de ancho completo en
             prosa en espanol. Precision muy alta en este repo. Es la clase
             que de verdad funciono durante la sesion que motivo el script.

  conocido   Cadenas literales de corrupciones ya observadas, cargadas de
             execution/detecciones_texto.json. Reactiva por naturaleza:
             solo detecta lo que alguien anadio antes. Sirve de red de
             seguridad, no de detector primario.

  camel      Minuscula seguida de mayuscula dentro de una palabra. Heuristica
             y por tanto opt-in: encuentra "seQFUEran" pero tambien nombres
             de API legitimos.

Codigos de salida:

  0  Sin hallazgos. El informe incluye el alcance escaneado.
  1  Hay hallazgos. El informe los lista con fichero, linea y clase.
  2  Uso incorrecto, o ningun fichero se pudo escanear. Nunca se reporta
     "limpio" cuando no se comprobo nada.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Iterator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWN_FILE = Path(__file__).resolve().parent / "detecciones_texto.json"

DEFAULT_EXCLUDES = (
    ".git",
    ".tmp",
    "node_modules",
    "chroma_db",
    "__pycache__",
    ".venv",
    "venv",
    ".pio",
    ".pio-mcp-workspace",
    "build",
    ".cache",
    "site-packages",
)

SCRIPT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("cirilico", r"[\u0400-\u04FF]"),
    ("cirilico_ext", r"[\u0500-\u052F]"),
    ("cjk_unificado", r"[\u4E00-\u9FFF]"),
    ("cjk_ext_a", r"[\u3400-\u4DBF]"),
    ("hiragana", r"[\u3040-\u309F]"),
    ("katakana", r"[\u30A0-\u30FF]"),
    ("hangul", r"[\uAC00-\uD7AF]"),
    ("ancho_completo", r"[\uFF00-\uFFEF]"),
)

# El Griego se excluido a proposito, y es la decision mas importante de este
# fichero. La primera version lo incluia y devolvio 127 hallazgos, de los
# cuales 123 (97%) eran Omega, beta, pi, mu, tau, rho, sigma y demas: la
# notacion normal de un repo de electronica y semiconductores. Un detector que
# marca el 97% del contenido sano del dominio no detecta corrupcion, clasifica
# el dominio como ajeno. Antes de anadir un patron por "parece sospechoso",
# hay que medirlo contra contenido que se sabe legitimo del propio repo.

CAMEL_RE = re.compile(r"(?<=[a-záéíóúñü])(?=[A-ZÁÉÍÓÚÑÜ])")


def sin_diacriticos(texto: str) -> str:
    """Normaliza a ASCII conservando mayusculas y minusculas.

    El emparejamiento de cadenas conocidas debe ser insensible a los
    diacriticos: la palabra corrompida se puede escribir con o sin tilde
    ("susArreglalo" y "susArreglalo" son el mismo fallo), y un detector que
    solo pilla una de las dos formas deja pasar la mitad de los casos.
    """
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))

TEXT_SUFFIXES = {
    ".md", ".tex", ".py", ".yaml", ".yml", ".txt", ".json", ".cfg", ".ini",
    ".sh", ".rst", ".adoc", ".csv", ".env", ".example", ".desktop", ".service",
}

SKIP_FILENAMES = {
    "package-lock.json", "poetry.lock", "uv.lock", "Cargo.lock",
    ".gitignore", ".gitattributes",
}

META_FILENAMES = {
    "detecciones_texto.json",
    "verificar_texto.py",
    "test_verificar_texto.py",
}


@dataclass
class Hallazgo:
    fichero: str
    linea: int
    columna: int
    clase: str
    detalle: str
    fragmento: str


@dataclass
class Cobertura:
    ficheros_escaneados: int
    ficheros_omitidos: int
    ficheros_no_texto: int
    lineas_escaneadas: int
    directorios_excluidos: list[str]
    motivos_omision: dict[str, int]
    modo: str


def _rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(p)


def cargar_conocidos(ruta_extra: Path | None = None) -> dict[str, list[str]]:
    datos: dict[str, list[str]] = {"cadenas": [], "permitidas": []}
    for ruta in (KNOWN_FILE, ruta_extra):
        if ruta is None or not ruta.is_file():
            continue
        try:
            crudo = json.loads(ruta.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise SystemExit(f"no se pudo leer {ruta}: {exc}") from exc
        for clave in ("cadenas", "permitidas"):
            valores = crudo.get(clave, [])
            if not isinstance(valores, list):
                raise SystemExit(f"{ruta}: '{clave}' debe ser una lista")
            datos[clave].extend(str(v) for v in valores)
    return datos


def motivo_exclusion(p: Path) -> str | None:
    """Clasifica un fichero. None = escanear.

    Distinguir 'no es texto' de 'no se pudo leer' importa: un PDF no es una
    omision que deba revisar nadie, y Contarlo como tal convierte la cobertura
    en ruido que obliga a ignorar el veredicto.
    """
    if p.name in META_FILENAMES:
        return "meta"
    if p.name in SKIP_FILENAMES:
        return "no_texto"
    if p.suffix.lower() in TEXT_SUFFIXES:
        return None
    return "no_texto"


def iterar_ficheros(
    raices: Iterable[Path], excluye: tuple[str, ...]
) -> Iterator[tuple[Path, str, str | None]]:
    """Recorre el alcance yielding (ruta, origen, motivo_de_exclusion).

    El filtro de escaneabilidad se aplica tambien a los ficheros que llegan
    como argumento explicito. La exclusion de los ficheros meta es una
    propiedad de su CONTENIDO (contienen, por definicion, lo que se caza), no
    del modo de descubrirlo: pedirlo a mano no lo convierte en otra cosa.
    """
    vistos: set[Path] = set()
    for raiz in raices:
        raiz = raiz.resolve()
        if raiz.is_file():
            vistos.add(raiz)
            yield raiz, "archivo", motivo_exclusion(raiz)
            continue
        if not raiz.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(raiz):
            dp = Path(dirpath)
            dirnames[:] = sorted(
                d for d in dirnames if d not in excluye and not d.startswith(".git")
            )
            for nombre in sorted(filenames):
                p = dp / nombre
                if p in vistos:
                    continue
                vistos.add(p)
                yield p, "directorio", motivo_exclusion(p)


def escanear_texto(
    texto: str,
    ruta_logica: str,
    patrones: tuple[tuple[str, str], ...],
    conocidos: list[str],
    permitidas: list[str],
    clases: set[str],
) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    permitidas_efectivas = [a for a in permitidas if a]
    conocida_norm = [(c, sin_diacriticos(c)) for c in conocidos if c]
    for n_linea, linea in enumerate(texto.splitlines(), start=1):
        if any(a in linea for a in permitidas_efectivas):
            continue
        if "script" in clases:
            for nombre, patron in patrones:
                for m in re.finditer(patron, linea):
                    hallazgos.append(
                        Hallazgo(
                            fichero=ruta_logica,
                            linea=n_linea,
                            columna=m.start() + 1,
                            clase="script",
                            detalle=f"{nombre} U+{ord(m.group()):04X}",
                            fragmento=linea.strip()[:160],
                        )
                    )
        if "conocido" in clases:
            linea_norm = sin_diacriticos(linea)
            for original, forma in conocida_norm:
                pos = linea_norm.find(forma)
                if pos != -1:
                    hallazgos.append(
                        Hallazgo(
                            fichero=ruta_logica,
                            linea=n_linea,
                            columna=pos + 1,
                            clase="conocido",
                            detalle=original,
                            fragmento=linea.strip()[:160],
                        )
                    )
        if "camel" in clases:
            for m in CAMEL_RE.finditer(linea):
                Trozo = linea[max(0, m.start() - 30) : m.start() + 30]
                hallazgos.append(
                    Hallazgo(
                        fichero=ruta_logica,
                        linea=n_linea,
                        columna=m.start() + 1,
                        clase="camel",
                        detalle="minuscula seguida de mayuscula dentro de palabra",
                        fragmento=Trozo.strip(),
                    )
                )
    return hallazgos


def diff_añadido(ref: str) -> tuple[str, str]:
    cmd = ["git", "diff", "--unified=0", f"{ref}..HEAD"]
    try:
        salida = subprocess.run(
            cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=120
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"no se pudo ejecutar git diff contra {ref}: {exc}") from exc
    if salida.returncode != 0:
        raise SystemExit(f"git diff {ref}..HEAD fallo: {salida.stderr.strip()}")
    bloques: list[tuple[str, int, str]] = []
    fichero = "<diff>"
    n_linea = 0
    for raw in salida.stdout.splitlines():
        if raw.startswith("+++ b/"):
            fichero = raw[6:].strip()
        elif raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            n_linea = int(m.group(1)) if m else 0
        elif raw.startswith("+") and not raw.startswith("+++"):
            bloques.append((fichero, n_linea, raw[1:]))
            n_linea += 1
        elif raw.startswith(" "):
            n_linea += 1
    return ("diff", "\n".join(linea for _, _, linea in bloques)), bloques  # type: ignore[return-value]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Detecta corrupcion de texto (scripts extranjeros, cadenas conocidas, camel) en prosa del repo."
    )
    ap.add_argument(
        "rutas", nargs="*",
        help="Ficheros o directorios a escanear. Sin argumentos usa el alcance por defecto del repo.",
    )
    ap.add_argument(
        "--diff", metavar="REF",
        help="Escanea solo las lineas anadidas por los commits posteriores a REF.",
    )
    ap.add_argument(
        "--class", dest="clases", action="append", default=None,
        choices=["script", "conocido", "camel"],
        help="Clase a activar. Repetible. Default: script,conocido (camel es heuristica y va apagada).",
    )
    ap.add_argument("--known-file", type=Path, help="Fichero adicional de cadenas conocidas/permitidas.")
    ap.add_argument("--exclude", action="append", default=[], help="Directorio a excluir (adicional al default).")
    ap.add_argument("--json", action="store_true", help="Salida en JSON por stdout.")
    ap.add_argument("--max-ficheros", type=int, default=4000, help="Tope de ficheros por pasada.")
    args = ap.parse_args(argv)

    clases = set(args.clases) if args.clases else {"script", "conocido"}
    excluye = tuple(DEFAULT_EXCLUDES) + tuple(args.exclude)
    conocidos = cargar_conocidos(args.known_file)

    hallazgos: list[Hallazgo] = []
    omitidos = 0
    omitidos_meta = 0
    omitidos_ilegible = 0
    omitidos_tope = 0
    no_texto = 0
    lineas = 0
    ficheros = 0
    modo = "arbol"

    if args.diff:
        modo = f"diff:{args.diff}..HEAD"
        _, bloques = diff_añadido(args.diff)
        if not bloques:
            print(f"git diff {args.diff}..HEAD no anadio lineas: nada que escanear.", file=sys.stderr)
            return 2
        por_fichero: dict[str, list[tuple[int, str]]] = {}
        for fichero, n, linea in bloques:
            por_fichero.setdefault(fichero, []).append((n, linea))
        for fichero, items in por_fichero.items():
            ficheros += 1
            lineas += len(items)
            for n, linea in items:
                hallazgos.extend(
                    escanear_texto(
                        linea, f"{fichero}:{n}", SCRIPT_PATTERNS,
                        conocidos["cadenas"], conocidos["permitidas"], clases,
                    )
                )
    else:
        raices = [Path(r) if Path(r).is_absolute() else PROJECT_ROOT / r for r in args.rutas]
        if not raices:
            raices = [PROJECT_ROOT / "Sessions", PROJECT_ROOT / "docs", PROJECT_ROOT / "directives",
                      PROJECT_ROOT / "execution", PROJECT_ROOT / "cursos", PROJECT_ROOT / "Proyectos"]
        for p, origen, motivo in iterar_ficheros(raices, excluye):
            if motivo == "meta":
                omitidos_meta += 1
                continue
            if motivo == "no_texto":
                no_texto += 1
                continue
            if ficheros >= args.max_ficheros:
                omitidos_tope += 1
                continue
            try:
                texto = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                omitidos_ilegible += 1
                continue
            ficheros += 1
            lineas += len(texto.splitlines())
            hallazgos.extend(
                escanear_texto(
                    texto, _rel(p), SCRIPT_PATTERNS,
                    conocidos["cadenas"], conocidos["permitidas"], clases,
                )
            )

    omitidos = omitidos_meta + omitidos_tope + omitidos_ilegible
    cobertura = Cobertura(
        ficheros_escaneados=ficheros,
        ficheros_omitidos=omitidos,
        lineas_escaneadas=lineas,
        directorios_excluidos=list(excluye),
        ficheros_no_texto=no_texto,
        motivos_omision={
            "fichero_meta": omitidos_meta,
            "ilegible": omitidos_ilegible,
            "tope_max_ficheros": omitidos_tope,
        },
        modo=modo,
    )

    if ficheros == 0:
        informe = {
            "estado": "sin_verificar",
            "motivo": "no se escaneo ningun fichero; un verde aqui es un falso negativo",
            "cobertura": asdict(cobertura),
            "hallazgos": [],
        }
        if args.json:
            print(json.dumps(informe, ensure_ascii=False, indent=2))
        else:
            print("SIN VERIFICAR: no se escaneo ningun fichero.")
            print("Revisa las rutas, las exclusiones o el limite --max-ficheros.")
        return 2

    informe = {
        "estado": "limpio" if not hallazgos else "con_hallazgos",
        "clases_activas": sorted(clases),
        "cadenas_conocidas_cargadas": len(conocidos["cadenas"]),
        "cobertura": asdict(cobertura),
        "hallazgos": [asdict(h) for h in hallazgos],
    }

    if args.json:
        print(json.dumps(informe, ensure_ascii=False, indent=2))
    else:
        print(f"== Verificacion de texto ({', '.join(sorted(clases))}) ==")
        print(f"  ficheros: {ficheros}  lineas: {lineas}  omitidos: {omitidos}")
        print(f"  cadenas conocidas cargadas: {len(conocidos['cadenas'])}")
        if hallazgos:
            print(f"  HALLAZGOS: {len(hallazgos)}")
            for h in hallazgos[:50]:
                print(f"    [{h.clase}] {h.fichero}:{h.linea}:{h.columna}  {h.detalle}")
                print(f"        {h.fragmento}")
            if len(hallazgos) > 50:
                print(f"    ... y {len(hallazgos) - 50} mas")
        else:
            print("  Sin hallazgos en el alcance escaneado.")
    return 1 if hallazgos else 0


if __name__ == "__main__":
    sys.exit(main())
