"""Sintetizador de resultados de búsqueda (Capa 3) para research_topic.

Lee el JSON de execution/web_search.py, rasca las N primeras fuentes vía
execution/scrape_single_site.py y produce el entregable: si hay LLM
disponible, un informe estructurado en markdown; si no, el corpus en bruto
(edge case de la directiva). El modelo lo decide el orquestador por el
enrutador determinista; este script nunca elige tier.

Salidas: JSON por stdout con la ruta del entregable. Códigos: 0 ok · 1 sin
fuentes que procesar · 2 búsqueda ilegible · 3 uso incorrecto (argparse).
El fallo del LLM NO es código de error: degrada a modo bruto y se avisa.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

import sys as _sys
_exec_path = str(Path(__file__).resolve().parent)
if _exec_path not in _sys.path:
    _sys.path.insert(0, _exec_path)
from scrape_single_site import fetch_html, html_to_markdown  # noqa: E402
from llm_client import openrouter_chat, load_api_key  # noqa: E402

MODELO_DEFAULT = "flash"
MAX_PAGES_DEFAULT = 4
MAX_CHARS_DEFAULT = 6000


def slugify(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text)
    ascii_like = "".join(c for c in norm if not unicodedata.combining(c))
    words = re.findall(r"[A-Za-z0-9]+", ascii_like.lower())
    return "-".join(words) if words else "investigacion"


def _fences_off(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[A-Za-z]*\s*", "", text)
    if text.endswith("```"):
        text = text[:-3].rstrip()
    return text.strip()


def cargar_busqueda(ruta: Path) -> dict:
    try:
        data = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def raspar_fuente(url: str, max_chars: int) -> tuple[str, str]:
    """Devuelve (estado, contenido_markdown). 'ok' o motivo de fallo."""
    try:
        resp = fetch_html(url)
    except Exception as exc:
        return f"fallo: {exc.__class__.__name__}: {exc}", ""
    try:
        md, _title = html_to_markdown(resp.text, max_chars=max_chars)
    except Exception as exc:
        return f"fallo_md: {exc.__class__.__name__}: {exc}", ""
    return "ok", md


def construir_corpus(busqueda: dict, max_pages: int, max_chars: int):
    fuentes: list[dict] = []
    trozos: list[str] = []
    for r in busqueda.get("results", [])[:max_pages]:
        estado, md = raspar_fuente(r["url"], max_chars)
        fuentes.append({
            "rank": r.get("rank"),
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("snippet", ""),
            "estado": estado,
            "chars": len(md),
        })
        if estado == "ok":
            trozos.append(f"## {r.get('title', '')}\nURL: {r.get('url', '')}\n\n{md}")
    return fuentes, "\n\n".join(trozos)


def sintetizar_llm(tema: str, corpus: str, modelo: str) -> str:
    api_key = load_api_key()
    reasoning = None if "flash" in modelo else {"enabled": False}
    messages = [
        {"role": "system", "content": (
            "Eres un investigador que redacta informes técnicos en español, "
            "precisos y con estructura markdown. Usa SOLO la información de "
            "las fuentes proporcionadas. Produce markdown (no JSON): un "
            "título, un resumen de 2-3 frases, secciones temáticas con "
            "encabezados ##/###, y una sección final 'Fuentes' con la lista "
            "de URLs citadas.")},
        {"role": "user", "content": (
            f"TEMA: {tema}\n\nFUENTES (búsqueda web + texto extraído):\n{corpus}")},
    ]
    contenido, _tokens = openrouter_chat(
        messages, model=modelo, api_key=api_key,
        temperature=0.3, max_tokens=2048, title="research_topic",
        reasoning=reasoning,
    )
    if not contenido or not contenido.strip():
        raise RuntimeError("el modelo devolvió contenido vacío")
    return _fences_off(contenido)


def escribir_deliverable(carpeta: Path, slug: str, tema: str, modo: str,
                         cuerpo: str, fuentes: list[dict], fallo_llm: str = "") -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{slug}.md"
    lineas = [
        f"# {tema}",
        "",
        "> Investigación generada por `research_topic` (web_search + síntesis).",
        f"- Modo: **{modo}**",
        "- Fuentes procesadas:",
    ]
    for f in fuentes:
        estado = f["estado"] if f["estado"] != "ok" else f"{f['chars']} chars"
        lineas.append(f"  - [{f['title']}]({f['url']}) — {estado}")
    if fallo_llm:
        lineas.append(f"\n> Aviso: el LLM falló (`{fallo_llm}`); el informe es el corpus en bruto.")
    lineas += ["", "---", "", cuerpo, ""]
    ruta.write_text("\n".join(lineas), encoding="utf-8")
    return ruta


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sintetiza resultados de web_search en un informe markdown")
    ap.add_argument("--search", required=True, help="JSON de execution/web_search.py")
    ap.add_argument("--tema", required=True, help="Tema investigado")
    ap.add_argument("--output", default="docs/INVESTIGACIONES", help="Carpeta del entregable")
    ap.add_argument("--modelo", default=MODELO_DEFAULT, help="Tier o ID de modelo OpenRouter")
    ap.add_argument("--max-pages", type=int, default=MAX_PAGES_DEFAULT, help="Páginas a raspar")
    ap.add_argument("--max-chars", type=int, default=MAX_CHARS_DEFAULT, help="Chars por página")
    ap.add_argument("--no-llm", action="store_true", help="Saltar la síntesis LLM (modo bruto)")
    args = ap.parse_args(argv)

    busqueda = cargar_busqueda(Path(args.search))
    if not busqueda or "results" not in busqueda:
        print(json.dumps({"status": "error", "code": 2,
                          "motivo": "JSON de búsqueda ilegible o vacío"},
                         ensure_ascii=False))
        return 2

    fuentes, corpus = construir_corpus(busqueda, args.max_pages, args.max_chars)
    ok = [f for f in fuentes if f["estado"] == "ok"]
    if not ok:
        print(json.dumps({"status": "error", "code": 1,
                          "motivo": "ninguna fuente se pudo raspar",
                          "fuentes": fuentes}, ensure_ascii=False, indent=2))
        return 1

    carpeta = Path(args.output)
    slug = slugify(args.tema)
    fallo_llm = ""
    if args.no_llm:
        modo = "bruto"
        cuerpo = corpus
    else:
        try:
            cuerpo = sintetizar_llm(args.tema, corpus, args.modelo)
            modo = "llm"
        except Exception as exc:
            modo = "bruto"
            fallo_llm = f"{exc.__class__.__name__}: {exc}"
            cuerpo = corpus

    ruta = escribir_deliverable(carpeta, slug, args.tema, modo, cuerpo, fuentes, fallo_llm)
    print(json.dumps({
        "status": "ok",
        "code": 0,
        "modo": modo,
        "entregable": str(ruta.resolve()),
        "fuentes_ok": len(ok),
        "fuentes_fallo": len(fuentes) - len(ok),
        "corpus_chars": len(corpus),
        "aviso_llm": fallo_llm or None,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())