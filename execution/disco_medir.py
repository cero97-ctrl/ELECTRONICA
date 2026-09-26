#!/usr/bin/env python3
"""
disco_medir.py — Medición del estado del disco y dimensionamiento de la whitelist
(Layer 3: Execution, SOLO LECTURA).

Mide, sin modificar nada:
  - Espacio del sistema de archivos (total, usado, libre, % de uso) y estado de INODOS
    (un disco puede tener espacio libre y estar "lleno" por inodos agotados).
  - Tamaño real (bytes de disco, no lógicos) de cada entrada de catalogo_disco.CATALOGO,
    con su antigüedad y el motivo por el que sería o no borrable.
  - Los directorios más pesados de $HOME y los archivos individuales más grandes
    (diagnóstico: sirve para descubrir basura que no está en el catálogo).
  - Rutas que requieren sudo: se INFORMAN, nunca se purgan (ver --sudo-hint).

Determinismo: mismo estado del disco -> mismo JSON. No inventa umbrales.

Uso:
  python3 execution/disco_medir.py [--top-dirs 12] [--top-files 15] [--output RUTA]
  python3 execution/disco_medir.py --sudo-hint

Códigos de salida:
  0 -> ok
  1 -> error de argumentos
  2 -> no se pudo leer el sistema de archivos
  3 -> error interno
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from catalogo_disco import (  # noqa: E402
    CATALOGO, HOME, REPO_ROOT, TAMANO_HUMANO, contenedor_de, du_bytes, du_bytes_lote,
    du_hijos, du_mayores, du_pies_carpeta, edad_entrada_dias, hay_entradas_recientes,
    pistas_sudo, validar_destino,
)

GB = 1024 ** 3


def _error(message: str, code: int) -> int:
    print(json.dumps({"status": "error", "code": code, "message": message}, ensure_ascii=False))
    return code


def medir_filesystem(ruta: str = "/") -> dict:
    """Espacio e inodos del filesystem que contiene `ruta`."""
    try:
        st = os.statvfs(ruta)
    except OSError as exc:
        raise RuntimeError(f"statvfs({ruta}) falló: {exc}") from exc
    total = st.f_blocks * st.f_frsize
    libre = st.f_bavail * st.f_frsize
    usado = total - st.f_bavail * st.f_frsize
    ino_total = st.f_files
    ino_libre = st.f_favail
    return {
        "ruta": ruta,
        "total_gb": round(total / GB, 2),
        "usado_gb": round(usado / GB, 2),
        "libre_gb": round(libre / GB, 2),
        "uso_pct": round(100.0 * usado / total, 1) if total else 0.0,
        "inodos_total": ino_total,
        "inodos_libres": ino_libre,
        "inodos_usados_pct": round(100.0 * (1 - ino_libre / ino_total), 1) if ino_total else 0.0,
        # f_bavail ya descuenta la reserva del sistema para usuarios sin privilegios,
        # así que `libre` es el espacio realmente utilizable (no restar otro 5%).
    }


def medir_targets() -> list[dict]:
    """Dimensiona cada entrada del catálogo (sin tocar nada)."""
    salida = []
    for t in CATALOGO:
        ruta = t.ruta_resuelta()
        # El contenedor lo decide el catálogo (fuente única): un glob puede no
        # llevar comodín en la ruta, así que buscar '*' medía el directorio
        # equivocado (el padre del repo entero).
        es_glob = t.modo == "glob"
        base = contenedor_de(t)
        existe = base.exists()
        if not existe:
            bytes_disco = 0
        elif es_glob:
            # Sumar solo las coincidencias: medir el padre (el repo entero) sería
            # inventar una cifra que no corresponde al target.
            bytes_disco = du_bytes_lote(du_pies_carpeta(base, t.patron))
        else:
            bytes_disco = du_bytes(ruta)
        # El modo decide cuál es la unidad borrable. En directorio/nativo esa unidad
        # es el propio contenedor, así que tiene que pasar la barrera como destino. En
        # contenido/glob/rotar el contenedor NUNCA se borra: solo sus entradas, que
        # disco_purgar.py revalida una a una. Validar el contenedor en esos modos
        # devolvía "raiz_no_permitida" (repo) o "no_existe" (el comodín no es una
        # ruta) y dejaba el target con 0 bytes purgables aunque sus entradas fueran
        # legítimas. Aquí se estima un techo; la barrera la aplica la capa de purga.
        if t.modo in ("directorio", "nativo"):
            permitido, motivo = (True, "ok") if not existe else validar_destino(ruta)
            unidad = "contenedor"
        else:
            permitido, motivo = True, "entradas_validadas_en_purga"
            unidad = "entradas"
        # Lo medido no es lo purgable: la guarda de antigüedad puede conservar el
        # target entero. Sin esto, quien decide vería espacio disponible que en
        # realidad no se puede tocar y despertaría para no hacer nada.
        reciente = bool(existe and t.min_edad_dias > 0
                        and hay_entradas_recientes(base, t.min_edad_dias))
        purgable = bool(existe and permitido and not reciente)
        if reciente:
            motivo = f"conservado_reciente(min_{t.min_edad_dias}d)"
        salida.append({
            "id": t.id,
            "tier": t.tier,
            "modo": t.modo,
            "ruta": t.ruta,
            "existe": existe,
            "bytes_disco": bytes_disco,
            "tamano_humano": TAMANO_HUMANO(bytes_disco),
            "bytes_purgables": bytes_disco if purgable else 0,
            "edad_dir_dias": round(edad_entrada_dias(base), 2) if existe else -1.0,
            "min_edad_dias": t.min_edad_dias,
            "borrable": purgable,
            "unidad_borrable": unidad,
            "conservado_reciente": reciente,
            "motivo": motivo,
            "descripcion": t.descripcion,
        })
    return salida


def _top_dirs(limite: int) -> list[dict]:
    """Subdirectorios de $HOME ordenados por peso real (una sola pasada de du)."""
    return [{"ruta": str(p), "bytes_disco": b, "tamano_humano": TAMANO_HUMANO(b)}
            for p, b in du_hijos(HOME)[:limite]]


def _top_files(limite: int) -> list[dict]:
    """Archivos individuales más grandes bajo $HOME (una sola pasada de find)."""
    return [{"ruta": str(p), "bytes_disco": b, "tamano_humano": TAMANO_HUMANO(b)}
            for b, p in du_mayores(HOME, limite)]


def medir_todo(top_dirs: int, top_files: int) -> dict:
    fs = medir_filesystem("/")
    targets = medir_targets()

    por_tier: dict[str, int] = {}
    medido_por_tier: dict[str, int] = {}
    for t in targets:
        if not t["existe"]:
            continue
        medido_por_tier[t["tier"]] = medido_por_tier.get(t["tier"], 0) + t["bytes_disco"]
        if t["borrable"]:
            por_tier[t["tier"]] = por_tier.get(t["tier"], 0) + t["bytes_purgables"]

    payload = {
        "filesystem": fs,
        "resumen_catalogo": {
            "entradas": len(targets),
            "reclaimable_por_tier": {
                k: {"bytes": v, "humano": TAMANO_HUMANO(v)} for k, v in sorted(por_tier.items())
            },
            "reclaimable_total_bytes": sum(por_tier.values()),
            "reclaimable_total": TAMANO_HUMANO(sum(por_tier.values())),
            "medido_por_tier": {
                k: {"bytes": v, "humano": TAMANO_HUMANO(v)}
                for k, v in sorted(medido_por_tier.items())
            },
            "medido_total": TAMANO_HUMANO(sum(medido_por_tier.values())),
            "nota_reclaimable": ("reclaimable = lo que se puede borrar AHORA (aplica la "
                                 "barrera y la guarda de antigüedad); medido = lo que "
                                 "ocupa el disco, sea purgable o no."),
        },
        "targets": sorted(targets, key=lambda t: t["bytes_disco"], reverse=True),
        "rutas_que_requieren_sudo": pistas_sudo(),
        "notas": [
            "bytes_disco mide bloques asignados: es el espacio que se recupera, no el lógico.",
            "Un disco con inodos al >80% se llena aunque haya gigabytes libres.",
            "Este script no modifica nada; el borrado vive en disco_purgar.py.",
        ],
    }
    # El escaneo profundo de $HOME cuesta ~1 min (1.6M inodos): solo bajo demanda.
    if top_dirs > 0:
        payload["top_directorios_home"] = _top_dirs(top_dirs)
    if top_files > 0:
        payload["top_archivos"] = _top_files(top_files)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Mide el disco y dimensiona la whitelist (solo lectura).")
    parser.add_argument("--top-dirs", type=int, default=0,
                        help="Directorios más pesados de $HOME. 0 = omitir (cada pasada "
                             "recorre ~1.6M inodos y cuesta minutos).")
    parser.add_argument("--top-files", type=int, default=0,
                        help="Archivos más grandes de $HOME. 0 = omitir (mismo coste).")
    parser.add_argument("--output", default=None, help="Además de stdout, escribir el JSON aquí.")
    parser.add_argument("--sudo-hint", action="store_true",
                        help="Solo imprime las rutas que requieren sudo y sale.")
    args = parser.parse_args()

    if args.sudo_hint:
        print(json.dumps({"status": "ok", "requieren_sudo": pistas_sudo()},
                         ensure_ascii=False, indent=2))
        return 0

    try:
        payload = medir_todo(max(args.top_dirs, 0), max(args.top_files, 0))
    except RuntimeError as exc:
        return _error(str(exc), 2)
    except Exception as exc:  # noqa: BLE001
        return _error(f"error interno: {exc}", 3)

    payload["status"] = "ok"
    texto = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(texto + "\n", encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
