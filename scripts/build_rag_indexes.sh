#!/usr/bin/env bash
# Build the BM25 and dense (BGE-M3, exact FAISS) indexes of the RAG corpus with FlashRAG.
#
# Usage:
#   bash scripts/build_rag_indexes.sh configs/rag.yaml
set -euo pipefail

CONFIG="${1:-configs/rag.yaml}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$REPO_ROOT/.venv-rag/bin/python"
cd "$REPO_ROOT"

read -r CORPUS INDEX_DIR < <("$PYTHON" -c "
import yaml, sys
c = yaml.safe_load(open('$CONFIG'))
print(c['corpus'], c['index_dir'])")

# Lexical: BM25 with bm25s (pure Python, no Java), English stopwords and stemming.
"$PYTHON" -m flashrag.retriever.index_builder --retrieval_method bm25 --bm25_backend bm25s \
    --corpus_path "$CORPUS" --save_dir "$INDEX_DIR"

# Dense: BGE-M3 dense vectors (CLS pooling, normalized), exact search (FAISS Flat).
"$PYTHON" -m flashrag.retriever.index_builder --retrieval_method bge-m3 --model_path BAAI/bge-m3 \
    --corpus_path "$CORPUS" --save_dir "$INDEX_DIR" --pooling_method cls --sentence_transformer \
    --max_length 512 --batch_size 32 --use_fp16 --faiss_type Flat

ls -la "$INDEX_DIR"
