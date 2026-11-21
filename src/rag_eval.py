"""Score the RAG runs written by src/rag_run.py, on gold document ids rather than answer strings.

Per run:
- acc: a gold answer appears in the prediction (both normalized); em: they are equal.
- hop@k: share of hops with at least one gold document in the first k retrieved.
- chain@k: share of questions whose every hop is found in the first k.
- shortcut: share of questions answered correctly although the reader did not get the full chain.
For ircot, retrieval counts every document seen over the steps (column "all").
Runs are read from runs_dir/<reader>/ (one folder per reader of src/rag_run.py), and the
summary covers every reader.
FlashRAG's own retrieval_recall only checks that the answer string appears in a passage.

    .venv-rag/bin/python src/rag_eval.py configs/rag.yaml
"""

import argparse
import json
import re
import string
from pathlib import Path

import yaml


def normalize(text: str) -> str:
    text = text.lower()
    text = "".join(c for c in text if c not in string.punctuation)
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(text.split())


def found(retrieved: list[str], hop: list[str], k: int | None) -> bool:
    return bool(set(retrieved[:k] if k else retrieved) & set(hop))


def score(rows: list[dict], ks: list[int], reader_k: int | None) -> dict:
    n = len(rows)
    result = {"n": n}
    correct = []
    for r in rows:
        pred, golds = normalize(r["pred"] or ""), [normalize(g) for g in r["golden_answers"]]
        correct.append(any(g and g in pred for g in golds))
        r["_em"] = any(pred == g for g in golds)
    result["acc"] = sum(correct) / n
    result["em"] = sum(r["_em"] for r in rows) / n
    if any(r["retrieved"] for r in rows):
        hops = sum(len(r["gold_docs"]) for r in rows)
        for k in ks + [None]:
            name = k or "all"
            hit = sum(found(r["retrieved"], h, k) for r in rows for h in r["gold_docs"])
            chain = sum(all(found(r["retrieved"], h, k) for h in r["gold_docs"]) for r in rows)
            result[f"hop@{name}"] = hit / hops
            result[f"chain@{name}"] = chain / n
        full = [all(found(r["retrieved"], h, reader_k) for h in r["gold_docs"]) for r in rows]
        result["shortcut"] = sum(c and not f for c, f in zip(correct, full, strict=True)) / n
        result["docs_seen"] = sum(len(r["retrieved"]) for r in rows) / n
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", help="YAML config, e.g. configs/rag.yaml")
    config = yaml.safe_load(Path(parser.parse_args().config).read_text(encoding="utf-8"))
    runs_dir, ks = Path(config["runs_dir"]), config["recall_k"]
    columns = ["n", "acc", "em"] + [f"{m}@{k}" for k in ks + ["all"] for m in ("hop", "chain")]
    columns += ["shortcut", "docs_seen"]
    lines = ["| run | " + " | ".join(columns) + " |", "|---|" + "---|" * len(columns)]
    summary = {}
    for path in sorted(runs_dir.glob("*/*.jsonl")):
        rows = [json.loads(line) for line in path.open(encoding="utf-8")]
        # the reader sees retrieval_topk documents in sequential, every document seen in ircot
        reader_k = config["retrieval_topk"] if path.stem.startswith("sequential") else None
        result = score(rows, ks, reader_k)
        run = f"{path.parent.name}/{path.stem}"
        summary[run] = result
        cells = [
            ""
            if c not in result
            else (f"{result[c]:.2f}" if isinstance(result[c], float) else str(result[c]))
            for c in columns
        ]
        lines.append(f"| {run} | " + " | ".join(cells) + " |")
    table = "\n".join(lines)
    print(table)
    (runs_dir / "summary.md").write_text(table + "\n", encoding="utf-8")
    (runs_dir / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
