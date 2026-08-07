#!/usr/bin/env python3
"""
empaquetar_dataset.py — Empaquetado y licenciado de datasets curados (Layer 3: Execution)

Genera paquetes listos para publicar/entrenar/comercializar a partir de los datasets
curados por curar_datasets.py. Produce el formato oficial de Hugging Face
(dataset_info.json + Parquet) y una tarjeta de dataset (README.md) con metadata
de licencia, autor y versión, más un archivo LICENSE.

El proceso es DETERMINISTA y NO destructivo: lee datasets/curated/ y solo escribe
en datasets/paquetes/.

── ESTRUCTURA DE SALIDA ────────────────────────────────────────────────────────
datasets/paquetes/<dataset>/
  ├── dataset_info.json     → metadata HF (config, features, splits, license, citation)
  ├── README.md             → tarjeta de dataset (markdown)
  ├── LICENSE               → texto de licencia
  ├── train.parquet|jsonl
  ├── val.parquet|jsonl
  └── test.parquet|jsonl
datasets/paquetes/manifest.json   → resumen general de todos los paquetes

── USO ──────────────────────────────────────────────────────────────────────────
    python3 execution/empaquetar_dataset.py
    python3 execution/empaquetar_dataset.py --format jsonl --license apache-2.0
    python3 execution/empaquetar_dataset.py --license custom-proprietary --pack
    python3 execution/empaquetar_dataset.py --dry-run

Códigos de salida:
    0 → OK (paquetes generados o dry-run emitido)
    1 → sin datasets curados en datasets/curated/
    2 → error de configuración (licencia/formato desconocido)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
DATASETS  = WORKSPACE / "datasets"
CURATED   = DATASETS / "curated"
SPLITS    = CURATED / "splits"
PAQUETES  = DATASETS / "paquetes"
MANIFEST  = PAQUETES / "manifest.json"

DEFAULT_AUTHOR = "GIDEAL — Grupo de Investigación y Desarrollo Electrónico"
DEFAULT_VERSION = "1.0.0"

# Mapeo de licencia interna → identificador válido en Hugging Face Hub
# (para licencias propias se usa "other" + license_name/license_link en el frontmatter)
LICENCIA_HF = {
    "custom-proprietary": "other",
    "apache-2.0": "apache-2.0",
    "cc-by-4.0": "cc-by-4.0",
    "mit": "mit",
}

# ── Licencias disponibles ──────────────────────────────────────────────────────

LICENCIAS = {
    "custom-proprietary": {
        "nombre": "Licencia de datos propietarios GIDEAL",
        "abrev": "GIDEAL-1.0",
        "texto": """LICENCIA DE DATOS PROPIETARIOS GIDEAL v1.0

El presente conjunto de datos es propiedad de GIDEAL (Grupo de Investigación
y Desarrollo Electrónico) y del autor que lo publica.

Queda permitido:
  - El uso interno para investigación y entrenamiento de modelos dentro de la
    organización que adquiere la licencia.

Queda PROHIBIDO sin autorización expresa por escrito:
  - La redistribución, reventa, cesión o sublicencia de los datos, total o parcial.
  - El uso para entrenamiento de modelos que se comercialicen o publicuen fuera
    de la organización licenciada.
  - La extracción, minería o scraping de los datos para bases de datos propias.

