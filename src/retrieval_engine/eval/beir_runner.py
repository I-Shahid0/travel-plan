from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np
from beir.datasets.data_loader import GenericDataLoader
from beir.util import download_and_unzip

from retrieval_engine.config import settings
from retrieval_engine.eval.metrics import aggregate_metrics
from retrieval_engine.query_understanding import apply_query_understanding
from retrieval_engine.query_understanding.expand import merge_variant_rankings
from retrieval_engine.retrieval.embeddings import embed_texts
from retrieval_engine.retrieval.fusion import rrf_merge
from retrieval_engine.retrieval.rerank import rerank_ids
from retrieval_engine.retrieval.sparse import bm25_search

logger = logging.getLogger(__name__)

BEIR_URLS = {
    "scifact": "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip",
}


def _beir_document(doc: dict[str, str]) -> str:
    title = doc.get("title") or ""
    text = doc.get("text") or ""
    return f"{title} {text}".strip()


def _rank_by_cosine(
    query_vec: np.ndarray, doc_matrix: np.ndarray, doc_ids: list[str], top_k: int
) -> list[str]:
    scores = doc_matrix @ query_vec
    order = np.argsort(-scores)[:top_k]
    return [doc_ids[i] for i in order]


def _latency_stats(latencies_ms: list[float]) -> dict[str, float]:
    if not latencies_ms:
        return {"mean_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0}
    arr = np.array(latencies_ms, dtype=np.float64)
    return {
        "mean_ms": float(arr.mean()),
        "p50_ms": float(np.percentile(arr, 50)),
        "p95_ms": float(np.percentile(arr, 95)),
    }


def _llm_cost_summary(prepared_list: list) -> dict[str, float]:
    if not prepared_list:
        return {"usd_per_query": 0.0, "tokens_per_query": 0.0}
    total_tokens = sum(p.total_tokens for p in prepared_list)
    total_usd = sum(sum(u.cost_usd() for u in p.usage) for p in prepared_list)
    n = len(prepared_list)
    return {
        "usd_per_query": total_usd / n,
        "tokens_per_query": total_tokens / n,
    }


def run_beir_eval(
    *,
    dataset: str | None = None,
    k: int | None = None,
    data_root: Path | None = None,
    technique: str | None = None,
) -> dict[str, float | dict]:
    dataset = dataset or settings.beir_dataset
    k = k or settings.eval_k
    candidate_k = max(k, settings.hybrid_candidate_k)
    data_root = data_root or Path("data/beir")
    technique = technique or settings.query_technique

    if dataset not in BEIR_URLS:
        raise ValueError(f"Unsupported BEIR dataset: {dataset}")

    data_path = data_root / dataset
    if not data_path.exists():
        logger.info("Downloading BEIR dataset: %s", dataset)
        download_and_unzip(BEIR_URLS[dataset], str(data_root))

    corpus, queries, qrels = GenericDataLoader(data_path).load(split="test")
    doc_ids = list(corpus.keys())
    doc_texts = [_beir_document(corpus[doc_id]) for doc_id in doc_ids]

    logger.info("Encoding %d BEIR documents …", len(doc_texts))
    doc_vectors = np.array(embed_texts(doc_texts), dtype=np.float32)

    ranked_lists: list[list[str]] = []
    rel_lists: list[dict[str, float]] = []
    latencies_ms: list[float] = []
    prepared_list = []

    query_items = [(qid, text) for qid, text in queries.items() if qid in qrels]
    logger.info(
        "Running hybrid retrieval on %d BEIR queries (technique=%s) …",
        len(query_items),
        technique,
    )

    for i, (query_id, query_text) in enumerate(query_items, start=1):
        start = time.perf_counter()
        prepared = apply_query_understanding(query_text, technique=technique)
        prepared_list.append(prepared)

        if prepared.query_variants:
            variant_lists = []
            for variant in prepared.query_variants:
                query_vec = np.array(embed_texts([variant])[0], dtype=np.float32)
                dense_ids = _rank_by_cosine(query_vec, doc_vectors, doc_ids, top_k=candidate_k)
                sparse_ids = bm25_search(variant, doc_ids, doc_texts, top_k=candidate_k)
                variant_lists.append(rrf_merge(dense_ids, sparse_ids, k=settings.rrf_k))
            merged = merge_variant_rankings(variant_lists, rrf_k=settings.rrf_k)
        else:
            dense_text = prepared.hyde_text or prepared.semantic_query
            query_vec = np.array(embed_texts([dense_text])[0], dtype=np.float32)
            dense_ids = _rank_by_cosine(query_vec, doc_vectors, doc_ids, top_k=candidate_k)
            sparse_query = query_text if prepared.hyde_text else prepared.semantic_query
            sparse_ids = bm25_search(sparse_query, doc_ids, doc_texts, top_k=candidate_k)
            merged = rrf_merge(dense_ids, sparse_ids, k=settings.rrf_k)

        id_to_text = dict(zip(doc_ids, doc_texts, strict=True))
        ranked, _ = rerank_ids(query_text, merged, id_to_text, limit=k)
        ranked_lists.append(ranked)
        rel_lists.append({doc_id: float(score) for doc_id, score in qrels[query_id].items()})
        latencies_ms.append((time.perf_counter() - start) * 1000)

        if i % 100 == 0:
            logger.info("BEIR progress: %d / %d queries", i, len(query_items))

    metrics = aggregate_metrics(ranked_lists, rel_lists, k=k)
    metrics["queries"] = float(len(query_items))
    metrics["latency"] = _latency_stats(latencies_ms)
    metrics["llm_cost"] = _llm_cost_summary(prepared_list)
    logger.info("BEIR %s results: %s", dataset, metrics)
    return metrics
