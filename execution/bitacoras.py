#!/usr/bin/env python3
r"""
bitacoras.py — Gestión de las bitácoras de sesión de ALTO NIVEL (Layer 3: Execution).

La memoria del workspace tiene dos capas:
  - BAJO nivel (datos): session_log_*.jsonl + run_state*.json — los gestiona
    estado_sesion.py. Reproducible, inmutable, ya blindado.
  - ALTO nivel (significado): Sessions/YYYY-MM-DD_<tema>.md — por QUÉ se decidió,
    qué se descartó, intenciones del usuario, matices. Este fichero NO vive en
    ningún log de ejecución: es el eslabón semántico de la continuidad.

Bitácora canónica: "Sessions/YYYY-MM-DD_<tema>.md" con secciones
  - ## Tema                — qué se abordó (1 frase)
  - ## Contexto           — detectos/porqué (opcional, recomendable)
  - ## Decisiones (usuario) — acuerdos explícitos del usuario (NO inventar)
  - ## Actividades        — qué se hizo (pasos/salidas)
  - ## Pendientes         — qué queda abierto/pendiente acordado

Comandos:
  nueva --tema "Tema de sesión"   — crea la bitácora de HOY si no existe
                                     (nunca sobrescribe). Salida: ruta + existía/creada.
  check [--today]                 — valida estructura de las bitácoras existentes:
                                     nombre (YYYY-MM-DD_tema.md), fecha parseable,
                                     secciones mínimas, y (si --today/por defecto)
                                     si la sesión de hoy tiene bitácora abierta.
                                     Solo diagnostica: 0 créditos, no borra nada.

Uso:
  python3 execution/bitacoras.py nueva --tema "Tema de sesión"
  python3 execution/bitacoras.py check
  python3 execution/bitacoras.py check --today

Códigos de salida:
  0 -> ok
  1 -> error de argumentos / uso
  2 -> check encontró anomalías estructurales
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
SESSIONS_DIR = SCRIPT_DIR / "Sessions"

SECCIONES_REQUERIDAS = ["## Tema", "## Decisiones (usuario)", "## Actividades", "## Pendientes"]
# Desde esta fecha las bitácoras deben seguir la plantilla canónica (PLANTILLA).
# Todo lo anterior es "legado transicional" que respetaba otra convención.
FECHA_PLANTILLA = date(2026, 9, 11)
PLANTILLA = """# @@FECHA@@ — @@TEMA@@

## Tema
@@TEMA@@

## Contexto
- (Por qué se aborda / eventos detectados que motivan la sesión.)

## Decisiones (usuario)
1. (Acuerdos explícitos del usuario. NO inventar; si no hay, anotar qué se
   asumió y por qué.)

## Actividades
- (Qué se hizo: pasos, scripts, salidas, veredictos.)

