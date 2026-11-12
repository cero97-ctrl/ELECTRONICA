#!/usr/bin/env python3
"""Pruebas de la barrera de publicación (solo la variante alumno).

Fija el contrato que impide que la clave llegue a un repo público: el payload
rechaza `_docente.html`, archivos con `const CLAVE`/`**Answer:**`/`Modo docente`
y HTML sin el módulo de datos; el índice no menciona al docente; y el mismo
payload produce los mismos bytes.

Ejecutar: python3 execution/test_publicar_cuestionario.py
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
        "publicar_bajo_test", RAIZ / "execution/publicar_cuestionario.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["publicar_bajo_test"] = mod
    spec.loader.exec_module(mod)
    return mod


P = _cargar()

ALUMNO = (
    "<!doctype html><html><head><title>Cuestionario de prueba</title></head><body>"
    '<section class="datos" id="datos-estudiante">'
    '<input type="text" id="estudiante-nombre" name="estudiante_nombre">'
    "</section></body></html>"
)
DOCENTE = (
    "<!doctype html><html><head><title>Cuestionario de prueba</title></head><body>"
    "<script>const CLAVE = {\"1\":\"B\"};</script></body></html>"
)


def _escribir(directorio: Path, nombre: str, texto: str) -> Path:
    ruta = directorio / nombre
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def test_payload_valido():
    with tempfile.TemporaryDirectory() as tmp:
        ruta = _escribir(Path(tmp), "cuestionario_alumno.html", ALUMNO)
        problemas = P._validar_payload([ruta])
        comprobar("el alumno con datos pasa", not problemas, str(problemas))


def test_rechaza_docente_por_nombre():
    with tempfile.TemporaryDirectory() as tmp:
        ruta = _escribir(Path(tmp), "cuestionario_docente.html", ALUMNO)
        problemas = P._validar_payload([ruta])
        comprobar("rechaza *_docente.html", any("docente" in p for p in problemas), str(problemas))


def test_rechaza_clave_en_contenido():
    with tempfile.TemporaryDirectory() as tmp:
        ruta = _escribir(Path(tmp), "cuestionario_alumno.html", DOCENTE)
        problemas = P._validar_payload([ruta])
        comprobar("rechaza const CLAVE", any("const CLAVE" in p for p in problemas), str(problemas))


def test_rechaza_marcas_de_respuestas():
    with tempfile.TemporaryDirectory() as tmp:
        texto = ALUMNO.replace("</body>", "**Answer:** B.</body>")
        ruta = _escribir(Path(tmp), "cuestionario_alumno.html", texto)
        problemas = P._validar_payload([ruta])
        comprobar("rechaza **Answer:**", any("Answer" in p for p in problemas), str(problemas))
        texto = ALUMNO.replace("</body>", "Modo docente</body>")
        ruta = _escribir(Path(tmp), "cuestionario_alumno.html", texto)
        problemas = P._validar_payload([ruta])
        comprobar("rechaza Modo docente", any("Modo docente" in p for p in problemas), str(problemas))


def test_rechaza_sin_datos():
    with tempfile.TemporaryDirectory() as tmp:
        texto = "<!doctype html><html><body>sin datos</body></html>"
        ruta = _escribir(Path(tmp), "cuestionario_alumno.html", texto)
        problemas = P._validar_payload([ruta])
        comprobar("rechaza HTML sin módulo de datos", any("datos del estudiante" in p for p in problemas), str(problemas))


def test_rechaza_lista_vacia():
    comprobar("rechaza carpeta sin *_alumno.html", bool(P._validar_payload([])))


def test_indice_solo_alumno():
    with tempfile.TemporaryDirectory() as tmp:
        a = _escribir(Path(tmp), "uno_alumno.html", ALUMNO)
        b = _escribir(Path(tmp), "dos_alumno.html", ALUMNO.replace("prueba", "segundo"))
        indice = P._indice_html([a, b])
        comprobar("índice enlaza los dos", indice.count("Abrir cuestionario") == 2, indice[:200])
        comprobar("índice sin docente", "docente" not in indice.lower())
        comprobar("índice sin clave", "CLAVE" not in indice)
        comprobar("índice pide datos", "cédula" in indice)


def test_payload_determinista():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        a = _escribir(base, "uno_alumno.html", ALUMNO)
        primera = P._preparar([a], base / "stage1")
        segunda = P._preparar([a], base / "stage2")
        comprobar(
            "mismo payload, mismos sha256",
            [x["sha256"] for x in primera] == [x["sha256"] for x in segunda],
        )
        comprobar(
            "index.html idéntico",
            (base / "stage1/index.html").read_bytes()
            == (base / "stage2/index.html").read_bytes(),
        )
        comprobar("crea .nojekyll", (base / "stage1/.nojekyll").is_file())


def test_barrera_de_rutas():
    try:
        P._validar_web_dir(RAIZ / "docs")
        comprobar("rechaza publicar desde docs/", False)
    except PermissionError:
        comprobar("rechaza publicar desde docs/", True)
    try:
        P._validar_web_dir(RAIZ / "cursos")
        comprobar("rechaza una carpeta que no es web/", False)
    except PermissionError:
        comprobar("rechaza una carpeta que no es web/", True)


def test_titulo():
    comprobar(
        "extrae el título del HTML",
        P._titulo_de(ALUMNO, "respaldo") == "Cuestionario de prueba",
    )
    comprobar("usa respaldo sin título", P._titulo_de("<html></html>", "respaldo") == "respaldo")


def test_visibilidad():
    """El interruptor de visibilidad: ocultar el cuestionario hasta el examen."""
    cmd = P._cmd_visibilidad("cero97-ctrl/cuestionarios", "private")
    comprobar("usa la API REST (no `gh repo edit`)", cmd[:4] == ["gh", "api", "-X", "PATCH"], str(cmd))
    comprobar("apunta al repo", "repos/cero97-ctrl/cuestionarios" in cmd, str(cmd))
    comprobar(
        "-F convierte a booleano: private=true",
        "private=true" in cmd and "-F" in cmd and "-f" not in cmd,
        str(cmd),
    )
    comprobar(
        "public invierte el flag",
        P._cmd_visibilidad("a/b", "public")[-1] == "private=false",
        str(P._cmd_visibilidad("a/b", "public")),
    )
    comprobar(
        "no depende de flags que faltan en gh 2.45",
        "--accept-visibility-change-consequences" not in cmd,
        str(cmd),
    )


def main() -> int:
    print("Pruebas de la barrera de publicación")
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
