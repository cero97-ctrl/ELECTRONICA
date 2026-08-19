#!/usr/bin/env python3
"""
elaborar_examen.py — Generación de exámenes de Electrónica con LLM (Layer 3: Execution)

Lee un tema del plan de estudios y genera 5 preguntas de razonamiento y cálculo
en formato JSON usando un modelo de lenguaje (Gemini / OpenRouter).

Uso:
    python3 execution/elaborar_examen.py --tema "Semana 4: Condensadores"
    python3 execution/elaborar_examen.py --tema "Semana 8: Transistor BJT" --nivel avanzada

Salida (stdout, JSON):
    {
      "status": "ok",
      "api_backend": "gemini",
      "tema": "Semana 4: Condensadores",
      "modelo": "gemini-2.5-flash",
      "nivel": "intermedia",
      "examen": {
        "titulo": "Examen: Fundamentos de Capacitores y Circuitos RC",
        "dificultad": "intermedia",
        "duracion_sugerida": "90 minutos",
        "instrucciones": "...",
        "preguntas": [
          {
            "numero": 1,
            "enunciado": "Enunciado con formato LaTeX",
            "puntaje": "2.0 puntos",
            "solucion": "Solución detallada paso a paso",
            "conceptos_evaluados": ["Concepto1", "Concepto2"],
            "dificultad": "media"
          }
        ]
      },
      "tokens_usados": {...},
      "timestamp": "..."
    }

Códigos de salida:
    0 — Examen generado exitosamente
    1 — Argumento inválido
    2 — Error de API (autenticación, límite de tasa, etc.)
    4 — Respuesta del modelo no parseable como JSON
"""

import argparse
import json
import os
import re
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── SDKs de LLMs ─────────────────────────────────────────────────────────────────
_GEMINI_AVAILABLE = False
_GENAI_SDK = None
try:
    from google import genai
    from google.genai import types as genai_types
    _GEMINI_AVAILABLE = True
    _GENAI_SDK = "new"
except ImportError:
    try:
        import google.generativeai as _genai_legacy
        from google.generativeai import types as _genai_legacy_types
        _GEMINI_AVAILABLE = True
        _GENAI_SDK = "legacy"
    except ImportError:
        pass

_OPENROUTER_AVAILABLE = False
try:
    from openai import OpenAI
    _OPENROUTER_AVAILABLE = True
except ImportError:
    pass

try:
    from execution.llm_client import openrouter_chat
except ImportError:
    from llm_client import openrouter_chat


# ── System Instruction ───────────────────────────────────────────────────────────

