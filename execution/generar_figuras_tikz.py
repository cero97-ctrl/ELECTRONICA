#!/usr/bin/env python3
"""Genera las figuras TikZ de las 8 prácticas desde el markdown del OCR (capa 3).

Contrato:
  * Las descripciones `[FIGURA: ...]` del OCR son la fuente de verdad. La
    numeración `pNN_fNN` NO se redefine aquí: se importa
    `figuras_de_practica` de `generar_practicas_desde_ocr.py`.
  * El modelo propone código TikZ por lotes (una práctica por lote). Cada
    bloque se valida COMPILÁNDOLO de forma aislada; solo lo que compila con
    0 líneas `!` entra al manifest.
  * El manifest se guarda tras cada lote, así que una corrida interrumpida se
    reanuda sin repetir lo ya validado. Con el manifest presente, el proceso
    es determinista: no se vuelve a llamar al modelo.

Sin manifest, el generador de prácticas sigue emitiendo cajas de descripción
(comportamiento heredado). Aquí no se procesa nada inline en el chat.

Uso:
  python3 execution/generar_figuras_tikz.py --check
  python3 execution/generar_figuras_tikz.py --limite 1 --json
  python3 execution/generar_figuras_tikz.py --modelo opus --json
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ / "execution") not in sys.path:
    sys.path.insert(0, str(RAIZ / "execution"))

from estilo_infografia import PREAMBULO_INFOGRAFIA  # noqa: E402
from generar_practicas_desde_ocr import (  # noqa: E402
    extraer_practicas,
    figuras_de_practica,
    parsear_rango,
)
from compile_latex import compile_latex_code  # noqa: E402
from llm_client import openrouter_chat, resolver_modelo  # noqa: E402

OCR_POR_DEFECTO = RAIZ / ".tmp" / "ocr_practicas" / "practicas_ocr.md"
SALIDA_POR_DEFECTO = RAIZ / ".tmp" / "figuras_tikz"
MANIFEST_NOMBRE = "figuras.json"
MAX_INTENTOS = 3
LOTE_TAMANO = 1  # una práctica por lote: mantiene el prompt acotado

RE_BLOQUE = re.compile(
    r"<<<FIGURA:\s*([a-z0-9_]+)\s*>>>\s*(.*?)\s*<<<FIN:\s*\1\s*>>>",
    re.IGNORECASE | re.DOTALL,
)

PROHIBIDOS = (
    r"\documentclass", r"\usepackage", r"\begin{document}", r"\end{document}",
    "pgfplots", "galvanometer", "full diode bridge", "pC",
    "[FIGURA", "[ILEGIBLE", r"\input", r"\include", r"\write18",
)

SYSTEM_INSTRUCTION = r"""Generas dibujos LaTeX para unas prácticas de Laboratorio de Física.
Tu salida es código TikZ/circuitikz, no prosa.

REGLAS OBLIGATORIAS:
1. El paquete circuitikz YA está cargado con la opción [european, straightvoltages].
   NO escribas \usepackage, \documentclass ni \begin{document}. NO uses pgfplots
   ni ningún paquete adicional. Para gráficas dibuja los ejes con \draw de TikZ.
2. Devuelve UN bloque por figura, exactamente así, sin nada más antes ni después:

<<<FIGURA:p01_f01>>>
\begin{center}
\begin{circuitikz}
  ...
\end{circuitikz}
\par\smallskip{\small\itshape Pie de la figura}
\end{center}
<<<FIN:p01_f01>>>

3. Usa el ID del bloque tal cual aparece en la lista. No inventes IDs, no omitas
   ninguno y no repitas ninguno. Un bloque por ID, en el mismo orden de la lista.
4. Bipolos circuitikz permitidos: V (fuente), R, L, C, D (diodo), ammeter,
   voltmeter, ohmmeter, switch (interruptor) y ground. NO existen
   `galvanometer`, `full diode bridge` ni el capacitor polar `pC`: no los uses.
5. Para gráficas usa \begin{tikzpicture} con \draw para ejes, escala y curva
   cualitativa; marca los puntos notables que pida la descripción. Sin tablas de datos.
6. Protege con llaves cualquier etiqueta que contenga `=` o comas, por ejemplo
   l={$V = I R$}. Escapa `%`, `&`, `#` y `_` que aparezcan en texto plano.
   No escribas caracteres Unicode griegos sueltos: usa $\Omega$, $\mu$, $\tau$.
7. El pie bajo la figura es una frase corta en español, sin el signo `%`.
8. No incluyas la descripción del OCR como texto dentro del dibujo: úsala solo
   para decidir QUÉ dibujar. No escribas markdown, cercas de código ni comentarios.
