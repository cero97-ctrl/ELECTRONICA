"""Cliente JSON-RPC de Solana (vía httpx, sin SDK de Solana).

Uso en el servicio: confirmar que un pago USDC al destino llegó y está
FINALIZADO en cadena (commitment=finalized, parámetro de la directiva).
"""
from __future__ import annotations

import time
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import Settings


class RpcError(RuntimeError):
    pass


def _call(rpc_url: str, method: str, params: list[Any]) -> dict[str, Any]:
    """POST JSON-RPC. Retorna el objeto 'result' o lanza RpcError."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    with httpx.Client(timeout=15) as client:
        resp = client.post(rpc_url, json=payload)
        resp.raise_for_status()
        body = resp.json()
    if "error" in body:
        raise RpcError(f"RPC {method}: {body['error']}")
    return body.get("result")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    retry=retry_if_exception_type((httpx.HTTPError, RpcError)),
)
def get_signature_status(rpc_url: str, signature: str) -> Optional[dict[str, Any]]:
    """Estado de la firma con commitment=finalized (directiva: confirmación RPC)."""
    result = _call(
        rpc_url,
        "getSignatureStatuses",
        [[signature], {"commitment": "finalized"}],
    )
    if not result or not result.get("value"):
        return None
    return result["value"][0]  # puede ser None si no existe


def is_finalized_ok(rpc_url: str, signature: str) -> bool:
    """True si la transacción existe, está finalizada y sin errores."""
    status = get_signature_status(rpc_url, signature)
    if status is None:
        return False
    # Solana RPC: confirmations None (no `maxSupportedTransactionVersion`) => finalized
    if status.get("confirmationStatus") != "finalized":
        return False
    if status.get("err") is not None:
        return False
    return True


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.5, max=3),
    retry=retry_if_exception_type((httpx.HTTPError, RpcError)),
)
def get_transaction(rpc_url: str, signature: str) -> Optional[dict[str, Any]]:
    """Transacción en formato jsonParsed (para revisar balances previos/posteriores)."""
    result = _call(
        rpc_url,
        "getTransaction",
        [signature, {"commitment": "finalized", "encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
    )
    return result


def payment_received(
    tx: dict[str, Any], destination: str, required_base: int, token_mint: str
) -> bool:
    """¿El destinatario recibió >= required_base del token en esta TX?

    Compara preTokenBalances/postTokenBalances de la cuenta de token de
    `destination` (método robusto que no depende de parsear instrucciones).
    """
    meta = (tx or {}).get("meta") or {}
    pre = {a.get("accountIndex"): a for a in meta.get("preTokenBalances") or []}
    post = {a.get("accountIndex"): a for a in meta.get("postTokenBalances") or []}

    for idx, after in post.items():
        if after.get("mint") != token_mint:
            continue
        if (after.get("owner") or "").lower() != destination.lower():
            continue
        before = pre.get(idx) or {}
        delta = _ui_amount(after) - _ui_amount(before)
        if delta >= required_base:
            return True
    return False


def _ui_amount(entry: Optional[dict]) -> int:
    if not entry or not entry.get("uiTokenAmount"):
        return 0
    amt = entry["uiTokenAmount"]
    return int(amt.get("amount", 0) or 0)


def await_payment(
    settings: Settings,
    signature: str,
    destination: str,
    required_base: int,
    token_mint: str,
    max_wait_seconds: int = 30,
) -> bool:
    """Verificación final: finalized + pago correcto al destino.

    Retorna True solo si la TX está finalized y el monto llegó al destino.
    """
    deadline = time.time() + max_wait_seconds
    while time.time() < deadline:
        if not is_finalized_ok(settings.rpc_url, signature):
            time.sleep(2)
            continue
        tx = get_transaction(settings.rpc_url, signature)
        if payment_received(tx, destination, required_base, token_mint):
            return True
        return False  # finalizada pero sin el pago esperado
    return False
