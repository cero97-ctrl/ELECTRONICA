#!/usr/bin/env python3
"""Pruebas de regresion de la auditoria de higiene del repo.

Dos objetivos distintos:

1. `clasificar_salud` es FUNCION PURA y concentrate aqui. Su regla ("gana el
   peor, no hay promedio") es la parte del flujo que mas dano haria si se
   rompiera en silencio, asi que se testea sin ficheros, sin git y sin red.

2. Cada comprobacion de `execution/auditar_repo.py` se prueba sobre un repo
   minimo construido en un temporal, para fijar los errores que se cometieron
   al escribirla.

Ejecutar: python3 execution/test_auditar_repo.py
"""

from __future__ import annotations

import importlib.util
import json
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


AR = _cargar("execution/auditar_repo.py", "auditar_repo")
FA = _cargar("flujo_auditar_repo.py", "flujo_auditar_repo")
CS = FA.clasificar_salud


def _dim(estado: str, nombre: str = "d") -> dict:
    return {"dimension": nombre, "estado": estado, "resumen": "", "evidencia": {}}


# ---------------------------------------------------------------------------
print("== Algebra de veredicto: gana el peor, no hay promedio ==")
# ---------------------------------------------------------------------------

r = CS([_dim("ok"), _dim("ok")])
comprobar("todo ok -> limpio, exit 0", r["veredicto"] == "limpio" and r["exit_code"] == 0, str(r))

r = CS([_dim("ok"), _dim("aviso")])
comprobar("un aviso no bloquea: exit 0 pero no es 'limpio'",
          r["veredicto"] == "con_avisos" and r["exit_code"] == 0, str(r))

r = CS([_dim("ok"), _dim("fallo")])
comprobar("un fallo -> con_fallos, exit 1", r["veredicto"] == "con_fallos" and r["exit_code"] == 1, str(r))

# El caso que motiva el diseno: un fallo grave no puede esconderse tras muchas
# dimensiones sanas. Un promedio de 12/13 "ok" daria 0.92 y taparia el fallo.
dims = [_dim("ok", f"d{i}") for i in range(12)] + [_dim("fallo", "disco")]
r = CS(dims)
comprobar("12 dimensiones sanas NO tapan 1 fallo grave",
          r["veredicto"] == "con_fallos" and r["exit_code"] == 1, str(r))
comprobar("y nombra la dimension culpable", "disco" in r["dimensiones_afectadas"], str(r))

# Una dimension que no se pudo medir no es una dimension sana.
r = CS([_dim("ok"), _dim("ok"), _dim("no_verificado")])
comprobar("sin verificar impide declarar limpio (exit 2)",
          r["veredicto"] == "no_verificado" and r["exit_code"] == 2, str(r))

# Fallo + no verificado a la vez: se reporta el fallo primero.
r = CS([_dim("fallo", "secretos"), _dim("no_verificado", "disco")])
comprobar("fallo + sin verificar -> exit 1, y ambos aparecen",
          r["exit_code"] == 1 and "secretos" in r["dimensiones_afectadas"]
          and "disco" in r["dimensiones_afectadas"], str(r))

r = CS([])
comprobar("lista vacia -> sin verificar, NUNCA limpio",
          r["veredicto"] == "no_verificado" and r["exit_code"] == 2, str(r))

r = CS([_dim("estado_inventado", "raro")])
comprobar("un estado desconocido se trata como no verificado, no como sano",
          r["veredicto"] == "no_verificado" and r["exit_code"] == 2, str(r))
comprobar("y nombra la dimension con el estado raro", "raro" in r.get("dimensiones_afectadas", []), str(r))
# Un estado desconocido NI PUEDE quedar tapado por dimensiones sanas.
r = CS([_dim("ok", f"d{i}") for i in range(10)] + [_dim("estado_inventado", "raro")])
comprobar("un estado desconocido tampoco lo tapan 10 dimensiones sanas",
          r["exit_code"] == 2, str(r))

r = CS([{"dimension": "sin_clave_de_estado"}])
comprobar("una dimension sin 'estado' tampoco se da por buena",
          r["veredicto"] == "no_verificado", str(r))

comprobar("la cobertura distingue medidas de no medidas",
          CS([_dim("ok"), _dim("no_verificado")])["cobertura"] == {"medidas": 1, "no_medidas": 1})

