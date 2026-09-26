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
        if t.modo == "directorio":
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


def main() -> int:
    test_positivos()
    test_negativos()
    test_barreras()
    test_nativo()
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
