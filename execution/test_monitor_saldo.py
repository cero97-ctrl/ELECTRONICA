#!/usr/bin/env python3
"""
test_monitor_saldo.py — Regresión del saldo de OpenRouter (Layer 3: Execution, sin red).

Congela el fallo del 2026-11-21: el monitor restaba el `usage` de /auth/key a
una constante CREDITS_TOTAL_REF = 24.769395 (referencia de 2026-09-01) y
reportaba -$30.29 con falsa alerta de top-up, aunque /api/v1/credits daba
$5.04 disponibles. La constante se eliminó: la fuente de verdad es
`total_credits - total_usage` de /api/v1/credits.

No llama a la API: inyecta los totales con mocks y restaura las funciones.

Uso:  python3 execution/test_monitor_saldo.py
Salida: 0 = todas las aserciones pasan; 1 = hay regresión.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import monitor_saldo_openrouter as M  # noqa: E402

fallos: list[str] = []
ok = 0


def comprobar(condicion: bool, mensaje: str) -> None:
    global ok
    if condicion:
        ok += 1
    else:
        fallos.append(mensaje)


def ejecutar_chequeo(credits: dict, usage: dict | None = None) -> dict:
    """chequeo() con la API inyectada: sin red, sin sonido y sin log en disco."""
    if usage is None:
        usage = {
            "usage": 55.059396678,
            "usage_daily": 0.43393,
            "usage_monthly": 49.89213,
            "is_free_tier": False,
            "limit": None,
        }
    reales = (M._load_api_key, M._get_credits, M._get_usage, M._log, M._alert)
    M._load_api_key = lambda: "clave-de-prueba"
    M._get_credits = lambda key: credits
    M._get_usage = lambda key: usage
    M._log = lambda line: None
    M._alert = lambda msg: None
    try:
        return M.chequeo(argparse.Namespace(watch=False, warn=3.50, alert=3.10))
    finally:
        (M._load_api_key, M._get_credits, M._get_usage, M._log, M._alert) = reales


def test_saldo_es_credits_menos_uso() -> None:
    saldo = M._saldo({"total_credits": 65.0, "total_usage": 59.959003626})
    comprobar(abs(saldo - 5.040996374) < 1e-9,
              f"saldo real debería ser 5.040996374, dio {saldo}")
    comprobar(M._saldo({"total_credits": 10.0, "total_usage": 10.0}) == 0.0,
              "total_credits == total_usage debe dar saldo 0")


def test_no_hay_constante_de_saldo() -> None:
    comprobar(not hasattr(M, "CREDITS_TOTAL_REF"),
              "la constante CREDITS_TOTAL_REF volvió: cada recarga la desactualiza")
    comprobar(not hasattr(M, "_estimado_saldo"),
              "_estimado_saldo volvió: el saldo debe venir de /credits")


def test_el_caso_real_no_emite_alerta() -> None:
    r = ejecutar_chequeo({"total_credits": 65.0, "total_usage": 59.959003626})
    comprobar(r["status"] == "ok", "chequeo con datos reales debe estar ok")
    comprobar(r["saldo"] == 5.04, f"saldo debería ser 5.04, dio {r.get('saldo')}")
    comprobar(r["saldo_estimado"] == r["saldo"], "alias legacy debe igualar al saldo")
    comprobar("alerta" not in r,
              "con $5.04 NO debe haber falsa alerta de top_up_inminente")


def test_usage_de_auth_key_no_decide_el_saldo() -> None:
    # El bug original: usage $55.059 contra la constante $24.77 daba -$30.29.
    r = ejecutar_chequeo(
        {"total_credits": 65.0, "total_usage": 59.959003626},
        {"usage": 55.059396678, "usage_daily": 0.43393,
         "usage_monthly": 49.89213, "is_free_tier": False, "limit": None},
    )
    comprobar(r["saldo"] > 0, "usage de /auth/key no debe volver negativo el saldo")
    comprobar(r["usage_total"] == 55.059397,
              "usage_total debe conservarse como dato informativo")
    comprobar(r["usage_daily"] == 0.43393, "usage_daily debe exponerse")


def test_la_alerta_sigue_funcionando() -> None:
    r = ejecutar_chequeo({"total_credits": 10.0, "total_usage": 7.5})
    comprobar(r["saldo"] == 2.5, "saldo bajo debe calcularse igual")
    comprobar(r.get("alerta") == "top_up_inminente",
              "con $2.50 SÍ debe avisar de top-up (la alerta no se desactivó)")


def main() -> int:
    test_saldo_es_credits_menos_uso()
    test_no_hay_constante_de_saldo()
    test_el_caso_real_no_emite_alerta()
    test_usage_de_auth_key_no_decide_el_saldo()
    test_la_alerta_sigue_funcionando()
    print(f"Aserciones OK: {ok}   Fallos: {len(fallos)}")
    for f in fallos:
        print(f"  FALLO: {f}")
    if fallos:
        print("MONITOR ROTO — no fiarse del saldo hasta arreglarlo.")
        return 1
    print("MONITOR OK: saldo desde /credits, sin constantes, alerta solo bajo umbral.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