9. Si la descripción menciona varias partes (a), (b), dibújalas una al lado de
   otra dentro del MISMO entorno, con sus etiquetas.

Devuelve SOLO los bloques delimitados. Ninguna explicación."""


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def cargar_manifest(ruta: Path) -> dict[str, Any]:
    """Lee el manifest; uno vacío si no existe o está corrupto."""
    if not ruta.is_file():
        return {"status": "pendiente", "figuras": {}, "fallos": []}
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"status": "pendiente", "figuras": {}, "fallos": []}
    datos.setdefault("figuras", {})
    datos.setdefault("fallos", [])
    return datos


def guardar_manifest(ruta: Path, manifest: dict[str, Any]) -> None:
    """Escritura atómica: el manifest nunca queda a medias."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".json.tmp")
    temporal.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporal.replace(ruta)


def extraer_figuras(ruta_ocr: Path, practicas: list[int]) -> dict[str, dict[str, Any]]:
    """Extrae todos los descriptores de figura de las prácticas pedidas."""
    texto = ruta_ocr.read_text(encoding="utf-8")
    por_numero = extraer_practicas(texto)
    figuras: dict[str, dict[str, Any]] = {}
    for numero in practicas:
        if numero not in por_numero:
            continue
        for descriptor in figuras_de_practica(por_numero[numero]):
            figuras[descriptor["id"]] = descriptor
    return figuras


def validar_codigo(codigo: str, fid: str) -> list[str]:
    """Validación determinista del bloque propuesto, antes de aceptarlo."""
    problemas: list[str] = []
    if not codigo.strip():
        return ["código vacío"]
    for patron in PROHIBIDOS:
        if patron in codigo:
            problemas.append(f"contiene '{patron}', prohibido")
    if codigo.count(r"\begin{") != codigo.count(r"\end{"):
        problemas.append("entornos LaTeX desbalanceados")
    if r"\begin{center}" not in codigo or r"\end{center}" not in codigo:
        problemas.append("falta el entorno center que enmarca la figura")
    if not (r"\begin{circuitikz}" in codigo or r"\begin{tikzpicture}" in codigo):
        problemas.append("no contiene circuitikz ni tikzpicture")
    if re.search(r"cumple|descripción|FIGURA:", codigo, re.IGNORECASE):
        problemas.append("parece prosa del OCR dentro del código")
    return problemas


def compilar_figura(codigo: str, fid: str, build: Path) -> list[str]:
    """Compila la figura aislada y devuelve los errores del log (0 = válida)."""
    documento = (
        PREAMBULO_INFOGRAFIA
        + "\n\\begin{document}\n"
        + codigo
        + "\n\\end{document}\n"
    )
    with contextlib.redirect_stdout(io.StringIO()):
        resultado = compile_latex_code(
            documento, job_name=f"figura_{fid}",
            output_dir=str(build), clean=False,
        )
    log = build / f"figura_{fid}.log"
    texto_log = log.read_text(encoding="utf-8", errors="ignore") if log.exists() else ""
    errores = re.findall(r"^! (.+)$", texto_log, re.M)
    if not errores and not resultado.get("success"):
        errores = [resultado.get("error", "compilación fallida sin detalle")]
    pdf = build / f"figura_{fid}.pdf"
    if not errores and not pdf.exists():
        errores = ["compilación sin errores pero sin PDF"]
    return [str(e)[:160] for e in errores]


def parsear_respuesta(respuesta: str, ids_esperados: list[str]) -> tuple[dict[str, str], list[str]]:
    """Extrae los bloques delimitados y reporta IDs ausentes o repetidos."""
    hallados: dict[str, str] = {}
    for m in RE_BLOQUE.finditer(respuesta):
        fid = m.group(1).lower()
        if fid in hallados:
            continue
        hallados[fid] = m.group(2).strip()
    problemas: list[str] = []
    for fid in ids_esperados:
        if fid not in hallados:
            problemas.append(f"falta el bloque {fid}")
    for fid in hallados:
        if fid not in ids_esperados:
            problemas.append(f"ID inesperado {fid}")
    return hallados, problemas


def armar_mensaje(lote: list[dict[str, Any]]) -> str:
    lineas = [
        "Genera un bloque LaTeX por cada una de estas figuras. "
        "Devuelve SOLO los bloques delimitados, sin explicación ni cercas de código.",
        "",
        "FIGURAS:",
    ]
    for f in lote:
        lineas.append(f"- {f['id']}: {f['descripcion']}")
    return "\n".join(lineas)


def _modelo_y_clave(modelo_solicitado: str) -> tuple[str, str]:
    clave = os.getenv("OPENROUTER_API_KEY", "")
    return resolver_modelo(modelo_solicitado), clave


