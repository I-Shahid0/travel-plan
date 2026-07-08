from __future__ import annotations

from enum import StrEnum

CORPUS_GROUP = "retrieval.example.com"
CORPUS_VERSION = "v1alpha1"
CORPUS_PLURAL = "corpora"


class CorpusPhase(StrEnum):
    PENDING = "Pending"
    INDEXING = "Indexing"
    READY = "Ready"
    FAILED = "Failed"