## Pendientes
- (Qué queda abierto; pendientes acordados de otras sesiones que NO se tocaron.)
"""


def _error(message: str, code: int = 1) -> int:
    print(f"error: {message}", file=sys.stderr)
    return code


_TRANSLIT = str.maketrans({
    "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
    "ü": "u", "ñ": "n", "Á": "a", "É": "e", "Í": "i",
    "Ó": "o", "Ú": "u", "Ü": "u", "Ñ": "n",
})


def _slug(tema: str) -> str:
    """Convierte el tema a nombre de archivo seguro (snake_case, ASCII)."""
    s = tema.translate(_TRANSLIT)
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return s[:60] or "sesion"


def nueva(tema: str) -> int:
    """Crea la bitácora de hoy. Nunca sobrescribe archivos existentes."""
    if not tema or not tema.strip():
        raise SystemExit(_error("El --tema es obligatorio."))
    fecha = date.today()
    nombre = f"{fecha.isoformat()}_{_slug(tema)}.md"
    ruta = SESSIONS_DIR / nombre

    creada = not ruta.exists()
    if creada:
        contenido = PLANTILLA.replace("@@FECHA@@", fecha.isoformat()).replace(
            "@@TEMA@@", tema.strip())
        ruta.write_text(contenido, encoding="utf-8")
        print(f"creada: {ruta}")
    else:
        print(f"ya_existia: {ruta} (no se sobrescribe)")

    import json
    print(json.dumps({"status": "ok", "archivo": str(ruta), "creada": creada,
                      "fecha": fecha.isoformat(), "tema": tema.strip()},
                     ensure_ascii=False, indent=2))
    return 0


def _validar_bitacora(ruta: Path, hoy: date) -> dict:
    """Evalúa una bitácora: nombre, fecha, secciones y periodo (hoy/reciente/legado)."""
    nombre = ruta.name
    base = {"archivo": str(ruta), "nombre": nombre}
    problemas: list[str] = []
    periodo = "legado"

    m = re.match(r"^(\d{4}-\d{2}-\d{2})_(.+)\.md$", nombre)
    if not m:
        problemas.append("nombre fuera de convención (YYYY-MM-DD_<tema>.md)")
    else:
        try:
            fecha = date.fromisoformat(m.group(1))
            if fecha > hoy:
                problemas.append("fecha en el futuro")
                periodo = "reciente"
            elif fecha >= FECHA_PLANTILLA:
                periodo = "hoy" if fecha == hoy else "reciente"
            # legado (anterior a la plantilla): estructura histórica, informativo
        except ValueError:
            problemas.append("fecha inválida")

    try:
        texto = ruta.read_text(encoding="utf-8")
    except Exception as exc:
        problemas.append(f"no legible: {exc}")
        texto = ""

    for sec in SECCIONES_REQUERIDAS:
        if sec not in texto:
            problemas.append(f"falta sección '{sec}'")

    if len(texto.strip()) < 60:
        problemas.append("contenido muy corto (¿plantilla sin rellenar?)")

    base["problemas"] = problemas
    base["periodo"] = periodo
    # Las bitácoras LEGADO responden a otra convención: se listan informativamente
    # pero solo hoy/reciente cuentan como anomalía estructural accionable.
    base["ok"] = (not problemas) or periodo == "legado"
    return base


def check(only_today: bool) -> int:
    """Diagnostica la estructura de las bitácoras. Nunca borra ni edita."""
    import json
    if not SESSIONS_DIR.exists():
        print(json.dumps({"status": "error", "message": f"No existe {SESSIONS_DIR}"},
                         ensure_ascii=False))
        return 2

    bitacoras = sorted(SESSIONS_DIR.glob("*.md"))
    anomalies = 0
    accionables = 0
    resultado: list[dict] = []
    hoy = date.today()

    for r in bitacoras:
        if only_today and not r.name.startswith(hoy.isoformat()):
            continue
        info = _validar_bitacora(r, hoy)
        resultado.append(info)
        if not info["ok"]:
            anomalies += 1
            if info["periodo"] != "legado":
                accionables += 1

    # Continuidad del día: ¿la sesión de hoy ya dejó bitácora?
    hoy_prefix = hoy.isoformat()
    hoy_bitacoras = [r for r in bitacoras if r.name.startswith(hoy_prefix)]
    if accionables > 0:
        veredicto = "atencion"
    elif not hoy_bitacoras:
        veredicto = "atencion"  # la sesión del día aún no tiene bitácora
    else:
        veredicto = "ok"
    payload = {
        "bitacoras": resultado,
        "sesion_hoy": {
            "fecha": hoy.isoformat(),
            "hay_bitacora": bool(hoy_bitacoras),
            "archivos": [str(r) for r in hoy_bitacoras],
        },
        "anomalias": anomalies,
        "accionables": accionables,
        "veredicto_global": veredicto,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 2 if accionables else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)

    p_nueva = sub.add_parser("nueva", help="Crea la bitácora de hoy.")
    p_nueva.add_argument("--tema", required=True, help="Tema de la sesión.")

    p_check = sub.add_parser("check", help="Valida la estructura de las bitácoras.")
    p_check.add_argument("--today", action="store_true",
                         help="Solo validar la/s bitácora/s de hoy.")
    args = parser.parse_args()

    if args.comando == "nueva":
        return nueva(args.tema)
    if args.comando == "check":
        return check(args.today)
    return _error("Comando no soportado.", 3)


if __name__ == "__main__":
    sys.exit(main())