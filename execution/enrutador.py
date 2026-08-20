#!/usr/bin/env python3
"""
enrutador.py — Decisión determinista de enrutamiento multi-LLM.

Dado un descriptor estructurado de la tarea (tipo de tarea, tamaño de entrada
medido, criticidad, visión requerida, modelo explícito), devuelve por reglas
puras el tier y el modelo a usar. NO hay criterio probabilístico: la misma
entrada produce siempre la misma salida.

El orquestador (opencode) NO decide el tier: solo extrae el descriptor a partir
de la petición del usuario y delega la decisión en este script.

Uso:
    python3 execution/enrutador.py --task examen_complejo --tokens 12000
    python3 execution/enrutador.py --task contexto_masivo --archivos a.txt b.tex
    python3 execution/enrutador.py --task rag --critico
    python3 execution/enrutador.py --task debug --modelo-explicito moonshotai/kimi-k3

Salida (stdout, JSON): {"tier", "model", "fallback", "reason", "tokens"}
Códigos de salida: 0 = ok, 1 = tipo de tarea inválido, 2 = sin archivos ni tokens.
"""

import argparse
import json
import os
import sys
import time

try:
    from execution.llm_client import MODEL_TIERS
except ImportError:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from execution.llm_client import MODEL_TIERS

# ---------------------------------------------------------------------------
# Constantes de la política (únicas fuentes de verdad de los umbrales)
# ---------------------------------------------------------------------------
# Umbral de "contexto largo": por encima se fuerza el tier de contexto masivo
# (determinista: se mide, no se adivina).
LONG_CONTEXT_THRESHOLD = 50_000

# Heurística determinista de estimación de tokens: ~4 caracteres por token.
CHARS_PER_TOKEN = 4

# Vocabulario controlado de tipos de tarea -> tier. Cada tipo vive en EXACTAMENTE
# una categoría; añadir un tipo nuevo requiere editar este mapa (y solo este).
FLASH_TASKS = frozenset({
    "formateo", "parsing", "sintaxis", "validacion", "resumen",
    "rag", "multimodal", "extraccion", "conversion",
})
KIMI_TASKS = frozenset({
    "contexto_masivo", "multi_archivo", "destilacion", "sintesis_logs",
    "auditoria", "razonamiento_intermedio",
})
OPUS_TASKS = frozenset({
    "arquitectura", "calculo_formal", "debug", "examen", "examen_complejo",
    "netlist", "kicad", "refactor", "diseño",
})

# Cadena de fallback por tier ante 429/errores repetidos. Determinista y
# cost-aware: el último recurso de kimi/flash NO es opus salvo tareas críticas.
FALLBACK_CHAINS = {
    "flash": ["flash", "kimi", "kimi_fallback"],
    "kimi":  ["kimi", "kimi_fallback", "opus"],
    "opus":  ["opus", "kimi", "kimi_fallback"],
}

# kimi_fallback ya vive en llm_client.MODEL_TIERS (deepseek/deepseek-v4-pro).

# Telemetría: log por decisión (tier, tokens, modelo) para poder tunear la política.
ROUTING_LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".tmp", "routing_log.jsonl")


def estimate_tokens_from_files(paths: list[str]) -> int:
    """Mide bytes de los archivos y estima tokens de forma determinista."""
    total_chars = 0
    for p in paths:
        if not os.path.isfile(p):
            continue
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            total_chars += len(f.read())
    return total_chars // CHARS_PER_TOKEN


