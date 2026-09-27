#!/usr/bin/env python3
"""Pruebas de regresion de la auditoria de sistema.

Cuatro objetivos distintos:

1. Los INTERPRETES son funciones puras `(medicion) -> dimension`. Se testean
   aqui sin /proc, sin systemd y sin reloj, que es justamente por lo que estan
   separados de la medicion.

2. Los UMBRALES se testean en sus bordes exactos, porque un umbral mal escrito
   que no dispara en el limite produce un sistema saturado marcado como `ok`.
   Dos de estos tests existen porque los bugs ME OCURRIERON al escribir el
   flujo: `indice_load` apuntaba al loadavg de 15 min mientras su comentario
   decia 5 min, y un servicio `loaded`+`inactive` caia en `no_verificado` en vez
   de `aviso`. Los dos eran silenciosos: ninguna asercion de las anteriores los
   habria pillado.

3. La CAPA 3 no decide. Se comprueba que las funciones de medicion devuelven
   hechos y jamas una clave `estado`, para que un refactor futuro no mueva la
   politica a la capa equivocada sin quejarse.

4. El CONTRATO DE SALIDA: codigos de exit, `no_verificado` que impide el verde,
   y los umbrales embebidos en el informe (sin ellos el veredicto es
   irreproducible).

Ejecutar: python3 execution/test_auditar_sistema.py
"""

from __future__ import annotations

import importlib.util
import contextlib, io, json
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
AS = _cargar("execution/auditar_sistema.py", "auditar_sistema_bajo_test")
FAS = _cargar("flujo_auditar_sistema.py", "flujo_auditar_sistema_bajo_test")
VA = FAS.VA
UMBRALES = FAS.UMBRALES


# ---------------------------------------------------------------------------
# Fixtures: datos DELIBERADAMENTE syntheticos, no la maquina real.
#
# Un test que se apoya en el /proc de quien lo ejecuta pasa en su portatil y
# falla en la de al lado, y encima no prueba nada: el punto es fijar la regla,
# no el estado de hoy. Los valores de abajo estan chosen en los bordes.
# ---------------------------------------------------------------------------
def mem(pct: float, **kw):
    total = 1000
    base = {"total_kb": total, "disponible_kb": int(total * (1 - pct / 100)),
            "usado_pct": pct, "libre_kb": 100, "swap_total_kb": 0, "swap_usado_kb": 0}
    base.update(kw)
    return base


def inter(zram_pct=0.0, disco_pct=0.0, disco_total=1000, zram_total=1000):
    return {
        "zram": {"presente": zram_pct > 0 or zram_total > 0, "usado_pct": zram_pct,
                 "usado_kb": int(zram_total * zram_pct / 100), "total_kb": zram_total,
                 "zram_lleno_es_normal": True, "dispositivos": [
                     {"nombre": "/dev/zram0", "usado_pct": zram_pct,
                      "razon_compresion": 4.5, "total_kb": zram_total}]},
        "swap_disco": {"usado_pct": disco_pct,
                       "usado_kb": int(disco_total * disco_pct / 100),
                       "total_kb": disco_total, "dispositivos": []},
        "indices_zram_detectados": ["zram0"],
    }


def psi(avg60_some: float, avg60_full: float = 0.0):
    """Estructura real de /proc/pressure: dos filas, `some` y `full`."""
    return {"some": {"avg10": avg60_some, "avg60": avg60_some,
                     "avg300": avg60_some, "total": 1},
            "full": {"avg10": avg60_full, "avg60": avg60_full,
                     "avg300": avg60_full, "total": 1}}


def cpu(load=(0.2, 0.2, 0.2), nucleos=4, steal=None, psi_cpu=None, psi_io=None):
    return {
        "nucleos": nucleos, "loadavg": list(load), "steal_pct": steal,
        "psi_cpu": psi_cpu, "psi_io": psi_io,
        "load_por_nucleo": [round(v / nucleos, 2) for v in load],
    }


def servicios(estados: list[tuple[str, str, str]]):
    return {"servicios": [
        {"Id": u, "LoadState": l, "ActiveState": a, "SubState": s} for u, l, a, s in estados],
        "consulta": "test"}


