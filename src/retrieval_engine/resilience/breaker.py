"""Hand-rolled circuit breaker.

State machine (dev plan Phase 6 — implemented by hand to own the mechanics):

    CLOSED --[failure_threshold consecutive failures]--> OPEN
    OPEN   --[reset_timeout elapsed, next acquire]-----> HALF_OPEN (single probe)
    HALF_OPEN --[probe succeeds]--> CLOSED
    HALF_OPEN --[probe fails]-----> OPEN (timer restarts)

The breaker deliberately does not own fallback logic — callers decide what a
degraded response looks like (that's the point of app-level breakers over
service-mesh outlier detection).
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from enum import StrEnum
from typing import Any, TypeVar

from retrieval_engine.config import settings
from retrieval_engine.metrics import record_breaker_state, record_breaker_transition

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Circuit '{name}' is open")
        self.breaker_name = name


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int | None = None,
        reset_timeout_sec: float | None = None,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold or settings.breaker_failure_threshold
        self.reset_timeout_sec = reset_timeout_sec or settings.breaker_reset_timeout_sec
        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at = 0.0
        self._forced_open = False
        record_breaker_state(name, self._state.value)

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._state

    @property
    def failure_count(self) -> int:
        with self._lock:
            return self._failure_count

    def _transition(self, new_state: CircuitState) -> None:
        """Must be called with the lock held."""
        if new_state is self._state:
            return
        logger.warning("Circuit '%s': %s -> %s", self.name, self._state.value, new_state.value)
        self._state = new_state
        record_breaker_state(self.name, new_state.value)
        record_breaker_transition(self.name, new_state.value)

    def try_acquire(self) -> bool:
        """Request permission to call the dependency.

        OPEN past the reset timeout transitions to HALF_OPEN and admits exactly
        one probe; further callers are rejected until the probe resolves via
        record_success/record_failure.
        """
        with self._lock:
            if self._forced_open:
                return False
            if self._state is CircuitState.CLOSED:
                return True
            if self._state is CircuitState.OPEN:
                if time.monotonic() - self._opened_at >= self.reset_timeout_sec:
                    self._transition(CircuitState.HALF_OPEN)
                    return True
                return False
            # HALF_OPEN: a probe is already in flight
            return False

    def ready_to_attempt(self) -> bool:
        """Non-mutating check for pull-based consumers (e.g. the queue worker).

        False only while the circuit is open and the reset timeout has not
        elapsed — the caller should pause consumption instead of failing work.
        """
        with self._lock:
            if self._forced_open:
                return False
            if self._state is CircuitState.OPEN:
                return time.monotonic() - self._opened_at >= self.reset_timeout_sec
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            if not self._forced_open:
                self._transition(CircuitState.CLOSED)

    def record_failure(self) -> None:
        with self._lock:
            if self._forced_open:
                return
            if self._state is not CircuitState.CLOSED:
                # Failed probe (or failure while open): restart the open timer.
                self._opened_at = time.monotonic()
                self._transition(CircuitState.OPEN)
                return
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._opened_at = time.monotonic()
                self._transition(CircuitState.OPEN)

    def call(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run fn through the breaker; raises CircuitOpenError when rejected."""
        if not self.try_acquire():
            raise CircuitOpenError(self.name)
        try:
            result = fn(*args, **kwargs)
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result

    def force_open(self) -> None:
        """Pin the circuit open (eval/testing) until reset() is called."""
        with self._lock:
            self._forced_open = True
            self._opened_at = time.monotonic()
            self._transition(CircuitState.OPEN)

    def reset(self) -> None:
        with self._lock:
            self._forced_open = False
            self._failure_count = 0
            self._transition(CircuitState.CLOSED)


_registry: dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()


def get_breaker(
    name: str,
    *,
    failure_threshold: int | None = None,
    reset_timeout_sec: float | None = None,
) -> CircuitBreaker:
    """Return the process-wide breaker for name, creating it on first use."""
    with _registry_lock:
        if name not in _registry:
            _registry[name] = CircuitBreaker(
                name,
                failure_threshold=failure_threshold,
                reset_timeout_sec=reset_timeout_sec,
            )
        return _registry[name]


def reset_registry() -> None:
    """Drop all breakers (test isolation)."""
    with _registry_lock:
        _registry.clear()
