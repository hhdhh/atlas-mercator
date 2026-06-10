#!/usr/bin/env bash
# Launch the Atlas Mercator Gradio demo.
#
# Usage:
#   ./scripts/run_demo.sh                 # default localhost:7860
#   ATLAS_RAG_BACKEND=tfidf ./scripts/run_demo.sh
#
# Required:
#   - Python 3.11 venv at ./.venv
#   - ANTHROPIC_API_KEY (or ANTHROPIC_AUTH_TOKEN for a proxy) in env or .env
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -d ".venv" ]]; then
  echo "✗ No .venv found. Run: uv venv .venv --python 3.11 && uv pip install -e '.[dev]'"
  exit 1
fi

# Build the KB index on first run.
if [[ ! -d ".chroma" || -z "$(ls -A .chroma 2>/dev/null)" ]]; then
  echo "→ Building KB index..."
  .venv/bin/python scripts/build_kb_index.py
fi

echo "→ Launching Gradio demo on http://127.0.0.1:7860"
exec .venv/bin/python -m atlas_mercator.web.gradio_app
