#!/usr/bin/env python3
"""Capa 2: composicion de TODOS los verificadores de higiene del repo.

El repo tiene 13 verificadores independientes, cada uno con su propio dialecto de
exit code, y ninguno los consolidaba: cada `check` dejaba su JSON en `.tmp/` y
no habia ningun sitio donde mirar para responder "¿esta sano el proyecto?".
Este flujo es ese sitio.

Regla de diseno, y es la importante: NO hay puntuacion. Ninguna media ponderada
puede resumir esto, porque un estado catastrofico en una dimension (disco lleno,
credencial publicada) tiene que poder pesar mas que veinte dimensiones
sanas. Se aplica "gana el peor": el veredicto global es el peor estado observado,
y `no_verificado` impide decir "limpio" aunque todo lo demas lo este. Sin esa
regla, un fallo real se esconderia detras de un promedio favorable, que es
justo la clase de mentira que un informe de salud no debe contar.

Reutiliza lo existente en vez de reimplementarlo: las dimensiones marcadas como
`reutilizada` se delegan por subprocess. Este flujo no reimplementa la barrera
de borrado, ni la deteccion de secretos, ni el analisis de disco.

Solo lectura. Sin red, sin LLM, sin coste, sin borrados.

Uso:
    python3 flujo_auditar_repo.py                    # informe legible
    python3 flujo_auditar_repo.py --json
    python3 flujo_auditar_repo.py --rapido           # omite las dimensiones lentas
    python3 flujo_auditar_repo.py --solo texto,disco
Salida: 0 sin fallos (puede haber avisos), 1 con algun fallo real, 2 si no se
pudo comprobar todo, 3 error de uso.
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

RAIZ = Path(__file__).resolve().parent        # este flujo vive en la raiz del repo
EJECUCION = RAIZ / "execution"                 # capa 3
TMP = RAIZ / ".tmp"
STATE_FILE = TMP / "run_state.json"
INFORME = TMP / "auditoria_repo.json"
SESION_LOG = EJECUCION / "sesion_log.py"
PYTHON = sys.executable

sys.path.insert(0, str(EJECUCION))
import auditar_repo as AR  # noqa: E402  (capa 3, resolucion explicita)

# ---------------------------------------------------------------------------
# Prioridad de estados. De peor a mejor. "no_verificado" va por delante de todo
# porque no es un problema del sistema: es un limite de lo que sabemos, y un
# informe que no sabe algo no puede llamarse limpio.
# ---------------------------------------------------------------------------
PRIORIDAD = {"no_verificado": 3, "fallo": 2, "aviso": 1, "ok": 0}
VEREDICTO_POR_ESTADO = {
    "no_verificado": "no_verificado",
    "fallo": "con_fallos",
    "aviso": "con_avisos",
    "ok": "limpio",
}


def clasificar_salud(dimensiones: list[dict[str, Any]]) -> dict[str, Any]:
    """Funcion PURA: lista de dimensiones -> veredicto global.

    Sin promedio, sin pesos, sin puntuacion. Gana el peor estado presente, y la
    precedencia entre `no_verificado` y `fallo` es explicita: si hay algo roto
    se dice primero, porque es lo que hay que arreglar, aunque ademas haya
    dimensiones que no se pudieron medir. El veredicto final tambien lo dice.

    Es una funcion pura a proposito: se testea sola, sin ficheros ni git.
    """
    if not dimensiones:
        return {
            "veredicto": "no_verificado",
            "exit_code": 2,
            "motivo": "no se evaluo ninguna dimension: un informe sin dimensiones no informa",
            "conteo": {},
        }

    conteo: dict[str, int] = {}
    desconocidos: list[str] = []
    for d in dimensiones:
        estado = d.get("estado", "no_verificado")
        conteo[estado] = conteo.get(estado, 0) + 1
        # Un estado que no existe en el vocabulario NO se cuenta como sano. Sin
        # esta comprobacion, una dimension con un `estado` mal escrito caia
        # fuera de todos los `if` siguientes y salia como "limpio": un verde
        # falsoproduced por una errata en una cadena.
        if estado not in PRIORIDAD:
            desconocidos.append(d.get("dimension", "?"))

    if not conteo:
        return {
            "veredicto": "no_verificado", "exit_code": 2,
            "motivo": "ninguna dimension devolvio estado", "conteo": conteo,
        }

    if desconocidos:
        return {
            "veredicto": "no_verificado", "exit_code": 2,
            "motivo": (
                f"{len(desconocidos)} dimension(es) devolvieron un estado fuera del "
                f"vocabulario {sorted(PRIORIDAD)}: {', '.join(desconocidos)}. "
                "Un estado no reconocido se trata como no comprobado, nunca como sano."
            ),
            "conteo": conteo,
            "dimensiones_afectadas": desconocidos,
            "cobertura": {"medidas": 0, "no_medidas": len(dimensiones)},
        }

    # Peor estado presente, con la precedencia explicita de arriba.
    if conteo.get("fallo"):
        veredicto = "con_fallos"
        exit_code = 1
    elif conteo.get("no_verificado"):
        veredicto = "no_verificado"
        exit_code = 2
    elif conteo.get("aviso"):
        veredicto = "con_avisos"
        exit_code = 0
    else:
        veredicto = "limpio"
        exit_code = 0

    motivos = [d["dimension"] for d in dimensiones if d.get("estado") == "fallo"]
    if conteo.get("no_verificado"):
        motivos += [d["dimension"] for d in dimensiones
                    if d.get("estado") == "no_verificado"]

    return {
        "veredicto": veredicto,
        "exit_code": exit_code,
        "motivo": (
            f"{conteo.get('fallo', 0)} dimension(es) con fallo"
            + (f", {conteo.get('no_verificado', 0)} sin verificar" if conteo.get("no_verificado") else "")
            if veredicto != "limpio" else
            f"las {len(dimensiones)} dimensiones medidas no tienen fallos"
        ),
        "conteo": conteo,
        "dimensiones_afectadas": motivos,
        "cobertura": {
            "medidas": len(dimensiones) - conteo.get("no_verificado", 0),
            "no_medidas": conteo.get("no_verificado", 0),
        },
    }


# ---------------------------------------------------------------------------
# Dimensiones reutilizadas. Solo comandos de LECTURA.
#
# `interpreta` es funcion pura: (returncode, stdout) -> dict de la dimension.
# Nada de esto deduce el estado a ojo: cada interprete decide por su propia
# regla, y si no reconoce la salida devuelve `no_verificado` en vez de asumir
# que todo va bien.
# ---------------------------------------------------------------------------

def _json_o_texto(stdout: str) -> Any:
    try:
        return json.loads(stdout)
    except (ValueError, TypeError):
        return None


def _interpreta_texto(rc: int, stdout: str, timeout: bool) -> dict[str, Any]:
    """verificar_texto.py: 0 limpio, 1 hallazgos, 2 sin verificar."""
    if timeout:
        return _dim_no_verificado("timeout al ejecutarse")
    if rc == 0:
        return {"estado": "ok", "resumen": "sin corrupcion de prosa",
                "evidencia": {"exit_code": rc}}
    if rc == 1:
        n = stdout.count("[conocido]") + stdout.count("[script]") + stdout.count("[camel]")
        return {"estado": "fallo", "resumen": f"{n} corrupcion(es) de prosa",
                "evidencia": {"exit_code": rc}}
    return _dim_no_verificado(f"el verificador de texto salio con codigo {rc}")


def _interpreta_test(stdout: str, timeout: bool) -> dict[str, Any]:
    """Los tests del repo imprimen 'Aserciones OK: N   Fallos: M'."""
    if timeout:
        return _dim_no_verificado("timeout al ejecutarse")
    import re
    m = re.search(r"Aserciones OK:\s*(\d+)\s*Fallos:\s*(\d+)", stdout)
    if not m:
        if re.search(r"OK:", stdout) or re.search(r"VERIFICADOR DE TEXTO OK", stdout):
            return {"estado": "ok", "resumen": "test verde",
                    "evidencia": {"detalle": "sin linea de aserciones pero con marca OK"}}
        return _dim_no_verificado("el test no imprime una linea de aserciones reconocible")
    ok, malos = int(m.group(1)), int(m.group(2))
    return {
        "estado": "fallo" if malos else "ok",
        "resumen": f"{ok} aserciones, {malos} fallo(s)",
        "evidencia": {"aserciones": ok, "fallos": malos},
    }


def _interpreta_disco(rc: int, stdout: str, timeout: bool) -> dict[str, Any]:
    if timeout:
        return _dim_no_verificado("timeout al ejecutarse")
    datos = _json_o_texto(stdout)
    if not isinstance(datos, dict) or "filesystem" not in datos:
        return _dim_no_verificado("la salida no trae 'filesystem'")
    fs = datos["filesystem"]
    uso = fs.get("uso_pct")
    if uso is None:
        return _dim_no_verificado("el informe no trae uso_pct")
    # Umbral de 90: el mismo que usa flujo_disco.py para decidir purgar. Si se
    # supera aqui y no se knew antes, el disco crecio sin que nadie lo midiera.
    estado = "fallo" if uso >= 90 else ("aviso" if uso >= 80 else "ok")
    rec = (datos.get("recuperable") or {}).get("bytes", 0) or 0
    return {
        "estado": estado,
        "resumen": (
            f"disco al {uso}% ({fs.get('libre_gb', '?')} GB libres); "
            f"{rec / 1048576:.0f} MB recuperables con borrado seguro"
        ),
        "evidencia": {
            "uso_pct": uso, "libre_gb": fs.get("libre_gb"),
            "inodos_pct": fs.get("inodos_usados_pct"),
            "recuperable_mb": round(rec / 1048576, 1),
            "nota": "si uso>=90 y recuperable==0, purgar no ayudara: hace falta una decision",
        },
    }


def _interpreta_estado_sesion(rc: int, stdout: str, timeout: bool) -> dict[str, Any]:
    """estado_sesion.py: mapear por VEREDICTO de cada vista, no por el contador.

    `estado_sesion.py` mete en la misma bolsa `huerfano` y `corrupto` y lo
    publica como `anomalias`, asi que contar esa cifra trataria como fallo de
    integridad a una vista simplemente pendiente de purgar. Su vocabulario real:

        ok            la vista casa con su log append-only
        huerfano      la corrida termino; la vista sobrevivio (mantenimiento)
        corrupto      JSON invalido o sin run_id (integridad rota)
        no_verificable  sin log append-only; no se puede juzgar

    Solo `corrupto` es un fallo. El resto se ve sin bloquear.
    """
    if timeout:
        return _dim_no_verificado("timeout al ejecutarse")
    datos = _json_o_texto(stdout)
    if not isinstance(datos, dict) or "checks" not in datos:
        return _dim_no_verificado("la salida no trae 'checks'")

    por_veredicto: dict[str, list[str]] = {}
    for c in datos.get("checks", []):
        if isinstance(c, dict):
            por_veredicto.setdefault(str(c.get("veredicto", "?")), []).append(
                Path(str(c.get("archivo", "?"))).name)
    if not por_veredicto:
        return _dim_no_verificado("ninguna vista de estado que comprobar")

    corruptas = por_veredicto.get("corrupto", [])
    huerfanas = por_veredicto.get("huerfano", [])
    sin_juzgar = por_veredicto.get("no_verificable", [])

    if corruptas:
        return {
            "estado": "fallo",
            "resumen": f"{len(corruptas)} vista(s) de estado con integridad rota",
            "accion": (
                "Una vista de estado corrupta (JSON invalido o sin run_id) rompe la "
                "trazabilidad. Reconstruirla con `sesion_log.py state --run <id> "
                "--destino .tmp/run_state.json`."
            ),
            "evidencia": {"corruptas": corruptas, "huerfanas": huerfanas,
                          "sin_juzgar": sin_juzgar,
                          "veredicto_global": datos.get("veredicto_global")},
        }

    if huerfanas:
        return {
            "estado": "aviso",
            "resumen": (f"{len(huerfanas)} vista(s) de corrida terminada pendiente(s) "
                        f"de purgar" + (f"; {len(sin_juzgar)} sin log" if sin_juzgar else "")),
            "accion": (
                "Vistas huerfanas: la corrida ya termino y su estado sobrevive. "
                "Purgar con `python3 execution/estado_sesion.py clean`; es "
                "regenerable con `sesion_log.py state` y no se pierde nada real."
            ),
            "evidencia": {"huerfanas": huerfanas, "sin_juzgar": sin_juzgar,
                          "veredicto_global": datos.get("veredicto_global"),
                          "acciones_recomendadas": datos.get("acciones_recomendadas", [])},
        }

    if sin_juzgar:
        return {
            "estado": "aviso",
            "resumen": f"{len(sin_juzgar)} estado(s) sin log append-only; no juzgables",
            "accion": (
                "Hay estados sin log append-only, asi que no se pueden verificar. "
                "No se borran solos: son evidencia de flujos antiguos que no "
                "usaban `sesion_log.py`."
            ),
            "evidencia": {"sin_juzgar": sin_juzgar,
                          "veredicto_global": datos.get("veredicto_global")},
        }

    return {
        "estado": "ok",
        "resumen": f"{len(datos['checks'])} vista(s) de estado integra(s) y trazable(s)",
        "evidencia": {"por_veredicto": {k: len(v) for k, v in por_veredicto.items()},
                      "veredicto_global": datos.get("veredicto_global")},
    }


def _interpreta_bitacoras(rc: int, stdout: str, timeout: bool) -> dict[str, Any]:
    """bitacoras.py: 'bitacoras' es una lista y 'accionables' un entero."""
    if timeout:
        return _dim_no_verificado("timeout al ejecutarse")
    datos = _json_o_texto(stdout)
    if not isinstance(datos, dict) or "bitacoras" not in datos:
        return _dim_no_verificado("la salida no trae 'bitacoras'")
    accionables = datos.get("accionables")
    if not isinstance(accionables, int):
        return _dim_no_verificado("'accionables' no es un entero")
    total = len(datos.get("bitacoras", []))
    return {
        "estado": "fallo" if accionables else "ok",
        "resumen": f"{accionables} bitacora(s) accionable(s) de {total}",
        "evidencia": {
            "accionables": accionables,
            "total": total,
            "veredicto_global": datos.get("veredicto_global"),
            "hoy": datos.get("sesion_hoy", {}).get("fecha"),
        },
    }


def _dim_no_verificado(motivo: str) -> dict[str, Any]:
    return {
        "estado": "no_verificado",
        "resumen": f"NO SE PUDO COMPROBAR: {motivo}",
        "evidencia": {"motivo": motivo},
    }


DIMENSIONES_REUTILIZADAS: list[dict[str, Any]] = [
    {
        "nombre": "texto", "capa": "reutilizada",
        "descripcion": "corrupcion de prosa (caracteres intrusos, palabras fusionadas)",
        "script": "execution/verificar_texto.py", "args": [],
        "timeout": 900, "lenta": True, "interpreta": _interpreta_texto,
    },
    {
        "nombre": "estado_sesion", "capa": "reutilizada",
        "descripcion": "frescura de run_state frente a su log append-only",
        "script": "execution/estado_sesion.py", "args": ["check"],
        "timeout": 180, "lenta": False, "interpreta": _interpreta_estado_sesion,
    },
    {
        "nombre": "bitacoras", "capa": "reutilizada",
        "descripcion": "continuidad y completitud de Sessions/",
        "script": "execution/bitacoras.py", "args": ["check"],
        "timeout": 180, "lenta": False,
        "interpreta": _interpreta_bitacoras,
    },
    {
        "nombre": "disco", "capa": "reutilizada",
        "descripcion": "uso de filesystem e inodos, y cuanto es recuperable sin riesgo",
        "script": "execution/disco_medir.py", "args": [],
        "timeout": 300, "lenta": False, "interpreta": _interpreta_disco,
    },
    {
        "nombre": "barrera_disco", "capa": "reutilizada",
        "descripcion": "la barrera anti-borrado sigue intacta? (si no, el flujo de disco es peligroso)",
        "script": "execution/test_barrera_disco.py", "args": [],
        "timeout": 600, "lenta": True,
        "interpreta": lambda rc, out, to: _interpreta_test(out, to),
    },
    {
        "nombre": "test_texto", "capa": "reutilizada",
        "descripcion": "el propio detector de texto sigue pasando sus regresiones?",
        "script": "execution/test_verificar_texto.py", "args": [],
        "timeout": 900, "lenta": True,
        "interpreta": lambda rc, out, to: _interpreta_test(out, to),
    },
]

DIMENSIONES_NUEVAS = {
    nombre: fn for nombre, fn in AR.DIMENSIONES_NUEVAS.items()
}


def ejecutar_reutilizada(dim: dict[str, Any]) -> dict[str, Any]:
    cmd = [PYTHON, str(RAIZ / dim["script"]), *dim["args"]]
    timeout = False
    try:
        proc = subprocess.run(
            cmd, cwd=RAIZ, capture_output=True, text=True, timeout=dim["timeout"],
        )
        rc, salida = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        rc, salida, timeout = -1, "", True
    except OSError as exc:
        return {
            "dimension": dim["nombre"], "capa": "reutilizada", "estado": "no_verificado",
            "resumen": f"NO SE PUDO EJECUTAR: {exc}",
            "evidencia": {"script": dim["script"], "error": str(exc)},
            "accion": "El verificador existe en la tabla pero no se puede lanzar. Revisarlo.",
        }
    try:
        cuerpo = dim["interpreta"](rc, salida, timeout)
    except Exception as exc:                      # un interprete no debe tumbar la auditoria
        cuerpo = _dim_no_verificado(f"el interprete de '{dim['nombre']}' fallo: {exc}")
    return {
        "dimension": dim["nombre"], "capa": "reutilizada",
        "descripcion": dim["descripcion"], **cuerpo,
        "evidencia": {**cuerpo.get("evidencia", {}), "script": dim["script"], "exit_code": rc},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Auditoria de higiene del repo (compone los verificadores existentes).")
    ap.add_argument("--json", action="store_true", help="salida en JSON")
    ap.add_argument("--rapido", action="store_true", help="omitir las dimensiones lentas")
    ap.add_argument("--solo", default="", help="comas: restringir a estas dimensiones")
    ap.add_argument("--timeout-dim", type=int, default=0,
                    help="forzar timeout por dimension (0 = el de cada una)")
    args = ap.parse_args(argv)

    solo = {s.strip() for s in args.solo.split(",") if s.strip()}
    conocidas = {d["nombre"] for d in DIMENSIONES_REUTILIZADAS} | set(DIMENSIONES_NUEVAS)
    desconocidas = solo - conocidas
    if desconocidas:
        print(f"error: dimensiones desconocidas: {', '.join(sorted(desconocidas))}", file=sys.stderr)
        print(f"       disponibles: {', '.join(sorted(conocidas))}", file=sys.stderr)
        return 3

    TMP.mkdir(parents=True, exist_ok=True)
    run_id = f"auditoria-repo-{time.strftime('%Y%m%d-%H%M%S')}"
    inicio = datetime.now(timezone.utc)

    def trazar(tipo: str, datos: dict[str, Any]) -> bool:
        """Trazabilidad append-only. Falla blanda: devuelve False, no tumba el flujo."""
        try:
            proc = subprocess.run(
                [PYTHON, str(SESION_LOG), "add", "--run", run_id, "--tipo", tipo,
                 "--datos", json.dumps(datos, ensure_ascii=False)],
                cwd=RAIZ, capture_output=True, text=True, timeout=60,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return proc.returncode == 0

    if not trazar("flujo/inicio", {"dimensiones": sorted(solo) or sorted(conocidas), "rapido": args.rapido}):
        print("  aviso: no se pudo escribir 'flujo/inicio' en el log append-only", file=sys.stderr)

    dimensiones: list[dict[str, Any]] = []

    for nombre, fn in DIMENSIONES_NUEVAS.items():
        if solo and nombre not in solo:
            continue
        try:
            d = fn(RAIZ)
        except Exception as exc:
            d = {
                "dimension": nombre, "estado": "no_verificado",
                "resumen": f"NO SE PUDO COMPROBAR: la comprobacion lanzo {type(exc).__name__}: {exc}",
                "evidencia": {"excepcion": str(exc)},
            }
        d["capa"] = "nueva"
        dimensiones.append(d)

    for dim in DIMENSIONES_REUTILIZADAS:
        if solo and dim["nombre"] not in solo:
            continue
        if args.rapido and dim["lenta"]:
            continue
        if args.timeout_dim:
            dim = {**dim, "timeout": args.timeout_dim}
        dimensiones.append(ejecutar_reutilizada(dim))

    salud = clasificar_salud(dimensiones)
    fin = datetime.now(timezone.utc)
    informe = {
        "run_id": run_id,
        "generado": inicio.isoformat(),
        "duracion_s": round((fin - inicio).total_seconds(), 1),
        "salud": salud,
        "dimensiones": dimensiones,
        "nota_metodologica": (
            "Sin puntuacion ni promedio: el veredicto es el peor estado presente. "
            "Una dimension no verificable impide declarar el conjunto limpio."
        ),
    }

    INFORME.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    STATE_FILE.write_text(json.dumps({
        "run_id": run_id, "current_step": 1, "status": salud["veredicto"],
        "salud": salud, "exit_code": salud["exit_code"],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    if not trazar("flujo/fin", {"veredicto": salud["veredicto"], "exit_code": salud["exit_code"]}):
        print("  aviso: no se pudo escribir 'flujo/fin' en el log append-only", file=sys.stderr)

    if args.json:
        print(json.dumps(informe, ensure_ascii=False, indent=2))
        return salud["exit_code"]

    print("== Auditoria de higiene del repo ==")
    print(f"  {len(dimensiones)} dimensiones medidas en {informe['duracion_s']}s\n")
    marcas = {"ok": "ok        ", "aviso": "AVISO     ",
              "fallo": "FALLO     ", "no_verificado": "SIN VERIF."}
    for d in sorted(dimensiones, key=lambda x: -PRIORIDAD.get(x.get("estado", "no_verificado"), 9)):
        print(f"  [{marcas.get(d.get('estado'), '?        ')}] {d['dimension']:16} {d.get('resumen', '')}")
    print(f"\n  VEREDICTO: {salud['veredicto']}  (exit {salud['exit_code']})")
    print(f"  {salud['motivo']}")
    if salud["veredicto"] != "limpio":
        print("\n  Que hacer, en orden de gravedad:")
        pendientes = [d for d in dimensiones
                      if d.get("estado") in ("fallo", "aviso", "no_verificado") and d.get("accion")]
        for d in sorted(pendientes, key=lambda x: -PRIORIDAD.get(x.get("estado", "no_verificado"), 9)):
            print(f"    [{d.get('estado', '?'):13}] {d['dimension']}: {d['accion']}")
    print(f"\n  Informe completo: {INFORME.relative_to(RAIZ)}")

    return salud["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
