"""Circuit breaker (directiva: >3 fallos consecutivos -> pausa + alerta).

Clase C: protege el cobro. Si el servicio encadena fallos (RPC caído, pagos
rechazados, errores 5xx), corta el flujo de cobros y expone `tripped`.
"""
from __future__ import annotations

import threading
import time


class CircuitBreaker:
    def __init__(self, max_failures: int = 3, cool_down_seconds: int = 300) -> None:
        self.max_failures = max_failures
        self.cool_down_seconds = cool_down_seconds
        self._failures = 0
        self._tripped_until = 0.0
        self._lock = threading.Lock()

    @property
    def tripped(self) -> bool:
        with self._lock:
            return time.time() < self._tripped_until

    def record_failure(self) -> None:
        """Cuenta un fallo; si supera el máximo, pausa la firma (el servicio)."""
        with self._lock:
            if time.time() >= self._tripped_until:
                self._failures += 1
                if self._failures >= self.max_failures:
                    self._tripped_until = time.time() + self.cool_down_seconds
                    self._failures = 0
            # si ya estaba tripped, no acumular más

    def record_success(self) -> None:
        with self._lock:
            if time.time() >= self._tripped_until:
                self._failures = 0

    def reset(self) -> None:
        with self._lock:
            self._failures = 0
            self._tripped_until = 0.0