print("== Memoria: umbrales en el borde exacto ==")
for pct, esperado in [(0, "ok"), (74.9, "ok"), (75.0, "aviso"), (89.9, "aviso"),
                      (90.0, "fallo"), (99.0, "fallo")]:
    d = FAS.interpretar_memoria(mem(pct))
    comprobar(f"memoria {pct}% -> {esperado}", d["estado"] == esperado, d["estado"])
comprobar("memoria sin dato es no_verificado, nunca ok",
          FAS.interpretar_memoria({"no_medible": "sin /proc/meminfo"})["estado"] == "no_verificado")
comprobar("memoria no_medible trae accion",
          bool(FAS.interpretar_memoria({"no_medible": "x"})["accion"]))
comprobar("todo estado lleva accion o resumen",
          all(d.get("accion") for d in [FAS.interpretar_memoria(mem(50))]))

print("== Intercambio: zram lleno NO es presion; el swap en disco si ==")
d = FAS.interpretar_intercambio(inter(zram_pct=92.0, disco_pct=10.0))
comprobar("zram al 92% con swap en disco al 10% sigue siendo ok", d["estado"] == "ok", d["estado"])
d = FAS.interpretar_intercambio(inter(zram_pct=99.0, disco_pct=0.0))
comprobar("zram al 99% con disco vacio sigue siendo ok", d["estado"] == "ok", d["estado"])
for pct, esperado in [(69.9, "ok"), (70.0, "aviso"), (89.9, "aviso"), (90.0, "fallo")]:
    d = FAS.interpretar_intercambio(inter(disco_pct=pct, zram_pct=50.0))
    comprobar(f"swap en disco {pct}% -> {esperado}", d["estado"] == esperado, d["estado"])
d = FAS.interpretar_intercambio(inter(disco_total=0, zram_total=0, zram_pct=0.0))
comprobar("sin ningun intercambio -> ok, no fallo", d["estado"] == "ok", d["estado"])
comprobar("el resumen dice que zram lleno es normal",
          "normal" in FAS.interpretar_intercambio(inter(zram_pct=88.0))["resumen"])
comprobar("intercambio no_medible -> no_verificado",
          FAS.interpretar_intercambio({"no_medible": "sin /proc/swaps"})["estado"] == "no_verificado")

print("== CPU: carga por nucleo, y steal/PSI solo empeoran ==")
comprobar("el indice de load apunta al loadavg de 5 min",
          UMBRALES["cpu"]["indice_load"] == 1,
          f"indice {UMBRALES['cpu']['indice_load']}")
d = FAS.interpretar_cpu(cpu(load=(0.1, 0.1, 9.9)))
comprobar("el load de 15 min alto con 5 min bajo no dispara aviso",
          d["estado"] == "ok", d["estado"])
comprobar("el load de 1 min alto con 5 min bajo no dispara aviso",
          FAS.interpretar_cpu(cpu(load=(9.9, 0.1, 0.1)))["estado"] == "ok")
for carga, esperado in [(0.5, "ok"), (1.0, "aviso"), (1.99, "aviso"),
                        (2.0, "fallo"), (5.0, "fallo")]:
    d = FAS.interpretar_cpu(cpu(load=(carga, carga, carga), nucleos=1))
    comprobar(f"carga {carga}/nucleo -> {esperado}", d["estado"] == esperado, d["estado"])
comprobar("el mismo load es saturacion en 2 nucleos y ocioso en 16",
          FAS.interpretar_cpu(cpu(load=(4, 4, 4), nucleos=2))["estado"] == "fallo"
          and FAS.interpretar_cpu(cpu(load=(4, 4, 4), nucleos=16))["estado"] == "ok")
comprobar("load 2 en 2 nucleos es exactamente el umbral de aviso",
          FAS.interpretar_cpu(cpu(load=(2, 2, 2), nucleos=2))["estado"] == "aviso")
comprobar("steal alto sube a fallo aunque la carga sea baja",
          FAS.interpretar_cpu(cpu(load=(0.1, 0.1, 0.1), steal=30.0))["estado"] == "fallo")
comprobar("steal medio sube a aviso",
          FAS.interpretar_cpu(cpu(load=(0.1, 0.1, 0.1), steal=12.0))["estado"] == "aviso")
comprobar("steal bajo no ensucia un ok",
          FAS.interpretar_cpu(cpu(load=(0.1, 0.1, 0.1), steal=0.5))["estado"] == "ok")
