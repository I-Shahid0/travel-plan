from __future__ import annotations

import pytest

from retrieval_engine.resilience import (
    CircuitOpenError,
    CircuitState,
    get_breaker,
    reset_registry,
)
from retrieval_engine.resilience.breaker import CircuitBreaker


@pytest.fixture(autouse=True)
def clean_registry():
    reset_registry()
    yield
    reset_registry()


def make_breaker(**kwargs) -> CircuitBreaker:
    kwargs.setdefault("failure_threshold", 3)
    kwargs.setdefault("reset_timeout_sec", 60.0)
    return CircuitBreaker("test", **kwargs)


def test_starts_closed():
    breaker = make_breaker()
    assert breaker.state is CircuitState.CLOSED
    assert breaker.try_acquire()


def test_opens_after_threshold_failures():
    breaker = make_breaker(failure_threshold=3)
    for _ in range(2):
        breaker.record_failure()
    assert breaker.state is CircuitState.CLOSED

    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
    assert not breaker.try_acquire()


def test_success_resets_failure_count():
    breaker = make_breaker(failure_threshold=3)
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    assert breaker.failure_count == 0
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state is CircuitState.CLOSED


def test_half_open_probe_after_timeout(monkeypatch):
    clock = {"now": 100.0}
    monkeypatch.setattr("retrieval_engine.resilience.breaker.time.monotonic", lambda: clock["now"])

    breaker = make_breaker(failure_threshold=1, reset_timeout_sec=30.0)
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
    assert not breaker.try_acquire()

    clock["now"] += 31.0
    # First caller after timeout gets the single half-open probe.
    assert breaker.try_acquire()
    assert breaker.state is CircuitState.HALF_OPEN
    # Concurrent callers are rejected while the probe is in flight.
    assert not breaker.try_acquire()


def test_half_open_success_closes(monkeypatch):
    clock = {"now": 0.0}
    monkeypatch.setattr("retrieval_engine.resilience.breaker.time.monotonic", lambda: clock["now"])
    breaker = make_breaker(failure_threshold=1, reset_timeout_sec=10.0)
    breaker.record_failure()
    clock["now"] += 11.0
    assert breaker.try_acquire()
    breaker.record_success()
    assert breaker.state is CircuitState.CLOSED
    assert breaker.try_acquire()


def test_half_open_failure_reopens(monkeypatch):
    clock = {"now": 0.0}
    monkeypatch.setattr("retrieval_engine.resilience.breaker.time.monotonic", lambda: clock["now"])
    breaker = make_breaker(failure_threshold=1, reset_timeout_sec=10.0)
    breaker.record_failure()
    clock["now"] += 11.0
    assert breaker.try_acquire()
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
    # Open timer restarted — still rejected before another full timeout.
    clock["now"] += 5.0
    assert not breaker.try_acquire()
    clock["now"] += 6.0
    assert breaker.try_acquire()


def test_call_raises_circuit_open():
    breaker = make_breaker(failure_threshold=1)

    with pytest.raises(RuntimeError, match="boom"):
        breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert breaker.state is CircuitState.OPEN

    with pytest.raises(CircuitOpenError):
        breaker.call(lambda: "unreachable")


def test_ready_to_attempt_pauses_while_open(monkeypatch):
    clock = {"now": 0.0}
    monkeypatch.setattr("retrieval_engine.resilience.breaker.time.monotonic", lambda: clock["now"])
    breaker = make_breaker(failure_threshold=1, reset_timeout_sec=10.0)
    assert breaker.ready_to_attempt()
    breaker.record_failure()
    assert not breaker.ready_to_attempt()
    clock["now"] += 11.0
    assert breaker.ready_to_attempt()
    # Non-mutating: state must still be OPEN, not HALF_OPEN.
    assert breaker.state is CircuitState.OPEN


def test_force_open_and_reset():
    breaker = make_breaker()
    breaker.force_open()
    assert breaker.state is CircuitState.OPEN
    assert not breaker.try_acquire()
    breaker.record_success()  # must not close a forced-open circuit
    assert breaker.state is CircuitState.OPEN
    breaker.reset()
    assert breaker.state is CircuitState.CLOSED
    assert breaker.try_acquire()


def test_registry_returns_same_instance():
    a = get_breaker("reranker")
    b = get_breaker("reranker")
    assert a is b
    assert get_breaker("other") is not a
