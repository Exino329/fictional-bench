"""Benchmark generator"""

import argparse
import random
from dataclasses import dataclass
from pathlib import Path

import yaml

from hetionet import Hetionet


@dataclass
class GeneratorConfig:
    seed: int

    @classmethod
    def from_yaml(cls, path: str | Path) -> "GeneratorConfig":
        return cls(**yaml.safe_load(Path(path).read_text(encoding="utf-8")))


class Generator:
    def __init__(self, seed: int, hetionet: Hetionet) -> None:
        self.rng = random.Random(seed)
        self.hetionet = hetionet


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", type=Path, nargs="?", default=Path("configs/generator.yaml"))
    config = GeneratorConfig.from_yaml(parser.parse_args().config)
    Generator(config.seed, Hetionet())


if __name__ == "__main__":
    main()