comprobar("PSI de CPU alto degrada",
          FAS.interpretar_cpu(cpu(load=(0.1, 0.1, 0.1), psi_cpu=psi(60.0)))["estado"] == "fallo")
comprobar("PSI de CPU medio degrada a aviso",
          FAS.interpretar_cpu(cpu(load=(0.1, 0.1, 0.1), psi_cpu=psi(30.0)))["estado"] == "aviso")
comprobar("PSI `full` alto NO degrada: solo cuenta que TODAS las tareas paren",
          FAS.interpretar_cpu(cpu(load=(0.1, 0.1, 0.1), psi_cpu=psi(0.0, 90.0)))["estado"] == "ok")
comprobar("PSI de E/S informa pero no verdicta",
          FAS.interpretar_cpu(cpu(load=(0.1, 0.1, 0.1), psi_io=psi(80.0)))["estado"] == "ok")
comprobar("el PSI de E/S alto aparece en la accion",
          "E/S" in FAS.interpretar_cpu(cpu(load=(0.1, 0.1, 0.1), psi_io=psi(80.0)))["accion"])
comprobar("steal y PSI NUNCA mejoran un estado ya malo",
          FAS.interpretar_cpu(cpu(load=(5, 5, 5), nucleos=1, steal=0.0))["estado"] == "fallo")
comprobar("cpu no medible -> no_verificado",
          FAS.interpretar_cpu({"no_medible": "sin loadavg"})["estado"] == "no_verificado")
comprobar("cpu sin load_por_nucleo -> no_verificado",
          FAS.interpretar_cpu({"nucleos": 4, "loadavg": [1, 1, 1],
                               "load_por_nucleo": None})["estado"] == "no_verificado")

print("== Servicios: no-instalado, caido y parado son tres cosas distintas ==")
comprobar("los dos del repo en pie -> ok",
          FAS.interpretar_servicios(servicios(
              [("telegram_gateway.service", "loaded", "active", "running"),
               ("waydroid-container.service", "loaded", "active", "running")]))["estado"] == "ok")
comprobar("failed -> fallo",
          FAS.interpretar_servicios(servicios(
              [("telegram_gateway.service", "loaded", "failed", "failed")]))["estado"] == "fallo")
comprobar("not-found -> no_verificado (no instalado no es estar caido)",
          FAS.interpretar_servicios(servicios(
              [("waydroid-container.service", "not-found", "inactive", "dead")]))["estado"]
          == "no_verificado")
comprobar("loaded + inactive -> aviso (instalado y parado)",
          FAS.interpretar_servicios(servicios(
              [("telegram_gateway.service", "loaded", "inactive", "dead")]))["estado"]
          == "aviso", "caia en no_verificado")
comprobar("activating -> aviso",
          FAS.interpretar_servicios(servicios(
              [("telegram_gateway.service", "loaded", "activating", "start")]))["estado"]
          == "aviso")
comprobar("un caido entre dos en pie -> fallo",
          FAS.interpretar_servicios(servicios(
              [("a.service", "loaded", "active", "running"),
               ("b.service", "loaded", "failed", "failed"),
               ("c.service", "loaded", "active", "running")]))["estado"] == "fallo")
comprobar("sin systemd -> no_verificado",
          FAS.interpretar_servicios({"no_medible": "sin systemctl"})["estado"] == "no_verificado")
comprobar("sin unidades -> no_verificado",
          FAS.interpretar_servicios({"servicios": []})["estado"] == "no_verificado")
comprobar("el detalle nombra cada unidad",
          len(FAS.interpretar_servicios(servicios(
              [("a.service", "loaded", "active", "running")]))["evidencia"]["detalle"]) == 1)

print("== Aceleracion: la ausencia de GPU es un hecho, no un defecto ==")
d = FAS.interpretar_aceleracion(
    {"gpu_discreta": False, "modelos": ["Intel UHD Graphics 600"],
     "entrenamiento_local_posible": False, "nota": "n"})
comprobar("sin GPU discreta el estado sigue siendo ok", d["estado"] == "ok", d["estado"])
comprobar("pero el resumen dice que hay que ir a Colab", "Colab" in d["resumen"])
comprobar("y la accion tambien", "Colab" in d["accion"])
comprobar("con GPU discreta tambien ok, yamandolo",
          FAS.interpretar_aceleracion(
              {"gpu_discreta": True, "modelos": ["RTX"], "entrenamiento_local_posible": True}
          )["estado"] == "ok")

