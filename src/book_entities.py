"""Find the Hetionet entities that each book mentions, how often, and where.

The book text is the reference text written by `src/books.py pages` (its cleaned pages joined
by a blank line): the closest we have to the PDF, and free of the table headers that mmore
repeats in each table-row chunk. Positions are character offsets in that text. The chunk
count comes from the per-book chunk files (`src/books.py split`). Writes one JSON per book:

    {"book", "pages": N, "chunks": N, "chars": length of the book text,
     "entities": {"<kind>": [{"identifier", "name", "mentions",
                              "chunks": number of chunks that mention it,
                              "positions": [char offset of each mention],
                              "pages": [page of each mention],
                              "gaps": [chars between two consecutive mentions]}, ...]},
     "dropped_gene_symbols": {...}}

Names are matched as whole words: case-insensitive for most kinds, case-sensitive for gene
symbols (so the gene "CAT" does not match "cat"). A gene symbol is dropped when the book
defines it as the abbreviation of something else ("familial adenomatous polyposis (FAP)").
Only the nodes kept by the licence filter of src/hetionet.py are searched.

    uv run python src/book_entities.py configs/books.yaml
"""

import argparse
import bisect
import json
import re
from collections import defaultdict
from pathlib import Path

import yaml

from hetionet import Hetionet, NodeId

MAX_WORDS = 8  # longest entity name we look for, in words
MIN_CHARS = 3  # shorter names are too ambiguous ("T", "AR")


def words(text: str, keep_case: bool) -> list[str]:
    text = text if keep_case else text.lower()
    return re.findall(r"[A-Za-z0-9]+", text)


def spans(text: str, keep_case: bool) -> tuple[list[str], list[int]]:
    """The words of `text` and the character offset where each one starts."""
    matches = list(re.finditer(r"[A-Za-z0-9]+", text))
    tokens = [m.group() if keep_case else m.group().lower() for m in matches]
    return tokens, [m.start() for m in matches]


def build_index(graph: Hetionet) -> tuple[dict[tuple, list], dict[tuple, list]]:
    """Map each node name, as a tuple of words, to its nodes; genes in a separate, case-kept map.

    A name can belong to several nodes (e.g. "Colon cancer" is both a Disease and a Side Effect).
    """
    names, genes = defaultdict(list), defaultdict(list)
    for node in graph.nodes.values():
        if len(node.name) < MIN_CHARS:
            continue
        if node.kind == "Gene":
            key = tuple(words(node.name, keep_case=True))
            if key and any(c.isupper() for c in node.name):
                genes[key].append(node.id)
        else:
            key = tuple(words(node.name, keep_case=False))
            if 0 < len(key) <= MAX_WORDS:
                names[key].append(node.id)
    return names, genes


def find(tokens: list[str], index: dict[tuple, list], longest: int) -> list[tuple[NodeId, int]]:
    """(node, index of its first token) for every entry found, longest match first at each token."""
    found, i = [], 0
    while i < len(tokens):
        for n in range(min(longest, len(tokens) - i), 0, -1):
            nodes = index.get(tuple(tokens[i : i + n]))
            if nodes:
                found += [(node, i) for node in nodes]
                i += n
                break
        else:
            i += 1
    return found


def other_meanings(text: str, symbol: str, description: str) -> list[str]:
    """Long forms the text gives for `symbol` ("familial adenomatous polyposis (FAP)") that share
    no word with the gene's own description: then the symbol stands for something else."""
    gene_words = set(words(description, keep_case=False)) - {"and", "of", "the"}
    found = []
    for m in re.finditer(r"((?:[A-Za-z\-]+ ){1,6})\(" + re.escape(symbol) + r"s?\)", text):
        long_form = words(m.group(1), keep_case=False)[-len(symbol) :]
        initials = "".join(w[0] for w in long_form)
        if initials == symbol.lower() and not gene_words & set(long_form):
            found.append(" ".join(long_form))
    return found


def mentions(text: str, names: dict, genes: dict) -> dict[NodeId, list[int]]:
    """Character offsets of every entity mention in `text`."""
    found = defaultdict(list)
    for keep_case, index, longest in [(False, names, MAX_WORDS), (True, genes, 3)]:
        tokens, starts = spans(text, keep_case)
        for node_id, i in find(tokens, index, longest):
            found[node_id].append(starts[i])
    return found


def book_entities(book: dict, chunks: list[str], graph: Hetionet, names: dict, genes: dict) -> dict:
    """`book` is one line of the texts file: {"book", "text", "page_numbers", "page_starts"}."""
    book_text, page_starts = book["text"], book["page_starts"]

    chunk_counts = defaultdict(int)
    for chunk in chunks:
        for node_id in mentions(chunk, names, genes):
            chunk_counts[node_id] += 1

    by_kind = defaultdict(list)
    dropped = {}  # gene symbols that the book defines as something else
    found = mentions(book_text, names, genes)
    for node_id, pos in sorted(found.items(), key=lambda item: -len(item[1])):
        node = graph.nodes[node_id]
        if node.kind == "Gene":
            meanings = other_meanings(book_text, node.name, node.description)
            if meanings:
                dropped[node.name] = sorted(set(meanings))
                continue
        pos.sort()
        pages = [book["page_numbers"][bisect.bisect_right(page_starts, p) - 1] for p in pos]
        by_kind[node.kind].append(
            {
                "identifier": node.identifier,
                "name": node.name,
                "mentions": len(pos),
                "chunks": chunk_counts[node_id],
                "positions": pos,
                "pages": pages,
                "gaps": [b - a for a, b in zip(pos, pos[1:], strict=False)],
            }
        )
    return {
        "book": book["book"],
        "pages": len(page_starts),
        "chunks": len(chunks),
        "chars": len(book_text),
        "entities": dict(by_kind),
        "dropped_gene_symbols": dropped,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", help="YAML config, e.g. configs/books.yaml")
    config = yaml.safe_load(Path(parser.parse_args().config).read_text(encoding="utf-8"))
    out_dir = Path(config["entities_dir"])
    graph = Hetionet()
    names, genes = build_index(graph)
    out_dir.mkdir(parents=True, exist_ok=True)
    with Path(config["texts"]).open(encoding="utf-8") as f:
        for line in f:
            book = json.loads(line)
            chunk_file = Path(config["chunks_dir"]) / f"{book['book']}.jsonl"
            chunks = [json.loads(row)["text"] for row in chunk_file.open(encoding="utf-8")]
            result = book_entities(book, chunks, graph, names, genes)
            path = out_dir / f"{book['book']}.json"
            path.write_text(json.dumps(result, indent=1), encoding="utf-8")
            counts = ", ".join(f"{kind}: {len(v)}" for kind, v in result["entities"].items())
            print(f"{book['book']}: {counts}")
