#!/usr/bin/env python3
"""
extraer_netlist_imagen.py — Extracción de netlist de imágenes con LLM multimodal (Layer 3: Execution)

Lee una o más imágenes (JPG/PNG) de circuitos desde el disco y las envía a un modelo multimodal
(Gemini o OpenRouter) para obtener un netlist estructurado en JSON.

Uso:
    python3 execution/extraer_netlist_imagen.py circuito.png

Salida (stdout, JSON):
    {
      "status": "ok",
      "api_backend": "gemini",
      "archivos_procesados": ["circuito.png"],
      "modelo": "gemini-2.5-flash",
      "analisis": {
        "components": [
          {"id": "R1", "type": "R", "value": "10k", "x": 100, "y": 100}
        ],
        "connections": [
          {"net_name": "Net_1", "pins": ["R1-1", "C1-1"]}
        ]
      },
      "tokens_usados": {...},
      "timestamp": "..."
    }

Códigos de salida:
    0 — Análisis completado exitosamente
    1 — Argumento inválido o archivo no encontrado
    2 — Error de API (autenticación, límite de tasa, etc.)
    4 — Respuesta del modelo no parseable como JSON
"""

import argparse
import base64
import glob
import json
import os
import re
import sys
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

# ── Dependencias externas ──────────────────────────────────────────────────────
try:
    from PIL import Image
except ImportError:
    print(json.dumps({
        "status": "error", "code": 1,
        "message": "Pillow no instalado. Ejecuta: pip install Pillow"
    }))
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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

try:
    from execution.llm_client import openrouter_chat, build_multimodal_content
except ImportError:
    from llm_client import openrouter_chat, build_multimodal_content


# ── Constantes ─────────────────────────────────────────────────────────────────

MAX_IMAGE_DIM = 2048  # px — lado más largo máximo para redimensionar


# ── Procesamiento de imágenes ──────────────────────────────────────────────────

def resolver_imagenes(patrones: list[str]) -> list[Path]:
    """Resuelve una lista de patrones glob/rutas a una lista de paths de imágenes."""
    rutas: list[Path] = []
    EXT_VALIDAS = {".jpg", ".jpeg", ".png"}

    for patron in patrones:
        expandidos = glob.glob(patron, recursive=False)
        if not expandidos:
            expandidos = [patron]
        for r in expandidos:
            p = Path(r)
            if p.suffix.lower() in EXT_VALIDAS:
                rutas.append(p)
            else:
                print(
                    f"  ⚠  Omitiendo '{p}' — extensión no soportada "
                    f"(solo: {', '.join(EXT_VALIDAS)})",
                    file=sys.stderr,
                )
    return sorted(set(rutas))