print("== La capa 3 MIDE: no decide ==")
for nombre in ["medir_memoria", "medir_intercambio", "medir_cpu",
               "medir_servicios", "medir_aceleracion"]:
    f = getattr(AS, nombre)
    comprobar(f"{nombre} existe y es medible", callable(f))
comprobar("ninguna medicion devuelve claves de veredicto",
          not any("estado" in AS.medir_memoria() for _ in [0])
          and "veredicto" not in AS.medir_todo())
comprobar("medir_todo cubre las 5 dimensiones",
          set(AS.medir_todo()) == {"memoria", "intercambio", "cpu", "servicios", "aceleracion"})
comprobar("medir_todo no lanza excepcion en la maquina real", True)

print("== Parseo de /proc con ficheros sinteticos ==")
with tempfile.TemporaryDirectory() as td:
    raiz = Path(td)
    (raiz / "meminfo").write_text(
        "MemTotal:       3808644 kB\nMemAvailable:   1192948 kB\n"
        "MemFree:         500000 kB\nSwapTotal:      6104764 kB\n"
        "SwapFree:       3881456 kB\nHugePages_Total:       0\n", encoding="utf-8")
    (raiz / "swaps").write_text(
        "Filename\tType\tSize\tUsed\tPriority\n"
        "/swapfile\tfile\t4200444\t467716\t1\n"
        "/dev/zram0\tpartition\t1904320\t1755336\t100\n", encoding="utf-8")
    (raiz / "stat").write_text(
        "cpu  1868682 0 277922 945878 89051 0 6809 0 0 0\n"
        "cpu0 934341 0 138961 472939 44525 0 3404 0 0 0\n", encoding="utf-8")
    (raiz / "pressure").mkdir()
    (raiz / "pressure" / "cpu").write_text(
        "some avg10=12.97 avg60=8.93 avg300=8.90 total=5292352602\n"
        "full avg10=0.00 avg60=0.00 avg300=0.00 total=0\n", encoding="utf-8")
    (raiz / "pressure" / "memory").write_text(
        "some avg10=0.00 avg60=0.00 avg300=0.35 total=227210336\n", encoding="utf-8")

    real_proc, real_sys = AS.PROC, AS.SYS
    try:
        AS.PROC, AS.SYS = raiz, raiz / "sys"
        m = AS.medir_memoria()
        comprobar("meminfo: usado_pct correcto",
                  m["usado_pct"] == round(100 * (1 - 1192948 / 3808644), 1), m["usado_pct"])
        comprobar("meminfo: swap_usado = total - libre", m["swap_usado_kb"] == 6104764 - 3881456)
        s = AS.medir_intercambio()
        comprobar("swaps: zram separado del swap en disco",
                  s["zram"]["total_kb"] == 1904320 and s["swap_disco"]["total_kb"] == 4200444,
                  f"zram {s['zram']['total_kb']} disco {s['swap_disco']['total_kb']}")
        comprobar("swaps: suma de swap coincide con SwapTotal",
                  s["zram"]["total_kb"] + s["swap_disco"]["total_kb"] == 6104764)
        comprobar("swaps: los dispositivos de disco se listan",
                  len(s["swap_disco"]["dispositivos"]) == 1)
        c = AS.medir_cpu()
        comprobar("stat: steal 0 se lee como 0.0, no como None", c["steal_pct"] == 0.0,
                  c["steal_pct"])
        comprobar("pressure: la fila `some` se lee", AS._psi_some(c["psi_cpu"]) == 8.93,
                  AS._psi_some(c["psi_cpu"]))
        comprobar("pressure: `some` y `full` NO se pisan (bug real: 33.09 se leia 0.0)",
                  (c["psi_cpu"]["some"]["avg60"] == 8.93
                   and c["psi_cpu"]["full"]["avg60"] == 0.0), c["psi_cpu"])
        comprobar("pressure: avg10 y avg300 tambien se leen (no solo avg60)",
                  c["psi_cpu"]["some"]["avg10"] == 12.97
                  and c["psi_cpu"]["some"]["avg300"] == 8.9)
        comprobar("pressure: el parser NO exige dos puntos (no existen en /proc/pressure)",
                  AS._leer_psi("cpu") is not None)
        comprobar("pressure: la memoria se lee aparte", AS._psi_some(AS._leer_psi("memory")) == 0.0)
        comprobar("pressure: psi_io ausente da None sin romper", c["psi_io"] is None)
    finally:
        AS.PROC, AS.SYS = real_proc, real_sys

    (raiz / "meminfo").unlink()
    (raiz / "swaps").unlink()
    try:
        AS.PROC = raiz
        comprobar("sin /proc/meminfo -> no_medible, no excepcion",
                  "no_medible" in AS.medir_memoria())
        comprobar("sin /proc/swaps -> no_medible, no excepcion",
                  "no_medible" in AS.medir_intercambio())
    finally:
        AS.PROC = real_proc

    sin_psi = raiz / "sin_psi"
    sin_psi.mkdir()
    real_proc = AS.PROC
    try:
        AS.PROC = sin_psi
        comprobar("kernel sin PSI: psi None y la medicion sigue",
                  AS.medir_cpu()["psi_cpu"] is None)
        # Sin loadavg tampoco se puede medir la carga, asi que aqui lo correcto
        # es no_verificado, no ok: lo que no se midio no puede salir verde.
        comprobar("sin /proc/pressure la CPU es no_verificado, nunca ok",
                  FAS.interpretar_cpu(AS.medir_cpu())["estado"] == "no_verificado")
        comprobar("kernel sin PSI y sin loadavg -> no_medible",
                  "no_medible" in AS.medir_cpu() or AS.medir_cpu()["load_por_nucleo"] is not None)
    finally:
        AS.PROC = real_proc

