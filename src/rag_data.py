"""Write the FlashRAG corpus and question set for the RAG experiments (see configs/rag.yaml).

- corpus: one document per chunk of the chosen books, `{"id", "contents"}` where contents is
  "<title>\\n<text>" (FlashRAG takes the first line as the title; we use the document id).
- questions: each hop of a question lists sentences of the text; every chunk that contains one
  of them is a gold document of that hop. Written as FlashRAG's `test.jsonl`:

    {"id", "question", "golden_answers", "metadata": {"gold_docs": [[ids of hop 1], ...]}}

    .venv-rag/bin/python src/rag_data.py configs/rag.yaml
"""

import argparse
import json
from pathlib import Path

import yaml


def normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def write_corpus(config: dict) -> list[dict]:
    docs = []
    for book in config["books"]:
        path = Path(config["chunks_dir"]) / f"{book}.jsonl"
        for i, line in enumerate(path.open(encoding="utf-8")):
            doc_id = f"{book.split('-', 1)[0]}-{i:05d}"  # e.g. "1-00217"
            docs.append({"id": doc_id, "contents": f"{doc_id}\n{json.loads(line)['text']}"})
    out = Path(config["corpus"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in docs), encoding="utf-8"
    )
    print(f"corpus: {len(docs)} documents -> {out}")
    return docs


def write_questions(config: dict, docs: list[dict]) -> None:
    texts = {d["id"]: normalize(d["contents"]) for d in docs}
    rows = []
    questions = Path(config["questions"]).read_text(encoding="utf-8").splitlines()
    for line in questions:
        q = json.loads(line)
        gold = []
        for hop, evidence in enumerate(q["hops"], start=1):
            ids = [i for i, t in texts.items() if any(normalize(e) in t for e in evidence)]
            if not ids:
                raise ValueError(f"{q['id']}: no document contains the evidence of hop {hop}")
            gold.append(ids)
        rows.append(
            {
                "id": q["id"],
                "question": q["question"],
                "golden_answers": q["answers"],
                "metadata": {"gold_docs": gold},
            }
        )
    out = Path(config["dataset_dir"]) / "test.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    print(f"questions: {len(rows)} -> {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", help="YAML config, e.g. configs/rag.yaml")
    config = yaml.safe_load(Path(parser.parse_args().config).read_text(encoding="utf-8"))
    write_questions(config, write_corpus(config))
