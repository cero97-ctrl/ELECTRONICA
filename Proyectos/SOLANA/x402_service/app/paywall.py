"""Paywall x402: construcción del checkout y cabeceras de la respuesta 402.

Protocolo seguido (x402 / HTTP 402 con pago en USDC en Solana):
  1. Respuesta 402 con cabeceras:
       X-Solana-Amount      -> monto en unidades base (USDC 1e6)
       X-Solana-Token       -> mint del token (USDC)
       X-Solana-Destination -> wallet destino del cobro
       X-Solana-Expires     -> unix ts límite para completar el pago
       X-Solana-Reason      -> motivo human-readable
  2. El cliente paga y reintenta la petición añadiendo:
       X-Solana-Signature   -> firma Ed25519 de la wallet sobre el mensaje canónico
       X-Solana-From        -> dirección pública de la wallet pagadora
       X-Solana-Expires     -> el mismo valor que se firmó
  3. El servicio verifica firma + pago on-chain (finalized) y anti-replay.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from .config import Settings


@dataclass(frozen=True)
class CheckoutRequest:
    """Lo que el cliente debe pagar y firmar."""

    amount_base: int      # unidades base (lamports de USDC)
    token_mint: str
    destination: str
    expires: int          # unix timestamp
    domain: str = "x402.solana.local"
    reason: str = "Pago por consulta al agente de IA (USDC)."

    def to_headers(self) -> dict[str, str]:
        return {
            "X-Solana-Amount": str(self.amount_base),
            "X-Solana-Token": self.token_mint,
            "X-Solana-Destination": self.destination,
            "X-Solana-Expires": str(self.expires),
            "X-Solana-Reason": self.reason,
        }


def amount_to_base(amount_usdc: float, decimals: int = 6) -> int:
    """Convierte USDC (float) a unidades base enteras."""
    return int(round(amount_usdc * (10**decimals)))


def new_checkout(settings: Settings) -> CheckoutRequest:
    """Genera un checkout nuevo basado en la configuración del servicio."""
    if not settings.pay_address:
        raise RuntimeError("SOLANA_WALLET_ADDRESS no configurada en .env")
    return CheckoutRequest(
        amount_base=amount_to_base(settings.amount_usdc, settings.usdc_decimals),
        token_mint=settings.usdc_mint,
        destination=settings.pay_address,
        expires=int(time.time()) + settings.checkout_expiry_seconds,
    )


def canonical_message(checkout: CheckoutRequest, from_address: str) -> str:
    """Mensaje canónico que la wallet firmará (lo firma el cliente).

    Orden estable; cualquier cambio aquí invalida las firmas anteriores.
    """
    return "\n".join(
        [
            checkout.domain,
            from_address,
            str(checkout.amount_base),
            checkout.token_mint,
            checkout.destination,
            str(checkout.expires),
        ]
    )