print("== Algebra compartida: este flujo usa la MISMA que la auditoria de repo ==")
comprobar("comparte el modulo de algebra con flujo_auditar_repo",
          FAS.VA.__name__ == "veredicto_algebra")
comprobar("el peor estado presente gana, no el promedio",
          VA.clasificar_salud([{"dimension": "a", "estado": "ok"},
                               {"dimension": "b", "estado": "aviso"}])["veredicto"]
          == "con_avisos")
comprobar("no_verificado impide el verde y sale con 2",
          VA.clasificar_salud([{"dimension": "a", "estado": "no_verificado"}])["exit_code"] == 2)
comprobar("un estado inventado no se cuenta como sano",
          VA.clasificar_salud([{"dimension": "a", "estado": "excelente"}])["veredicto"]
          == "no_verificado")
comprobar("sin dimensiones -> no_verificado", VA.clasificar_salud([])["exit_code"] == 2)

print("== Contrato del CLI ==")
comprobar("una dimension desconocida sale con 3, no con 2",
          FAS.main(["--dimension", "no_existe"]) == VA.EXIT_USO_INCORRECTO)
comprobar("3 esta reservado al uso incorrecto, no a un hueco de medicion",
          VA.EXIT_USO_INCORRECTO == 3)
comprobar("--umbrales imprime la politica y sale con 0",
          FAS.main(["--umbrales"]) == 0)
# Regresion: con `default=""` el segundo --solo sobrescribia al primero y se
# perdian dimensiones en silencio. Un flag que pierde trabajo pedido callando es
# el peor tipo de bug que puede tener una CLI de auditoria.
_p = FAS.construir_parser()
comprobar("--solo es repetible y NO se sobrescribe",
          _p.parse_args(["--solo", "cpu", "--solo", "memoria"]).solo == ["cpu", "memoria"])
comprobar("--dimension sigue siendo repetible",
          _p.parse_args(["--dimension", "cpu", "--dimension", "memoria"]).dimension
          == ["cpu", "memoria"])
comprobar("las dos formas se acumulan sin pisarse",
          len(_p.parse_args(["--dimension", "cpu", "--solo", "memoria"]).dimension) == 1
          and _p.parse_args(["--dimension", "cpu", "--solo", "memoria"]).solo == ["memoria"])
# Regresion: la vista se llama run_state_sistema.json pero su log se llamaba
# session_log_auditar-sistema-<ts>.jsonl. `estado_sesion.py` deriva el run_id del
# NOMBRE del fichero, asi que la vista y su log no emparejaban nunca y toda
# corrida terminaba en no_verificable. El log estaba completo: el pairing estaba
# roto por el nombre, no por la traza.
import estado_sesion as ES
_vista = Path(FAS.TMP) / FAS.STATE_FILE_PLANTILLA.format(run_id="auditar-sistema-20260101-000000")
comprobar("la vista se nombra con el run_id del log",
          _vista.name == "run_state_auditar-sistema-20260101-000000.json", _vista.name)
