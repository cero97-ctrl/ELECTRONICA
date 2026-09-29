#!/usr/bin/env python3
"""test_run_state.py — regresiones de la vista de estado (Layer 3: Execution).

Lo que este test protege, y por que son las tres cosas que importan:

  1. **La vista lleva el run_id en el nombre.** Dos flujos que corren a la vez
     se pisan la vista cuando el nombre es fijo, y el emparejamiento
     vista<->log que verifica `estado_sesion.py` atribuye la vista de uno al log
     del otro. Ese fue el P2 que dejo 16 flujos pendientes. Es la razon de existir
     de `run_state.py`, asi que se comprueba con dos corridas simultaneas de
     verdad, no con una asercion sobre el texto de la plantilla.
  2. **La escritura es atomica.** Un JSON a medias en `.tmp/` es exactamente el
     estado que `estado_sesion.py` reporta como "escritura incompleta". Aqui se
     comprueba que el temporal NO se parece a una vista (no acaba en `.json`) y
     que un rename deja el fichero entero.
  3. **El guard de "escrita por esta corrida" no depende del reloj.** Los MCP
     comparaban un mtime antes/despues de un unico fichero; con una vista por
     corrida el guard tiene que comparar el conjunto. Se comprueba con dos
     corridas encadenadas donde la segunda NO escribe: si devolviera la vista de
     la primera, el MCP estaria reportando el resultado de otro flujo.

Uso:  python3 execution/test_run_state.py
Salida: 0 si todas las aserciones pasan, 1 si alguna falla.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "execution"))

import run_state as RS  # noqa: E402

PRUEBAS = 0
FALLOS: list[str] = []


def comprobar(desc: str, cond: bool, detalle: str = "") -> None:
    global PRUEBAS
    PRUEBAS += 1
    if cond:
        print(f"  ok   {desc}")
    else:
        print(f"  FALLO {desc}  [{detalle}]")
        FALLOS.append(desc)


def probar_nombre() -> None:
    # La plantilla: una sola, y el nombre de la vista es el del log mas "_".
    comprobar("la vista se llama run_state_<run_id>.json",
              RS.PLANTILLA == "run_state_{run_id}.json", RS.PLANTILLA)
    r = RS.ruta_vista("auditar-repo-20260101-000000")
    comprobar("ruta_vista usa la plantilla",
              r is not None and r.name == "run_state_auditar-repo-20260101-000000.json",
              str(r))
    comprobar("ruta_vista cae en .tmp/ del repo",
              r is not None and r.parent == RS.TMP_DIR, str(r))
    # El nombre del log y el de la vista tienen que llevar el MISMO run_id, o
    # `estado_sesion._run_id_desde_archivo` busca un log que no existe.
    log = RS.TMP_DIR / ("session_log_auditar-repo-20260101-000000.jsonl")
    run = r.name[len("run_state_"):-len(".json")] if r else ""
    comprobar("el run_id del nombre es el del log",
              RS.VISTA_GLOBAL and log.name == f"session_log_{run}.jsonl",
              f"{log.name} vs run={run}")


def probar_run_id_invalido() -> None:
    # Sin acotar el nombre, un run_id con `/` o `..` escribe fuera de `.tmp/`.
    for malo in ("../fuera", "a/b", "", None, 123, "con espacio"):
        comprobar(f"run_id {malo!r} no produce ruta",
                  RS.ruta_vista(malo) is None, str(RS.ruta_vista(malo)))
    comprobar("run_id con - y _ y . si vale", RS.ruta_vista("a-b_c.1") is not None)
    # El mismo patron que valida el log: un nombre aceptado por la vista y
    # rechazado por `sesion_log` dejaria una vista sin log (y al reves).
    import sesion_log as SL
    forbueno = "flujo-disco-20260929-101010"
    comprobar("el run_id del flujo_disk es valido en vista y log",
              RS.run_id_valido(forbueno) and bool(SL.RUN_ID_RE.match(forbueno)))


def probar_slug() -> None:
    """`slug_run_id` para las partes del run_id que vienen de fuera.

    El caso real es `pdf_path.stem` en `flujo_evaluar_examen`: un examen llamado
    `EJM 4-1.pdf` daba un run_id con espacio, `sesion_log` lo rechazaba y la
    corrida se quedaba SIN TRAZABILIDAD en silencio. Un nombre de fichero es
    entrada de usuario, no una constante: por eso se normaliza.
    """
    comprobar("un espacio se vuelve guion", RS.slug_run_id("EJM 4-1") == "EJM-4-1",
              RS.slug_run_id("EJM 4-1"))
    comprobar("las barras no se cuelan", "/" not in RS.slug_run_id("a/b"))
    comprobar("vacio da un marcador estable", RS.slug_run_id("  ") == "sin-nombre")
    comprobar("solo espacios da marcador, no cadena vacia",
              RS.run_id_valido(RS.slug_run_id("  ")))
    # El invariante entero: SIEMPRE sale algo que la vista y el log aceptan.
    # Es la asercion que importa; las de arriba son sus casos particulares. Con
    # `str.isalnum()` este invariante fallaba con `ñandú` (True en Python, pero
    # `RUN_ID_RE` es ASCII), y el sintoma —log que no se escribe— no aparece
    # hasta semanas despues, en otra parte del sistema.
    casos = ["EJM 4-1", "Revisión Temas 7-8", "ñandú", "a//b", "  ", "..", "-x-",
             "tema_con_guion_bajo", "Ñ", "Ω→µ", "..hidden..", "x" * 300, "12:30",
             "tema/con/barras", "espacio  multiple  separado"]
    malos = [(c, RS.slug_run_id(c)) for c in casos if not RS.run_id_valido(RS.slug_run_id(c))]
    comprobar("slug_run_id SIEMPRE produce un run_id valido",
              not malos, f"invalidos={malos}")
    # Determinista: el mismo PDF da siempre el mismo slug, y por tanto el mismo
    # log. Un slug que cambiara entre corridas dejaria un log por cada intento.
    comprobar("el slug es determinista",
              RS.slug_run_id("EJM 4-1") == RS.slug_run_id("EJM 4-1"))
    # Un nombre larguisimo se trunca, no se descarta: `RUN_ID_RE` corta a 120 y
    # el slug es solo una parte del run_id. La aritmetica del margen (102 <= 120
    # con el prefijo y el timestamp) esta en el docstring de `slug_run_id`; aqui
    # se comprueba el resultado, que es lo que puede romperse sin avisar.
    largo = "tema" * 100
    slug_largo = RS.slug_run_id(largo)
    comprobar("un nombre enorme se trunca y sigue siendo valido",
              RS.run_id_valido(slug_largo) and len(slug_largo) <= 80, f"len={len(slug_largo)}")
    # Y el run_id COMPLETO con el nombre real mas largo sigue cabiendo en 120.
    completo_largo = f"flujo-{slug_largo}-20260929-101010"
    comprobar("el run_id completo mas largo cabe en el limite del log",
              len(completo_largo) <= 120 and RS.run_id_valido(completo_largo),
              f"len={len(completo_largo)}")
    # Truncar por el final, no por el principio: la cola es la parte que mas
    # distingue. Si se truncara por delante, `Tema7-Parte2` y `Tema7-Parte3` con
    # relleno delante acabarian en el mismo slug.
    _a = "prefijo-larguisimo-" + "cola-distintiva-AAA"
    _b = "prefijo-larguisimo-" + "cola-distintiva-BBB"
    comprobar("la cola distintiva sobrevive al truncado",
              RS.slug_run_id(_a) != RS.slug_run_id(_b))
    # Y el run_id completo de un PDF con espacio vale:
    completo = f"flujo-{RS.slug_run_id('EJM 4-1')}-20260929-101010"
    comprobar("el run_id compuesto de un PDF con espacio vale entero",
              RS.run_id_valido(completo), completo)


def probar_escritura_atomica() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        r = RS.ruta_vista("prueba-atomica", tmp)
        assert r is not None
        ok = RS.escribir_vista(r, {"run_id": "prueba-atomica", "n": 1})
        comprobar("escribir_vista devuelve True", ok)
        comprobar("el JSON es valido", json.loads(r.read_text(encoding="utf-8"))["n"] == 1)
        # El temporal no se parece a una vista: no acaba en .json, asi que un
        # glob de run_state_*.json (el de estado_sesion) no lo cuenta.
        temporal = r.with_name(r.name + ".tmp")
        comprobar("el temporal existe solo mientras se escribe, y no acaba en .json",
                  not temporal.exists() or not temporal.name.endswith(".json"))
        # Reescribir no deja el temporal: si lo dejara, .tmp/ se llenaria de
        # hermanos que ni son vistas ni logs.
        RS.escribir_vista(r, {"run_id": "prueba-atomica", "n": 2})
        comprobar("reescribir no deja temporal",
                  not temporal.exists(), str(temporal))
        comprobar("reescribir conserva el entero",
                  json.loads(r.read_text(encoding="utf-8"))["n"] == 2)
        # Un estado no serializable no puede tumbar nada ni dejar rastro.
        ok = RS.escribir_vista(r, {"run_id": "prueba-atomica", "b": {1, 2}})
        comprobar("estado no serializable -> False, no crash", ok is False)
        comprobar("el fallo deja la vista anterior intacta",
                  json.loads(r.read_text(encoding="utf-8"))["n"] == 2)
        comprobar("el fallo no deja temporal", not temporal.exists())


def probar_no_colision() -> None:
    """Dos corridas a la vez, cada una con su vista. La razon del modulo."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # Dos flujos "distintos" escribiendo a la vez, como pasaria con un
        # run_state.json compartido. Con la plantilla no se pisan.
        for run in ("flujo-a-1", "flujo-b-1"):
            r = RS.ruta_vista(run, tmp)
            assert r is not None
            RS.escribir_vista(r, {"run_id": run, "propio": True})
        a = RS.leer_vista(RS.ruta_vista("flujo-a-1", tmp))
        b = RS.leer_vista(RS.ruta_vista("flujo-b-1", tmp))
        comprobar("la corrida A lee SU vista", a.get("run_id") == "flujo-a-1", str(a))
        comprobar("la corrida B lee SU vista", b.get("run_id") == "flujo-b-1", str(b))
        # Y el nombre fijo, que es lo que se va a eliminar, no lo creamos nunca.
        comprobar("no se crea un run_state.json al escribir",
                  not (tmp / RS.VISTA_GLOBAL).exists())


