#!/usr/bin/env python3
"""
sintetizar_skill.py — Destilación del texto de un libro en un skill (Layer 3: Execution).

Flujo asociado: directives/libro_a_skill.yaml

Toma el texto extraído de un libro (ej. extraer_libro_pdf.py) más el descriptor
de la entrevista y genera un skill de referencia rápida:
  - SKILL.md  (frontmatter válido name/description + cuerpo de referencia)
  - references/*.md (tablas, fórmulas, índices, glosarios auxiliares)

El chunking y el ensamblaje final son deterministas; solo la redacción de cada
sección delega en un LLM vía openrouter_chat (según el tier decidido por el
enrutador). Aplica el algoritmo de llaves balanceadas para extraer el JSON.

Uso:
    python3 execution/sintetizar_skill.py \
        --texto .tmp/libro_<name>_texto/texto_completo.txt \
        --entrevista .tmp/entrevista_skill_<name>.json \
        --nombre <name> \
        --tema "<Tema>" \
        --idioma es \
        [--api-backend openrouter|gemini] \
        [--modelo <id>] \
        [--max-chunk-tokens 16000] \
        [--salida .tmp/skill_<name>/]

Salida (stdout, JSON):
    {
      "status": "ok",
      "skill_dir": "...",
      "archivos": ["SKILL.md", "references/..."],
      "secciones": [...],
      "modelo": "...",
      "tokens_consumidos": {...}
    }

Códigos de salida:
    0 — Skill generado y validado
    1 — Error de argumentos o archivos ilegibles
    3 — No se pudo extraer JSON válido del LLM (tras reintentos)
    4 — Estructura del skill inválida (frontmatter/validación)
"""

import argparse
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import yaml

CHARS_PER_TOKEN = 4
MAX_RETRIES = 3


def _razonamiento_para(modelo: str) -> Optional[dict]:
    """Desactiva el thinking de modelos razonadores (deepseek-v4-pro consume
    todo el budget de salida en razonamiento y deja content=None). None = sin
    control (modelos no-razonadores: openai/gpt-oss, gemini, etc.)."""
    return {"enabled": False} if "deepseek" in modelo else None

# Backends de LLM. Default: openrouter (consumo de créditos).
DEFAULT_BACKEND = "openrouter"


