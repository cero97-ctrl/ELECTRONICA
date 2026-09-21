#!/usr/bin/env python3
"""
execution/aplicar_switch_modelo.py — Conmuta/restaura el modelo del motor de opencode.

Edita el campo "model" de la configuración global de opencode (por defecto
~/.config/opencode/opencode.jsonc) de forma SEGURA:
  1. Verifica que el archivo sea JSON estricto (si no, NO reescribe: error 2).
  2. (Opcional) verifica que el modelo destino exista en el catálogo (opencode models).
  3. Valida el JSON modificado con json.loads antes de escribir.
  4. Escritura atómica: archivo temporal en el mismo directorio + os.replace.
  5. Backup previo + marker de estado .tmp/motor_fallback.json (mismo input ->
     mismo output; idempotente: si el modelo ya es el destino, no escribe).

Modos:
    --modo switch  -> pone "model": <--modelo>
    --modo restore -> restaura el contenido original previo al switch
    --modo estado  -> imprime el modelo actual de la config y el marker (solo lectura)

Códigos de salida: 0 ok | 1 error general | 2 config no-JSON | 4 modelo inexistente.

Uso:
    python3 execution/aplicar_switch_modelo.py --modo switch --modelo openrouter/qwen/qwen3.8-max-0902
    python3 execution/aplicar_switch_modelo.py --modo restore
    python3 execution/aplicar_switch_modelo.py --modo estado
    python3 execution/aplicar_switch_modelo.py --modo switch --modelo <id> --dry-run
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TMP = PROJECT_ROOT / ".tmp"
_BACKUP_DIR = _TMP / "motor_fallback"
_PREVIO = _BACKUP_DIR / "previo.jsonc"
_MARKER = _TMP / "motor_fallback.json"
_DEFAULT_CONFIG = Path.home() / ".config/opencode/opencode.jsonc"


def _config_actual(config: Path) -> dict:
    """Lee y valida la config como JSON estricto. Sube JSONDecodeError si no lo es."""
    texto = config.read_text(encoding="utf-8")
    return json.loads(texto)


def _modelo_existe(modelo: str) -> bool:
    """Comprueba contra `opencode models` (lectura del catálogo cacheado)."""
    try:
        proc = subprocess.run(
            ["opencode", "models"], capture_output=True, text=True, timeout=60
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    if proc.returncode != 0:
        return False
    return any(modelo in linea for linea in (proc.stdout or "").splitlines())


def _escribir_atomico(config: Path, contenido: str) -> None:
    tmp = config.with_suffix(config.suffix + ".tmp_motor")
    tmp.write_text(contenido, encoding="utf-8")
    # Valida que lo que escribimos siga siendo JSON válido antes de reemplazar.
    json.loads(tmp.read_text(encoding="utf-8"))
    os.replace(tmp, config)


def _modo_estado(config: Path) -> dict:
    try:
        data = _config_actual(config)
    except (OSError, json.JSONDecodeError) as e:
        return {"estado": "error", "motivo": str(e)}
    modelo_actual = data.get("model") if isinstance(data, dict) else None
    marker = {}
    if _MARKER.is_file():
        try:
            marker = json.loads(_MARKER.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            marker = {"estado": "corrupto"}
    return {
        "estado": "ok",
        "config": str(config),
        "modelo_actual": modelo_actual,
        "marker": marker,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Conmuta/restaura el modelo del motor.")
    parser.add_argument("--config", type=Path, default=_DEFAULT_CONFIG)
    parser.add_argument("--modo", choices=["switch", "restore", "estado"], required=True)
    parser.add_argument("--modelo", default="",
                        help="Identificador del modelo destino (modo switch).")
    parser.add_argument("--sin-verificar", action="store_true",
                        help="No verificar la existencia del modelo (modo switch).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Calcula el resultado sin escribir nada.")
    parser.add_argument("--marker", type=Path, default=_MARKER)
    args = parser.parse_args()

    salida: dict = {"modo": args.modo, "config": str(args.config),
                    "timestamp": datetime.now(timezone.utc).isoformat()}

    if args.modo == "estado":
        res = _modo_estado(args.config)
        salida.update(res)
        salida["dry_run"] = False
        print(json.dumps(salida, ensure_ascii=False))
        sys.exit(0 if res["estado"] == "ok" else 1)

    # switch / restore: el archivo debe ser JSON estricto.
    try:
        data = _config_actual(args.config)
    except FileNotFoundError:
        salida.update({"estado": "error", "codigo": 2,
                       "motivo": f"config no encontrada: {args.config}"})
        print(json.dumps(salida, ensure_ascii=False))
        sys.exit(2)
    except json.JSONDecodeError as e:
        salida.update({"estado": "error", "codigo": 2,
                       "motivo": f"config no es JSON estricto: {e}",
                       "instrucciones": "Migrar la config a JSON puro o editar el campo "
                                        "\\\"model\\\" manualmente; este script nunca "
                                        "reescribe un archivo con comentarios a ciegas."})
        print(json.dumps(salida, ensure_ascii=False))
        sys.exit(2)

    if not isinstance(data, dict):
        salida.update({"estado": "error", "codigo": 2,
                       "motivo": "config JSON no es un objeto"})
        print(json.dumps(salida, ensure_ascii=False))
        sys.exit(2)

    if args.modo == "switch":
        if not args.modelo:
            salida.update({"estado": "error", "codigo": 1,
                           "motivo": "--modelo es obligatorio en modo switch"})
            print(json.dumps(salida, ensure_ascii=False))
            sys.exit(1)
        if not args.sin_verificar and not _modelo_existe(args.modelo):
            salida.update({"estado": "error", "codigo": 4,
                           "motivo": f"modelo no está en el catálogo de opencode: "
                                     f"{args.modelo}"})
            print(json.dumps(salida, ensure_ascii=False))
            sys.exit(4)

    if args.modo == "switch":
        modelo_previo = data.get("model")
        if modelo_previo == args.modelo:
            salida.update({"estado": "ok", "cambio": False, "modelo": args.modelo,
                           "motivo": "el modelo ya está activo (idempotente)"})
            print(json.dumps(salida, ensure_ascii=False))
            sys.exit(0)

        if not args.dry_run:
            _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            # Backups: previo (siempre) + backup con timestamp (histórico).
            if not _PREVIO.is_file() or modelo_previo is None:
                shutil.copyfile(args.config, _PREVIO)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copyfile(args.config, _BACKUP_DIR / f"motor_fallback_backup_{ts}.jsonc")

        nuevo = dict(data)
        nuevo["model"] = args.modelo
        contenido = json.dumps(nuevo, ensure_ascii=False, indent=2) + "\n"
        # Conserva $schema tal cual ya que vive en `data`.
        salida.update({"estado": "ok", "cambio": True, "modelo": args.modelo,
                       "modelo_previo": modelo_previo})
        if args.dry_run:
            salida["dry_run"] = True
            salida["_vista_prevista"] = nuevo
            print(json.dumps(salida, ensure_ascii=False))
            sys.exit(0)

        try:
            _escribir_atomico(args.config, contenido)
        except (OSError, json.JSONDecodeError) as e:
            # Rollback: intentar restaurar el backup previo.
            try:
                if _PREVIO.is_file():
                    shutil.copyfile(_PREVIO, args.config)
            except OSError:
                pass
            salida.update({"estado": "error", "codigo": 1,
                           "motivo": f"escritura fallida y revertida: {e}"})
            print(json.dumps(salida, ensure_ascii=False))
            sys.exit(1)

        args.marker.parent.mkdir(parents=True, exist_ok=True)
        marker = {
            "motor_activo": args.modelo,
            "estandar": modelo_previo,
            "trigger": "motor_fallback",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        args.marker.write_text(json.dumps(marker, ensure_ascii=False, indent=2),
                               encoding="utf-8")
        salida["backup"] = str(_BACKUP_DIR / f"motor_fallback_backup_{ts}.jsonc")
        print(json.dumps(salida, ensure_ascii=False))
        sys.exit(0)

    # modo == restore
    if not _PREVIO.is_file():
        salida.update({"estado": "error", "codigo": 1,
                       "motivo": "no hay backup previo para restaurar"})
        print(json.dumps(salida, ensure_ascii=False))
        sys.exit(1)

    contenido_previo = _PREVIO.read_text(encoding="utf-8")
    try:
        json.loads(contenido_previo)
    except json.JSONDecodeError as e:
        salida.update({"estado": "error", "codigo": 2,
                       "motivo": f"backup previo corrupto: {e}"})
        print(json.dumps(salida, ensure_ascii=False))
        sys.exit(2)

    modelo_previo_json = json.loads(contenido_previo).get("model")
    salida.update({"modelo_previo": modelo_previo_json})
    if args.dry_run:
        salida.update({"estado": "ok", "cambio": True, "dry_run": True,
                       "_vista_prevista": json.loads(contenido_previo)})
        print(json.dumps(salida, ensure_ascii=False))
        sys.exit(0)

    try:
        _escribir_atomico(args.config, contenido_previo)
    except (OSError, json.JSONDecodeError) as e:
        salida.update({"estado": "error", "codigo": 1,
                       "motivo": f"restauración fallida: {e}"})
        print(json.dumps(salida, ensure_ascii=False))
        sys.exit(1)

    try:
        args.marker.write_text("{}", encoding="utf-8")
    except OSError:
        pass

    salida.update({"estado": "ok", "cambio": True})
    print(json.dumps(salida, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()