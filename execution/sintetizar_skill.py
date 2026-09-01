#!/usr/bin/env python3
"""
sintetizar_skill.py — Destilación del texto de un libro en un skill (Layer 3: Execution).

Flujo asociado: directives/libro_a_skill.yaml

Toma el texto extraído de un libro (ej. extraer_libro_pdf.py) más el descriptor
de la entrevista y genera un skill de referencia rápida orientado a RAZONAR y
resolver problemas:
  - SKILL.md  (frontmatter válido name/description + cuerpo de referencia)
  - references/*.md (formulas con representación formal Python/SymPy,
    metodologías de resolución, límites de aplicabilidad, prerrequisitos,
    tablas, glosario)

Opcionalmente acepta --feedback con los errores de validación neuro-simbólica
para corregirlos en un bucle de reflexión (re-síntesis reutilizando el corpus
destilado persistido, sin distilar de nuevo).

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
import time
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


def _sanear_json(s: str) -> str:
    """Repara JSON de LLM tolerando sus descuidos habituales:
       - trailing commas:  [, } / , ] -> } / ]  (python.md #4)
       - barras LaTeX crudas:\O, \mu... -> \O, \mu (invalid escape #6-equivalente)
       Nunca toca escapes válidos (\\n, \\", \\\\, \\u...)."""
    s = re.sub(r",\s*([}\]])", r"\1", s)
    s = re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', r"\\\\", s)
    return s


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
    return json.loads(_sanear_json(candidate))


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


def _yaml_q(valor: str) -> str:
    """Convierte un scalar YAML a string doble-comilla válido (soporta ':' y
    caracteres especiales que rompen scalars planos)."""
    return json.dumps(str(valor), ensure_ascii=False)


def _normalizar_frontmatter(texto: str, nombre: str) -> str:
    """Reescribe el bloque ---...--- con scalares YAML entre comillas.

    El LLM suele emitir descriptions con ':' (ej. 'clave: valor') que rompen el
    scalar plano YAML ('mapping values are not allowed here'). Este saneo
    determinista re-emite name/description con comillas dobles, garantizando que
    yaml.safe_load nunca falle por formato de scalar."""
    m = re.match(r"^---\s*\n(?P<cuerpo>.*?)\n---\s*\n(?P<resto>.*)$", texto, re.DOTALL)
    if not m:
        return texto
    cuerpo, resto = m.group("cuerpo"), m.group("resto")
    lineas: list[str] = []
    if not re.search(r"(?m)^name\s*:", cuerpo):
        lineas.append(f"name: {_yaml_q(nombre)}")
    for linea in cuerpo.splitlines():
        km = re.match(r"^(?P<clave>\w+)\s*:(?P<valor>.*)$", linea)
        if not km:
            lineas.append(linea)
            continue
        clave, valor = km.group("clave"), km.group("valor").strip()
        if clave == "name":
            lineas.append(f"name: {_yaml_q(nombre)}")
        elif clave == "description":
            if valor.startswith('"') or valor.startswith("'"):
                lineas.append(linea)
            else:
                lineas.append(f"description: {_yaml_q(valor)}")
        else:
            lineas.append(linea)
    return f"---\n" + "\n".join(lineas) + "\n---\n" + resto


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


def _llm_estructura(
    resumen_chunks: str, tema: str, idioma: str, nombre: str, modelo: str,
    feedback: Optional[list[dict]] = None,
    estructura_max_tokens: int = 8192,
) -> dict:
    """Pide al LLM el SKILL.md (con frontmatter) y la lista de references."""
    try:
        from execution.llm_client import load_api_key, openrouter_chat  # type: ignore
    except ImportError:
        from llm_client import load_api_key, openrouter_chat  # type: ignore

    api_key = load_api_key()
    sys_prompt = (
        "Eres un arquitecto de 'skills' de agente. Creas un SKILL.md de referencia "
        "rápida para un asistente de código, más archivos auxiliares que habilitan "
        "RAZONAR y RESOLVER problemas (no solo responder preguntas sobre el libro): "
        "metodologías de resolución paso a paso, límites de aplicabilidad y "
        "prerrequisitos conceptuales. Toda representación formal de fórmulas debe "
        "usar código Python/SymPy ejecutable. Extrae TODO del libro: no inventes. "
        f"Responde en {idioma}. Siempre devuelves un único objeto JSON válido."
    )
    ejemplo_json = (
        '{\\n'
        '  "skilL_md": "---\\nname: <NOMBRE>\\ndescription: <frase en 3a persona, '
        'cuándo usarlo, con palabras clave de disparo>\\n---\\n\\n'
        '<Cuerpo del skill: Cuando usar, Conceptos clave, Formulas con su '
        'representacion formal, Tablas, Glosario, Procedimiento basico, '
        'Metodologias de resolucion, Limites de aplicacion, Prerrequisitos>",\\n'
        '  "references": [ {"archivo": "formulas.md", "contenido": "..."}, '
        '{"archivo": "metodologias.md", "contenido": "..."}, '
        '{"archivo": "limites_aplicabilidad.md", "contenido": "..."}, '
        '{"archivo": "prerrequisitos.md", "contenido": "..."}, '
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
        "NORMAS DE CONTENIDO:\n"
        "1. formulas.md: cada fórmula relevante con (a) notación $...$, (b) "
        "representación formal en un bloque ```python con sympy (variables "
        "simbólicas explícitas y restricciones de dominio, ej. x > 0), y (c) nota "
        "'Validez:' indicando el rango de aplicación.\n"
        "2. metodologias.md: plantillas de razonamiento — para cada clase de "
        "problema común del libro, el procedimiento paso a paso numerado que el "
        "autor emplea para resolverlo (método, no solo teoría).\n"
        "3. limites_aplicabilidad.md: por fórmula/teorema, las CONDICIONES DE "
        "BORDE — cuándo NO aplica ('NUNCA aplicar si ...'), supuestos que deben "
        "cumplirse y qué usar en su lugar.\n"
        "4. prerrequisitos.md: grafo de dependencias conceptuales — por concepto "
        "clave, 'requiere: [concepto A, B]' (los conceptos previos necesarios "
        "antes de aplicar el nuevo).\n"
        "5. tablas.md y glosario.md: como de costumbre.\n"
        "6. Los bloques ```python solo deben usar sympy y math (variables, "
        "ecuaciones, solve/simplify), sin archivos, sin red, sin os/subprocess.\n"
        "IMPORTANTE: 'name' del frontmatter debe ser exactamente: " + nombre + ".\n"
        "JSON válido, sin texto fuera del JSON."
    )
    if feedback:
        _fb: list[str] = []
        for err in feedback:
            if isinstance(err, dict):
                ficha = f"- {err.get('archivo', '?')} (bloque {err.get('indice', '?')}): "
                ficha += str(err.get('error') or err.get('estado') or 'error')
                _fb.append(ficha)
            elif isinstance(err, str):
                _fb.append(f"- {err}")
        if _fb:
            user_prompt += (
                "\n\nCORRECCIONES PENDIENTES (el validador neuro-simbólico falló en "
                "estos bloques de esta misma síntesis; corrígelos en la nueva "
                "salida):\n" + "\n".join(_fb[:20])
            )
    content, tokens = openrouter_chat(
        [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=modelo,
        api_key=api_key,
        temperature=0.2,
        max_tokens=estructura_max_tokens,
        title="ELECTRONICA - Estructura Skill",
        reasoning=_razonamiento_para(modelo),
    )
    try:
        raw_dir = Path(__file__).resolve().parent.parent / ".tmp"
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / f"sintesis_estructura_{nombre}_{int(time.time())}.json").write_text(
            content, encoding="utf-8")
    except OSError:
        pass
    return extract_json_from_response(content)


def _destilar_chunks(
    resumen_chunks: list[str], tema: str, idioma: str, modelo: str,
) -> str:
    """Fase 1: destila cada chunk en notas de referencia (devuelve el corpus)."""
    resumenes: list[str] = []
    for chunk in resumen_chunks:
        # nos interesa solo el texto devuelto; los tokens se reportan globalmente
        texto = _llm_chunk(chunk, tema, idioma, modelo)
        if texto and texto.strip() and texto.strip() != "[sin contenido relevante]":
            resumenes.append(texto)
    return "\n\n".join(resumenes) if resumenes else "(sin contenido extraído)"


def _ensamblar_estructura(
    cuerpo_resumen: str, nombre: str, tema: str, idioma: str, modelo: str,
    feedback: Optional[list[dict]] = None,
    estructura_max_tokens: int = 8192,
) -> tuple[str, list[dict]]:
    """Fase 2: ensambla SKILL.md + references a partir del corpus destilado."""
    ultimo_error = None
    for intento in range(1, MAX_RETRIES + 1):
        try:
            estructura = _llm_estructura(
                cuerpo_resumen, tema, idioma, nombre, modelo, feedback=feedback,
                estructura_max_tokens=estructura_max_tokens,
            )
            skilL = estructura.get("skilL_md") or estructura.get("skill_md") or estructura.get("SKILL.md")
            if not isinstance(skilL, str) or not skilL.strip():
                raise ValueError("El LLM no devolvió el campo del SKILL.md")
            skilL = _normalizar_frontmatter(skilL, nombre)
            refs = estructura.get("references") or []
            if not isinstance(refs, list):
                refs = []
            errores_fm = _validar_frontmatter(skilL, nombre)
            if errores_fm:
                raise ValueError(" | ".join(errores_fm))
            return skilL, refs
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
    feedback: Optional[list[dict]] = None,
    estructura_max_tokens: int = 8192,
    usar_corpus: bool = False,
) -> dict:
    chunks = _repartir_chunks(texto, max_chunk_tokens)

    # Corpus destilado persistido como intermedio (hermano del dir, fuera del
    # skill): en re-síntesis con --feedback se reutiliza sin distilar de nuevo
    # (el feedback afecta solo a la fase de estructura, no al chunking).
    corpus_file = salida.parent / f"{salida.name}_destilado.txt"
    if (feedback or usar_corpus) and corpus_file.is_file():
        cuerpo_resumen = corpus_file.read_text(encoding="utf-8")
    else:
        cuerpo_resumen = _destilar_chunks(chunks, tema, idioma, modelo)
        try:
            corpus_file.write_text(cuerpo_resumen, encoding="utf-8")
        except OSError:
            pass

    # Fase 2: estructura (SKILL.md + references) con retry budget.
    skilL_md, refs = _ensamblar_estructura(
        cuerpo_resumen, nombre, tema, idioma, modelo, feedback=feedback,
        estructura_max_tokens=estructura_max_tokens,
    )

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
        "chunks": len(chunks),
        "re_sintesis": bool(feedback),
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
    parser.add_argument("--feedback", default=None, help=(
        "JSON con los errores del validador (bucle de reflexión). Opcional."
    ))
    parser.add_argument("--estructura-max-tokens", type=int, default=8192, help=(
        "Presupuesto de tokens de salida para la fase de ensamblaje (SKILL.md + "
        "references en un JSON grande). Subir si el corpus destilado es muy grande."
    ))
    parser.add_argument("--usar-corpus", action="store_true", help=(
        "Reutilizar el corpus destilado persistido (<salida>_destilado.txt) si "
        "existe, en lugar de distilar los chunks de nuevo (0 créditos extra)."
    ))

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

    # Feedback opcional (bucle de reflexión): lista de dicts {archivo, indice, estado, error}.
    feedback = None
    if args.feedback:
        try:
            feedback = _leer_json(args.feedback).get("bloques") or _leer_json(args.feedback)
        except (FileNotFoundError, json.JSONDecodeError):
            print(json.dumps({"status": "error", "code": 1, "message": f"Feedback JSON inválido: {args.feedback}"}, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)
        if not isinstance(feedback, list):
            feedback = [feedback]

    try:
        resultado = sintetizar(
            texto, entrevista, args.nombre, args.tema, args.idioma,
            modelo, args.max_chunk_tokens, salida, feedback=feedback,
            estructura_max_tokens=args.estructura_max_tokens,
            usar_corpus=args.usar_corpus,
        )
    except (ValueError, RuntimeError, KeyError) as exc:
        print(json.dumps({"status": "error", "code": 3, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(3)

    print(json.dumps(resultado, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
