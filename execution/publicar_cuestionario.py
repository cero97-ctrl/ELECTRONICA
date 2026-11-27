#!/usr/bin/env python3
"""Capa 3: publica en GitHub Pages solo la variante `alumno` de los cuestionarios.

El repo del curso es público y la carpeta `cursos/<CURSO>/evaluaciones/web/`
(o su subcarpeta `SEMANA_NN`, p. ej. `web/SEMANA_01/`) contiene también
`_docente.html` (con `const CLAVE`) y `fuentes/*_respuestas.md` (la clave).
Publicar la carpeta entera, o un `git add -A` con una regla mal
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
    python3 execution/publicar_cuestionario.py --web-dir cursos/OTRO/evaluaciones/web/SEMANA_01 --json

Códigos de salida: 0 ok · 1 error de E/S · 3 payload rechazado (fuga) ·
4 gh/git falló · 5 ruta rechazada.

La mecánica de git/Pages (commit fijo, push --force, visibilidad por API REST)
vive una única vez en `execution/publicar_github.py`; este script solo aporta
la recolección y la barrera anti-fuga del payload.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EJECUCION = RAIZ / "execution"
sys.path.insert(0, str(EJECUCION))
import md_a_html as M  # noqa: E402  (reusa `_documento` y el estilo)
import publicar_github as G  # noqa: E402  (mecánica git/Pages compartida)

WEB_POR_DEFECTO = "cursos/CYBERSEGURIDAD/evaluaciones/web/SEMANA_01"
STAGE_POR_DEFECTO = ".tmp/publicacion"
MARCAS_FUGA = ("const CLAVE", "**Answer:**", "Modo docente")
MARCA_DATOS = 'id="estudiante-nombre"'
MENSAJE_COMMIT = "Publicar cuestionarios (alumno)"
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


def _validar_web_dir(ruta: Path) -> Path:
    """Admite `web/` y `web/SEMANA_NN/`, pero no subcarpetas arbitrarias.

    Los cursos que aún no se organizan por semana publican desde la raíz `web/`;
    Ciberseguridad ya trabaja en `web/SEMANA_NN/`. Se rechaza cualquier nivel
    adicional (p. ej. `web/SEMANA_01/fuentes/`) para que el glob de
    `_recolectar()` no se convierta en una excusa para publicar la carpeta entera.
    """
    resuelta = ruta.resolve()
    partes = resuelta.parts
    permitida = False
    if "cursos" in partes and "evaluaciones" in partes and "web" in partes:
        indice = len(partes) - 1 - partes[::-1].index("web")
        restantes = partes[indice + 1 :]
        permitida = not restantes or (
            len(restantes) == 1 and re.fullmatch(r"SEMANA_\d{2}", restantes[0]) is not None
        )
    if not permitida:
        raise PermissionError(
            "solo se publica desde cursos/<CURSO>/evaluaciones/web/ o desde "
            f"cursos/<CURSO>/evaluaciones/web/SEMANA_NN/, no desde {resuelta}"
        )
    return resuelta


def _recolectar(web_dir: Path) -> list[Path]:
    return sorted(
        (p for p in web_dir.glob("*_alumno.html") if p.is_file()),
        key=lambda p: p.name,
    )


def _validar_payload(archivos: list[Path]) -> list[str]:
    problemas: list[str] = []
    avisos: list[str] = []
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
        avisos.append(_aviso_de(texto))
    if any(avisos) and len(set(avisos)) != 1:
        problemas.append(
            "los cuestionarios no coinciden en el aviso del encabezado; "
            "regenerar todos desde el mismo `aviso:`"
        )
    return problemas


def _titulo_de(texto: str, respaldo: str) -> str:
    coincidencia = re.search(r"<title>(.*?)</title>", texto, re.S)
    if not coincidencia:
        return respaldo
    return html.unescape(coincidencia.group(1).strip()) or respaldo


def _aviso_de(texto: str) -> str:
    """Lee el aviso del encabezado de una página de alumno, si lo tiene."""
    coincidencia = re.search(r'<p class="aviso-cabecera">(.*?)</p>', texto, re.S)
    return html.unescape(coincidencia.group(1).strip()) if coincidencia else ""


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
    avisos = [_aviso_de(ruta.read_text(encoding="utf-8")) for ruta in archivos]
    aviso = next((a for a in avisos if a), "")
    documento = M._documento(
        "Cuestionarios del curso",
        {"curso": "", "tipo": "", "aviso": aviso},
        cuerpo,
        "",
    )
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


_resultado = G.resultado
_ejecutar = G.ejecutar
_cmd_visibilidad = G.cmd_visibilidad
_visibilidad_actual = G.visibilidad_actual
_cambiar_visibilidad = G.cambiar_visibilidad
_habilitar_pages = G.habilitar_pages
_esperar_pages = G.esperar_pages
_owner_por_defecto = G.owner_por_defecto


def _transicion_visibilidad(
    repo: str,
    pedida: str | None,
    *,
    cambiar=_cambiar_visibilidad,
    habilitar=_habilitar_pages,
    actual=_visibilidad_actual,
) -> tuple[str | None, bool]:
    """Deja `repo` en `pedida` (o como esté, si es None) y, si queda público,
    habilita Pages DESPUÉS del cambio. Devuelve (error, quedó_privado).

    El orden no es cosmético. Pages rechaza los repos privados sin plan de pago
    (HTTP 422 «Your current plan does not support GitHub Pages»), así que no se
    puede habilitar antes; y si el repo acaba de pasar a público y no se habilita
    después, la URL sigue en 404 y el flujo reporta `pages_visible` falso. Antes
    de unificar aquí, la rama `--push` calculaba `privado` con el estado viejo y
    se saltaba Pages al pasar a público: `--push --visibilidad public` dejaba el
    repo público y sin servir.
    """
    if pedida:
        error = cambiar(repo, pedida)
        if error is not None:
            return error, pedida == "private"
        privado = pedida == "private"
    else:
        privado = actual(repo) == "private"
    if not privado:
        error = habilitar(repo)
        if error is not None:
            return error, privado
    return None, privado


def _asegurar_repo(repo: str) -> str | None:
    return G.asegurar_repo(repo, "Cuestionarios del curso (variante alumno)")


def _publicar_git(stage: Path, repo: str) -> str | None:
    return G.publicar_git(stage, repo, MENSAJE_COMMIT)


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
        error, privado = _transicion_visibilidad(repo, args.visibilidad)
        if error is not None:
            salida = _resultado("error", 4, repo=repo, message=error)
            print(json.dumps(salida) if args.json else f"error: {error}", file=None if args.json else sys.stderr)
            return 4
        visible = False if privado else _esperar_pages(url)
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
    # Visibilidad y Pages en una sola transición (ver _transicion_visibilidad):
    # el contenido se puede subir a un repo privado, donde Pages no existe
    # todavía, y `--visibilidad public` es quien lo habilita el día del examen.
    if error is None:
        error, privado = _transicion_visibilidad(repo, args.visibilidad)
    else:
        privado = True
    if error is not None:
        salida = _resultado("error", 4, repo=repo, message=error)
        print(json.dumps(salida) if args.json else f"error: {error}", file=None if args.json else sys.stderr)
        return 4

    oculto = privado
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
