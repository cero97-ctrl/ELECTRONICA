#!/usr/bin/env python3
"""
ocr_pdf_escaneado.py — OCR determinista de un PDF escaneado (Layer 3: Execution).

Flujo asociado: directives/ocr_pdf_escaneado.yaml
Orquestador:    flujo_ocr_pdf.py

Cubre el hueco que deja `extraer_libro_pdf.py` (que devuelve código 2 cuando el
PDF no tiene texto selectable). Extrae las imágenes nativas del PDF, las reduce a
un ancho fijo y las transcribe con Gemini en lotes. La caché por página hace el
proceso reanudable: si se agota la cuota, se retoma sin repetir lo ya hecho.

Uso:
    python3 execution/ocr_pdf_escaneado.py \\
        --pdf practicas.pdf --salida .tmp/ocr_practicas \\
        [--paginas 1-56] [--lote 4] [--ancho 1400] \\
        [--modelo gemini-2.5-flash] [--forzar] [--json]

Salida (stdout, JSON):
    {
      "status": "ok",
      "pdf": "...", "paginas": 56, "paginas_ok": 56,
      "paginas_vacias": [], "paginas_ilegibles": [], "paginas_faltantes": [],
      "modelo": "...", "ancho": 1400, "lote": 4,
      "archivo": "...", "cache": "...", "peticiones": 14, "tokens": {...}
    }

Códigos de salida:
    0 — Todas las páginas pedidas transcritas
    1 — Argumentos inválidos o PDF inexistente/ilegible
    2 — El PDF tiene capa de texto (usar execution/extraer_libro_pdf.py)
    3 — Error del backend/SDK (red, API key, modelo)
    4 — Páginas incompletas tras el retry budget (máx 3 intentos)
    5 — Cuota agotada: se conserva la caché y se reanuda después
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

MAX_INTENTOS = 3
MIN_CHARS_PAGINA = 40
MIN_CHARS_POR_MARCA = 100
MIN_CHARS_POR_PAGINA_TEXTO = 100
MARCA_PAGINA = re.compile(r"@@@\s*PAGINA\s*:?\s*(\d+)\s*@@@", re.IGNORECASE)

INSTRUCCION = """Eres un transcriptor de documentos escaneados. Transcribe el texto de
cada página de forma LITERAL, sin resumir, sin interpretar y sin completar nada.