Los datos se distribuyen "tal cual", sin garantías de exactitud ni idoneidad
para un fin particular. El licenciante no será responsable de daños derivados
de su uso. Esta licencia se rige por la ley de la República Bolivariana de
Venezuela y los tratados internacionales de propiedad intelectual aplicables.
""",
    },
    "apache-2.0": {
        "nombre": "Apache License 2.0",
        "abrev": "apache-2.0",
        "texto": "Licencia Apache 2.0 — http://www.apache.org/licenses/LICENSE-2.0",
    },
    "cc-by-4.0": {
        "nombre": "Creative Commons Attribution 4.0",
        "abrev": "cc-by-4.0",
        "texto": "Creative Commons Atribución 4.0 — https://creativecommons.org/licenses/by/4.0/legalcode",
    },
    "mit": {
        "nombre": "MIT License",
        "abrev": "mit",
        "texto": "MIT License — https://opensource.org/licenses/MIT",
    },
}

# Mapa de tipos JSON → dtype HF (para dataset_info.json)
_JSON_TO_DTYPE = {
    "str": "string",
    "int": "int64",
    "float": "float64",
    "bool": "bool",
    "list": "string",
    "dict": "struct",
    "NoneType": "null",
}


# ── Utilidades ──────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _infer_type(value):
    t = type(value).__name__
    if t == "list":
        if not value:
            return "sequence[string]"
        inner = _infer_type(value[0])
        inner = inner if isinstance(inner, str) else json.dumps(inner, ensure_ascii=False)
        return "sequence[" + inner + "]"
    if t == "dict":
        return {k: _infer_type(v) for k, v in value.items()}
    return _JSON_TO_DTYPE.get(t, "string")


def _infer_features(record: dict) -> dict:
    """Infiera el esquema de features a partir del primer registro."""
    features = {}
    for k, v in record.items():
        if k == "id":
            features[k] = "string"
            continue
        features[k] = _infer_type(v)
    return features


def _read_curated() -> dict[str, list[dict]]:
    """Lee los datasets curados por dataset (archivos *_curated.jsonl)."""
    por_dataset: dict[str, list[dict]] = {}
    for path in sorted(CURATED.glob("*_curated.jsonl")):
        dataset = path.name.replace("_curated.jsonl", "")
        recs = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        por_dataset[dataset] = recs
    return por_dataset


def _partition(
    recs: list[dict], split: tuple[int, int, int] = (80, 10, 10), seed: int = 42
) -> dict[str, list[dict]]:
    """Particiona un dataset en train/val/test (estratificado, determinista)."""
    recs = recs[:]
    rng = random.Random(seed)
    rng.shuffle(recs)
    n = len(recs)
    n_val = round(n * split[1] / 100)
    n_test = round(n * split[2] / 100)
    return {
        "train": recs[: n - n_val - n_test],
        "val": recs[n - n_val - n_test: n - n_test],
        "test": recs[n - n_test:],
    }


def _write_jsonl(path: Path, recs: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n",
        encoding="utf-8",
    )


def _write_parquet(path: Path, recs: list[dict]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    if not recs:
        # Parquet vacío con esquema mínimo
        table = pa.table({"empty": pa.array([], type=pa.string())})
        pq.write_table(table, path)
        return
    table = pa.Table.from_pylist(recs)
    pq.write_table(table, path)


def _dataset_card(
    nombre: str,
    descripcion: str,
    recs: list[dict],
    licencia: str,
    autor: str,
    version: str,
    features: dict,
) -> str:
    meta = recs[0].get("metadata", {}) if recs else {}
    source = meta.get("source", "GIDEAL")
    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    licencia_hf = LICENCIA_HF.get(licencia, "other")
    extra_lic = ""
    if licencia_hf == "other":
        extra_lic = (
            f"\nlicense_name: {licencia.lower()}"
            f"\nlicense_link: https://github.com/cero2k6/ELECTRONICA"
        )

    # Campos de ejemplo (primer registro, truncado)
    ejemplos = json.dumps(recs[0] if recs else {}, ensure_ascii=False, indent=2)[:1500]

    return f"""---
license: {licencia_hf}
{extra_lic}
task_categories:
  - text-generation
  - image-to-text
language:
  - es
tags:
  - gideal
  - electronica
  - entrenamiento-llm
size_categories:
  - n<1K
---

# {nombre}

- **Autor:** {autor}
- **Fuente:** {source}
- **Versión:** {version}
- **Licencia:** {licencia}
- **Fecha de empaquetado:** {fecha}
- **Descripción:** {descripcion}
- **Registros:** {len(recs)}

## Esquema (features)

```json
{json.dumps(features, ensure_ascii=False, indent=2)}
```

## Ejemplo

```json
{ejemplos}
```

## Uso en Hugging Face

Nota: desde la raíz de este workspace, el directorio local `datasets/` sombrea la
librería `datasets` de Hugging Face. Para cargar estos Parquet sin conflicto usa
`pyarrow` directamente:

```python
import pyarrow.parquet as pq

table = pq.read_table("datasets/paquetes/{nombre}/train.parquet")
print(table.to_pylist())
```

