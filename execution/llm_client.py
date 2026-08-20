#!/usr/bin/env python3
"""
llm_client.py — Cliente único para consultas LLM vía OpenRouter (API compatible con OpenAI).

Centraliza la creación del cliente y las llamadas a https://openrouter.ai/api/v1 para
evitar la duplicación que había en execution/*.py. También construye mensajes
multimodales (texto + imágenes base64) de forma consistente.

Uso:
    from execution.llm_client import openrouter_chat, build_multimodal_content, get_openai_client, get_chat_openai

    # Texto simple
    content, tokens = openrouter_chat(
        [{"role": "system", "content": sys}, {"role": "user", "content": prompt}],
        model="anthropic/claude-opus-5",
        api_key=api_key,
        temperature=0.7,
        max_tokens=8192,
        title="ELECTRONICA - Tarea",
    )

    # Multimodal (imágenes base64)
    content, tokens = openrouter_chat(
        [
            {"role": "system", "content": sys},
            {"role": "user", "content": build_multimodal_content(images_bytes, labels, trailing_text=prompt)},
        ],
        model=modelo,
        api_key=api_key,
        temperature=0.2,
        max_tokens=8192,
    )

    # Cliente directo (LangChain)
    chat = get_chat_openai(api_key, model="google/gemini-3.7-flash", max_tokens=get_max_tokens())
"""

import base64
import os
from typing import Optional

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_APP_URL = "https://github.com/cero/MEGA/VS_CODE_WORKSPACE/ELECTRONICA"

MODEL_TIERS = {
    "flash":         "google/gemini-3.7-flash",  # Rutina: parsing/formatting, RAG, multimodal rápido
    "kimi":          "moonshotai/kimi-k3",       # Contexto masivo (>50k tok) / razonamiento intermedio
    "kimi_fallback": "deepseek/deepseek-v4-pro", # Sustituto de kimi ante 429 (razonamiento, 1M ctx)
    "opus":          "anthropic/claude-opus-5",  # Razonamiento crítico: diseño, cálculo formal, debugging
}


def load_api_key() -> str:
    """Carga OPENROUTER_API_KEY del entorno o del .env del proyecto."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        try:
            from dotenv import load_dotenv
            load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
            key = os.environ.get("OPENROUTER_API_KEY")
        except Exception:
            pass
    if not key:
        raise ValueError("No se encontró OPENROUTER_API_KEY en el .env o en el entorno.")
    return key


def get_max_tokens() -> int:
    """Presupuesto de salida configurable (OPENROUTER_MAX_TOKENS en .env/entorno)."""
    return int(os.environ.get("OPENROUTER_MAX_TOKENS", "2048"))


def get_openai_client(api_key: str):
    """Cliente OpenAI configurado para OpenRouter."""
    from openai import OpenAI
    return OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL)


def get_chat_openai(api_key: str, model: str, temperature: float = 0.1, max_tokens: int = 2048):
    """ChatOpenAI de LangChain configurado para OpenRouter (usa el patrón de agent_eda/rag_system)."""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        base_url=OPENROUTER_BASE_URL,
    )


def build_multimodal_content(
    images: list[bytes],
    labels: Optional[list[str]] = None,
    trailing_text: Optional[str] = None,
) -> list[dict]:
    """Construye el contenido 'user' multimodal (texto + imágenes base64 PNG).

    images: lista de bytes de las imágenes (PNG).
    labels: etiqueta por imagen (opcional). Default: "Imagen N".
    trailing_text: texto final tras las imágenes (opcional, p. ej. el prompt).
    """
    content: list[dict] = []
    for i, img_bytes in enumerate(images, start=1):
        label = labels[i - 1] if labels and i - 1 < len(labels) else f"Imagen {i}"
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        content.append({"type": "text", "text": f"--- {label} ---"})
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
        })
    if trailing_text:
        content.append({"type": "text", "text": trailing_text})
    return content


def openrouter_chat(
    messages: list[dict],
    model: str,
    api_key: str,
    *,
    temperature: float = 0.7,
    max_tokens: int = 8192,
    title: str = "ELECTRONICA",
    response_format: Optional[dict] = None,
) -> tuple[str, dict]:
    """Envía mensajes a OpenRouter y devuelve (contenido, tokens).

    messages: lista de {role, content}; content puede ser str o list multimodal
              (ver build_multimodal_content).
    """
    client = get_openai_client(api_key)
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "extra_headers": {
            "HTTP-Referer": _APP_URL,
            "X-Title": title,
        },
    }
    if response_format:
        kwargs["response_format"] = response_format

    response = client.chat.completions.create(**kwargs)

    tokens = {}
    try:
        if hasattr(response, "usage") and response.usage:
            tokens = {
                "prompt": response.usage.prompt_tokens,
                "respuesta": response.usage.completion_tokens,
                "total": response.usage.total_tokens,
            }
    except (AttributeError, TypeError):
        pass

    if not response or not hasattr(response, "choices") or not response.choices:
        raise RuntimeError(
            "El modelo no devolvió una respuesta válida. "
            "Es probable que no soporte imágenes o esté caído en OpenRouter."
        )
    choice = response.choices[0]
    if not choice.message or choice.message.content is None:
        raise RuntimeError(
            f"El modelo devolvió un mensaje vacío. "
            f"Verifica si el modelo '{model}' soporta multimodalidad (visión) en OpenRouter."
        )
    return choice.message.content, tokens