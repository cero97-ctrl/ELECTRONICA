#!/usr/bin/env python3
"""Pruebas de regresion de la dimension `entornos` y de `bytes_exclusivos`.

Cuatro objetivos, y el tercero es el que mas suele fallar en silencio:

1. `bytes_exclusivos` en sus bordes exactos. Un hardlink NO son bloques
   recuperables y un directorio SI lo es, aunque `st_nlink` de un directorio
   valga 2 o mas porque ese numero cuenta subdirectorios. Los dos casos se
   contrapone aqui porque se anulan entre si: si solo se probara el fichero
   compartido, una implementacion que se olvidara de la excepcion de
   directorios pasaria los tests y perderia los bloques de directorio en un
   arbol con 200k entradas.

2. Los ANCLAJES de referencia. Un entorno se busca como lo que es (algo que un
   script le dice a conda), no como palabra. `IA` con `grep -w` da 226 lineas
   en este workspace y ninguna es una activacion de entorno. Y el fallo
   inverso tambien se prueba: si el anclaje seAnchor a demasiado, el detector
   de referencias no puede distinguir "lo nombran" de "lo nombran de verdad".

3. LA CAPA 3 NO DECIDE. `clasificar` devuelve hechos y `construir_resultado`
   decide. Se comprueba que `clasificar` no mete una clave `estado` y jamas, y
   que las funciones puras se testean sin reloj, sin disco y sin conda.

4. El CONTRATO DE SALIDA. `no_verificado` cuando algo no se pudo medir (y
   nunca `fallo` por un entorno frio: un entorno que ocupa espacio no es un
   defecto, es una decision del operador), y codigo 3 para uso incorrecto.

Este archivo existe porque la primera version de `buscar_referencias` usaba
`grep -l`, que imprime solo el nombre del fichero, y luego intentaba atribuir
cada coincidencia a un entorno leyendo la linea que nunca estuvo ahi. La
funcion devolvia SIEMPRE vacio, sin error y sin nota: indistinguible de un
"no hay nada que limpiar". Un detector de referencias que nunca se dispara
solo se encuentra con un control positivo, y por eso el punto 2 trae tres.

Ejecutar: python3 execution/test_auditar_entornos.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
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


def _cargar(fichero: str, nombre_modulo: str):
    spec = importlib.util.spec_from_file_location(nombre_modulo, RAIZ / fichero)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nombre_modulo] = mod
    spec.loader.exec_module(mod)
    return mod


sys.path.insert(0, str(RAIZ / "execution"))
AEC = _cargar("execution/auditar_envs_conda.py", "auditar_envs_conda")
CAT = _cargar("execution/catalogo_disco.py", "catalogo_disco_para_test")
ALG = _cargar("execution/veredicto_algebra.py", "veredicto_algebra_para_test")


# ---------------------------------------------------------------------------
# 1. bytes_exclusivos en sus bordes
# ---------------------------------------------------------------------------

def probar_bytes_exclusivos() -> None:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        a, b = base / "a", base / "b"
        a.mkdir()
        b.mkdir()

        # fichero con bloques propios
        (a / "solo.txt").write_text("x" * 8192)
        exclusivo_a, _ = CAT.bytes_exclusivos(a)
        comprobar("fichero con bloques propios SI se cuenta", exclusivo_a > 0,
                  f"devolvio {exclusivo_a}")

        # el MISMO inodo enlazado en dos sitios: no se puede recuperar borrando uno
        (a / "compartido.txt").write_text("y" * 8192)
        os.link(a / "compartido.txt", b / "compartido.txt")
        con_compartido, _ = CAT.bytes_exclusivos(a)
        comprobar("fichero hardlinkado NO se cuenta como exclusivo",
                  con_compartido == exclusivo_a,
                  f"con={con_compartido} sin={exclusivo_a}")

        # al desaparecer el otro enlace, pasa a ser exclusivo
        (b / "compartido.txt").unlink()
        tras_unlink, _ = CAT.bytes_exclusivos(a)
        comprobar("al soltar el segundo enlace SI se cuenta",
                  tras_unlink > con_compartido,
                  f"{tras_unlink} vs {con_compartido}")

        # directorio: nunca se hardlinkea, sus bloques son suyos
        solo_dir = base / "solo_dir"
        (solo_dir / "sub" / "hondo").mkdir(parents=True)
        bytes_dir, entradas_dir = CAT.bytes_exclusivos(solo_dir)
        comprobar("directorios SI se cuentan pese a st_nlink >= 2",
                  bytes_dir > 0, f"devolvio {bytes_dir}")
        comprobar("recorre directorios anidados", entradas_dir >= 2,
                  f"entradas={entradas_dir}")

        # symlink: no se sigue, para no medir dos veces el mismo destino
        (solo_dir / "enlace").symlink_to(a / "solo.txt")
        con_enlace, _ = CAT.bytes_exclusivos(solo_dir)
        comprobar("symlink no se sigue", con_enlace == bytes_dir,
                  f"{con_enlace} vs {bytes_dir}")

        # ruta inexistente: 0, no excepcion
        comprobar("ruta inexistente devuelve 0",
                  CAT.bytes_exclusivos(base / "no_existe") == (0, 0))

        # simlink a directorio: se ignora por completo
        enlace_dir = base / "enlace_dir"
        enlace_dir.symlink_to(solo_dir)
        comprobar("symlink a directorio se ignora",
                  CAT.bytes_exclusivos(enlace_dir) == (0, 0))

        # nunca mas que el tamano asignado que ya conoce el catalogo
        exclusivo_a2 = CAT.bytes_exclusivos(a)[0]
        asignado_a2 = CAT.tamano(a)[1]
        comprobar("exclusivo <= asignado (nunca inventa espacio)",
                  exclusivo_a2 <= asignado_a2, f"{exclusivo_a2} > {asignado_a2}")


# ---------------------------------------------------------------------------
# 2. anclajes de referencia, con control positivo y negativo
# ---------------------------------------------------------------------------

def probar_patrones() -> None:
    rx = lambda n: AEC._patrones_referencia([n])  # noqa: E731

    import re
    compila = lambda n: re.compile(rx(n))  # noqa: E731

    # Cada linea se prueba contra el entorno que REALMENTE nombra. Probar la
    # linea de `cyber_env` contra el patron de `pcb_env` daria un fallo que
    # parece del detector y no lo es.
    casos = [
        ("pcb_env", "conda activate pcb_env"),
        ("pcb_env", 'conda activate "pcb_env"'),
        ("cyber_env", "/home/cero/anaconda3/envs/cyber_env/bin/python3.11"),
        ("pcb_env", 'ENV_NAME="pcb_env"'),
        ("pcb_env", "conda create -n pcb_env python=3.10 -y"),
        ("pcb_env", "conda create --name pcb_env python=3.10 -y"),
        ("agent_env", "conda env export -n agent_env > x.yml"),
        ("agent_env", "conda env remove -n agent_env"),
        ("pcb_env", 'python.defaultInterpreterPath": ".../envs/pcb_env/bin/python"'),
    ]
    for nombre, linea in casos:
        comprobar(f"anclaje casa ({nombre}): {linea[:40]!r}",
                  compila(nombre).search(linea) is not None)

    # lo que NO debe casar: la palabra suelta
    for linea in [
        "Entrenamiento de IA -> SIEMPRE en Google Colab",
        "un asistente IA con arquitectura de 3 capas",
        "la IA que integracion es esta",
    ]:
        comprobar(f"NO casa con la palabra suelta: {linea[:36]!r}",
                  compila("IA").search(linea) is None)

    # el mismo prefijo no puede referencias OTRO entorno
    comprobar("pcb_env no casa con pcb_env_312 como si fuera el mismo",
              compila("pcb_env_312").search("conda activate pcb_env") is None)
    comprobar("pcb_env_312 SI casa con su propia activacion",
              compila("pcb_env_312").search("conda activate pcb_env_312") is not None)

    # y el nombre mas corto no puede ser prefijo del largo al reves
    comprobar("IA no casa con 'conda activate IA_EXTRA'",
              compila("IA").search("conda activate IA_EXTRA") is None)


def probar_referencias_fichero_real() -> None:
    """Control positivo sobre el workspace real: sin el, el punto 2 es teatro."""
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        (ws / "setup.sh").write_text('ENV_NAME="entorno_fantasma"\n')
        (ws / "notas.md").write_text("hablamos de IA y de pcb_env en general\n")
        (ws / "binario.bin").write_bytes(b"\x00\x01ENV_NAME=x\x00")
        (ws / "node_modules").mkdir()
        (ws / "node_modules" / "setup.js").write_text('ENV_NAME="entorno_fantasma"\n')

        res, nota = AEC.buscar_referencias(ws, ["entorno_fantasma"], 60)
        comprobar("control POSITIVO: encuentra el ENV_NAME real",
                  "entorno_fantasma" in res, f"res={res} nota={nota}")
        comprobar("control POSITIVO: la ruta es relativa al workspace",
                  any(r == "setup.sh" for r in res.get("entorno_fantasma", [])),
                  f"res={res}")

        res_ruido, _ = AEC.buscar_referencias(ws, ["pcb_env"], 60)
        comprobar("control NEGATIVO: la palabra suelta no es referencia",
                  "pcb_env" not in res_ruido, f"res={res_ruido}")

        res_ignorado, _ = AEC.buscar_referencias(ws, ["entorno_fantasma"], 60)
        comprobar("node_modules queda excluido", len(res_ignorado.get("entorno_fantasma", [])) == 1,
                  f"res={res_ignorado}")

        # ruta con dos puntos en el nombre: el numero de linea debe caer
        (ws / "con:dos:puntos.sh").write_text('ENV_NAME="entorno_fantasma"\n')
        res_colon, _ = AEC.buscar_referencias(ws, ["entorno_fantasma"], 60)
        comprobar("una ruta con ':' no se parte mal", "con:dos:puntos.sh" in res_colon.get("entorno_fantasma", []),
                  f"res={res_colon}")

        # workspace inexistente: nota, no excepcion
        res_nada, nota_nada = AEC.buscar_referencias(Path(td) / "no_existe", ["x"], 60)
        comprobar("workspace inexistente devuelve nota, no crash",
                  nota_nada != "" and res_nada == {}, f"nota={nota_nada!r}")


# ---------------------------------------------------------------------------
# 3. la capa 3 no decide
# ---------------------------------------------------------------------------

def probar_descubrimiento() -> None:
    with tempfile.TemporaryDirectory() as td:
        raiz = Path(td)
        (raiz / "bueno" / "conda-meta").mkdir(parents=True)
        (raiz / "bueno" / "conda-meta" / "history").write_text("historial\n")
        (raiz / "carpeta_sin_meta").mkdir()

        dirs, motivo = AEC.descubrir_entornos(raiz)
        nombres = sorted(d.name for d in dirs)
        comprobar("solo cuenta los que tienen conda-meta/history",
                  nombres == ["bueno"], f"encontrados={nombres}")
        comprobar("sin motivo de fallo cuando si hay entornos", motivo is None, f"motivo={motivo}")

        _, motivo_vacio = AEC.descubrir_entornos(raiz / "no_existe")
        comprobar("raiz inexistente da motivo", motivo_vacio is not None)

        vacio = raiz / "vacio"
        vacio.mkdir()
        _, motivo_vacio2 = AEC.descubrir_entornos(vacio)
        comprobar("directorio sin entornos da motivo, no lista vacia silenciosa",
                  motivo_vacio2 is not None, f"motivo={motivo_vacio2}")


def probar_umbral_dias() -> None:
    """`clasificar` no lleva clave `estado`: la medicion no decide el veredicto."""
    import inspect
    fuente = inspect.getsource(AEC.clasificar)
    comprobar("clasificar no devuelve una clave 'estado'", '"estado"' not in fuente)
    comprobar("construir_resultado es donde nace 'estado'",
              '"estado"' in inspect.getsource(AEC.construir_resultado))

    # El borde del umbral: un .pyc justo dentro y otro fuera. El reloj es el
    # REAL, no uno inyectado: `clasificar` no recibe `ahora` a proposito (su
    # firma no tiene donde meterlo), asi que un tiempo de test inventado
    # mediria un fichero de 2023 contra un presente de 2026 y daria "frio" a
    # un entorno que se acaba de ejecutar. Si algum dia se le anade un
    # `ahora` inyectable, este test pasa a valer la mitad.
    import time
    with tempfile.TemporaryDirectory() as td:
        raiz = Path(td)
        for nombre in ("dentro", "fuera"):
            (raiz / nombre / "conda-meta").mkdir(parents=True)
            (raiz / nombre / "conda-meta" / "history").write_text("h\n")
            (raiz / nombre / "mod.pyc").write_bytes(b"\x00")
        ahora = time.time()
        viejo = ahora - 100 * 86400          # 100 dias: fuera de una ventana de 90
        os.utime(raiz / "dentro" / "mod.pyc", (ahora - 10 * 86400, ahora - 10 * 86400))
        os.utime(raiz / "fuera" / "mod.pyc", (viejo, viejo))

        res = AEC.clasificar(raiz, raiz / "ws_inexistente", 90, (), False, 60)
        filas = {f["entorno"]: f for f in res["entornos"]}
        comprobar("un .pyc de hace 10 dias = ejecutado en ventana",
                  filas.get("dentro", {}).get("ejecutado_en_ventana") is True,
                  f"{filas.get('dentro')}")
        comprobar("un .pyc de hace 100 dias = fuera de la ventana",
                  filas.get("fuera", {}).get("ejecutado_en_ventana") is False,
                  f"{filas.get('fuera')}")

        # El borde, por los DOS lados y con margen. El corte es
        # `find -newermt @(ahora - 90d)`, o sea un `>` estricto: la ventana es
        # "estrictamente mas reciente que hace 90 dias". Un fichero con la
        # marca de tiempo exactamente en el corte cae fuera, y no es un fallo:
        # el instante exacto no ocurre nunca con reloj real, y decidir `>=` o
        # `>` es una eleccion que se escribe aqui, no una que se hereda sola.
        for nombre, dias, esperado in [("borde_dentro", 89.9, True),
                                       ("borde_fuera", 90.1, False)]:
            (raiz / nombre / "conda-meta").mkdir(parents=True)
            (raiz / nombre / "conda-meta" / "history").write_text("h\n")
            (raiz / nombre / "e.pyc").write_bytes(b"\x00")
            marca = ahora - dias * 86400
            os.utime(raiz / nombre / "e.pyc", (marca, marca))
            r = AEC.clasificar(raiz, raiz / "ws_inexistente", 90, (), False, 60)
            fila = {f["entorno"]: f for f in r["entornos"]}.get(nombre, {})
            comprobar(f"borde a {dias} dias -> {esperado}",
                      fila.get("ejecutado_en_ventana") is esperado,
                      f"{fila}")

        # sin ningun .pyc = nunca ejecutado en la ventana
        solo_meta = raiz / "solo_meta"
        (solo_meta / "conda-meta").mkdir(parents=True)
        (solo_meta / "conda-meta" / "history").write_text("h\n")
        res_s = AEC.clasificar(raiz, raiz / "ws_inexistente", 90, (), False, 60)
        filas_s = {f["entorno"]: f for f in res_s["entornos"]}
        comprobar("sin .pyc = fuera de la ventana",
                  filas_s.get("solo_meta", {}).get("ejecutado_en_ventana") is False,
                  f"{filas_s.get('solo_meta')}")
        comprobar("sin .pyc no inventa una fecha",
                  filas_s.get("solo_meta", {}).get("ultimo_pyc") is None,
                  f"{filas_s.get('solo_meta')}")


# ---------------------------------------------------------------------------
# 4. veredicto y contrato de salida
# ---------------------------------------------------------------------------

def _fila(nombre: str, clase_esperada: str, ejec: bool, bytes_: int = 1000,
          refs: list[str] | None = None) -> dict:
    return {
        "entorno": nombre, "clase": clase_esperada, "ejecutado_en_ventana": ejec,
        "bytes_exclusivos": bytes_, "bytes_aparentes": bytes_, "entradas": 3,
        "referencias": refs or [], "ultimo_pyc": "2026-01-01",
    }


def probar_veredicto() -> None:
    # 1. hay frios -> aviso (nunca fallo: ocupa espacio no es un defecto)
    r = AEC.construir_resultado({"entornos": [
        _fila("a", "frio", False, 500), _fila("b", "en_uso", True),
    ], "nota_refs": ""}, 90)
    comprobar("frio -> aviso", r["estado"] == "aviso", f"estado={r['estado']}")
    comprobar("frio nunca es fallo", r["estado"] != "fallo")
    comprobar("el resumen cuenta los frios", "1 de 2" in r["resumen"], r["resumen"])
    comprobar("recuperable suma solo los frios",
              r["evidencia"]["recuperable_bytes_exclusivos"] == 500,
              f"{r['evidencia']['recuperable_bytes_exclusivos']}")

    # 2. sin frios -> ok
    r = AEC.construir_resultado({"entornos": [
        _fila("a", "en_uso", True), _fila("b", "protegido", False),
    ], "nota_refs": ""}, 90)
    comprobar("sin frios -> ok", r["estado"] == "ok", f"estado={r['estado']}")

    # 3. no medido -> no_verificado, y NUNCA ok
    r = AEC.construir_resultado({"no_verificado": "find devolvio 2", "entornos": []}, 90)
    comprobar("no medido -> no_verificado", r["estado"] == "no_verificado")
    comprobar("no medido impide el verde", r["estado"] != "ok")
    comprobar("no medido no es un fallo (no hay defecto, falta dato)",
              r["estado"] != "fallo")

    # 4. la politica gana a la medicion: un frio protegido no es opportunity
    r = AEC.construir_resultado({"entornos": [_fila("IA", "protegido", False, 1480)],
                                 "nota_refs": ""}, 90)
    comprobar("protegido no cuenta como recuperable",
              r["evidencia"]["recuperable_bytes_exclusivos"] == 0,
              f"{r['evidencia']['recuperable_bytes_exclusivos']}")
    comprobar("protegido sigue listado en el reparto",
              r["evidencia"]["reparto"]["protegido"] == ["IA"])

    # 5. un frio REFERENCIADO no se recomienda para borrar
    r = AEC.construir_resultado({"entornos": [
        _fila("z", "referenciado", False, 900, ["otro/setup.sh"])], "nota_refs": ""}, 90)
    comprobar("referenciado no se ofrece para borrar",
              r["evidencia"]["reparto"]["frio"] == [],
              f"{r['evidencia']['reparto']}")

    # 6. el estado es valido segun la algebra compartida
    validos = {d["estado"] for d in [r]}
    comprobar("estados que la algebra acepta",
              all(ALG.estado_valido(e) for e in validos), f"{validos}")

    # 7. proteger un entorno NO puede convertirlo en "no hay entornos frios".
    #    Este es el caso de bio_env: frio desde 2026-06-25, 0,37 GB, con su
    #    proyecto (BIOANALISIS) vivo. Al meterlo en PROTEGIDOS_POR_POLITICA deja
    #    de ser recuperable, que es lo correcto, pero sigue siendo un entorno sin
    #    ejecucion que ocupa disco. Un resumen que lo borre de la lectura diria
    #    que el espacio desaparecio cuando sigue ahi.
    r = AEC.construir_resultado({"entornos": [
        _fila("a", "en_uso", True), _fila("bio_env", "protegido", False, 368),
    ], "nota_refs": ""}, 90)
    comprobar("protegido y frio NO es recuperable",
              r["evidencia"]["recuperable_bytes_exclusivos"] == 0)
    comprobar("protegido y frio sigue informado, no borrado de la lectura",
              len(r["evidencia"]["frios_conservados"]) == 1
              and r["evidencia"]["frios_conservados"][0]["entorno"] == "bio_env",
              f"{r['evidencia']['frios_conservados']}")
    comprobar("el resumen nombra los frios conservados",
              "conservados a proposito" in r["resumen"], r["resumen"])
    comprobar("el resumen NO afirma que no hay frios",
              "no hay entornos frios" not in r["resumen"].lower(), r["resumen"])
    comprobar("la accion NO ofrece borrar conservados",
              "no borrarlo" not in r["accion"] and "recuperable" in r["accion"],
              r["accion"])
    comprobar("peso de los conservados visible en el resumen",
              "0.00 GB" in r["resumen"], r["resumen"])

    # 8. sin frios y sin conservados -> si, aqui si se puede decir que no hay
    #    frios, porque no hay ninguno. Distinguir este caso del anterior es
    #    justo lo que evita que el mensaje "no hay frios" sea una mentira.
    r = AEC.construir_resultado({"entornos": [
        _fila("a", "en_uso", True), _fila("b", "en_uso", True),
    ], "nota_refs": ""}, 90)
    comprobar("todos en uso -> el si afirma que no hay frios",
              r["resumen"] == "los 2 entornos estan en uso", r["resumen"])
    comprobar("todos en uso -> sin conservados que informar",
              r["evidencia"]["frios_conservados"] == [])

    # 9. un referenciado tambien es un frio conservado: son dimensiones
    #    distintas (el porque se conserva), no una categoria aparte de "frio".
    r = AEC.construir_resultado({"entornos": [
        _fila("z", "referenciado", False, 900, ["otro/setup.sh"])], "nota_refs": ""}, 90)
    comprobar("referenciado cuenta como frio conservado, no como recuperable",
              len(r["evidencia"]["frios_conservados"]) == 1
              and r["evidencia"]["recuperable_bytes_exclusivos"] == 0)
    comprobar("el motivo del referenciado se explica",
              "script" in r["evidencia"]["frios_conservados"][0]["motivo"],
              r["evidencia"]["frios_conservados"][0]["motivo"])


def probar_politica_congelada() -> None:
    # 10. La lista de protegidos es una DECISION del operador, no un hecho que
    #     la medicion deduzca. Se congela en test a proposito: cambiarla es
    #     cambiar politica (anadir bio_env por su proyecto BIOANALISIS vivo), y
    #     un cambio debe tenerse que romper el test a proposito, no colarse.
    comprobar("elect_env protegido (lo fija el plugin de opencode)",
              "elect_env" in AEC.PROTEGIDOS_POR_POLITICA)
    comprobar("IA protegido (unico TensorFlow funcional)",
              "IA" in AEC.PROTEGIDOS_POR_POLITICA)
    comprobar("bio_env protegido (proyecto BIOANALISIS vivo, entorno inactivo)",
              "bio_env" in AEC.PROTEGIDOS_POR_POLITICA,
              f"protegidos={AEC.PROTEGIDOS_POR_POLITICA}")
    comprobar("la politica no crece sola: 3 entradas, sin duplicados",
              len(AEC.PROTEGIDOS_POR_POLITICA) == 3
              and len(set(AEC.PROTEGIDOS_POR_POLITICA)) == 3,
              f"protegidos={AEC.PROTEGIDOS_POR_POLITICA}")
    # La politica se publica en la evidencia: una excepcion que no se ve es una
    # excepcion que el proximo no puede ni cuestionar.
    r = AEC.construir_resultado({"entornos": [_fila("a", "en_uso", True)],
                                 "nota_refs": ""}, 90)
    comprobar("la evidencia publica la lista de protegidos",
              r["evidencia"]["criterio"]["protegidos_por_politica"]
              == list(AEC.PROTEGIDOS_POR_POLITICA))


def probar_contrato_cli() -> None:
    py = sys.executable
    script = str(RAIZ / "execution" / "auditar_envs_conda.py")

    p = subprocess.run([py, script, "--dias", "0"], capture_output=True, text=True)
    comprobar("--dias 0 -> codigo 3 (uso incorrecto, no 'no medido')",
              p.returncode == 3, f"rc={p.returncode}")

    p = subprocess.run([py, script, "--timeout", "0"], capture_output=True, text=True)
    comprobar("--timeout 0 -> codigo 3", p.returncode == 3, f"rc={p.returncode}")

    p = subprocess.run([py, script, "--flag-que-no-existe"],
                       capture_output=True, text=True)
    comprobar("flag inexistente -> codigo 3, no 2", p.returncode == 3, f"rc={p.returncode}")

    p = subprocess.run([py, script, "--envs-root", "/no/existe/ni/caso",
                        "--json"], capture_output=True, text=True)
    comprobar("raiz de entornos inexistente -> no_verificado, no crash",
              p.returncode == 0 and '"no_verificado"' in p.stdout,
              f"rc={p.returncode} out={p.stdout[:160]}")


def main() -> int:
    print("== bytes_exclusivos: bloques recuperables, no tamano aparente ==")
    probar_bytes_exclusivos()
    print("== anclajes de referencia: con control positivo y negativo ==")
    probar_patrones()
    probar_referencias_fichero_real()
    print("== descubrimiento y umbral de dias ==")
    probar_descubrimiento()
    probar_umbral_dias()
    print("== veredicto: la politica gana a la medicion ==")
    probar_veredicto()
    probar_politica_congelada()
    print("== contrato de salida ==")
    probar_contrato_cli()

    print()
    print(f"{PRUEBAS} aserciones, {len(FALLOS)} fallo(s)")
    if FALLOS:
        for f in FALLOS:
            print(f"  - {f}")
        return 1
    print("  todas las aserciones pasan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
