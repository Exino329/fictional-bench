"""Download the MedRAG corpus: all the textbooks plus random PubMed files.

PubMed is split into 1,166 files of ~20k abstracts each (roughly ordered by date, all topics
mixed); `pubmed_files` of them are drawn at random and kept whole.

Writes one `{"id", "contents"}` per line, the format FlashRAG's index_builder expects.
Everything is set in a YAML config (see configs/corpus.yaml):

    uv run python -m fictional_bench.corpus configs/corpus.yaml
"""

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path

import yaml
from huggingface_hub import HfApi, hf_hub_download

TEXTBOOKS_REPO = "MedRAG/textbooks"
PUBMED_REPO = "MedRAG/pubmed"


@dataclass
class CorpusConfig:
    out: Path
    seed: int
    pubmed_files: int

    def __post_init__(self) -> None:
        self.out = Path(self.out)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "CorpusConfig":
        return cls(**yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def list_files(repo_id: str) -> list[str]:
    files = HfApi().list_repo_files(repo_id, repo_type="dataset")
    return sorted(f for f in files if f.startswith("chunk/") and f.endswith(".jsonl"))


def download(repo_id: str, filename: str) -> Path:
    return Path(hf_hub_download(repo_id, filename, repo_type="dataset"))


def build_corpus(config: CorpusConfig) -> None:
    rng = random.Random(config.seed)
    pubmed = sorted(rng.sample(list_files(PUBMED_REPO), config.pubmed_files))
    to_download = [(TEXTBOOKS_REPO, f) for f in list_files(TEXTBOOKS_REPO)]
    to_download += [(PUBMED_REPO, f) for f in pubmed]

    config.out.parent.mkdir(parents=True, exist_ok=True)
    with config.out.open("w", encoding="utf-8") as out:
        for repo_id, filename in to_download:
            print(f"{repo_id}: {filename}")
            with download(repo_id, filename).open(encoding="utf-8") as f:
                for line in f:
                    snippet = json.loads(line)
                    out.write(json.dumps({"id": snippet["id"], "contents": snippet["contents"]}))
                    out.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", type=Path, nargs="?", default=Path("configs/corpus.yaml"))
    build_corpus(CorpusConfig.from_yaml(parser.parse_args().config))


if __name__ == "__main__":
    main()
