# Source INSIDE the job. The repo clone, its RAG venv and the model weights stay on scratch between
# jobs, so only the first job installs and downloads.
GASPAR=lieberhe
export SCRATCH=/lightscratch/users/$GASPAR
export WORK=$SCRATCH/fictional-bench
export REPO=$WORK/fictional-bench
export DATA_TGZ=$WORK/needles-data.tgz    # uploaded by submit.sh
export RESULTS=$WORK/results              # one tarball of runs per job
export HF_HOME=$SCRATCH/hf_cache
# The container home is wiped with each job: keep uv's Python and download cache on scratch
export UV_PYTHON_INSTALL_DIR=$WORK/.uv-python
export UV_CACHE_DIR=$SCRATCH/uv_cache
export UV_LINK_MODE=copy
export PATH="$HOME/.local/bin:$PATH"