> **Aviso legal:** {licencia}. Ver archivo `LICENSE` del paquete para los términos
> exactos. Este dataset NO es de uso público general salvo indicación contraria.
"""


def empaquetar(
    fmt: str = "parquet",
    licencia: str = "custom-proprietary",
    autor: str = DEFAULT_AUTHOR,
    version: str = DEFAULT_VERSION,
    pack: bool = False,
    dry_run: bool = False,
) -> dict:
    """Empaqueta los datasets curados en paquetes listos para publicar."""
    if licencia not in LICENCIAS:
        return {"status": "error", "exit_code": 2,
                "message": f"Licencia desconocida '{licencia}'. Válidas: {list(LICENCIAS)}"}
    if fmt not in ("jsonl", "parquet"):
        return {"status": "error", "exit_code": 2,
                "message": f"Formato '{fmt}' inválido. Válidos: jsonl, parquet"}

    por_dataset = _read_curated()
    if not por_dataset:
        return {"status": "no_data", "exit_code": 1,
                "message": "No se encontraron datasets curados en datasets/curated/."}

    lic = LICENCIAS[licencia]
    result = {"status": "ok", "exit_code": 0, "dry_run": dry_run, "paquetes": {}}

    if not dry_run:
        PAQUETES.mkdir(parents=True, exist_ok=True)

    for dataset, recs in por_dataset.items():
        splits = _partition(recs)
        total = len(recs)
        features = _infer_features(recs[0]) if recs else {}

        card = _dataset_card(dataset, "Dataset curado y empaquetado por GIDEAL.",
                             recs, lic["abrev"], autor, version, features)

        pkg = result["paquetes"].setdefault(dataset, {
            "registros": total,
            "splits": {k: len(v) for k, v in splits.items()},
            "formato": fmt,
            "licencia": lic["abrev"],
            "version": version,
            "archivos": [],
        })

        if not dry_run:
            dir_paq = PAQUETES / dataset
            dir_paq.mkdir(parents=True, exist_ok=True)

            # dataset_info.json (formato HF)
            info = {
                "description": card.split("## Esquema")[0].replace("---\n", "").strip(),
                "license": lic["abrev"],
                "version": version,
                "features": features,
                "splits": {
                    name: {"name": name, "num_examples": len(s), "shard_lengths": [len(s)]}
                    for name, s in splits.items() if s
                },
                "download_size": None,
                "dataset_size": sum(
                    len(json.dumps(r, ensure_ascii=False)) for r in recs
                ),
                "citation": f"@misc{{gideal-{dataset.replace('_','-')},\n"
                            f"  author = {{{autor}}},\n"
                            f"  title = {{{dataset}}},\n"
                            f"  year = {{{datetime.now(timezone.utc).year}}},\n"
                            f"  note = {{Licencia {lic['abrev']}}} }}",
            }
            (dir_paq / "dataset_info.json").write_text(
                json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (dir_paq / "README.md").write_text(card, encoding="utf-8")
            (dir_paq / "LICENSE").write_text(lic["texto"], encoding="utf-8")

            # Datos por split
            for name, s in splits.items():
                if not s:
                    continue
                if fmt == "parquet":
                    _write_parquet(dir_paq / f"{name}.parquet", s)
                else:
                    _write_jsonl(dir_paq / f"{name}.jsonl", s)
                pkg["archivos"].append(f"{name}.{fmt}")

            pkg["archivos"].extend(["dataset_info.json", "README.md", "LICENSE"])

            # Empaquetado en tar.gz
            if pack:
                tar_path = PAQUETES / f"{dataset}.tar.gz"
                with tarfile.open(tar_path, "w:gz") as tar:
                    for f in pkg["archivos"]:
                        tar.add(dir_paq / f, arcname=f"{dataset}/{f}")
                pkg["archivo_tar"] = str(tar_path)

    if not dry_run:
        MANIFEST.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Empaqueta los datasets curados con licencia y metadata HF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--format", dest="fmt", default="parquet", choices=["jsonl", "parquet"],
                        help="Formato de almacenamiento de las muestras (default: parquet).")
    parser.add_argument("--license", default="custom-proprietary",
                        help="Licencia a aplicar (default: custom-proprietary).")
    parser.add_argument("--author", default=DEFAULT_AUTHOR, help="Autor/entidad propietaria.")
    parser.add_argument("--version", default=DEFAULT_VERSION, help="Versión del paquete.")
    parser.add_argument("--pack", action="store_true",
                        help="Además, genera un archivo .tar.gz por dataset.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo reportar el resultado sin escribir archivos.")
    args = parser.parse_args()

    result = empaquetar(
        fmt=args.fmt,
        licencia=args.license,
        autor=args.author,
        version=args.version,
        pack=args.pack,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result.get("exit_code", 0)


if __name__ == "__main__":
    sys.exit(main())