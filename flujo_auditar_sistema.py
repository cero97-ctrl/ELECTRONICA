#!/usr/bin/env python3
"""Capa 2 (`orquestacion`) de `auditar_sistema`: RAM, CPU, servicios, GPU.

Solo LECTURA. No purga, no reinicia, no escribe fuera de `.tmp/`, no necesita
sudo. Auditar el sistema y mantenerlo son dos flujos distintos a proposito: si
esteissea el que purga, un veredicto de `fallo` y un borrado serian el mismo
comando, y entonces la tentacion de "arreglarlo" dejan de ser una decision
consciente. `system_maintenance.yaml` sigue siendo el sitio de purgar.

Que aporta frente a `flujo_diagnostico.py`, que ya mide RAM, CPU y disco: este
flujo no imprime numeros, **emite veredicto y codigo de salida**. La diferencia
es la que importa en automatismo: un informe que dice "carga 1.3" no se puede
enmarcar; uno que dice "con_avisos, exit 0" se puede.

Diseno, y por que:

- El algebra de estados es la MISMA de la auditoria de repo, extraida a
  `execution/veredicto_algebra.py`. Dos flujos con dos algebras distintas
  divergen en silencio, que es la forma mas cara de equivocarse en un modulo
  cuya unica razon de ser es la consistencia. Peor estado presente, nunca un
  promedio; `no_verificado` impide el verde.
- Los umbrales NO son parametros de linea de comandos. Son constantes, y se
  **imprimen dentro del informe**: la misma maquina con umbrales distintos da
  veredictos distintos, asi que un informe que no dice que umbrales uso es
  irreproducible por construccion.
- Los interpretes son funciones PURAS `(medicion) -> dimension`: sin ficheros,
  sin procesos, sin hora. Se testean enteras.
- `servicios` distingue `not-found` (no instalado, no juzgable) de `failed` (si
  juzgable). Sin esa distincion, instalar el repo en una maquina sin
  Waydroid produciria un `fallo` falso.
- `aceleracion` devuelve `ok` aunque no haya GPU, porque la ausencia de GPU es un
  HECHO del entorno, no un defecto. Marcarla `aviso` haria que el veredicto
  global no pudiese ser `limpio` nunca en esta maquina, y un veredicto que no
  puede distinguir "todo bien" de "todo bien y sin GPU" no sirve para detectar
  una degradacion real. El hecho y la regla de Colab van en el resumen y en la
  accion, que se emiten siempre.

Codigos de salida: 0 limpio/con avisos, 1 con fallos, 2 sin verificar (reservado:
nunca verde), 3 uso incorrecto de flags.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

RAIZ = Path(__file__).resolve().parent
EJECUCION = RAIZ / "execution"
TMP = RAIZ / ".tmp"
# La vista se nombra DESPUES del run_id, no antes. `estado_sesion.py` deriva el
# run_id del nombre del fichero (ver _run_id_desde_archivo): una vista llamada
# run_state_sistema.json busca session_log_sistema.jsonl, que no existe, y
# acaba en no_verificable aunque su log este completo. El nombre de la vista y
# el del log tienen que llevar el MISMO run_id.
STATE_FILE_PLANTILLA = "run_state_{run_id}.json"
INFORME = TMP / "auditoria_sistema.json"
SESION_LOG = EJECUCION / "sesion_log.py"
PYTHON = sys.executable

sys.path.insert(0, str(EJECUCION))
import auditar_sistema as AS  # noqa: E402  (capa 3, medicion)
import veredicto_algebra as VA  # noqa: E402  (capa 3, algebra compartida)

# ---------------------------------------------------------------------------
# Umbrales. Constantes, no flags: se documentan en el informe para que el
# veredicto sea reproducible. Cambiarlos es cambiar la politica, y eso se
# committea, no se pasa por linea de comandos.
# ---------------------------------------------------------------------------
UMBRALES: dict[str, Any] = {
    "memoria": {
        "aviso_pct": 75.0,
        "fallo_pct": 90.0,
        "nota": "sobre MemAvailable, no MemFree: MemAvailable es lo que el kernel "
                "calcula para 'cuanto puedo pedir sin swap'",
    },
    "intercambio": {
        # Solo swap EN DISCO. El llenado de zram es su estado de diseno.
        "aviso_pct": 70.0,
        "fallo_pct": 90.0,
        "zram_lleno_es_normal": True,
        "nota": "zram lleno no es presion de memoria; el swap en disco si lo es",
    },
    "cpu": {
        "indice_load": 1,  # loadavg de 5 min: el de 1 min es espurio y el de 15 lagea
        "aviso_por_nucleo": 1.0,
        "fallo_por_nucleo": 2.0,
        "aviso_steal_pct": 10.0,
        "fallo_steal_pct": 25.0,
        "aviso_psi_cpu_avg60": 25.0,
        "fallo_psi_cpu_avg60": 50.0,
        "psi_io_informa_pero_no_verdicta": True,
        "nota": "carga normalizada por nucleos (load 2 en 2 nucleos es saturacion, "
                "en 16 es ocioso); steal y PSI de CPU pueden solo EMPEORAR el "
                "estado, nunca mejorarlo",
    },
    "servicios": {
        "nota": "not-found = no instalado = no_verificado; failed = fallo; "
                "inactive = instalado y parado = aviso",
    },
    "aceleracion": {
        "sin_gpu_es_ok": True,
        "nota": "la ausencia de GPU discreta es un hecho del entorno, no un "
                "defecto: se registra con estado ok y la regla de Colab va en "
                "el resumen y la accion",
    },
}

# ---------------------------------------------------------------------------
# Interpretes. Funciones PURAS: (medicion) -> dimension. Sin I/O, sin reloj.
# ---------------------------------------------------------------------------

def _peor(estados: list[str]) -> str:
    return max(estados, key=lambda e: VA.PRIORIDAD.get(e, 3))


def interpretar_memoria(m: dict[str, Any]) -> dict[str, Any]:
    if "no_medible" in m:
        return {"dimension": "memoria", "estado": "no_verificado",
                "resumen": m["no_medible"], "evidencia": m,
                "accion": "No se pudo leer la memoria: el veredicto no puede ser "
                          "verde con un hueco. Revisar /proc/meminfo y el kernel."}
    pct = m["usado_pct"]
    u = UMBRALES["memoria"]
    estado = "fallo" if pct >= u["fallo_pct"] else "aviso" if pct >= u["aviso_pct"] else "ok"
    accion = {
        "ok": f"RAM con holgura: {pct}% usada, {m['disponible_kb']} kB disponibles.",
        "aviso": f"RAM al {pct}% ({UMBRALES['memoria']['aviso_pct']}% es el umbral). "
                 "Revisar consumidores antes de que llegue al 90%.",
        "fallo": f"RAM al {pct}%, por encima del {UMBRALES['memoria']['fallo_pct']}%. "
                 "Este flujo NO purga: usar flujo_disco o mantenimiento manual.",
    }[estado]
    return {
        "dimension": "memoria", "estado": estado,
        "resumen": f"RAM al {pct}% usada ({m['total_kb']} kB totales, "
                   f"{m['disponible_kb']} kB disponibles)",
        "evidencia": m, "accion": accion,
    }


def interpretar_intercambio(m: dict[str, Any]) -> dict[str, Any]:
    if "no_medible" in m:
        return {"dimension": "intercambio", "estado": "no_verificado",
                "resumen": m["no_medible"], "evidencia": m,
                "accion": "No se pudo leer /proc/swaps: no juzgable."}
    disco = m["swap_disco"]
    zram = m["zram"]
    u = UMBRALES["intercambio"]
    if not disco["total_kb"] and not zram["total_kb"]:
        return {"dimension": "intercambio", "estado": "ok",
                "resumen": "Sin intercambio configurado (ni zram ni swap en disco)",
                "evidencia": m,
                "accion": "Nada que hacer: con 3.6 GB de RAM y sin swap el kernel "
                          "puede matar procesos, pero no habria disco lento."}
    pct = disco["usado_pct"] if disco["total_kb"] else 0.0
    estado = "fallo" if pct >= u["fallo_pct"] else "aviso" if pct >= u["aviso_pct"] else "ok"
    razon = ""
    if zram["dispositivos"] and zram["dispositivos"][0].get("razon_compresion"):
        razon = (f" zram al {zram['usado_pct']}% con compresion "
                 f"{zram['dispositivos'][0]['razon_compresion']}x, que es su "
                 "estado de diseno y NO cuenta como presion.")
    accion = {
        "ok": f"Swap en disco al {pct}% de {disco['total_kb']} kB: sin presion."
              + (f" zram al {zram['usado_pct']}% con compresion "
                 f"{zram['dispositivos'][0].get('razon_compresion', '?')}x, "
                 "normal para RAM comprimida." if zram["presente"] else ""),
        "aviso": f"Swap en disco al {pct}%: por encima del {u['aviso_pct']}%. "
                 "Cerrar aplicaciones pesadas antes de que vaya a mas.",
        "fallo": f"Swap en disco al {pct}%, por encima del {u['fallo_pct']}% con "
                 "20.3 GB de disco al 91%: paginacion activa con el disco casi "
                 "lleno. Este flujo no purga nada; la decision es del operador.",
    }[estado]
    return {
        "dimension": "intercambio", "estado": estado,
        "resumen": f"swap en disco {pct}%"
                   + (f"; zram {zram['usado_pct']}% (normal)" if zram["presente"] else ""),
        "evidencia": m, "accion": accion + razon,
    }


def interpretar_cpu(m: dict[str, Any]) -> dict[str, Any]:
    if "no_medible" in m or not m.get("load_por_nucleo"):
        return {"dimension": "cpu", "estado": "no_verificado",
                "resumen": m.get("no_medible", "loadavg no disponible"),
                "evidencia": m,
                "accion": "No se pudo medir la carga: el veredicto no puede ser verde."}
    u = UMBRALES["cpu"]
    por_nucleo = m["load_por_nucleo"]
    idx = u["indice_load"]
    carga = por_nucleo[idx]
    etiquetas = ["1 min", "5 min", "15 min"]
    estado = ("fallo" if carga >= u["fallo_por_nucleo"]
              else "aviso" if carga >= u["aviso_por_nucleo"] else "ok")
    razones: list[str] = []

    # steal y PSI solo pueden EMPEORAR. Una CPU con steal alto puede tener load
    # bajo y seguir siendo lentisima, y ese caso es invisible con el load solo.
    steal = m.get("steal_pct")
    if steal is not None:
        if steal >= u["fallo_steal_pct"]:
            estado = _peor([estado, "fallo"])
            razones.append(f"steal al {steal}%: el anfitrion roba el CPU")
        elif steal >= u["aviso_steal_pct"]:
            estado = _peor([estado, "aviso"])
            razones.append(f"steal al {steal}%: el anfitrion roba parte del CPU")
    psi_cpu = AS._psi_some(m.get("psi_cpu"))
    if psi_cpu is not None:
        if psi_cpu >= u["fallo_psi_cpu_avg60"]:
            estado = _peor([estado, "fallo"])
            razones.append(f"PSI de CPU al {psi_cpu}% (avg60): hay procesos esperando")
        elif psi_cpu >= u["aviso_psi_cpu_avg60"]:
            estado = _peor([estado, "aviso"])
            razones.append(f"PSI de CPU al {psi_cpu}% (avg60)")
    psi_io = AS._psi_some(m.get("psi_io"))
    if psi_io is not None:
        razones.append(f"PSI de E/S al {psi_io}% (avg60, informativo: disco, no CPU)")

    accion = {
        "ok": f"Carga sostenida de {carga} por nucleo en {etiquetas[idx]}: "
              f"holgura sobre {m['nucleos']} nucleos.",
        "aviso": f"Carga de {carga} por nucleo en {etiquetas[idx]} (umbral "
                 f"{u['aviso_por_nucleo']}): el equipo va tirado de CPU. Ojo: este "
                 "flujo puede estar midiendo su propia carga si corre junto a un "
                 "trabajo pesado.",
        "fallo": f"Carga de {carga} por nucleo en {etiquetas[idx]}, por encima de "
                 f"{u['fallo_por_nucleo']}: saturacion.",
    }[estado]
    if razones:
        accion += " " + "; ".join(razones) + "."
    return {
        "dimension": "cpu", "estado": estado,
        "resumen": f"carga {carga}/nucleo ({etiquetas[idx]}) sobre {m['nucleos']} "
                   f"nucleos; loadavg {m['loadavg']}; steal {steal}%",
        "evidencia": m, "accion": accion,
    }


def interpretar_servicios(m: dict[str, Any]) -> dict[str, Any]:
    if "no_medible" in m:
        return {"dimension": "servicios", "estado": "no_verificado",
                "resumen": m["no_medible"], "evidencia": m,
                "accion": "Sin systemd no se puede juzgar el estado de los servicios."}
    if not m.get("servicios"):
        return {"dimension": "servicios", "estado": "no_verificado",
                "resumen": "systemctl respondio pero sin unidades",
                "evidencia": m, "accion": "No se obtuvo ninguna unidad."}
    detalle: list[dict[str, Any]] = []
    for s in m["servicios"]:
        load, active = s.get("LoadState", "?"), s.get("ActiveState", "?")
        # `LoadState` va primero y es el que decide si la unidad existe. Sin esa
        # comprobacion, "inactive" mezclaria "no instalado" con "instalado y
        # parado", que son cosas opuestas.
        if load != "loaded":
            est = "no_verificado"          # no instalado / masked / error
        elif active == "failed":
            est = "fallo"                  # instalado y caido: si juzgable
        elif active == "active":
            est = "ok"
        elif active in ("inactive", "activating", "deactivating", "reloading"):
            est = "aviso"                  # instalado y no en pie
        else:
            est = "no_verificado"
        detalle.append({"unidad": s.get("Id", "?"), "load": load, "active": active,
                        "sub": s.get("SubState", "?"), "estado": est})
    estado = _peor([d["estado"] for d in detalle])
    caidos = [d["unidad"] for d in detalle if d["estado"] in ("fallo", "aviso")]
    ausentes = [d["unidad"] for d in detalle if d["estado"] == "no_verificado"]
    ok = [d["unidad"] for d in detalle if d["estado"] == "ok"]
    if estado == "ok":
        accion = f"En pie: {', '.join(ok)}."
    elif estado == "fallo":
        accion = (f"Caidos: {', '.join(caidos)}. Este flujo solo mira: se arrancan "
                  "con sudo ./manage_bot.sh o sudo ./manage_waydroid.sh.")
    elif estado == "aviso":
        accion = f"Parados o arrancando: {', '.join(caidos)}."
    else:
        accion = f"No instalados: {', '.join(ausentes)}: no juzgables."
    return {
        "dimension": "servicios", "estado": estado,
        "resumen": f"{len(ok)}/{len(detalle)} en pie"
                   + (f"; caidos: {', '.join(caidos)}" if caidos else "")
                   + (f"; no instalados: {', '.join(ausentes)}" if ausentes else ""),
        "evidencia": {**m, "detalle": detalle}, "accion": accion,
    }


def interpretar_aceleracion(m: dict[str, Any]) -> dict[str, Any]:
    if m.get("gpu_discreta"):
        return {"dimension": "aceleracion", "estado": "ok",
                "resumen": f"GPU discreta presente: {', '.join(m['modelos'])}",
                "evidencia": m,
                "accion": "Hay GPU, pero 3.6 GB de RAM siguen siendo el limite real: "
                          "el entrenamiento puede morir por RAM, no por VRAM."}
    return {
        "dimension": "aceleracion", "estado": "ok",
        "resumen": "sin GPU discreta ("
                   + (", ".join(m["modelos"]) if m.get("modelos") else "ninguna detectada")
                   + "); el entrenamiento va a Google Colab con TensorFlow",
        "evidencia": m,
        "accion": "Aqui solo es legitimo: inferencia, prototipos y validacion. "
                  "Para entrenar, Google Colab con TensorFlow y el canario "
                  "docs/COLAB/entorno_colab.ipynb. Es un hecho del entorno, no un "
                  "defecto: por eso no degrada el veredicto.",
    }


DIMENSIONES: list[dict[str, Any]] = [
    {"nombre": "memoria", "descripcion": "RAM usada sobre MemAvailable",
     "medir": AS.medir_memoria, "interpreta": interpretar_memoria},
    {"nombre": "intercambio", "descripcion": "zram y swap en disco, por separado",
     "medir": AS.medir_intercambio, "interpreta": interpretar_intercambio},
    {"nombre": "cpu", "descripcion": "carga por nucleo, steal y presion PSI",
     "medir": AS.medir_cpu, "interpreta": interpretar_cpu},
    {"nombre": "servicios", "descripcion": "estado de los servicios que declara el repo",
     "medir": AS.medir_servicios, "interpreta": interpretar_servicios},
    {"nombre": "aceleracion", "descripcion": "GPU presente; regla de Colab",
     "medir": AS.medir_aceleracion, "interpreta": interpretar_aceleracion},
]


def ensamblar_informe(dimensiones: list[dict[str, Any]], global_: dict[str, Any],
                      run_id: str, inicio: datetime, fin: datetime) -> dict[str, Any]:
    """Funcion PURA: dimensiones + algebra -> informe.

    Vive fuera de `main()` por un motivo concreto: el invariante de que los
    umbrales van DENTRO del informe (sin ellos el veredicto es irreproducible)
    solo se puede comprobar si el ensamblado se puede llamar sin ejecutar el
    flujo, que escribe en `.tmp/`.
    """
    return {
        "salud": {
            "veredicto": global_["veredicto"],
            "exit_code": global_["exit_code"],
            "motivo": global_["motivo"],
            "conteo": global_["conteo"],
            "dimensiones_afectadas": global_["dimensiones_afectadas"],
            "cobertura": global_["cobertura"],
        },
        # Sin esto el informe es irreproducible: la misma maquina con otros
        # umbrales daria otro veredicto y nadie podria saber con cuales se hizo.
        "umbrales": UMBRALES,
        "dimensiones": dimensiones,
        "contexto": {
            "run_id": run_id, "inicio_utc": inicio.isoformat(), "fin_utc": fin.isoformat(),
            "duracion_s": round((fin - inicio).total_seconds(), 3),
            "host": _hostname(), "nucleos": _cpus(),
        },
        "notas": [
            "Solo lectura: este flujo no purga, no reinicia y no necesita sudo.",
            "El veredicto es el PEOR estado presente, nunca un promedio.",
            "El flujo puede medir su propia carga de CPU: un aviso de cpu con un "
            "trabajo pesado corriendo a la vez no es necesariamente una averia.",
        ],
    }


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Audita RAM, CPU, servicios y aceleracion. Solo lectura, no purga.",
        epilog="Codigos: 0 limpio/con avisos, 1 con fallos, 2 sin verificar, 3 uso incorrecto.",
    )
    p.add_argument("--dimension", action="append", default=[], metavar="NOMBRE",
                   help="repetible; solo audita esa dimension")
    p.add_argument("--solo", action="append", default=[], metavar="A,B",
                   help="alias de lista para --dimension; repetible, y las "
                        "repeticiones se unen en vez de sobrescribirse")
    p.add_argument("--json", action="store_true", help="informe completo en stdout")
    p.add_argument("--umbrales", action="store_true",
                   help="imprime los umbrales aplicados y termina")
    return p


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)

    if args.umbrales:
        print(json.dumps({"umbrales": UMBRALES}, ensure_ascii=False, indent=2))
        return 0

    # Ver flujo_auditar_repo.py: `--solo` es append a proposito, porque con
    # `default=""` la segunda repeticion borraba a la primera en silencio.
    pedidas = set(args.dimension)
    for bloque in args.solo:
        pedidas |= {d.strip() for d in bloque.split(",") if d.strip()}
    conocidas = {d["nombre"] for d in DIMENSIONES}
    desconocidas = pedidas - conocidas
    if desconocidas:
        print(f"error: dimensiones desconocidas: {', '.join(sorted(desconocidas))}",
              file=sys.stderr)
        print(f"       disponibles: {', '.join(sorted(conocidas))}", file=sys.stderr)
        return VA.EXIT_USO_INCORRECTO

    TMP.mkdir(parents=True, exist_ok=True)
    run_id = f"auditar-sistema-{time.strftime('%Y%m%d-%H%M%S')}"
    ruta_estado = TMP / STATE_FILE_PLANTILLA.format(run_id=run_id)
    inicio = datetime.now(timezone.utc)

    def trazar(tipo: str, datos: dict[str, Any]) -> bool:
        """Trazabilidad append-only. Falla blanda: no tumba el flujo."""
        try:
            proc = subprocess.run(
                [PYTHON, str(SESION_LOG), "add", "--run", run_id, "--tipo", tipo,
                 "--datos", json.dumps(datos, ensure_ascii=False)],
                cwd=RAIZ, capture_output=True, text=True, timeout=60,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return proc.returncode == 0

    trazar("flujo/inicio", {"dimensiones": sorted(pedidas) or sorted(conocidas)})
    # La vista existe para que, si el proceso muere a medias, se vea hasta donde
    # llego. En exito NO debe sobrevivir: una corrida terminada con vista puesta
    # es un huerfano por construccion, y `estado_sesion.py` avisa de que los
    # huerfanos envenenan las respuestas MCP. El log append-only es la verdad
    # permanente; la vista es solo un andamio.
    ruta_estado.write_text(json.dumps(
        {"run_id": run_id, "paso": "midiendo", "terminado": False,
         "log": f"session_log_{run_id}.jsonl", "timestamp": inicio.isoformat()},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    dimensiones: list[dict[str, Any]] = []
    for spec in DIMENSIONES:
        if pedidas and spec["nombre"] not in pedidas:
            continue
        t0 = time.perf_counter()
        try:
            medicion = spec["medir"]()
        except Exception as exc:  # una medicion rota no puede tumbar el informe
            dimensiones.append({
                "dimension": spec["nombre"], "estado": "no_verificado",
                "resumen": f"la medicion lanzo {type(exc).__name__}: {exc}",
                "evidencia": {}, "duracion_s": round(time.perf_counter() - t0, 3),
                "accion": "Medicion fallida: se corrige el script, no el veredicto.",
            })
            continue
        d = spec["interpreta"](medicion)
        d["duracion_s"] = round(time.perf_counter() - t0, 3)
        dimensiones.append(d)
        trazar("dimension/medida", {"dimension": d["dimension"], "estado": d["estado"]})

    global_ = VA.clasificar_salud(dimensiones)
    fin = datetime.now(timezone.utc)
    informe = ensamblar_informe(dimensiones, global_, run_id, inicio, fin)
    INFORME.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    trazar("flujo/fin", {"veredicto": global_["veredicto"],
                         "exit_code": global_["exit_code"]})
    # La corrida cerro: se retira el andamio. El log append-only queda intacto.
    try:
        ruta_estado.unlink()
    except OSError:
        pass  # un andamio que no se puede retirar no puede tumbar el informe

    if args.json:
        print(json.dumps(informe, ensure_ascii=False, indent=2))
    else:
        _imprimir_informe(informe)
    return global_["exit_code"]


def _hostname() -> str:
    try:
        return __import__("socket").gethostname()
    except OSError:
        return "desconocido"


def _cpus() -> int:
    import os
    return os.cpu_count() or 0


def _imprimir_informe(info: dict[str, Any]) -> None:
    salud = info["salud"]
    ancho = max(len(d["dimension"]) for d in info["dimensiones"])
    print(f"\n  AUDITORIA DE SISTEMA  ({info['contexto']['host']}, "
          f"{info['contexto']['nucleos']} nucleos)")
    print("  " + "-" * (ancho + 52))
    for d in info["dimensiones"]:
        etiqueta = {"ok": "ok", "aviso": "aviso", "fallo": "FALLO",
                    "no_verificado": "no verif"}[d["estado"]]
        print(f"  [{etiqueta:<8}] {d['dimension']:<{ancho}}  "
              f"[{d['duracion_s']:>6.2f}s] {d['resumen']}")
    print("  " + "-" * (ancho + 52))
    print(f"\n  VEREDICTO: {salud['veredicto']}  (exit {salud['exit_code']})")
    if salud["dimensiones_afectadas"]:
        print("\n  Que hacer, en orden de gravedad:")
        for d in info["dimensiones"]:
            if d["estado"] != "ok":
                print(f"    [{d['estado']:<8}] {d['dimension']}: {d['accion']}")
    print(f"\n  Informe completo: {INFORME.relative_to(RAIZ)}")


if __name__ == "__main__":
    raise SystemExit(main())