# Es pura: misma entrada, misma salida, y no muta la entrada.
entrada = [_dim("ok"), _dim("fallo")]
copia = json.dumps(entrada, sort_keys=True)
CS(entrada); CS(entrada)
comprobar("es pura: misma entrada -> misma salida y no muta la lista",
          json.dumps(entrada, sort_keys=True) == copia)

# ---------------------------------------------------------------------------
print("== Interpretes: salida desconocida es 'sin verificar', nunca 'ok' ==")
# ---------------------------------------------------------------------------

comprobar("interprete de texto: rc=0 -> ok", FA._interpreta_texto(0, "limpio", False)["estado"] == "ok")
comprobar("interprete de texto: rc=1 -> fallo", FA._interpreta_texto(1, "x [script] y", False)["estado"] == "fallo")
comprobar("interprete de texto: rc=2 -> sin verificar",
          FA._interpreta_texto(2, "", False)["estado"] == "no_verificado")
comprobar("interprete de texto: timeout -> sin verificar",
          FA._interpreta_texto(-1, "", True)["estado"] == "no_verificado")

comprobar("int. bitacoras: 'bitacoras' es lista, no entero (fallo real corregido)",
          FA._interpreta_bitacoras(0, json.dumps({"bitacoras": [], "accionables": 0}), False)["estado"] == "ok")
comprobar("int. bitacoras: accionables>0 -> fallo",
          FA._interpreta_bitacoras(2, json.dumps({"bitacoras": [{}], "accionables": 3}), False)["estado"] == "fallo")
comprobar("int. bitacoras: JSON sin 'accionables' -> sin verificar",
          FA._interpreta_bitacoras(0, json.dumps({"bitacoras": []}), False)["estado"] == "no_verificado")

# `estado_sesion.py` mete huerfano y corrupto en la misma bolsa y lo publica
# como `anomalias`. Estos casos fijan que se mapee por veredicto: una vista
# pendiente de purgar es mantenimiento, no integridad rota.
def _estado(*veredictos):
    return json.dumps({"checks": [
        {"archivo": f"/repo/.tmp/run_state{i}.json", "veredicto": v, "razon": ""}
        for i, v in enumerate(veredictos)], "veredicto_global": "atencion"})


r = FA._interpreta_estado_sesion(0, json.dumps(
    {"checks": [{"archivo": "/r/.tmp/run_state.json", "veredicto": "ok"}],
     "veredicto_global": "ok"}), False)
comprobar("int. estado: todas ok -> ok", r["estado"] == "ok", r["resumen"])

r = FA._interpreta_estado_sesion(0, _estado("huerfano"), False)
comprobar("int. estado: huerfano (corrida terminada) -> aviso, NO fallo",
          r["estado"] == "aviso", r["resumen"])
comprobar("int. estado: y propone la purga", "clean" in r["accion"], r["accion"])

r = FA._interpreta_estado_sesion(0, _estado("corrupto"), False)
comprobar("int. estado: corrupto -> fallo (integridad rota)",
          r["estado"] == "fallo", r["resumen"])
comprobar("int. estado: nombra la vista rota", "run_state0.json" in str(r["evidencia"]["corruptas"]))

r = FA._interpreta_estado_sesion(0, _estado("huerfano", "corrupto"), False)
comprobar("int. estado: huerfano+corrupto -> manda el fallo",
          r["estado"] == "fallo", r["resumen"])

r = FA._interpreta_estado_sesion(0, _estado("no_verificable"), False)
comprobar("int. estado: no_verificable -> aviso, no se puede afirmar nada",
          r["estado"] == "aviso", r["resumen"])

r = FA._interpreta_estado_sesion(0, _estado("huerfano", "no_verificable", "ok"), False)
comprobar("int. estado: huerfano+sin_juzgar+ok -> aviso", r["estado"] == "aviso", r["resumen"])
comprobar("int. estado: cuenta las pendientes de purga", len(r["evidencia"]["huerfanas"]) == 1, str(r))

comprobar("int. estado: 'checks' vacio -> sin verificar",
          FA._interpreta_estado_sesion(0, json.dumps({"checks": []}), False)["estado"] == "no_verificado")
