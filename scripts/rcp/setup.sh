#!/usr/bin/env bash
# Run INSIDE the job. Clones fictional-bench on <branch> and installs its RAG venv (FlashRAG +
# vLLM, scripts/setup_rag_env.sh cluster). Safe to re-run.
#
# Usage: setup.sh <branch>
set -euo pipefail
source "$(dirname "$(readlink -f "$0")")/env.sh"
BRANCH=$1
mkdir -p "$WORK" "$HF_HOME" "$RESULTS"
nvidia-smi

echo "===== [$(date +%H:%M:%S)] clone $BRANCH"
[ -d "$REPO/.git" ] || git clone https://github.com/Exino329/fictional-bench.git "$REPO"
git -C "$REPO" fetch origin
git -C "$REPO" checkout "$BRANCH"
git -C "$REPO" pull --ff-only
echo "Commit: $(git -C "$REPO" log --oneline -1)"

command -v uv > /dev/null || pip install --user uv
echo "===== [$(date +%H:%M:%S)] RAG venv"
bash "$REPO/scripts/setup_rag_env.sh" cluster
echo "Setup done."
