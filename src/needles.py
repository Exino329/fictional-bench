"""Needle test: insert the needles of a hardcoded question file into the textbooks corpus.

The question file (configs/needles/questions_2hop.jsonl) is fixed, one question per line:

    {"id", "type", "question", "answer",
     "needles": [{"book", "chunk": index in the book's chunk file, "sentence"}, ...]}

Each needle sentence goes at a random (seeded) sentence boundary of its chunk. Chunk indices refer
to the chunk files of `source_chunks_dir` (src/books.py chunk with configs/chunker.yaml): rechunking
moves them. Writes, under `out_dir`:

- chunks/<book>.jsonl  every textbook's chunks, needles included (input of src/rag_data.py)
- questions.jsonl      {"id", "question", "answers", "hops": [[sentence], ...]} for src/rag_data.py

    uv run python src/needles.py configs/needles.yaml
"""

import argparse
import json
import random
import re
from pathlib import Path

import yaml


def insert(text: str, sentence: str, rng: random.Random) -> str:
    """The text with the sentence inserted at a random sentence boundary."""
    cuts = [m.end() for m in re.finditer(r"(?<=[.!?])\s+(?=[A-Z])", text)] or [len(text)]
    cut = rng.choice(cuts)
    return text[:cut].rstrip() + " " + sentence + " " + text[cut:].lstrip()


def main(config: dict) -> None:
    rng = random.Random(config["seed"])
    source, out = Path(config["source_chunks_dir"]), Path(config["out_dir"])
    chunks = {
        book: [json.loads(line) for line in (source / f"{book}.jsonl").open(encoding="utf-8")]
        for book in config["books"]
    }
    items = [json.loads(line) for line in Path(config["needles"]).read_text().splitlines()]
    hosts = [(n["book"], n["chunk"]) for item in items for n in item["needles"]]
    if len(hosts) != len(set(hosts)):
        raise ValueError("two needles share a chunk")

    questions = []
    for item in items:
        for needle in item["needles"]:
            row = chunks[needle["book"]][needle["chunk"]]
            row["text"] = insert(row["text"], needle["sentence"], rng)
        questions.append(
            {
                "id": item["id"],
                "question": item["question"],
                "answers": [item["answer"]],
                "hops": [[n["sentence"]] for n in item["needles"]],
            }
        )

    (out / "chunks").mkdir(parents=True, exist_ok=True)
    for book, rows in chunks.items():
        (out / "chunks" / f"{book}.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
        )
    (out / "questions.jsonl").write_text(
        "".join(json.dumps(q, ensure_ascii=False) + "\n" for q in questions), encoding="utf-8"
    )
    print(f"{len(questions)} questions, {len(hosts)} needles inserted -> {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", help="YAML config, e.g. configs/needles.yaml")
    main(yaml.safe_load(Path(parser.parse_args().config).read_text(encoding="utf-8")))