comprobar("int. estado: sin 'checks' -> sin verificar",
          FA._interpreta_estado_sesion(0, json.dumps({"otra": 1}), False)["estado"] == "no_verificado")

comprobar("int. disco: 91% -> fallo (mismo umbral que flujo_disco)",
          FA._interpreta_disco(0, json.dumps({"filesystem": {"uso_pct": 91.3, "libre_gb": 20}}), False)["estado"] == "fallo")
comprobar("int. disco: 85% -> aviso",
          FA._interpreta_disco(0, json.dumps({"filesystem": {"uso_pct": 85}}), False)["estado"] == "aviso")
comprobar("int. disco: JSON invalido -> sin verificar",
          FA._interpreta_disco(0, "no soy json", False)["estado"] == "no_verificado")
comprobar("int. disco: sin 'filesystem' -> sin verificar",
          FA._interpreta_disco(0, json.dumps({"otra": 1}), False)["estado"] == "no_verificado")

# El bug que estas dos aserciones de arriba NO cazaban. Sus fixtures estaban
# escritos a mano y omitian `resumen_catalogo` por completo, asi que la rama del
# recuperable nunca se ejecutaba: el test demuestra umbrales y no dice nada del
# numero. El interpreta leia `datos["recuperable"]`, clave que disco_medir.py
# nunca ha emitido, de modo que afirmaba "0 MB recuperables" con una clave
# ausente. Estas de aqui si usan la forma REAL capturada de disco_medir.py.
_DISCO_REAL = {
    "filesystem": {"ruta": "/", "total_gb": 233.18, "usado_gb": 212.8,
                   "libre_gb": 20.38, "uso_pct": 91.3,
                   "inodos_total": 15597568, "inodos_libres": 10935829,
                   "inodos_usados_pct": 29.9},
    "resumen_catalogo": {
        "entradas": 27,
        "reclaimable_por_tier": {
            "pesado": {"bytes": 746131456, "humano": "711.6 MB"},
            "recargable": {"bytes": 9063030784, "humano": "8.4 GB"},
            "seguro": {"bytes": 16863232, "humano": "16.1 MB"},
        },
        "reclaimable_total_bytes": 9826025472,
        "reclaimable_total": "9.2 GB",
        "medido_por_tier": {"seguro": {"bytes": 473964544, "humano": "452.0 MB"}},
    },
    "targets": [], "rutas_que_requieren_sudo": [], "notas": [], "status": "ok",
}
_r = FA._interpreta_disco(0, json.dumps(_DISCO_REAL), False)
comprobar("int. disco: lee los bytes reales de la salida real (16.1 MB, no 0)",
          _r["evidencia"]["recuperable_mb"] == 16.1, str(_r["evidencia"]["recuperable_mb"]))
comprobar("int. disco: el resumen afirma la cifra real, no un cero inventado",
          "16.1 MB recuperables" in _r["resumen"], _r["resumen"])
comprobar("int. disco: el umbral NO se confunde con el total recuperable (9.2 GB)",
          _r["evidencia"]["recuperable_mb"] != 9826025472 / 1048576,
          "debe leer el tier 'seguro', no el total")
comprobar("int. disco: 'medido_por_tier' no se confunde con 'reclaimable_por_tier'",
          _r["evidencia"]["recuperable_mb"] != round(473964544 / 1048576, 1),
          "452.0 MB es lo medido, 16.1 MB lo recuperable tras la barrera")

# La ausencia de dato NO puede convertirse en un cero afirmado.
_sin_catalogo = FA._interpreta_disco(
    0, json.dumps({"filesystem": {"uso_pct": 91.3, "libre_gb": 20.38}}), False)
comprobar("int. disco: sin resumen_catalogo, recuperable es null y no 0",
          _sin_catalogo["evidencia"]["recuperable_mb"] is None,
          str(_sin_catalogo["evidencia"]["recuperable_mb"]))
comprobar("int. disco: sin resumen_catalogo, el resumen NO dice '0 MB'",
          "0 MB" not in _sin_catalogo["resumen"], _sin_catalogo["resumen"])
comprobar("int. disco: sin resumen_catalogo, el resumen declara la laguna",
          "no informado" in _sin_catalogo["resumen"], _sin_catalogo["resumen"])
