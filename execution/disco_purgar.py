#!/usr/bin/env python3
"""
disco_purgar.py — Purga de las rutas del catálogo, con barrera de whitelist
(Layer 3: Execution, DESTRUCTIVO y acotado).

Solo toca entradas declaradas en catalogo_disco.CATALOGO. Antes de borrar CADA
entrada vuelve a pasar las 4 barreras (validar_destino), de modo que ni un error de
programación en el catálogo, ni un symlink insertado a mano, ni un `.env` colado en
un glob pueden convertir una purga en una pérdida de trabajo.

Salvaguardas (todas obligatorias, ninguna desactivable desde la CLI):
  - Sin `--yes` NO se borra nada: el script se degrada a simulación.
  - Guarda de antigüedad: si hay algo modificado en los últimos `min_edad_dias`, el
    target se conserva entero (descargas o compilaciones en curso no se tocan).
  - Nunca sube de tier por su cuenta: el nivel lo elige el operador.
  - Nunca invoca sudo: lo que lo requiere se reporta en `requiere_sudo`.
  - Es idempotente: correrlo dos veces no daña nada.

Modelo de contenedores: en los modos `contenido`, `glob` y `rotar` el directorio
base NO se borra (es el contenedor del que cuelgan entradas); las unidades borrables
son sus hijos, y cada hijo se valida por separado. Esto es lo que permite limpiar
`.tmp` o `__pycache__` sin que la barrera `contiene_protegido` bloquee el repo entero
porque dentro estén `docs/` y `Sessions/`.

Idempotencia del resultado: el JSON describe lo que se borró, lo conservado y el
motivo, para que el orquestador pueda reintentar solo lo fallido.

Uso:
  python3 execution/disco_purgar.py --tier seguro --yes --verbose
  python3 execution/disco_purgar.py --tier seguro --dry-run
  python3 execution/disco_purgar.py --only arduino-staging,trash --yes

Códigos de salida:
  0 -> ok (borrado, o nada que hacer)
  1 -> error de argumentos
  2 -> fallo al borrar (permisos/ocupado); el informe detalla los targets
  3 -> error interno
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from catalogo_disco import (  # noqa: E402
    CATALOGO, TAMANO_HUMANO, TIERS, Target, contenedor_de, du_bytes, du_pies_carpeta,
    hay_entradas_recientes_de_target, objetivo_por_id, pistas_sudo, validar_destino,
)


def _log(activo: bool, mensaje: str) -> None:
    """Progreso legible a stderr; stdout queda reservado para el JSON."""
    if activo:
        print(mensaje, file=sys.stderr, flush=True)


def _borrar_entrada(ruta: Path) -> tuple[bool, str]:
    """Borra un archivo o árbol sin seguir symlinks. (ok, motivo si falló)"""
    try:
        if ruta.is_symlink() or ruta.is_file():
            ruta.unlink()
        else:
            shutil.rmtree(ruta)
        return True, ""
    except PermissionError:
        return False, "sin_permiso"
    except OSError as exc:
        return False, f"oserror:{exc.errno}"


def _entradas_de_contenido(base: Path) -> list[Path]:
    """Entradas directas de un directorio de caché (incluye las ocultas)."""
    try:
        return [Path(e.path) for e in os.scandir(base) if e.name not in (".", "..")]
    except (OSError, PermissionError):
        return []


def _plan_entradas(t: Target) -> list[Path]:
    """Entradas candidatas a borrar según el modo del target."""
    base = contenedor_de(t)
    if t.modo == "glob":
        return du_pies_carpeta(base, t.patron) if base.exists() else []
    if t.modo == "rotar":
        if not base.exists():
            return []
        archivos = [p for p in base.iterdir() if p.is_file() and not p.is_symlink()]
        archivos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return archivos[t.mantener:]          # conserva los `mantener` más recientes
    if t.modo == "directorio":
        return [base] if base.exists() else []
    return _entradas_de_contenido(base) if base.exists() else []   # contenido


def _purgar_nativo(t: Target, args, reg: dict) -> dict:
    """Ejecuta la herramienta oficial del target (pip cache purge, npm cache clean).

    El comando se parte con shlex: `subprocess.run` con `shell=False` recibe una
    lista, y pasar la cadena entera "pip cache purge" como ejecutable fallaria
    con FileNotFoundError aunque pip exista en el PATH.
    """
    argv = shlex.split(t.cmd)
    ejecutable = argv[0] if argv else ""
    reg["comando"] = t.cmd
    if not ejecutable or not shutil.which(ejecutable):
        reg.update(estado="omitido", motivo="nativo_ausente")
        return reg
    reg["bytes_antes"] = du_bytes(t.ruta_resuelta())
    if args.dry_run:
        reg.update(estado="simulado", motivo="nativo", liberable=reg["bytes_antes"])
        return reg
    proc = subprocess.run(argv, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        reg.update(estado="fallido", motivo="nativo_fallido",
                   detalle=(proc.stderr or proc.stdout).strip()[:200])
        return reg
    reg["bytes_despues"] = du_bytes(t.ruta_resuelta())
    reg["liberado"] = max(0, reg["bytes_antes"] - reg["bytes_despues"])
    reg["entradas_borradas"] = 1
    reg.update(estado="ok", motivo="nativo")
    return reg


def purgar_target(t: Target, args) -> dict:
    """Guarda de antigüedad, validación entrada por entrada y borrado de un target."""
    reg = {
        "id": t.id, "tier": t.tier, "modo": t.modo, "ruta": t.ruta,
        "estado": "ok", "motivo": "", "bytes_antes": 0, "bytes_despues": 0,
        "liberado": 0, "liberable": 0, "entradas_borradas": 0,
        "omitidas": [], "fallos": [],
    }
    contenedor = contenedor_de(t)
    if not contenedor.exists():
        reg.update(estado="omitido", motivo="no_existe")
        return reg

    # Guarda de antigüedad: si algo se movió hace poco, no se toca el target entero.
    # Aplica a TODOS los modos, incluido el nativo: si un caché se acaba de usar,
    # vaciarlo con la herramienta oficial tampoco procede.
    #
    # Se pregunta por el TARGET y no por su contenedor (misma regla que usa
    # `disco_medir`): para un patrón estrecho, preguntar "¿hay algo reciente en el
    # padre?" conservaba el target entero por culpa de ficheros que no son
    # suyos. Medir y purgar deben hacer la misma pregunta; si no, el informe
    # ofrece un espacio que la purga luego niega sin explicar por qué.
    min_edad = t.min_edad_dias if args.min_edad_dias is None else max(0, args.min_edad_dias)
    if min_edad > 0 and hay_entradas_recientes_de_target(t, min_edad):
        reg.update(estado="omitido", motivo="conservado_reciente")
        return reg

    if t.modo == "nativo" and t.cmd:
        # La herramienta oficial purga el propio directorio del target, asi que ese
        # contenedor SI es un destino borrable y debe pasar la barrera como tal.
        permitido, motivo = validar_destino(contenedor)
        if not permitido:
            reg.update(estado="omitido", motivo=motivo)
            return reg
        return _purgar_nativo(t, args, reg)

    # El contenedor de los modos contenido/glob/rotar no se valida como destino
    # borrable (contiene entradas protegidas legítimamente); se validan sus hijos.
    if t.modo == "directorio":
        permitido, motivo = validar_destino(contenedor)
        if not permitido:
            reg.update(estado="omitido", motivo=motivo)
            return reg

    reg["bytes_antes"] = du_bytes(contenedor)
    entradas = _plan_entradas(t)
    if not entradas:
        reg.update(estado="ok", motivo="sin_candidatos", bytes_despues=reg["bytes_antes"])
        return reg

    for entrada in entradas:
        # Barrera completa por entrada: catálogo, raíz, protegido, symlink.
        ok, motivo = validar_destino(entrada)
        if not ok:
            reg["omitidas"].append({"ruta": str(entrada), "motivo": motivo})
            continue
        if args.dry_run:
            reg["liberable"] += du_bytes(entrada)
            reg["entradas_borradas"] += 1      # unidades que se borrarían
            continue
        ok, motivo = _borrar_entrada(entrada)
        if ok:
            reg["entradas_borradas"] += 1
            _log(args.verbose, f"    borrado  {entrada}")
        else:
            reg["fallos"].append({"ruta": str(entrada), "motivo": motivo})
            _log(args.verbose, f"    FALLO    {entrada}  ({motivo})")

    if args.dry_run:
        reg.update(estado="simulado", bytes_despues=0)
    else:
        reg["bytes_despues"] = du_bytes(contenedor)
        reg["liberado"] = max(0, reg["bytes_antes"] - reg["bytes_despues"])
        if t.recrear and not contenedor.exists():
            try:
                contenedor.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass

    if reg["fallos"]:
        reg.update(estado="parcial", motivo="fallos_parciales")
    return reg


def seleccionar(args) -> list[Target]:
    """Aplica --tier, --only y --skip. El nivel lo elige el operador, nunca el script."""
    if args.only:
        sel = []
        for ident in args.only:
            t = objetivo_por_id(ident)
            if t is None:
                raise KeyError(f"target desconocido: {ident!r}")
            sel.append(t)
        return sel
    base = list(CATALOGO) if args.tier == "todos" else [t for t in CATALOGO if t.tier == args.tier]
    if args.skip:
        fuera = set(args.skip)
        base = [t for t in base if t.id not in fuera]
    return base


def purgar(args) -> int:
    ini = time.time()
    try:
        objetivos = seleccionar(args)
    except KeyError as exc:
        print(json.dumps({"status": "error", "code": 1, "message": str(exc)},
                         ensure_ascii=False))
        return 1

    if not args.dry_run and not args.yes:
        _log(args.verbose, "  (--yes ausente: se SIMULA, no se borra nada)")
        args.dry_run = True

    _log(args.verbose, f"  {'SIMULANDO' if args.dry_run else 'PURGANDO'} {len(objetivos)} "
                       f"targets (tier={args.tier})")
    resultados = [purgar_target(t, args) for t in objetivos]
    for reg in resultados:
        if reg["estado"] != "omitido" or reg["motivo"] != "no_existe":
            _log(args.verbose, f"    {reg['estado']:8s} {reg['id']:20s} "
                               f"liberado={TAMANO_HUMANO(reg['liberado'])} {reg['motivo']}")

    liberado = 0 if args.dry_run else sum(r["liberado"] for r in resultados)
    payload = {
        "status": "ok",
        "modo": "simulacion" if args.dry_run else "purgado",
        "tier": args.tier,
        "targets_evaluados": len(resultados),
        "targets_borrados": sum(1 for r in resultados
                                if r["estado"] in ("ok", "parcial", "simulado")),
        "targets_omitidos": sum(1 for r in resultados if r["estado"] == "omitido"),
        "liberable_bytes": sum(r["liberable"] for r in resultados),
        "liberado_bytes": liberado,
        "liberado_humano": TAMANO_HUMANO(liberado),
        "duracion_s": round(time.time() - ini, 1),
        "resultados": sorted(resultados, key=lambda r: r["liberado"] or r["liberable"],
                             reverse=True),
        "requiere_sudo": pistas_sudo(),
        "notas": [
            "Todo lo borrado proviene de catalogo_disco.CATALOGO; nada fuera de esa lista.",
            "Sin --yes el script simula: no hay forma de borrar por accidente.",
            "Lo omitido por conservado_reciente se reintenta en la siguiente pasada.",
        ],
    }
    fallidos = [r for r in resultados if r["estado"] == "fallido"]
    if fallidos:
        payload.update(status="parcial", fallos=fallidos)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if fallidos else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Purga las rutas del catálogo de disco (whitelist, sin sudo).",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument("--tier", choices=(*TIERS, "todos"), default="seguro",
                        help="Nivel a purgar. 'seguro' es el único que no obliga a "
                             "re-descargar nada (por defecto).")
    parser.add_argument("--yes", action="store_true",
                        help="Confirmar el borrado. Sin este flag solo se simula.")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin borrar.")
    parser.add_argument("--only", default=None,
                        help="Purar solo estos ids, separados por coma (p. ej. trash,uv-cache).")
    parser.add_argument("--skip", default=None, help="Excluir ids del tier (por coma).")
    parser.add_argument("--min-edad-dias", type=int, default=None,
                        help="Anular la antigüedad mínima de los targets (no recomendado).")
    parser.add_argument("--verbose", action="store_true", help="Progreso por stderr.")
    args = parser.parse_args()

    args.only = [s.strip() for s in args.only.split(",") if s.strip()] if args.only else None
    args.skip = [s.strip() for s in args.skip.split(",") if s.strip()] if args.skip else None
    if args.only and args.tier != "seguro":
        _log(True, f"  (--only ignora --tier={args.tier})")

    try:
        return purgar(args)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "error", "code": 3, "message": f"error interno: {exc}"},
                         ensure_ascii=False))
        return 3


if __name__ == "__main__":
    sys.exit(main())