SYSTEM_INSTRUCTION = r"""
Eres un profesor universitario de Electrónica con amplia experiencia en la elaboración de exámenes de razonamiento y cálculo. Tu tarea es generar un examen original de 5 preguntas que evalúe tanto la comprensión conceptual como la capacidad de análisis cuantitativo de los estudiantes.

## Requisitos del examen
1. **5 preguntas de desarrollo** (no opción múltiple) de razonamiento y cálculo.
2. **Originalidad:** las preguntas deben ser inéditas, no copiadas de libros de texto.
3. **Contexto práctico:** situar las preguntas en aplicaciones reales o ingenieriles siempre que sea posible.
4. **Dificultad progresiva:** preguntas 1-2 de dificultad baja-media; preguntas 3-5 de dificultad media-alta.
5. **Cada pregunta debe incluir:**
   - Enunciado claro con datos numéricos y valores de componentes.
   - Puntaje sugerido según su complejidad y peso en el examen total (la suma debe dar 10.0).
   - Solución directa, estructurada y matemáticamente completa (en LaTeX), de forma concisa y evitando explicaciones conversacionales redundantes para optimizar la longitud del archivo.
   - Conceptos evaluados (lista de temas específicos que la pregunta cubre).
6. **Formato LaTeX:** los enunciados y soluciones deben usar sintaxis LaTeX para fórmulas matemáticas ($V_{out}$, $I_C$, $\frac{dv}{dt}$, etc.) y referencias a componentes.
7. **Diagramas:** si la pregunta requiere un circuito eléctrico, incluir una descripción textual detallada del diagrama con valores de componentes y conexiones para que el profesor lo dibuje con circuitikz.

## Formato de respuesta
Debes responder ÚNICAMENTE con un objeto JSON válido, sin texto adicional, con esta estructura exacta:

{
  "examen": {
    "titulo": "Título descriptivo del examen",
    "dificultad": "intermedia",
    "duracion_sugerida": "90 minutos",
    "instrucciones": "Instrucciones claras para el estudiante sobre el formato del examen, materiales permitidos y criterios de evaluación.",
    "preguntas": [
      {
        "numero": 1,
        "enunciado": "Enunciado completo de la pregunta con fórmulas $LaTeX$.",
        "puntaje": "2.0 puntos",
        "solucion": "Desarrollo matemático en LaTeX paso a paso, conciso y directo al grano (sin rodeos explicativos).",
        "conceptos_evaluados": ["Concepto 1", "Concepto 2"],
        "dificultad": "baja | media | alta",
        "diagrama_sugerido": "Descripción textual del circuito o diagrama necesario (si aplica). De lo contrario, null."
      }
    ],
    "material_permitido": "Calculadora científica, formulario personal de una hoja."
  }
}

Asegúrate de que TODAS las fórmulas usen sintaxis LaTeX correcta (encerradas en $...$ o $$...$$). Sé riguroso con los valores numéricos, unidades y notación científica.
""".strip()


# ── Extracción JSON ──────────────────────────────────────────────────────────────

def _find_balanced_json(text: str) -> str | None:
    """Encuentra el primer objeto JSON balanceado en el texto, respetando strings."""
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
    """Extrae el primer objeto JSON válido de la respuesta del modelo."""
    # 1. Intentar parsear directamente toda la respuesta
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 2. Buscar bloque ```json ... ``` y extraer todo su contenido
    match = re.search(r"```(?:json)?\s*(\{.*)\s*```", text, re.DOTALL)
    if match:
        candidate = _find_balanced_json(match.group(1))
        if candidate:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    # 3. Buscar el primer objeto JSON balanceado en todo el texto
    candidate = _find_balanced_json(text)
    if candidate:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise ValueError("No se pudo extraer un JSON válido de la respuesta del modelo.")


# ── Pipelines LLM ────────────────────────────────────────────────────────────────

def generar_con_nuevo_sdk(
    tema: str,
    nivel: str,
    modelo: str,
    system_instruction: str,
    api_key: str,
) -> tuple[str, dict]:
    client = genai.Client(api_key=api_key)
    prompt = (
        f"Genera un examen de Electrónica de nivel {nivel} "
        f"sobre el siguiente tema:\n\n{tema}\n\n"
        "El examen debe tener exactamente 5 preguntas de razonamiento y cálculo "
        "en el formato JSON especificado."
    )
    response = client.models.generate_content(
        model=modelo,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7,
            max_output_tokens=8192,
            response_mime_type="application/json",
        ),
    )
    tokens = {}
    try:
        tokens = {
            "prompt": response.usage_metadata.prompt_token_count,
            "respuesta": response.usage_metadata.candidates_token_count,
            "total": response.usage_metadata.total_token_count,
        }
    except (AttributeError, TypeError):
        pass
    return response.text, tokens