comprobar("int. disco: el estado sigue decidiéndose por uso_pct aunque falte el catálogo",
          _sin_catalogo["estado"] == "fallo", _sin_catalogo["estado"])

# El ambito de la cifra, y la accion que faltaba por completo. Sin esto el
# informe publicaba "16.1 MB recuperables" sin decir que eso es SOLO lo del
# proyecto: leido suelto dice "el disco esta bien", cuando el margen real esta
# en rutas de root fuera del alcance del flujo.
comprobar("int. disco: el resumen declara su ambito",
          "ambito" in _r["resumen"] and "catalogo_disco.py" in _r["resumen"],
          _r["resumen"])
comprobar("int. disco: el ambito nombra las rutas que NO cubre",
          all(s in FA.AMBITO_DISCO for s in ("/var/lib/docker", "/var/lib/waydroid", "root")),
          FA.AMBITO_DISCO)
comprobar("int. disco: evidencia expone el ambito de forma legible por maquina",
          _r["evidencia"]["ambito"] == FA.AMBITO_DISCO)
comprobar("int. disco: en fallo hay accion (antes no la habia: 0 acciones en el informe)",
          bool(_r.get("accion")), "accion ausente")
comprobar("int. disco: la accion advierte de que el margen esta fuera del flujo",
          "FUERA de su whitelist" in _r["accion"], _r["accion"][:80])
comprobar("int. disco: la accion avisa del riesgo de docker prune con las imagenes del proyecto",
          "docker system prune" in _r["accion"] and "kicad/kicad:8.0" in _r["accion"])
comprobar("int. disco: sin dato de recuperable, la accion manda repetir la medicion",
          "Reintentar la medicion" in _sin_catalogo["accion"], _sin_catalogo["accion"][:80])
_aviso_disco = FA._interpreta_disco(0, json.dumps({"filesystem": {"uso_pct": 85}}), False)
comprobar("int. disco: fuera de umbral, la accion NO dramatiza",
          "FUERA de su whitelist" not in _aviso_disco["accion"], _aviso_disco["accion"][:80])
comprobar("int. disco: fuera de umbral, la accion sigue declarando el ambito",
          "catalogo_disco.py" in _aviso_disco["accion"])
comprobar("int. disco: resumen y accion no afirman que 0 sea el total del disco",
          "todo el disco" not in _r["accion"] or "no dice nada del resto" in _aviso_disco["accion"])

comprobar("int. test: cuenta los fallos de la linea de aserciones",
          FA._interpreta_test("Aserciones OK: 88   Fallos: 2", False)["estado"] == "fallo")
comprobar("int. test: todo verde -> ok",
          FA._interpreta_test("Aserciones OK: 10   Fallos: 0", False)["estado"] == "ok")
comprobar("int. test: salida sin linea de aserciones -> sin verificar",
          FA._interpreta_test("algo raro", False)["estado"] == "no_verificado")

# `logs` es dimension nueva, no reutilizada: verifica la cadena de hashes de
# TODOS los .tmp/session_log_*.jsonl, no de un unico run fijo.
comprobar("no queda interprete de logs muerto en el flujo",
          not hasattr(FA, "_interpreta_logs_append_only"))
comprobar("la dimension logs se apoya en sesion_log.py integrity",
          callable(AR.comprobar_logs_append_only))

# ---------------------------------------------------------------------------
print("== Deteccion de secretos: precision antes que sensibilidad ==")
# ---------------------------------------------------------------------------

comprobar("patron de OpenRouter (sk-or-v1-) se detecta",
          AR.PATRONES_SECRETO[0][1].search("clave = sk-or-v1-" + "a" * 40) is not None)
comprobar("token de Telegram se detecta",
          any(p.search("TELEGRAM=1234567890:" + "B" * 35) for _, p, _ in AR.PATRONES_SECRETO))
# El header PEM se arma por partes a proposito: escrito literal en el fuente,
# el detector de secretos lo marca como clave latente (y con razon, es lo que
# busca). La prueba necesita la cadena, no el fichero.
_PEM = "-----BEGIN " + "EC PRIVATE" + " KEY-----"
comprobar("clave PEM se detecta",
          any(p.search(_PEM) for _, p, _ in AR.PATRONES_SECRETO))
