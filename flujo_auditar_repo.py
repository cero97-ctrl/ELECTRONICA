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
import veredicto_algebra as VA  # noqa: E402  (capa 3, algebra compartida)

# ---------------------------------------------------------------------------
# Algebra de veredictos: vive en CAPA 3 (`execution/veredicto_algebra.py`) porque
# `flujo_auditar_sistema.py` necesita exactamente la misma y duplicarla
# produciria dos verdades divergiendo en silencio. Se reexporta aqui con estos
# nombres porque el modulo entero, sus interpretes y sus 123 tests los usan.
# ---------------------------------------------------------------------------
PRIORIDAD = VA.PRIORIDAD
VEREDICTO_POR_ESTADO = VA.VEREDICTO_POR_ESTADO
clasificar_salud = VA.clasificar_salud


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


AMBITO_DISCO = (
    "solo la whitelist del proyecto (execution/catalogo_disco.py, validada por "
    "la barrera); no incluye /var/lib/docker, /var/lib/waydroid, /var/lib/containerd "
    "ni ninguna ruta de root"
)


def _accion_disco(estado: str, rec_mb: float | None) -> str:
    """Accion de la dimension `disco`.

    Antes de este cambio el interprete no devolvia clave `accion`, de modo que
    `disco` --que suele ser la dimension en `fallo`-- no aparecia entre las
    acciones de la seccion "Que hacer, en orden de gravedad". La dimension mas
    grave era la unica que callaba.

    El texto dice la verdad incomoda: lo que el flujo puede liberar es
    irrelevante frente a lo que el disco tiene ocupado fuera de su alcance. Las
    cifras (43.6 GB de imagenes Docker) son una medicion con fecha, no un
    contrato, asi que van en el documento y en la bitacora, no aqui: este
    resumen tiene que ser estable entre corridas.
    """
    if estado != "fallo":
        return ("Fuera de umbral de purga. La cifra recuperable es solo la del "
                f"proyecto ({AMBITO_DISCO}); no dice nada del resto del disco.")
    if rec_mb is None:
        return ("Lo recuperable no se puede cuantificar: disco_medir.py no lo "
                "informo. Ausencia de dato, no cero, asi que no se puede afirmar "
                "que el margen sea poco ni mucho. Reintentar la medicion antes de "
                "decidir nada; si se confirma, la cifra sera de la whitelist y el "
                "margen real quedara fuera del alcance del flujo.")
    return (
        "El flujo casi no puede hacer nada por si mismo: lo recuperable por su "
        "cuenta es irrelevante. El margen real esta FUERA de su whitelist, en rutas de root "
        "que `du` no puede leer sin privilegios (imagenes de Docker, Waydroid, "
        "containerd), asi que hace falta una decision del operador; el flujo no "
        "las toca y no debe. Ojo con `docker system prune -a`: tambien se lleva "
        "las imagenes de build del proyecto (kicad/kicad:8.0, pcb_sandbox, "
        "agent-sandbox), que habria que volver a descargar."
    )


