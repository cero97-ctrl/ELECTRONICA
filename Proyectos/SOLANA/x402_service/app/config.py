"""Configuración del servicio x402.

Carga Proyectos/SOLANA/.env sin dependencias externas (sin python-dotenv).
Los valores se leen desde el entorno si ya están definidos; el .env solo
completa lo que falta. Nunca se registran secretos en logs.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Ruta del .env del proyecto SOLANA (dos niveles arriba de este módulo).
_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


def _load_dotenv(path: Path = _ENV_PATH) -> None:
    """Carga KEY=VALUE de un archivo .env a os.environ (solo claves ausentes)."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    """Parámetros del servicio. Calibrados a la matriz de delegación x402."""

    # --- Red / pagos -----------------------------------------------------
    network: str = field(
        default_factory=lambda: os.getenv("SOLANA_NETWORK", "devnet")
    )
    rpc_url: str = field(
        default_factory=lambda: os.getenv(
            "SOLANA_RPC_URL", "https://api.devnet.solana.com"
        )
    )
    # Wallet destino del pago (debe estar en .env). Por seguridad en devnet.
    pay_address: str = field(
        default_factory=lambda: os.getenv("SOLANA_WALLET_ADDRESS", "")
    )

    # --- Monetización (params de la directiva) ---------------------------
    amount_usdc: float = 0.05          # cobro por consulta (USDC)
    usdc_mint: str = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC mainnet
    usdc_decimals: int = 6
    checkout_expiry_seconds: int = 300  # 5 min para completar el pago

    # --- Anti-replay / circuit breaker -----------------------------------
    replay_ttl_hours: int = 24
    circuit_breaker_max_failures: int = 3

    # --- Nivel de delegación del agente -----------------------------------
    # Clase B (sin dinero, reversible, verificación parcial) -> Nivel 1:
    # el resultado se genera aquí y la entrega/cobro final requiere revisión.
    agent_level: int = 1

    # --- LLM del agente (opcional; si no hay API key, responde "mock") ----
    llm_provider: str = field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "groq")
    )
    llm_api_key: str = field(
        default_factory=lambda: os.getenv("LLM_API_KEY", "")
    )
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "qwen/qwen3.6-27b"))

    # --- Redis opcional ----------------------------------------------------
    redis_url: str = field(
        default_factory=lambda: os.getenv("REDIS_URL", "")
    )


def get_settings() -> Settings:
    _load_dotenv()
    return Settings()
