"""Pruebas del flujo 402 sin tocar la red (tests deterministas).

Para ejecutar (desde Proyectos/SOLANA):
    python -m pytest x402_service/tests -v
o sin pytest:
    python3 x402_service/tests/test_paywall.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import nacl.signing  # noqa: E402

from app.config import Settings, get_settings  # noqa: E402
from app.paywall import (  # noqa: E402
    CheckoutRequest,
    amount_to_base,
    canonical_message,
    new_checkout,
)
from app.replay_store import MemoryReplayStore, new_anti_replay_id  # noqa: E402
from app.verify import (  # noqa: E402
    b58decode,
    b58encode,
    verify_signature,
)


def _test_settings() -> Settings:
    # wallet de destino arbitraria (base58), no se toca red en estos tests
    s = Settings(pay_address="11111111111111111111111111111111")
    return s


def test_amount_to_base():
    assert amount_to_base(0.05, 6) == 50000
    assert amount_to_base(1.0, 6) == 1_000_000


def test_checkout_tiene_cabeceras():
    c = new_checkout(_test_settings())
    h = c.to_headers()
    assert h["X-Solana-Amount"] == "50000"
    assert h["X-Solana-Destination"] == "11111111111111111111111111111111"
    assert "X-Solana-Expires" in h


def test_base58_roundtrip():
    data = b"\x00\x01\x02abc\xff"
    assert b58decode(b58encode(data)) == data
    # firma de 64 bytes válida
    assert len(b58decode(b58encode(b"\x11" * 64))) == 64


def test_verify_firma_valida_y_rechaza():
    signing_key = nacl.signing.SigningKey.generate()
    pub = signing_key.verify_key.encode()
    from_addr = b58encode(pub)
    checkout = _checkout(_test_settings())
    msg = canonical_message(checkout, from_addr)
    sig = signing_key.sign(msg.encode("utf-8")).signature

    verify_signature(from_addr, msg, b58encode(sig))  # no debe lanzar

    # firma manipulada debe fallar
    bad = sig[:-1] + bytes([sig[-1] ^ 0xFF])
    try:
        verify_signature(from_addr, msg, b58encode(bad))
        raise AssertionError("firma manipulada no debe pasar")
    except Exception:
        pass


def test_memory_replay_mark_seen():
    store = MemoryReplayStore()
    key = new_anti_replay_id()
    assert not store.seen(key)
    store.mark_used(key, ttl_hours=24)
    assert store.seen(key)


def test_circuit_breaker_triggers():
    from app.circuit_breaker import CircuitBreaker

    cb = CircuitBreaker(max_failures=3, cool_down_seconds=999)
    cb.record_failure(); cb.record_failure()
    assert not cb.tripped
    cb.record_failure()
    assert cb.tripped


def _checkout(_: object = None) -> CheckoutRequest:
    return CheckoutRequest(
        amount_base=50000,
        token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        destination="11111111111111111111111111111111",
        expires=int(time.time()) + 300,
    )


def _main() -> int:
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for fn in fns:
        try:
            fn()
            print(f"  ok  {fn.__name__}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"FAIL  {fn.__name__}: {e!r}")
    print(f"\n{len(fns) - failures}/{len(fns)} pasaron")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_main())