Reglas:
- Empieza cada página con la marca exacta @@@PAGINA: <número>@@@ en su propia línea.
- Ecuaciones: LaTeX entre $...$ en línea, o \\[...\\] si van destacadas.
- Tablas: tabla Markdown con los mismos encabezados y valores.
- Figuras y diagramas: escribe [FIGURA: descripción de una línea] donde aparezcan.
- Texto que no puedas leer: escribe [ILEGIBLE].
- Página en blanco: solo la marca y [PAGINA VACIA].
- No añadas comentarios, ni resúmenes, ni texto que no esté en la página."""


class _ArgParserExit1(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(json.dumps({"status": "error", "code": 1, "message": message}), file=sys.stderr)
        sys.exit(1)


def parse_paginas(spec: str | None, total: int) -> list[int]:
    """Convierte '1-56', '1,3,5-7' o None en una lista de páginas 1..total."""
    if not spec or spec.strip().lower() in ("todas", "all", "*"):
        return list(range(1, total + 1))
    paginas: set[int] = set()
    for trozo in spec.split(","):
        trozo = trozo.strip()
        if not trozo:
            continue
        if "-" in trozo:
            ini, _, fin = trozo.partition("-")
            try:
                a, b = int(ini), int(fin)
            except ValueError as exc:
                raise ValueError(f"rango de páginas inválido: {trozo!r}") from exc
            if a > b:
                a, b = b, a
            paginas.update(range(a, b + 1))
        else:
            try:
                paginas.add(int(trozo))
            except ValueError as exc:
                raise ValueError(f"página inválida: {trozo!r}") from exc
    fuera = sorted(p for p in paginas if p < 1 or p > total)
    if fuera:
        raise ValueError(f"páginas fuera del PDF ({total} páginas): {fuera[:5]}")
    return sorted(paginas)


def dividir_lotes(paginas: list[int], lote: int) -> list[list[int]]:
    """Parte la lista de páginas en lotes de tamaño fijo (el último puede ser menor)."""
    if lote < 1:
        raise ValueError("el lote debe ser >= 1")
    return [paginas[i:i + lote] for i in range(0, len(paginas), lote)]


def dividir_respuesta(texto: str, esperadas: list[int]) -> dict[int, str]:
    """Separa la respuesta del modelo por las marcas @@@PAGINA: n@@@."""
    resultado: dict[int, str] = {}
    marcas = list(MARCA_PAGINA.finditer(texto))
    if not marcas:
        if len(esperadas) == 1:
            return {esperadas[0]: texto.strip()}
        return {}
    for i, marca in enumerate(marcas):
        numero = int(marca.group(1))
        ini = marca.end()
        fin = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        if numero not in esperadas:
            continue
        resultado[numero] = texto[ini:fin].strip()
    return resultado


def validar_pagina(texto: str) -> tuple[bool, bool]:
    """Devuelve (ok, vacia). Una página demasiado corta o dominada por [ILEGIBLE] falla."""
    limpio = texto.strip()
    if not limpio or "[PAGINA VACIA]" in limpio.upper():
        return True, True
    if len(limpio) < MIN_CHARS_PAGINA:
        return False, False
    marcas = limpio.upper().count("[ILEGIBLE]")
    return marcas * MIN_CHARS_POR_MARCA <= len(limpio), False


def _cargar_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        load_dotenv(os.path.join(raiz, ".env"))
    except Exception:
        pass


def _sha_pdf(pdf: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with pdf.open("rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _info_pdf(pdf: Path) -> tuple[int, float]:
    import fitz

    doc = fitz.open(pdf)
    try:
        total = doc.page_count
        chars = sum(len(pagina.get_text() or "") for pagina in doc)
    finally:
        doc.close()
    return total, (chars / total if total else 0.0)


def extraer_imagen_pagina(pdf: Path, pagina: int, destino: Path) -> Path | None:
    """Extrae la imagen dominante de una página con pdfimages (JPEG nativo)."""
    destino.mkdir(parents=True, exist_ok=True)
    prefijo = destino / "img"
    for viejo in destino.glob("img-*"):
        viejo.unlink()
    proc = subprocess.run(
        ["pdfimages", "-j", "-f", str(pagina), "-l", str(pagina), str(pdf), str(prefijo)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"pdfimages falló en la página {pagina}: {proc.stderr[:300]}")
    imagenes = sorted(destino.glob("img-*"), key=lambda p: p.stat().st_size, reverse=True)
    return imagenes[0] if imagenes else None


def reducir_imagen(ruta: Path, ancho: int) -> bytes:
    from io import BytesIO

    from PIL import Image

    with Image.open(ruta) as img:
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        if img.width > ancho:
            alto = round(img.height * ancho / img.width)
            img = img.resize((ancho, alto), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=88, optimize=True)
        return buf.getvalue()


def _construir_config(genai_types, tokens_salida: int):
    kwargs = {
        "system_instruction": INSTRUCCION,
        "temperature": 0.0,
        "max_output_tokens": tokens_salida,
    }
    try:
        kwargs["thinking_config"] = genai_types.ThinkingConfig(
            thinking_budget=0, include_thoughts=False
        )
    except (AttributeError, TypeError):
        pass
    try:
        return genai_types.GenerateContentConfig(**kwargs)
    except TypeError:
        kwargs.pop("thinking_config", None)
        return genai_types.GenerateContentConfig(**kwargs)


def transcribir_lote(
    client, genai_types, modelo: str, imagenes: list[tuple[int, bytes]], tokens_salida: int
) -> tuple[dict[int, str], dict]:
    contenido: list = []
    for numero, datos in imagenes:
        contenido.append(f"--- Página {numero} ---")
        contenido.append(genai_types.Part.from_bytes(data=datos, mime_type="image/jpeg"))
    contenido.append("Transcribe cada página con su marca @@@PAGINA: <número>@@@.")

    respuesta = client.models.generate_content(
        model=modelo,
        contents=contenido,
        config=_construir_config(genai_types, tokens_salida),
    )
    tokens: dict = {}
    try:
        uso = respuesta.usage_metadata
        tokens = {
            "prompt": uso.prompt_token_count,
            "respuesta": uso.candidates_token_count,
            "total": uso.total_token_count,
        }
    except (AttributeError, TypeError):
        pass
    esperadas = [n for n, _ in imagenes]
    return dividir_respuesta(respuesta.text or "", esperadas), tokens


def _es_limite_cuota(exc: Exception) -> bool:
    texto = str(exc).upper()
    return "429" in texto or "RESOURCE_EXHAUSTED" in texto or "QUOTA" in texto


def ejecutar(
    pdf: Path,
    salida: Path,
    paginas: list[int],
    lote: int,
    ancho: int,
    modelo: str,
    forzar: bool,
    reanudar: bool,
) -> tuple[dict, int]:
    total, chars_por_pagina = _info_pdf(pdf)
    if chars_por_pagina >= MIN_CHARS_POR_PAGINA_TEXTO and not forzar:
        return {
            "status": "error", "code": 2,
            "message": (
                "el PDF tiene capa de texto "
                f"({chars_por_pagina:.0f} caracteres por página); "
                "usar execution/extraer_libro_pdf.py, o --forzar para OCR igualmente"
            ),
        }, 2

    _cargar_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return {"status": "error", "code": 3, "message": "falta GOOGLE_API_KEY en .env"}, 3
    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        return {"status": "error", "code": 3, "message": "SDK google-genai no instalado"}, 3

    sha = _sha_pdf(pdf)
    cache = salida / ".cache" / sha[:12]
    textos_dir = cache / "textos"
    imagenes_dir = cache / "imagenes"
    textos_dir.mkdir(parents=True, exist_ok=True)
    meta = {"pdf": str(pdf), "sha256": sha, "modelo": modelo, "ancho": ancho, "total": total}
    (cache / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    try:
        client = genai.Client(api_key=api_key)
    except Exception as exc:
        return {"status": "error", "code": 3, "message": f"no se pudo crear el cliente: {exc}"}, 3

    tokens_totales = {"prompt": 0, "respuesta": 0, "total": 0}
    peticiones = 0
    faltantes: list[int] = []

    pendientes = [
        p for p in paginas
        if not (reanudar and (textos_dir / f"pagina_{p:03d}.txt").exists())
    ]

    def _reducir_pagina(numero: int) -> bytes:
        destino = imagenes_dir / f"pagina_{numero:03d}"
        ruta = extraer_imagen_pagina(pdf, numero, destino)
        if ruta is None:
            return b""
        return reducir_imagen(ruta, ancho)

    for grupo in dividir_lotes(pendientes, lote):
        imagenes: list[tuple[int, bytes]] = []
        for numero in grupo:
            try:
                datos = _reducir_pagina(numero)
            except Exception as exc:
                faltantes.append(numero)
                print(f"aviso: página {numero} sin imagen extraíble: {exc}", file=sys.stderr)
                continue
            if not datos:
                faltantes.append(numero)
                continue
            imagenes.append((numero, datos))

        restantes = list(grupo)
        intento = 0
        while imagenes and restantes and intento < MAX_INTENTOS:
            intento += 1
            tokens_salida = 8192
            try:
                obtenidos, tokens = transcribir_lote(
                    client, genai_types, modelo, imagenes, tokens_salida
                )
                peticiones += 1
                for clave in tokens_totales:
                    tokens_totales[clave] += tokens.get(clave, 0)
            except Exception as exc:
                if _es_limite_cuota(exc):
                    return {
                        "status": "error", "code": 5,
                        "message": f"cuota del modelo agotada: {str(exc)[:300]}",
                        "paginas_hechas": len(paginas) - len(pendientes) + peticiones * lote,
                        "cache": str(cache),
                    }, 5
                if intento >= MAX_INTENTOS:
                    faltantes.extend(restantes)
                    restantes = []
                    break
                time.sleep(2 ** intento)
                continue

            for numero, texto in obtenidos.items():
                (textos_dir / f"pagina_{numero:03d}.txt").write_text(texto, encoding="utf-8")
                if numero in restantes:
                    restantes.remove(numero)
            if not obtenidos and len(grupo) > 1:
                imagenes = [
                    (n, d) for n, d in [(n, _reducir_pagina(n)) for n in restantes] if d
                ]
                continue
            if restantes:
                imagenes = [
                    (n, d) for n, d in [(n, _reducir_pagina(n)) for n in restantes] if d
                ]

    faltantes = sorted(set(faltantes) | {
        p for p in paginas if not (textos_dir / f"pagina_{p:03d}.txt").exists()
    })

    textos: dict[int, str] = {}
    vacias: list[int] = []
    ilegibles: list[int] = []
    for numero in paginas:
        ruta = textos_dir / f"pagina_{numero:03d}.txt"
        texto = ruta.read_text(encoding="utf-8") if ruta.exists() else ""
        textos[numero] = texto
        ok, vacia = validar_pagina(texto)
        if vacia:
            vacias.append(numero)
        elif not ok:
            ilegibles.append(numero)

    salida.mkdir(parents=True, exist_ok=True)
    archivo = salida / f"{pdf.stem}_ocr.md"
    partes = [f"# OCR de {pdf.name}\n"]
    for numero in paginas:
        partes.append(f"\n\n<!-- pagina {numero} -->\n\n## Página {numero}\n\n")
        partes.append(textos.get(numero) or "[SIN TRANSCRIBIR]\n")
    archivo.write_text("".join(partes), encoding="utf-8")

    estado = "ok" if not faltantes else "incompleto"
    informe = {
        "status": estado,
        "pdf": str(pdf),
        "paginas": len(paginas),
        "paginas_ok": len(paginas) - len(faltantes) - len(vacias),
        "paginas_vacias": vacias,
        "paginas_ilegibles": ilegibles,
        "paginas_faltantes": faltantes,
        "modelo": modelo,
        "ancho": ancho,
        "lote": lote,
        "archivo": str(archivo),
        "cache": str(cache),
        "peticiones": peticiones,
        "tokens": tokens_totales,
    }
    return informe, (0 if not faltantes else 4)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = _ArgParserExit1(description="OCR de un PDF escaneado con caché reanudable.")
    parser.add_argument("--pdf", required=True, help="PDF escaneado de entrada")
    parser.add_argument("--salida", default=".tmp/ocr", help="directorio de salida")
    parser.add_argument("--paginas", default=None, help="'1-56', '1,3,5-7' o 'todas'")
    parser.add_argument("--lote", type=int, default=4, help="páginas por petición (default 4)")
    parser.add_argument("--ancho", type=int, default=1400, help="ancho en px (default 1400)")
    parser.add_argument("--modelo", default="gemini-2.5-flash")
    parser.add_argument("--forzar", action="store_true", help="OCR aunque haya capa de texto")
    parser.add_argument("--sin-reanudar", action="store_true", help="ignora la caché")
    parser.add_argument("--json", action="store_true", help="salida JSON compacta")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    pdf = Path(args.pdf)
    if not pdf.exists() or not pdf.is_file():
        print(json.dumps({"status": "error", "code": 1, "message": f"no existe: {pdf}"}), file=sys.stderr)
        sys.exit(1)
    try:
        total, _ = _info_pdf(pdf)
        paginas = parse_paginas(args.paginas, total)
        dividir_lotes(paginas, args.lote)
    except Exception as exc:
        print(json.dumps({"status": "error", "code": 1, "message": str(exc)}), file=sys.stderr)
        sys.exit(1)

    try:
        informe, codigo = ejecutar(
            pdf=pdf,
            salida=Path(args.salida),
            paginas=paginas,
            lote=args.lote,
            ancho=args.ancho,
            modelo=args.modelo,
            forzar=args.forzar,
            reanudar=not args.sin_reanudar,
        )
    except Exception as exc:
        print(json.dumps({"status": "error", "code": 3, "message": str(exc)[:500]}), file=sys.stderr)
        sys.exit(3)

    destino = sys.stdout if codigo == 0 else sys.stderr
    print(json.dumps(informe, ensure_ascii=False, indent=None if args.json else 2), file=destino)
    sys.exit(codigo)


if __name__ == "__main__":
    main()
