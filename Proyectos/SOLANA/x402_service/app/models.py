"""Modelos Pydantic del servicio x402.

Flujo (checkout + agente):
  1. El cliente pide /v1/agent-task sin pago -> 402 con cabeceras de pago.
  2. El cliente paga USDC on-chain y reintenta con las cabeceras X-Solana-*.
  3. El servicio verifica firma + pago on-chain y responde con el resultado.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class AgentTaskRequest(BaseModel):
    """Cuerpo de la consulta al agente (Clase B, Nivel 1 supervisado)."""

    prompt: str = Field(..., min_length=1, max_length=4000, description="Instrucción/consulta del cliente")
    params: dict = Field(default_factory=dict, description="Parámetros opcionales del agente")
    mode: Literal["chat", "analysis"] = "chat"


class AgentTaskResponse(BaseModel):
    """Respuesta final tras cobro y verificación exitosa."""

    task_id: str
    prompt: str
    result: str
    model: str
    paid_amount_usdc: float
    signature: str
    reviewed: bool = Field(
        default=False,
        description="Nivel 1: requiere revisión humana antes de la entrega final",
    )


class ErrorResponse(BaseModel):
    """Cuerpo de error uniforme."""

    error: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    network: str
    pay_address: str
    agent_level: int
