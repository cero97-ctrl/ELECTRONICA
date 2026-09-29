#!/usr/bin/env python3
"""
run_state.py — Nombre y ciclo de vida de la VISTA de estado de un flujo
(Layer 3: Execution).

Que es una vista y por que lleva el run_id en el nombre. El log append-only
(`.tmp/session_log_<run_id>.jsonl`) es la fuente de verdad y no se toca nunca. La
vista (`.tmp/run_state*.json`) es un ANDAMIO: sirve para que, si el proceso muere
a medias, se vea hasta donde llego, y para que un servidor MCP pueda devolver el
resultado de la corrida que acaba de lanzar.

Con un nombre fijo (`run_state.json`) el andamio tiene un problema que no
depende de quien lo use: **dos flujos que corren a la vez se escriben el mismo
fichero**, y el emparejamiento vista<->log que verifica `estado_sesion.py`
deja de tener sentido, porque la vista de la corrida B se atribuye al log de
la corrida A. Ese es el bug que se cocio a mano en `flujo_auditar_sistema.py` y
`flujo_auditar_repo.py` y que quedaba pendiente para los demas: **16 flujos
mas seguian escribiendo el mismo nombre**. La regla es una sola, y este modulo
es su unica definicion:

    la vista se nombra DESPUES del run_id, igual que su log.

Nada aqui decide nada sobre el flujo. Solo decide donde va el fichero y como
se lee sin confundirse con el de otra corrida.

Por que la escritura es atomica. `write_text()` directo deja un JSON a medias si
el proceso muere entre escribir y cerrar, y `estado_sesion.py` tiene una comprobacion
especifica para eso ("run_state no es JSON valido (escritura incompleta)"): es un
estado que el codigo ya sabia ver llegar, en vez de una condicion que se IMPUSO.
Escribir en un hermano temporal y `os.replace` lo hace imposible, porque en el
sistema de ficheros el rename es atomico: se ve el viejo entero o el nuevo
entero, nunca un mitad.

Por que `cambios_desde()` y no comparar un mtime. Los servidores MCP lanzan el
flujo como subproceso y despues quieren el estado de ESA corrida. Antes se
comparaba el mtime de un unico fichero; con una vista por corrida eso ya no
basta, porque "el fichero" son N. `instantiate()` saca una foto de las vistas
existentes (nombre -> mtime) y `cambios_desde()` devuelve las que son nuevas o
las que cambiaron, ordenadas de mas reciente a mas antigua. Es el mismo
criterio de antes —"solo el estado que escribio ESTA corrida"— sin depender de
que haya un solo nombre.

Uso:

    from run_state import ruta_vista, escribir_vista, cambios_desde

    ruta = ruta_vista(state["run_id"])
    escribir_vista(ruta, state)
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = SCRIPT_DIR / ".tmp"

#: La plantilla del nombre. Una sola, compartida: si el nombre viviera tambien
#: en `estado_sesion.py` y en cada flujo, el dia que cambiara uno solo, el
#: emparejamiento vista<->log se romperia en silencio (que es la forma mas cara
#: de equivocarse en un modulo cuya unica razon de ser es la consistencia).
PLANTILLA = "run_state_{run_id}.json"

#: Nombre fijo heredado. Se conserva LEYENDOLO, no escribiendolo: un flujo viejo
#: que aun use `run_state.json` tiene que seguir siendo encontrable por
#: `cambios_desde()`, y `estado_sesion.py` lo sigue juzgando. Es la costura que
#: permite migrar un flujo cada vez sin romper el resto.
VISTA_GLOBAL = "run_state.json"

#: Prefijo que distingue una vista de otro fichero de `.tmp/`. Es el mismo que
#: usa `estado_sesion._candidatos()`; un nombre mal formado (un `.log`, un
#: `.json.tmp` de una escritura a medias) no debe pasar por vista.
PREFIJO = "run_state_"

#: El nombre del log y el de la vista tienen que llevar el MISMO run_id, y el
#: run_id tiene que ser acotado: sin esto, un `run_id` con `/` o `..` escribiria
#: fuera de `.tmp/`. El mismo patron que valida `sesion_log.RUN_ID_RE`, importado
#: y no reescrito: dos validaciones de nombres de corrida que divergen en
#: silencio son la forma mas discreta de perder un log.
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from sesion_log import RUN_ID_RE  # noqa: E402
except Exception:  # pragma: no cover — solo si el modulo no esta importable
    RUN_ID_RE = None  # type: ignore[assignment]

#: Los caracteres que `slug_run_id` deja pasar. ASCII explicito (no
#: `str.isalnum()`, que acepta `ñ` y `ó` en Python mientras que `RUN_ID_RE` no:
#: el slug pasaba el filtro y el log seguia sin escribirse).
_ASCII_SEGUROS = frozenset(
    "abcdefghijklmnopqrstuvwxyz" "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "0123456789" "._-"
)


def run_id_valido(run_id: str) -> bool:
    """El run_id tiene que servir para un nombre de fichero y nada mas."""
    if not run_id or not isinstance(run_id, str):
        return False
    if RUN_ID_RE is not None:
        return bool(RUN_ID_RE.match(run_id))
    # Solo si el import fallo: el patron minimo, no un segundo criterio. Se
    # prefiere un `no` conservador (no se escribe una vista de nombre dudoso) a
    # un `si` que puede leer fuera de `.tmp/`.
    return all(c.isalnum() or c in "._-" for c in run_id)


#: Variable de entorno con la que un ORQUESTADOR (un servidor MCP, o un
#: operador) fija el `run_id` de la corrida que va a lanzar. Sin ella, cada flujo
#: se fabrica su propio `run_id` y el orquestador no tiene forma de saber con
#: que nombre acabara la vista: solo puede suponerlo, y "suponer" es
#: exactamente el fallo que el guard de mtime hacia antes.
ENV_RUN_ID = "ELECTRONICA_RUN_ID"


def run_id_de_la_corrida(prefijo: str) -> str:
    """El `run_id` de esta corrida: el que fije el orquestador, o uno nuevo.

    Se respeta `ELECTRONICA_RUN_ID` **solo si es valido**. Un valor invalido se
    ignora a proposito, en vez de propagarse: si el orquestador manda basura, el
    flujo se salva con un `run_id` propio y su traza sigue siendo correcta. La
    alternativa —abortar el flujo— dejaria sin resultado una operacion que si
    podia tener exito, que es el peor sitio donde poner un filtro de entrada.

    El `prefijo` solo se usa cuando NO hay orquestador, y se normaliza con
    `slug_run_id` por la misma razon que el resto: el `run_id` va a ser nombre
    de dos ficheros.
    """
    propuesto = os.environ.get(ENV_RUN_ID, "").strip()
    if propuesto and run_id_valido(propuesto):
        return propuesto
    marca = time.strftime("%Y%m%d-%H%M%S")
    return f"{slug_run_id(prefijo)}-{marca}"


def slug_run_id(parte: str, max_len: int = 80) -> str:
    """Parte de un run_id que viene de fuera (un nombre de fichero, un tema).

    El run_id acaba en el NOMBRE de dos ficheros: el log y la vista. Asi que un
    `run_id` con un espacio no es solo "un nombre feo": `sesion_log.py` rechaza
    escribir el log (`RUN_ID_RE`) y la vista no se escribe. `flujo_evaluar_examen`
    lo construia con `pdf_path.stem`, y un examen llamado `EJM 4-1.pdf` se
    quedaba SIN TRAZABILIDAD en silencio, mucho antes de que existiera la
    vista. El fallo era invisible porque el que se perdia era el log, no la
    vista.

    Aqui se sustituye por `-` y se colapsan las repeticiones. Determinista a
    proposito: el mismo PDF da siempre el mismo slug, y por tanto el mismo
    `run_id` y el mismo log. Si se colapsara a vacio, se avisa con un marcador
    estable en vez de dejar un nombre sin ningun que_lo_distinga.

    ASCII ESTRICTO a proposito. `str.isalnum()` devuelve True para `ñ`, `ó` y
    `ñandú` en Python, pero `RUN_ID_RE` es `[A-Za-z0-9._-]`: un acento pasaria
    el filtro y el log seguiria sin escribirse. Se usa un conjunto explicito, y
    el test comprueba el invariante entero —`slug_run_id` SIEMPRE devuelve algo
    que `run_id_valido` acepta— en vez de fiarse de que los dos filtros
    coincidan.

    `max_len` existe por la misma razon, y su valor esta justificado con
    aritmetica, no a ojo. `RUN_ID_RE` corta a 120. El run_id real se compone
    como `flujo-<slug>-<YYYYMMDD-HHMMSS>`:

        6 ("flujo-") + 80 (slug) + 1 ("-") + 15 (timestamp) = 102 <= 120

    Sobran 18 caracteres de margen. Un nombre mas largo se trunca al final
    (no al principio: el final es donde esta la parte que mas distingue entre
    dos ficheros parecidos, p. ej. `Tema7-Parte2` vs `Tema7-Parte3`). Dos
    nombres que solo difieren mas alla del corte pueden acabar en el mismo
    slug; el timestamp del final del run_id los separa igual, que es lo que
    evita de verdad que dos logs se pisen.
    """
    limpio = "".join(
        c if (c in _ASCII_SEGUROS) else "-"
        for c in str(parte)
    )
    limpio = re.sub(r"-{2,}", "-", limpio).strip("-")
    if not limpio:
        return "sin-nombre"
    if len(limpio) > max_len:
        limpio = limpio[-max_len:].lstrip("-")
    return limpio or "sin-nombre"


def ruta_vista(run_id: str, tmp_dir: Path | None = None) -> Path | None:
    """Ruta de la vista de un run, o None si el run_id no sirve como nombre.

    None y no una exception: escribir una vista es una cortesia de diagnostico.
    Un run_id raro no puede tumbar un flujo que por lo demas va bien, y tampoco
    desviar la escritura a un sitio raro; lo que hace es no escribir.
    """
    base = Path(tmp_dir) if tmp_dir is not None else TMP_DIR
    if not run_id_valido(run_id):
        return None
    return base / PLANTILLA.format(run_id=run_id)


def escribir_vista(ruta: Path, estado: dict) -> bool:
    """Escribe la vista de forma atomica. Devuelve si lo conseguiu.

    El temporal va como hermano CON el mismo nombre mas `.tmp`, asi que un glob
    de `run_state_*.json` (el de `estado_sesion.py`) no lo confundira con una
    vista: no acaba en `.json`.
    """
    if ruta is None:
        return False
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        tmp = ruta.with_name(ruta.name + ".tmp")
        cuerpo = json.dumps(estado, ensure_ascii=False, indent=2) + "\n"
        with tmp.open("w", encoding="utf-8") as f:
            f.write(cuerpo)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, ruta)  # atomico: viejo entero o nuevo entero
        return True
    except (OSError, TypeError, ValueError):
        # Un andamio que no se puede escribir no puede tumbar un flujo. Si el
        # temporal llego a crearse, se retira para no dejar un `.tmp` que otro
        # recorrido confundiria con una vista.
        try:
            if ruta is not None:
                ruta.with_name(ruta.name + ".tmp").unlink(missing_ok=True)
        except OSError:
            pass
        return False


def retirar_vista(ruta: Path) -> bool:
    """Quita la vista. El log append-only no se toca: es la verdad permanente.

    Nunca propaga: una vista que no se puede quitar (permisos, montura) no puede
    tumbar el informe de un flujo que ya termino bien. Es lo que hacen
    `flujo_auditar_sistema.py` y `flujo_auditar_repo.py` al cerrar.
    """
    if ruta is None:
        return False
    try:
        ruta.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def listar_vistas(tmp_dir: Path | None = None) -> list[Path]:
    """Las vistas de verdad, en orden de mtime: mas reciente primero.

    Filtra por el prefijo y por el sufijo `.json`, para no meter en la lista ni
    un `.tmp` de una escritura a medias ni un fichero que se llame `run_state_`
    sin ser una vista. La vista global entra tambien: se lee, no se escribe ya,
    pero mientras quede alguna tiene que seguir encontrandose.
    """
    base = Path(tmp_dir) if tmp_dir is not None else TMP_DIR
    if not base.is_dir():
        return []
    rutas = [base / VISTA_GLOBAL] + [
        p for p in base.glob(PREFIJO + "*.json")
        if p.is_file()
    ]
    vistos: list[Path] = []
    for p in rutas:
        if p.is_file() and p not in vistos:
            vistos.append(p)
    try:
        vistos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        # Un fichero que desaparece entre el glob y el stat (otro flujo
        # retirando su propia vista) no es un fallo: se salta y se sigue.
        vistos = [p for p in vistos if p.exists()]
    return vistos


def instantiate(tmp_dir: Path | None = None) -> dict[str, float]:
    """Foto de las vistas que hay AHORA, como {nombre: mtime}.

    La toma un servidor MCP justo antes de lanzar el flujo, para poder afirmar
    despues "estas vistas las escribio ESTA corrida" sin suponer nada del
    reloj. La foto se puede leer mal: si una vista aparece sin mtime no se anota
    y punto, porque es la foto de una carrera.
    """
    foto: dict[str, float] = {}
    for p in listar_vistas(tmp_dir):
        try:
            foto[p.name] = p.stat().st_mtime
        except OSError:
            continue
    return foto


def cambios_desde(foto: dict[str, float], tmp_dir: Path | None = None) -> list[Path]:
    """Las vistas nuevas o reescritas despues de `foto`, mas reciente primero.

    Es el guard de "el estado de esta corrida" que usaban los MCP comparando el
    mtime de un solo fichero. Con una vista por corrida, "el fichero" son N, y
    el guard se generaliza: lo que no estaba en la foto, o estaba con otro
    mtime, lo escribio esta corrida. Devuelve tambien la vista global si cambio,
    para que un flujo aun sin migrar siga siendo legible.
    """
    cambiadas: list[Path] = []
    for p in listar_vistas(tmp_dir):
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        antes = foto.get(p.name)
        if antes is None or mtime > antes:
            cambiadas.append(p)
    return cambiadas


def leer_vista(ruta: Path) -> dict:
    """Lee una vista. Un JSON invalido o ilegible devuelve {}: no inventa.

    Devolver {} y no lanzar es lo que deja al servidor MCP decir "no hay estado"
    en vez de morir: el flujo ya corrio, y perder su resumen por un fichero a
    medias seria el peor resultado posible.
    """
    if ruta is None:
        return {}
    try:
        with ruta.open("r", encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def nueva_run_id(prefijo: str) -> str:
    """Un run_id con marca de tiempo, para flujos que aun no trazarron.

    Utiles hasta que el flujo migre a `ruta_vista` con un run_id propio. Un
    run_id con la misma marca que otro flujo no se solapa porque el prefijo es
    el del flujo.
    """
    return f"{prefijo}-{time.strftime('%Y%m%d-%H%M%S')}"


if __name__ == "__main__":  # diagnostico:python3 execution/run_state.py
    import glob as _glob
    print(f"PLANTILLA  : {PLANTILLA}")
    print(f"VISTA GLOBAL: {VISTA_GLOBAL}")
    print(f"run_id valido ('x-1'): {run_id_valido('x-1')}")
    print(f"run_id valido ('../x'): {run_id_valido('../x')}")
    print(f"ruta('x-1')  : {ruta_vista('x-1')}")
    print("vistas vivas :")
    for _p in listar_vistas():
        print(f"  {_p.name}  {_p.stat().st_size} B")
