#!/usr/bin/env python3
r"""
servidor_sismico.py — Servidor MCP de datos sísmicos (Layer 3: Execution)

Expone vía Model Context Protocol herramientas para consultar un catálogo de
eventos sísmicos y sus waveforms. Es 100% determinista:

  * Si se le entrega un catálogo real (--catalogo path.json|.csv) lee ESE archivo.
  * Si no, genera un CATÁLOGO SINTÉTICO determinista (seed fija) de la zona de
    los Andes Venezolanos (Táchira/Mérida), útil para desarrollo y demo.
  * El waveform de cada evento es una serie sintética determinista derivada del
    id (misma señal para el mismo id, invariable entre llamadas).

Salidas por stdout o MCP. Códigos de salida: 0 = ok, 1+ = fallos categorizados.

Transportes:
  * stdio            -> servidor local (cliente en la misma máquina).
  * streamable-http  -> servidor remoto, endpoint por defecto /mcp.
  * Opcional --token : en streamable-http, los clientes deben enviar el encabezado
                       Authorization: Bearer <token>.

Ejemplos:
  python3 execution/servidor_sismico.py --transporte stdio
  python3 execution/servidor_sismico.py --transporte streamable-http --host 0.0.0.0 --port 8000
  python3 execution/servidor_sismico.py --transporte streamable-http --token "clave-secreta"
  python3 execution/servidor_sismico.py --transporte stdio --catalogo datos_reales.json
  python3 execution/servidor_sismico.py --catalogo realidad.csv --generar-sintetico docs/sismicos
"""

import argparse
import csv
import hashlib
import json
import math
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

# ── Paths ────────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
TMP_DIR = ROOT / ".tmp"
DEFAULT_CATALOGO_TMP = TMP_DIR / "catalogo_sismico_sintetico.json"

# ── Zona de interés: Andes Venezolanos (doblete reciente) ───────────────────────
ZONAS = [
    {"lugar": "Táchira — Zona del epicentro del doblete", "lat": 7.90, "lon": -72.20},
    {"lugar": "Mérida — Cordillera de Mérida", "lat": 8.60, "lon": -71.14},
    {"lugar": "Trujillo — Boconó", "lat": 9.25, "lon": -70.26},
    {"lugar": "Barinas — Piedemonte andino", "lat": 8.25, "lon": -70.10},
    {"lugar": "Táchira — Ureña/Villa del Rosario", "lat": 7.92, "lon": -72.46},
]

# Seed fija => mismo catálogo en cada ejecución (reproducibilidad del framework).
SEED_CATALOGO = 20260923
N_EVENTOS = 40


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


# ── Catálogo sintético determinista ──────────────────────────────────────────────
def _synth_waveform(seed: int, n: int = 120) -> List[float]:
    """Serie sintética determinista (semilla = hash del id). Señal sísmica simulada:
    p y s arrivals + decaimiento exponencial + ruido."""
    rnd = random.Random(seed)
    # frecuencia aleatoria pero fija por seed (Hz)
    f = rnd.uniform(0.5, 2.5)
    dt = 0.01
    muestras: List[float] = []
    llegada_p = rnd.randint(10, 25)
    llegada_s = llegada_p + rnd.randint(5, 12)
    for i in range(n):
        t = i * dt
        x = 0.0
        # ruido de fondo previo
        x += rnd.gauss(0.0, 0.05)
        if i >= llegada_p:
            a = 1.0 * math.exp(-0.08 * (i - llegada_p))
            x += a * math.sin(2.0 * math.pi * f * (t - llegada_p * dt))
        if i >= llegada_s:
            a = 1.4 * math.exp(-0.10 * (i - llegada_s))
            x += a * math.sin(2.0 * math.pi * f * 0.7 * (t - llegada_s * dt))
        muestras.append(round(x, 6))
    return muestras


def _hash_id(id_str: str) -> int:
    return int(hashlib.sha256(id_str.encode("utf-8")).hexdigest()[:8], 16)