def generar_con_sdk_legacy(
    tema: str,
    nivel: str,
    modelo: str,
    system_instruction: str,
    api_key: str,
) -> tuple[str, dict]:
    import warnings
    warnings.filterwarnings("ignore")
    _genai_legacy.configure(api_key=api_key)
    model = _genai_legacy.GenerativeModel(
        model_name=modelo,
        system_instruction=system_instruction,
        generation_config=_genai_legacy_types.GenerationConfig(
            temperature=0.7,
            top_p=0.95,
            max_output_tokens=8192,
            response_mime_type="application/json",
        ),
    )
    prompt = (
        f"Genera un examen de Electrónica de nivel {nivel} "
        f"sobre el siguiente tema:\n\n{tema}\n\n"
        "El examen debe tener exactamente 5 preguntas de razonamiento y cálculo "
        "en el formato JSON especificado."
    )
    response = model.generate_content(prompt)
    tokens = {}
    try:
        tokens = {
            "prompt": response.usage_metadata.prompt_token_count,
            "respuesta": response.usage_metadata.candidates_token_count,
            "total": response.usage_metadata.total_token_count,
        }
    except (AttributeError, TypeError):
        pass
    return response.text, tokens


def generar_con_groq(
    tema: str, nivel: str, modelo: str, system_instruction: str, api_key: str
) -> tuple[str, dict]:
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("SDK de OpenAI no instalado. (pip install openai)")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )
    prompt = (
        f"Genera un examen de Electrónica de nivel {nivel} "
        f"sobre el siguiente tema:\n\n{tema}\n\n"
        "El examen debe tener exactamente 5 preguntas de razonamiento y cálculo "
        "en el formato JSON especificado."
    )
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": prompt},
    ]

    try:
        response = client.chat.completions.create(
            model=modelo,
            messages=messages,
            temperature=0.7,
            max_tokens=8192,
            response_format={"type": "json_object"},
        )
        response_text = response.choices[0].message.content
        tokens = {}
        if response.usage:
            tokens = {
                "prompt": response.usage.prompt_tokens,
                "respuesta": response.usage.completion_tokens,
                "total": response.usage.total_tokens,
            }
        return response_text, tokens
    except Exception as e:
        raise RuntimeError(f"Error de API (Groq): {str(e)}")


def generar_con_openrouter(
    tema: str,
    nivel: str,
    modelo: str,
    system_instruction: str,
    api_key: str,
) -> tuple[str, dict]:
    prompt = (
        f"Genera un examen de Electrónica de nivel {nivel} "
        f"sobre el siguiente tema:\n\n{tema}\n\n"
        "El examen debe tener exactamente 5 preguntas de razonamiento y cálculo "
        "en el formato JSON especificado."
    )
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": prompt},
    ]
    return openrouter_chat(
        messages,
        modelo,
        api_key,
        temperature=0.7,
        max_tokens=8192,
        title="ELECTRONICA - Elaboracion de Examenes",
    )


# ── Orquestador principal ────────────────────────────────────────────────────────

