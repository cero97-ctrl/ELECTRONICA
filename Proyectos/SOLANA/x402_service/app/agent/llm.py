"""Agente de IA (Clase B de la matriz: sin dinero, reversible, verificación
parcial). Nivel 1: ejecutor supervisado — el resultado se genera aquí pero la
entrega/cobro final exige revisión humana.

Implementación ligera: llama a la API REST del proveedor (Groq/OpenRouter) con
httpx. Si no hay LLM_API_KEY configurada, devuelve una respuesta determinista
("mock") para desarrollo y tests — nunca falla por falta de key.
"""
from __future__ import annotations

import httpx

from ..config import Settings

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_SYSTEM = (
    "Eres un asistente de electrónica y blockchain Solana. Responde en español, "
    "técnico y conciso. Regla: NO inventas datos que no conozcas."
)


async def run_agent(prompt: str, settings: Settings, params: dict | None = None) -> tuple[str, str]:
    """Ejecuta la consulta. Retorna (resultado, modelo_efectivo)."""
    params = params or {}
    if not settings.llm_api_key:
        return (
            "[mock] Agente sin LLM_API_KEY. Prompt recibido: " + prompt,
            "mock",
        )

    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    payload = {
        "model": settings.llm_model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
    }
    if settings.llm_provider.lower() == "openrouter":
        url = "https://openrouter.ai/api/v1/chat/completions"
        payload["extra_headers"] = {"HTTP-Referer": "x402.solana.local"}
    else:
        url = _GROQ_URL

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"], settings.llm_model
