"""Anti-replay de firmas: evita que un mismo pago se cobre varias veces.

Clase A (sin dinero, verificable) — Nivel 2. Almacenamiento por defecto en
memoria (TTL); si se configura REDIS_URL usa Redis. La directiva exige TTL 24h.
"""
from __future__ import annotations

import time
import uuid


class ReplayStore:
    """Interfaz mínima: `seen` y `mark_used`. Redis opcional."""

    def seen(self, key: str) -> bool:  # pragma: no cover
        raise NotImplementedError

    def mark_used(self, key: str, ttl_hours: float) -> None:  # pragma: no cover
        raise NotImplementedError


class MemoryReplayStore(ReplayStore):
    """Fallback sin dependencias. NUNCA para producción multi-proceso."""

    def __init__(self) -> None:
        self._seen: dict[str, float] = {}  # key -> expira (unix)

    def _purge(self) -> None:
        now = time.time()
        expired = [k for k, v in self._seen.items() if v < now]
        for k in expired:
            self._seen.pop(k, None)

    def seen(self, key: str) -> bool:
        self._purge()
        return key in self._seen

    def mark_used(self, key: str, ttl_hours: int) -> None:
        self._seen[key] = time.time() + ttl_hours * 3600


def make_replay_store(redis_url: str = "") -> ReplayStore:
    """Construye un store Redis si hay REDIS_URL; si no, memoria."""
    if redis_url:
        try:
            import redis  # type: ignore

            return _RedisReplayStore(redis.from_url(redis_url))
        except Exception:
            pass  # si Redis falla, caemos a memoria (sin dejar de operar)
    return MemoryReplayStore()


class _RedisReplayStore(ReplayStore):
    def __init__(self, client) -> None:
        self._r = client

    def seen(self, key: str) -> bool:
        return bool(self._r.exists(key))

    def mark_used(self, key: str, ttl_hours: int) -> None:
        self._r.set(key, "1", ex=ttl_hours * 3600)


def new_anti_replay_id() -> str:
    return str(uuid.uuid4())