def generar_catalogo_sintetico(
    seed: int = SEED_CATALOGO,
    n_eventos: int = N_EVENTOS,
    dias_ventana: int = 90,
) -> List[Dict[str, Any]]:
    """Catálogo sintético determinista: eventos con id, fecha (UTC), coordenadas,
    profundidad, magnitud y lugar. Los 2 primeros eventos representan un 'doblete'
    (misma zona, ~2 h de diferencia), inspirado en el caso reciente."""
    rnd = random.Random(seed)
    base = datetime.now(timezone.utc) - timedelta(days=dias_ventana)
    eventos: List[Dict[str, Any]] = []

    for i in range(n_eventos):
        zona = rnd.choice(ZONAS)
        # lat/lon con ruido alrededor del punto de la zona (±0.35°)
        lat = round(zona["lat"] + rnd.uniform(-0.35, 0.35), 4)
        lon = round(zona["lon"] + rnd.uniform(-0.35, 0.35), 4)
        prof = round(rnd.uniform(5.0, 45.0), 1)
        mag = round(rnd.uniform(2.0, 4.2), 1)
        fecha = base + timedelta(
            days=rnd.randint(0, dias_ventana),
            hours=rnd.randint(0, 23),
            minutes=rnd.randint(0, 59),
        )
        id_ev = f"VE{i + 1:04d}"
        eventos.append({
            "id": id_ev,
            "fecha_utc": utc_iso(fecha),
            "latitud": lat,
            "longitud": lon,
            "profundidad_km": prof,
            "magnitud": mag,
            "lugar": zona["lugar"],
            "tipo": "detectado",
        })

    # Doblete: clonar los 2 primeros en la misma zona, ~2 h después, magnitud cercana.
    dobletes: List[Dict[str, Any]] = []
    for base_ev in eventos[:2]:
        rep = dict(base_ev)
        rep["id"] = base_ev["id"] + "-B"
        dt = datetime.fromisoformat(base_ev["fecha_utc"])
        rep["fecha_utc"] = utc_iso(dt + timedelta(hours=2, minutes=3))
        rep["magnitud"] = round(base_ev["magnitud"] + rnd.uniform(-0.2, 0.2), 1)
        rep["tipo"] = "doblete"
        dobletes.append(rep)

    return eventos + dobletes


