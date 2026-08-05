"""Servicio x402 — punto de entrada FastAPI.

Flujo:
  GET/POST /v1/agent-task
    - sin pago          -> 402 (cabeceras de checkout)
    - con pago y firma  -> verificación + resultado del agente
    - firma inválida    -> 401
    - pago no verificado-> 402 (aún no finalizado) o 409 (replay)
  GET /health           -> estado del servicio

Guardarraíles de la directiva aplicados:
  - Anti-replay (TTL 24h)         -> replay_store
  - Confirmación RPC finalized    -> rpc.await_payment
  - Circuit breaker (>3 fallos)   -> circuit_breaker
  - Umbral humano y Nivel 1       -> el resultado sale con reviewed=False
"""
from __future__ import annotations

import time

from fastapi import FastAPI, Header, HTTPException, Response, status

from .agent.llm import run_agent
from .circuit_breaker import CircuitBreaker
from .config import Settings, get_settings
from .models import AgentTaskRequest, AgentTaskResponse, ErrorResponse, HealthResponse
from .paywall import canonical_message, new_checkout
from .replay_store import make_replay_store
from .rpc import await_payment
from .verify import verify_signature

settings = get_settings()
app = FastAPI(
    title="SOLANA x402 Agent Service",
    version="0.1.0",
    description="Servicio pay-per-use: el cliente paga USDC y el agente de IA responde.",
)
breaker = CircuitBreaker(max_failures=settings.circuit_breaker_max_failures)
replay = make_replay_store(settings.redis_url)

TASK_COUNTER = {"n": 0}


def _new_task_id() -> str:
    TASK_COUNTER["n"] += 1
    return f"x402-{int(time.time())}-{TASK_COUNTER['n']}"


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="degraded" if breaker.tripped else "ok",
        network=settings.network,
        pay_address=settings.pay_address,
        agent_level=settings.agent_level,
    )


@app.post(
    "/v1/agent-task",
    response_model=AgentTaskResponse,
    responses={
        402: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def agent_task(
    body: AgentTaskRequest,
    x_solana_signature: str | None = Header(default=None),
    x_solana_from: str | None = Header(default=None),
    x_solana_expires: str | None = Header(default=None),
) -> AgentTaskResponse | Response:
    if breaker.tripped:
        raise HTTPException(
            status_code=503,
            detail="Circuit breaker activo: cobros pausados, reintenta en unos minutos.",
        )

    # --- Paso 1: sin firma -> checkout (HTTP 402) --------------------------
    if not x_solana_signature or not x_solana_from or not x_solana_expires:
        checkout = new_checkout(settings)
        return Response(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            headers={
                **checkout.to_headers(),
                "Retry-After": str(settings.checkout_expiry_seconds),
            },
            content="Pago requerido: envía la firma X-Solana-* para completar.",
        )

    # --- Paso 2: con firma -> verificar todo -------------------------------
    try:
        expires = int(x_solana_expires)
    except ValueError:
        raise HTTPException(status_code=400, detail="X-Solana-Expires debe ser un unix ts")

    # 2a. Vigencia
    if expires < int(time.time()):
        raise HTTPException(status_code=402, detail="Checkout expirado: genera uno nuevo")

    # 2b. Anti-replay (clave = firma)
    replay_key = x_solana_signature
    if replay.seen(replay_key):
        raise HTTPException(
            status_code=409, detail="Firma ya procesada (anti-replay): no se re-cobra."
        )

    # 2c. Firma Ed25519 sobre el mensaje canónico
    checkout = new_checkout(settings)
    msg = canonical_message(checkout, x_solana_from)
    try:
        verify_signature(x_solana_from, msg, x_solana_signature)
    except Exception as exc:
        breaker.record_failure()
        raise HTTPException(status_code=401, detail=f"Firma inválida: {exc}")

    # 2d. Pago on-chain (finalized) con el monto esperado al destino
    try:
        paid = await await_payment(
            settings,
            signature=x_solana_signature,
            destination=settings.pay_address,
            required_base=checkout.amount_base,
            token_mint=checkout.token_mint,
        )
    except Exception as exc:
        breaker.record_failure()
        raise HTTPException(status_code=502, detail=f"RPC no disponible: {exc}")

    if not paid:
        breaker.record_failure()
        raise HTTPException(
            status_code=402,
            detail="Pago no verificado on-chain (finalized) al destino esperado.",
        )

    # 2e. Marcar la firma como usada SOLO tras pago verificado
    replay.mark_used(replay_key, ttl_hours=settings.replay_ttl_hours)
    breaker.record_success()

    # --- Paso 3: ejecutar el agente (Clase B, Nivel 1 supervisado) ---------
    result, model = await run_agent(body.prompt, settings, body.params)

    return AgentTaskResponse(
        task_id=_new_task_id(),
        prompt=body.prompt,
        result=result,
        model=model,
        paid_amount_usdc=settings.amount_usdc,
        signature=x_solana_signature,
        reviewed=False,  # Nivel 1: entrega final tras revisión humana
    )