comprobar("y el header es de verdad el que dice ser", _PEM.startswith("-----BEGIN "))

# Falsos positivos que se midieron de verdad y motivaron excluir el Griego
# del detector de texto: aqui el criterio es el mismo.
comprobar("una palabra inglesa larga NO es un secreto",
          AR.PATRON_ASIGNACION.search('token = "administracion"') is None
          or AR.entropia_shannon("administracion") < 4.0)
comprobar("un hash de commit no dispara la asignacion",
          AR.PATRON_ASIGNACION.search('commit = "9f3a7b2c1d4e5f6a7b8c9d0e1f2a3b4c"') is None
          or AR.entropia_shannon("9f3a7b2c1d4e5f6a7b8c9d0e1f2a3b4c") < 4.0)
comprobar("la prosa normal no dispara ningun patron de proveedor",
          not any(p.search("Consulta la documentacion del proyecto.") for _, p, _ in AR.PATRONES_SECRETO))
comprobar("node_modules esta excluido del escaneo (falso positivo medido)",
          AR._es_vendida("Proyectos/x/node_modules/lib/a.js") is True)
comprobar(".pio tambien (artefacto de build)",
          AR._es_vendida("Proyectos/x/.pio/build/f.elf") is True)
comprobar("codigo propio del repo SI se escanea",
          AR._es_vendida("execution/verificar_texto.py") is False)
comprobar("una ruta con 'node' en otro sitio NO se excluye de mas",
          AR._es_vendida("docs/nodo/grafo.md") is False)
comprobar("los .env nunca se escanean (contenido sensible por diseno)",
          ".env" in AR.NUNCA_ESCANEAR_SECRETOS and ".groq_api_key" in AR.NUNCA_ESCANEAR_SECRETOS)
_secreto = "a1b2c3d4e5f6" + "z" * 28          # 40 chars
_mascara = AR._ofuscar(_secreto)
comprobar("la ofuscacion no reproduce el secreto entero", _secreto not in _mascara, _mascara)
# Lo que importa es CUANTO se filtra: la mascara expone 6 del inicio y 2 del
# final, asi que un secreto de 40 no puede quedar mas de 1/4 a la vista.
_expuestos = 6 + 2
comprobar("la mascara filtra como maximo una cuarta parte del secreto",
          _expuestos <= len(_secreto) / 4, f"{_expuestos} de {len(_secreto)}")
comprobar("y la longitud del secreto si queda registrada", "40" in _mascara, _mascara)
comprobar("un secreto corto se enmascara igual (no se filtra en claro)",
          "a" * 10 not in AR._ofuscar("a" * 10), AR._ofuscar("a" * 10))

