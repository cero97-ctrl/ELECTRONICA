#!/usr/bin/env python3
"""
test_barrera_disco.py — Regresión de la barrera de whitelist de disco
(Layer 3: Execution, test de seguridad; NO toca datos reales salvo fixtures propios).

Comprueba tres cosas, que son las que pueden producir pérdida de trabajo:

  1. POSITIVOS — todo target del catálogo que exista tiene su unidad borrable
     (contenedor o primer hijo) permitida por `validar_destino`.
  2. NEGATIVOS — una lista curada de rutas peligrosas se rechaza, y cada una con el
     motivo ESPERADO (no basta con que rechace: importa por qué rechaza).
  3. BARRERAS — symlinks, rutasinexistentes, fuera-de-catálogo y la propia raíz del
     repo se rechazan siempre, incluidas las trampas que se pueden plantar a mano.

No borra nada: los únicos ficheros que crea son symlinks/directorios efímeros que
borra al terminar, y solo dentro de rutas del catálogo o de /tmp.

Uso:  python3 execution/test_barrera_disco.py
Salida: 0 = todas las aserciones pasan; 1 = hay regresión.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalogo_disco as C  # noqa: E402

fallos: list[str] = []
ok = 0


def comprobar(condicion: bool, mensaje: str) -> None:
    global ok
    if condicion:
        ok += 1
    else:
        fallos.append(mensaje)


# ── 1. Positivos: lo declarado en el catálogo debe ser alcanzable ───────────────
def test_positivos() -> None:
    for t in C.CATALOGO:
        base = t.ruta_resuelta()
        if not base.exists():
            continue
        # Modos de destino: el propio directorio del target es lo que se purga, asi que
        # se valida el. Los nativos también: la herramienta oficial (conda clean) purga
        # el directorio del target, no sus hijos, y es justo esa ruta la que valida
        # disco_purgar antes de ejecutarse. Validar el primer hijo en nativo daria
        # "fuera_de_catalogo" sin motivo real, porque los hijos no se borran uno a uno.
        if t.modo in ("directorio", "nativo"):
            permitido, motivo = C.validar_destino(base)
            comprobar(permitido, f"[positivos] {t.id}: el target debe ser válido, dio {motivo}")
            continue
        # Modos de entradas: el contenedor es de entrada; se valida la primera unidad.
        if t.modo == "glob":
            candidatas = C.du_pies_carpeta(base, t.patron)
        else:
            try:
                candidatas = [Path(e.path) for e in os.scandir(base)]
            except OSError:
                continue
        if not candidatas:
            continue
        permitido, motivo = C.validar_destino(candidatas[0])
        comprobar(permitido, f"[positivos] {t.id}: primera entrada no borrable ({motivo})")


# ── 2. Negativos: lo peligroso se rechaza, y por el motivo correcto ───────────
PELIGROSOS: tuple[tuple[str, str], ...] = (
    # (ruta, prefijo de motivo esperado)
    ("/", "raiz_no_permitida"),
    ("/home", "raiz_no_permitida"),
    ("/usr", "raiz_no_permitida"),
    ("/etc", "raiz_no_permitida"),
    ("~", "raiz_no_permitida"),
    ("~/.ssh", "^protegido_exacto"),
    ("~/.ssh/id_ed25519", "^protegido_ancestro|^protegido_exacto"),
    ("~/.config/opencode", "^protegido_exacto"),
    ("~/.config/opencode/opencode.db", "^protegido_exacto|^no_existe"),
    ("~/.config/opencode/opencode.db-wal", "^protegido_exacto|^no_existe"),
    ("~/.config/opencode/opencode.log", "^protegido_exacto|^no_existe"),
    ("~/.local/share/opencode/opencode.db", "^protegido_exacto"),
    ("~/.npm-global", "^protegido_exacto"),
    # El binario de platformio-mcp es un symlink: la barrera lo rechaza por es_symlink
    # aunque el padre este protegido, porque resolver el enlace exponeria el destino real.
    ("~/.npm-global/bin/platformio-mcp", "^es_symlink"),
    ("~/.platformio", "^protegido_exacto"),
    ("~/.cargo", "^fuera_de_catalogo|^protegido_exacto"),
    ("~/.local/share/solana", "^protegido_exacto"),
    ("~/.gitconfig", "fuera_de_catalogo|protegido_ancestro|no_existe"),
    ("~/.bashrc", "fuera_de_catalogo|protegido_ancestro|no_existe"),
    (".env", "protegido_exacto|protegido_ancestro|fuera_de_catalogo|no_existe"),
    (".env.local", "protegido_ancestro|fuera_de_catalogo|no_existe"),
    (".git", "protegido_ancestro|protegido_exacto|fuera_de_catalogo|no_existe"),
    (".git/config", "protegido_ancestro|protegido_exacto|fuera_de_catalogo|no_existe"),
    ("docs", "protegido_ancestro|protegido_exacto|fuera_de_catalogo|no_existe"),
    ("cursos", "protegido_ancestro|protegido_exacto|fuera_de_catalogo|no_existe"),
    ("Proyectos", "protegido_ancestro|protegido_exacto|fuera_de_catalogo|no_existe"),
    ("datasets", "protegido_ancestro|protegido_exacto|fuera_de_catalogo|no_existe"),
    ("directives", "protegido_ancestro|protegido_exacto|fuera_de_catalogo|no_existe"),
    ("execution", "protegido_ancestro|protegido_exacto|fuera_de_catalogo|no_existe"),
    ("db_state.json", "protegido_exacto|protegido_ancestro|fuera_de_catalogo|no_existe"),
)


def test_negativos() -> None:
    import re
    for ruta, esperado in PELIGROSOS:
        permitido, motivo = C.validar_destino(C._norm(Path(ruta)))
        comprobar(not permitido, f"[negativos] {ruta} fue ACEPTADO: razón de seguridad rota")
        comprobar(bool(re.match(esperado, motivo)),
                  f"[negativos] {ruta}: motivo inesperado '{motivo}' (esperaba ~{esperado})")


# ── 3. Barreras plantadas a mano (las trampas reales) ─────────────────────────
def test_barreras() -> None:
    # 3a. La raíz del repo nunca es destino, aunque sea el contenedor de un glob.
    comprobar(not C.validar_destino(C._norm(C.REPO_ROOT))[0],
              "[barreras] la raíz del repo no debe ser borrable")
    comprobar(not C.validar_destino(C._norm(Path("/")))[0],
              "[barreras] / no debe ser borrable")

    # 3b. Un symlink a ~/.ssh colado en una ruta del catálogo NO se sigue.
    sandbox = Path(tempfile.mkdtemp(prefix="barrera_prueba_", dir="/tmp"))
    try:
        trampa = sandbox / "enlace_a_ssh"
        trampa.symlink_to(Path.home() / ".ssh")
        permitido, motivo = C.validar_destino(trampa)
        comprobar(not permitido and motivo == "es_symlink",
                  f"[barreras] symlink a ~/.ssh: permitido={permitido} motivo={motivo}")

        # 3c. Una ruta fuera de toda raíz permitida también.
        fuera =sandbox / "sub"
        fuera.mkdir()
        permitido, motivo = C.validar_destino(fuera)
        comprobar(not permitido,
                  f"[barreras] /tmp fixture fuera de catálogo: permitido={permitido} ({motivo})")
    finally:
        for e in sorted(sandbox.rglob("*"), reverse=True):
            try:
                e.unlink() if e.is_symlink() or e.is_file() else e.rmdir()
            except OSError:
                pass
        try:
            sandbox.rmdir()
        except OSError:
            pass

    # 3d. Un symlink DENTRO de una ruta del catálogo real también se rechaza.
    contenedor = Path(C._norm("~/.local/share/Trash/files"))
    if contenedor.exists():
        trampa = contenedor / "__barrera_enlace_prueba"
        try:
            trampa.symlink_to(Path.home() / ".ssh")
            permitido, motivo = C.validar_destino(trampa)
            comprobar(not permitido and motivo == "es_symlink",
                      f"[barreras] symlink en Trash: permitido={permitido} motivo={motivo}")
        finally:
            trampa.unlink(missing_ok=True)


def test_nativo() -> None:
    """El modo nativo (pip cache purge, npm cache clean) tiene las mismas barreras.

    El catálogo actual no declara ningún target nativo, así que sin este test la
    rama quedaría sin cubrir: es donde antes se ejecutaba la guarda de antigüedad
    y donde la cadena del comando se pasaba cruda a subprocess (FileNotFoundError
    con shell=False).
    """
    import argparse

    import catalogo_disco as C2
    import disco_purgar as P

    sandbox = Path(tempfile.mkdtemp(prefix="nativo_prueba_", dir="/tmp"))
    try:
        canario = sandbox / "canario"
        cmd = f"touch {canario}"
        t = C2.Target(
            id="nativo-de-prueba", ruta=str(sandbox), tier="seguro", modo="nativo",
            descripcion="fixture de test", cmd=cmd, min_edad_dias=7,
        )
        # CATALOGO es una tupla: se re-liga el atributo del módulo (validar_destino lo
        # lee en tiempo de llamada) y se restaura al terminar.
        cat0, pcat0 = C2.CATALOGO, P.CATALOGO
        C2.CATALOGO = cat0 + (t,)
        P.CATALOGO = pcat0 + (t,)
        args = argparse.Namespace(dry_run=True, min_edad_dias=None, verbose=False)
        try:
            # 4a. Con la guarda de antigüedad (dir recien creado) no se ejecuta nada.
            r = P.purgar_target(t, args)
            comprobar(r["estado"] == "omitido" and r["motivo"] == "conservado_reciente",
                      f"[nativo] la guarda de antigüedad debe aplicar: {r['estado']}/{r['motivo']}")
            comprobar(not canario.exists(),
                      "[nativo] un target reciente no debe ejecutar su comando")

            # 4b. Sin guarda: dry-run simula y sigue sin ejecutar. Si el comando no se
            #    partiese con shlex, esto reventaria con FileNotFoundError.
            args.min_edad_dias = 0
            r = P.purgar_target(t, args)
            comprobar(r["estado"] == "simulado" and r["motivo"] == "nativo",
                      f"[nativo] dry-run debe simular: {r['estado']}/{r['motivo']}")
            comprobar(not canario.exists(),
                      "[nativo] dry-run no debe ejecutar el comando")
            comprobar(r.get("liberable", 0) > 0,
                      "[nativo] dry-run debe estimar lo liberable")

            # 4c. Con la ejecucion habilitada el comando se parte bien y corre.
            args.dry_run = False
            r = P.purgar_target(t, args)
            comprobar(r["estado"] == "ok" and canario.exists(),
                      f"[nativo] la ejecucion real debe funcionar: {r['estado']} {r.get('detalle','')}")
        finally:
            C2.CATALOGO, P.CATALOGO = cat0, pcat0
    finally:
        for e in sorted(sandbox.rglob("*"), reverse=True):
            try:
                e.unlink() if e.is_symlink() or e.is_file() else e.rmdir()
            except OSError:
                pass
        try:
            sandbox.rmdir()
        except OSError:
            pass


def test_guarda_antigueda_por_target() -> None:
    """La guarda pregunta por el TARGET, no por el directorio que lo contiene.

    Regresion de un fallo medido en `tmp-clones` (`.tmp/repo_clone_*`, min 7d):
    120 MB de clones de 20 dias salian `conservado_reciente` porque `.tmp/` — el
    padre — tenia 211 ficheros de menos de 7 dias. Un guard que da True siempre
    que haya actividad en el repo no protege nada; solo impide ver el espacio.
    """
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "contenedor"
        base.mkdir()
        # Un clon VIEJO, como los reales: no se toca.
        viejo = base / "repo_clone_viejo"
        (viejo / ".git").mkdir(parents=True)
        _envejecer(viejo)
        # Ruido ajeno al target, fresco: es lo que hacia disparar la guarda.
        for n in ("informe.json", "descriptor.json", "log.txt"):
            (base / n).write_text("x")

        t = C.Target(id="x-glob", ruta=str(base / "repo_clone_*"), tier="seguro",
                     modo="glob", patron="repo_clone_*", descripcion="test",
                     min_edad_dias=7)
        # Solo el clon viejo: el ruido fresco del padre NO debe conservarlo.
        comprobar(not C.hay_entradas_recientes_de_target(t, 7),
                  "[glob] un clon de 20 dias no es reciente aunque el padre tenga ruido fresco")

        # Aparece un clon RECIENTE: es el que la guarda debe seguir parando.
        nuevo = base / "repo_clone_nuevo"
        nuevo.mkdir()
        (nuevo / "trabajo.txt").write_text("x")
        comprobar(C.hay_entradas_recientes_de_target(t, 7),
                  "[glob] un clon recien clonado sigue protegido por su propia edad")
        comprobar(nuevo.exists(),
                  "[glob] el clon reciente no puede desaparecer: la guarda no se relaja")

        # `contenido` (patron `*`) NO cambia: preguntar por todos los hijos ya era
        # correcto, porque la unidad borrable son todos los hijos.
        tc = C.Target(id="x-cont", ruta=str(base), tier="seguro", modo="contenido",
                      patron="*", descripcion="test", min_edad_dias=7)
        comprobar(C.hay_entradas_recientes_de_target(tc, 7),
                  "[contenido] con patron `*` cualquier hijo fresco conserva el target")

        # La edad que se reporta es la de la entrada mas JOVEN, no la del padre.
        edad = C.edad_util_de_target(t)
        comprobar(0 <= edad < 1,
                  f"[glob] la edad reportada debe ser la del clon recien (0 d), no la del padre; vino {edad}")
        _envejecer(nuevo)
        e2 = C.edad_util_de_target(t)
        comprobar(e2 > 7, f"[glob] con todo envejecido la edad debe ser >7 d; vino {e2}")


def test_guarda_ignora_bookkeeping_vcs() -> None:
    """La guarda mide actividad de la persona, no bookkeeping de la herramienta.

    Regresion del caso medido en `tmp-clones`: los dos clones seguian saliendo
    `conservado_reciente` con 115 MB porque lo unico reciente bajo ellos era el
    directorio `.git` en si, que un `git status` refresca sin que nadie toque un
    solo fichero de trabajo (medido: no reescribe ni `.git/index`). El autor del
    toque quedo sin identificar, pero da igual: lo que se mide es si la persona
    estuvo trabajando, y ahi la respuesta era no.
    """
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "contenedor"
        base.mkdir()
        clon = base / "repo_clone_x"
        (clon / ".git" / "objects").mkdir(parents=True)
        (clon / "src").mkdir()
        (clon / "src" / "main.py").write_text("x")
        _envejecer(clon)
        _envejecer(base)

        t = C.Target(id="x-vcs", ruta=str(base / "repo_clone_*"), tier="seguro",
                     modo="glob", patron="repo_clone_*", descripcion="test",
                     min_edad_dias=7)

        # 1) Todo viejo: no reciente, y la edicion anterior no lo abria.
        comprobar(not C.hay_entradas_recientes_de_target(t, 7),
                  "[vcs] un clon de 30 dias no es reciente")

        # 2) Solo `.git` y su contenido frescos: eso es lo que hace `git status`.
        ahora = time.time()
        for x in (clon / ".git", clon / ".git" / "objects"):
            os.utime(x, (ahora, ahora))
        comprobar(not C.hay_entradas_recientes_de_target(t, 7),
                  "[vcs] un `git status` no debe conservar el clon: no hay trabajo humano")
        # El flag es lo que hace el trabajo, no una casualidad del fixture.
        comprobar(C.hay_entradas_recientes(clon, 7),
                  "[vcs] sin el flag, `.git` fresco SI es reciente (control del test)")

        # 3) Un fichero de trabajo fresco: la guarda SIGUE parando. Esto es lo que
        #    protege de verdad, y es lo que no se puede relajar.
        (clon / "src" / "nuevo.py").write_text("y")
        comprobar(C.hay_entradas_recientes_de_target(t, 7),
                  "[vcs] un clon con trabajo reciente sigue protegido")
        comprobar(clon.exists(), "[vcs] el clon con trabajo reciente no puede desaparecer")

        # 4) Criterio del informe == criterio de la guarda. `disco_medir` publica
        #    los dos en el mismo objeto; si discrepan, el informe se contradice.
        _envejecer(clon)
        edad = C.edad_util_de_target(t)
        comprobar(not C.hay_entradas_recientes_de_target(t, 7),
                  "[vcs] tras envejecer, la guarda se abre")
        comprobar(20.0 < edad < 60.0,
                  f"[vcs] la edad reportada debe ignorar `.git` como la guarda; vino {edad}")

        # 5) El respaldo en Python tiene la misma semantica que el `find`. Si
        #    divergieran, la misma pregunta daria dos respuestas segun la maquina.
        _envejecer(clon)
        ahora = time.time()
        for x in (clon / ".git", clon / ".git" / "objects"):
            os.utime(x, (ahora, ahora))
        comprobar(C.edad_dias(clon, ignorar_vcs=True) > 7,
                  "[vcs] edad_dias(ignorar_vcs=True) no debe contar `.git`")
        comprobar(C.edad_dias(clon) < 1,
                  "[vcs] edad_dias() sin el flag debe contar `.git` (control del test)")

        # 6) Aplica a todos los modos, no solo a `glob`. Aqui la unidad borrable
        #    son TODOS los hijos, `.git` incluido: si lo unico reciente de una cache
        #    es su propio bookkeeping, la cache no esta en uso y borrarla es lo
        #    correcto. Queda escrito para que sea una decision y no un accidente.
        tc = C.Target(id="x-vcs-cont", ruta=str(clon), tier="seguro", modo="contenido",
                      patron="*", descripcion="test", min_edad_dias=7)
        comprobar(not C.hay_entradas_recientes_de_target(tc, 7),
                  "[vcs] en `contenido`, un `.git` fresco tampoco es trabajo humano")


def _envejecer(p: Path, dias: int = 30) -> None:
    """Baja el mtime de `p` y de todo lo que cuelga de el."""
    viejo = time.time() - dias * 86400
    for x in [p, *p.rglob("*")]:
        try:
            os.utime(x, (viejo, viejo))
        except OSError:
            pass


def main() -> int:
    test_positivos()
    test_negativos()
    test_barreras()
    test_nativo()
    test_guarda_antigueda_por_target()
    test_guarda_ignora_bookkeeping_vcs()
    print(f"Aserciones OK: {ok}   Fallos: {len(fallos)}")
    for f in fallos:
        print(f"  FALLO: {f}")
    if fallos:
        print("BARRERA ROTA — no purgar nada hasta arreglarlo.")
        return 1
    print("BARRERA OK: whitelist, motivos y trampas verificados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
