"""Build the Chroma knowledge-base index. Run once after `git clone`."""

from __future__ import annotations

import sys

from atlas_mercator.rag.indexer import build_index


def main() -> int:
    n = build_index(force=True)
    print(f"✓ Indexed {n} chunks into Chroma")
    return 0


if __name__ == "__main__":
    sys.exit(main())
