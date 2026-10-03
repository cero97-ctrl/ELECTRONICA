#!/usr/bin/env python3
"""
test_sync_faq.py — Tests deterministas de execution/regenerar_faq_flujo.py (0 deps externas).

Cubre los dos bugs encontrados el 2026-09-29 al sincronizar el diagrama del FAQ:

  1. `_llm_edits` NO consumía su propio retry budget ante un 'old' desalineado.
     La validación vivía en el llamador (FUERA del bucle de reintentos), así que
     un solo 'old' mal citado por el modelo tumbaba la corrida entera sin probar
     los otros dos candidatos/tiers que el presupuesto ya autorizaba.
  2. `openrouter_chat` recibía NOMBRES DE TIER ('deepseek') en vez de IDs de
     OpenRouter ('deepseek/deepseek-v4.1-flash'), y OpenRouter respondía
     `400: 'deepseek' is not a valid model ID` — es decir, el fallback se
     gastaba entero y sin producir edición alguna. Se corrige resolviendo el
     nombre de tier a ID en `llm_client.resolver_modelo`.

Ninguno de los dos testea la red: el `openrouter_chat` se sustituye por un doble
con respuestas preparadas. Ejecutar: python3 execution/test_sync_faq.py
Salida: nombre del caso + PASS/FAIL. Código 0 si todos pasan, 1 si alguno falla.
"""

import importlib.util
import sys
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


REGEN = None
BLOQUE = (
    "\\begin{tcolorbox}[cajaContenido, title={\\faIcon{table}~Leyenda de etiquetas}]\n"
    "\\small\n"
    "T1 & Corrida MCP lanzada. \\\\\n"
    "P1 & Toma \\texttt{mtime\\_before} antes de la corrida. \\\\\n"
    "\\end{tcolorbox}"
)


@test("resolver_modelo: nombre de tier -> ID de OpenRouter")
def _():
    llm = _load("llm_client")
    for tier, esperado in (
        ("flash", "google/gemini-2.5-flash"),
        ("deepseek", "deepseek/deepseek-v4.1-flash"),
        ("glm", "z-ai/glm-5.2"),
        ("opus", "anthropic/claude-opus-5"),
    ):
        got = llm.resolver_modelo(tier)
        if got != esperado:
            raise AssertionError(f"{tier}: esperado {esperado}, got {got}")
        # Es el bug exacto: un nombre de tier desnudo devolvía 400 en OpenRouter.
        if "/" not in got:
            raise AssertionError(f"ID sin proveedor (OpenRouter lo rechaza): {got!r}")


@test("resolver_modelo: ID explícito pasa intacto e idempotencia")
def _():
    llm = _load("llm_client")
    for explicito in ("moonshotai/kimi-k3", "google/gemini-2.5-flash"):
        if llm.resolver_modelo(explicito) != explicito:
            raise AssertionError(f"un ID explícito debe pasar intacto: {explicito}")
    if llm.resolver_modelo(llm.resolver_modelo("flash")) != llm.MODEL_TIERS["flash"]:
        raise AssertionError("resolver_modelo no es idempotente")


@test("openrouter_chat envía el ID, no el nombre de tier")
def _():
    llm = _load("llm_client")
    visto = {}

    class _ClienteFalso:
        class chat:  # noqa: N801 — imita la superficie de openai
            class completions:  # noqa: N801
                @staticmethod
                def create(**kw):
                    visto.update(kw)

                    class _Msg:
                        content = "ok"
                    class _Choice:
                        message = _Msg()
                    class _R:
                        usage = None
                        choices = [_Choice()]
                    return _R()

    llm.get_openai_client = lambda api_key: _ClienteFalso()
    llm.openrouter_chat([{"role": "user", "content": "hola"}],
                        model="deepseek", api_key="k", temperature=0.1, max_tokens=64)
    if visto.get("model") != "deepseek/deepseek-v4.1-flash":
        raise AssertionError(f"se envió {visto.get('model')!r}, no el ID completo")