def decide(task: str, tokens: int, critico: bool, vision: bool, modelo_explicito: str | None) -> dict:
    """Reglas puras. Sin aleatoriedad, sin LLM, sin heurísticas no documentadas.

    Orden de precedencia:
      1. Modelo explícito del usuario  -> se respeta (override total).
      2. Tamaño de entrada medido      -> fuerza contexto masivo (o opus si crítico).
      3. Tipo de tarea                 -> tier por vocabulario controlado.
    """
    if modelo_explicito:
        tier = "explicito"
        return {
            "tier": tier,
            "model": modelo_explicito,
            "fallback": [],
            "reason": f"Modelo explícito solicitado por el usuario: {modelo_explicito}.",
            "tokens": tokens,
        }

    if tokens > LONG_CONTEXT_THRESHOLD:
        # Entrada medida por encima del umbral: contexto masivo obligatorio.
        if critico or task in OPUS_TASKS:
            tier = "opus"
            reason = (
                f"Entrada de {tokens} tokens supera el umbral de {LONG_CONTEXT_THRESHOLD} "
                f"y la tarea es crítica o de razonamiento crítico -> opus."
            )
        else:
            tier = "kimi"
            reason = (
                f"Entrada de {tokens} tokens supera el umbral de {LONG_CONTEXT_THRESHOLD} "
                f"y la tarea no es crítica -> kimi (contexto masivo)."
            )
        return {
            "tier": tier,
            "model": MODEL_TIERS[tier],
            "fallback": FALLBACK_CHAINS[tier],
            "reason": reason,
            "tokens": tokens,
        }

    if task in FLASH_TASKS:
        tier = "opus" if critico else "flash"
        reason = (
            f"Tipo de tarea '{task}' es de rutina -> flash."
            if not critico else
            f"Tipo de tarea '{task}' es de rutina pero marcada crítica -> opus."
        )
    elif task in KIMI_TASKS:
        tier = "kimi"
        reason = f"Tipo de tarea '{task}' es de contexto/síntesis -> kimi."
    elif task in OPUS_TASKS:
        tier = "opus"
        reason = f"Tipo de tarea '{task}' es de razonamiento crítico -> opus."
    else:
        return {
            "tier": "desconocido",
            "model": None,
            "fallback": [],
            "reason": f"Tipo de tarea '{task}' no está en el vocabulario controlado.",
            "tokens": tokens,
        }

    return {
        "tier": tier,
        "model": MODEL_TIERS[tier],
        "fallback": FALLBACK_CHAINS[tier],
        "reason": reason,
        "tokens": tokens,
    }


def append_log(entry: dict) -> None:
    """Telemetría: registra cada decisión en .tmp/routing_log.jsonl."""
    try:
        os.makedirs(os.path.dirname(ROUTING_LOG), exist_ok=True)
        with open(ROUTING_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), **entry}, ensure_ascii=False) + "\n")
    except OSError:
        pass  # la telemetría no debe romper el enrutamiento


def main() -> int:
    parser = argparse.ArgumentParser(description="Router determinista de modelos LLM")
    parser.add_argument("--task", required=True, help="Tipo de tarea (vocabulario controlado).")
    parser.add_argument("--tokens", type=int, default=None,
                        help="Tokens de entrada medidos (si ya se conocen).")
    parser.add_argument("--archivos", nargs="*", default=None,
                        help="Archivos a medir (suma sus tamaños para estimar tokens).")
    parser.add_argument("--critico", action="store_true",
                        help="Tarea crítica: escala a opus aunque sea rutina.")
    parser.add_argument("--vision", action="store_true",
                        help="Requiere visión (imágenes/PDF). Solo informativo: todos los tiers la soportan.")
    parser.add_argument("--modelo-explicito", default=None,
                        help="Modelo indicado por el usuario: override total.")
    parser.add_argument("--no-log", action="store_true", help="No escribir telemetría.")
    args = parser.parse_args()

    if args.tokens is None:
        if not args.archivos and not args.modelo_explicito:
            print(json.dumps({"status": "error", "code": 2,
                              "message": "Debes pasar --tokens o --archivos (o --modelo-explicito)."}))
            return 2
        args.tokens = estimate_tokens_from_files(args.archivos) if args.archivos else 0

    result = decide(args.task, args.tokens, args.critico, args.vision, args.modelo_explicito)

    if result["tier"] == "desconocido":
        print(json.dumps({"status": "error", "code": 1, **result}, ensure_ascii=False))
        return 1

    result = {"status": "ok", "code": 0, "vision": args.vision, **result}
    if not args.no_log:
        append_log(result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())