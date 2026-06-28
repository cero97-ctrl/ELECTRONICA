#!/usr/bin/env python3
"""
evaluar_examen.py — Evaluación preliminar de exámenes con LLM multimodal (Layer 3: Execution)

Lee un PDF de examen de estudiante, renderiza cada página como imagen de alta resolución
en memoria y se las envía en bloque a un modelo multimodal (Gemini o OpenRouter) para una
evaluación académica estructurada.

Uso:
    python3 execution/evaluar_examen.py --pdf examenes/01/examen_estudiantes/Ana_Alcala.pdf
    python3 execution/evaluar_examen.py --pdf <ruta> [--modelo gemini-2.5-flash] [--dpi 250] [--rubrica <ruta_yaml>]

Salida (stdout, JSON):
    {
      "estudiante": "...",
      "archivo": "...",
      "modelo": "...",
      "paginas_procesadas": N,
      "evaluacion": {
        "puntaje_sugerido": "X.X/10",
        "nivel_desempeno": "...",
        "resumen_general": "...",
        "fortalezas": [...],
        "areas_de_mejora": [...],
        "observaciones_por_pregunta": [...],
        "errores_conceptuales": [...],
        "errores_procedimentales": [...],
        "recomendaciones_al_estudiante": "...",
        "nota_para_el_profesor": "..."
      },
      "tokens_usados": {...},
      "timestamp": "..."
    }

Códigos de salida:
    0 — Evaluación completada exitosamente
    1 — Argumento inválido o archivo no encontrado
    2 — Error de API (autenticación, límite de tasa, etc.)
    3 — Error al procesar el PDF (corrupto, sin páginas, etc.)
    4 — Respuesta del modelo no parseable como JSON
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# ── Dependencias externas ──────────────────────────────────────────────────────
try:
    import fitz  # PyMuPDF
except ImportError:
    print(json.dumps({
        "status": "error", "code": 1,
        "message": "PyMuPDF no instalado. Ejecuta: pip install pymupdf"
    }))
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # .env opcional si la variable ya está en el entorno

# ── SDKs de LLMs (importación según backend) ────────────────────────────────────
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


# ── System Instruction ─────────────────────────────────────────────────────────

SYSTEM_INSTRUCTION = """
Eres un asistente académico especializado en la corrección de exámenes de **Electrónica** a nivel universitario.
Tu función es realizar una evaluación preliminar rigurosa, objetiva y pedagógicamente útil de la respuesta escrita de un estudiante.

## Tu perfil
- Tienes dominio profundo de Electrónica: análisis de circuitos (CC y CA), dispositivos semiconductores (diodos, transistores, amplificadores operacionales), electrónica digital y analógica, leyes de Kirchhoff, teoremas de redes, respuesta en frecuencia y diseño básico de circuitos.
- Comprendes el nivel de formación esperado en estudiantes de Ingeniería Electrónica, Ingeniería Eléctrica o carreras afines.
- Tu evaluación es una **observación preliminar** que apoya al profesor humano, no una calificación definitiva.

## Tu tarea
Se te entregará un conjunto de imágenes correspondientes a las páginas de un examen escrito. Debes:

1. **Identificar cada pregunta o ítem** que aparezca en el examen.
2. **Evaluar la respuesta de cada pregunta** considerando:
   - Corrección conceptual: ¿el estudiante comprendió el principio de funcionamiento del circuito o dispositivo?
   - Corrección procedimental: ¿el análisis matemático/lógico es correcto?
   - Claridad y organización: ¿la respuesta es legible y coherente?
   - Manejo de unidades: ¿las unidades son correctas y consistentes?
   - Uso de fórmulas: ¿son apropiadas y bien aplicadas?
3. **Detectar errores conceptuales** (malentendidos de teoría de circuitos, comportamiento de componentes, polarización, etc.).
4. **Detectar errores procedimentales** (cálculos incorrectos, pasos omitidos, errores de álgebra).
5. **Estimar un puntaje sugerido** sobre 10 puntos (escala del 0 al 10, permitiendo decimales).
6. **Redactar observaciones** útiles para el estudiante (formativas) y notas para el profesor.

## Reglas de evaluación
- Sé riguroso pero justo. Penaliza los errores conceptuales más que los procedimentales menores.
- Si una respuesta está parcialmente correcta, reconócelo explícitamente.
- Si una pregunta está en blanco o ilegible, indícalo.
- No inventes contenido: evalúa solo lo que está escrito en las imágenes.
- Si detectas que el examen tiene una estructura de puntaje visible (ej: "Pregunta 1: 20 pts" o "Pregunta 1: 2 pts"), úsala como referencia para ponderar, pero el puntaje total final sugerido debe ser escalado a base 10 puntos (ej. 8.5/10).

