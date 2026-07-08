from __future__ import annotations

import logging
from functools import lru_cache

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from transformers import AutoTokenizer

from retrieval_engine.config import settings
from retrieval_engine.retrieval.embeddings import prepare_gpu_runtime

logger = logging.getLogger(__name__)


def resolve_ort_providers() -> list[str]:
    """ONNX Runtime providers for reranker — mirrors embed GPU stack, not PyTorch."""
    requested = settings.reranker_device.lower()
    if requested == "cpu":
        logger.info("Using CPUExecutionProvider for reranker")
        return ["CPUExecutionProvider"]

    prepare_gpu_runtime()
    available = ort.get_available_providers()
    if "CUDAExecutionProvider" in available:
        logger.info("Using CUDAExecutionProvider for reranker")
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]

    if requested.startswith("cuda"):
        logger.warning("RERANKER_DEVICE=cuda but CUDAExecutionProvider unavailable — using CPU")
    return ["CPUExecutionProvider"]


@lru_cache(maxsize=1)
def _get_tokenizer() -> AutoTokenizer:
    return AutoTokenizer.from_pretrained(settings.reranker_onnx_model)


@lru_cache(maxsize=1)
def _get_session() -> ort.InferenceSession:
    model_path = hf_hub_download(
        repo_id=settings.reranker_onnx_model,
        filename="onnx/model.onnx",
    )
    providers = resolve_ort_providers()
    session = ort.InferenceSession(model_path, providers=providers)
    logger.info("ONNX reranker session ready — active providers: %s", session.get_providers())
    return session


def active_provider() -> str:
    return _get_session().get_providers()[0]


def score_pairs(query: str, texts: list[str], *, batch_size: int) -> list[float]:
    if not texts:
        return []

    session = _get_session()
    tokenizer = _get_tokenizer()
    input_names = {inp.name for inp in session.get_inputs()}
    scores: list[float] = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        pairs = [[query, text] for text in batch]
        encoded = tokenizer(
            pairs,
            return_tensors="np",
            truncation=True,
            padding=True,
            max_length=128,
        )
        inputs = {
            name: value.astype(np.int64) for name, value in encoded.items() if name in input_names
        }
        batch_scores = session.run(None, inputs)[0]
        scores.extend(float(score) for score in batch_scores.reshape(-1))

    return scores