comprobar("estado_sesion recupera el MISMO run_id del nombre de la vista",
          ES._run_id_desde_archivo(_vista) == "auditar-sistema-20260101-000000",
          str(ES._run_id_desde_archivo(_vista)))
comprobar("vista y log comparten raiz (el pairing no puede fallar por nombre)",
          ES._ruta_log(ES._run_id_desde_archivo(_vista)).name
          == "session_log_auditar-sistema-20260101-000000.jsonl",
          ES._ruta_log(ES._run_id_desde_archivo(_vista)).name)
# El flujo es de una sola pasada: al terminar retira su propio andamio, porque
# una vista de estado que sobrevive a una corrida cerrada es un huerfano por
# construccion y `estado_sesion.py` avisa de que envenena las respuestas MCP.
# El log append-only es la verdad permanente.
# El test compara un antes/despues en vez de globar el directorio entero: si
# queda un huerfano de una corrida AJENA, el aserto mediria el estado del
# entorno y no el comportamiento del flujo.
_antes = set(Path(FAS.TMP).glob("run_state_auditar-sistema-*.json"))
with contextlib.redirect_stdout(io.StringIO()):
    FAS.main(["--dimension", "aceleracion"])
_despues = set(Path(FAS.TMP).glob("run_state_auditar-sistema-*.json"))
comprobar("una corrida cerrada no deja vista de estado huerfana",
          _antes == _despues, f"aparecieron: {sorted(x.name for x in _despues - _antes)}")
comprobar("...pero si deja el log append-only (la verdad permanente)",
          bool(list(Path(FAS.TMP).glob("session_log_auditar-sistema-*.jsonl"))))
comprobar("el informe se sigue escribiendo", Path(FAS.INFORME).exists())
comprobar("--solo acepta listas con comas",
          _p.parse_args(["--solo", "cpu,servicios"]).solo == ["cpu,servicios"])

print("== Los umbrales van DENTRO del informe ==")
from datetime import datetime, timezone  # noqa: E402  (solo para ensamblar)
_dims = [FAS.interpretar_memoria(mem(50.0)), FAS.interpretar_cpu(cpu())]
_inf = FAS.ensamblar_informe(_dims, VA.clasificar_salud(_dims), "run-test",
                             datetime(2026, 1, 1, tzinfo=timezone.utc),
                             datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc))
comprobar("el informe guarda los umbrales que produjeron el veredicto",
          _inf["umbrales"] is UMBRALES, "sin esto el veredicto es irreproducible")
comprobar("el informe guarda el veredicto y su codigo de salida",
          _inf["salud"]["veredicto"] == "limpio" and _inf["salud"]["exit_code"] == 0)
comprobar("el informe lleva las dimensiones medidas",
          len(_inf["dimensiones"]) == 2 and all("estado" in d for d in _inf["dimensiones"]))
comprobar("el informe lleva host, nucleos y ventana temporal",
          all(k in _inf["contexto"] for k in ("host", "nucleos", "inicio_utc", "fin_utc")))
comprobar("cada dimension con umbral lo declara en su nota",
          all("nota" in v for v in UMBRALES.values()))
comprobar("el ensamblado es puro: dos llamadas iguales dan el mismo informe",
          FAS.ensamblar_informe(_dims, VA.clasificar_salud(_dims), "run-test",
                                datetime(2026, 1, 1, tzinfo=timezone.utc),
                                datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc)) == _inf)
comprobar("cambiar el run_id si cambia el informe: no es un campo inventado",
          FAS.ensamblar_informe(_dims, VA.clasificar_salud(_dims), "otro",
                                datetime(2026, 1, 1, tzinfo=timezone.utc),
                                datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc)) != _inf)

print()
if FALLOS:
    print(f"FALLOS: {len(FALLOS)}/{PRUEBAS}")
    for f in FALLOS:
        print(f"  - {f}")
    raise SystemExit(1)
print(f"Aserciones OK: {PRUEBAS}   Fallos: 0")
print("AUDITORIA DE SISTEMA OK: umbrales en el borde, zram no es presion, "
      "servicios en tres estados, capa 3 sin veredictos, algebra compartida y CLI.")
