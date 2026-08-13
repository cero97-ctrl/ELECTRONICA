#!/usr/bin/env python3
"""
consultar_docs.py — Consulta de documentación reciente de tecnologías (Layer 3: Execution)

Resuelve una tecnología (o una URL directa), obtiene su documentación oficial vigente,
la convierte a Markdown y la guarda en .tmp/docs_cache/. Las páginas de docs de la mayoría
de frameworks (Next.js, Supabase, Expo...) son prerenderizadas por el servidor, por lo que
el contenido principal es extraíble sin ejecutar JavaScript.

Uso (CLI):
    python3 execution/consultar_docs.py --tech nextjs
    python3 execution/consultar_docs.py --tech supabase --topic api
    python3 execution/consultar_docs.py --url https://nextjs.org/docs/app --output docs/nextjs.md
    python3 execution/consultar_docs.py --list

Salida (stdout, JSON):
    { "status": "ok", "tecnologia", "url", "url_final", "title", "archivo", "chars", "cached", ... }

Códigos de salida:
    0 — Éxito
    1 — Tecnología desconocida o argumentos inválidos
    2 — Error de red / HTTP / 403 (propagado del scraper)
    3 — Contenido insuficiente o no procesable (SPA)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.scrape_single_site import fetch_html, html_to_markdown

# ── Registro de documentación oficial por tecnología ─────────────────────────
# La URL apunta a la documentación "latest". Se puede ampliar libremente.
DOCS_REGISTRY = {
    "nextjs":    "https://nextjs.org/docs",
    "supabase":  "https://supabase.com/docs",
    "expo":      "https://docs.expo.dev",
    "react":     "https://react.dev/reference/react",
    "langchain": "https://python.langchain.com/docs",
    "openai":    "https://platform.openai.com/docs",
    "fastapi":   "https://fastapi.tiangolo.com",
    "flask":     "https://flask.palletsprojects.com/en/stable",
    "esp-idf":   "https://docs.espressif.com/projects/esp-idf/en/latest",
}

TMP_DIR     = PROJECT_ROOT / ".tmp" / "docs_cache"
CACHE_STALE_HOURS = 24
MIN_CONTENT_CHARS = 200


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_url(tecnologia: str, topic: Optional[str] = None) -> str:
    """Resuelve la URL base de la tecnología y le anexa el tema si se indica."""
    url = DOCS_REGISTRY[tecnologia].rstrip("/")
    if topic:
        url += "/" + topic.strip().strip("/")
    return url


def is_cache_fresh(path: Path, stale_hours: int = CACHE_STALE_HOURS) -> bool:
    """Determina si un archivo de caché es lo suficientemente reciente."""
    if not path.exists():
        return False
    age = datetime.now().timestamp() - path.stat().st_mtime
    return age < stale_hours * 3600


def main() -> int:
    parser = argparse.ArgumentParser(description="Consulta documentación reciente de una tecnología.")
    parser.add_argument("--tech", help="Tecnología a consultar (ver --list).")
    parser.add_argument("--topic", default=None, help="Sub-ruta/tema opcional dentro de la documentación.")
    parser.add_argument("--url", default=None, help="URL directa de documentación (alternativa a --tech).")
    parser.add_argument("--output", default=None, help="Ruta de salida del archivo Markdown.")
    parser.add_argument("--max-chars", type=int, default=200000, help="Truncar salida a N caracteres.")
    parser.add_argument("--fresh", action="store_true", help="Ignorar caché y volver a descargar.")
    parser.add_argument("--list", action="store_true", help="Listar tecnologías soportadas y salir.")
    args = parser.parse_args()

    if args.list:
        print(json.dumps({"status": "ok", "tecnologias": sorted(DOCS_REGISTRY)}, ensure_ascii=False))
        return 0

    if args.url and args.tech:
        out = {"status": "error", "code": 1, "message": "--tech y --url son mutuamente excluyentes."}
        print(json.dumps(out, ensure_ascii=False))
        return 1

    if args.tech and args.tech not in DOCS_REGISTRY:
        out = {"status": "error", "code": 1,
               "message": f"Tecnología '{args.tech}' no soportada.",
               "disponibles": sorted(DOCS_REGISTRY)}
        print(json.dumps(out, ensure_ascii=False))
        return 1

    if not args.tech and not args.url:
        out = {"status": "error", "code": 1, "message": "Debe indicarse --tech o --url."}
        print(json.dumps(out, ensure_ascii=False))
        return 1

    url = args.url if args.url else resolve_url(args.tech, args.topic)
    nombre_base = args.tech or "url"

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    output_file = Path(args.output) if args.output else TMP_DIR / f"{nombre_base}.md"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if not args.fresh and is_cache_fresh(output_file):
        cached_text = output_file.read_text(encoding="utf-8")
        if len(cached_text) >= MIN_CONTENT_CHARS:
            out = {
                "status": "ok", "tecnologia": nombre_base, "url": url,
                "title": cached_text.splitlines()[0] if cached_text else "",
                "archivo": str(output_file.resolve()), "chars": len(cached_text),
                "cached": True, "cached_archivo": str(output_file.resolve()),
            }
            print(json.dumps(out, ensure_ascii=False))
            return 0

    try:
        resp = fetch_html(url)
        url_final = resp.url or url
        markdown, title = html_to_markdown(resp.text, max_chars=args.max_chars)
    except Exception as e:
        msg = str(e)
        code = 2
        if "403" in msg:
            msg = "Acceso denegado (HTTP 403) por protección anti-bot."
        out = {"status": "error", "code": code, "url": url, "message": msg}
        print(json.dumps(out, ensure_ascii=False))
        return code

    if len(markdown) < MIN_CONTENT_CHARS:
        out = {"status": "error", "code": 3, "url": url,
               "message": "Contenido insuficiente: la página parece requerir JavaScript (SPA) o bloquear a bots.",
               "chars": len(markdown), "title": title}
        print(json.dumps(out, ensure_ascii=False))
        return 3

    header = (
        f"# {title or nombre_base}\n\n"
        f"> Fuente: {url_final}  \n"
        f"> Fecha de consulta: {now_iso()}  \n"
        f"> Tecnología: {args.tech or 'URL directa'}\n\n---\n\n"
    )
    full = header + markdown
    if args.max_chars and len(full) > args.max_chars:
        full = full[:args.max_chars].rsplit("\n", 1)[0] + "\n…(truncado)"

    try:
        output_file.write_text(full, encoding="utf-8")
    except Exception as e:
        out = {"status": "error", "code": 1, "message": f"No se pudo escribir el archivo de salida: {e}"}
        print(json.dumps(out, ensure_ascii=False))
        return 1

    out = {
        "status": "ok",
        "tecnologia": nombre_base,
        "url": url,
        "url_final": url_final,
        "title": title,
        "archivo": str(output_file.resolve()),
        "chars": len(full),
        "max_chars": args.max_chars,
        "cached": False,
        "truncated": len(full) >= args.max_chars if args.max_chars else False,
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())