## Formato de respuesta
Debes responder ÚNICAMENTE con un objeto JSON válido, sin texto adicional antes ni después, con exactamente esta estructura:

```json
{
  "puntaje_sugerido": "X.X/10",
  "nivel_desempeno": "Excelente | Bueno | Suficiente | Deficiente | Insuficiente",
  "resumen_general": "Párrafo breve describiendo el desempeño global del estudiante.",
  "fortalezas": [
    "Descripción de fortaleza 1",
    "Descripción de fortaleza 2"
  ],
  "areas_de_mejora": [
    "Descripción de área de mejora 1"
  ],
  "observaciones_por_pregunta": [
    {
      "pregunta": "Pregunta 1 (o descripción del ítem)",
      "puntaje_parcial": "X.X/2.0 (o el peso correspondiente de la pregunta en base a 10)",
      "evaluacion": "Descripción detallada de la evaluación de esta pregunta.",
      "errores": ["error específico 1", "error específico 2"]
    }
  ],
  "errores_conceptuales": [
    "Descripción del error conceptual 1"
  ],
  "errores_procedimentales": [
    "Descripción del error procedimental 1"
  ],
  "recomendaciones_al_estudiante": "Párrafo con retroalimentación formativa directamente dirigida al estudiante.",
  "nota_para_el_profesor": "Observaciones especiales para el profesor: ambigüedades encontradas, respuestas dudosas, ítems que requieren revisión manual, etc."
}
```
""".strip()


# ── Funciones de renderizado PDF ───────────────────────────────────────────────

def pdf_to_images_bytes(pdf_path: str, dpi: int = 250) -> list[bytes]:
    """
    Renderiza cada página del PDF como PNG en memoria.
    Retorna lista de bytes PNG (una por página).
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        raise RuntimeError(f"No se pudo abrir el PDF '{pdf_path}': {e}")

    if len(doc) == 0:
        raise RuntimeError(f"El PDF '{pdf_path}' no contiene páginas.")

    zoom = dpi / 72.0  # 72 DPI es la resolución base de PDF
    mat = fitz.Matrix(zoom, zoom)
    images = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB, alpha=False)
        images.append(pix.tobytes("png"))

    doc.close()
    return images


# ── Funciones de extracción JSON ───────────────────────────────────────────────

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
    """
    Intenta extraer el JSON de la respuesta del modelo.
    Maneja casos donde el modelo envuelva el JSON en bloques de código markdown.
    """
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


# ── Pipeline con nuevo SDK (google-genai) ──────────────────────────────────────

def evaluar_con_nuevo_sdk(
    images_bytes: list[bytes],
    modelo: str,
    system_instruction: str,
    api_key: str,
) -> tuple[str, dict]:
    """Usa el SDK moderno google-genai."""
    client = genai.Client(api_key=api_key)

    # Construir contenidos multimodales
    contents = []
    for i, img_bytes in enumerate(images_bytes, start=1):
        contents.append(f"--- Página {i} de {len(images_bytes)} ---")
        contents.append(
            genai_types.Part.from_bytes(data=img_bytes, mime_type="image/png")
        )
    contents.append(
        "\nAnaliza el examen completo mostrado en las imágenes anteriores y responde con el JSON de evaluación."
    )

    response = client.models.generate_content(
        model=modelo,
        contents=contents,
        config=genai_types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2,
            max_output_tokens=8192,
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


# ── Pipeline con SDK legacy (google-generativeai) ──────────────────────────────

def evaluar_con_sdk_legacy(
    images_bytes: list[bytes],
    modelo: str,
    system_instruction: str,
    api_key: str,
) -> tuple[str, dict]:
    """Usa el SDK legacy google-generativeai como fallback."""
    import warnings
    warnings.filterwarnings("ignore")  # Suprimir FutureWarnings del SDK deprecated

    _genai_legacy.configure(api_key=api_key)

    model = _genai_legacy.GenerativeModel(
        model_name=modelo,
        system_instruction=system_instruction,
        generation_config=_genai_legacy_types.GenerationConfig(
            temperature=0.2,
            top_p=0.95,
            max_output_tokens=8192,
        ),
    )

    parts = []
    for i, img_bytes in enumerate(images_bytes, start=1):
        parts.append(f"--- Página {i} de {len(images_bytes)} ---")
        parts.append(_genai_legacy_types.Part.from_bytes(
            data=img_bytes, mime_type="image/png"
        ))
    parts.append(
        "\nAnaliza el examen completo mostrado en las imágenes anteriores y responde con el JSON de evaluación."
    )

    response = model.generate_content(parts)

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


# ── Pipeline con OpenRouter (API compatible con OpenAI) ─────────────────────────

def evaluar_con_openrouter(
    images_bytes: list[bytes],
    modelo: str,
    system_instruction: str,
    api_key: str,
) -> tuple[str, dict]:
    """Evalúa usando OpenRouter (API compatible con OpenAI)."""
    import base64

    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )

    user_content = []
    for i, img_bytes in enumerate(images_bytes, start=1):
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        user_content.append({
            "type": "text",
            "text": f"--- Página {i} de {len(images_bytes)} ---",
        })
        user_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{b64}",
                "detail": "high",
            },
        })
    user_content.append({
        "type": "text",
        "text": "Analiza el examen completo mostrado en las imágenes anteriores y responde con el JSON de evaluación.",
    })

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_content},
    ]

    response = client.chat.completions.create(
        model=modelo,
        messages=messages,
        temperature=0.2,
        max_tokens=8192,
        extra_headers={
            "HTTP-Referer": "https://github.com/cero/MEGA/VS_CODE_WORKSPACE/ELECTRONICA",
            "X-Title": "ELECTRONICA - Evaluacion de Examenes",
        },
    )

    tokens = {}
    try:
        if hasattr(response, 'usage') and response.usage:
            tokens = {
                "prompt": response.usage.prompt_tokens,
                "respuesta": response.usage.completion_tokens,
                "total": response.usage.total_tokens,
            }
    except (AttributeError, TypeError):
        pass

    if not response or not hasattr(response, 'choices') or not response.choices:
        raise RuntimeError(f"El modelo no devolvió una respuesta válida. Es probable que no soporte imágenes o esté caído en OpenRouter.")

    choice = response.choices[0]
    if not choice.message or choice.message.content is None:
        raise RuntimeError(f"El modelo devolvió un mensaje vacío. Verifica si el modelo '{modelo}' soporta multimodalidad (visión) en OpenRouter.")

    return choice.message.content, tokens


