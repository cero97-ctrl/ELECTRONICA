#!/usr/bin/env python3
"""
publicar_hf.py — Publicación de datasets en Hugging Face Hub (Layer 3: Execution)

Sube un paquete generado por empaquetar_dataset.py a un repositorio de datasets
en Hugging Face Hub, con su metadata (dataset_info.json, README.md, LICENSE).

Credenciales: lee HF_TOKEN del entorno (export HF_TOKEN=...) o de .env
(HF_TOKEN=...). Sin token, el script falla con código 3 informando la causa.

── USO ──────────────────────────────────────────────────────────────────────────
    python3 execution/publicar_hf.py <dataset>              # datasets/paquetes/<dataset>
    python3 execution/publicar_hf.py <dataset> --repo mi-org/ds-electronica
    python3 execution/publicar_hf.py <dataset> --dry-run     # simula sin subir

Ejemplos de --repo:
    --repo mi-usuario/gideal-rag-v1
    --repo gideal/eda-imagen-circuito   (si gideal es una org con permiso)

Códigos de salida:
    0 → publicado
    3 → sin HF_TOKEN configurado
    4 → dataset inexistente o sin archivos
    5 → error de red/API del Hub
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
PAQUETES  = WORKSPACE / "datasets" / "paquetes"
ENV_FILE  = WORKSPACE / ".env"


def _cargar_env() -> None:
    """Carga HF_TOKEN desde .env si existe (no sobrescribe variables ya definidas)."""
    if not ENV_FILE.exists():
        return
    try:
        for linea in ENV_FILE.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, _, valor = linea.partition("=")
            clave = clave.strip()
            valor = valor.strip().strip('"').strip("'")
            if clave and not os.environ.get(clave):
                os.environ[clave] = valor
    except OSError:
        pass


def _read_manifest() -> dict:
    path = PAQUETES / "manifest.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def publicar(
    dataset: str,
    repo_id: str,
    private: bool,
    dry_run: bool,
) -> dict:
    """Publica datasets/paquetes/<dataset> en Hugging Face Hub."""
    _cargar_env()

    dir_paq = PAQUETES / dataset
    if not dir_paq.exists():
        return {"status": "not_found", "exit_code": 4,
                "message": f"No existe el paquete datasets/paquetes/{dataset}."}
    archivos = [f for f in dir_paq.iterdir() if f.is_file()]
    if not archivos:
        return {"status": "not_found", "exit_code": 4,
                "message": f"El paquete {dataset} no contiene archivos."}

    manifest = _read_manifest()
    info = manifest.get("paquetes", {}).get(dataset, {})
    licencia = info.get("licencia", "desconocida")

    if dry_run:
        return {
            "status": "ok", "exit_code": 0, "dry_run": True,
            "repo_id": repo_id, "private": private,
            "archivos": sorted(p.name for p in archivos),
            "licencia": licencia,
            "registros": info.get("registros"),
        }

    token = os.environ.get("HF_TOKEN")
    if not token:
        return {"status": "no_token", "exit_code": 3,
                "message": "HF_TOKEN no configurado. Exporta HF_TOKEN o añádelo a .env."}

    from huggingface_hub import HfApi, create_repo, upload_folder

    api = HfApi(token=token)

    # 1. Crear/verificar el repositorio (no falla si ya existe)
    try:
        create_repo(repo_id, repo_type="dataset", private=private,
                    exist_ok=True, token=token)
    except Exception as e:
        return {"status": "error", "exit_code": 5,
                "message": f"No se pudo crear el repositorio: {e}"}

    # 2. Subir el contenido del paquete
    try:
        upload_folder(
            repo_id=repo_id,
            repo_type="dataset",
            folder_path=str(dir_paq),
            commit_message=f"Publicación de dataset {dataset} ({licencia})",
            token=token,
        )
    except Exception as e:
        return {"status": "error", "exit_code": 5,
                "message": f"Error al subir al Hub: {e}"}

    return {
        "status": "ok", "exit_code": 0,
        "repo_id": repo_id,
        "private": private,
        "archivos": sorted(p.name for p in archivos),
        "licencia": licencia,
        "url": f"https://huggingface.co/datasets/{repo_id}",
    }


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publica un dataset empaquetado en Hugging Face Hub.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("dataset", help="Nombre del paquete en datasets/paquetes/.")
    parser.add_argument("--repo", dest="repo_id", default=None,
                        help="repo_id del Hub (ej. gideal/gideal-rag-v1). "
                             "Por defecto: <usuario>/gideal-<dataset>.")
    parser.add_argument("--private", action="store_true",
                        help="Crea el repositorio como privado (default: público).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula la publicación sin conectarse al Hub.")
    args = parser.parse_args()

    repo_id = args.repo_id
    if not repo_id:
        # derivar: usar el usuario del token si es posible
        from huggingface_hub import HfApi
        _cargar_env()
        token = os.environ.get("HF_TOKEN")
        user = ""
        if token and not args.dry_run:
            try:
                user = HfApi(token=token).whoami()["name"]
            except Exception:
                user = ""
        repo_id = (user + "/" if user else "") + f"gideal-{args.dataset}"

    result = publicar(
        dataset=args.dataset,
        repo_id=repo_id,
        private=args.private,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result.get("exit_code", 0)


if __name__ == "__main__":
    sys.exit(main())