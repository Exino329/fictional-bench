#!/usr/bin/env bash
# Run INSIDE the job, after setup.sh. Needle test (configs/needles.yaml): unpacks the corpus and
# questions uploaded by submit.sh, builds the BM25 and BGE-M3 indexes, runs every method
# (closed-book, oracle, sequential, IRCoT) with each reader, scores them all, and packs the runs
# into $RESULTS/needles_<timestamp>.tgz. A reader that fails does not stop the others.
#
# Usage: ./submit.sh <branch> run_needles.sh
set -euo pipefail
source "$(dirname "$(readlink -f "$0")")/env.sh"
cd "$REPO"
CONFIG=configs/needles.yaml
PY=.venv-rag/bin/python
READERS=${READERS:-"apertus qwen gemma"}
STAMP=$(date +%Y-%m-%d_%H%M%S)
mkdir -p data/rag/needles
exec > >(tee -a "data/rag/needles/run_$STAMP.log") 2>&1
echo "Commit: $(git log --oneline -1)"
step() { echo; echo "===== [$(date +%H:%M:%S)] $*"; }
run() { SECONDS=0; if "$@"; then echo "ok (${SECONDS} s)"; else echo "!!! FAILED (${SECONDS} s): $*"; fi; }
$PY -c "import vllm, torch, transformers; print('vllm', vllm.__version__, '| torch', torch.__version__, '| transformers', transformers.__version__)"

step "data: corpus and questions from $DATA_TGZ (fresh runs and indexes)"
rm -rf data/rag/needles/runs data/rag/needles/indexes
tar xzf "$DATA_TGZ" -C data/rag/needles
ls -la data/rag/needles data/rag/needles/dataset

step "indexes: BM25 and BGE-M3"
bash scripts/build_rag_indexes.sh $CONFIG

for reader in $READERS; do
  step "reader $reader: every method"
  run $PY src/rag_run.py $CONFIG --generator "$reader"
done

step "scores"
$PY src/rag_eval.py $CONFIG
tar czf "$RESULTS/needles_$STAMP.tgz" -C data/rag/needles runs questions.jsonl "run_$STAMP.log"
echo "Results: $RESULTS/needles_$STAMP.tgz"
echo "DONE"
