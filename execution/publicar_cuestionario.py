#!/usr/bin/env python3
"""Capa 3: publica en GitHub Pages solo la variante `alumno` de los cuestionarios.

El repo del curso es público y la carpeta `cursos/<CURSO>/evaluaciones/web/`
contiene también `_docente.html` (con `const CLAVE`) y `fuentes/*_respuestas.md`
(la clave). Publicar la carpeta entera, o un `git add -A` con una regla mal
puesta, filtraría las respuestas y en GitHub quedarían en el historial para
siempre. Por eso este script:

1. Recolecta **solo** `*_alumno.html`.
2. Rechaza cualquier archivo que contenga marcas de la clave o del modo docente
   (código 3) y cualquier archivo sin el módulo de datos del estudiante.
3. Arma un `index.html` propio (sin enlace al docente) y un `.nojekyll`.
4. Con `--push`, crea/actualiza el repo destino y habilita Pages.
5. Con `--visibilidad private|public`, cambia la visibilidad del repo destino.
   Es el interruptor de "ocultar hasta el día del examen": Pages **no sirve**
   repos privados sin plan de pago, así que `private` deja la URL en 404 y
   `public` la devuelve (re-habilitando Pages si hace falta). Borrar el archivo
   del repo NO lo oculta: el blob sigue alcanzable por su SHA en el historial
   público.

Uso:
    python3 execution/publicar_cuestionario.py --dry-run
    python3 execution/publicar_cuestionario.py --push --repo cero97-ctrl/cuestionarios
    python3 execution/publicar_cuestionario.py --visibilidad private
    python3 execution/publicar_cuestionario.py --visibilidad public --push
    python3 execution/publicar_cuestionario.py --web-dir cursos/OTRO/evaluaciones/web --json

Códigos de salida: 0 ok · 1 error de E/S · 3 payload rechazado (fuga) ·
4 gh/git falló · 5 ruta rechazada.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EJECUCION = RAIZ / "execution"
sys.path.insert(0, str(EJECUCION))
import md_a_html as M  # noqa: E402  (reusa `_documento` y el estilo)

WEB_POR_DEFECTO = "cursos/CYBERSEGURIDAD/evaluaciones/web"
STAGE_POR_DEFECTO = ".tmp/publicacion"
MARCAS_FUGA = ("const CLAVE", "**Answer:**", "Modo docente")
MARCA_DATOS = 'id="estudiante-nombre"'
MENSAJE_COMMIT = "Publicar cuestionarios (alumno)"
FECHA_FIJA = "2026-01-01T00:00:00+0000"
CSS_INDICE = (
    ".indice { list-style: none; padding: 0; margin: 0; }\n"
    ".indice li { display: flex; justify-content: space-between; gap: 1rem; "
    "align-items: center; background: #fff; border: 1px solid var(--linea); "
    "border-radius: 10px; padding: .8rem 1rem; margin: 0 0 .6rem; flex-wrap: wrap; }\n"
    ".indice .titulo { font-weight: 600; color: var(--azul); }\n"
    ".boton { display: inline-block; background: var(--azul); color: #fff; "
    "padding: .35rem .7rem; border-radius: 6px; text-decoration: none; "
    "font-size: .85rem; }\n"
)


def _resultado(status: str, code: int, **extra) -> dict:
    return {"status": status, "code": code, **extra}


def _validar_web_dir(ruta: Path) -> Path:
    resuelta = ruta.resolve()
    partes = resuelta.parts
    if resuelta.name != "web" or "cursos" not in partes or "evaluaciones" not in partes:
        raise PermissionError(
            "solo se publica desde cursos/<CURSO>/evaluaciones/web/, no desde "
            f"{resuelta}"
        )
    return resuelta


def _recolectar(web_dir: Path) -> list[Path]:
    return sorted(
        (p for p in web_dir.glob("*_alumno.html") if p.is_file()),
        key=lambda p: p.name,
    )


def _validar_payload(archivos: list[Path]) -> list[str]:
    problemas: list[str] = []
    if not archivos:
        problemas.append("no hay ningún `*_alumno.html` en la carpeta")
    for ruta in archivos:
        nombre = ruta.name.lower()
        if "docente" in nombre or "respuesta" in nombre:
            problemas.append(f"{ruta.name}: es material del docente, no se publica")
            continue
        try:
            texto = ruta.read_text(encoding="utf-8")
        except OSError as exc:
            problemas.append(f"{ruta.name}: no se pudo leer ({exc})")
            continue
        for marca in MARCAS_FUGA:
            if marca in texto:
                problemas.append(f"{ruta.name}: contiene «{marca}»; se rechaza")
        if MARCA_DATOS not in texto:
            problemas.append(
                f"{ruta.name}: no tiene el módulo de datos del estudiante "
                f"(`{MARCA_DATOS}`); regenerar antes de publicar"
            )
    return problemas


def _titulo_de(texto: str, respaldo: str) -> str:
    coincidencia = re.search(r"<title>(.*?)</title>", texto, re.S)
    if not coincidencia:
        return respaldo
    return html.unescape(coincidencia.group(1).strip()) or respaldo


def _indice_html(archivos: list[Path]) -> str:
    entradas = []
    for ruta in archivos:
        titulo = _titulo_de(ruta.read_text(encoding="utf-8"), ruta.stem)
        entradas.append(
            "<li>"
            f'<span class="titulo">{html.escape(titulo)}</span>'
            f'<a class="boton" href="{html.escape(ruta.name)}">Abrir cuestionario</a>'
            "</li>"
        )
    cuerpo = (
        '<div class="progreso">Ingresa tu nombre, cédula y grupo antes de responder. '
        "Cada respuesta se fija al primer clic.</div>\n"
        "<h2>Cuestionarios disponibles</h2>\n"
        f'<ul class="indice">{"".join(entradas)}</ul>'
    )
    documento = M._documento("Cuestionarios del curso", {"curso": "", "tipo": ""}, cuerpo, "")
    return documento.replace("</style>\n", f"</style>\n<style>\n{CSS_INDICE}</style>\n", 1)


def _preparar(archivos: list[Path], stage: Path) -> list[dict]:
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    publicados = []
    for ruta in archivos:
        destino = stage / ruta.name
        shutil.copyfile(ruta, destino)
        publicados.append(
            {
                "archivo": ruta.name,
                "sha256": hashlib.sha256(destino.read_bytes()).hexdigest(),
            }
        )
    (stage / "index.html").write_text(_indice_html(archivos), encoding="utf-8")
    (stage / ".nojekyll").write_text("", encoding="utf-8")
    return publicados


def _entorno_git() -> dict[str, str]:
    entorno = dict(os.environ)
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


def _ejecutar(cmd: list[str], cwd: Path | None = None, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_entorno_git(),
    )


def _asegurar_repo(repo: str) -> str | None:
    vista = _ejecutar(["gh", "repo", "view", repo, "--json", "name"])
    if vista.returncode == 0:
        return None
    creacion = _ejecutar(
        [
            "gh",
            "repo",
            "create",
            repo,
            "--public",
            "--description",
            "Cuestionarios del curso (variante alumno)",
        ]
    )
    if creacion.returncode != 0:
        return (creacion.stderr or creacion.stdout or "gh repo create falló")[-600:]
    return None


def _publicar_git(stage: Path, repo: str) -> str | None:
    pasos = [
        ["git", "init", "-b", "main"],
        ["git", "add", "-A"],
        ["git", "commit", "-m", MENSAJE_COMMIT],
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
        proc = _ejecutar(cmd, cwd=stage)
        if proc.returncode != 0:
            return f"{' '.join(cmd)}: {(proc.stderr or proc.stdout)[-500:]}"
    return None


def _cmd_visibilidad(repo: str, visibilidad: str) -> list[str]:
    """Comando para cambiar la visibilidad del repo.

    Se usa la API REST en vez de `gh repo edit --visibility`: ese subcomando pide
    confirmación interactiva y su flag de aceptación
    (`--accept-visibility-change-consequences`) solo existe desde gh 2.56; esta
    máquina trae 2.45, donde el comando muere imprimiendo la ayuda. `-F` (no `-f`)
    convierte `true`/`false` en booleanos de verdad.
    """
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


def _visibilidad_actual(repo: str) -> str | None:
    proc = _ejecutar(["gh", "api", f"repos/{repo}", "--jq", ".visibility"])
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()
    return None


def _cambiar_visibilidad(repo: str, visibilidad: str) -> str | None:
    """None si el repo quedó en la visibilidad pedida; si no, el motivo."""
    proc = _ejecutar(_cmd_visibilidad(repo, visibilidad))
    if proc.returncode != 0:
        return (proc.stderr or proc.stdout or "gh repo edit falló")[-500:]
    actual = _visibilidad_actual(repo)
    if actual != visibilidad:
        return f"el repo sigue en {actual!r} después de pedir {visibilidad!r}"
    return None


def _habilitar_pages(repo: str) -> str | None:
    proc = _ejecutar(
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


def _esperar_pages(url: str, intentos: int = 18, espera: float = 5.0) -> bool:
    for _ in range(intentos):
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(espera)
    return False


def _owner_por_defecto() -> str:
    proc = _ejecutar(["gh", "api", "user", "--jq", ".login"])
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()
    return "cero97-ctrl"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publica solo la variante alumno en un repo público de GitHub Pages."
    )
    parser.add_argument("--web-dir", default=WEB_POR_DEFECTO, help="Carpeta web del curso.")
    parser.add_argument("--stage", default=STAGE_POR_DEFECTO, help="Directorio de preparación.")
    parser.add_argument("--repo", default=None, help="owner/nombre destino.")
    parser.add_argument("--push", action="store_true", help="Crea/actualiza el repo y Pages.")
    parser.add_argument("--dry-run", action="store_true", help="Solo prepara el payload.")
    parser.add_argument(
        "--visibilidad",
        choices=["public", "private"],
        default=None,
        help=(
            "Cambia la visibilidad del repo destino. `private` deja la URL en 404 "
            "(Pages no sirve repos privados sin plan de pago): es la forma de "
            "ocultar el cuestionario hasta el día del examen."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    args = parser.parse_args()

    repo = args.repo or f"{_owner_por_defecto()}/cuestionarios"
    owner, nombre = repo.split("/", 1)
    url = f"https://{owner}.github.io/{nombre}/"

    if args.visibilidad and not args.push:
        error = _cambiar_visibilidad(repo, args.visibilidad)
        if error is not None:
            salida = _resultado("error", 4, repo=repo, message=error)
            print(json.dumps(salida) if args.json else f"error: {error}", file=None if args.json else sys.stderr)
            return 4
        visible = False
        if args.visibilidad == "public":
            _habilitar_pages(repo)
            visible = _esperar_pages(url)
        salida = _resultado(
            "ok", 0, repo=repo, url=url, visibilidad=args.visibilidad,
            publicado=False, pages_visible=visible,
        )
        if args.json:
            print(json.dumps(salida, ensure_ascii=False, indent=2))
        else:
            print(f"Visibilidad de {repo}: {args.visibilidad}")
            if args.visibilidad == "private":
                print(f"  {url} deja de responder (404): Pages no sirve repos privados")
            elif visible:
                print(f"  {url} responde 200")
            else:
                print(f"  aviso: {url} aún no responde (puede tardar un minuto)")
        return 0

    try:
        web_dir = _validar_web_dir(RAIZ / args.web_dir)
    except PermissionError as exc:
        salida = _resultado("error", 5, message=str(exc))
        print(json.dumps(salida) if args.json else f"error: {exc}", file=None if args.json else sys.stderr)
        return 5

    archivos = _recolectar(web_dir)
    problemas = _validar_payload(archivos)
    if problemas:
        salida = _resultado("error", 3, problemas=problemas)
        if args.json:
            print(json.dumps(salida, ensure_ascii=False))
        else:
            print("publicación rechazada:", file=sys.stderr)
            for problema in problemas:
                print(f"  - {problema}", file=sys.stderr)
        return 3

    stage = (RAIZ / args.stage / nombre).resolve()

    try:
        publicados = _preparar(archivos, stage)
    except OSError as exc:
        salida = _resultado("error", 1, message=str(exc))
        print(json.dumps(salida) if args.json else f"error: {exc}", file=None if args.json else sys.stderr)
        return 1

    if args.dry_run or not args.push:
        salida = _resultado(
            "ok", 0, repo=repo, url=url, stage=str(stage), archivos=publicados,
            publicado=False,
        )
        if args.json:
            print(json.dumps(salida, ensure_ascii=False, indent=2))
        else:
            print(f"Preparado en {stage} (sin publicar)")
            for item in publicados:
                print(f"  ok    {item['archivo']}  {item['sha256'][:16]}")
            print(f"Destino: {repo}  →  {url}")
        return 0

    error = _asegurar_repo(repo)
    if error is None:
        error = _publicar_git(stage, repo)
    if error is None:
        error = _habilitar_pages(repo)
    if error is not None:
        salida = _resultado("error", 4, repo=repo, message=error)
        print(json.dumps(salida) if args.json else f"error: {error}", file=None if args.json else sys.stderr)
        return 4

    if args.visibilidad:
        error = _cambiar_visibilidad(repo, args.visibilidad)
        if error is not None:
            salida = _resultado("error", 4, repo=repo, url=url, message=error)
            print(json.dumps(salida) if args.json else f"error: {error}", file=None if args.json else sys.stderr)
            return 4

    oculto = args.visibilidad == "private"
    visible = False if oculto else _esperar_pages(url)
    salida = _resultado(
        "ok", 0, repo=repo, url=url, stage=str(stage), archivos=publicados,
        publicado=True, pages_visible=visible,
        visibilidad=_visibilidad_actual(repo) or args.visibilidad,
    )
    if args.json:
        print(json.dumps(salida, ensure_ascii=False, indent=2))
    else:
        print(f"Publicado en {repo}")
        for item in publicados:
            print(f"  ok    {item['archivo']}  {item['sha256'][:16]}")
        print(f"URL: {url}")
        if oculto:
            print("  repo privado: la URL responde 404 hasta que se vuelva a poner público")
        elif not visible:
            print("  aviso: Pages aún no responde (puede tardar un minuto)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
