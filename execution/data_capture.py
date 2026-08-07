#!/usr/bin/env python3
"""
data_capture.py — Captura de datos para entrenamiento de LLMs (Layer 3: Execution)

Genera datasets JSONL de alto valor a partir de los flujos de trabajo existentes,
para su posterior curación y comercialización en Web3.

El módulo es 100% pasivo: nunca rompe el flujo que lo invoca (todo va en try/except).
Los datos se escriben en `datasets/` en el workspace, excluidos de git.

── SCHEMAS JSONL ────────────────────────────────────────────────────────────

1) datasets/rag_conversaciones.jsonl   (format ShareGPT)
   {
     "id": "rag-<timestamp>-<hash8>",
     "messages": [
       {"role": "system",    "content": "..."},
       {"role": "user",      "content": "..."},
       {"role": "assistant", "content": "..."}
     ],
     "metadata": {
       "schema_version": "1.0",
       "source": "GIDEAL_RAG_v1",
       "dataset": "rag_conversaciones",
       "domain": "electronica",
       "model": "llama-3.1-8b-instant",
       "retrieved_context": [{"source": "ruta/doc.tex", "content_preview": "..."}],
       "quality_score": 1.0,
       "timestamp": "2026-08-06T..."
     }
   }

2) datasets/eda_imagen_circuito.jsonl  (format instrucción multimodal imagen→netlist)
   {
     "id": "eda-<timestamp>-<hash8>",
     "images": ["docs/IMAGENES/circuito.png"],
     "instruction": "Convierte esta imagen de circuito en un netlist estructurado JSON...",
     "output": {
       "components": [{"id": "R1", "type": "R", "value": "10k", "x": 100, "y": 100}],
       "connections": [{"net_name": "Net_1", "pins": ["R1-1", "C1-1"]}]
     },
     "metadata": {
       "schema_version": "1.0",
       "source": "GIDEAL_EDA_v1",
       "dataset": "eda_imagen_circuito",
       "api_backend": "gemini",
       "model": "gemini-2.5-flash",
       "tokens_usados": {"total": 4510},
       "quality_score": 1.0,
       "timestamp": "2026-08-06T..."
     }
   }

── USO ────────────────────────────────────────────────────────────────────────

Desde un orquestador:
    from execution.data_capture import data_capture
    data_capture.capture_rag(user_query=..., assistant_response=..., retrieved_context=...)
    data_capture.capture_eda(image_paths=[...], instruction=..., output=netlist_json)

CLI (auto-test):
    python3 execution/data_capture.py --self-test

Desactivar captura en tiempo de ejecución:
    export DATA_CAPTURE_DISABLED=1
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Configuración ──────────────────────────────────────────────────────────────
WORKSPACE   = Path(__file__).resolve().parents[1]
DATASETS    = WORKSPACE / "datasets"
INDEX_FILE  = DATASETS / ".capture_index.json"

SCHEMA_VERSION = "1.0"
SOURCE_RAG     = "GIDEAL_RAG_v1"
SOURCE_EDA     = "GIDEAL_EDA_v1"

# Límite de caracteres para campos de texto libre (protección + trazabilidad)
MAX_TEXT = 20_000


# ── Sanitización (PII básica) ──────────────────────────────────────────────────

_PII_PATTERNS = [
    re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),  # emails
    re.compile(r"\bV-?\s?\d{6,9}\b", re.IGNORECASE),                      # cédula venezolana
    re.compile(r"\b\d{8}\b"),                                             # id/ci genérico 8 dígitos
    re.compile(r"\b(\+?\d{1,3}[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b"),  # teléfono
]


def sanitize_text(text: str) -> str:
    """Elimina PII (emails, cédulas, teléfonos) y normaliza el texto."""
    if not text:
        return ""
    text = str(text)[:MAX_TEXT]
    for pattern in _PII_PATTERNS:
        text = pattern.sub("[REDACTADO]", text)
    return text.strip()


def _sanitize_value(value):
    """Aplica sanitización recursiva a dicts/listas/strings."""
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(v) for v in value]
    return value


# ── Deduplicación (por hash del contenido canónico) ─────────────────────────────

def _canonical_hash(record: dict) -> str:
    """Hash del contenido sin id/timestamp para detectar duplicados."""
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


class DataCapture:
    """Captura pasiva de muestras de entrenamiento a datasets JSONL versionados."""

    def __init__(self, datasets_dir: Path | None = None, enabled: bool | None = None):
        self.datasets_dir = Path(datasets_dir) if datasets_dir else DATASETS
        self.enabled = enabled if enabled is not None else (
            os.environ.get("DATA_CAPTURE_DISABLED", "0") != "1"
        )
        self._index: dict[str, list[str]] = {}
        if self.enabled:
            self._load_index()

    # ── gestión del índice ────────────────────────────────────────────────────
    def _load_index(self) -> None:
        try:
            if INDEX_FILE.exists():
                self._index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            self._index = {}

    def _save_index(self) -> None:
        try:
            self.datasets_dir.mkdir(parents=True, exist_ok=True)
            INDEX_FILE.write_text(
                json.dumps(self._index, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _is_duplicate(self, dataset: str, h: str) -> bool:
        return h in self._index.get(dataset, [])

    def _mark_seen(self, dataset: str, h: str) -> None:
        self._index.setdefault(dataset, []).append(h)
        if len(self._index[dataset]) > 100_000:  # acotar memoria
            self._index[dataset] = self._index[dataset][-50_000:]

    # ── escritura ────────────────────────────────────────────────────────────
    def _append(self, dataset: str, record: dict) -> bool:
        if not self.enabled:
            return False
        record = _sanitize_value(record)
        h = _canonical_hash(record)
        if self._is_duplicate(dataset, h):
            return False

        self.datasets_dir.mkdir(parents=True, exist_ok=True)
        path = self.datasets_dir / f"{dataset}.jsonl"
        line = json.dumps(record, ensure_ascii=False)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

        self._mark_seen(dataset, h)
        self._save_index()
        return True

    @staticmethod
    def _make_id(prefix: str, h: str) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        return f"{prefix}-{ts}-{h[:8]}"

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── Dataset 1: conversaciones RAG (ShareGPT) ─────────────────────────────
    def capture_rag(
        self,
        user_query: str,
        assistant_response: str,
        system_prompt: str | None = None,
        retrieved_context: list | None = None,
        domain: str = "electronica",
        model: str | None = None,
        quality_score: float | None = None,
        extra: dict | None = None,
    ) -> bool:
        """Captura un turno de conversación RAG en formato ShareGPT."""
        if not self.enabled:
            return False

        messages = [{"role": "user", "content": sanitize_text(user_query)}]
        if system_prompt:
            messages.insert(0, {"role": "system", "content": sanitize_text(system_prompt)})
        messages.append({"role": "assistant", "content": sanitize_text(assistant_response)})

        ctx = []
        for doc in retrieved_context or []:
            source = getattr(doc, "metadata", {}).get("source") if hasattr(doc, "metadata") else None
            content = getattr(doc, "page_content", None)
            ctx.append({
                "source": sanitize_text(str(source)) if source else "",
                "content_preview": sanitize_text(str(content))[:500],
            })

        record = {
            "id": "rag-" + self._now_iso(),
            "messages": messages,
            "metadata": {
                "schema_version": SCHEMA_VERSION,
                "source": SOURCE_RAG,
                "dataset": "rag_conversaciones",
                "domain": sanitize_text(domain),
                "model": model,
                "retrieved_context": ctx,
                "quality_score": quality_score if quality_score is not None else 1.0,
                "timestamp": self._now_iso(),
            },
        }
        if extra:
            record["metadata"].update(_sanitize_value(extra))
        return self._append("rag_conversaciones", record)

    # ── Dataset 2: EDA imagen → circuito (netlist JSON) ──────────────────────
    def capture_eda(
        self,
        image_paths: list[str],
        instruction: str,
        output: dict | list | str,
        model: str | None = None,
        api_backend: str | None = None,
        tokens_usados: dict | None = None,
        quality_score: float | None = None,
        extra: dict | None = None,
    ) -> bool:
        """Captura un par imagen→netlist/circuito en formato instrucción multimodal."""
        if not self.enabled:
            return False

        record = {
            "id": "eda-" + self._now_iso(),
            "images": [str(p) for p in image_paths],
            "instruction": sanitize_text(instruction),
            "output": output,
            "metadata": {
                "schema_version": SCHEMA_VERSION,
                "source": SOURCE_EDA,
                "dataset": "eda_imagen_circuito",
                "api_backend": api_backend,
                "model": model,
                "tokens_usados": tokens_usados or {},
                "quality_score": quality_score if quality_score is not None else 1.0,
                "timestamp": self._now_iso(),
            },
        }
        if extra:
            record["metadata"].update(_sanitize_value(extra))
        return self._append("eda_imagen_circuito", record)

    # ── Dataset 3: análisis multimodal de imágenes (descripciones) ──────────────
    def capture_imagen(
        self,
        image_paths: list[str],
        prompt: str,
        analisis: dict | list | str,
        model: str | None = None,
        api_backend: str | None = None,
        tokens_usados: dict | None = None,
        quality_score: float | None = None,
        extra: dict | None = None,
    ) -> bool:
        """Captura un par imagen→análisis descriptivo en formato instrucción multimodal."""
        if not self.enabled:
            return False

        record = {
            "id": "img-" + self._now_iso(),
            "images": [str(p) for p in image_paths],
            "instruction": sanitize_text(prompt),
            "output": analisis,
            "metadata": {
                "schema_version": SCHEMA_VERSION,
                "source": "GIDEAL_VISION_v1",
                "dataset": "analisis_imagenes",
                "api_backend": api_backend,
                "model": model,
                "tokens_usados": tokens_usados or {},
                "quality_score": quality_score if quality_score is not None else 1.0,
                "timestamp": self._now_iso(),
            },
        }
        if extra:
            record["metadata"].update(_sanitize_value(extra))
        return self._append("analisis_imagenes", record)


# ── Instancia global para integración simple en orquestadores ─────────────────
data_capture = DataCapture()


# ── CLI (auto-test) ────────────────────────────────────────────────────────────

def _self_test() -> int:
    """Escribe una muestra de ejemplo de cada dataset y reporta el estado."""
    print(f"Captura {'HABILITADA' if data_capture.enabled else 'DESHABILITADA'}")
    print(f"Directorio de datasets: {DATASETS}")

    ok_rag = data_capture.capture_rag(
        user_query="Diseña una fuente conmutada de 12V 2A usando el LM2576.",
        assistant_response="Aquí está el diseño completo con esquemático en circuitikz, netlist y BOM.",
        system_prompt="Eres un experto en electrónica analógica.",
        domain="electronica_analogica",
        model="llama-3.1-8b-instant",
        extra={"test": True},
    )
    ok_eda = data_capture.capture_eda(
        image_paths=["docs/IMAGENES/kee.jpeg"],
        instruction="Convierte esta imagen de circuito en un netlist estructurado JSON.",
        output={
            "components": [{"id": "R1", "type": "R", "value": "10k"}],
            "connections": [{"net_name": "Net_1", "pins": ["R1-1"]}],
        },
        api_backend="gemini",
        model="gemini-2.5-flash",
        tokens_usados={"total": 100},
        extra={"test": True},
    )

    print(f"  RAG (ShareGPT)  -> {'escrita' if ok_rag else 'omitida/deshabilitada'}")
    print(f"  EDA (imagen)    -> {'escrita' if ok_eda else 'omitida/deshabilitada'}")

    for name in ("rag_conversaciones.jsonl", "eda_imagen_circuito.jsonl"):
        path = DATASETS / name
        if path.exists():
            n = sum(1 for _ in path.open(encoding="utf-8"))
            print(f"  {name}: {n} registros")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print(__doc__)
