#!/usr/bin/env python3
"""
flujo_disco.py — Orquestador del mantenimiento de disco (Layer 2)

Implementa la directiva directives/mantenimiento_disco.yaml. La decisión de purgar
NO se razona aquí ni en el chat: es una función pura de los números que devuelve
`disco_medir.py` (uso% frente a umbral, y bytes recuperables del tier elegido).

Pipeline:
  1. disco_medir.py   → estado del filesystem, inodos y tamaño real por target
  2. DECISIÓN         → purgar solo si uso% > --umbral y el tier tiene algo que
                        recuperar. Un umbral más permisivo no autoescala de tier.
  3. disco_purgar.py  → borra (o simula con --dry-run) lo que la barrera permita
  4. disco_medir.py   → verificación posterior: comprueba que el espacio cayó
  5. alerta           → alerta audible solo si el flujo corrigió el problema

Uso:
  python3 flujo_disco.py                        # diagnóstico + purga si hace falta (seguro)
  python3 flujo_disco.py --check                # solo informe, nunca borra
  python3 flujo_disco.py --dry-run              # simula la purga
  python3 flujo_disco.py --tier recargable --yes # exige --yes por ser re-descargable
  python3 flujo_disco.py --watch --interval 3600 # mantenimiento periódico
  python3 flujo_disco.py --watch --no-alert     # en modo daemon, sin pitidos

Para instalarlo como servicio del usuario (no requiere sudo):
  crontab -e
  0 * * * * cd /ruta/al/repo && python3 flujo_disco.py --watch --interval 3600 --no-alert

Guarda progreso en .tmp/run_state.json y traza append-only en
.tmp/session_log_<run_id>.jsonl (fuente de verdad), con la vista run_state derivada.

Códigos de salida: 0 ok · 1 argumentos · 2 fallo de purga · 3 error interno
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
EJECUCION = SCRIPT_DIR / "execution"
if str(EJECUCION) not in sys.path:
    sys.path.insert(0, str(EJECUCION))
PYTHON = sys.executable
MEDIR = SCRIPT_DIR / "execution" / "disco_medir.py"
PURGAR = SCRIPT_DIR / "execution" / "disco_purgar.py"
ALERTAR = SCRIPT_DIR / "execution" / "alert_user.py"
SESION_LOG = SCRIPT_DIR / "execution" / "sesion_log.py"
TMP_DIR = SCRIPT_DIR / ".tmp"
# La vista de estado vive en `execution/run_state.py` (capa 3): nombre por
# corrida, escritura atomica y validacion del `run_id` en un solo sitio. La
# importacion es explicita y va aqui (y no arriba del todo) porque necesita
# `SCRIPT_DIR`, que se define justo encima.
sys.path.insert(0, str(SCRIPT_DIR / "execution"))
import run_state as RS  # noqa: E402  (capa 3, resolucion explicita)
INFORME = TMP_DIR / "disco_informe.json"

#: Uso% a partir del cual limpiar es conveniente. Constante, no un parámetro de
#: opinión: el operador puede endurecerlo con --umbral, nunca aflojarlo por fase.
UMBRAL_POR_DEFECTO = 90.0
#: Intervalo mínimo entre pasadas en --watch, para no martillear el disco.
INTERVALO_MINIMO_S = 300


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_state(state: dict) -> None:
    """Delega en `execution/run_state.py`: vista por corrida + escritura atomica.

    La vista lleva el `run_id` en el nombre porque `run_state.json` a pelo es un
    fichero compartido por todos los flujos: dos corridas simultaneas se pisan
    la misma vista, y el emparejamiento vista<->log que verifica
    `estado_sesion.py` atribuye la vista de una corrida al log de otra. El log
    append-only es la verdad permanente; la vista es un andamio, y el andamio
    necesita nombre propio.
    """
    RS.escribir_vista(RS.ruta_vista(state.get("run_id")), state)


def registrar_evento(state: dict, tipo: str, datos: dict | None = None) -> None:
    """Trazabilidad append-only. Falla blanda: nunca debe tumbar el flujo."""
    run_id = state.get("run_id")
    if not run_id:
        return
    cmd = [PYTHON, str(SESION_LOG), "add", "--run", run_id, "--tipo", tipo]
    if datos:
        try:
            cmd += ["--datos", json.dumps(datos, ensure_ascii=False)]
        except (TypeError, ValueError):
            pass
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"  (aviso) no se registró {tipo}", file=sys.stderr)


def run_script(cmd: list[str]) -> tuple[int, dict]:
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.returncode, {"status": "error", "message": (proc.stderr or proc.stdout)[:300]}


def medir(args) -> tuple[int, dict]:
    cmd = [PYTHON, str(MEDIR), "--output", str(TMP_DIR / "disco_medicion.json")]
    if args.profundo:
        cmd += ["--top-dirs", "10", "--top-files", "10"]
    return run_script(cmd)


def decidir(uso_pct: float, umbral: float, bytes_tier: int, check: bool) -> tuple[bool, str]:
    """DECISIÓN DETERMINISTA. Función pura: mismos números → misma decisión.

    No conoce el contenido del disco ni "opina": solo compara uso% y disponibilidad.
    """
    if check:
        return False, "modo --check: solo informe, nunca borra"
    if uso_pct <= umbral:
        return False, f"uso {uso_pct}% <= umbral {umbral}%: no hace falta limpiar"
    if bytes_tier <= 0:
        return False, f"uso {uso_pct}% > umbral, pero el tier no tiene nada recuperable"
    return True, f"uso {uso_pct}% > umbral {umbral}% y {bytes_tier} B recuperables: se purga"


def formatear_uso(fs: dict) -> str:
    return (f"{fs['usado_gb']} GB usados de {fs['total_gb']} GB  "
            f"({fs['uso_pct']}%)  →  {fs['libre_gb']} GB libres  "
            f"| inodos {fs['inodos_usados_pct']}%")


def formatear_bytes(n: int | float) -> str:
    """Cifra legible desde bytes, con la misma escala que usa la capa 3.

    Se importa de `catalogo_disco` en vez de reimplementar el redondeo: dos
    funciones que dan "1,9 GB" y "1.86 GiB" para el mismo numero hacen dudar de
    las dos, y el redondeo es justo el sitio donde una cifra de disco miente sin
    que se note.
    """
    from catalogo_disco import TAMANO_HUMANO  # noqa: E402  (capa 3, resolución explícita)
    return TAMANO_HUMANO(n)


def pasar(args, state: dict) -> int:
    """Una pasada completa: medir → decidir → purgar → verificar → alertar."""
    inicio = time.time()
    state["current_step"] = 1
    save_state(state)

    code, antes = medir(args)
    if code != 0 or "filesystem" not in antes:
        state.update(status="error", current_step=1)
        save_state(state)
        registrar_evento(state, "flujo/error", {"paso": "medir", "code": code})
        print(f"  ERROR: no se pudo medir el disco: {antes.get('message', code)}")
        return 3

    fs = antes["filesystem"]
    resumen = antes["resumen_catalogo"]["reclaimable_por_tier"]
    # `todos` no es una clave de `reclaimable_por_tier`, asi que la cifra se
    # saca del total cuando el tier es `todos`. Se imprime y se decide con la
    # MISMA variable: antes se imprimia una vez con una busqueda en el
    # diccionario y se decidia con otra, asi que el flujo podia decir una cifra
    # y decidir sobre otra. Con `--tier todos` la impresion caia en el default
    # '0 B' mientras la decision si veia los bytes reales.
    bytes_tier = (resumen.get(args.tier, {}).get("bytes", 0)
                  if args.tier != "todos"
                  else antes["resumen_catalogo"]["reclaimable_total_bytes"])
    print(f"  ANTES   {formatear_uso(fs)}")
    print(f"          recuperable {args.tier}: {formatear_bytes(bytes_tier)}")

    purgar, razon = decidir(fs["uso_pct"], args.umbral, bytes_tier, args.check)
    registrar_evento(state, "flujo/paso", {"paso": "decision", "purga": purgar, "razon": razon})
    print(f"  DECISIÓN {razon}")

    purga: dict = {"status": "no-ejecutada", "motivo": razon}
    if purgar:
        state["current_step"] = 2
        save_state(state)
        cmd = [PYTHON, str(PURGAR), "--tier", args.tier]
        if args.only:
            cmd += ["--only", args.only]
        if args.dry_run:
            cmd += ["--dry-run"]
        else:
            cmd += ["--yes", "--verbose"]     # --yes solo si el usuario lo pidió
        code, purga = run_script(cmd)
        if code not in (0, 2):
            state.update(status="error", current_step=2)
            save_state(state)
            registrar_evento(state, "flujo/error", {"paso": "purgar", "code": code})
            print(f"  ERROR: la purga falló ({code}): {purga.get('message', '')}")
            return 2

    state["current_step"] = 3
    save_state(state)
    code, despues = medir(args)
    if code != 0 or "filesystem" not in despues:
        fs2 = fs
    else:
        fs2 = despues["filesystem"]
    print(f"  DESPUÉS {formatear_uso(fs2)}")

    liberado = purga.get("liberado_bytes", 0) or 0
    delta = round(fs["libre_gb"] - fs2["libre_gb"], 2)
    if liberado:
        # La diferencia de medición puede ser ±0.2 GB por procesos de fondo: solo
        # se reporta cuando hubo un borrado real que explicar.
        print(f"          liberado {liberado / 2**30:.2f} GB (medición del disco: {delta:+} GB)")

    informe = {
        "run_id": state["run_id"], "timestamp": now_iso(),
        "tier": args.tier, "check": args.check, "dry_run": args.dry_run,
        "decision": {"purgar": purgar, "razon": razon, "umbral": args.umbral},
        "antes": fs, "despues": fs2,
        "purga": {k: v for k, v in purga.items() if k != "resultados"},
        "omitidos": [{"id": r["id"], "motivo": r["motivo"]}
                     for r in purga.get("resultados", []) if r["estado"] == "omitido"],
        "requiere_sudo": purga.get("requiere_sudo", antes.get("rutas_que_requieren_sudo", [])),
        "duracion_s": round(time.time() - inicio, 1),
    }
    TMP_DIR.mkdir(exist_ok=True)
    INFORME.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")

    avisos = informe["omitidos"]
    if avisos:
        print(f"          {len(avisos)} targets conservados: "
              f"{', '.join(sorted({a['motivo'] for a in avisos}))}")
    if informe["requiere_sudo"]:
        print(f"          {len(informe['requiere_sudo'])} rutas requieren sudo "
              f"(NO se tocan: este flujo nunca usa sudo)")

    # Solo se pita si el flujo realmente corrigió el espacio.
    if liberado and not args.no_alert:
        run_script([PYTHON, str(ALERTAR), "success"])

    state.update(status="ok", current_step=4, finished_at=now_iso(),
                 duracion_s=informe["duracion_s"])
    save_state(state)
    registrar_evento(state, "flujo/fin", {"status": "ok", "liberado": liberado})
    print(f"  Informe: {INFORME.relative_to(SCRIPT_DIR)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mantenimiento de disco: medir, purgar lo seguro y verificar.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument("--tier", default="seguro", choices=("seguro", "recargable", "pesado", "todos"),
                        help="Nivel máximo a purgar (por defecto 'seguro').")
    parser.add_argument("--umbral", type=float, default=UMBRAL_POR_DEFECTO,
                        help=f"Uso%% a partir del cual se purga (por defecto {UMBRAL_POR_DEFECTO}).")
    parser.add_argument("--only", default=None, help="Purar solo estos ids del catálogo.")
    parser.add_argument("--yes", action="store_true",
                        help="Autorizar el borrado. Sin este flag solo se simula.")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin borrar nada.")
    parser.add_argument("--check", action="store_true", help="Solo informe; nunca borra.")
    parser.add_argument("--watch", action="store_true", help="Repetir el flujo cada --interval s.")
    parser.add_argument("--interval", type=int, default=3600,
                        help=f"Segundos entre pasada en --watch (mínimo {INTERVALO_MINIMO_S}).")
    parser.add_argument("--profundo", action="store_true",
                        help="Añade top-10 de directorios y archivos de $HOME (lento, ~2-4 min).")
    parser.add_argument("--no-alert", action="store_true", help="Sin alerta audible (modo daemon).")
    args = parser.parse_args()

    if args.watch and args.interval < INTERVALO_MINIMO_S:
        parser.error(f"--interval mínimo {INTERVALO_MINIMO_S}s para no martillear el disco")
    if args.yes and args.dry_run:
        parser.error("--yes y --dry-run son excluyentes")
    if args.check and args.yes:
        parser.error("--check nunca borra: no se combina con --yes")
    if not args.dry_run and not args.yes:
        args.dry_run = True          # sin autorización explícita, nunca se borra

    state = {
        "run_id": f"flujo-disco-{time.strftime('%Y%m%d-%H%M%S')}",
        "directive": "mantenimiento_disco.yaml",
        "started_at": now_iso(), "last_updated": now_iso(),
        "current_step": 0, "status": "en_curso",
        "tier": args.tier, "check": args.check, "watch": args.watch,
    }
    TMP_DIR.mkdir(exist_ok=True)
    save_state(state)
    registrar_evento(state, "flujo/inicio", {"tier": args.tier, "check": args.check})

    print(f"== Mantenimiento de disco (tier={args.tier}, "
          f"{'SIMULACION' if args.dry_run else 'BORRADO'}) ==")
    rc = pasar(args, state)

    if args.watch and rc == 0:
        print(f"== Modo watch: cada {args.interval} s. Ctrl-C para salir. ==")
        try:
            while True:
                time.sleep(args.interval)
                print(f"\n-- pasada {now_iso()} --")
                state["run_id"] = f"flujo-disco-{time.strftime('%Y%m%d-%H%M%S')}"
                state["started_at"] = now_iso()
                state["current_step"] = 0
                save_state(state)
                registrar_evento(state, "flujo/inicio", {"tier": args.tier, "watch": True})
                rc = pasar(args, state)
                if rc != 0:
                    print(f"  (watch) la pasada devolvió {rc}; se reintenta en {args.interval}s")
        except KeyboardInterrupt:
            print("\n== Watch detenido por el usuario ==")
    return rc


if __name__ == "__main__":
    sys.exit(main())