def evaluar_con_groq(
    images_bytes: list[bytes],
    modelo: str,
    system_instruction: str,
    api_key: str,
) -> tuple[str, dict]:
    """Evalúa usando Groq (API compatible con OpenAI)."""
    import base64
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )

    user_content = []
    for i, img_bytes in enumerate(images_bytes, start=1):
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        user_content.append({
            "type": "text",
            "text": f"--- Página {i} de {len(images_bytes)} ---",
        })
        user_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{b64}",
                "detail": "high",
            },
        })
    user_content.append({
        "type": "text",
        "text": "Analiza el examen completo mostrado en las imágenes anteriores y responde con el JSON de evaluación.",
    })

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_content},
    ]

    response = client.chat.completions.create(
        model=modelo,
        messages=messages,
        temperature=0.2,
        max_tokens=8192,
        response_format={"type": "json_object"},
    )

    tokens = {}
    try:
        if hasattr(response, 'usage') and response.usage:
            tokens = {
                "prompt": response.usage.prompt_tokens,
                "respuesta": response.usage.completion_tokens,
                "total": response.usage.total_tokens,
            }
    except (AttributeError, TypeError):
        pass

    if not response or not hasattr(response, 'choices') or not response.choices:
        raise RuntimeError(f"El modelo no devolvió una respuesta válida. Es probable que no soporte imágenes o esté caído en Groq.")

    choice = response.choices[0]
    if not choice.message or choice.message.content is None:
        raise RuntimeError(f"El modelo devolvió un mensaje vacío. Verifica si el modelo '{modelo}' soporta multimodalidad en Groq.")

    return choice.message.content, tokens


# ── Orquestador principal ──────────────────────────────────────────────────────

