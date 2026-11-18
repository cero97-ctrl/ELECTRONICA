#!/usr/bin/env python3
"""Pruebas de la barrera de publicación del sitio de Sara.

Qué se fija aquí y por qué:
  - El origen es uno solo: `SARA/`. Publicar otra carpeta por error expondría
    material que no es de Sara (código 5).
  - El payload es solo `.html` enlazado consigo mismo: sin symlinks, sin
    recursos externos, sin enlaces absolutos (Pages sirve el sitio en un
    subdirectorio), sin enlaces que escapen de la raíz y sin `href` rotos.
    Un enlace roto en el colegio es una página que no se puede usar.
  - La fuente privada (`SARA/contenido/*.yaml`) nunca entra al stage.
  - El sitio real publicado no menciona el nombre de Sara: es una menor y la
    página es pública e indexable.
  - El payload es determinista: mismo sitio, mismos sha256.

Ejecutar: python3 execution/test_publicar_material_sara.py
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FALLOS: list[str] = []
PRUEBAS = 0


def comprobar(nombre: str, condicion: bool, detalle: str = "") -> None:
    global PRUEBAS
    PRUEBAS += 1
    if condicion:
        print(f"  ok   {nombre}")
    else:
        print(f"  FALLA {nombre}" + (f" -- {detalle}" if detalle else ""))
        FALLOS.append(nombre)


def _cargar():
    spec = importlib.util.spec_from_file_location(
        "publicar_sara_bajo_test", RAIZ / "execution/publicar_material_sara.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["publicar_sara_bajo_test"] = mod
    spec.loader.exec_module(mod)
    return mod


P = _cargar()

PAGINA = (
    "<!DOCTYPE html>\n<html lang=\"es\">\n<head><title>{titulo}</title></head>\n"
    "<body>{cuerpo}</body></html>\n"
)


def _escribir(base: Path, rel: str, cuerpo: str = "", titulo: str = "Tema") -> Path:
    ruta = base / rel
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(PAGINA.format(titulo=titulo, cuerpo=cuerpo), encoding="utf-8")
    return ruta


def _arbol_ok(base: Path) -> None:
    _escribir(base, "index.html", '<a href="mate/index.html">Mate</a>')
    _escribir(
        base,
        "mate/index.html",
        '<a href="../index.html">Inicio</a><a href="01-tema.html">Tema</a>',
    )
    _escribir(base, "mate/01-tema.html", '<a href="index.html">Volver</a><a href="#c">Ancla</a>')


def test_origen_rechazado():
    try:
        P._validar_origen(RAIZ / "docs")
        comprobar("rechaza publicar desde docs/", False)
    except PermissionError:
        comprobar("rechaza publicar desde docs/", True)
    try:
        P._validar_origen(RAIZ / "SARA" / "contenido")
        comprobar("rechaza un subdirectorio de SARA/", False)
    except PermissionError:
        comprobar("rechaza un subdirectorio de SARA/", True)
    comprobar(
        "acepta el sitio generado",
        P._validar_origen(RAIZ / "SARA") == (RAIZ / "SARA").resolve(),
    )


def test_payload_valido():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _arbol_ok(base)
        relativas, problemas_reco = P._recolectar(base)
        problemas = problemas_reco + P._validar_payload(base, relativas)
        comprobar("el árbol enlazado pasa", not problemas, str(problemas))
        comprobar("recolecta las tres páginas", relativas == [
            "index.html",
            "mate/01-tema.html",
            "mate/index.html",
        ], str(relativas))


def test_rechaza_enlace_externo():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _escribir(base, "index.html", '<a href="https://ejemplo.com">Fuera</a>')
        relativas, _ = P._recolectar(base)
        problemas = P._validar_payload(base, relativas)
        comprobar("rechaza https:// en un href", any("externo" in p for p in problemas), str(problemas))


def test_rechaza_marca_de_recurso_externo():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _escribir(base, "index.html", '<img src="logo.png">')
        relativas, _ = P._recolectar(base)
        problemas = P._validar_payload(base, relativas)
        comprobar("rechaza src= (recurso externo)", any("src=" in p for p in problemas), str(problemas))


def test_rechaza_enlace_roto():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _escribir(base, "index.html", '<a href="no-existe.html">Roto</a>')
        relativas, _ = P._recolectar(base)
        problemas = P._validar_payload(base, relativas)
        comprobar("rechaza un href que no resuelve", any("no resuelve" in p for p in problemas), str(problemas))


def test_rechaza_enlace_absoluto():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _escribir(base, "index.html", '<a href="/index.html">Absoluto</a>')
        relativas, _ = P._recolectar(base)
        problemas = P._validar_payload(base, relativas)
        comprobar("rechaza href absoluto", any("absoluto" in p for p in problemas), str(problemas))


def test_rechaza_escape_de_raiz():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _escribir(base, "index.html", "")
        _escribir(base, "mate/index.html", '<a href="../../fuera.html">Fuera</a>')
        relativas, _ = P._recolectar(base)
        problemas = P._validar_payload(base, relativas)
        comprobar("rechaza un enlace que escapa de la raíz", any("escapa" in p for p in problemas), str(problemas))


def test_rechaza_fuente_privada():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _escribir(base, "index.html", '<a href="contenido/tema.yaml">Fuente</a>')
        relativas, _ = P._recolectar(base)
        problemas = P._validar_payload(base, relativas)
        comprobar("rechaza referencias a contenido/*.yaml", any("fuente privada" in p for p in problemas), str(problemas))


def test_rechaza_symlink():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _arbol_ok(base)
        enlace = base / "mate" / "atajo.html"
        enlace.symlink_to(base / "index.html")
        relativas, problemas = P._recolectar(base)
        comprobar("rechaza symlinks", any("simbólico" in p for p in problemas), str(problemas))
        comprobar("el symlink no entra al payload", all("atajo" not in r for r in relativas), str(relativas))


def test_falta_indice():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _escribir(base, "mate/index.html", "sin raíz")
        relativas, _ = P._recolectar(base)
        problemas = P._validar_payload(base, relativas)
        comprobar("rechaza un sitio sin index.html raíz", any("falta index.html" in p for p in problemas), str(problemas))


def test_stage_solo_html():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _arbol_ok(base)
        (base / "contenido").mkdir()
        (base / "contenido" / "tema.yaml").write_text("materia: matematicas\n", encoding="utf-8")
        relativas, _ = P._recolectar(base)
        stage = base / "stage"
        publicados = P._preparar(base, relativas, stage)
        nombres = {item["archivo"] for item in publicados}
        comprobar("el stage no lleva YAML", not (stage / "contenido").exists())
        comprobar("el stage lleva las tres páginas", nombres == {
            "index.html",
            "mate/01-tema.html",
            "mate/index.html",
        }, str(nombres))
        comprobar("el stage crea .nojekyll", (stage / ".nojekyll").is_file())
        comprobar(
            "preserva las rutas relativas",
            (stage / "mate" / "01-tema.html").is_file(),
        )


def test_payload_determinista():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _arbol_ok(base)
        relativas, _ = P._recolectar(base)
        primera = P._preparar(base, relativas, base / "stage1")
        segunda = P._preparar(base, relativas, base / "stage2")
        comprobar(
            "mismo sitio, mismos sha256",
            [x["sha256"] for x in primera] == [x["sha256"] for x in segunda],
        )


def test_sitio_real_valido():
    origen = RAIZ / "SARA"
    if not origen.is_dir():
        comprobar("el sitio real existe", False, "falta SARA/")
        return
    relativas, problemas_reco = P._recolectar(origen)
    problemas = problemas_reco + P._validar_payload(origen, relativas)
    comprobar("el sitio real pasa la barrera", not problemas, str(problemas))
    comprobar("el sitio real tiene 14 páginas", len(relativas) == 14, str(len(relativas)))


def test_sitio_real_offline_y_anonimo():
    origen = RAIZ / "SARA"
    if not origen.is_dir():
        comprobar("el sitio real existe", False, "falta SARA/")
        return
    todo = "\n".join((origen / rel).read_text(encoding="utf-8") for rel in sorted(
        p.relative_to(origen).as_posix() for p in origen.rglob("*.html")
    ))
    for marca in ("http://", "https://", "<link", "src=", "@import"):
        comprobar(f"el sitio real no contiene {marca}", marca not in todo)
    comprobar(
        "el sitio real no menciona el nombre de Sara",
        "Sara" not in todo and "SARA" not in todo,
    )


def test_mecanica_compartida():
    comprobar(
        "la visibilidad viene de publicar_github",
        P.G.cmd_visibilidad("a/b", "private")[-1] == "private=true",
    )
    comprobar(
        "el commit y la descripción del repo están fijados",
        bool(P.MENSAJE_COMMIT) and bool(P.DESCRIPCION_REPO),
    )


def main() -> int:
    print("Pruebas de la barrera de publicación del sitio de Sara")
    print("=" * 60)
    for fn in sorted(
        (f for f in globals() if f.startswith("test_")),
        key=lambda n: list(globals()).index(n),
    ):
        print(f"\n[{fn}]")
        globals()[fn]()
    print("\n" + "=" * 60)
    print(f"{PRUEBAS - len(FALLOS)}/{PRUEBAS} aserciones OK")
    if FALLOS:
        print(f"\n{len(FALLOS)} FALLAS:")
        for fallo in FALLOS:
            print(f"  - {fallo}")
        return 1
    print("Sin fallos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
