#!/usr/bin/env python3
"""Pruebas de regresion de execution/verificar_texto.py.

Cada caso fija un fallo que se cometio de verdad al construir el detector, no
un fallo hipotetico. Sin estas pruebas, todo lo que se corrigio vuelve en la
siguiente refactorizacion.

Ejecutar: python3 execution/test_verificar_texto.py
Salida:  0 si todas pasan, 1 si alguna falla.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / "execution" / "verificar_texto.py"
FLUJO = PROJECT_ROOT / "flujo_verificar_texto.py"

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


def ejecutar(args: list[str], guion: Path = SCRIPT) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(guion), *args],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=600,
    )
    return proc.returncode, proc.stdout


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        limpio = base / "limpio.md"
        limpio.write_text("Texto normal en espanol, con acentos: el orden.\n", encoding="utf-8")
        extranjero = base / "extranjero.md"
        extranjero.write_text("Una frase con cirilico: Привет.\n", encoding="utf-8")
        Griego = base / "griego.md"
        Griego.write_text("Resistencias de 1 kΩ, beta=100, tau=0.1 s, pi y mu.\n", encoding="utf-8")
        cjk = base / "cjk.md"
        cjk.write_text("Un manual en 简体 chino.\n", encoding="utf-8")

        print("== Clases de deteccion ==")
        rc, _ = ejecutar([str(extranjero)])
        comprobar("cirilico se detecta", rc == 1, f"exit={rc}")

        rc, _ = ejecutar([str(cjk)])
        comprobar("CJK se detecta", rc == 1, f"exit={rc}")

        rc, out = ejecutar([str(Griego)])
        comprobar(
            "griego NO se detecta (notacion de electronica, no corrupcion)",
            rc == 0, f"exit={rc}; {out[:120]}",
        )

        rc, _ = ejecutar([str(limpio)])
        comprobar("texto limpio no dispara", rc == 0, f"exit={rc}")

        print("== Guardas contra el verde falso ==")
        rc, out = ejecutar([str(base / "no_existe")])
        comprobar("ruta inexistente da 2, no 0", rc == 2, f"exit={rc}")
        comprobar("y lo dice explicitamente", "SIN VERIFICAR" in out)

        solo_pdf_dir = base / "solopdf"
        solo_pdf_dir.mkdir()
        (solo_pdf_dir / "documento.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
        rc, _ = ejecutar([str(solo_pdf_dir)])
        comprobar(
            "directorio sin texto da 2, no un verde vacio",
            rc == 2, f"exit={rc}",
        )

        print("== Cobertura honesta ==")
        rc, out = ejecutar(["--json", str(base)])
        import json as _json
        datos = _json.loads(out)
        cov = datos["cobertura"]
        comprobar("no_texto se cuenta aparte", cov["ficheros_no_texto"] >= 1,
                  str(cov.get("ficheros_no_texto")))
        comprobar("griego no figura como omision", cov["ficheros_omitidos"] == 0,
                  str(cov["motivos_omision"]))

        print("== Ficheros meta ==")
        # Pedir SOLO ficheros meta da 2, no 0: si lo unico que se pide esta
        # excluido, no se escaneo nada, y 'no se ha comprobado nada' es la
        # respuesta honesta. Un 0 aqui seria un verde sobre el vacio.
        rc, _ = ejecutar([str(SCRIPT)])
        comprobar("pedir solo el propio script da 2 (no queda nada que leer)", rc == 2, f"exit={rc}")
        rc, _ = ejecutar([str(SCRIPT.parent / "detecciones_texto.json")])
        comprobar("pedir solo el catalogo de cadenas da 2", rc == 2, f"exit={rc}")
        rc, _ = ejecutar([str(SCRIPT.parent / "test_verificar_texto.py")])
        comprobar("pedir solo el fichero de pruebas da 2 (contiene los fixtures)", rc == 2, f"exit={rc}")
        rc, out = ejecutar(["--json", str(limpio), str(SCRIPT)])
        comprobar("meta + un fichero real si se escanea", '"ficheros_escaneados": 1' in out)

        print("== Opt-in de heuristicas ==")
        camel = base / "camel.md"
        # No se puede reutilizar una cadena del catalogo: entonces dispararia
        # por la clase 'conocido' y la prueba no mediria nada de 'camel'.
        camel.write_text("El informe unTextoFusionado en la seccion tres.\n", encoding="utf-8")
        rc, _ = ejecutar([str(camel)])
        comprobar("camel apagado por defecto", rc == 0, f"exit={rc}")
        rc, _ = ejecutar([str(camel), "--class", "camel"])
        comprobar("camel se activa al pedirlo", rc == 1, f"exit={rc}")

        print("== Diacriticos ==")
        con_tilde = base / "tilde.md"
        con_tilde.write_text("Investiga el error y susArréglalo ya.\n", encoding="utf-8")
        sin_tilde = base / "sintilde.md"
        sin_tilde.write_text("Investiga el error y susArreglalo ya.\n", encoding="utf-8")
        rc_a, _ = ejecutar([str(con_tilde)])
        rc_b, _ = ejecutar([str(sin_tilde)])
        comprobar("con tilde se detecta", rc_a == 1, f"exit={rc_a}")
        comprobar("sin tilde tambien (insensible a diacriticos)", rc_b == 1, f"exit={rc_b}")

        # Este test corre el flujo real, que escribe en el .tmp REAL del
        # proyecto. Antes se dejaba la vista puesta y `estado_sesion.py` la
        # reportaba como huerfana en cada ejecucion: el test contaminaba el
        # estado que despues audita. El snapshot va ANTES de la primera
        # invocacion (las siguientes ya lo crean), y al final se retira solo lo
        # que el test creo, sin tocar una vista preexistente de otro flujo.
        _vista = PROJECT_ROOT / ".tmp" / "run_state.json"
        _preexistente = _vista.is_file()
        print("== Flujo (capa 2) ==")
        rc, out = ejecutar([str(base)], guion=FLUJO)
        comprobar("el flujo propaga exit 1 con hallazgos", rc == 1, f"exit={rc}")
        comprobar("y nombra el veredicto", "con_hallazgos" in out)

        rc, out = ejecutar([str(base / "no_existe")], guion=FLUJO)
        comprobar("el flujo propaga exit 2 sin verificar", rc == 2, f"exit={rc}")
        comprobar("y advierte que no comprobo nada", "NO ha comprobado nada" in out)

        rc, out = ejecutar([str(base)], guion=FLUJO)
        comprobar("el flujo escribe estado en run_state", _vista.is_file())

    # Retirar la vista que este test creo (ver el snapshot mas arriba). El
    # log append-only NO se toca: es la verdad permanente.
    if "_vista" in dir() and not _preexistente and _vista.is_file():
        _vista.unlink()

    print()
    if FALLOS:
        print(f"FALLOS: {len(FALLOS)}/{PRUEBAS}")
        for f in FALLOS:
            print(f"  - {f}")
        return 1
    print(f"Aserciones OK: {PRUEBAS}   Fallos: 0")
    print("VERIFICADOR DE TEXTO OK: clases, guardas, cobertura, meta, opt-in y flujo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
