#!/usr/bin/env python3
"""
monitor_saldo_openrouter.py — Estima el saldo de créditos de OpenRouter desde la API (Layer 3: Execution)

OpenRouter NO expone el saldo por API (solo en la página web). Este script lo
estima restando el uso acumulado (`/api/v1/auth/key` → usage) a los créditos
totales comprados, tomando como referencia el saldo visto en la página en un
momento dado (ver constantes y la sección "Sesión" en Sessions/).

Uso:
    python3 execution/monitor_saldo_openrouter.py                 # chequeo puntual
    python3 execution/monitor_saldo_openrouter.py --watch         # bucle en segundo plano
    python3 execution/monitor_saldo_openrouter.py --watch --interval 300

Salida (stdout, JSON):
    { "status": "ok", "saldo_estimado": 9.81, "usage": 0.02, ... }

Códigos de salida:
    0 — OK (o alerta emitida)
    1 — Error (API o red)

Alertas audibles (execution/alert_user.py "waiting") cuando el saldo cruza
los umbrales --warn (por defecto 5.50) y --alert (por defecto 5.10). El umbral
--alert corresponde al punto donde OpenRouter dispara el auto top-up de $10
(la recarga se intenta cuando el saldo baja de $5).
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Referencia de créditos totales ───────────────────────────────────────────
# balance_visto + usage en ese instante. Ajustar si cambia la compra/top-up.
# 2026-08-16: página mostró $9.82 con usage=0.01721381 → créditos totales ≈ 9.83721381
CREDITS_TOTAL_REF = 9.83721381

_ALERT_SCRIPT = Path(__file__).resolve().parent / "alert_user.py"
_LOG_PATH = Path(__file__).resolve().parent.parent / ".tmp" / "saldo_openrouter.log"


def _load_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
        key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("No se encontró OPENROUTER_API_KEY en .env/entorno.")
    return key


def _get_usage(key: str) -> dict:
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/auth/key",
        headers={"Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.load(resp).get("data", {})
    return {
        "usage": data.get("usage", 0.0),
        "usage_monthly": data.get("usage_monthly", 0.0),
        "is_free_tier": data.get("is_free_tier"),
        "limit": data.get("limit"),
    }


def _estimado_saldo(usage: float) -> float:
    return CREDITS_TOTAL_REF - usage


def _log(line: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(f"[{ts}] {line}\n")
    print(f"[{ts}] {line}", flush=True)


def _alert(mensaje: str) -> None:
    subprocess.run(
        [sys.executable, str(_ALERT_SCRIPT), "waiting", "--message", mensaje],
        capture_output=True,
        timeout=10,
    )


def chequeo(args) -> dict:
    try:
        key = _load_api_key()
        info = _get_usage(key)
    except Exception as e:
        _log(f"[ERROR] No se pudo consultar OpenRouter: {e}")
        return {"status": "error", "message": str(e)}

    saldo = _estimado_saldo(info["usage"])
    cruzando_warn = not args.watch and saldo < args.warn
    cruzando_alert = not args.watch and saldo < args.alert

    result = {
        "status": "ok",
        "saldo_estimado": round(saldo, 2),
        "usage_total": round(info["usage"], 6),
        "usage_monthly": round(info["usage_monthly"], 6),
        "is_free_tier": info["is_free_tier"],
        "limit": info["limit"],
    }
    _log(
        "Saldo estimado: ${:.2f} (usage ${:.4f}, tier {})".format(
            saldo, info["usage"], "gratis" if info["is_free_tier"] else "pago"
        )
    )

    if cruzando_alert:
        _alert(f"Saldo < ${args.alert:.2f} — OpenRouter intentará cobrar $10 a tu tarjeta. Verifica fondos.")
        result["alerta"] = "top_up_inminente"
    elif cruzando_warn:
        _alert(f"Saldo cerca de ${args.warn:.2f} — prepara la tarjeta para el top-up de $10.")
        result["alerta"] = "cerca_umbral"
    return result


def main():
    parser = argparse.ArgumentParser(description="Estima el saldo de créditos de OpenRouter.")
    parser.add_argument("--watch", action="store_true", help="Bucle continuo (segundo plano).")
    parser.add_argument("--interval", type=int, default=300, help="Segundos entre chequeos (default 300).")
    parser.add_argument("--warn", type=float, default=5.50, help="Umbral de advertencia (default 5.50).")
    parser.add_argument("--alert", type=float, default=5.10, help="Umbral de alerta/top-up (default 5.10).")
    args = parser.parse_args()

    if not args.watch:
        result = chequeo(args)
        print(json.dumps(result))
        sys.exit(0 if result["status"] == "ok" else 1)

    _log(f"[MONITOR] Iniciado: interval={args.interval}s warn=${args.warn:.2f} alert=${args.alert:.2f}")
    cruzo_warn = cruzo_alert = False
    while True:
        try:
            key = _load_api_key()
            info = _get_usage(key)
            saldo = _estimado_saldo(info["usage"])
            _log(
                "Saldo estimado: ${:.2f} (usage ${:.4f})".format(saldo, info["usage"])
            )
            if saldo < args.alert and not cruzo_alert:
                cruzo_alert = True
                _alert(f"Saldo < ${args.alert:.2f} — OpenRouter intentará cobrar $10 a tu tarjeta. Verifica fondos.")
                _log("[ALERTA] Top-up inminente, alerta audible emitida.")
            elif saldo < args.warn and not cruzo_warn:
                cruzo_warn = True
                _alert(f"Saldo cerca de ${args.warn:.2f} — prepara la tarjeta para el top-up de $10.")
                _log("[WARN] Cerca del umbral, alerta audible emitida.")
            elif saldo >= args.warn:
                cruzo_warn = cruzo_alert = False
        except Exception as e:
            _log(f"[ERROR] {e}")
        time.sleep(max(10, args.interval))


if __name__ == "__main__":
    main()