def imagen_a_bytes_png(ruta: Path, max_dim: int = MAX_IMAGE_DIM) -> bytes:
    """
    Abre una imagen, la redimensiona proporcionalmente si excede max_dim,
    y la convierte a PNG en memoria. Retorna los bytes PNG.
    """
    img = Image.open(ruta)
    img = img.convert("RGB")  # estandarizar a RGB

    # Redimensionar si es necesario
    w, h = img.size
    if w > max_dim or h > max_dim:
        escala = min(max_dim / w, max_dim / h)
        nuevo_w = int(w * escala)
        nuevo_h = int(h * escala)
        img = img.resize((nuevo_w, nuevo_h), Image.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── Extracción JSON ────────────────────────────────────────────────────────────

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


# ── System Instruction ─────────────────────────────────────────────────────────

SYSTEM_INSTRUCTION = """
Eres un asistente experto en ingeniería electrónica. Tu tarea es examinar la imagen de un circuito eléctrico
y extraer un Netlist estructurado con componentes, conexiones lógicas y coordenadas estimadas.

Debes responder ÚNICAMENTE con un objeto JSON válido, sin texto adicional, con exactamente esta estructura:

```json
{
  "components": [
    {
      "id": "R1",
      "type": "R",
      "value": "10k",
      "x": 100,
      "y": 100
    }
  ],
  "connections": [
    {
      "net_name": "Net_1",
      "pins": ["R1-1", "U1-2"]
    }
  ]
}
```

Reglas:
1. `type` debe ser estándar para KiCAD: "R" (Resistor), "C" (Capacitor), "D" (Diode), "Q_NPN_BCE" (Transistor), "Battery" (Batería), "GND" (Tierra), etc.
2. Las coordenadas (`x`, `y`) deben ser números enteros aproximados que representen la posición relativa del componente en la imagen, asumiendo una grilla donde el centro de la imagen está alrededor de x=100, y=100. Espacia los componentes adecuadamente (ej. de a 20 o 30 unidades).
3. Los pines en `connections` se nombran como `ID-NumeroDePin` (ej. `R1-1`, `R1-2`).
4. Identifica las tierras como componentes con ID "GND1", tipo "GND".
""".strip()


# ── Pipeline con nuevo SDK (google-genai) ──────────────────────────────────────

def analizar_con_nuevo_sdk(
    images_bytes: list[bytes],
    nombres: list[str],
    modelo: str,
    prompt: str,
    system_instruction: str,
    api_key: str,
) -> tuple[str, dict]:
    """Usa el SDK moderno google-genai."""
    client = genai.Client(api_key=api_key)

    contents = []
    for img_bytes, nombre in zip(images_bytes, nombres):
        contents.append(f"--- Imagen: {nombre} ---")
        contents.append(
            genai_types.Part.from_bytes(data=img_bytes, mime_type="image/png")
        )
    contents.append(f"\n{prompt}")

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

def analizar_con_sdk_legacy(
    images_bytes: list[bytes],
    nombres: list[str],
    modelo: str,
    prompt: str,
    system_instruction: str,
    api_key: str,
) -> tuple[str, dict]:
    """Usa el SDK legacy google-generativeai como fallback."""
    import warnings
    warnings.filterwarnings("ignore")

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
    for img_bytes, nombre in zip(images_bytes, nombres):
        parts.append(f"--- Imagen: {nombre} ---")
        parts.append(_genai_legacy_types.Part.from_bytes(
            data=img_bytes, mime_type="image/png"
        ))
    parts.append(f"\n{prompt}")

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

def analizar_con_openrouter(
    images_bytes: list[bytes],
    nombres: list[str],
    modelo: str,
    prompt: str,
    system_instruction: str,
    api_key: str,
) -> tuple[str, dict]:
    """Analiza usando OpenRouter (API compatible con OpenAI)."""
    user_content = build_multimodal_content(
        images_bytes,
        labels=nombres,
        trailing_text=prompt,
    )
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_content},
    ]
    return openrouter_chat(
        messages,
        modelo,
        api_key,
        temperature=0.2,
        max_tokens=8192,
        title="ELECTRONICA - Analisis de Imagenes",
    )


