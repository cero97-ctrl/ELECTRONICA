#!/usr/bin/env python3
"""
scrape_single_site.py — Extracción determinista de contenido de una URL (Layer 3: Execution)

Obtiene el HTML de una URL, lo convierte a Markdown (títulos, listas, código, enlaces)
y lo guarda en texto plano. Diseñado para ser importado por otros scripts
(ej. consultar_docs.py) o usado vía CLI por la directiva scrape_website.yaml.

Uso (CLI):
    python3 execution/scrape_single_site.py --url https://... --output_file out.md
    python3 execution/scrape_single_site.py --url https://... --output_file out.md --max-chars 50000

Salida (stdout, JSON):
    { "status": "ok", "url_final", "title", "chars", "max_chars", "bytes_written", "truncated", ... }

Códigos de salida:
    0 — Éxito
    1 — Error (URL inválida/inalcanzable)
    2 — Acceso denegado (HTTP 403) persistente
    3 — Contenido insuficiente o no procesable (SPA)
"""

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

# ── Configuración ──────────────────────────────────────────────────────────────
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
ALT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
ALT_USER_AGENT_2 = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0"
)
TIMEOUT = 25
MIN_CONTENT_CHARS = 200

# Política de reintento (retry budget del framework: máx 3 intentos)
RETRY_ATTEMPTS = 3
BACKOFF_BASE = 2.0
RETRY_STATUSES = {403, 429, 500, 502, 503, 504}


def _browser_headers(user_agent: str) -> dict:
    """Encabezados que imitan una navegación directa real desde un navegador."""
    accept_encoding = "gzip, deflate"
    for mod in ("brotli", "brotlicffi"):
        try:
            __import__(mod)
            accept_encoding += ", br"
            break
        except ImportError:
            continue
    return {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.6,en;q=0.4",
        "Accept-Encoding": accept_encoding,
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }


def _sleep_backoff(attempt: int, max_jitter: float = 1.0) -> None:
    """Espera exponencial con jitter antes del siguiente reintento."""
    time.sleep(BACKOFF_BASE ** attempt + random.uniform(0, max_jitter))


def fetch_html(url: str, user_agent: str = DEFAULT_USER_AGENT, timeout: int = TIMEOUT,
               session: Optional[requests.Session] = None) -> requests.Response:
    """Descarga el HTML de la URL siguiendo redirecciones.

    Reintenta hasta RETRY_ATTEMPTS veces ante 403/429/5xx o fallos de red,
    rotando el user-agent y aplicando backoff exponencial con jitter.
    Usa requests.Session para conservar cookies entre redirecciones.
    """
    agents = [user_agent, ALT_USER_AGENT, ALT_USER_AGENT_2]
    sess = session or requests.Session()
    last_exc: Optional[Exception] = None
    last_403: Optional[requests.Response] = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            resp = sess.get(
                url,
                headers=_browser_headers(agents[attempt % len(agents)]),
                timeout=timeout,
                allow_redirects=True,
            )
        except requests.exceptions.RequestException as e:
            last_exc = e
            if attempt < RETRY_ATTEMPTS - 1:
                _sleep_backoff(attempt)
            continue
        if resp.status_code == 403:
            last_403 = resp
        if resp.status_code in RETRY_STATUSES:
            last_exc = requests.exceptions.HTTPError(
                f"HTTP {resp.status_code}", response=resp
            )
            if attempt < RETRY_ATTEMPTS - 1:
                _sleep_backoff(attempt)
            continue
        resp.raise_for_status()
        return resp
    if last_403 is not None:
        raise requests.exceptions.HTTPError("HTTP 403", response=last_403)
    assert last_exc is not None
    raise last_exc


def _extract_main_container(soup: BeautifulSoup) -> BeautifulSoup:
    """Selecciona el contenedor principal de la página (main/article/body)."""
    for sel in ("main", "article", "#content", ".main-content", "[role='main']"):
        node = soup.select_one(sel)
        if node is not None:
            for tag in node.find_all(["nav", "footer", "aside", "script", "style"]):
                tag.decompose()
            return node
    for tag in soup.find_all(["nav", "footer", "aside", "script", "style"]):
        tag.decompose()
    return soup.body if soup.body else soup


def _inline_text(node) -> str:
    """Convierte un nodo (o su contenido) a texto Markdown inline."""
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""

    name = node.name
    if name in {"script", "style", "noscript"}:
        return ""

    inner = "".join(_inline_text(child) for child in node.children)

    if name == "br":
        return "\n"
    if name in {"strong", "b"}:
        return f"**{inner}**"
    if name in {"em", "i", "q"}:
        return f"*{inner}*"
    if name in {"code", "tt"}:
        return f"`{inner}`"
    if name == "a":
        href = node.get("href", "")
        return f"[{inner}]({href})" if inner.strip() else inner
    return inner


# Contenedores que se recorren pero no se emiten como bloque.
_CONTAINER_TAGS = {"div", "section", "article", "main", "body", "span", "header"}
# Bloques compuestos: se emiten completos y no se recorren sus hijos.
_COMPOSITE_BLOCK_TAGS = {"ul", "ol", "table", "blockquote", "pre"}
# Bloques hoja: se emiten como línea individual.
_LEAF_BLOCK_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "hr", "li", "tr"}


