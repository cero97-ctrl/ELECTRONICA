#!/usr/bin/env python3
"""
flujo_motor_fallback.py — Orquestador (Layer 2): detección de cuota free del motor
y failover automático a Qwen3.8 Max 0902 (o al modelo de respaldo configurado).

Encadena (SOP: directives/motor_fallback.yaml):
  1. execution/verificar_cuota_motor.py  -> sonda determinista (ok | agotada | error_infra)
  2. confirmaciones (retry budget máx 3)  -> evita falsos positivos que costarían créditos
  3. execution/aplicar_switch_modelo.py   -> conmuta "model" en la config global de opencode
  4. start_opencode.sh relaunch           -> relanza el TUI (dentro de tmux) con el nuevo motor
  5. watch (daemon)                       -> re-sondea el motor free y auto-restaura al recuperar cuota

Uso:
    python3 flujo_motor_fallback.py check          # sonda única (exit code = estado)
    python3 flujo_motor_fallback.py switch         # conmutar (con confirmaciones)
    python3 flujo_motor_fallback.py restore        # restaurar motor free
    python3 flujo_motor_fallback.py estado         # modelo activo en config + marker
    python3 flujo_motor_fallback.py pasivo         # escaneo del log (0 tokens, informativo)
    python3 flujo_motor_fallback.py watch [--daemon] [--intervalo 900] [--auto-restart]
Opciones comunes: --dry-run --no-alert --confirmaciones N
Salida: JSON por corrida/iteración. Códigos: 0 ok | 1 agotado/conmutado | 2 error infra
| 3 indeterminado | 4 modelo inexistente | 5 argumentos inválidos.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable
VERIFICAR = SCRIPT_DIR / "execution" / "verificar_cuota_motor.py"
APLICAR = SCRIPT_DIR / "execution" / "aplicar_switch_modelo.py"
ALERTAR = SCRIPT_DIR / "execution" / "alert_user.py"
SUPERVISOR = SCRIPT_DIR / "start_opencode.sh"
TMP = SCRIPT_DIR / ".tmp"
STATE_FILE = TMP / "run_state.json"
WATCH_STATE = TMP / "motor_watch_state.json"
CONFIG_GLOBAL = Path.home() / ".config/opencode/opencode.jsonc"

MODELO_VIGENTE = "opencode/big-pickle"
MODELO_FALLBACK = "openrouter/qwen/qwen3.8-max-0902"
LOOP_INTERVALO = 900
CONFIRMACIONES_DEF = 2

_ESTADO_EXIT = {"ok": 0, "agotada": 1, "error_infra": 2, "indeterminado": 3}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _guardar_run_state(step: str, exit_code: int) -> None:
    TMP.mkdir(exist_ok=True)
    try:
        prev = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.is_file() else {}
    except (OSError, json.JSONDecodeError):
        prev = {}
    prev.update({"flujo_motor_fallback": {"step": step, "exit_code": exit_code,
                                          "timestamp": _utcnow()}})
    STATE_FILE.write_text(json.dumps(prev, ensure_ascii=False, indent=2), encoding="utf-8")


def _leer_watch_state() -> dict:
    if WATCH_STATE.is_file():
        try:
            return json.loads(WATCH_STATE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def _guardar_watch_state(st: dict) -> None:
    TMP.mkdir(exist_ok=True)
    WATCH_STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def _sondear(vigente: str, pasivo: bool = False) -> dict:
    cmd = [PYTHON, str(VERIFICAR), "--modelo", vigente]
    if pasivo:
        cmd.append("--pasivo")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        data = {"estado": "indeterminado", "detalles": {"stdout": proc.stdout[:200]}}
    data["exit"] = proc.returncode
    return data


def _aplicar(mode: str, fallback: str, dry_run: bool, sin_verificar: bool = False) -> dict:
    cmd = [PYTHON, str(APLICAR), "--modo", mode, "--config", str(CONFIG_GLOBAL)]
    if mode == "switch":
        cmd += ["--modelo", fallback]
    if sin_verificar:
        cmd.append("--sin-verificar")
    if dry_run:
        cmd.append("--dry-run")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        data = {"estado": "error", "motivo": f"stdout no JSON: {proc.stdout[:200]}"}
    data["exit"] = proc.returncode
    return data


def _alertar(mensaje: str) -> None:
    subprocess.run([PYTHON, str(ALERTAR), "success", "--message", mensaje],
                   capture_output=True, timeout=30)


def _relaunch_tui() -> None:
    """Relanza la sesión TUI dentro de tmux (delegado a start_opencode.sh)."""
    if not SUPERVISOR.is_file():
        return
    subprocess.run([str(SUPERVISOR), "relaunch"], capture_output=True, timeout=60)


def _cmd_check(args) -> int:
    res = _sondear(args.modelo_vigente, pasivo=args.pasivo)
    _guardar_run_state("check", 0)
    print(json.dumps(res, ensure_ascii=False))
    return _ESTADO_EXIT.get(res.get("estado"), 3)


def _cmd_switch(args) -> int:
    """Sondea, confirma (máx 3) y conmuta si es sólido."""
    estado, exit_code = _confirmar_agotada(args.modelo_vigente, args.confirmaciones,
                                           args.pasivo)
    _guardar_run_state("confirmacion", exit_code)
    if exit_code != 1:  # no agotada
        res = {"comando": "switch", "estado": estado}
        if exit_code != 0:
            res["motivo"] = "no se conmuta sin firma de agotamiento confirmada"
        print(json.dumps(res, ensure_ascii=False))
        return exit_code

    if args.dry_run:
        res = {"comando": "switch", "estado": "agotada", "dry_run": True,
               "acccion": f"switch a {args.modelo_fallback} (no aplicado)"}
        print(json.dumps(res, ensure_ascii=False))
        _guardar_run_state("switch", 0)
        return 0

    cambio = _aplicar("switch", args.modelo_fallback, dry_run=False)
    _guardar_run_state("switch", cambio.get("exit", 1) if cambio.get("estado") == "ok" else 1)
    if cambio.get("estado") == "ok":
        if not args.no_alert:
            _alertar(f"Cuota free del motor agotada; motor conmutado a "
                     f"{args.modelo_fallback}.")
        if args.auto_restart and not args.no_relaunch:
            _relaunch_tui()
    print(json.dumps({"comando": "switch", "estado": "agotada", "aplicado": cambio},
                     ensure_ascii=False))
    return 0 if cambio.get("estado") == "ok" else 1


def _confirmar_agotada(vigente: str, confirmaciones: int, pasivo: bool) -> tuple[str, int]:
    """Sondea hasta confirmaciones negativas consecutivas (máx 3 intentos)."""
    intentos = 0
    pruebas = []
    while intentos < 3:
        res = _sondear(vigente, pasivo=pasivo)
        pruebas.append(res.get("estado"))
        if res.get("estado") == "agotada":
            intentos += 1
            if intentos >= min(max(confirmaciones, 1), 3):
                break
            time.sleep(10 * intentos)
        else:
            return res.get("estado", "indeterminado"), _ESTADO_EXIT.get(
                res.get("estado", "indeterminado"), 3)
    return "agotada", 1


def _cmd_restore(args) -> int:
    res = _aplicar("restore", args.modelo_fallback, args.dry_run)
    _guardar_run_state("restore", res.get("exit", 1) if res.get("estado") == "ok" else 1)
    if res.get("estado") == "ok" and not args.dry_run:
        if not args.no_alert:
            _alertar("Cuota free de Big Pickle restablecida; motor free de nuevo.")
    print(json.dumps({"comando": "restore", **res}, ensure_ascii=False))
    return 0 if res.get("estado") == "ok" else 1


def _cmd_estado(args) -> int:
    cmd = [PYTHON, str(APLICAR), "--modo", "estado", "--config", str(CONFIG_GLOBAL)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    print(proc.stdout or "{}")
    return proc.returncode


def _cmd_watch(args) -> int:
    """Bucle daemon: detecta agotamiento, conmuta+relanza; auto-restaura al recuperar."""
    st = _leer_watch_state()
    if args.daemon:
        st.setdefault("consecutivas_ok", 0)
        st.setdefault("consecutivas_agotada", 0)
        _guardar_watch_state(st)

    iteracion = 0
    while True:
        iteracion += 1
        res = _sondear(args.modelo_vigente)
        estado = res.get("estado")
        exit_code = _ESTADO_EXIT.get(estado, 3)
        _guardar_run_state("watch_iteracion", exit_code)

        if estado == "agotada":
            st["consecutivas_agotada"] = st.get("consecutivas_agotada", 0) + 1
            st["consecutivas_ok"] = 0
            _guardar_watch_state(st)
            res_confirm = {
                "comando": "watch",
                "iteracion": iteracion,
                "estado": "agotada",
                "confirmaciones": st["consecutivas_agotada"],
                "requeridas": args.confirmaciones,
            }
            if st["consecutivas_agotada"] >= args.confirmaciones:
                cambio = _aplicar("switch", args.modelo_fallback, dry_run=False)
                if cambio.get("estado") == "ok":
                    st["consecutivas_agotada"] = 0
                    st["motor_activo"] = args.modelo_fallback
                    _guardar_watch_state(st)
                    if not args.no_alert:
                        _alertar("Motor agotado -> conmutado a " + args.modelo_fallback)
                    if args.auto_restart and not args.no_relaunch:
                        _relaunch_tui()
                res_confirm["aplicado"] = cambio
            print(json.dumps(res_confirm, ensure_ascii=False), flush=True)

        elif estado == "ok":
            st["consecutivas_ok"] = st.get("consecutivas_ok", 0) + 1
            st["consecutivas_agotada"] = 0
            motor_activo = st.get("motor_activo")
            if motor_activo == args.modelo_fallback and st["consecutivas_ok"] >= 2:
                _guardar_watch_state(st)
                cambio = _aplicar("restore", args.modelo_fallback, dry_run=False)
                if cambio.get("estado") == "ok":
                    st["motor_activo"] = None
                    st["consecutivas_ok"] = 0
                    if not args.no_alert:
                        _alertar("Cuota free de Big Pickle restablecida; motor free de nuevo.")
                print(json.dumps({"comando": "watch", "iteracion": iteracion,
                                  "estado": "restaurado", "aplicado": cambio},
                                 ensure_ascii=False), flush=True)
            else:
                _guardar_watch_state(st)
                print(json.dumps({"comando": "watch", "iteracion": iteracion,
                                  "estado": "ok"}, ensure_ascii=False), flush=True)

        else:
            st["consecutivas_agotada"] = 0
            _guardar_watch_state(st)
            print(json.dumps({"comando": "watch", "iteracion": iteracion, "estado": estado,
                              "detalles": res.get("detalles")}, ensure_ascii=False), flush=True)

        if not args.daemon:
            return exit_code
        time.sleep(args.intervalo)


def main() -> None:
    parser = argparse.ArgumentParser(description="Detección y failover del motor orquestador.")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("check")
    p.add_argument("--modelo-vigente", default=MODELO_VIGENTE)
    p.add_argument("--pasivo", action="store_true")

    p = sub.add_parser("switch")
    p.add_argument("--modelo-vigente", default=MODELO_VIGENTE)
    p.add_argument("--modelo-fallback", default=MODELO_FALLBACK)
    p.add_argument("--confirmaciones", type=int, default=CONFIRMACIONES_DEF)
    p.add_argument("--pasivo", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-alert", action="store_true")
    p.add_argument("--auto-restart", action="store_true", default=True)
    p.add_argument("--no-relaunch", action="store_true")

    p = sub.add_parser("restore")
    p.add_argument("--modelo-fallback", default=MODELO_FALLBACK)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-alert", action="store_true")

    sub.add_parser("estado")

    p = sub.add_parser("pasivo")
    p.add_argument("--modelo-vigente", default=MODELO_VIGENTE)

    p = sub.add_parser("watch")
    p.add_argument("--modelo-vigente", default=MODELO_VIGENTE)
    p.add_argument("--modelo-fallback", default=MODELO_FALLBACK)
    p.add_argument("--confirmaciones", type=int, default=CONFIRMACIONES_DEF)
    p.add_argument("--daemon", action="store_true")
    p.add_argument("--intervalo", type=int, default=LOOP_INTERVALO)
    p.add_argument("--no-alert", action="store_true")
    p.add_argument("--auto-restart", action="store_true", default=True)
    p.add_argument("--no-relaunch", action="store_true")

    args = parser.parse_args()

    if args.comando == "check":
        sys.exit(_cmd_check(args))
    if args.comando == "switch":
        sys.exit(_cmd_switch(args))
    if args.comando == "restore":
        sys.exit(_cmd_restore(args))
    if args.comando == "estado":
        sys.exit(_cmd_estado(args))
    if args.comando == "pasivo":
        args.pasivo = True
        sys.exit(_cmd_check(args))
    if args.comando == "watch":
        sys.exit(_cmd_watch(args))
    sys.exit(5)


if __name__ == "__main__":
    main()