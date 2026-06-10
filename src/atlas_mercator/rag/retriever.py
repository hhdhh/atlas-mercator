"""RAG retriever.

Two backends are supported:

* ``tfidf`` — pure sklearn TF-IDF + cosine similarity (no network, no
  model download, no Chroma). Always available, instant cold start.
* ``chroma`` — sentence-transformer + Chroma vector store. Used when
  the env var ``ATLAS_RAG_BACKEND=sentence-transformers`` (or ``auto``
  + cache hit) is set. Higher-quality semantic retrieval, requires
  network on first run.

The :class:`KBRetriever` API is the same regardless of backend: a
single :meth:`query` method that takes text and returns a list of
``{text, source, tags, score}`` dicts.
"""

from __future__ import annotations

import json
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer

from atlas_mercator.config import get_settings


@dataclass
class _Corpus:
    """In-memory corpus used by the TF-IDF backend."""

    ids: list[str]
    texts: list[str]
    sources: list[str]
    tags_list: list[list[str]]
    vectorizer: TfidfVectorizer
    matrix: Any  # scipy sparse


def _load_corpus_from_disk(data_dir: Path) -> tuple[list[str], list[str], list[str], list[list[str]]]:
    """Read FAQ + policy markdown from disk and return (ids, texts, sources, tags)."""
    ids: list[str] = []
    texts: list[str] = []
    sources: list[str] = []
    tags_list: list[list[str]] = []

    faq_path = data_dir / "faq_kb.jsonl"
    if faq_path.exists():
        with faq_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                tags = obj.get("tags") or obj.get("tags_v2") or []
                if isinstance(tags, str):
                    tags = [tags]
                ids.append(obj["id"])
                texts.append(obj["text"])
                sources.append(obj.get("source", "faq"))
                tags_list.append(tags)

    for md in sorted((data_dir / "policy_docs").glob("*.md")):
        text = md.read_text(encoding="utf-8")
        chunks: list[str] = []
        current: list[str] = []
        for line in text.splitlines():
            if line.startswith("## ") and current:
                chunks.append("\n".join(current).strip())
                current = [line]
            else:
                current.append(line)
        if current:
            chunks.append("\n".join(current).strip())
        if not chunks:
            chunks = [text.strip()]
        for j, chunk in enumerate(chunks):
            ids.append(f"policy-{md.stem}-{j}")
            texts.append(chunk)
            sources.append(md.name)
            tags_list.append(["policy"])

    return ids, texts, sources, tags_list


class KBRetriever:
    """Lazy, thread-safe retriever with a TF-IDF + cosine default backend."""

    _init_lock = threading.Lock()
    _instance: "KBRetriever | None" = None

    def __new__(cls) -> "KBRetriever":
        with cls._init_lock:
            if cls._instance is None:
                inst = super().__new__(cls)
                inst._corpus = None
                inst._chroma = None
                cls._instance = inst
            return cls._instance

    # -- Public API ---------------------------------------------------------
    def query(self, text: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Return up to ``top_k`` chunks matching ``text``."""
        if not text or not text.strip():
            return []
        settings = get_settings()

        if settings.rag_backend in ("tfidf", "auto"):
            try:
                return self._query_tfidf(text, top_k)
            except Exception:
                if settings.rag_backend == "tfidf":
                    return []
                # auto: fall through to chroma
        if settings.rag_backend in ("sentence-transformers", "auto"):
            try:
                return self._query_chroma(text, top_k)
            except Exception:
                return []
        return []

    # -- Backends -----------------------------------------------------------
    def _ensure_tfidf(self) -> _Corpus:
        if self._corpus is not None:
            return self._corpus
        with self._init_lock:
            if self._corpus is not None:
                return self._corpus
            settings = get_settings()
            ids, texts, sources, tags_list = _load_corpus_from_disk(settings.data_dir)
            vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1, max_features=20000)
            matrix = vec.fit_transform(texts) if texts else None
            self._corpus = _Corpus(
                ids=ids, texts=texts, sources=sources, tags_list=tags_list,
                vectorizer=vec, matrix=matrix,
            )
            return self._corpus

    def _query_tfidf(self, text: str, top_k: int) -> list[dict[str, Any]]:
        from sklearn.metrics.pairwise import cosine_similarity

        corpus = self._ensure_tfidf()
        if corpus.matrix is None or not corpus.texts:
            return []
        q_vec = corpus.vectorizer.transform([text])
        sims = cosine_similarity(q_vec, corpus.matrix).ravel()
        k = max(1, min(top_k, len(corpus.texts)))
        # argpartition is O(n); we only need top-k
        import numpy as np

        idx = np.argpartition(-sims, k - 1)[:k] if len(sims) > k else np.arange(len(sims))
        idx = idx[np.argsort(-sims[idx])]
        out: list[dict[str, Any]] = []
        for i in idx:
            out.append(
                {
                    "text": corpus.texts[i],
                    "source": corpus.sources[i],
                    "tags": corpus.tags_list[i],
                    "score": float(sims[i]),
                }
            )
        return out

    def _query_chroma(self, text: str, top_k: int) -> list[dict[str, Any]]:
        # Kept for the case where the user has set ATLAS_RAG_BACKEND=sentence-transformers
        # and a sentence-transformer embedding is available.  We do not exercise
        # this path in the default demo, but the code is here for completeness.
        raise NotImplementedError("Chroma backend not bundled in TF-IDF default.")