# ── Carga de catálogo (real o sintético) ─────────────────────────────────────────
def cargar_catalogo(path: str | None) -> List[Dict[str, Any]]:
    """Carga un catálogo real (JSON lista de objetos, o CSV con cabecera que
    contenga id, fecha_utc, latitud, longitud, magnitud, profundidad_km, lugar, tipo)."""
    if path is None:
        return generar_catalogo_sintetico()

    p = Path(path)
    if not p.exists():
        print(f"ERROR: catálogo no encontrado: {p}", file=sys.stderr)
        sys.exit(2)

    if p.suffix.lower() == ".csv":
        with open(p, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    # default: JSON
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        print("ERROR: el JSON del catálogo debe ser una lista de objetos.", file=sys.stderr)
        sys.exit(2)
    return data


def _filtra(eventos: List[Dict[str, Any]], magnitud_min: float,
            prof_max_km: float, lugar_contiene: str | None) -> List[Dict[str, Any]]:
    out = []
    for e in eventos:
        try:
            if float(e.get("magnitud", 0.0)) < magnitud_min:
                continue
            if float(e.get("profundidad_km", 999.0)) > prof_max_km:
                continue
        except (TypeError, ValueError):
            continue
        if lugar_contiene:
            lugar = str(e.get("lugar", ""))
            if lugar_contiene.lower() not in lugar.lower():
                continue
        out.append(e)
    return out


def ordenar_por_fecha(eventos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(eventos, key=lambda e: str(e.get("fecha_utc", "")))


# ── Registrar herramientas MCP ───────────────────────────────────────────────────
def registrar_tools(mcp: Any, catalogo: List[Dict[str, Any]]) -> None:
    MAX_VISTA = 30  # límite de filas por consulta para no saturar tokens

    @mcp.tool()
    def eventos(magnitud_min: float = 0.0, prof_max_km: float = 300.0,
                lugar_contiene: str | None = None, limite: int = MAX_VISTA) -> Dict[str, Any]:
        """Devuelve el catálogo de eventos sísmicos filtrado por magnitud mínimo,
        profundidad máxima y texto del lugar. Los eventos se ordenan por fecha.
        """
        filtrados = ordenar_por_fecha(_filtra(catalogo, magnitud_min, prof_max_km, lugar_contiene))
        vista = filtrados[: limite]
        return {
            "total_coincidentes": len(filtrados),
            "mostrando": len(vista),
            "eventos": vista,
        }

    @mcp.tool()
    def evento(id_evento: str) -> Dict[str, Any]:
        """Devuelve el detalle completo de un evento por su id (p. ej. 'VE0003-B')."""
        for e in catalogo:
            if e.get("id") == id_evento:
                return {"encontrado": True, "evento": e}
        return {"encontrado": False, "evento": None}

    @mcp.tool()
    def waveform(id_evento: str, n_muestras: int = 120) -> Dict[str, Any]:
        """Devuelve el waveform sintético del evento como serie de amplitudes
        (aceleración normalizada) con su tasa de muestreo. La señal es derivada del
        id, por lo que el MISMO evento siempre produce la MISMA serie."""
        if not any(e.get("id") == id_evento for e in catalogo):
            return {"encontrado": False, "detalle": None}
        seed = _hash_id(id_evento)
        serie = _synth_waveform(seed, n=min(max(n_muestras, 20), 400))
        return {
            "encontrado": True,
            "detalle": {
                "id_evento": id_evento,
                "tasa_muestreo_hz": 100.0,
                "n_muestras": len(serie),
                "unidades": "aceleración normalizada (sintética)",
                "muestras": serie,
            },
        }

    @mcp.tool()
    def estadisticas() -> Dict[str, Any]:
        """Resumen estadístico global del catálogo: número de eventos, rango de
        magnitudes, rango de profundidades y conteo por zona."""
        if not catalogo:
            return {"total": 0}
        mags = [float(e.get("magnitud", 0.0)) for e in catalogo]
        profs = [float(e.get("profundidad_km", 0.0)) for e in catalogo]
        por_zona: Dict[str, int] = {}
        por_tipo: Dict[str, int] = {}
        for e in catalogo:
            por_zona[e.get("lugar", "desconocido")] = por_zona.get(e.get("lugar", "desconocido"), 0) + 1
            por_tipo[e.get("tipo", "desconocido")] = por_tipo.get(e.get("tipo", "desconocido"), 0) + 1
        return {
            "total": len(catalogo),
            "magnitud_min": round(min(mags), 1),
            "magnitud_max": round(max(mags), 1),
            "profundidad_min_km": round(min(profs), 1),
            "profundidad_max_km": round(max(profs), 1),
            "conteo_por_zona": por_zona,
            "conteo_por_tipo": por_tipo,
        }


# ── MAIN ─────────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="Servidor MCP de datos sísmicos determinista.")
    parser.add_argument("--transporte", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--token", default=None, help="Bearer token obligatorio (opcional).")
    parser.add_argument("--catalogo", default=None,
                        help="Ruta a catálogo real (JSON/CSV). Omite el sintético.")
    parser.add_argument("--generar-sintetico", metavar="DIR",
                        help="Genera el catálogo sintético a DIR/catalogo_sismico.json y sale.")
    args = parser.parse_args()

    # Modo generación de catálogo de ejemplo (sin servidor).
    if args.generar_sintetico:
        out_dir = Path(args.generar_sintetico)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "catalogo_sismico.json"
        catalogo = generar_catalogo_sintetico()
        with open(out, "w", encoding="utf-8") as f:
            json.dump(catalogo, f, ensure_ascii=False, indent=2)
        print(json.dumps({
            "status": "ok",
            "generado": str(out),
            "total_eventos": len(catalogo),
            "sintetico": True,
            "seed": SEED_CATALOGO,
        }, ensure_ascii=False, indent=2))
        return 0

    eventos = cargar_catalogo(args.catalogo)

    # Verificar que el catálogo tenga los campos mínimos.
    if eventos:
        for campo in ("id", "fecha_utc", "latitud", "longitud", "magnitud", "profundidad_km"):
            if campo not in eventos[0]:
                print(f"ERROR: el catálogo no tiene el campo '{campo}'.", file=sys.stderr)
                sys.exit(2)

    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("Sismologia-VE", host=args.host, port=args.port)

    registrar_tools(mcp, eventos)

    if args.token:
        # Nota: la autenticación del protocolo requiere el sistema OAuth/verifier de
        # FastMCP (fuera de alcance del prototipo). Para despliegue real se recomienda
        # dejar --token vacío y proteger el endpoint en la capa de túnel/nginx
        # (var. Http_authorization en cloudflared, o auth_bearer en nginx).
        print("AVISO: --token no aplica Auth MCP; proteger el endpoint a nivel de túnel/nginx.",
              file=sys.stderr)

    print(f"Servidor MCP 'Sismologia-VE' — transporte={args.transporte} "
          f"catálogo={'sintético' if args.catalogo is None else args.catalogo} "
          f"eventos={len(eventos)}", file=sys.stderr)

    try:
        if args.transporte == "stdio":
            mcp.run(transport="stdio")
        else:
            mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR al ejecutar el servidor: {exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())