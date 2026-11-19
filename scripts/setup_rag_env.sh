#!/usr/bin/env bash
# Create the separate Python environment for the RAG experiments: FlashRAG with vLLM.
# vLLM and FlashRAG need transformers<5 (so huggingface-hub<1), which clashes with the main
# project (src/corpus.py needs huggingface-hub>=2.4); they live in .venv-rag instead.
#
# Usage:
#   bash scripts/setup_rag_env.sh local     # RTX 5080 laptop (driver CUDA 12.8): run models in FP8
#   bash scripts/setup_rag_env.sh cluster   # cluster GPUs
# Then:
#   .venv-rag/bin/python <script>
#
# Versions follow the vLLM environments validated in mmore-lorin (benchmark/medqa/scripts).
set -euo pipefail

TARGET="${1:-local}"
case "$TARGET" in
    local)   PYTHON_VERSION="3.11"; VLLM_VERSION="0.11.0"; TRANSFORMERS_SPEC="transformers>=4.55.2,<5" ;;
    cluster) PYTHON_VERSION="3.12"; VLLM_VERSION="0.19.1"; TRANSFORMERS_SPEC="transformers>=4.57,<5" ;;
    *) echo "usage: $0 local|cluster"; exit 1 ;;
esac

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_DIR="$REPO_ROOT/.venv-rag"
# The PyPI release (flashrag-dev 0.1.2) dates from 2024: take GitHub main, pinned.
FLASHRAG_SPEC="flashrag-dev @ git+https://github.com/RUC-NLPIR/FlashRAG@7926ac3c3c5ce0781f53d60ebac48fc511abed12"

command -v uv >/dev/null || { echo "uv is required: https://docs.astral.sh/uv/"; exit 1; }

# (re)create the env unless it already runs the right Python version
if ! "$ENV_DIR/bin/python" -c "import sys; sys.exit(sys.version_info[:2] != tuple(map(int, '$PYTHON_VERSION'.split('.'))))" 2>/dev/null; then
    uv venv --clear --managed-python --python "$PYTHON_VERSION" "$ENV_DIR"
fi

# sentence-transformers (dense indexes) for transformers 4 needs huggingface-hub<1;
# termcolor is imported by FlashRAG's pipelines but not declared as a dependency.
uv pip install --python "$ENV_DIR/bin/python" "vllm==$VLLM_VERSION" "$TRANSFORMERS_SPEC" "$FLASHRAG_SPEC" \
    faiss-cpu sentence-transformers termcolor pyyaml "huggingface-hub<1"

"$ENV_DIR/bin/python" -c "import vllm, torch, flashrag; print('vllm', vllm.__version__, '| torch', torch.__version__, '| cuda', torch.cuda.is_available())"
