from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from retrieval_engine.eval.tradeoff import build_tradeoff_chart


def test_build_tradeoff_chart(tmp_path: Path):
    records = [
        {
            "phase": 3,
            "beir_scifact": {"ndcg@10": 0.69},
            "yelp_implicit": {"ndcg@10": 0.16},
        },
        {
            "phase": 4,
            "technique": "rewrite",
            "beir_scifact": {"ndcg@10": 0.70, "recall@10": 0.81, "mrr": 0.66},
            "yelp_implicit": {"ndcg@10": 0.17, "recall@10": 0.21, "mrr": 0.15},
            "latency": {"mean_ms": 120.0, "p50_ms": 100.0, "p95_ms": 250.0},
            "llm_cost": {"usd_per_query": 0.0001, "tokens_per_query": 50.0},
        },
    ]
    out = tmp_path / "tradeoff-phase4.json"
    with patch("retrieval_engine.eval.tradeoff.settings") as mock_settings:
        mock_settings.results_dir = str(tmp_path)
        mock_settings.eval_k = 10
        chart = build_tradeoff_chart(records, output_path=out)

    assert chart["phase"] == 4
    assert len(chart["points"]) == 2
    assert out.exists()
    saved = json.loads(out.read_text())
    assert saved["baseline_reference"]["beir_ndcg@10"] == 0.69
