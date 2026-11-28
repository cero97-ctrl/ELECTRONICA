#!/usr/bin/env python3
"""Capa 3 compartida: mecánica de publicación en GitHub Pages de repos generados.

Qué vive aquí y por qué: crear/actualizar el repo, commit con autor, correo y
fecha fijos, `push --force`, habilitar Pages, esperar el 200 y el interruptor de
visibilidad por API REST son independientes del contenido que se publica. Si
cada publicador (cuestionarios del curso, material de Sara) tuviera su copia,
dos copias divergirían en silencio justo en la parte que toca la red y el
historial público: la más cara de depurar. Los publicadores concretos aportan
SOLO la recolección y la validación del payload; la mecánica de git/Pages se
define una única vez aquí.

Reglas que no se tocan:
  - Commit con identidad y fecha fijas: el mismo payload produce el mismo
    commit, así la reproducibilidad no depende de quién publique.
  - `push --force`: el repo destino es generado, no un archivo con historial
    propio. Nunca usar este módulo sobre un repo con contenido ajeno.
  - Visibilidad por API REST (`gh api -X PATCH repos/<repo> -F private=...`),
    no `gh repo edit --visibility`: ese subcomando pide confirmación
    interactiva y su flag de aceptación solo existe desde gh 2.56 (esta máquina
    trae 2.45, donde muere imprimiendo la ayuda). `-F` (no `-f`) convierte
    `true`/`false` en booleanos de verdad.
  - «Privado» significa **404**, no «acceso restringido»: Pages no sirve repos
    privados sin plan de pago.

Uso (desde otro script de execution/):
    import publicar_github as G
    G.asegurar_repo("owner/repo", "Descripción")
    G.publicar_git(stage, "owner/repo", "Mensaje de commit")
    G.habilitar_pages("owner/repo")
"""

from __future__ import annotations

import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

FECHA_FIJA = "2026-01-01T00:00:00+0000"


def resultado(status: str, code: int, **extra) -> dict:
    return {"status": status, "code": code, **extra}


def entorno_git() -> dict[str, str]:
    entorno = dict(os.environ)
    # `gh` prioriza GITHUB_TOKEN/GH_TOKEN del entorno por encima de su propio
    # login (keyring). Un token caducado en .env producía `HTTP 401: Bad
    # credentials` en `gh repo view` aunque `gh auth status` estuviera sano
    # (fallo real 2026-11-28). La autenticación la decide `gh auth`: una sola
    # fuente, sin secretos duplicados que puedan divergir.
    entorno.pop("GITHUB_TOKEN", None)
    entorno.pop("GH_TOKEN", None)
    entorno.update(
        {
            "GIT_AUTHOR_NAME": "ELECTRONICA",
            "GIT_AUTHOR_EMAIL": "electronica@local",
            "GIT_COMMITTER_NAME": "ELECTRONICA",
            "GIT_COMMITTER_EMAIL": "electronica@local",
            "GIT_AUTHOR_DATE": FECHA_FIJA,
            "GIT_COMMITTER_DATE": FECHA_FIJA,
        }
    )
    return entorno


def ejecutar(cmd: list[str], cwd: Path | None = None, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=entorno_git(),
    )


def asegurar_repo(repo: str, descripcion: str) -> str | None:
    """None si el repo existe o se creó público; si no, el motivo del fallo."""
    vista = ejecutar(["gh", "repo", "view", repo, "--json", "name"])
    if vista.returncode == 0:
        return None
    creacion = ejecutar(
        [
            "gh",
            "repo",
            "create",
            repo,
            "--public",
            "--description",
            descripcion,
        ]
    )
    if creacion.returncode != 0:
        return (creacion.stderr or creacion.stdout or "gh repo create falló")[-600:]
    return None


def publicar_git(stage: Path, repo: str, mensaje: str) -> str | None:
    """Commit + push --force del stage al repo. None si salió bien."""
    pasos = [
        ["git", "init", "-b", "main"],
        ["git", "add", "-A"],
        ["git", "commit", "-m", mensaje],
        ["git", "remote", "add", "origin", f"https://github.com/{repo}.git"],
        [
            "git",
            "-c",
            "credential.helper=",
            "-c",
            "credential.helper=!gh auth git-credential",
            "push",
            "--force",
            "origin",
            "main",
        ],
    ]
    for cmd in pasos:
        proc = ejecutar(cmd, cwd=stage)
        if proc.returncode != 0:
            return f"{' '.join(cmd)}: {(proc.stderr or proc.stdout)[-500:]}"
    return None


def cmd_visibilidad(repo: str, visibilidad: str) -> list[str]:
    privado = "true" if visibilidad == "private" else "false"
    return [
        "gh",
        "api",
        "-X",
        "PATCH",
        f"repos/{repo}",
        "-F",
        f"private={privado}",
    ]


def visibilidad_actual(repo: str) -> str | None:
    proc = ejecutar(["gh", "api", f"repos/{repo}", "--jq", ".visibility"])
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()
    return None


def cambiar_visibilidad(repo: str, visibilidad: str) -> str | None:
    """None si el repo quedó en la visibilidad pedida; si no, el motivo."""
    proc = ejecutar(cmd_visibilidad(repo, visibilidad))
    if proc.returncode != 0:
        return (proc.stderr or proc.stdout or "gh api falló")[-500:]
    actual = visibilidad_actual(repo)
    if actual != visibilidad:
        return f"el repo sigue en {actual!r} después de pedir {visibilidad!r}"
    return None


def habilitar_pages(repo: str) -> str | None:
    proc = ejecutar(
        [
            "gh",
            "api",
            "-X",
            "POST",
            f"repos/{repo}/pages",
            "-f",
            "source[branch]=main",
            "-f",
            "source[path]=/",
        ]
    )
    if proc.returncode == 0:
        return None
    salida = (proc.stderr or proc.stdout).lower()
    if "already" in salida or "409" in salida:
        return None
    return (proc.stderr or proc.stdout or "no se pudo habilitar Pages")[-500:]


def esperar_pages(url: str, intentos: int = 18, espera: float = 5.0) -> bool:
    for _ in range(intentos):
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(espera)
    return False


def owner_por_defecto() -> str:
    proc = ejecutar(["gh", "api", "user", "--jq", ".login"])
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()
    return "cero97-ctrl"