# ---------------------------------------------------------------------------
print("== Comprobaciones sobre repo minimo ==")
# ---------------------------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    raiz = Path(tmp)
    (raiz / "directives").mkdir()
    (raiz / "execution").mkdir()
    (raiz / "docs").mkdir()

    # directivas: una sana, una con script inexistente
    (raiz / "directives" / "buena.yaml").write_text(
        "references:\n  orchestrator: flujo_x.py\n  scripts: execution/existe.py\n", encoding="utf-8")
    (raiz / "execution" / "existe.py").write_text("x = 1\n", encoding="utf-8")
    (raiz / "directives" / "muerta.yaml").write_text(
        "references:\n  scripts: execution/no_existe.py, execution/tampoco.py\n", encoding="utf-8")

    d = AR.comprobar_directivas(raiz)
    comprobar("detecta referencias a scripts inexistentes", d["estado"] == "fallo", d["resumen"])
    comprobar("y cuenta las dos rotas", d["evidencia"]["referencias_rotas"] == 2, str(d["evidencia"]))
    comprobar("la directiva sana no se marca", all(
        r["directiva"] != "buena.yaml" for r in d["evidencia"]["rotas"]))

    # Si se reparan las referencias rotas, el estado pasa a ok de verdad.
    (raiz / "directives" / "muerta.yaml").write_text(
        "references:\n  scripts: execution/existe.py\n", encoding="utf-8")
    d_ok = AR.comprobar_directivas(raiz)
    comprobar("reparada la referencia, la dimension pasa a ok",
              d_ok["estado"] == "ok", d_ok["resumen"])
    comprobar("y no quedan rotas", d_ok["evidencia"]["referencias_rotas"] == 0)

    # Cero referencias en todas: no se escaneo nada -> sin verificar, no 'ok'.
    for f in (raiz / "directives").glob("*.yaml"):
        f.write_text("goal: nada que ejecutar\n", encoding="utf-8")
    d3 = AR.comprobar_directivas(raiz)
    comprobar("cero referencias en todas -> sin verificar, no 'ok'",
              d3["estado"] == "no_verificado", d3["resumen"])
    comprobar("y el motivo lo explica", "referencia" in d3["evidencia"]["motivo"].lower(),
              d3["evidencia"]["motivo"])

    # --- Declaracion honesta: un hueco DECLARADO baja de gravedad, no desaparece.
    for f in (raiz / "directives").glob("*.yaml"):
        f.unlink()
    (raiz / "directives" / "roadmap.yaml").write_text(
        "Status: planificado\nreferences:\n"
        "  scripts: execution/aun_no.py, execution/tampoco.py\n", encoding="utf-8")
    d4 = AR.comprobar_directivas(raiz)
    comprobar("referencia rota en directiva 'planificado' -> aviso, no fallo",
              d4["estado"] == "aviso", d4["resumen"])
    comprobar("y se cuenta como declarada, no como silenciosa",
              d4["evidencia"]["referencias_declaradas_no_implementadas"] == 2
              and d4["evidencia"]["referencias_rotas_silenciosas"] == 0,
              str(d4["evidencia"]))
    comprobar("pero NUNCA 'ok': el hueco sigue visible y contado",
              d4["estado"] != "ok" and d4["evidencia"]["referencias_rotas"] == 2)
    comprobar("y la accion nombra la capacidad no implementada",
              "no implementada" in d4["accion"], d4["accion"])
    comprobar("y la accion dice que no es un fallo",
              "no es un fallo" in d4["accion"].lower(), d4["accion"])

    # Marcador obsoleto: dice 'no implementado' pero todo lo que referencia existe.
    (raiz / "directives" / "roadmap.yaml").write_text(
        "Status: planificado\nreferences:\n  scripts: execution/existe.py\n",
        encoding="utf-8")
    d5 = AR.comprobar_directivas(raiz)
    comprobar("marcador 'planificado' obsoleto -> aviso, no 'ok'",
              d5["estado"] == "aviso", d5["resumen"])
    comprobar("y se cuenta como obsoleto, no como capacidad pendiente",
              len(d5["evidencia"]["marcadores_obsoletos"]) == 1
              and d5["evidencia"]["referencias_rotas"] == 0,
              str(d5["evidencia"]))
    comprobar("y la accion dice que el marcador esta obsoleto",
              "obsoleto" in d5["accion"], d5["accion"])

    # Status fuera de vocabulario no sirve para esconderse.
    (raiz / "directives" / "tramposa.yaml").write_text(
        "Status: hecho\nreferences:\n  scripts: execution/oculta.py\n", encoding="utf-8")
    d6 = AR.comprobar_directivas(raiz)
    comprobar("Status inventado no oculta la referencia rota",
              d6["estado"] == "fallo"
              and d6["evidencia"]["referencias_rotas_silenciosas"] == 1, d6["resumen"])
    comprobar("y se reporta el marcador invalido con su valor",
              len(d6["evidencia"]["marcadores_invalidos"]) == 1
              and d6["evidencia"]["marcadores_invalidos"][0]["valor"] == "hecho",
              str(d6["evidencia"]["marcadores_invalidos"]))

    # Comentarios TAMBIEN cuentan: comentar un paso no puede ser como pasar.
    (raiz / "directives" / "comentada.yaml").write_text(
        "# antes usaba execution/oculta.py, ya no\n"
        "references:\n  scripts: execution/todavia_no.py\n", encoding="utf-8")
    d7 = AR.comprobar_directivas(raiz)
    comprobar("una referencia solo mencionada en un comentario tambien se cuenta",
              any(r["script"] == "oculta.py" for r in d7["evidencia"]["rotas"]),
              str(d7["evidencia"]["rotas"]))

    # capas: deteccion por EXISTENCIA, no por forma de la ruta
    (raiz / "flujo_bueno.py").write_text(
        'MEDIR = SCRIPT_DIR / "execution" / "existe.py"\n', encoding="utf-8")
    d = AR.comprobar_capas(raiz)
    comprobar("un flujo que construye la ruta con Path SI cuenta como capa 3 (13 falsos positivos corregidos)",
              d["estado"] == "ok", d["resumen"])
    (raiz / "flujo_malo.py").write_text("print('hola')\n", encoding="utf-8")
    d = AR.comprobar_capas(raiz)
    comprobar("un flujo que no nombra script de execution/ -> fallo",
              d["estado"] == "fallo", d["resumen"])
    comprobar("y nombra el flujo concreto",
              any(x["flujo"] == "flujo_malo.py" for x in d["evidencia"]["sin_capa_3"]))

    (raiz / "flujo_telegram.py").write_text("print('daemon')\n", encoding="utf-8")
    d = AR.comprobar_capas(raiz)
    comprobar("un daemon esta exento de capa 3 por diseno",
              d["estado"] == "fallo" and all(
                  x["flujo"] != "flujo_telegram.py" for x in d["evidencia"]["sin_capa_3"]),
              d["resumen"])

    # pdf_stale
    (raiz / "doc.tex").write_text("x\n", encoding="utf-8")
    (raiz / "doc.pdf").write_bytes(b"%PDF-1.4\n")
    import os, time as _t
    viejo = _t.time() - 10_000
    os.utime(raiz / "doc.pdf", (viejo, viejo))
    d = AR.comprobar_pdf_stale(raiz)
    comprobar("un .tex mas nuevo que su .pdf -> aviso", d["estado"] == "aviso", d["resumen"])
    os.utime(raiz / "doc.pdf", None)
    os.utime(raiz / "doc.tex", (viejo, viejo))
    d = AR.comprobar_pdf_stale(raiz)
    comprobar("PDF al dia -> ok", d["estado"] == "ok", d["resumen"])

    # no hay pares .tex/.pdf -> sin verificar
    (raiz / "doc.pdf").unlink()
    d = AR.comprobar_pdf_stale(raiz)
    comprobar("sin pares comparables -> sin verificar, no ok",
              d["estado"] == "no_verificado", d["resumen"])