def _interpreta_disco(rc: int, stdout: str, timeout: bool) -> dict[str, Any]:
    """disco_medir.py: el estado lo decide `filesystem.uso_pct`.

    Sobre los bytes recuperables hay que ser exquisito. La version anterior leia
    `datos["recuperable"]`, clave que `disco_medir.py` NUNCA ha emitido: el
    numero vivia en `resumen_catalogo.reclaimable_por_tier.seguro.bytes`. Como
    la clave no existia, `rec` valia siempre 0 y el informe afirmaba "0 MB
    recuperables" como si fuera un dato medido. No lo era: era una clave
    ausente. Un `or 0` sobre algo opcional convierte "no lo sé" en "cero", y
    "cero" es un hecho; "no lo sé" es una laguna. Por eso aqui la ausencia del
    resumen se declara en vez de rellenarse con un cero.
    """
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
    # supera aqui y no se midio antes, el disco crecio sin que nadie lo midiera.
    estado = "fallo" if uso >= 90 else ("aviso" if uso >= 80 else "ok")

    # Bytes realmente recuperables SIN riesgo, segun el catalogo ya validado
    # por la barrera. Si el resumen no viene, no se inventa la cifra.
    seguro = ((datos.get("resumen_catalogo") or {})
              .get("reclaimable_por_tier", {})
              .get("seguro") or {})
    rec_bytes = seguro.get("bytes")
    if isinstance(rec_bytes, (int, float)):
        legible = f"{rec_bytes / 1048576:.1f} MB recuperables con borrado seguro"
        rec_mb = round(rec_bytes / 1048576, 1)
    else:
        legible = "recuperable no informado por disco_medir.py"
        rec_mb = None

    return {
        "estado": estado,
        "resumen": (f"disco al {uso}% ({fs.get('libre_gb', '?')} GB libres); "
                    f"{legible} [ambito: {AMBITO_DISCO}]"),
        "accion": _accion_disco(estado, rec_mb),
        "evidencia": {
            "uso_pct": uso, "libre_gb": fs.get("libre_gb"),
            "inodos_pct": fs.get("inodos_usados_pct"),
            "recuperable_mb": rec_mb,
            "ambito": AMBITO_DISCO,
            "nota": (
                "si uso>=90 y recuperable_mb==0, purgar no ayudara: hace falta una "
                "decision. Si recuperable_mb es null, el dato no vino y hay que "
                "repetir la medicion; no debe leerse como cero. El numero es lo "
                "que el flujo PUEDE borrar, no lo que el disco PUEDE liberar."
            ),
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


class _Parser(argparse.ArgumentParser):
    """Argparse sale con codigo 2, que aqui ya significa 'no verificado'.

    Remapea el error de uso a 3 para que 2 signifique una sola cosa en todo el
    flujo. Sin esto, un flag mal escrito se reporta como una dimension que no
    se pudo comprobar, que es una lectura falsa y grave: invita a reintentar la
    medicion cuando el problema era el comando.
    """

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(3)


def construir_parser() -> argparse.ArgumentParser:
    """Construye el parser del flujo.

    Vive fuera de main() para que el contrato del CLI se pueda inspeccionar y
    probar sin ejecutar la auditoria entera.
    """
    ap = _Parser(description="Auditoria de higiene del repo (compone los verificadores existentes).")
    ap.add_argument("--json", action="store_true", help="salida en JSON")
    ap.add_argument("--rapido", action="store_true", help="omitir texto, barrera y test_texto")
    ap.add_argument("--dimension", action="append", default=[],
                    help="repetible: restringir la pasada a esa dimension")
    ap.add_argument("--solo", action="append", default=[],
                    help="alias de --dimension como lista separada por comas")
    ap.add_argument("--timeout-dim", type=int, default=0,
                    help="forzar timeout por dimension (0 = el de cada una)")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)

    # Las dos formas se unen, de modo que --dimension texto --solo disco
    # restringe a las dos, y repetir una dimension no la ejecuta dos veces.
    # `--solo` es append, no un string: con `default=""` el segundo `--solo`
    # SOBRESCRIBIA al primero y se perdian dimensiones en silencio
    # (`--solo bitacoras --solo texto` ejecutaba solo `texto`). Perder trabajo
    # pedido sin decir nada es el peor tipo de bug en una flag.
    pedidas = set(args.dimension)
    for bloque in args.solo:
        pedidas |= {s.strip() for s in bloque.split(",") if s.strip()}
    conocidas = {d["nombre"] for d in DIMENSIONES_REUTILIZADAS} | set(DIMENSIONES_NUEVAS)
    desconocidas = pedidas - conocidas
    if desconocidas:
        print(f"error: dimensiones desconocidas: {', '.join(sorted(desconocidas))}", file=sys.stderr)
        print(f"       disponibles: {', '.join(sorted(conocidas))}", file=sys.stderr)
        return 3
    solo = pedidas

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
        t0 = time.perf_counter()
        try:
            d = fn(RAIZ)
        except Exception as exc:
            d = {
                "dimension": nombre, "estado": "no_verificado",
                "resumen": f"NO SE PUDO COMPROBAR: la comprobacion lanzo {type(exc).__name__}: {exc}",
                "evidencia": {"excepcion": str(exc)},
            }
        d["capa"] = "nueva"
        # La duracion por dimension es lo que permite decidir si --rapido vale
        # algo. Sin ella, el flag solo es una promesa.
        d["duracion_s"] = round(time.perf_counter() - t0, 2)
        dimensiones.append(d)

    for dim in DIMENSIONES_REUTILIZADAS:
        if solo and dim["nombre"] not in solo:
            continue
        if args.rapido and dim["lenta"]:
            continue
        if args.timeout_dim:
            dim = {**dim, "timeout": args.timeout_dim}
        t0 = time.perf_counter()
        d = ejecutar_reutilizada(dim)
        d["duracion_s"] = round(time.perf_counter() - t0, 2)
        dimensiones.append(d)

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
        coste = d.get("duracion_s")
        marca_coste = f"  [{coste:6.2f}s]" if isinstance(coste, (int, float)) else ""
        print(f"  [{marcas.get(d.get('estado'), '?        ')}] {d['dimension']:16}{marca_coste} {d.get('resumen', '')}")
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
