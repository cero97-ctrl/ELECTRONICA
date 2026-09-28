#!/usr/bin/env python3
"""
catalogo_disco.py — Catálogo autoritativo de rutas borrables + barrera de seguridad
(Layer 3: Execution, módulo de datos compartido por disco_medir.py y disco_purgar.py).

Este archivo es la ÚNICA fuente de verdad de "qué se puede borrar". No hay lógica de
decisión ni de negociación: solo una lista declarativa de targets (ruta, tier, modo,
edad mínima) y las funciones de validación que impiden borrar fuera de ella.

Principio de seguridad (4 barreras, todas deben pasar):
  1. WHITELIST    : la ruta debe coincidir con una entrada de CATALOGO. Nunca se
                    recorren directorios buscando "lo que se pueda borrar".
  2. RAÍZ         : debe resolver bajo $HOME, /tmp o la raíz del repo.
  3. NO PROTEGIDO : no puede ser un path protegido ni estar dentro de uno.
  4. NO CONTIENE  : no puede contener ningún path protegido (impide borrar
                    ~/.local/share/opencode, que aloja opencode.db de 651 MB).

Tiers (el nivel lo elige el operador; el script NUNCA escala solo):
  seguro      — caché pura, se regenera sola, cero riesgo de perder trabajo.
  recargable  — se regenera pero exige volver a descargar (navegadores, toolchains).
  pesado      — se regenera pero cuesta mucho (modelos IA; rag_system.py re-embedea).

Nada de este catálogo requiere sudo. Lo que sí lo requiere (journal, apt) se reporta
como pista y lo ejecuta el operador a mano (`--sudo-hint`).

Uso:
  from catalogo_disco import CATALOGO, objetivos_por_tier, validar_destino
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

# ── Raíces del espacio de trabajo ──────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home()

TIERS: tuple[str, ...] = ("seguro", "recargable", "pesado")
MODOS: tuple[str, ...] = ("nativo", "contenido", "directorio", "glob", "rotar")


# ── Modelo de un target ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Target:
    """Una entrada borrable, declarada de forma explícita y auditable.

    ruta           Path absoluto (o con comodín) que se evalúa.
    tier           seguro | recargable | pesado.
    modo           nativo   -> ejecuta `cmd` (herramienta oficial; preference).
                   contenido -> borra las entradas internas, conserva el directorio.
                   directorio-> borra el directorio completo (y lo recrea si recrear).
                   glob      -> borra solo las entradas que casen con `patron`.
                   rotar     -> conserva los `mantener` mas recientes, borra el resto.
    min_edad_dias  No se toca nada modificado mas recientemente que esto.
                   Protege descargas/compilaciones en curso.
    cmd            Comando nativo opcional (modo=nativo). Se usa si `which` lo
                   encuentra; si no, se cae al `fallback`.
    fallback       (ruta, modo) alternativos cuando el comando nativo no existe o falla.
    recrear        Tras purgar un `directorio`, recrear el directorio vacío.
    medir_exclusivo
                   Que `bytes_purgables` sea el peso en bloques EXCLUSIVOS
                   (st_nlink == 1) y no el tamano aparente. Es necesario en
                   los targets con hardlinks: `du` cuenta un fichero con
                   n>1 una vez por recorrido, asi que midiendo solo `pkgs/`
                   sigue contando bloques que un entorno vivo sigue
                   enlazando. Borrar la entrada de `pkgs` no libera ese
                   bloque: sigue vivo en `envs/`. Purgar segun el peso
                   aparente promete espacio que no existe.
    """

    id: str
    ruta: str
    tier: str
    modo: str
    descripcion: str
    min_edad_dias: int = 1
    cmd: str | None = None
    fallback: tuple[str, str] | None = None
    mantener: int = 0
    patron: str = "*"
    recrear: bool = False
    medir_exclusivo: bool = False

    def ruta_resuelta(self) -> Path:
        return Path(self.ruta).expanduser()


# ── El catálogo ────────────────────────────────────────────────────────────────
# Ordenado por tier y luego por tamaño esperado (descendente en la práctica) para
# que un run interrumpido ya haya recuperado lo mas rentables.
CATALOGO: tuple[Target, ...] = (
    # ══ TIER SEGURO ═════════════════════════════════════════════════════════════
    Target(
        id="arduino-staging",
        ruta="~/.arduino15/staging",
        tier="seguro",
        modo="contenido",
        descripcion="Descargas a medio desempaquetar del IDE Arduino (basura pura).",
        min_edad_dias=1,
    ),
    Target(
        id="trash",
        ruta="~/.local/share/Trash/files",
        tier="seguro",
        modo="contenido",
        descripcion="Papelera del escritorio: archivos ya borrados por el usuario.",
        min_edad_dias=1,
    ),
    Target(
        id="trash-info",
        ruta="~/.local/share/Trash/info",
        tier="seguro",
        modo="contenido",
        descripcion="Metadatos .trashinfo de la papelera (huérfanos tras vaciarla).",
        min_edad_dias=1,
    ),
    Target(
        id="pycache-repo",
        ruta=f"{REPO_ROOT}",
        tier="seguro",
        modo="glob",
        patron="__pycache__",
        descripcion="Bytecode Python compilado (.pyc) de todo el repo: se regenera al importar.",
        min_edad_dias=2,
    ),
    Target(
        id="uv-cache",
        ruta="~/.local/share/uv",
        tier="seguro",
        modo="contenido",
        descripcion="Cache de paquetes/wheels de uv (equivalente a pip cache).",
        min_edad_dias=1,
        cmd="uv cache clean",
    ),
    Target(
        id="npm-cacache",
        ruta="~/.npm/_cacache",
        tier="seguro",
        modo="contenido",
        descripcion="Cache de contenido de npm (lo que rompia el arranque MCP con npx).",
        min_edad_dias=1,
        cmd="npm cache clean --force",
    ),
    Target(
        id="npm-npx",
        ruta="~/.npm/_npx",
        tier="seguro",
        modo="contenido",
        descripcion="Arboles de ejecucion efimera de npx: se recrean al volver a usar npx.",
        min_edad_dias=1,
    ),
    Target(
        id="pip-cache",
        ruta="~/.cache/pip",
        tier="seguro",
        modo="contenido",
        descripcion="Cache HTTP/wheels de pip.",
        min_edad_dias=1,
        cmd="pip cache purge",
    ),
    Target(
        id="thumbnails",
        ruta="~/.cache/thumbnails",
        tier="seguro",
        modo="contenido",
        descripcion="Miniaturas de GNOME; se regeneran al navegar el gestor de archivos.",
        min_edad_dias=1,
    ),
    Target(
        id="node-gyp",
        ruta="~/.cache/node-gyp",
        tier="seguro",
        modo="contenido",
        descripcion="Headers de compilacion descargados por node-gyp.",
        min_edad_dias=1,
    ),
    Target(
        id="arduino-cache",
        ruta="~/.cache/arduino",
        tier="seguro",
        modo="contenido",
        descripcion="Cache de descargas del IDE Arduino (~/.cache, no el toolchain).",
        min_edad_dias=1,
    ),
    Target(
        id="mesa-shaders",
        ruta="~/.cache/mesa_shader_cache",
        tier="seguro",
        modo="contenido",
        descripcion="Cache de shaders de Mesa; se recompila en el primer arranque 3D.",
        min_edad_dias=1,
    ),
    Target(
        id="mesa-shaders-db",
        ruta="~/.cache/mesa_shader_cache_db",
        tier="seguro",
        modo="contenido",
        descripcion="Variante .db de la cache de shaders de Mesa.",
        min_edad_dias=1,
    ),
    Target(
        id="mintinstall",
        ruta="~/.cache/mintinstall",
        tier="seguro",
        modo="contenido",
        descripcion="Cache de descargadores de mintinstall (instaladores .deb parciales).",
        min_edad_dias=1,
    ),
    Target(
        id="opencode-logs",
        ruta="~/.local/share/opencode/log",
        tier="seguro",
        modo="rotar",
        mantener=3,
        descripcion="Rotacion de logs de opencode: conserva los 3 mas recientes.",
        min_edad_dias=0,
    ),
    Target(
        id="tmp-latex",
        ruta=f"{REPO_ROOT}/.tmp/latex_build",
        tier="seguro",
        modo="contenido",
        descripcion="Artefactos intermedios de compilacion LaTeX (los borra compile_latex.py).",
        min_edad_dias=1,
    ),
    Target(
        id="tmp-clones",
        ruta=f"{REPO_ROOT}/.tmp/repo_clone_*",
        tier="seguro",
        modo="glob",
        patron="repo_clone_*",
        descripcion="Clones Git temporales de .tmp/ (flujos libro_a_skill / repo_a_skill).",
        min_edad_dias=7,
    ),
    # ══ TIER RECARGABLE ════════════════════════════════════════════════════════
    Target(
        id="conda-pkgs",
        ruta="~/anaconda3/pkgs",
        tier="recargable",
        modo="nativo",
        cmd="conda clean --all -y",
        descripcion="Cache de paquetes de conda: tarballs, indice y paquetes sin uso. "
                    "MEDIDURA OBLIGATORIA EN EXCLUSIVO: conda hardlinkea cada paquete "
                    "contra los entornos que lo usan, asi que la carpeta ronda los 7 GB "
                    "aparentes y solo ~2 GB son bloques exclusivos. Los demas siguen "
                    "enlazados desde envs/: 'conda clean' no los toca y borrarlos no "
                    "libera ni un byte. Por eso este target lleva medir_exclusivo=True; "
                    "prometer los 7 GB seria mentir con una medicion real. Ojo: "
                    "'conda clean --all' no comprueba paquetes instalados con enlaces "
                    "simbolicos al cache, por lo que puede romper esos envs; "
                    "verificado antes que ningun env de esta maquina los usa. -y es "
                    "necesario porque el flujo lo ejecuta sin terminal interactiva.",
        min_edad_dias=1,
        medir_exclusivo=True,
    ),
    Target(
        id="arduino-packages",
        ruta="~/.arduino15/packages",
        tier="recargable",
        modo="contenido",
        descripcion="Toolchains del IDE Arduino (cores ESP32, etc.): ~5.4 GB que se "
                    "re-descargan; el IDE no arranca hasta que terminen de bajar.",
        min_edad_dias=1,
    ),
    Target(
        id="puppeteer",
        ruta="~/.cache/puppeteer",
        tier="recargable",
        modo="contenido",
        descripcion="Chromium descargado por Puppeteer; se re-descarga al reinstalar.",
        min_edad_dias=1,
    ),
    Target(
        id="google-chrome",
        ruta="~/.cache/google-chrome",
        tier="recargable",
        modo="contenido",
        descripcion="Perfil/cache de Chrome for Testing; se regenera al abrirlo.",
        min_edad_dias=1,
    ),
    Target(
        id="opera",
        ruta="~/.cache/opera",
        tier="recargable",
        modo="contenido",
        descripcion="Cache de Opera; se regenera al abrirlo.",
        min_edad_dias=1,
    ),
    Target(
        id="playwright-go",
        ruta="~/.cache/ms-playwright-go",
        tier="recargable",
        modo="contenido",
        descripcion="Binarios de Playwright; se re-descargan con `playwright install`.",
        min_edad_dias=1,
    ),
    Target(
        id="mozilla",
        ruta="~/.cache/mozilla",
        tier="recargable",
        modo="contenido",
        descripcion="Cache de Firefox/Thunderbird.",
        min_edad_dias=1,
    ),
    Target(
        id="cloud-code",
        ruta="~/.cache/cloud-code",
        tier="recargable",
        modo="contenido",
        descripcion="Cache de la extension Cloud Code (VS Code).",
        min_edad_dias=1,
    ),
    # ══ TIER PESADO ═════════════════════════════════════════════════════════════
    Target(
        id="huggingface",
        ruta="~/.cache/huggingface",
        tier="pesado",
        modo="contenido",
        descripcion="Modelos/embeddings de Hugging Face; rag_system.py debe re-embeber.",
        min_edad_dias=1,
    ),
    Target(
        id="chroma-model",
        ruta="~/.cache/chroma",
        tier="pesado",
        modo="contenido",
        descripcion="Modelo ONNX de embeddings de Chroma; se re-descarga al indexar.",
        min_edad_dias=1,
    ),
)


# ── Paths protegidos: jamás se borran ni se puede contener un borrado ──────────
_PROTEGIDOS_ABSOLUTOS: tuple[str, ...] = (
    "/", "/home", "/etc", "/usr", "/var", "/opt", "/boot", "/dev", "/proc",
    "/sys", "/bin", "/sbin", "/lib", "/lib64", "/srv", "/media", "/mnt",
)

#: Rutas relativas que se protegen bajo CUALQUIER de las bases de abajo.
_PROTEGIDOS_RELATIVOS: tuple[str, ...] = (
    ".git", "Sessions", "docs", "cursos", "Proyectos", "directives",
    "execution", "chroma_db", "datasets",
    ".env", ".groq_api_key", "db_state.json", "opencode.json",
    ".platformio", ".npm-global", ".ssh", ".gnupg",
    "Arduino", "libraries", "sketches",
    ".config/opencode",
    ".local/share/solana", ".local/share/waydroid", ".local/share/data",
    ".local/share/unity3d",
)

#: Patrones con comodín, resueltos contra la raíz del repo.
_PROTEGIDOS_GLOB: tuple[str, ...] = ("mcp_*.py", "flujo_*.py")


def contenedor_de(t: Target) -> Path:
    """Directorio contenedor del target: el que NO se borra en contenido/glob/rotar.

    Un solo lugar decide esto, porque discrepar del criterio es como se midió el
    directorio equivocado: si la ruta lleva comodín (`repo_clone_*`) el contenedor
    es su padre; si no, el contenedor es la propia ruta (un glob puede declararse
    como `base` + `patron` sin comodín en la ruta, p. ej. `__pycache__` en el repo).
    """
    ruta = t.ruta_resuelta()
    return ruta.parent if any(c in t.ruta for c in "*?[") else ruta


def _norm(p: Path | str) -> Path:
    """Normaliza a ruta absoluta sin resolver symlinks intermedios (para comparar)."""
    return Path(os.path.abspath(os.path.expanduser(str(p))))


#: Rutas que se protegen como destino EXACTO, nunca como ancestro. Comparar `/` o
#: `$HOME` como ancestro bloquearía cualquier ruta absoluta del sistema o del usuario.
_SISTEMA_EXACTOS: frozenset[Path] = frozenset(
    [_norm(p) for p in _PROTEGIDOS_ABSOLUTOS] + [_norm(HOME)]
)

#: Archivos sueltos que deben sobrevivir (base $HOME).
_PROTEGIDOS_ARCHIVO: tuple[str, ...] = (
    ".local/share/opencode/opencode.db",
    ".local/share/opencode/opencode.db-wal",
    ".local/share/opencode/opencode.db-shm",
    ".bash_history", ".zsh_history",
)


#: Patrones con comodín, resueltos contra la raíz del repo.
_PROTEGIDOS_GLOB: tuple[str, ...] = ("mcp_*.py", "flujo_*.py")


def _bases() -> list[Path]:
    """Bases contra las que se resuelven los nombres relativos protegidos."""
    return [_norm(HOME), _norm(REPO_ROOT)]


def rutas_protegidas() -> list[Path]:
    """Lista absoluta de paths protegidos (sistema, herramientas y datos del usuario)."""
    salida: list[Path] = [_norm(p) for p in _PROTEGIDOS_ABSOLUTOS]
    salida.append(_norm(HOME))
    for base in _bases():
        for rel in _PROTEGIDOS_RELATIVOS:
            salida.append(base / rel)
        for pat in _PROTEGIDOS_GLOB:
            try:
                salida.extend(sorted(p for p in base.glob(pat) if p.is_file()))
            except OSError:
                pass
    for rel in _PROTEGIDOS_ARCHIVO:
        salida.append(_norm(HOME / rel))
    # Deduplicar preservando orden y excluir el repo de la lista de sus propios hijos.
    vistos: dict[Path, None] = {}
    for p in salida:
        vistos.setdefault(p, None)
    return [p for p in vistos if p != _norm(REPO_ROOT)]


def es_protegido(ruta: Path | str) -> str | None:
    """Devuelve el motivo si la ruta está protegida, o None si es borrable.

    Las raíces del sistema (`/`, `/home`, ...) solo se comparan por EXACTITUD: si se
    comprobaran como ancestros, `/` sería ancestro de toda ruta absoluta y no se
    borraría nada. La exclusión de rutas fuera de $HOME//tmp/repo la hace
    `es_raiz_permitida`.
    """
    r = _norm(ruta)
    for prot in rutas_protegidas():
        if r == prot:
            return f"protegido_exacto:{prot}"
        if prot in _SISTEMA_EXACTOS:
            continue
        if prot in r.parents:
            return f"protegido_ancestro:{prot}"
    return None


def contiene_protegido(ruta: Path | str) -> str | None:
    """Devuelve el path protegido contenido en `ruta`, o None."""
    r = _norm(ruta)
    for prot in rutas_protegidas():
        if prot == r:
            continue
        if prot.is_relative_to(r):
            return str(prot)
    return None


def es_raiz_permitida(ruta: Path | str) -> bool:
    r = _norm(ruta)
    for raiz in (_norm(HOME), _norm("/tmp"), _norm(REPO_ROOT)):
        if r == raiz or r.is_relative_to(raiz):
            # $HOME y el repo están permitidos como raíz, pero nunca como destino.
            if r in (_norm(HOME), _norm(REPO_ROOT), _norm("/tmp")):
                return False
            return True
    return False


# ── Barrera principal ──────────────────────────────────────────────────────────
def validar_destino(ruta: Path | str, *, exigir_en_catalogo: bool = True) -> tuple[bool, str]:
    """Aplica las 4 barreras. Devuelve (permitido, motivo).

    Es la función que disco_purgar.py consulta antes de tocar NADA. Los códigos de
    motivo son estables (se usan como claves en el JSON del informe):
      ok | no_existe | raiz_no_permitida | protegido_exacto:* | protegido_ancestro:*
      contiene_protegido:* | es_symlink | fuera_de_catalogo
    """
    r = _norm(ruta)

    if not r.exists():
        return False, "no_existe"

    if r.is_symlink():
        return False, "es_symlink"

    if not es_raiz_permitida(r):
        return False, "raiz_no_permitida"

    motivo = es_protegido(r)
    if motivo:
        return False, motivo

    contenido = contiene_protegido(r)
    if contenido:
        return False, f"contiene_protegido:{contenido}"

    if exigir_en_catalogo and not _esta_en_catalogo(r):
        return False, "fuera_de_catalogo"

    return True, "ok"


def _esta_en_catalogo(r: Path) -> bool:
    """Segunda barrera: la ruta debe corresponder a una entrada declarada.

    Se acepta el path del target, y —para los modos que operan sobre las entradas
    internas— cualquiera de sus hijos (contenido, glob, rotar).
    """
    for t in CATALOGO:
        base = _norm(t.ruta_resuelta())
        if r == base:
            return True
        if "*" in t.ruta and r.is_relative_to(base.parent):
            return True
        # Modos de entradas: cualquier descendiente del contenedor es una entrada
        # candidata legítima, siempre sujeto a las barreras de protegido/symlink.
        if t.modo in ("contenido", "glob", "rotar") and r != base and r.is_relative_to(base):
            return True
    return False


# ── Presentación ───────────────────────────────────────────────────────────────
_UNIDADES = ("B", "KB", "MB", "GB", "TB")


def TAMANO_HUMANO(n: int | float) -> str:
    """Formatea bytes en una escala legible (1,6 GB)."""
    valor = float(n)
    for unidad in _UNIDADES:
        if abs(valor) < 1024.0 or unidad == _UNIDADES[-1]:
            return f"{valor:.0f} {unidad}" if unidad == "B" else f"{valor:.1f} {unidad}"
        valor /= 1024.0
    return f"{valor:.1f} TB"


# ── Consultas sobre el catálogo ────────────────────────────────────────────────
def objetivo_por_id(ident: str) -> Target | None:
    for t in CATALOGO:
        if t.id == ident:
            return t
    return None


def objetivos_por_tier(tier: str | None) -> list[Target]:
    """Devuelve los targets del tier pedido. `seguro` NO arrastra los demas."""
    if tier is None or tier == "todos":
        return list(CATALOGO)
    return [t for t in CATALOGO if t.tier == tier]


def objetivo_nativo_disponible(t: Target) -> tuple[str | None, str]:
    """Resuelve el modo efectivo: comando nativo si existe, si no el fallback."""
    if t.modo == "nativo" and t.cmd:
        ejecutable = t.cmd.split()[0]
        if shutil.which(ejecutable):
            return t.cmd, "nativo"
    if t.fallback:
        ruta, modo = t.fallback
        return ruta, modo
    return None, "sin_fallback"


# ── Medición de tamaño ─────────────────────────────────────────────────────────
def tamano(ruta: Path | str) -> tuple[int, int, int]:
    """(bytes aparentes, bytes de disco, nº de entradas). sin seguir symlinks.

    bytes de disco usa st_blocks (lo que el sistema de archivos ocupa de verdad):
    es la cifra que refleja el espacio recuperado, no la lógica.
    """
    r = Path(ruta)
    aparente = disco = entradas = 0
    if r.is_symlink():
        return 0, 0, 0
    if r.is_file():
        try:
            st = r.stat()
        except OSError:
            return 0, 0, 0
        return st.st_size, st.st_blocks * 512, 1
    stack = [r]
    while stack:
        actual = stack.pop()
        try:
            with os.scandir(actual) as it:
                for entrada in it:
                    entradas += 1
                    try:
                        if entrada.is_symlink():
                            continue
                        st = entrada.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    aparente += st.st_size
                    disco += st.st_blocks * 512
                    if entrada.is_dir(follow_symlinks=False):
                        stack.append(Path(entrada.path))
        except (OSError, PermissionError):
            continue
    return aparente, disco, entradas


def bytes_exclusivos(ruta: Path | str) -> tuple[int, int]:
    """(bytes de bloques EXCLUSIVOS, nº de entradas). Sin seguir symlinks.

    `tamano()` cuenta `st_blocks * 512`, que es el espacio asignado, pero suma
    los bloques de un fichero hardlinkeado tantas veces como enlaces tenga. Eso
    esta bien para "cuanto ocupa esto" y esta mal para "cuanto se recupera al
    borrarlo": si el mismo inodo esta enlazado desde otro sitio, borrar una de
    las dos rutas no devuelve sus bloques, solo baja el contador de enlaces.

    Aqui solo se cuentan los bloques con `st_nlink == 1`, que son los que de
    verdad se devuelven. Es la diferencia que hacia que el catalogo declarara
    9,68 GB de `conda-pkgs` donde habia ~2,2 GB reales: conda hardlinkea cada
    entorno contra la cache, asi que el 85,6 % de los ficheros de `pkgs` eran
    bloques de algun entorno y no se podian liberar.

    Excepcion deliberada: los DIRECTORIOS se cuentan siempre. POSIX prohibe
    hardlinkear directorios, asi que sus bloques son suyos aunque `st_nlink`
    valga 2 o mas (ese numero cuenta los subdirectorios, no enlaces externos).
    Sin esta excepcion se perderian los bloques de directorio, que en un arbol
    con 200k entradas no son despreciables.
    """
    r = Path(ruta)
    if r.is_symlink():
        return 0, 0
    if r.is_file():
        try:
            st = r.stat()
        except OSError:
            return 0, 0
        return (st.st_blocks * 512, 1) if st.st_nlink == 1 else (0, 1)
    total = entradas = 0
    stack = [r]
    while stack:
        actual = stack.pop()
        try:
            with os.scandir(actual) as it:
                for entrada in it:
                    try:
                        if entrada.is_symlink():
                            continue
                        es_dir = entrada.is_dir(follow_symlinks=False)
                        st = entrada.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    entradas += 1
                    if es_dir or st.st_nlink == 1:
                        total += st.st_blocks * 512
                    if es_dir:
                        stack.append(Path(entrada.path))
        except (OSError, PermissionError):
            continue
    return total, entradas


def du_bytes_lote(rutas: list[Path], trocear: int = 400) -> int:
    """Suma de bytes asignados de varias rutas con un único proceso du (por lotes)."""
    if not rutas:
        return 0
    if not shutil.which("du"):
        return sum(tamano(p)[1] for p in rutas)
    total = 0
    for i in range(0, len(rutas), trocear):
        lote = [str(p) for p in rutas[i:i + trocear] if p.exists()]
        if not lote:
            continue
        proc = subprocess.run(["du", "-s", "-B1", *lote],
                              capture_output=True, text=True, check=False)
        for linea in proc.stdout.splitlines():
            try:
                total += int(linea.split("\t", 1)[0])
            except ValueError:
                continue
    return total


def hay_entradas_recientes(ruta: Path | str, dias: float) -> bool:
    """True si hay ALGO bajo `ruta` modificado en los últimos `dias` días.

    Es la guarda que impide borrar descargas o compilaciones en curso. Se resuelve
    con `find -newermt @<epoch> -quit`, que abandona en la primera coincidencia: en
    el caso normal (algo reciente) es instantáneo, y en el peor caso es un recorrido
    en C, no un `stat()` por inodo en Python. El corte se pasa como época absoluta
    para no depender del locale ni de la fecha del sistema.
    """
    r = _ruta_abs(ruta)
    if not r.exists():
        return False
    corte = int(time.time() - dias * 86400)
    if shutil.which("find"):
        proc = subprocess.run(
            ["find", str(r), "-xdev", "-newermt", f"@{corte}", "-print", "-quit"],
            capture_output=True, text=True, check=False,
        )
        # Se lee stdout aunque returncode != 0: `find` sale con 1 si hay un
        # directorio sin permiso, pero ya imprimió todo lo que sí pudo leer.
        if proc.stdout.strip():
            return True
        if proc.returncode == 0:
            return False
    return edad_dias(r) < dias


def hay_entradas_recientes_de_target(t: Target, dias: float) -> bool:
    """La guarda de antigüedad del TARGET, no la del directorio que lo contiene.

    `contenedor_de()` responde a otra pregunta: qué directorio no se borra en
    contenido/glob/rotar. Para un target con comodín devuelve el padre, y
    "¿hay algo reciente en el padre?" no es "¿hay algo reciente entre lo que este
    target puede borrar?". Para un patrón estrecho las dos preguntas no se
    parecen en nada.

    El caso medido: `tmp-clones` (`.tmp/repo_clone_*`, min 7d) salía
    `conservado_reciente` con 120 MB de clones de 20 días. No porque los clones
    tuvieran algo reciente, sino porque `.tmp/` — el padre — tiene 211 ficheros de
    menos de 7 días, incluidos los informes que genera la propia auditoría. La
    guarda daba True siempre que hubiera actividad en el repo, que es siempre.
    Un guard que no se puede abrir es indistinguible de un guard que no existe.

    Solo cambia `modo="glob"`, donde el patrón es un subconjunto de los hijos. En
    `contenido`/`rotar` el patrón es `*` y la unidad borrable son todos los hijos,
    así que preguntar por todos ellos ya es la pregunta correcta. En
    `directorio`/`nativo` la unidad es el contenedor entero y sus hijos cuentan.

    La guarda no se relaja: pasa a perguntar por las entradas que casan, que es
    justo la lista que `disco_purgar._plan_entradas()` borra. Un clon recién
    clonado sigue protegido por su propia edad.
    """
    if t.modo in ("directorio", "nativo"):
        return hay_entradas_recientes(contenedor_de(t), dias)
    return any(
        hay_entradas_recientes(entrada, dias)
        for entrada in du_pies_carpeta(contenedor_de(t), t.patron)
    )


def edad_util_de_target(t: Target) -> float:
    """Antigüedad de la entrada MÁS JOVEN que el target puede llegar a borrar.

    Importa la más joven, no la del contenedor: es la que decide si la guarda se
    abre. Con `base` se reportaba la edad de `.tmp/` para `tmp-clones` (casi 0
    días) cuando las entradas reales tenían 20 — un número que no correspondía a
    nada de lo que el target describe. -1 si no hay entradas.
    """
    base = contenedor_de(t)
    if t.modo in ("directorio", "nativo"):
        return edad_entrada_dias(base)
    edades = [e for e in (edad_entrada_dias(x) for x in du_pies_carpeta(base, t.patron)) if e >= 0]
    return min(edades) if edades else -1.0


def edad_entrada_dias(ruta: Path | str) -> float:
    """Antigüedad en días de la entrada en sí (un stat). -1 si no existe.

    Es la cifra barata para el informe. NO sustituye a `hay_entradas_recientes()`
    como guarda de borrado: un directorio puede ser viejo y contener hijos frescos.
    """
    r = Path(ruta)
    try:
        return max(0.0, (time.time() - r.stat().st_mtime) / 86400)
    except OSError:
        return -1.0


def edad_dias(ruta: Path | str) -> float:
    """Antigüedad en días de la entrada más reciente bajo la ruta (0 si no existe)."""
    r = Path(ruta)
    if not r.exists():
        return -1.0
    mas_reciente = r.stat().st_mtime
    if r.is_file():
        return max(0.0, (_ahora() - mas_reciente) / 86400)
    pila = [r]
    while pila:
        actual = pila.pop()
        try:
            with os.scandir(actual) as it:
                for entrada in it:
                    try:
                        if entrada.is_symlink():
                            continue
                        st = entrada.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    mas_reciente = max(mas_reciente, st.st_mtime)
                    if entrada.is_dir(follow_symlinks=False):
                        pila.append(Path(entrada.path))
        except (OSError, PermissionError):
            continue
    return max(0.0, (_ahora() - mas_reciente) / 86400)


# ── Medición nativa (du/find) ──────────────────────────────────────────────────
# $HOME de este equipo supera el millón de inodos: recorrerlo con os.scandir + un
# stat() por entrada tarda minutos. Se delega en `du` (C) y, en su ausencia, se cae
# al recorrido en Python. `du -s -B1` reporta bloques asignados: el espacio que de
# verdad ocupa la entrada, que es lo que se recupera al borrarla.

def _du_bytes(ruta: str) -> int:
    proc = subprocess.run(
        ["du", "-s", "-B1", ruta],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(proc.stderr.strip() or f"du falló sobre {ruta}")
    return int(proc.stdout.split()[0])


def _ruta_abs(p: Path | str) -> Path:
    """Ruta absoluta con `~` expandido. Todos los helpers de medición la usan para
    que pasar '~/x' o 'x' dé el mismo resultado (mismo destino, misma decisión)."""
    return Path(os.path.abspath(os.path.expanduser(str(p))))


def du_bytes(ruta: Path | str) -> int:
    """Bytes REALES asignados en disco (st_blocks) bajo `ruta`. 0 si no existe."""
    r = _ruta_abs(ruta)
    if not r.exists() or r.is_symlink():
        return 0
    if shutil.which("du"):
        try:
            return _du_bytes(str(r))
        except (RuntimeError, ValueError, OSError):
            pass
    return tamano(r)[1]


def du_pies_carpeta(base: Path, patron: str) -> list[Path]:
    """Entradas de `base` que casan con `patron`, con `find` nativo si existe.

    Se usa para los targets con comodín (`__pycache__`, `repo_clone_*`), donde un
    glob recursivo de Python sería lentísimo sobre un árbol de million de inodos.
    """
    b = _ruta_abs(base)
    if not b.exists():
        return []
    if shutil.which("find"):
        proc = subprocess.run(
            ["find", str(b), "-xdev", "-name", patron],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode == 0:
            return [Path(line) for line in proc.stdout.splitlines() if line.strip()]
    try:
        return [p for p in b.rglob(patron) if p.is_dir()]
    except OSError:
        return []


def du_mayores(base: Path, limite: int) -> list[tuple[int, Path]]:
    """(bytes, ruta) de los `limite` archivos más pesados bajo `base`.

    Una sola pasada de `find` con `%b` (bloques de 512 B asignados): no hace falta
    un `du` por archivo, que multiplicaría el coste por el número de resultados.
    """
    b = _ruta_abs(base)
    if not b.exists() or limite <= 0:
        return []
    filas: list[tuple[int, str]] = []
    if shutil.which("find"):
        proc = subprocess.run(
            ["find", str(b), "-xdev", "-type", "f", "-printf", "%b\t%p\n"],
            capture_output=True, text=True, check=False,
        )
        # Se lee stdout aunque returncode != 0: `find` sale con 1 si encuentra un
        # directorio sin permiso, pero ya imprimió todo lo que sí pudo leer.
        # Descartarlo por el código de retorno vaciaría el informe entero.
        if proc.stdout.strip():
            for linea in proc.stdout.splitlines():
                bloques, _, ruta = linea.partition("\t")
                try:
                    filas.append((int(bloques) * 512, ruta))
                except ValueError:
                    continue
    else:
        pila = [b]
        while pila:
            actual = pila.pop()
            try:
                with os.scandir(actual) as it:
                    for entrada in it:
                        if entrada.is_symlink():
                            continue
                        if entrada.is_dir(follow_symlinks=False):
                            pila.append(Path(entrada.path))
                        else:
                            filas.append((entrada.stat(follow_symlinks=False).st_blocks * 512,
                                          entrada.path))
            except (OSError, PermissionError):
                continue
    filas.sort(key=lambda f: f[0], reverse=True)
    return [(b, Path(r)) for b, r in filas[:limite]]


def du_hijos(base: Path) -> list[tuple[Path, int]]:
    """(hijo, bytes) de cada subdirectorio de `base`, con una sola pasada de du."""
    b = _ruta_abs(base)
    if not b.exists():
        return []
    if shutil.which("du"):
        proc = subprocess.run(
            ["du", "-s", "-B1", "--max-depth=1", str(b)],
            capture_output=True, text=True, check=False,
        )
        # Ídem: un subárbol ilegible no invalida el resto del listado.
        if proc.stdout.strip():
            salida = []
            for linea in proc.stdout.splitlines():
                try:
                    bytes_txt, ruta = linea.split("\t", 1)
                    p = Path(ruta.strip())
                except ValueError:
                    continue
                if p != b and p.is_dir():
                    salida.append((p, int(bytes_txt)))
            return sorted(salida, key=lambda f: f[1], reverse=True)
    return sorted(
        ((hijo, tamano(hijo)[1]) for hijo in b.iterdir() if hijo.is_dir() and not hijo.is_symlink()),
        key=lambda f: f[1], reverse=True,
    )


def _ahora() -> float:
    return time.time()


def pistas_sudo() -> list[dict]:
    """Rutas que requieren privilegios. El script NO las purga: solo informa."""
    return [
        {
            "ruta": "/var/log",
            "motivo": "Logs del sistema y journal (requiere root).",
            "comando": "sudo journalctl --vacuum-size=200M",
        },
        {
            "ruta": "/var/cache/apt",
            "motivo": "Cache de .deb descargados (requiere root).",
            "comando": "sudo apt clean",
        },
    ]


def resumen_catalogo() -> dict:
    conteo: dict[str, int] = {t: 0 for t in TIERS}
    for t in CATALOGO:
        conteo[t.tier] += 1
    return {
        "total_targets": len(CATALOGO),
        "por_tier": conteo,
        "tiers_disponibles": list(TIERS),
        "modos_disponibles": list(MODOS),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(resumen_catalogo(), ensure_ascii=False, indent=2))
