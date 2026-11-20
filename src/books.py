"""Turn the PDF documents of a corpus (textbooks, guidelines) into chunks, one file per document.

A corpus config (configs/textbooks.yaml, configs/guidelines.yaml) names the folder of PDFs and the
folder for every output. Two steps; the second runs mmore, which lives in its own environment
(see configs/chunker.yaml):

    uv run python src/books.py pages configs/textbooks.yaml   # PDF -> pages, and the full text
    uv run python src/books.py chunk configs/textbooks.yaml   # pages -> chunks, one file per doc

Pages and chunks are mmore `MultimodalSample`s, one per line ("book" is the document's file name):

    {"text": "<markdown>", "modalities": [], "metadata": {"file_path", "book", "page", ...}}

`pages` also writes the reference text of each document, before chunking, one line per document:

    {"book", "text": its pages joined by a blank line, "page_numbers", "page_starts"}

Character positions elsewhere (e.g. src/book_entities.py) are offsets in that text.
"""

import argparse
import json
import re
import subprocess
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf
import pymupdf4llm
import yaml

CHUNKER_CONFIG = Path("configs/chunker.yaml")  # mmore's chunker settings, shared by every corpus


@dataclass
class CorpusConfig:
    name: str
    pdf_dir: Path  # the PDFs of the corpus
    processed_dir: Path  # every output, at the fixed paths below
    titles: dict = field(default_factory=dict)  # file name or number prefix -> title (for plots)

    def __post_init__(self) -> None:
        self.pdf_dir, self.processed_dir = Path(self.pdf_dir), Path(self.processed_dir)

    @property
    def pages(self) -> Path:  # one cleaned page per line, input of mmore
        return self.processed_dir / "pages.jsonl"

    @property
    def texts(self) -> Path:  # the reference text of each document, one per line
        return self.processed_dir / "texts.jsonl"

    @property
    def chunks(self) -> Path:  # mmore's output, every document
        return self.processed_dir / "chunks.jsonl"

    @property
    def chunks_dir(self) -> Path:  # one <document>.jsonl of chunks per document
        return self.processed_dir / "chunks"

    @property
    def entities_dir(self) -> Path:  # output of src/book_entities.py
        return self.processed_dir / "entities"

    @property
    def plots_dir(self) -> Path:  # output of src/plot_entities.py
        return self.processed_dir / "plots"

    @classmethod
    def from_yaml(cls, path: str | Path) -> "CorpusConfig":
        return cls(**yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def _shape(line: str) -> str:
    """A line with its digits masked, so "Page 12" and "Page 13" count as the same line."""
    return re.sub(r"\d+", "#", line.strip())


def strip_running_lines(texts: list[str], min_share: float = 0.2) -> list[str]:
    """Drop headers, footers and page numbers: short lines found on many pages of the book.

    Table rows are kept, since a real table can repeat across pages.
    """
    counts = Counter()
    for text in texts:
        counts.update({_shape(line) for line in text.split("\n") if line.strip()})
    running = {
        shape
        for shape, n in counts.items()
        if (n >= min_share * len(texts) or shape == "#")
        and len(shape) < 120
        and not shape.startswith("|")
    }
    return [
        "\n".join(line for line in text.split("\n") if _shape(line) not in running)
        for text in texts
    ]


REF_HEADING = re.compile(
    r"(?i)^((text|image|chapter) )?(references?|bibliography|further reading|works cited"
    r"|suggested (further )?readings?|recommended readings?|key references|license|licence)$"
)
REFERENCE_LINE = re.compile(r"^\s*(-|\d{1,4}\.|\[\d+\])\s")  # "- Smith J…", "12. Smith J…"
CITATION = re.compile(r"(et al|\b(19|20)\d{2}\b|doi|https?://|\bvol\b|\d+\s*\(\d+\)\s*:)", re.I)
ATTRIBUTION = re.compile(r"(?i)(licensed under|derivative of|access for free at|cc by)")


def _title_key(text: str) -> str:
    """A title reduced for matching: "3: What Defines a Good Tumour Antigen?" -> "what defines…"."""
    text = re.sub(r"^\s*[\d.]+[:.]?\s+", "", re.sub(r"[#*_`]", "", text))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _heading(line: str, toc_titles: set[str]) -> str | None:
    """The text of a heading line, else None: a Markdown heading ("## **_References_**"), or a
    line that matches a title of the PDF's table of contents (some chapter titles are only bold).
    """
    text = re.sub(r"[#*_`]", "", line).strip()
    if line.lstrip().startswith("#") or (len(text) < 200 and _title_key(text) in toc_titles):
        return text
    return None


def _looks_like_references(lines: list[str]) -> bool:
    entries = [line for line in lines if line.strip()][:3]
    return bool(entries) and all(
        REFERENCE_LINE.match(line) or CITATION.search(line) for line in entries
    )


def strip_references(texts: list[str], toc_titles: set[str]) -> tuple[list[str], int]:
    """Drop reference sections and numbered attribution footnotes; return pages, words removed.

    A reference section runs from a heading such as "References" or "Further Reading" to the
    next heading, unless the lines after that heading still look like references (a running
    header in the middle of the list). This also drops what follows the list in the same
    section, e.g. Springer's open-access licence box. Pressbooks books (Open RN, Virginia Tech)
    credit their sources in numbered footnotes ("1. This work is a derivative of …").
    `toc_titles` (see _title_key) are the PDF's chapter and section titles: they end a section
    even when they are not Markdown headings.
    """
    lines = [(i, line) for i, text in enumerate(texts) for line in text.split("\n")]
    kept = [[] for _ in texts]
    removed, in_refs = 0, False
    for k, (page, line) in enumerate(lines):
        heading = _heading(line, toc_titles)
        bold = re.fullmatch(r"\s*\*\*([^*]+)\*\*\s*", line)  # "**References**" (no "#")
        if (heading is not None and REF_HEADING.match(heading)) or (
            bold and REF_HEADING.match(bold.group(1).strip())
        ):
            in_refs = True
        elif heading is not None and in_refs:
            following = [text for _, text in lines[k + 1 : k + 8]]
            in_refs = _looks_like_references(following)
        drop = in_refs or (REFERENCE_LINE.match(line) and ATTRIBUTION.search(line))
        if drop:
            removed += len(line.split())
        else:
            kept[page].append(line)
    return ["\n".join(page) for page in kept], removed


def write_pages(config: CorpusConfig) -> None:
    config.pages.parent.mkdir(parents=True, exist_ok=True)
    with (
        config.pages.open("w", encoding="utf-8") as out,
        config.texts.open("w", encoding="utf-8") as texts_out,
    ):
        for pdf in sorted(config.pdf_dir.glob("*.pdf")):
            pages = pymupdf4llm.to_markdown(str(pdf), page_chunks=True, show_progress=False)
            texts = strip_running_lines([page["text"] for page in pages])
            toc_titles = {
                _title_key(title)
                for _, title, _ in pymupdf.open(pdf).get_toc()
                if not REF_HEADING.match(re.sub(r"[#*_`]", "", title).strip())
            }
            texts, removed = strip_references(texts, toc_titles - {""})
            kept = []  # (page number, text) of the non-empty pages
            for page, text in zip(pages, texts, strict=True):
                if text.strip():
                    kept.append((page["metadata"]["page_number"], text.strip()))
            for number, text in kept:
                sample = {
                    "text": text,
                    "modalities": [],
                    "metadata": {"file_path": str(pdf), "book": pdf.stem, "page": number},
                }
                out.write(json.dumps(sample, ensure_ascii=False) + "\n")
            starts = [0]
            for _, text in kept[:-1]:
                starts.append(starts[-1] + len(text) + 2)
            book = {
                "book": pdf.stem,
                "text": "\n\n".join(text for _, text in kept),
                "page_numbers": [number for number, _ in kept],  # page in the PDF, from 1
                "page_starts": starts,  # offset where each page begins in "text"
            }
            texts_out.write(json.dumps(book, ensure_ascii=False) + "\n")
            words = sum(len(text.split()) for _, text in kept)
            print(
                f"{pdf.name}: {len(pages)} pages, {words} words kept, "
                f"{removed} reference words removed"
            )


def chunk(config: CorpusConfig) -> None:
    """Chunk the pages with mmore (settings in CHUNKER_CONFIG), then write one file per document."""
    settings = yaml.safe_load(CHUNKER_CONFIG.read_text(encoding="utf-8"))
    settings["output"] = {"output_path": str(config.chunks), "save_each_step": False}
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump(settings, f)
    config.chunks.unlink(missing_ok=True)  # mmore appends to an existing file
    command = ["mmore", "postprocess", "--config-file", f.name, "--input-data", str(config.pages)]
    subprocess.run(command, check=True)
    Path(f.name).unlink()

    by_book = defaultdict(list)
    with config.chunks.open(encoding="utf-8") as chunks:
        for line in chunks:
            by_book[json.loads(line)["metadata"]["book"]].append(line)
    config.chunks_dir.mkdir(parents=True, exist_ok=True)
    for book, lines in sorted(by_book.items()):
        (config.chunks_dir / f"{book}.jsonl").write_text("".join(lines), encoding="utf-8")
        print(f"{book}: {len(lines)} chunks")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=["pages", "chunk"])
    parser.add_argument("config", help="corpus config, e.g. configs/textbooks.yaml")
    args = parser.parse_args()
    config = CorpusConfig.from_yaml(args.config)
    write_pages(config) if args.step == "pages" else chunk(config)
