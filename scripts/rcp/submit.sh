#!/usr/bin/env bash
# Run LOCALLY (EPFL network or VPN), from anywhere in the repo. Uploads the needle-test data
# (data/rag/needles: corpus and questions; build them first with the commands at the top of
# configs/needles.yaml) to scratch through the jumphost, then submits a 1-GPU H100 job running
# <script> on <branch>. The branch must be pushed: the job clones it.
#
# Usage: scripts/rcp/submit.sh [branch] [script]     (defaults: main, run_needles.sh)
#        READERS="qwen" scripts/rcp/submit.sh          (a subset of the readers)
# Results, when the log says DONE:
#   scp lieberhe@jumphost.rcp.epfl.ch:/mnt/light/scratch/users/lieberhe/fictional-bench/results/needles_<date>.tgz .
#   runai delete job <job name>
set -euo pipefail
BRANCH=${1:-main}
SCRIPT=${2:-run_needles.sh}
GASPAR=lieberhe
JOB_NAME=fb-$(basename "$SCRIPT" .sh | tr '_' '-')
JOB_DIR=/lightscratch/users/$GASPAR/fictional-bench/rcp
HERE="$(dirname "$(readlink -f "$0")")"
DATA="$HERE/../../data/rag/needles"

echo "upload: needle-test data -> scratch"
tar czf /tmp/needles-data.tgz -C "$DATA" corpus.jsonl dataset questions.jsonl
ssh $GASPAR@jumphost.rcp.epfl.ch mkdir -p /mnt/light/scratch/users/$GASPAR/fictional-bench
scp /tmp/needles-data.tgz $GASPAR@jumphost.rcp.epfl.ch:/mnt/light/scratch/users/$GASPAR/fictional-bench/
rm /tmp/needles-data.tgz

cd "$HERE"
SCRIPTS=$(tar cz --exclude=__pycache__ . | base64 -w0)
runai submit \
  --name "$JOB_NAME" \
  --image registry.rcp.epfl.ch/mmore-lorin/basic:amd64-cuda-${GASPAR}-latest \
  --pvc light-scratch:/lightscratch \
  --large-shm \
  -e NAS_HOME=/lightscratch/users/$GASPAR \
  -e GIT_CONFIG_AT=/lightscratch/users/$GASPAR/.gitconfig \
  -e GIT_CREDENTIALS_AT=/lightscratch/users/$GASPAR/.git-credentials \
  -e HF_TOKEN_PATH=/lightscratch/users/$GASPAR/keys/hf_key.txt \
  -e READERS="${READERS:-apertus qwen gemma}" \
  -e RCP_SCRIPTS="$SCRIPTS" \
  --backoff-limit 0 \
  --run-as-gid 84257 \
  --node-pool h100 \
  --gpu 1 \
  -- bash -c "set -e
    rm -rf $JOB_DIR
    mkdir -p $JOB_DIR && cd $JOB_DIR
    echo \"\$RCP_SCRIPTS\" | base64 -d | tar xz
    bash setup.sh $BRANCH
    bash $SCRIPT"

echo "Follow:  runai logs -f $JOB_NAME"
echo "Finally: runai delete job $JOB_NAME"
