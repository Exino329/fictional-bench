"""Quantize a Hugging Face causal LM to FP8 (weights FP8, activations quantized on the fly).

FP8_DYNAMIC needs no calibration data and runs on the CPU. The result loads directly in vLLM,
at about half the memory of bf16 (an 8B model: ~16 GB -> ~8.5 GB).

llm-compressor pins its own transformers, so it runs outside the project environment:

    uv run --no-project --python 3.12 --with llmcompressor \
        python src/quantize_fp8.py EPFLiGHT/Apertus-8B-MeditronFO \
        data/models/Apertus-8B-MeditronFO-FP8-Dynamic
"""

import argparse
import shutil
from pathlib import Path

from huggingface_hub import snapshot_download
from llmcompressor import oneshot
from llmcompressor.modifiers.quantization import QuantizationModifier
from transformers import AutoModelForCausalLM

# Copied as they are: re-saving them with the transformers 5 that llm-compressor installs writes
# a tokenizer class ("TokenizersBackend") that the transformers 4 of vLLM cannot load.
TOKENIZER_FILES = [
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "chat_template.jinja",
]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("model", help="Hugging Face model id or local path")
    parser.add_argument("out", help="directory for the quantized model")
    args = parser.parse_args()

    model = AutoModelForCausalLM.from_pretrained(args.model, torch_dtype="auto", device_map="cpu")
    # Every Linear layer except the output head, which stays in full precision.
    recipe = QuantizationModifier(targets="Linear", scheme="FP8_DYNAMIC", ignore=["lm_head"])
    oneshot(model=model, recipe=recipe)
    model.save_pretrained(args.out, save_compressed=True)

    source = Path(args.model)
    if not source.is_dir():
        source = Path(snapshot_download(args.model, allow_patterns=TOKENIZER_FILES))
    for name in TOKENIZER_FILES:
        if (source / name).exists():
            shutil.copy(source / name, Path(args.out) / name)
    print(f"saved to {args.out}")