def analizar_con_groq(
    images_bytes: list[bytes],
    nombres: list[str],
    modelo: str,
    prompt: str,
    system_instruction: str,
    api_key: str,
) -> tuple[str, dict]:
    """Usa Groq (API compatible con OpenAI)."""
    import base64
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )

    user_content = []
    for img_bytes, nombre in zip(images_bytes, nombres):
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        user_content.append({
            "type": "text",
            "text": f"--- Imagen: {nombre} ---",
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
        "text": prompt,
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
        raise RuntimeError(
            "El modelo no devolvió una respuesta válida. "
            "Es probable que no soporte imágenes o esté caído en Groq."
        )

    choice = response.choices[0]
    if not choice.message or choice.message.content is None:
        raise RuntimeError(
            f"El modelo devolvió un mensaje vacío. "
            f"Verifica si el modelo '{modelo}' soporta multimodalidad (visión) en Groq."
        )

    return choice.message.content, tokens


# ── Orquestador principal ──────────────────────────────────────────────────────

def analizar_imagenes(
    rutas_imagenes: list[Path],
    modelo: str,
    prompt: str,
    api_key: str,
    api_backend: str = "gemini",
) -> dict:
    """Orquesta el pipeline completo de análisis de imágenes."""

    # 1. Leer y convertir imágenes a PNG en memoria
    nombres = []
    images_bytes = []
    for ruta in rutas_imagenes:
        if not ruta.exists():
            raise FileNotFoundError(f"Imagen no encontrada: {ruta}")
        nombres.append(ruta.name)
        images_bytes.append(imagen_a_bytes_png(ruta))

    if not images_bytes:
        raise RuntimeError("No se encontraron imágenes válidas para analizar.")

    # 2. Llamar al modelo según backend
    if api_backend == "openrouter":
        response_text, tokens = analizar_con_openrouter(
            images_bytes, nombres, modelo, prompt, SYSTEM_INSTRUCTION, api_key
        )
    elif api_backend == "groq":
        response_text, tokens = analizar_con_groq(
            images_bytes, nombres, modelo, prompt, SYSTEM_INSTRUCTION, api_key
        )
    elif _GENAI_SDK == "new":
        response_text, tokens = analizar_con_nuevo_sdk(
            images_bytes, nombres, modelo, prompt, SYSTEM_INSTRUCTION, api_key
        )
    else:
        response_text, tokens = analizar_con_sdk_legacy(
            images_bytes, nombres, modelo, prompt, SYSTEM_INSTRUCTION, api_key
        )

    # 3. Extraer y validar JSON
    analisis_dict = extract_json_from_response(response_text)

    # 4. Construir resultado final
    result = {
        "status": "ok",
        "api_backend": api_backend,
        "archivos_procesados": [str(r.resolve()) for r in rutas_imagenes],
        "modelo": modelo,
        "analisis": analisis_dict,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if tokens:
        result["tokens_usados"] = tokens

    return result


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Analiza imágenes con LLM multimodal.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 execution/analizar_imagen.py foto1.jpg,foto2.jpg
  python3 execution/analizar_imagen.py "*.jpg" --prompt "Describe este circuito"
  python3 execution/analizar_imagen.py esquema.png --modelo gemini-1.5-pro
  python3 execution/analizar_imagen.py "*.jpg" --api-backend openrouter
        """,
    )
    parser.add_argument(
        "imagenes",
        help=(
            "Ruta(s) a las imágenes separadas por coma, o un patrón glob "
            "(ej: '*.jpg', 'fotos/*.png')."
        ),
    )
    parser.add_argument(
        "--modelo",
        default="gemini-2.5-flash",
        help="Modelo multimodal a usar (default: gemini-2.5-flash).",
    )
    parser.add_argument(
        "--prompt",
        default="Describe detalladamente lo que ves en la(s) imagen(es).",
        help="Instrucción de análisis para el modelo.",
    )
    parser.add_argument(
        "--api-backend",
        default="gemini",
        choices=["gemini", "openrouter", "groq"],
        help="Backend de API: gemini, openrouter o groq. (default: gemini).",
    )
    parser.add_argument(
        "--max-dim",
        type=int,
        default=MAX_IMAGE_DIM,
        help=f"Lado más largo máximo en px para redimensionar (default: {MAX_IMAGE_DIM}).",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # ── Resolver imágenes ──────────────────────────────────────────────────────
    patrones = [p.strip() for p in args.imagenes.split(",")]
    rutas = resolver_imagenes(patrones)

    if not rutas:
        print(json.dumps({
            "status": "error", "code": 1,
            "message": (
                f"No se encontraron imágenes válidas con: {args.imagenes}. "
                "Extensiones soportadas: .jpg, .jpeg, .png"
            )
        }))
        sys.exit(1)

    for r in rutas:
        if not r.exists():
            print(json.dumps({
                "status": "error", "code": 1,
                "message": f"Imagen no encontrada: {r}"
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

    # ── Ejecutar análisis ──────────────────────────────────────────────────────
    try:
        result = analizar_imagenes(
            rutas_imagenes=rutas,
            modelo=args.modelo,
            prompt=args.prompt,
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
