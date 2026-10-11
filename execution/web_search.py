"""Buscador web determinista (Capa 3) para research_topic.

Busca en DuckDuckGo (HTML y Lite) SIN API key, usando curl_cffi para
suplantar la huella TLS de un navegador: `requests` plano recibe respuestas
bloqueo/anomalía de DDG (202/decoy) incluso con headers realistas. Se rota
la huella entre intentos (ver .agent/python.md #18, escalación curl_cffi).

Entradas: CLI. Salidas: JSON por stdout. Códigos: 0 ok · 1 sin resultados ·
2 error de búsqueda (acceso bloqueado / red rota).

Retry budget: máx 3 intentos de transporte TOTALES, rotando motor
(html -> lite) y huella (chrome124 -> firefox133 -> safari18). El fallback de
motor no es un reintento del mismo intento; es la siguiente estrategia de la
cadena. Si los 3 se agotan sin parsear, se reporta y se sube al orquestador.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from typing import Any

from bs4 import BeautifulSoup
from curl_cffi import requests as creq

BUDGET_ATTEMPTS = 3
USER_AGENTS = ["chrome124", "firefox133", "safari18"]
ENGINE_CHAIN = ["html", "lite"]
DDG_BASE = "https://html.duckduckgo.com/html/"
DDG_LITE = "https://lite.duckduckgo.com/lite/"

_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.5",
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
}


def _clean_redirect(href: str) -> str:
    """Extrae la URL real de un redirect `//duckduckgo.com/l/?uddg=<encoded>`."""
    if not href:
        return ""
    m = re.search(r"uddg=([^&]+)", href)
    if m:
        return urllib.parse.unquote(m.group(1))
    if href.startswith("//"):
        return "https:" + href
    return href


def _parse_html(body: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(body, "html.parser")
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for block in soup.select("div.result"):
        a = block.select_one("h2.result__title a.result__a") or block.select_one("a.result__a")
        if not a:
            continue
        url = _clean_redirect(a.get("href", ""))
        if not url or url in seen:
            continue
        sn = block.select_one("a.result__snippet") or block.select_one("div.result__snippet")
        seen.add(url)
        out.append({
            "title": a.get_text(" ", strip=True),
            "url": url,
            "snippet": sn.get_text(" ", strip=True) if sn else "",
        })
    return out


def _parse_lite(body: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(body, "html.parser")
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    links = soup.select("td.result-link a[rel=nofollow]")
    if not links:
        links = soup.select("a[href^='//duckduckgo.com/l/']")
    snippets = [td.get_text(" ", strip=True)
                for td in soup.select("td.result-snippet")]
    for i, a in enumerate(links):
        url = _clean_redirect(a.get("href", ""))
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({
            "title": a.get_text(" ", strip=True),
            "url": url,
            "snippet": snippets[i] if i < len(snippets) else "",
        })
    return out


_PARSERS = {"html": _parse_html, "lite": _parse_lite}


def _fetch(query: str, engine: str, impersonate: str) -> str:
    url = DDG_LITE if engine == "lite" else DDG_BASE
    params = {"q": query, "l": "es-es", "kl": "es-es"}
    resp = creq.get(url, params=params, headers=_HEADERS,
                    impersonate=impersonate, timeout=25)
    resp.raise_for_status()
    return resp.text


def search(query: str, max_results: int) -> tuple[str, list[dict[str, str]], list[str]]:
    """Devuelve (motor, resultados, errores). Determinista dentro del budget."""
    errors: list[str] = []
    for attempt in range(BUDGET_ATTEMPTS):
        engine = ENGINE_CHAIN[attempt % len(ENGINE_CHAIN)]
        ua = USER_AGENTS[attempt % len(USER_AGENTS)]
        try:
            body = _fetch(query, engine, ua)
        except Exception as exc:  # red, HTTP 5xx/4xx, timeout...
            errors.append(f"{engine}({ua}): {exc.__class__.__name__}: {exc}")
            continue
        results = _PARSERS[engine](body)
        if results:
            return engine, results[:max_results], errors
        errors.append(f"{engine}({ua}): 200 sin resultados parseables")
    return "ninguno", [], errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Buscador web determinista (DDG sin API key)")
    ap.add_argument("--query", required=True, help="Consulta de búsqueda")
    ap.add_argument("--max-results", type=int, default=8, help="Máx resultados (default 8)")
    args = ap.parse_args(argv)

    engine, results, errors = search(args.query, args.max_results)

    payload: dict[str, Any] = {
        "query": args.query,
        "motor": engine,
        "results": [{"rank": i + 1, **r} for i, r in enumerate(results)],
        "errores": errors,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if results:
        return 0
    if errors:
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())