#!/usr/bin/env python3
"""Capa 3: publica el sitio de estudio generado en `SARA/` en GitHub Pages.

A diferencia de `publicar_cuestionario.py` (que recolecta solo `*_alumno.html`
de una carpeta plana), aquí se publica un **árbol** de páginas enlazadas entre
sí (portada, índices de materia y temas). El riesgo no es una clave, es publicar
algo que no debería salir o romper los enlaces al subirlo a un subdirectorio de
`github.io`. Por eso este script:

1. Solo acepta como origen `SARA/` (código 5 cualquier otra ruta) y solo copia
   archivos `.html`; la fuente privada (`SARA/contenido/*.yaml`) nunca viaja.
2. Rechaza (código 3) symlinks, recursos externos (`http(s)://`, `<link`,
   `src=`, `@import`), enlaces absolutos, enlaces que escapen de la raíz y
   cualquier `href` que no resuelva a un archivo del propio payload: un enlace
   roto en el colegio es una página que no se puede usar.
3. Copia el árbol preservando las rutas relativas (los `href` ya son relativos,
   así funcionan igual en `https://<owner>.github.io/<repo>/`), añade
   `.nojekyll` y reporta el sha256 de cada archivo.
4. Con `--push`, crea/actualiza el repo y habilita Pages usando la mecánica
   compartida de `execution/publicar_github.py` (commit fijo, push --force).
5. Con `--visibilidad private|public`, cambia la visibilidad del repo destino:
   `private` deja la URL en 404 (Pages no sirve repos privados sin plan de
   pago); `public` la devuelve.

Uso:
    python3 execution/publicar_material_sara.py --dry-run
    python3 execution/publicar_material_sara.py --push --repo cero97-ctrl/material-sara
    python3 execution/publicar_material_sara.py --visibilidad private
    python3 execution/publicar_material_sara.py --visibilidad public --push

Códigos de salida: 0 ok · 1 error de E/S · 3 payload rechazado ·
4 gh/git falló · 5 ruta de origen rechazada.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EJECUCION = RAIZ / "execution"
sys.path.insert(0, str(EJECUCION))
import publicar_github as G  # noqa: E402  (mecánica git/Pages compartida)

ORIGEN_POR_DEFECTO = "SARA"
STAGE_POR_DEFECTO = ".tmp/publicacion_sara"
MENSAJE_COMMIT = "Publicar material de estudio"
DESCRIPCION_REPO = "Material de estudio 3.º año (HTML autocontenido, sin dependencias)"
MARCAS_EXTERNAS = ("http://", "https://", "<link", "src=", "@import")
ESQUEMAS_PROHIBIDOS = ("http:", "https:", "mailto:", "javascript:", "//")
HREF = re.compile(r'href="([^"]*)"')


def _validar_origen(ruta: Path) -> Path:
    """El único origen permitido es el sitio generado del proyecto."""
    resuelta = ruta.resolve()
    esperada = (RAIZ / ORIGEN_POR_DEFECTO).resolve()
    if resuelta != esperada or not resuelta.is_dir():
        raise PermissionError(
            f"solo se publica el sitio generado en {esperada}; se recibió {resuelta}"
        )
    return resuelta


def _recolectar(origen: Path) -> tuple[list[str], list[str]]:
    """Devuelve (rutas relativas .html ordenadas, problemas)."""
    problemas: list[str] = []
    relativas: list[str] = []
    for ruta in sorted(origen.rglob("*"), key=lambda p: p.as_posix()):
        rel = ruta.relative_to(origen).as_posix()
        if ruta.is_symlink():
            problemas.append(f"{rel}: es un enlace simbólico; no se publica")
            continue
        if ruta.is_dir():
            continue
        if ruta.suffix == ".html":
            relativas.append(rel)
    return relativas, problemas


def _validar_payload(origen: Path, relativas: list[str]) -> list[str]:
    problemas: list[str] = []
    if "index.html" not in relativas:
        problemas.append("falta index.html en la raíz del sitio")
    conjunto = set(relativas)
    for rel in relativas:
        try:
            texto = (origen / rel).read_text(encoding="utf-8")
        except OSError as exc:
            problemas.append(f"{rel}: no se pudo leer ({exc})")
            continue
        for marca in MARCAS_EXTERNAS:
            if marca in texto:
                problemas.append(f"{rel}: contiene «{marca}»; el sitio debe ser offline")
        for coincidencia in HREF.finditer(texto):
            valor = coincidencia.group(1)
            if valor.startswith("#"):
                continue
            bajo = valor.lower()
            if any(bajo.startswith(esquema) for esquema in ESQUEMAS_PROHIBIDOS):
                problemas.append(f"{rel}: enlace externo o esquema prohibido «{valor}»")
                continue
            destino = valor.split("#", 1)[0].split("?", 1)[0]
            if not destino:
                continue
            if destino.startswith("/"):
                problemas.append(
                    f"{rel}: enlace absoluto «{valor}»; en Pages el sitio vive en un subdirectorio"
                )
                continue
            if ".yaml" in destino or "contenido/" in destino:
                problemas.append(f"{rel}: referencia a la fuente privada «{valor}»")
                continue
            normalizado = posixpath.normpath(
                posixpath.join(posixpath.dirname(rel), destino)
            )
            if normalizado.startswith("..") or normalizado.startswith("/"):
                problemas.append(f"{rel}: el enlace «{valor}» escapa de la raíz del sitio")
                continue
            if normalizado not in conjunto:
                problemas.append(f"{rel}: el enlace «{valor}» no resuelve a ningún archivo publicado")
    return problemas


def _preparar(origen: Path, relativas: list[str], stage: Path) -> list[dict]:
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    publicados = []
    for rel in relativas:
        destino = stage / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origen / rel, destino)
        publicados.append(
            {
                "archivo": rel,
                "sha256": hashlib.sha256(destino.read_bytes()).hexdigest(),
            }
        )
    (stage / ".nojekyll").write_text("", encoding="utf-8")
    return publicados


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publica el sitio de estudio generado en SARA/ en GitHub Pages."
    )
    parser.add_argument("--origen", default=ORIGEN_POR_DEFECTO, help="Carpeta del sitio generado.")
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
            "(Pages no sirve repos privados sin plan de pago); `public` la devuelve."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    args = parser.parse_args()

    repo = args.repo or f"{G.owner_por_defecto()}/material-sara"
    owner, nombre = repo.split("/", 1)
    url = f"https://{owner}.github.io/{nombre}/"

    if args.visibilidad and not args.push:
        error = G.cambiar_visibilidad(repo, args.visibilidad)
        if error is not None:
            salida = G.resultado("error", 4, repo=repo, message=error)
            print(json.dumps(salida) if args.json else f"error: {error}", file=None if args.json else sys.stderr)
            return 4
        visible = False
        if args.visibilidad == "public":
            G.habilitar_pages(repo)
            visible = G.esperar_pages(url)
        salida = G.resultado(
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
        origen = _validar_origen(RAIZ / args.origen)
    except PermissionError as exc:
        salida = G.resultado("error", 5, message=str(exc))
        print(json.dumps(salida) if args.json else f"error: {exc}", file=None if args.json else sys.stderr)
        return 5

    relativas, problemas = _recolectar(origen)
    problemas = problemas + _validar_payload(origen, relativas)
    if problemas:
        salida = G.resultado("error", 3, problemas=problemas)
        if args.json:
            print(json.dumps(salida, ensure_ascii=False))
        else:
            print("publicación rechazada:", file=sys.stderr)
            for problema in problemas:
                print(f"  - {problema}", file=sys.stderr)
        return 3

    stage = (RAIZ / args.stage / nombre).resolve()
    try:
        publicados = _preparar(origen, relativas, stage)
    except OSError as exc:
        salida = G.resultado("error", 1, message=str(exc))
        print(json.dumps(salida) if args.json else f"error: {exc}", file=None if args.json else sys.stderr)
        return 1

    if args.dry_run or not args.push:
        salida = G.resultado(
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

    error = G.asegurar_repo(repo, DESCRIPCION_REPO)
    if error is None:
        error = G.publicar_git(stage, repo, MENSAJE_COMMIT)
    # El orden importa: Pages no se habilita en un repo privado (HTTP 422), así
    # que primero se aplica `--visibilidad` y solo después, si quedó público, se
    # enciende Pages. Calcular `privado` antes del cambio dejaba
    # `--push --visibilidad public` con el repo público y la URL en 404.
    if error is None and args.visibilidad:
        error = G.cambiar_visibilidad(repo, args.visibilidad)
    if error is not None:
        salida = G.resultado("error", 4, repo=repo, message=error)
        print(json.dumps(salida) if args.json else f"error: {error}", file=None if args.json else sys.stderr)
        return 4

    privado = G.visibilidad_actual(repo) == "private"
    if not privado:
        error = G.habilitar_pages(repo)
        if error is not None:
            salida = G.resultado("error", 4, repo=repo, url=url, message=error)
            print(json.dumps(salida) if args.json else f"error: {error}", file=None if args.json else sys.stderr)
            return 4

    oculto = privado
    visible = False if oculto else G.esperar_pages(url)
    salida = G.resultado(
        "ok", 0, repo=repo, url=url, stage=str(stage), archivos=publicados,
        publicado=True, pages_visible=visible,
        visibilidad=G.visibilidad_actual(repo) or args.visibilidad,
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