class _ArgParserExit1(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(json.dumps({"status": "error", "code": 1, "message": message}), file=sys.stderr)
        sys.exit(1)


def _find_balanced_json(text: str) -> str | None:
    """Encuentra el primer objeto JSON balanceado, respetando strings y escapes."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            if in_string:
                escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def extract_json_from_response(text: str) -> dict:
    """Extrae el primer objeto JSON balanceado del texto crudo del LLM."""
    bloque = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    candidate = None
    if bloque:
        candidate = _find_balanced_json(bloque.group(1))
    if candidate is None:
        candidate = _find_balanced_json(text)
    if candidate is None:
        raise ValueError("No se pudo extraer un JSON válido de la respuesta del modelo.")
    return json.loads(candidate)


def _repartir_chunks(texto: str, max_tokens: int) -> list[str]:
    """Divide el texto en chunks bajo max_tokens aprox., partiendo en párrafos."""
    max_chars = max_tokens * CHARS_PER_TOKEN
    parrafos = [p.strip() for p in texto.split("\n\n") if p.strip()]
    chunks: list[str] = []
    actual: list[str] = []
    actual_len = 0
    for parrafo in parrafos:
        # Párrafos individuales más grandes que el límite: partir por página.
        if len(parrafo) > max_chars:
            if actual:
                chunks.append("\n\n".join(actual))
                actual, actual_len = [], 0
            for i in range(0, len(parrafo), max_chars):
                chunks.append(parrafo[i:i + max_chars])
            continue
        if actual_len + len(parrafo) > max_chars and actual:
            chunks.append("\n\n".join(actual))
            actual, actual_len = [], 0
        actual.append(parrafo)
        actual_len += len(parrafo) + 2
    if actual:
        chunks.append("\n\n".join(actual))
    return chunks or [texto]


def _leer_json(ruta: str) -> dict:
    p = Path(ruta)
    if not p.is_file():
        raise FileNotFoundError(f"No existe: {ruta}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _validar_frontmatter(texto: str, nombre: str) -> list[str]:
    """Valida que el SKILL.md tenga frontmatter name/description coherentes."""
    errores: list[str] = []
    m = re.match(r"^---\s*\n(.*?)\n---", texto, re.DOTALL)
    if not m:
        return ["El SKILL.md no tiene bloque de frontmatter YAML (--- ... ---)"]
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:
        return [f"Frontmatter YAML inválido: {exc}"]
    if not isinstance(fm, dict):
        return ["El frontmatter no es un objeto YAML"]
    name = fm.get("name")
    if not isinstance(name, str) or not name.strip():
        errores.append("El frontmatter carece de 'name' no vacío")
    elif nombre and name.strip() != nombre:
        errores.append(f"'name' del skill ({name!r}) no coincide con la carpeta ({nombre!r})")
    desc = fm.get("description")
    if not isinstance(desc, str) or len(desc.strip()) < 20:
        errores.append("La 'description' del skill es demasiado corta (<20 chars)")
    return errores


def _llm_chunk(chunk: str, tema: str, idioma: str, modelo: str) -> str:
    """Destila un chunk del libro en notas de referencia (texto plano markdown)."""
    try:
        from execution.llm_client import load_api_key, openrouter_chat  # type: ignore
    except ImportError:
        from llm_client import load_api_key, openrouter_chat  # type: ignore

    api_key = load_api_key()
    sys_prompt = (
        "Eres un asistente experto que destila libros técnicos en material de "
        "referencia rápida y conciso. No inventes: solo sintetiza lo que está en "
        f"el fragmento. Responde en {idioma}."
    )
    user_prompt = (
        f"Tema del libro: {tema}\n\n"
        "A partir del fragmento, produce un resumen de referencia (markdown) con: "
        "conceptos clave, definiciones, fórmulas si las hay (en notación simple, "
        "usando $...$ para matemáticas), tablas si proceden, y ejemplos breves. "
        "Sé denso y estructurado en secciones con encabezados ###. "
        "NO incluyas frontmatter YAML. Si el fragmento no aporta información "
        "nueva, devuelve solo la línea '[sin contenido relevante]'.\n\n"
        f"FRAGMENTO INICIA:\n{chunk}\nFRAGMENTO TERMINA."
    )
    ultimo_error = None
    for intento in range(1, MAX_RETRIES + 1):
        try:
            content, tokens = openrouter_chat(
                [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=modelo,
                api_key=api_key,
                temperature=0.3,
                max_tokens=2048,
                title="ELECTRONICA - Sintetizar Skill",
                reasoning=_razonamiento_para(modelo),
            )
            if content and content.strip():
                return content.strip()
            raise RuntimeError("El modelo devolvió un mensaje vacío.")
        except Exception as exc:  # noqa: BLE001
            ultimo_error = exc
            if intento >= MAX_RETRIES:
                break
    raise RuntimeError(
        f"No se pudo destilar el chunk tras {MAX_RETRIES} intentos: {ultimo_error}"
    )


def _llm_estructura(resumen_chunks: str, tema: str, idioma: str, nombre: str, modelo: str) -> dict:
    """Pide al LLM el SKILL.md (con frontmatter) y la lista de references."""
    try:
        from execution.llm_client import load_api_key, openrouter_chat  # type: ignore
    except ImportError:
        from llm_client import load_api_key, openrouter_chat  # type: ignore

    api_key = load_api_key()
    sys_prompt = (
        "Eres un arquitecto de 'skills' de agente. Creas un SKILL.md de referencia "
        "rápida para un asistente de código, más archivos auxiliares. "
        f"Responde en {idioma}. Siempre devuelves un único objeto JSON válido."
    )
    ejemplo_json = (
        '{\\n'
        '  "skilL_md": "---\\nname: <NOMBRE>\\ndescription: <frase en 3a persona, '
        'cuándo usarlo, con palabras clave de disparo>\\n---\\n\\n'
        '<Cuerpo del skill: Cuando usar, Conceptos clave, Formulas, Tablas, '
        'Glosario, Procedimiento basico>",\\n'
        '  "references": [ {"archivo": "formulas.md", "contenido": "..."}, '
        '{"archivo": "tablas.md", "contenido": "..."}, '
        '{"archivo": "glosario.md", "contenido": "..."} ]\\n'
        '}'
    )
    user_prompt = (
        f"El skill se llamará: {nombre}\n"
        f"Tema del libro: {tema}\n\n"
        "Este es el resumen de referencia generado del libro:\n\n"
        f"{resumen_chunks}\n\n"
        "Genera un objeto JSON con esta forma EXACTA:\n"
        f"{ejemplo_json}\n"
        "IMPORTANTE: 'name' del frontmatter debe ser exactamente: " + nombre + ".\n"
        "JSON válido, sin texto fuera del JSON."
    )
    content, tokens = openrouter_chat(
        [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=modelo,
        api_key=api_key,
        temperature=0.2,
        max_tokens=8192,
        title="ELECTRONICA - Estructura Skill",
        reasoning=_razonamiento_para(modelo),
    )
    return extract_json_from_response(content)


def _construir_skill(
    nombre: str, tema: str, idioma: str, resumen_chunks: list[str], modelo: str
) -> tuple[str, list[dict], dict]:
    """Devuelve (skilL_md_text, references, tokens_totales)."""
    tokens_totales: dict = {"prompt": 0, "respuesta": 0}

    # Fase 1: destilar cada chunk.
    resumenes: list[str] = []
    for chunk in resumen_chunks:
        # nos interesa solo el texto devuelto; los tokens se reportan globalmente
        texto = _llm_chunk(chunk, tema, idioma, modelo)
        if texto and texto.strip() and texto.strip() != "[sin contenido relevante]":
            resumenes.append(texto)

    cuerpo_resumen = "\n\n".join(resumenes) if resumenes else "(sin contenido extraído)"

    # Fase 2: ensamblar estructura (SKILL.md + references). Con reintentos.
    ultimo_error = None
    for intento in range(1, MAX_RETRIES + 1):
        try:
            estructura = _llm_estructura(cuerpo_resumen, tema, idioma, nombre, modelo)
            skilL = estructura.get("skilL_md") or estructura.get("skill_md") or estructura.get("SKILL.md")
            if not isinstance(skilL, str) or not skilL.strip():
                raise ValueError("El LLM no devolvió el campo del SKILL.md")
            refs = estructura.get("references") or []
            if not isinstance(refs, list):
                refs = []
            errores_fm = _validar_frontmatter(skilL, nombre)
            if errores_fm:
                raise ValueError(" | ".join(errores_fm))
            return skilL, refs, tokens_totales
        except Exception as exc:  # noqa: BLE001
            ultimo_error = exc
            if intento >= MAX_RETRIES:
                break
    raise ValueError(f"No se pudo ensamblar un skill válido tras {MAX_RETRIES} intentos: {ultimo_error}")


def _sanitizar_ref_nombre(archivo: str) -> str:
    base = Path(archivo).name
    base = re.sub(r"[^a-zA-Z0-9_.\-]", "_", base)
    if not base.endswith(".md"):
        base += ".md"
    return base


def _limpiar_salida(salida: Path) -> None:
    """Elimina artefactos de una corrida anterior para que el directorio de
    salida refleje EXACTAMENTE la síntesis actual (evita references/ o SKILL.md
    obsoletos acumulados en carreras previas con un modelo que omitió refs)."""
    for p in (salida / "SKILL.md", salida / "references"):
        try:
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            elif p.is_file():
                p.unlink(missing_ok=True)
        except OSError:
            pass


def sintetizar(
    texto: str, entrevista: dict, nombre: str, tema: str, idioma: str,
    modelo: str, max_chunk_tokens: int, salida: Path,
) -> dict:
    chunks = _repartir_chunks(texto, max_chunk_tokens)

    # Fase LLM (con retry budget del framework sobre la fase de estructura).
    skilL_md, refs, tokens = _construir_skill(nombre, tema, idioma, chunks, modelo)

    salida.mkdir(parents=True, exist_ok=True)
    _limpiar_salida(salida)

    archivo_md = salida / "SKILL.md"
    archivo_md.write_text(skilL_md.strip() + "\n", encoding="utf-8")

    refs_dir = salida / "references"
    archivos: list[str] = [str(archivo_md)]
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        nombre_ref = _sanitizar_ref_nombre(str(ref.get("archivo", "")))
        contenido = ref.get("contenido")
        if not isinstance(contenido, str) or not contenido.strip():
            continue
        refs_dir.mkdir(parents=True, exist_ok=True)
        ruta = refs_dir / nombre_ref
        ruta.write_text(contenido.strip() + "\n", encoding="utf-8")
        archivos.append(str(ruta))

    # Re-validar el SKILL.md final ya en disco.
    errores = _validar_frontmatter(archivo_md.read_text(encoding="utf-8"), nombre)
    if errores:
        print(
            json.dumps(
                {"status": "error", "code": 4, "message": "; ".join(errores)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(4)

    return {
        "status": "ok",
        "skill_dir": str(salida),
        "archivos": archivos,
        "secciones": [str(s) for s in sorted(refs_dir.glob("*.md"))] if refs_dir.is_dir() else [],
        "modelo": modelo,
        "tokens_consumidos": tokens,
        "chunks": len(chunks),
    }


def main() -> None:
    parser = _ArgParserExit1(description=__doc__)
    parser.add_argument("--texto", required=True, help="Archivo txt extraído del PDF.")
    parser.add_argument("--entrevista", required=True, help="JSON de la entrevista.")
    parser.add_argument("--nombre", required=True, help="Nombre snake_case del skill.")
    parser.add_argument("--tema", required=True, help="Tema/dominio del libro.")
    parser.add_argument("--idioma", default="es", help="Idioma del skill (default es).")
    parser.add_argument("--api-backend", default=DEFAULT_BACKEND, choices=["openrouter", "gemini"])
    parser.add_argument("--modelo", default=None, help="ID de modelo OpenRouter (override).")
    parser.add_argument("--max-chunk-tokens", type=int, default=16000)
    parser.add_argument("--salida", default=None, help="Directorio del skill generado.")

    args = parser.parse_args()

    try:
        texto = Path(args.texto).read_text(encoding="utf-8")
        entrevista = _leer_json(args.entrevista)
    except FileNotFoundError as exc:
        print(json.dumps({"status": "error", "code": 1, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(json.dumps({"status": "error", "code": 1, "message": f"Entrevista JSON inválida: {exc}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    # Backend gemini NO está soportado para la síntesis (requiere estructura JSON
    # robusta que openrouter_chat provee). Forzamos openrouter.
    if args.api_backend == "gemini":
        print(
            json.dumps(
                {
                    "status": "error",
                    "code": 1,
                    "message": (
                        "Backend 'gemini' no soportado para sintetizar_skill.py; "
                        "usar 'openrouter' (o pasar --modelo con backend openrouter)."
                    ),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    modelo = args.modelo
    if not modelo:
        # Decision determinista: contexto masivo por defecto (destilación de libros).
        MODEL_TIERS = {"deepseek": "deepseek/deepseek-v4-pro"}
        modelo = MODEL_TIERS["deepseek"]

    salida = Path(args.salida) if args.salida else Path(".tmp") / f"skill_{args.nombre}"

    # Dry-run de estructura: si hay una bandera, se resuelve en el orquestador.
    try:
        resultado = sintetizar(
            texto, entrevista, args.nombre, args.tema, args.idioma,
            modelo, args.max_chunk_tokens, salida,
        )
    except (ValueError, RuntimeError, KeyError) as exc:
        print(json.dumps({"status": "error", "code": 3, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(3)

    print(json.dumps(resultado, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