def elaborar_examen(
    tema: str,
    nivel: str,
    modelo: str,
    api_key: str,
    api_backend: str = "gemini",
) -> dict:
    max_retries = 3
    last_error = None
    
    for attempt in range(max_retries):
        try:
            if api_backend == "openrouter":
                response_text, tokens = generar_con_openrouter(
                    tema, nivel, modelo, SYSTEM_INSTRUCTION, api_key
                )
            elif api_backend == "groq":
                response_text, tokens = generar_con_groq(
                    tema, nivel, modelo, SYSTEM_INSTRUCTION, api_key
                )
            elif _GENAI_SDK == "new":
                response_text, tokens = generar_con_nuevo_sdk(
                    tema, nivel, modelo, SYSTEM_INSTRUCTION, api_key
                )
            else:
                response_text, tokens = generar_con_sdk_legacy(
                    tema, nivel, modelo, SYSTEM_INSTRUCTION, api_key
                )

            examen_dict = extract_json_from_response(response_text)

            if "examen" not in examen_dict:
                raise ValueError(
                    "La respuesta del modelo no contiene el campo 'examen'."
                )
            
            # Exit loop if successful
            break

        except ValueError as e:
            last_error = e
            if attempt < max_retries - 1:
                print(f"Advertencia: {e} Reintentando (intento {attempt+2}/{max_retries})...", file=sys.stderr)
                continue
            else:
                os.makedirs(".tmp", exist_ok=True)
                with open(".tmp/last_failed_response.txt", "w", encoding="utf-8") as f:
                    f.write(response_text)
                raise ValueError(f"{e} (Revisa .tmp/last_failed_response.txt para ver el texto truncado/inválido generado por el LLM)")

    # Validar que haya exactamente 5 preguntas (o al menos advertir)
    preguntas = examen_dict.get("examen", {}).get("preguntas", [])
    if len(preguntas) != 5:
        warnings.warn(
            f"El modelo generó {len(preguntas)} preguntas en lugar de 5. "
            "Verifica la instrucción al modelo."
        )

    result = {
        "status": "ok",
        "api_backend": api_backend,
        "tema": tema,
        "modelo": modelo,
        "nivel": nivel,
        "examen": examen_dict.get("examen", examen_dict),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if tokens:
        result["tokens_usados"] = tokens

    return result


# ── CLI ──────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Genera un examen de 5 preguntas de razonamiento y cálculo sobre un tema de Electrónica.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 execution/elaborar_examen.py --tema "Semana 4: Condensadores y circuitos RC"
  python3 execution/elaborar_examen.py --tema "Transistor BJT" --nivel avanzada
  python3 execution/elaborar_examen.py --tema "Amplificadores Operacionales" --api-backend openrouter
        """,
    )
    parser.add_argument(
        "--tema", required=True,
        help="Tema del plan de estudios sobre el que generar el examen.",
    )
    parser.add_argument(
        "--nivel", default="intermedia",
        choices=["basica", "intermedia", "avanzada"],
        help="Nivel de dificultad del examen (default: intermedia).",
    )
    parser.add_argument(
        "--modelo",
        default="anthropic/claude-opus-5",
        help="Modelo a usar (default: anthropic/claude-opus-5 para tareas complejas).",
    )
    parser.add_argument(
        "--api-backend",
        default="openrouter",
        choices=["gemini", "openrouter", "groq"],
        help="Backend de API: gemini, openrouter o groq. (default: openrouter).",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.api_backend in ["openrouter", "groq"]:
        if not _OPENROUTER_AVAILABLE:
            print(json.dumps({
                "status": "error", "code": 1,
                "message": "SDK de OpenAI no instalado. Ejecuta: pip install openai"
            }))
            sys.exit(1)
    elif args.api_backend == "gemini":
        if not _GEMINI_AVAILABLE:
            print(json.dumps({
                "status": "error", "code": 1,
                "message": "SDK de Gemini no instalado. Ejecuta: pip install google-genai"
            }))
            sys.exit(1)

    if args.api_backend == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        key_name = "OPENROUTER_API_KEY"
    elif args.api_backend == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            try:
                with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".groq_api_key"), "r") as f:
                    api_key = f.read().strip()
            except Exception:
                pass
        key_name = "GROQ_API_KEY"
    else:
        api_key = os.getenv("GOOGLE_API_KEY")
        key_name = "GOOGLE_API_KEY"

    if not api_key:
        print(json.dumps({
            "status": "error", "code": 2,
            "message": f"API key no encontrada. Define {key_name} en tu archivo .env o como variable de entorno."
        }))
        sys.exit(2)

    try:
        result = elaborar_examen(
            tema=args.tema,
            nivel=args.nivel,
            modelo=args.modelo,
            api_key=api_key,
            api_backend=args.api_backend,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    except ValueError as e:
        print(json.dumps({"status": "error", "code": 4, "message": str(e)}))
        sys.exit(4)

    except RuntimeError as e:
        print(json.dumps({"status": "error", "code": 3, "message": str(e)}))
        sys.exit(3)

    except Exception as e:
        error_type = type(e).__name__
        print(json.dumps({
            "status": "error", "code": 2,
            "message": f"Error de API ({error_type}): {str(e)}"
        }))
        sys.exit(2)


if __name__ == "__main__":
    main()