def evaluar_examen(
    pdf_path: str,
    modelo: str,
    dpi: int,
    rubrica_path: str | None,
    api_key: str,
    api_backend: str = "gemini",
) -> dict:
    """Orquesta el pipeline completo de evaluación."""

    # ── 1. Renderizar PDF ──────────────────────────────────────────────────────
    images_bytes = pdf_to_images_bytes(pdf_path, dpi=dpi)

    # ── 2. Construir System Instruction (con rúbrica opcional) ─────────────────
    system_instruction = SYSTEM_INSTRUCTION
    if rubrica_path:
        rubrica_path_obj = Path(rubrica_path)
        if not rubrica_path_obj.exists():
            raise FileNotFoundError(f"Rúbrica no encontrada: {rubrica_path}")
        rubrica_content = rubrica_path_obj.read_text(encoding="utf-8")
        system_instruction += f"\n\n## Rúbrica específica de este examen\n{rubrica_content}"

    # ── 3. Llamar al modelo según backend ──────────────────────────────────────
    if api_backend == "openrouter":
        response_text, tokens = evaluar_con_openrouter(
            images_bytes, modelo, system_instruction, api_key
        )
    elif api_backend == "groq":
        response_text, tokens = evaluar_con_groq(
            images_bytes, modelo, system_instruction, api_key
        )
    elif _GENAI_SDK == "new":
        response_text, tokens = evaluar_con_nuevo_sdk(
            images_bytes, modelo, system_instruction, api_key
        )
    else:
        response_text, tokens = evaluar_con_sdk_legacy(
            images_bytes, modelo, system_instruction, api_key
        )

    # ── 4. Extraer y validar JSON ──────────────────────────────────────────────
    evaluacion_dict = extract_json_from_response(response_text)

    # ── 5. Construir resultado final ───────────────────────────────────────────
    nombre_estudiante = (
        Path(pdf_path).stem
        .replace("evaluacion_", "")
        .replace("examen_", "")
        .replace("_", " ")
    )

    result = {
        "status": "ok",
        "api_backend": api_backend,
        "estudiante": nombre_estudiante,
        "archivo": str(Path(pdf_path).resolve()),
        "modelo": modelo,
        "dpi_renderizado": dpi,
        "paginas_procesadas": len(images_bytes),
        "evaluacion": evaluacion_dict,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    if tokens:
        result["tokens_usados"] = tokens

    return result


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Evalúa exámenes de Electrónica con LLM multimodal.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 execution/evaluar_examen.py --pdf examenes/01/examen_estudiantes/Ana_Alcala.pdf
  python3 execution/evaluar_examen.py --pdf <ruta> --modelo gemini-1.5-pro --dpi 300
  python3 execution/evaluar_examen.py --pdf <ruta> --api-backend openrouter --modelo qwen/qwen-2.5-vl-72b-instruct:free
        """,
    )
    parser.add_argument(
        "--pdf",
        required=True,
        help="Ruta al archivo PDF del examen del estudiante.",
    )
    parser.add_argument(
        "--modelo",
        default="gemini-2.5-flash",
        help="Modelo a usar (default: gemini-2.5-flash). Con --api-backend openrouter usa IDs de OpenRouter.",
    )
    parser.add_argument(
        "--api-backend",
        default="gemini",
        choices=["gemini", "openrouter", "groq"],
        help="Backend de API a usar: gemini, openrouter o groq. (default: gemini).",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=250,
        help="Resolución de renderizado del PDF en DPI (default: 250). Rango recomendado: 150-300.",
    )
    parser.add_argument(
        "--rubrica",
        default=None,
        help="(Opcional) Ruta a un archivo YAML o TXT con la rúbrica específica del examen.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # ── Validar PDF ────────────────────────────────────────────────────────────
    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(json.dumps({
            "status": "error", "code": 1,
            "message": f"PDF no encontrado: {args.pdf}"
        }))
        sys.exit(1)

    if pdf_path.suffix.lower() != ".pdf":
        print(json.dumps({
            "status": "error", "code": 1,
            "message": f"El archivo no es un PDF: {args.pdf}"
        }))
        sys.exit(1)

    # ── Validar DPI ────────────────────────────────────────────────────────────
    if not (72 <= args.dpi <= 600):
        print(json.dumps({
            "status": "error", "code": 1,
            "message": f"DPI fuera de rango. Usa un valor entre 72 y 600. Recibido: {args.dpi}"
        }))
        sys.exit(1)

    # ── Validar SDK según backend ──────────────────────────────────────────────
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

    # ── Obtener API Key según backend ──────────────────────────────────────────
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
            "message": (
                f"API key no encontrada. Define {key_name} "
                "en tu archivo .env o como variable de entorno."
            )
        }))
        sys.exit(2)

    # ── Ejecutar evaluación ────────────────────────────────────────────────────
    try:
        result = evaluar_examen(
            pdf_path=str(pdf_path),
            modelo=args.modelo,
            dpi=args.dpi,
            rubrica_path=args.rubrica,
            api_key=api_key,
            api_backend=args.api_backend,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    except FileNotFoundError as e:
        print(json.dumps({"status": "error", "code": 1, "message": str(e)}))
        sys.exit(1)

    except RuntimeError as e:
        print(json.dumps({"status": "error", "code": 3, "message": str(e)}))
        sys.exit(3)

    except ValueError as e:
        print(json.dumps({"status": "error", "code": 4, "message": str(e)}))
        sys.exit(4)

    except Exception as e:
        error_type = type(e).__name__
        print(json.dumps({
            "status": "error", "code": 2,
            "message": f"Error de API ({error_type}): {str(e)}"
        }))
        sys.exit(2)


if __name__ == "__main__":
    main()
