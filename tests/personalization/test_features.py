from __future__ import annotations

import numpy as np

from retrieval_engine.personalization.features import preference_from_history


def _cos(a: list[float], b: list[float]) -> float:
    va, vb = np.asarray(a), np.asarray(b)
    return float(va @ vb / (np.linalg.norm(va) * np.linalg.norm(vb)))


def test_empty_history_is_cold_start():
    assert preference_from_history([], [], []) is None


def test_single_interaction_points_at_its_embedding():
    pref = preference_from_history([[3.0, 0.0]], [5.0], [0.0])
    assert pref is not None
    assert _cos(pref, [1.0, 0.0]) > 0.999
    assert abs(np.linalg.norm(pref) - 1.0) < 1e-6


def test_higher_rating_dominates():
    pref = preference_from_history(
        [[1.0, 0.0], [0.0, 1.0]],
        [5.0, 1.0],
        [0.0, 0.0],
    )
    assert pref is not None
    assert _cos(pref, [1.0, 0.0]) > _cos(pref, [0.0, 1.0])


def test_recent_interaction_dominates_old_one():
    pref = preference_from_history(
        [[1.0, 0.0], [0.0, 1.0]],
        [5.0, 5.0],
        [0.0, 3650.0],
        half_life_days=365.0,
    )
    assert pref is not None
    assert _cos(pref, [1.0, 0.0]) > _cos(pref, [0.0, 1.0])


def test_missing_rating_uses_neutral_weight():
    pref = preference_from_history([[0.0, 2.0]], [None], [0.0])
    assert pref is not None
    assert _cos(pref, [0.0, 1.0]) > 0.999
