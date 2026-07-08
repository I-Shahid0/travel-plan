from __future__ import annotations

import logging
import site
import sys
from typing import TYPE_CHECKING

import numpy as np
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from retrieval_engine.config import settings

if TYPE_CHECKING:
    from retrieval_engine.db.models import Listing

logger = logging.getLogger(__name__)

MAX_REVIEW_CHARS = 2_000
HNSW_INDEX_NAME = "ix_listings_embedding_hnsw"
_model = None


def _log(msg: str, *args) -> None:
    logger.info(msg, *args)
    sys.stdout.flush()


def _ensure_onnx_gpu_package() -> None:
    """Remove cpu-only onnxruntime when both cpu and gpu wheels are installed.

    Both packages expose the ``onnxruntime`` module; the cpu wheel shadows gpu
    and hides CUDAExecutionProvider.
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        version("onnxruntime-gpu")
    except PackageNotFoundError:
        return

    try:
        version("onnxruntime")
    except PackageNotFoundError:
        return

    _log("Removing conflicting onnxruntime (cpu) package — keeping onnxruntime-gpu")
    import subprocess

    subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", "onnxruntime"],
        check=False,
        capture_output=True,
    )


def _ensure_cuda_on_path() -> None:
    """Prepend CUDA toolkit + pip-shipped cuDNN/cuBLAS dirs to PATH."""
    import os
    from pathlib import Path

    if sys.platform != "win32":
        return

    prepend: list[str] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        if not path.is_dir():
            return
        resolved = str(path.resolve())
        if resolved not in seen:
            seen.add(resolved)
            prepend.append(resolved)

    cuda_path = os.environ.get("CUDA_PATH")
    if cuda_path:
        add(Path(cuda_path) / "bin")

    toolkit_root = Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA")
    if toolkit_root.is_dir():
        for version_dir in sorted(toolkit_root.iterdir(), reverse=True):
            add(version_dir / "bin")

    for site_dir in site.getsitepackages():
        nvidia_root = Path(site_dir) / "nvidia"
        if nvidia_root.is_dir():
            for pkg_dir in nvidia_root.iterdir():
                add(pkg_dir / "bin")

    if prepend:
        existing = os.environ.get("PATH", "").split(os.pathsep)
        os.environ["PATH"] = os.pathsep.join(prepend + [p for p in existing if p not in seen])


def resolve_onnx_providers() -> list[str]:
    """Pick ONNX Runtime providers based on config."""
    requested = settings.embedding_device.lower()

    if requested == "cpu":
        _log("Using CPUExecutionProvider for embeddings")
        return ["CPUExecutionProvider"]

    _ensure_onnx_gpu_package()
    _ensure_cuda_on_path()

    import onnxruntime as ort

    if "CUDAExecutionProvider" not in ort.get_available_providers():
        if requested.startswith("cuda"):
            raise RuntimeError(
                "EMBEDDING_DEVICE=cuda but CUDAExecutionProvider is unavailable. "
                "Run: uv sync --group gpu  (installs onnxruntime-gpu + nvidia-cudnn-cu12). "
                "Or set EMBEDDING_DEVICE=cpu."
            )
        _log("CUDA unavailable — using CPUExecutionProvider for embeddings")
        return ["CPUExecutionProvider"]

    _log("Using CUDAExecutionProvider for embeddings")
    return ["CUDAExecutionProvider", "CPUExecutionProvider"]


def prepare_gpu_runtime() -> None:
    """Call before any onnxruntime import when using CUDA."""
    _ensure_onnx_gpu_package()
    _ensure_cuda_on_path()


def get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        providers = resolve_onnx_providers()
        _log("Loading embedding model: %s …", settings.embedding_model)
        _model = TextEmbedding(
            model_name=settings.embedding_model,
            providers=providers,
        )
        active = _model.model.model.get_providers()
        if (
            settings.embedding_device.lower() in {"cuda", "auto"}
            and "CUDAExecutionProvider" not in active
        ):
            raise RuntimeError(
                f"CUDA was requested but active ONNX providers are {active}. "
                "Install cuDNN: uv pip install nvidia-cudnn-cu12, then re-run embed."
            )
        _log("Model ready — active providers: %s", active)
    return _model


def listing_document(listing: Listing) -> str:
    parts: list[str] = [listing.title or ""]
    if listing.categories:
        parts.append(" ".join(listing.categories))
    if listing.description:
        parts.append(listing.description)
    if listing.review_text:
        parts.append(listing.review_text[:MAX_REVIEW_CHARS])
    return " ".join(part for part in parts if part).strip()


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return vectors / norms


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = get_model()
    prepared = [text.strip() or " " for text in texts]
    vectors = np.array(
        list(model.embed(prepared, batch_size=settings.embedding_batch_size)),
        dtype=np.float32,
    )
    vectors = _l2_normalize(vectors)
    return vectors.tolist()


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]


def ensure_hnsw_index(session: Session) -> None:
    exists = session.execute(
        text("SELECT 1 FROM pg_indexes WHERE indexname = :name"),
        {"name": HNSW_INDEX_NAME},
    ).scalar_one_or_none()
    if exists:
        logger.info("HNSW index %s already exists", HNSW_INDEX_NAME)
        return

    logger.info("Creating HNSW index on listings.embedding …")
    session.execute(
        text(
            f"""
            CREATE INDEX {HNSW_INDEX_NAME}
            ON listings USING hnsw (embedding vector_cosine_ops)
            """
        )
    )
    session.commit()
    logger.info("HNSW index created")


def embed_listings(
    session: Session,
    *,
    batch_size: int | None = None,
    skip_existing: bool = True,
    create_index: bool = True,
) -> dict[str, int]:
    from retrieval_engine.db.models import Listing

    batch_size = batch_size or settings.embedding_batch_size

    if skip_existing:
        pending = session.execute(
            select(func.count()).select_from(Listing).where(Listing.embedding.is_(None))
        ).scalar_one()
    else:
        pending = session.execute(select(func.count()).select_from(Listing)).scalar_one()

    if skip_existing and pending == 0:
        total_with = session.execute(
            select(func.count()).select_from(Listing).where(Listing.embedding.isnot(None))
        ).scalar_one()
        logger.info("All listings already have embeddings")
        if create_index:
            ensure_hnsw_index(session)
        return {"embedded": 0, "total_with_embeddings": total_with}

    total = pending
    _log("Embedding %d listings (batch_size=%d)", total, batch_size)
    _log("Pre-loading model …")
    get_model()

    embedded = 0
    batch_num = 0
    last_id: str | None = None

    while True:
        stmt = select(Listing).order_by(Listing.id)
        if skip_existing:
            stmt = stmt.where(Listing.embedding.is_(None))
        if last_id is not None:
            stmt = stmt.where(Listing.id > last_id)
        stmt = stmt.limit(batch_size)

        rows = session.execute(stmt).scalars().all()
        if not rows:
            break

        texts = [listing_document(row) or row.title for row in rows]
        vectors = embed_texts(texts)

        for row, vector in zip(rows, vectors, strict=True):
            row.embedding = vector

        session.commit()
        embedded += len(rows)
        batch_num += 1
        last_id = rows[-1].id

        if batch_num == 1 or batch_num % 5 == 0 or embedded >= total:
            _log("Embedded %d / %d listings", embedded, total)

    if create_index:
        ensure_hnsw_index(session)

    total_with = session.execute(
        select(func.count()).select_from(Listing).where(Listing.embedding.isnot(None))
    ).scalar_one()
    return {"embedded": embedded, "total_with_embeddings": total_with}