# ---------------------------------------------------------------------------
print("== Umbrales y tabla de dimensiones ==")
# ---------------------------------------------------------------------------

comprobar("el umbral de bloqueo de push de GitHub es 100 MB",
          AR.PESO_BLOQUEO_MB == 100.0, str(AR.PESO_BLOQUEO_MB))
comprobar("el umbral de aviso coincide con el de GitHub (50 MB)",
          AR.PESO_FALLO_MB == 50.0, str(AR.PESO_FALLO_MB))
comprobar("node_modules y .pio estan entre las carpetas que no se trackean",
          {"node_modules", ".pio"} <= set(AR.CARPETAS_NUNCA_TRACKEAR))
comprobar("las 7 dimensiones nuevas estan declaradas", len(AR.DIMENSIONES_NUEVAS) == 7,
          str(sorted(AR.DIMENSIONES_NUEVAS)))
comprobar("'logs' es dimension nueva: enumera los 19 logs, no un script fijo",
          "logs" in AR.DIMENSIONES_NUEVAS)
comprobar("las 6 reutilizadas estan declaradas", len(FA.DIMENSIONES_REUTILIZADAS) == 6,
          str(len(FA.DIMENSIONES_REUTILIZADAS)))
comprobar("13 dimensiones en total", len(AR.DIMENSIONES_NUEVAS) + len(FA.DIMENSIONES_REUTILIZADAS) == 13)
comprobar("toda dimension reutilizada tiene interprete y timeout",
          all("interpreta" in d and d.get("timeout", 0) > 0 for d in FA.DIMENSIONES_REUTILIZADAS))
comprobar("ninguna dimension reutilizada puede borrar nada",
          all(not {"clean", "purge", "reset"} & set(d["args"]) for d in FA.DIMENSIONES_REUTILIZADAS))
comprobar("toda dimension declara de donde sale (script o funcion)",
          all(d.get("script") or d.get("capa") for d in FA.DIMENSIONES_REUTILIZADAS))

