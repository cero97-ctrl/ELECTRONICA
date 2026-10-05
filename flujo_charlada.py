#!/usr/bin/env python3
r"""
flujo_charlada.py — Orquestador del material de la conferencia (Layer 2)

Su trabajo NO es generar el material: eso lo hace `execution/generar_charlada_latex.py`
(capa 3). Su trabajo es decidir, delegar y, sobre todo, **no publicar nada que no
haya sido verificado**.

La capa 2 no calcula ni compila. Hace tres cosas que la capa 3 no puede hacer por sí
misma, y las tres son validaciones:

  1. Delegar la generación en la capa 3 y leer su informe.
  2. **Verificar las cifras** que el material afirma. El generador las mide, pero
     quien las juzga es el orquestador: si una cifra no se puede reproducir, no se
     publica. Un número en una transparencia es una afirmación que alguien puede
     comprobar en el atril.
  3. **No copiar los PDF si su log vino sucio.** Un PDF existe aunque el documento
     esté roto (modo nonstopmode); por eso la pregunta correcta no es «¿existe el
     PDF?» sino «¿su log está limpio?».

Uso:
    python3 flujo_charlada.py --salida-dir docs/AGENTE_IA --autor "César R."
    python3 flujo_charlada.py --verificar-cifras     # solo comprueba, no genera

Códigos de salida:
    0  material generado, verificado y publicado
    1  fallo de verificación (cifras que no cuadran)
    2  uso incorrecto
    3  la capa 3 falló o devolvió compilación sucia -> no se publica nada
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
SCRIPT_DIR = RAIZ / "execution"
BUILD_DIR = RAIZ / ".tmp" / "charlada"
INFORME = BUILD_DIR / "deck.json"
GENERADOR = SCRIPT_DIR / "generar_charlada_latex.py"
TESTS_CIFRA = [
    "barrera_disco", "auditar_repo", "auditar_sistema",
    "evaluar_rubrica", "inspeccionar_entrega", "verificar_texto",
]

sys.path.insert(0, str(SCRIPT_DIR))
import run_state as RS  # noqa: E402  (capa 3, resolucion explicita)

PYTHON = sys.executable
ALERTAR = SCRIPT_DIR / "alert_user.py"


# ─────────────────────────────────────────────────────────────────────────────
def paso(n: int, total: int, desc: str) -> None:
    print(f"\n[{n}/{total}] {desc}")


def ok(msg: str) -> None:
    print(f"      OK   {msg}")


def fallo(msg: str) -> None:
    print(f"      FALLO {msg}")


def avisar(tipo: str) -> None:
    subprocess.run([PYTHON, str(ALERTAR), tipo], capture_output=True)


# ─────────────────────────────────────────────────────────────────────────────
def verificar_cifras() -> tuple[bool, list[str]]:
    """Reejecuta los tests para confirmar la cifra de aserciones del material.

    Es la comprobación que sostiene la credibilidad de la transparencia más
    citados. El número del deck no se copia de un documente: se vuelve a obtener
    ejecutando. Si un día un test se rompe, la cifra del material deja de ser
    cierta y hay que saberlo antes de hablar, no después.
    """
    notas: list[str] = []
    total = 0
    for nombre in TESTS_CIFRA:
        test = SCRIPT_DIR / f"test_{nombre}.py"
        if not test.exists():
            notas.append(f"{nombre}: test no encontrado")
            continue
        res = subprocess.run([PYTHON, str(test)], capture_output=True, text=True, cwd=str(RAIZ))
        salida = res.stdout + res.stderr
        # Los tests no hablan todos igual: cinco imprimen "Aserciones OK: N" y uno
        # "41/41 aserciones OK". Dos patrones explicitos, no una alternancia
        # imposible de leer.
        n = None
        if m := re.search(r"Aserciones OK:\s*(\d+)", salida):
            n = int(m.group(1))
        elif m := re.search(r"(\d+)/\s*(\d+)\s*aserciones", salida):
            n = int(m.group(2))
        if n is None:
            notas.append(f"{nombre}: no se pudo leer el conteo (código {res.returncode})")
            continue
        if res.returncode != 0:
            notas.append(f"{nombre}: FALLA (código {res.returncode})")
        total += n
    ok(f"aserciones verificadas ejecutando {len(TESTS_CIFRA)} ficheros de test: {total}")
    return (not notas), notas


def comparar_cifras(informe: dict) -> list[str]:
    """Contrasta las cifras del informe con lo que el disco tiene hoy."""
    c = informe.get("cifras", {})
    import glob
    esperado_directivas = len(glob.glob(str(RAIZ / "directives" / "*.yaml")))
    esperado_ejec = len([p for p in glob.glob(str(RAIZ / "execution" / "*.py"))
                         if not Path(p).name.startswith("test_")])
    problemas = []
    if c.get("directivas") != esperado_directivas:
        problemas.append(f"directivas: informe {c.get('directivas')} vs disco {esperado_directivas}")
    if c.get("scripts_ejecucion") != esperado_ejec:
        problemas.append(f"scripts: informe {c.get('scripts_ejecucion')} vs disco {esperado_ejec}")
    return problemas


# ─────────────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="Genera y verifica el material de la conferencia.")
    ap.add_argument("--salida-dir", default="docs/AGENTE_IA")
    ap.add_argument("--autor", default="ELECTRONICA")
    ap.add_argument("--titulo", default=None)
    ap.add_argument("--fecha", default="2026-10-05")
    ap.add_argument("--minutos", type=int, default=30)
    ap.add_argument("--verificar-cifras", action="store_true",
                    help="Solo reejecuta los tests y comprueba las cifras; no genera.")
    args = ap.parse_args()

    if not args.titulo:
        args.titulo = "IA en ingeniería con un esquema determinista de tres capas"

    total = 1 if args.verificar_cifras else 4
    run_id = RS.nueva_run_id("charlada")
    estado = {"run_id": run_id, "pasos": [], "minutos": args.minutos}

    if args.verificar_cifras:
        paso(1, 1, "Verificación de cifras")
        bien, notas = verificar_cifras()
        if not bien:
            for n in notas:
                fallo(n)
            avisar("error")
            return 1
        avisar("success")
        return 0

    # ── Paso 1: delegar en la capa 3 ──────────────────────────────────────────
    paso(1, total, "Delegar la generación en la capa 3")
    cmd = [PYTHON, str(GENERADOR), "--salida-dir", args.salida_dir,
           "--autor", args.autor, "--titulo", args.titulo,
           "--fecha", args.fecha, "--minutos", str(args.minutos)]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(RAIZ))
    if res.returncode != 0:
        fallo(f"la capa 3 salió con código {res.returncode}")
        for linea in (res.stderr or "").strip().splitlines()[-12:]:
            print(f"           {linea}")
        avisar("error")
        return 3
    estado["pasos"].append({"paso": 1, "script": GENERADOR.name, "codigo": 0})
    ok(f"capa 3 generó el material (código {res.returncode})")

    # ── Paso 2: la compilación la decides por el log ─────────────────────────
    if not INFORME.exists():
        fallo(f"la capa 3 no dejó informe en {INFORME}")
        avisar("error")
        return 3
    informe = json.loads(INFORME.read_text(encoding="utf-8"))
    piezas = informe.get("piezas") or {}
    if not piezas:
        fallo("el informe no contiene ninguna pieza")
        avisar("error")
        return 3

    paso(2, total, "Verificar la compilación por el log (no por la existencia del PDF)")
    sucias = []
    for nombre, info in piezas.items():
        if info.get("limpio"):
            ok(f"{nombre}: log sin errores")
        else:
            sucias.append(nombre)
            fallo(f"{nombre}: {len(info.get('errores', []))} error(es) en el log")
            for e in (info.get("errores") or [])[:5]:
                print(f"           ! {e}")
    if sucias:
        fallo(f"compilación sucia en {sucias}: NO se publica nada")
        avisar("error")
        return 3
    estado["pasos"].append({"paso": 2, "verificacion": "logs limpios", "codigo": 0})

    # ── Paso 3: cifras reproducibles ─────────────────────────────────────────
    paso(3, total, "Verificar que las cifras del material son reproducibles")
    descuadres = comparar_cifras(informe)
    if descuadres:
        for d in descuadres:
            fallo(f"descuadre: {d}")
        avisar("error")
        return 1
    ok("las cifras del informe coinciden con el disco")
    c = informe.get("cifras", {})
    print(f"           {c.get('directivas')} directivas · {c.get('scripts_ejecucion')} scripts "
          f"· {c.get('fronteras_llm')} fronteras LLM · {c.get('pct_determinista')}% determinista")
    estado["pasos"].append({"paso": 3, "verificacion": "cifras coinciden", "codigo": 0})

    # ── Paso 4: publicar ──────────────────────────────────────────────────────
    paso(4, total, "Publicar el material (PDF y su fuente) en la carpeta de entrega")
    destino = Path(args.salida_dir)
    if not destino.is_absolute():
        destino = RAIZ / destino
    destino.mkdir(parents=True, exist_ok=True)
    publicados = []
    for nombre, info in piezas.items():
        # El .tex NO es un intermedio que se pueda descartar en .tmp/: es la
        # fuente del PDF que se entrega. Todos los entregables LaTeX del repo
        # versionan su fuente, y un PDF sin ella no se puede regenerar ni
        # revisar, que es justo lo que hace inutilizable la auditoría
        # pdf_stale (recorre los .tex, asi que un PDF huerfano le es
        # invisible). Se publican los dos o no se publica nada.
        for sufijo in (".pdf", ".tex"):
            origen = Path(info["pdf"]).with_suffix(sufijo)
            if not origen.exists():
                fallo(f"{nombre}: falta {sufijo} de origen ({origen}); "
                      "un entregable sin fuente no es publicable")
                avisar("error")
                return 3
            final = destino / origen.name
            shutil.copy2(origen, final)
            publicados.append(final.name)
            ok(f"{final.relative_to(RAIZ)}")
    estado["pasos"].append({"paso": 4, "publicados": publicados, "codigo": 0})

    # escribir_vista ya tolera ruta=None: un andamio que no se puede escribir
    # no puede tumbar el flujo.
    RS.escribir_vista(RS.ruta_vista(run_id), estado)
    avisar("success")
    print(f"\nListo: {len(publicados)} archivos en {destino.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())