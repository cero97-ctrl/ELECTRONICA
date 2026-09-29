#!/usr/bin/env python3
"""
test_motor_fallback.py — Tests deterministas del flujo motor_fallback (0 deps externas).

Cubre:
  1. Clasificación pura del detector (_clasificar_mensaje / _extraer_retry) con
     fixtures de respuestas de proveedor (Zen/OpenRouter) y mensajes benignos.
  2. Composición del mensaje de error desde un evento {"type":"error",...}.
  3. Soneo de la sonda (sondear) con un `opencode run` FAKE (stdout NDJSON) sin
     gastar cuota ni red: casos ok, agotada, error_infra, indeterminado.
  4. Integración del conmutador sobre archivos de config temporales: switch ->
     validate -> estado -> restore -> idempotencia, sin tocar la config real.

Ejecutar: python3 execution/test_motor_fallback.py
Salida: nombre del caso + PASS/FAIL. Código 0 si todos pasan, 1 si alguno falla.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = []


def test(nombre):
    def deco(fn):
        TESTS.append((nombre, fn))
        return fn
    return deco


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "execution" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


VERIF = None
APLICAR = None


@test("clasificar: firmas de cuota reales -> agotada")
def _():
    firmas = [
        "HTTP 429 Too Many Requests: you have exceeded your quota",
        "usage_exceeded: free tier quota exhausted, retry in 3600 seconds",
        "Retry-After: 900; rate limit exceeded",
        "Error 429: no credits remaining on this account",
        "tokens exhausted, insufficient balance for this request",
        "quota reset at 2026-09-21T18:00:00Z",
    ]
    benignos = [
        "pool the loop iterator lazily (Python style) and measure the speedup",
        "response slowly; it could be an infrastructure timeout error 500",
        "no such file or directory: /tmp/prueba.json",
    ]
    for msg in firmas:
        if not VERIF._clasificar_mensaje(msg):
            raise AssertionError(f"debería clasificar agotada: {msg!r}")
    for msg in benignos:
        if VERIF._clasificar_mensaje(msg):
            raise AssertionError(f"no debería clasificar agotada: {msg!r}")


@test("retry: conversión de unidades a segundos")
def _():
    casos = {
        "retry in 3600 seconds": 3600,
        "reset after 15 minutes": 900,
        "Retry-After: 90": 90,
        "retry in 500ms": 0,
        "sin ventana de reset aquí": None,
    }
    for msg, esperado in casos.items():
        got = VERIF._extraer_retry(msg)
        if got != esperado:
            raise AssertionError(f"{msg!r}: esperado {esperado}, got {got}")


@test("componer mensaje de error desde evento")
def _():
    ev = {"type": "error", "error": {
        "name": "HTTPError",
        "data": {"status": 429, "message": "quota exceeded"}}}
    msg, nombre = VERIF._componer_mensaje_error(ev)
    if nombre != "HTTPError" or "quota" not in msg.lower():
        raise AssertionError(f"mensaje/nombre mal compuestos: {nombre!r} {msg!r}")


class _FakeProc:
    def __init__(self, stdout="", returncode=0):
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


def _fake_runner(ndjson: str, rc: int = 0):
    original = subprocess.run

    def fake(cmd, capture_output=False, text=False, timeout=None, cwd=None):
        del capture_output, text, timeout, cwd
        return _FakeProc("".join(
            line + "\n" for line in ndjson.splitlines() if line.strip()), rc)

    VERIF.subprocess.run = fake
    return lambda: setattr(VERIF.subprocess, "run", original)


@test("sondear: respuesta ok")
def _():
    ndjson = (
        '{"type":"step_start","part":{"type":"step-start"}}\n'
        '{"type":"text","part":{"type":"text","text":"OK"}}\n'
        '{"type":"step_finish","part":{"type":"step-finish","reason":"stop"}}\n'
    )
    restore = _fake_runner(ndjson)
    try:
        estado, detalles = VERIF.sondear("opencode/big-pickle", 30, "/tmp", False)
        restore()
    except Exception:
        restore()
        raise
    if estado != "ok":
        raise AssertionError(f"esperado ok, got {estado}: {detalles}")


@test("sondear: evento error con firma -> agotada")
def _():
    ndjson = (
        '{"type":"error","error":{"name":"HTTPError","data":'
        '{"status":429,"message":"usage quota exceeded, retry in 3600 seconds"}}}\n'
    )
    restore = _fake_runner(ndjson)
    try:
        estado, detalles = VERIF.sondear("opencode/big-pickle", 30, "/tmp", False)
        restore()
    except Exception:
        restore()
        raise
    if estado != "agotada" or detalles.get("retry_en_segundos") != 3600:
        raise AssertionError(f"esperado agotada/3600, got {estado}: {detalles}")


@test("sondear: evento error benigno -> error_infra (no conmuta)")
def _():
    ndjson = (
        '{"type":"error","error":{"name":"UnknownError","data":'
        '{"message":"Unrecognized model"}}}\n'
    )
    restore = _fake_runner(ndjson)
    try:
        estado, detalles = VERIF.sondear("opencode/inexistente", 30, "/tmp", False)
        restore()
    except Exception:
        restore()
        raise
    if estado != "error_infra":
        raise AssertionError(f"esperado error_infra, got {estado}: {detalles}")


@test("sondear: stderr con firma y exit != 0 -> agotada")
def _():
    original = subprocess.run

    def fake(cmd, capture_output=False, text=False, timeout=None, cwd=None):
        del capture_output, text, timeout, cwd
        p = _FakeProc("", 1)
        p.stderr = "openrouter: 429 quota exceeded"
        return p

    VERIF.subprocess.run = fake
    try:
        estado, detalles = VERIF.sondear("x", 30, "/tmp", False)
    finally:
        VERIF.subprocess.run = original
    if estado != "agotada":
        raise AssertionError(f"esperado agotada (stderr), got {estado}: {detalles}")


@test("sondear: timeout -> indeterminado")
def _():
    original = subprocess.run

    def fake(cmd, capture_output=False, text=False, timeout=None, cwd=None):
        del capture_output, text, cwd
        raise subprocess.TimeoutExpired("opencode run", timeout)

    VERIF.subprocess.run = fake
    try:
        estado, _ = VERIF.sondear("x", 5, "/tmp", False)
    finally:
        VERIF.subprocess.run = original
    if estado != "indeterminado":
        raise AssertionError(f"esperado indeterminado, got {estado}")


def _run_switch_cli(args: list, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "execution/aplicar_switch_modelo.py"), *args],
        capture_output=True, text=True, timeout=60, env=env)


@test("aplicar_switch: switch->estado->restore->idempotencia (config temporal)")
def _():
    with tempfile.TemporaryDirectory() as td:
        cfg = Path(td) / "opencode.jsonc"
        cfg.write_text('{\n  "$schema": "https://opencode.ai/config.json",\n'
                       '  "default_agent": "plan"\n}\n', encoding="utf-8")
        env = dict(os.environ)
        # Marker y backups del script van a .tmp/ real; aíslalos via markers dir? El
        # script usa PROJECT_ROOT/.tmp — lo mantenemos pero limpiamos al final.
        fallback = "openrouter/qwen/qwen3.8-max-0902"

        # 1) switch (sin verificar catálogo)
        r = _run_switch_cli(["--config", str(cfg), "--modo", "switch",
                             "--modelo", fallback, "--sin-verificar"], env)
        out = json.loads(r.stdout or "{}")
        assert r.returncode == 0, f"switch rc={r.returncode}: {out}"
        assert out["estado"] == "ok" and out["cambio"] is True, out
        data = json.loads(cfg.read_text(encoding="utf-8"))
        assert data["model"] == fallback, data
        assert data.get("$schema"), "$schema no se ha perdido"

        # 2) idempotencia: segundo switch al mismo modelo no reescribe
        antes = cfg.read_bytes()
        r2 = _run_switch_cli(["--config", str(cfg), "--modo", "switch",
                              "--modelo", fallback, "--sin-verificar"], env)
        assert r2.returncode == 0 and json.loads(r2.stdout)["cambio"] is False, r2.stdout
        assert cfg.read_bytes() == antes, "no debería reescribir en idempotencia"

        # 3) estado
        r3 = _run_switch_cli(["--config", str(cfg), "--modo", "estado"], env)
        assert json.loads(r3.stdout)["modelo_actual"] == fallback, r3.stdout

        # 4) restore: volver al contenido original
        r4 = _run_switch_cli(["--config", str(cfg), "--modo", "restore"], env)
        assert r4.returncode == 0 and json.loads(r4.stdout)["estado"] == "ok", r4.stdout
        restaurado = json.loads(cfg.read_text(encoding="utf-8"))
        assert "model" not in restaurado, restaurado

        # 5) switch fallido: modelo inexistente NO conmuta (verificación activada)
        r5 = _run_switch_cli(["--config", str(cfg), "--modo", "switch",
                              "--modelo", "openrouter/modelo/inexistente-xyz"], env)
        assert r5.returncode == 4, f"rc={r5.returncode}: {r5.stdout}"
        data5 = json.loads(cfg.read_text(encoding="utf-8"))
        assert "model" not in data5, data5

        # 6) config no-JSON: no se toca
        rotos = Path(td) / "opencode_rotos.jsonc"
        rotos.write_text('{ "default_agent": "plan", // comentario\n}', encoding="utf-8")
        r6 = _run_switch_cli(["--config", str(rotos), "--modo", "switch",
                              "--modelo", fallback, "--sin-verificar"], env)
        assert r6.returncode == 2, f"rc={r6.returncode}: {r6.stdout}"

        # Limpieza de .tmp/motor_fallback.json y backups creados por los tests
        import shutil
        try:
            (ROOT / ".tmp/motor_fallback.json").unlink(missing_ok=True)
        except OSError:
            pass
        shutil.rmtree(ROOT / ".tmp/motor_fallback", ignore_errors=True)


import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--solo", default="")
    args = parser.parse_args()

    VERIF = _load("verificar_cuota_motor")
    APLICAR = _load("aplicar_switch_modelo")

    fallidos = 0
    for nombre, fn in TESTS:
        if args.solo and args.solo not in nombre:
            continue
        try:
            fn()
            print(f"PASS  {nombre}")
        except Exception as e:  # noqa: BLE001
            fallidos += 1
            print(f"FAIL  {nombre}: {e}")
    if args.solo and not any(args.solo in n for n, _ in TESTS):
        print(f"aviso: --solo {args.solo!r} no coincide con ningún test")
    print(f"{len([1 for n, _ in TESTS if not args.solo or args.solo in n]) - fallidos}/{len([1 for n, _ in TESTS if not args.solo or args.solo in n])} tests ok" if not args.solo else "filtro aplicado")
    sys.exit(1 if fallidos else 0)