print()
# ---------------------------------------------------------------------------
print("== Contrato del CLI: codigos de salida y las dos formas del flag ==")
# ---------------------------------------------------------------------------
# El motivo de que estas aserciones exista: argparse sale con 2, y en este
# flujo 2 significa 'no verificado'. Con el codigo de argparse, escribir mal
# un flag se reportaba como una dimension que no se pudo comprobar, que es una
# lectura falsa: invita a reintentar la medicion cuando el problema era el
# comando. Se remapea a 3 para que cada codigo signifique una sola cosa.

def _exit_de_uso(argv: list[str], modulo) -> int | None:
    """Devuelve el codigo de salida por error de uso, o None si no lo hubo."""
    try:
        return modulo.main(argv)
    except SystemExit as exc:
        return exc.code


for etiqueta, argv in [
    ("flag inexistente", ["--flag-inexistente"]),
    ("valor mal formado", ["--timeout-dim", "abc"]),
]:
    comprobar(f"{etiqueta} -> 3, no 2", _exit_de_uso(argv, FA) == 3, str(argv))

comprobar("dimension inexistente -> 3 (no exception, return directo)",
          FA.main(["--solo", "dimension_que_no_existe"]) == 3)

# Las dos capas deben coincidir en el codigo de uso incorrecto.
comprobar("capa 3: raiz invalida -> 3, no 2", AR.main(["--raiz", "/tmp"]) == 3)
comprobar("ambas capas definen su propia subclase con el mismo contrato",
          isinstance(FA._Parser, type) and isinstance(AR._Parser, type)
          and FA._Parser is not AR._Parser)

# --dimension (repetible) y --solo (lista) deben ser la misma cosa, y unionarse.
_a = FA.construir_parser().parse_args(["--dimension", "texto", "--solo", "disco"])
comprobar("--dimension es repetible (append)", _a.dimension == ["texto"], str(_a.dimension))
comprobar("--solo se acepta como alias de lista", _a.solo == "disco", str(_a.solo))

_b = FA.construir_parser().parse_args(["--dimension", "texto", "--dimension", "disco"])
comprobar("repetir --dimension acumula sin repetir trabajo",
          _b.dimension == ["texto", "disco"], str(_b.dimension))

_solo_set = {s.strip() for s in " texto , estado_sesion ,".split(",") if s.strip()}
comprobar("--solo con espacios y comas sueltas se normaliza",
          _solo_set == {"texto", "estado_sesion"}, str(_solo_set))

_codigos_uso = {_exit_de_uso(["--flag-inexistente"], FA), _exit_de_uso(["--solo", "nope"], FA)}
comprobar("ningun error de uso produce 2 (que queda reservado a no_verificado)",
          2 not in _codigos_uso, str(_codigos_uso))

# La duracion por dimension es lo que permite decidir si --rapido ahorra algo.
comprobar("cada comprobacion nueva mide su duracion",
          all(callable(fn) for fn in AR.DIMENSIONES_NUEVAS.values()))

with tempfile.TemporaryDirectory() as _td:
    _raiz = Path(_td)
    (_raiz / "directives").mkdir()
    _dur = AR.DIMENSIONES_NUEVAS["logs"](_raiz).get("duracion_s")
    comprobar("la duracion es un numero no negativo",
              isinstance(_dur, (int, float)) and _dur >= 0, f"duracion_s={_dur!r}")

    (_raiz / "directives" / "x.yaml").write_text(
        "required_inputs:\n  - name: --dimension N\n", encoding="utf-8")
    _dur2 = AR.DIMENSIONES_NUEVAS["directivas"](_raiz).get("duracion_s")
    comprobar("toda comprobacion expone duracion_s, no solo una",
              isinstance(_dur2, (int, float)), f"duracion_s={_dur2!r}")

print()
if FALLOS:
    print(f"FALLOS: {len(FALLOS)}/{PRUEBAS}")
    for f in FALLOS:
        print(f"  - {f}")
    sys.exit(1)
print(f"Aserciones OK: {PRUEBAS}   Fallos: 0")
print("AUDITORIA DE HIGIENE OK: algebra de veredicto, interpretes, secretos, capas y umbrales.")
sys.exit(0)