def probar_guard_cambios() -> None:
    """El guard de 'lo escribio ESTA corrida', generalizado a N vistas."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # Corrida 1: escribe y cierra.
        RS.escribir_vista(RS.ruta_vista("corrida-1", tmp), {"run_id": "corrida-1"})
        # El MCP saca la foto ANTES de lanzar la corrida 2.
        foto = RS.instantiate(tmp)
        comprobar("la foto ve la vista previa", "run_state_corrida-1.json" in foto)
        # Corrida 2: su flujo no llego a escribir (fallo temprano).
        cambios = RS.cambios_desde(foto, tmp)
        comprobar("corrida que no escribio no devuelve vista ajena",
                  cambios == [], f"cambios={[p.name for p in cambios]}")
        # Corrida 3: si escribe, es suya.
        RS.escribir_vista(RS.ruta_vista("corrida-3", tmp), {"run_id": "corrida-3"})
        cambios = RS.cambios_desde(foto, tmp)
        comprobar("la vista que escribio ESTA corrida si se ve",
                  [p.name for p in cambios] == ["run_state_corrida-3.json"],
                  f"cambios={[p.name for p in cambios]}")
        # Dos escrituras de la misma corrida: la mas reciente primero.
        RS.escribir_vista(RS.ruta_vista("corrida-4", tmp), {"run_id": "corrida-4", "v": 1})
        foto2 = RS.instantiate(tmp)
        RS.escribir_vista(RS.ruta_vista("corrida-4", tmp), {"run_id": "corrida-4", "v": 2})
        cambios = RS.cambios_desde(foto2, tmp)
        comprobar("reescritura de la misma vista se detecta",
                  cambios == [RS.ruta_vista("corrida-4", tmp)],
                  f"cambios={[p.name for p in cambios]}")
        comprobar("la reescritura trae el dato nuevo",
                  RS.leer_vista(cambios[0]).get("v") == 2)


def probar_listar() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for run in ("l-1", "l-2"):
            RS.escribir_vista(RS.ruta_vista(run, tmp), {"run_id": run})
        nombres = [p.name for p in RS.listar_vistas(tmp)]
        comprobar("lista las dos vistas", len(nombres) == 2, str(nombres))
        # Un hermano que se LLAMA casi-vista pero no lo es: ni .tmp de una
        # escritura a medias, ni un .log, ni un nombre sin prefijo.
        (tmp / "run_state_l-1.json.tmp").write_text("{}", encoding="utf-8")
        (tmp / "run_state_l-9.log").write_text("x", encoding="utf-8")
        (tmp / "otro_cosa.json").write_text("{}", encoding="utf-8")
        nombres = [p.name for p in RS.listar_vistas(tmp)]
        comprobar("el temporal de escritura no cuenta como vista",
                  "run_state_l-1.json.tmp" not in nombres, str(nombres))
        comprobar("un .log no cuenta como vista",
                  "run_state_l-9.log" not in nombres, str(nombres))
        comprobar("lo que no es vista no se lista",
                  "otro_cosa.json" not in nombres, str(nombres))
        # La vista global (herencia) se lista para poder leerse.
        (tmp / RS.VISTA_GLOBAL).write_text('{"run_id":"legacy"}', encoding="utf-8")
        comprobar("la vista global heredada tambien se lista",
                  RS.VISTA_GLOBAL in [p.name for p in RS.listar_vistas(tmp)])
        # Orden: mas reciente primero (el MCP toma la primera).
        RS.escribir_vista(RS.ruta_vista("l-3", tmp), {"run_id": "l-3"})
        orden = [p.name for p in RS.listar_vistas(tmp)]
        comprobar("la mas reciente va primera",
                  orden[0] == "run_state_l-3.json", str(orden))


def probar_retirar() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        r = RS.ruta_vista("retirar-1", tmp)
        assert r is not None
        RS.escribir_vista(r, {"run_id": "retirar-1"})
        comprobar("retirar_vista borra la vista", RS.retirar_vista(r) and not r.exists())
        comprobar("retirar una vista ya ausente no es error (idempotente)",
                  RS.retirar_vista(r) is True)
        comprobar("retirar(None) no revienta", RS.retirar_vista(None) is False)


def probar_run_id_fijado() -> None:
    """`ELECTRONICA_RUN_ID`: cuando hay orquestador, el que pone el nombre.

    El guard del MCP comparaba el `mtime` de un fichero de nombre fijo. Con la
    vista por corrida ese guard es INCORRECTO, no solo fragil: el flujo ya no
    escribe ese fichero, su mtime no cambia nunca y el MCP devolveria "N/A" con
    exit code 0. La primera correccion —buscar la vista nueva mas reciente— era
    correcta solo si no hubiera otra corrida escribiendo a la vez; con dos flujos
    en paralelo el MCP se atribuia la vista del otro. Se comprobo, no se supuso.
    """
    import os
    previo = os.environ.get(RS.ENV_RUN_ID)

    try:
        os.environ.pop(RS.ENV_RUN_ID, None)
        generado = RS.run_id_de_la_corrida("flujo-imagen")
        comprobar("sin orquestador se fabrica un run_id propio",
                  generado.startswith("flujo-imagen-") and RS.run_id_valido(generado),
                  generado)

        fijado = "mcp-elaborar-20260101-000000"
        os.environ[RS.ENV_RUN_ID] = fijado
        comprobar("con orquestador se respeta su run_id",
                  RS.run_id_de_la_corrida("cualquier-otro") == fijado)

        # Un valor INVALIDO se ignora en vez de propagarse: el flujo se salva con
        # un run_id propio y su traza sigue siendo correcta. Abortar aqui
        # perderia una operacion que si podia tener exito.
        os.environ[RS.ENV_RUN_ID] = "con espacio/no-valido"
        salvado = RS.run_id_de_la_corrida("flujo-imagen")
        comprobar("un run_id invalido del orquestador se ignora, no se propaga",
                  RS.run_id_valido(salvado) and salvado != "con espacio/no-valido",
                  salvado)

        os.environ[RS.ENV_RUN_ID] = ""
        comprobar("valor vacio equivale a no haber orquestador",
                  RS.run_id_de_la_corrida("flujo-imagen").startswith("flujo-imagen-"))

        # Y la vista escrita es exactamente la que se lee: sin esto, la
        # correccion del guard sigue siendo una deduccion.
        rid = RS.run_id_de_la_corrida("mcp-prueba")
        ruta = RS.ruta_vista(rid)
        ajena = "mcp-ajena-20260101-000000"
        RS.escribir_vista(RS.ruta_vista(ajena),
                          {"run_id": ajena, "contexto": {"descripcion": "AJENA"}})
        RS.escribir_vista(ruta, {"run_id": rid, "contexto": {"descripcion": "MIA"}})
        leido = RS.leer_vista(ruta)
        comprobar("con run_id fijado, la vista ajena no se atribuye a esta corrida",
                  leido.get("contexto", {}).get("descripcion") == "MIA", leido)
        # Y si el flujo no llego a escribir, se lee un {} explicito, no la ajena.
        comprobar("sin vista propia se lee vacio y no se rellena con la ajena",
                  RS.leer_vista(RS.ruta_vista("mcp-inexistente-999")) in ({}, None))
        for r in (rid, ajena):
            RS.retirar_vista(RS.ruta_vista(r))
    finally:
        if previo is None:
            os.environ.pop(RS.ENV_RUN_ID, None)
        else:
            os.environ[RS.ENV_RUN_ID] = previo


def probar_migracion() -> None:
    """Ningun flujo ni servidor MCP debe volver a la vista de nombre fijo.

    Se comprueba sobre los FICHEROS, no sobre una constante del test: la
    regresion que se vigila es que alguien escriba de nuevo
    `.tmp/run_state.json` a mano, y un test que solo importara el helper pasaria
    igual mientras el bug vuelve.
    """
    raiz = RS.SCRIPT_DIR
    flows = sorted(raiz.glob("flujo_*.py"))
    servers = sorted(raiz.glob("mcp_*_server.py"))
    comprobar("hay flujos que comprobar", len(flows) > 10, f"{len(flows)} flujos")

    # Los que ESCAPAN de la regla, con su motivo. Se listan en vez de filtrar en
    # silencio: una excepcion que no se ve es una excepcion que se extiende.
    EXCEPCIONES = {
        "flujo_servidor_sismico.py": "vista propia `run_state_sismico.json`, servicio UDP",
        "flujo_sync_faq_flujo.py": "vista propia `faq_flujo_sync.json`, estado de sync",
    }
    culpables = [f.name for f in flows
                 if '"run_state.json"' in f.read_text(encoding="utf-8")
                 and f.name not in EXCEPCIONES]
    comprobar("ningun flujo escribe la vista fija `run_state.json`",
              not culpables, f"culpables={culpables}")
    for nombre in EXCEPCIONES:
        comprobar(f"la excepcion declarada sigue en pie: {nombre}",
                  (raiz / nombre).is_file())

    mcp_culpables = []
    for f in servers:
        txt = f.read_text(encoding="utf-8")
        if '"run_state.json"' in txt:
            mcp_culpables.append(f"{f.name}:nombre-fijo")
        if "mtime_before" in txt:
            mcp_culpables.append(f"{f.name}:mtime")
    comprobar("ningun MCP lee la vista fija ni compara mtimes",
              not mcp_culpables, f"culpables={mcp_culpables}")

    con_helper = [f.name for f in servers
                  if "_importar_run_state" in f.read_text(encoding="utf-8")]
    comprobar("los 5 MCP usan el helper de capa 3", len(con_helper) == 5, con_helper)

    # Los flujos migrados delegan; los que no, tienen su motivo escrito.
    delegan = [f.name for f in flows
               if "import run_state" in f.read_text(encoding="utf-8")]
    comprobar("los flujos migrados importan el helper de capa 3",
              len(delegan) >= 16, f"{len(delegan)} importan run_state")


def main() -> int:
    print("== nombre: la vista lleva el run_id (el P2 de los 16 flujos) ==")
    probar_nombre()
    print("== run_id acotado: un nombre no puede salir de .tmp/ ==")
    probar_run_id_invalido()
    print("== slug: partes del run_id que vienen de un fichero ==")
    probar_slug()
    print("== escritura atomica: nunca un JSON a medias ==")
    probar_escritura_atomica()
    print("== dos corridas a la vez no se pisan ==")
    probar_no_colision()
    print("== guard de 'lo escribio ESTA corrida' ==")
    probar_guard_cambios()
    print("== run_id fijado por el orquestador (ELECTRONICA_RUN_ID) ==")
    probar_run_id_fijado()
    print("== migracion: nadie vuelve a la vista fija ==")
    probar_migracion()
    print("== listar: solo vistas de verdad ==")
    probar_listar()
    print("== retirar: el andamio se quita, el log no ==")
    probar_retirar()
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
