"""TF-IDF based embedding function for Chroma.

A network-free fallback when ``sentence-transformers`` cannot reach
HuggingFace.  It implements the Chroma 0.5+ protocol:

* ``name()`` — identifier used by Chroma to detect embedder conflicts
* ``embed_query(input)`` — embed a single query string
* ``embed_documents(input)`` — embed a list of documents
* ``__call__(input)`` — legacy protocol (also accepted)
"""

from __future__ import annotations

import threading
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


class TfidfEmbeddingFunction:
    """Chroma-compatible embedding function backed by TF-IDF + cosine."""

    def __init__(self) -> None:
        self._vec = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 4),
            min_df=1,
            max_features=20000,
        )
        self._fitted = False
        self._lock = threading.Lock()

    def _ensure_fit(self, seed_docs: list[str]) -> None:
        if self._fitted:
            return
        with self._lock:
            if self._fitted:
                return
            if not seed_docs:
                seed_docs = ["placeholder"]
            self._vec.fit(seed_docs)
            self._fitted = True

    def _transform(self, docs: list[str]) -> list[list[float]]:
        self._ensure_fit(docs if len(docs) > 1 else docs + ["placeholder"])
        matrix = self._vec.transform(docs)
        dense = matrix.toarray().astype(np.float32)
        return [row.tolist() for row in dense]

    # -- Chroma 0.5+ protocol ----------------------------------------------
    def name(self) -> str:
        return "tfidf-charngram"

    def embed_query(self, input: str) -> list[float]:  # noqa: A002
        return self._transform([input])[0]

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        return self._transform(list(input))

    # -- Legacy / fallback ------------------------------------------------
    def __call__(self, input: Any) -> list[list[float]]:  # noqa: A002
        if isinstance(input, str):
            return [self._transform([input])[0]]
        return self._transform([str(x) for x in input])
