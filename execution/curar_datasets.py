#!/usr/bin/env python3
"""
curar_datasets.py — Curación y empaquetado de datasets capturados (Layer 3: Execution)

Transforma los JSONL crudos capturados por data_capture.py en datasets curados,
deduplicados, validados y particionados en train/val/test, listos para entrenar
o comercializar en Web3.

El proceso es DETERMINISTA y NO destructivo: lee de datasets/*.jsonl y escribe
solo en datasets/curated/. Nunca modifica los archivos de captura crudos.

── PASOS ─────────────────────────────────────────────────────────────────────
  1. Cargar  : lee datasets/{rag_conversaciones,eda_imagen_circuito,analisis_imagenes}.jsonl
  2. Filtrar : quality_score >= --min-quality, contenido no vacío, longitud mínima
  3. Validar : exige id + metadata.schema_version + metadata.dataset coherente
  4. Dedupe  : hash canónico (ignora id/timestamp) descarta duplicados
  5. Particionar: train/val/test con estratificación por dataset (default 80/10/10)
  6. Empaquetar y reportar

── USO ──────────────────────────────────────────────────────────────────────────

    python3 execution/curar_datasets.py                 # cura con defaults
    python3 execution/curar_datasets.py --min-quality 0.8 --split 80-10-10
    python3 execution/curar_datasets.py --dry-run       # solo reportar, sin escribir

Salida: datasets/curated/ (muestras curadas + splits + manifest.json + resumen.md)

Interzipar desde un orquestador:
    from execution.curar_datasets import curar
    result = curar(min_quality=0.7)

Códigos de salida:
    0 → OK (curado o dry-run emitido)
    1 → sin datasets crudos para curar
    2 → error de configuración
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE  = Path(__file__).resolve().parents[1]
DATASETS   = WORKSPACE / "datasets"
CURATED    = DATASETS / "curated"
SPLITS     = CURATED / "splits"
MANIFEST   = CURATED / "manifest.json"
RESUMEN    = CURATED / "resumen.md"

MIN_TEXT_LEN = 20   # mínimo de caracteres de contenido útil por registro

# Datasets crudos que este flujo conoce (nombre de archivo → etiqueta descriptiva)
RAW_DATASETS = {
    "rag_conversaciones": "Conversaciones RAG (ShareGPT)",
    "eda_imagen_circuito": "EDA imagen → netlist",
    "analisis_imagenes": "Análisis multimodal de imágenes",
}


# ── Utilidades ────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_hash(record: dict) -> str:
    """Hash del contenido sin id/timestamp para detectar duplicados entre batches."""
    canonical = dict(record)
    canonical.pop("id", None)
    meta = canonical.get("metadata")
    if isinstance(meta, dict):
        meta = dict(meta)
        meta.pop("timestamp", None)
        canonical["metadata"] = meta
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _content_size(record: dict) -> int:
    """Tamaño del contenido útil según el tipo de dataset."""
    if "messages" in record:
        return sum(len(str(m.get("content", ""))) for m in record.get("messages", []))
    size = len(json.dumps(record.get("output", ""), ensure_ascii=False))
    size += sum(len(str(i)) for i in record.get("images", []))
    return size


# ── Paso 1-2: cargar, validar y filtrar ───────────────────────────────────────

def _load_raw(limit: int | None = None) -> list[tuple[str, dict]]:
    """Carga todos los registros crudos como (dataset, record)."""
    records: list[tuple[str, dict]] = []
    for stem, label in RAW_DATASETS.items():
        path = DATASETS / f"{stem}.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue  # línea corrupta → se ignora, no es crítica
            records.append((stem, rec))
    return records


def _validate(rec: dict) -> bool:
    """Valida el esquema mínimo de un registro curado."""
    meta = rec.get("metadata") or {}
    if not rec.get("id"):
        return False
    if meta.get("dataset") not in RAW_DATASETS:
        return False
    if not meta.get("schema_version"):
        return False
    return True


def curar(
    min_quality: float = 0.7,
    split: tuple[int, int, int] = (80, 10, 10),
    seed: int = 42,
    dry_run: bool = False,
) -> dict:
    """Ejecuta el pipeline de curado completo. Retorna un resumen JSON."""
    raw = _load_raw()

    if not raw:
        return {
            "status": "no_data", "exit_code": 1,
            "message": "No se encontraron datasets crudos en datasets/.",
        }

    # Filtrado + validación + dedup
    seen: set[str] = set()
    curados: list[tuple[str, dict]] = []
    rechazados = {"quality": 0, "schema": 0, "corto": 0, "duplicado": 0}
    quality_total: list[float] = []

    for dataset, rec in raw:
        meta = rec.get("metadata") or {}
        q = float(meta.get("quality_score", 0.0) or 0.0)
        quality_total.append(q)

        if not _validate(rec):
            rechazados["schema"] += 1
            continue
        if q < min_quality:
            rechazados["quality"] += 1
            continue
        if _content_size(rec) < MIN_TEXT_LEN:
            rechazados["corto"] += 1
            continue

        h = _canonical_hash(rec)
        if h in seen:
            rechazados["duplicado"] += 1
            continue
        seen.add(h)
        curados.append((dataset, rec))

    por_dataset: dict[str, list[dict]] = defaultdict(list)
    for dataset, rec in curados:
        por_dataset[dataset].append(rec)

    # Particionado estratificado por dataset
    partes = {"train": [], "val": [], "test": []}
    rng = random.Random(seed)
    for dataset, recs in por_dataset.items():
        recs = recs[:]
        rng.shuffle(recs)
        n = len(recs)
        n_val = round(n * split[1] / 100)
        n_test = round(n * split[2] / 100)
        partes["train"].extend(recs[: n - n_val - n_test])
        partes["val"].extend(recs[n - n_val - n_test: n - n_test])
        partes["test"].extend(recs[n - n_test:])

    if not dry_run:
        CURATED.mkdir(parents=True, exist_ok=True)
        SPLITS.mkdir(parents=True, exist_ok=True)
        for dataset, recs in por_dataset.items():
            (CURATED / f"{dataset}_curated.jsonl").write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n",
                encoding="utf-8",
            )
        for name, recs in partes.items():
            (SPLITS / f"{name}.jsonl").write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n",
                encoding="utf-8",
            )
        _write_manifest(por_dataset, partes, raw, rechazados, quality_total, min_quality, split)
        _write_resumen(por_dataset, partes, rechazados, min_quality)

    result = {
        "status": "ok",
        "exit_code": 0,
        "dry_run": dry_run,
        "crudos": len(raw),
        "curados": len(curados),
        "rechazados": rechazados,
        "por_dataset": {k: len(v) for k, v in por_dataset.items()},
        "splits": {k: len(v) for k, v in partes.items()},
        "salida": str(CURATED),
    }
    return result


def _write_manifest(
    por_dataset, partes, raw, rechazados, quality_total, min_quality, split
) -> None:
    ts = _now_iso()
    meta = {
        "generado": ts,
        "min_quality": min_quality,
        "split": {"train": split[0], "val": split[1], "test": split[2]},
        "totales": {
            "crudos": len(raw),
            "curados": sum(len(v) for v in por_dataset.values()),
            "train": len(partes["train"]),
            "val": len(partes["val"]),
            "test": len(partes["test"]),
        },
        "rechazados": rechazados,
        "por_dataset": {k: len(v) for k, v in por_dataset.items()},
    }
    if quality_total:
        meta["calidad_promedio"] = round(sum(quality_total) / len(quality_total), 3)
    MANIFEST.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_resumen(por_dataset, partes, rechazados, min_quality) -> None:
    lines = [
        "# Resumen de curado de datasets",
        "",
        f"- **Generado:** {_now_iso()}",
        f"- **Criterio de calidad:** mín. {min_quality}",
        f"- **Total curado:** {sum(len(v) for v in por_dataset.values())} registros",
        "",
        "## Por dataset",
        "",
        "| Dataset | Registros |",
        "|---------|----------:|",
    ]
    for k, v in sorted(por_dataset.items()):
        lines.append(f"| {RAW_DATASETS.get(k, k)} ({k}) | {len(v)} |")
    lines += ["", "## Splits (train/val/test)", "", f"- train: {len(partes['train'])}"]
    lines.append(f"- val:  {len(partes['val'])}")
    lines.append(f"- test: {len(partes['test'])}")
    lines += ["", "## Rechazados", ""]
    for k, v in rechazados.items():
        lines.append(f"- {k}: {v}")
    RESUMEN.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── CLI ────────────────────────────────────────────────────────────────────────

def _parse_split(s: str) -> tuple[int, int, int]:
    parts = [int(x) for x in s.replace(" ", "").split("-")]
    if len(parts) != 3 or sum(parts) != 100:
        raise ValueError(f"Split inválido '{s}': debe ser tres números que sumen 100 (ej. 80-10-10).")
    return (parts[0], parts[1], parts[2])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cura y particiona los datasets capturados por data_capture.py.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--min-quality", type=float, default=0.7,
                        help="Cota mínima de quality_score (default: 0.7).")
    parser.add_argument("--split", default="80-10-10",
                        help="Proporción train-val-test separada por guiones (default: 80-10-10).")
    parser.add_argument("--seed", type=int, default=42, help="Semilla aleatoria (default: 42).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo reportar el resultado sin escribir archivos curados.")
    args = parser.parse_args()

    try:
        split_tuple = _parse_split(args.split)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    result = curar(
        min_quality=args.min_quality,
        split=split_tuple,
        seed=args.seed,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result.get("exit_code", 0)


if __name__ == "__main__":
    sys.exit(main())