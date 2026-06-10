"""Build the Chroma knowledge-base index from FAQ + policy docs.

Run via ``python -m scripts.build_kb_index`` (or via :func:`build_index`).
The index lives at ``.chroma/`` by default. Re-running wipes and rebuilds
the collection (idempotent).

Tries to use a real sentence-transformer embedding first; falls back to
a TF-IDF char-ngram embedder if the model cannot be loaded (e.g. offline).
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions

from atlas_mercator.config import get_settings


@dataclass
class KBChunk:
    id: str
    text: str
    source: str
    tags: list[str]


def _load_faq(path: Path) -> list[KBChunk]:
    if not path.exists():
        return []
    out: list[KBChunk] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            tags = obj.get("tags") or obj.get("tags_v2") or []
            if isinstance(tags, str):
                tags = [tags]
            out.append(
                KBChunk(
                    id=obj["id"],
                    text=obj["text"],
                    source=obj.get("source", "faq"),
                    tags=tags,
                )
            )
    return out


def _load_policies(dir_path: Path) -> list[KBChunk]:
    if not dir_path.exists():
        return []
    out: list[KBChunk] = []
    for md in sorted(dir_path.glob("*.md")):
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
            out.append(
                KBChunk(
                    id=f"policy-{md.stem}-{j}",
                    text=chunk,
                    source=md.name,
                    tags=["policy"],
                )
            )
    return out


def _try_sentence_transformer(name: str) -> Callable | None:
    """Return a Chroma-compatible embedding fn, or None on failure."""
    try:
        return embedding_functions.SentenceTransformerEmbeddingFunction(model_name=name)
    except Exception as exc:  # pragma: no cover - depends on network/cache
        print(f"  ! sentence-transformers unavailable ({exc}); using TF-IDF fallback")
        return None


def _tfidf_embedder() -> Callable:
    from atlas_mercator.rag.tfidf_embedder import TfidfEmbeddingFunction

    return TfidfEmbeddingFunction()


def build_index(force: bool = False) -> int:
    """Build (or rebuild) the Chroma KB index. Returns the number of chunks."""
    settings = get_settings()
    data_dir = settings.data_dir
    chroma_dir = settings.chroma_dir

    if force and chroma_dir.exists():
        shutil.rmtree(chroma_dir, ignore_errors=True)
    chroma_dir.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
    )

    collection_name = "atlas_kb"
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    embed_fn: Callable | None
    if settings.rag_backend == "tfidf":
        embed_fn = _tfidf_embedder()
    elif settings.rag_backend == "sentence-transformers":
        embed_fn = _try_sentence_transformer(settings.embed_model)
    else:  # auto
        embed_fn = _try_sentence_transformer(settings.embed_model) or _tfidf_embedder()
    coll = client.create_collection(
        name=collection_name,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )

    chunks = _load_faq(data_dir / "faq_kb.jsonl") + _load_policies(data_dir / "policy_docs")
    if not chunks:
        return 0

    coll.add(
        ids=[c.id for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=[{"source": c.source, "tags": ",".join(c.tags)} for c in chunks],
    )
    return len(chunks)


def main() -> int:
    n = build_index(force=True)
    print(f"✓ Indexed {n} chunks into Chroma")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
