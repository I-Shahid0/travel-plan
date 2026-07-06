from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from beir.datasets.data_loader import GenericDataLoader
from beir.util import download_and_unzip

from retrieval_engine.config import settings
from retrieval_engine.eval.metrics import aggregate_metrics
from retrieval_engine.retrieval.embeddings import embed_texts
from retrieval_engine.retrieval.fusion import rrf_merge
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


def run_beir_eval(
    *,
    dataset: str | None = None,
    k: int | None = None,
    data_root: Path | None = None,
) -> dict[str, float]:
    dataset = dataset or settings.beir_dataset
    k = k or settings.eval_k
    candidate_k = max(k, settings.hybrid_candidate_k)
    data_root = data_root or Path("data/beir")

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

    query_items = [(qid, text) for qid, text in queries.items() if qid in qrels]
    logger.info("Running hybrid retrieval on %d BEIR queries …", len(query_items))

    for i, (query_id, query_text) in enumerate(query_items, start=1):
        query_vec = np.array(embed_texts([query_text])[0], dtype=np.float32)
        dense_ids = _rank_by_cosine(query_vec, doc_vectors, doc_ids, top_k=candidate_k)
        sparse_ids = bm25_search(query_text, doc_ids, doc_texts, top_k=candidate_k)
        ranked = rrf_merge(dense_ids, sparse_ids, k=settings.rrf_k)[:k]
        ranked_lists.append(ranked)
        rel_lists.append({doc_id: float(score) for doc_id, score in qrels[query_id].items()})

        if i % 100 == 0:
            logger.info("BEIR progress: %d / %d queries", i, len(query_items))

    metrics = aggregate_metrics(ranked_lists, rel_lists, k=k)
    logger.info("BEIR %s results: %s", dataset, metrics)
    return metrics
