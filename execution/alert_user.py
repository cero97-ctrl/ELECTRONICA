#!/usr/bin/env python3
"""
alert_user.py — Emite alertas audibles y notificaciones al usuario (Layer 3: Execution)

Uso:
    python3 execution/alert_user.py success
    python3 execution/alert_user.py waiting
    python3 execution/alert_user.py error

Salida (stdout, JSON):
    { "status": "ok", "alert_emitida": true, "metodo": "paplay"|"bell"|"none", ... }

Códigos de salida:
    0 — Alerta emitida correctamente
    1 — Error
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

# ── Sonidos del sistema Freedesktop ──────────────────────────────────────────
_SOUND_DIR = Path("/usr/share/sounds/freedesktop/stereo")
_SOUNDS = {
    "success": _SOUND_DIR / "complete.oga",
    "waiting": _SOUND_DIR / "phone-incoming-call.oga",
    "error":   _SOUND_DIR / "dialog-error.oga",
}


def _emitir_sonido(status: str) -> tuple[bool, str]:
    """
    Intenta reproducir un sonido usando paplay (PulseAudio).
    Si no está disponible o falla, usa el bell de la terminal.
    Retorna (exitoso, método_usado).
    """
    # Intento 1: paplay con sonido del sistema
    wav = _SOUNDS.get(status)
    if wav and wav.exists():
        try:
            subprocess.run(
                ["paplay", str(wav)],
                capture_output=True,
                timeout=3,
            )
            return True, "paplay"
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass

    # Intento 2: bell de terminal
    try:
        print("\a", end="", flush=True)
        return True, "bell"
    except Exception:
        pass

    return False, "none"


def main():
    parser = argparse.ArgumentParser(
        description="Emite notificaciones audibles al usuario."
    )
    parser.add_argument(
        "status",
        choices=["success", "waiting", "error"],
        help="Estado a notificar.",
    )
    parser.add_argument(
        "--message",
        type=str,
        default="",
        help="Mensaje opcional de la notificación.",
    )

    args = parser.parse_args()
    emitida, metodo = _emitir_sonido(args.status)

    output = {
        "status": "ok" if emitida else "fallback",
        "alert": args.status,
        "message": args.message,
        "metodo": metodo,
        "alert_emitida": emitida,
    }

    print(json.dumps(output))

    if args.status == "error" and not emitida:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