def generar(
    ruta_ocr: Path,
    salida: Path,
    esperadas: list[int],
    modelo: str = "opus",
    limite: int | None = None,
    forzar: bool = False,
    max_intentos: int = MAX_INTENTOS,
    informar: bool = True,
) -> dict[str, Any]:
    """Genera, valida y cachea las figuras. Devuelve un informe JSON."""
    try:
        figuras = extraer_figuras(ruta_ocr, esperadas)
    except OSError as exc:
        return {"status": "error", "code": 2, "message": f"no se pudo leer el OCR: {exc}"}
    if not figuras:
        return {"status": "error", "code": 2, "message": "el OCR no contiene figuras"}

    if limite is not None:
        elegidas = list(figuras)[:limite]
        figuras = {fid: figuras[fid] for fid in elegidas}

    ruta_manifest = salida / MANIFEST_NOMBRE
    manifest = cargar_manifest(ruta_manifest)
    cache_actual = manifest.get("figuras", {})
    pendientes: dict[str, dict[str, Any]] = {}
    for fid, descriptor in figuras.items():
        guardado = cache_actual.get(fid, {})
        if (not forzar and guardado.get("codigo")
                and guardado.get("sha256_16") == descriptor["sha256_16"]):
            continue
        pendientes[fid] = descriptor

    if not pendientes:
        manifest["status"] = "ok"
        manifest["ocr"] = str(ruta_ocr)
        manifest["figuras"] = {
            fid: cache_actual[fid] for fid in figuras if fid in cache_actual
        }
        guardar_manifest(ruta_manifest, manifest)
        return {
            "status": "ok", "code": 0, "manifest": str(ruta_manifest),
            "figuras": len(figuras), "generadas_ahora": 0,
            "sha_conjunto": _sha("".join(
                manifest["figuras"][fid]["codigo"] for fid in sorted(manifest["figuras"])
            )),
        }

    modelo_resuelto, api_key = _modelo_y_clave(modelo)
    if not api_key:
        return {"status": "error", "code": 7,
                "message": "falta OPENROUTER_API_KEY en .env"}
    max_tokens = int(os.getenv("OPENROUTER_MAX_TOKENS", "8192"))
    build = salida / ".build_figuras"
    build.mkdir(parents=True, exist_ok=True)
    generadas = 0
    fallos: list[str] = []

    # Un lote por práctica, en orden de práctica y de índice dentro de ella.
    por_practica: dict[int, list[dict[str, Any]]] = {}
    for descriptor in pendientes.values():
        por_practica.setdefault(descriptor["practica"], []).append(descriptor)
    lotes = [
        sorted(items, key=lambda d: d["indice"])
        for _, items in sorted(por_practica.items())
    ]

    for lote in lotes:
        ids = [d["id"] for d in lote]
        pendientes_lote = {d["id"]: d for d in lote}
        for intento in range(1, max_intentos + 1):
            mensaje = armar_mensaje([d for d in lote if d["id"] in pendientes_lote])
            if intento > 1:
                mensaje += ("\n\nEl intento anterior falló en: "
                            + ", ".join(pendientes_lote)
                            + ". Corrige esos bloques y devuélvelos todos otra vez.")
            try:
                respuesta, _tokens = openrouter_chat(
                    [
                        {"role": "system", "content": SYSTEM_INSTRUCTION},
                        {"role": "user", "content": mensaje},
                    ],
                    model=modelo_resuelto,
                    api_key=api_key,
                    temperature=0.1,
                    max_tokens=max_tokens,
                    title="ELECTRONICA-FIGURAS-TIKZ",
                )
            except Exception as exc:  # noqa: BLE001 — error de red/API del proveedor
                if intento == max_intentos:
                    fallos.append(f"{ids}: error de API: {type(exc).__name__}: {exc}"[:200])
                if informar:
                    print(f"  API falló (intento {intento}/{max_intentos}) para {ids}",
                          file=sys.stderr)
                continue

            bloques, problemas_formato = parsear_respuesta(respuesta, list(pendientes_lote))
            if problemas_formato:
                if informar:
                    print(f"  formato incompleto (intento {intento}): "
                          + "; ".join(problemas_formato[:3]), file=sys.stderr)
                if intento == max_intentos:
                    fallos.extend(problemas_formato[:5])
                continue

            for fid in list(pendientes_lote):
                codigo = bloques[fid]
                problemas = validar_codigo(codigo, fid)
                if not problemas:
                    problemas = compilar_figura(codigo, fid, build)
                if problemas:
                    if informar:
                        print(f"  {fid} rechazada (intento {intento}): "
                              + "; ".join(problemas[:2]), file=sys.stderr)
                    if intento == max_intentos:
                        fallos.append(f"{fid}: " + "; ".join(problemas[:3])[:160])
                    continue
                descriptor = pendientes_lote.pop(fid)
                manifest.setdefault("figuras", {})[fid] = {
                    **descriptor,
                    "codigo": codigo,
                    "sha_codigo": _sha(codigo),
                    "modelo": modelo_resuelto,
                }
                generadas += 1
            manifest["fallos"] = list(fallos)
            guardar_manifest(ruta_manifest, manifest)
            if not pendientes_lote:
                break

    manifest["status"] = "ok" if not fallos and all(
        fid in manifest.get("figuras", {}) for fid in figuras
    ) else "error"
    manifest["ocr"] = str(ruta_ocr)
    manifest["modelo"] = modelo_resuelto
    manifest["fallos"] = fallos
    guardar_manifest(ruta_manifest, manifest)

    informe: dict[str, Any] = {
        "status": manifest["status"],
        "code": 0 if manifest["status"] == "ok" else 4,
        "manifest": str(ruta_manifest),
        "figuras": len(figuras),
        "generadas_ahora": generadas,
        "fallos": fallos,
    }
    if manifest["status"] == "ok":
        informe["sha_conjunto"] = _sha("".join(
            manifest["figuras"][fid]["codigo"] for fid in sorted(manifest["figuras"])
        ))
    return informe


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Genera y valida las figuras TikZ de las prácticas desde el OCR"
    )
    ap.add_argument("--ocr", default=str(OCR_POR_DEFECTO), help="markdown del OCR")
    ap.add_argument("--salida", default=str(SALIDA_POR_DEFECTO), help="directorio del manifest")
    ap.add_argument("--practicas", default=None, help="'1-8', '1,3,5-7' o 'todas'")
    ap.add_argument("--modelo", default="opus", help="tier o ID de OpenRouter (default: opus)")
    ap.add_argument("--limite", type=int, default=None, help="generar solo las primeras N (prueba)")
    ap.add_argument("--forzar", action="store_true", help="regenerar figuras ya cacheadas")
    ap.add_argument("--max-intentos", type=int, default=MAX_INTENTOS, help="retry budget (máx 3)")
    ap.add_argument("--check", action="store_true", help="solo listar figuras y cobertura, sin API")
    ap.add_argument("--dry-run", action="store_true", help="mostrar lotes sin llamar al modelo")
    ap.add_argument("--json", action="store_true", help="emitir informe JSON")
    args = ap.parse_args(argv)

    ruta_ocr = Path(args.ocr).resolve()
    salida = Path(args.salida).resolve()
    try:
        esperadas = parsear_rango(args.practicas)
    except ValueError:
        print("rango de prácticas inválido", file=sys.stderr)
        return 1

    if not ruta_ocr.is_file():
        print(json.dumps({"status": "error", "code": 2,
                          "message": f"no existe el OCR: {ruta_ocr}"}, ensure_ascii=False),
              file=sys.stderr)
        return 2
    if args.max_intentos < 1 or args.max_intentos > MAX_INTENTOS:
        print(f"--max-intentos debe estar entre 1 y {MAX_INTENTOS}", file=sys.stderr)
        return 3

    if args.check or args.dry_run:
        figuras = extraer_figuras(ruta_ocr, esperadas)
        por_practica: dict[int, int] = {}
        for d in figuras.values():
            por_practica[d["practica"]] = por_practica.get(d["practica"], 0) + 1
        informe = {
            "status": "ok", "ocr": str(ruta_ocr),
            "figuras": len(figuras), "por_practica": por_practica,
            "lotes": len(por_practica), "dry_run": args.dry_run,
        }
        print(json.dumps(informe, ensure_ascii=False, indent=2))
        return 0

    try:
        from dotenv import load_dotenv
        load_dotenv(RAIZ / ".env")
    except ImportError:
        pass

    informe = generar(
        ruta_ocr, salida, esperadas, modelo=args.modelo, limite=args.limite,
        forzar=args.forzar, max_intentos=args.max_intentos,
    )
    if args.json:
        print(json.dumps(informe, ensure_ascii=False, indent=2))
    elif informe.get("status") == "ok":
        print(f"OK: {informe['figuras']} figuras validadas "
              f"({informe['generadas_ahora']} generadas ahora) → {informe['manifest']}")
    else:
        print(informe.get("message", "falló la generación de figuras"), file=sys.stderr)
        for detalle in informe.get("fallos", []):
            print(" - " + detalle, file=sys.stderr)
    return int(informe.get("code", 1))


if __name__ == "__main__":
    sys.exit(main())