@test("_edits_validos: rechaza 'old' ausente y token estructural")
def _():
    val = REGEN._edits_validos
    try:
        val([{"old": "texto que no existe en el bloque", "new": "x"}], BLOQUE)
        raise AssertionError("debió rechazar un 'old' inexistente")
    except ValueError as e:
        if "UNA vez" not in str(e):
            raise AssertionError(f"mensaje de error inesperado: {e}")
    try:
        val([{"old": "T1 & Corrida MCP lanzada. \\\\", "new": "\\begin{document}"}], BLOQUE)
        raise AssertionError("debió rechazar un token estructural")
    except ValueError as e:
        if "token estructural" not in str(e):
            raise AssertionError(f"mensaje de error inesperado: {e}")
    # El caso feliz: un 'old' que aparece exactamente una vez.
    ok = val([{"old": "Corrida MCP lanzada.", "new": "Corrida lanzada (run_id fijo)."}], BLOQUE)
    if len(ok) != 1:
        raise AssertionError(f"edit válido descartado: {ok}")


@test("_llm_edits: un 'old' desalineado CONSUME el retry budget (bug 1)")
def _():
    """El fallo de una respuesta debe reintentar, no abortar la corrida."""
    intentos = {"n": 0}
    respuestas = [
        '{"edits":[{"old":"NO EXISTE ESTE TEXTO","new":"x"}]}',   # 'old' desalineado
        '{"edits":[{"old":"Corrida MCP lanzada.","new":"Corrida lanzada."}]}',  # válido
    ]

    def _chat_falso(messages, **kw):
        idx = min(intentos["n"], len(respuestas) - 1)
        intentos["n"] += 1
        return respuestas[idx], {}

    original = REGEN.openrouter_chat
    REGEN.openrouter_chat = _chat_falso
    try:
        edits = REGEN._llm_edits(None, [], 500, False, BLOQUE, "1", [])
    finally:
        REGEN.openrouter_chat = original

    if intentos["n"] < 2:
        raise AssertionError(
            f"el 'old' desalineado abortó tras {intentos['n']} intento(s): "
            "la validación está fuera del bucle de reintentos")
    if not edits or edits[0]["new"] != "Corrida lanzada.":
        raise AssertionError(f"no devolvió el edit del segundo intento: {edits}")


@test("_llm_edits: agota el budget y nombra el último error si todo falla")
def _():
    intentos = {"n": 0}

    def _chat_falso(messages, **kw):
        intentos["n"] += 1
        return '{"edits":[{"old":"TAMPOCO EXISTE","new":"x"}]}', {}

    original = REGEN.openrouter_chat
    REGEN.openrouter_chat = _chat_falso
    try:
        REGEN._llm_edits(None, [], 500, False, BLOQUE, "1", [])
        raise AssertionError("debió lanzar RuntimeError tras agotar el budget")
    except RuntimeError as e:
        if f"{REGEN.RETRY_BUDGET} intentos" not in str(e):
            raise AssertionError(f"mensaje inesperado: {e}")
    finally:
        REGEN.openrouter_chat = original
    if intentos["n"] != REGEN.RETRY_BUDGET:
        raise AssertionError(f"usó {intentos['n']} intentos, budget={REGEN.RETRY_BUDGET}")


@test("_aplicar_edits: un solo remplazo, sin nodos nuevos")
def _():
    nuevo = REGEN._aplicar_edits(
        BLOQUE, [{"old": "Corrida MCP lanzada.", "new": "Corrida con run_id."}])
    if nuevo.count("Corrida con run_id.") != 1:
        raise AssertionError("no aplicó el edit")
    if "Corrida MCP lanzada." in nuevo:
        raise AssertionError("el texto viejo sobrevivió")
    if nuevo.count("\\begin{tcolorbox}") != 1 or nuevo.count("\\end{tcolorbox}") != 1:
        raise AssertionError("la estructura LaTeX se rompió")


if __name__ == "__main__":
    REGEN = _load("regenerar_faq_flujo")
    fallidos = 0
    for nombre, fn in TESTS:
        try:
            fn()
            print(f"PASS  {nombre}")
        except Exception as e:  # noqa: BLE001
            fallidos += 1
            print(f"FAIL  {nombre}: {e}")
    total = len(TESTS)
    print(f"{total - fallidos}/{total} tests ok")
    sys.exit(1 if fallidos else 0)