def _iter_blocks(node) -> list[tuple[str, str]]:
    """
    Recorre recursivamente el contenedor emitiendo bloques-hoja markdown.

    Retorna lista de (kind, text) donde kind ∈ {"heading", "code", "list",
    "quote", "raw", "hr"}.
    """
    out: list[tuple[str, str]] = []

    for child in node.children:
        if isinstance(child, NavigableString):
            continue
        if not isinstance(child, Tag):
            continue
        name = child.name
        if name in {"script", "style", "noscript", "nav", "footer", "aside"}:
            continue

        if name in _CONTAINER_TAGS:
            out.extend(_iter_blocks(child))

        elif name in _COMPOSITE_BLOCK_TAGS:
            if name == "pre":
                out.append(("code", child.get_text().strip()))
            elif name == "blockquote":
                quotes = [" ".join(child.get_text().split())]
                out.append(("quote", "\n".join(quotes)))
            elif name == "table":
                rows = [" | ".join(" ".join(c.get_text().split()) for c in tr.find_all(["th", "td"]))
                        for tr in child.find_all("tr")]
                out.append(("raw", "\n".join(rows)))
            else:
                items = [it.get_text(" ", strip=True) for it in child.find_all("li")]
                out.append(("list", "\n- " + "\n- ".join(items)))

        elif name in _LEAF_BLOCK_TAGS:
            raw = _inline_text(child).strip()
            if not raw:
                continue
            if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                out.append(("heading", raw))
            elif name == "hr":
                out.append(("hr", ""))
            else:
                out.append(("raw", raw))

    return out


def html_to_markdown(html: str, max_chars: Optional[int] = None) -> tuple[str, str]:
    """
    Convierte contenido HTML a Markdown limpio.

    Retorna (markdown, title). El Markdown puede truncarse con max_chars.
    """
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    container = _extract_main_container(soup)
    lines: list[str] = []
    for kind, text in _iter_blocks(container):
        if kind == "heading":
            lines.append(f"\n# {text}")
        elif kind == "code":
            lines.append(f"\n```\n{text}\n```\n")
        elif kind == "quote":
            lines.append(f"> {text.replace(chr(10), ' ')}")
        elif kind == "list":
            lines.append(text.replace("\n\n", "\n"))
        elif kind == "hr":
            lines.append("\n---\n")
        else:
            lines.append(text.replace("\n", " "))

    markdown = "\n".join(lines)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()

    if max_chars and len(markdown) > max_chars:
        markdown = markdown[:max_chars].rsplit("\n", 1)[0] + "\n…(truncado)"

    return markdown, title


def main() -> int:
    parser = argparse.ArgumentParser(description="Extrae contenido de una URL.")
    parser.add_argument("--url", required=True, help="URL de la página web.")
    parser.add_argument("--output_file", required=True, help="Ruta del archivo de salida.")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="User-Agent HTTP.")
    parser.add_argument("--max-chars", type=int, default=None, help="Truncar salida a N caracteres.")
    args = parser.parse_args()

    url_final, title, markdown = args.url, "", ""
    try:
        resp = fetch_html(args.url, user_agent=args.user_agent)
        url_final = resp.url or args.url
        markdown, title = html_to_markdown(resp.text, max_chars=args.max_chars)
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 403:
            out = {"status": "error", "code": 2, "url": args.url,
                   "message": "Acceso denegado (HTTP 403) persistente por protección anti-bot."}
            print(json.dumps(out, ensure_ascii=False))
            return 2
        else:
            out = {"status": "error", "code": 1, "url": args.url,
                   "message": f"Error HTTP al descargar la URL: {e}"}
            print(json.dumps(out, ensure_ascii=False))
            return 1
    except requests.exceptions.RequestException as e:
        out = {"status": "error", "code": 1, "url": args.url,
               "message": f"URL inválida o inalcanzable: {e}"}
        print(json.dumps(out, ensure_ascii=False))
        return 1
    except Exception as e:
        out = {"status": "error", "code": 3, "url": args.url,
               "message": f"Error al procesar el contenido: {e}"}
        print(json.dumps(out, ensure_ascii=False))
        return 3

    truncated = bool(args.max_chars and len(markdown) > args.max_chars)
    if not truncated and args.max_chars and len(markdown) >= args.max_chars:
        truncated = True

    if len(markdown) < MIN_CONTENT_CHARS:
        out = {"status": "error", "code": 3, "url": args.url,
               "message": "Contenido insuficiente: la página parece requerir JavaScript (SPA) o bloquear a bots.",
               "chars": len(markdown), "title": title}
        print(json.dumps(out, ensure_ascii=False))
        return 3

    try:
        Path(args.output_file).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_file).write_text(markdown, encoding="utf-8")
    except Exception as e:
        out = {"status": "error", "code": 1, "url": args.url,
               "message": f"No se pudo escribir el archivo de salida: {e}"}
        print(json.dumps(out, ensure_ascii=False))
        return 1

    out = {
        "status": "ok",
        "url": args.url,
        "url_final": url_final,
        "title": title,
        "output_file": str(Path(args.output_file).resolve()),
        "chars": len(markdown),
        "max_chars": args.max_chars,
        "bytes_written": Path(args.output_file).stat().st_size,
        "truncated": truncated,
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())