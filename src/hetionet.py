"""Load Hetionet v1.0 (JSON), downloading it on first use, and print what it contains."""

import bz2
import json
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

HETIONET_URL = "https://media.githubusercontent.com/media/hetio/hetionet/main/hetnet/json/hetionet-v1.0.json.bz2"
HETIONET_PATH = Path("data/hetionet/hetionet-v1.0.json.bz2")

# Keep CC0 part of Hetionet graph
LICENSE = "CC0 1.0"

# A node is identified by its type and its identifier, e.g. ("Compound", "DB00331").
NodeId = tuple[str, str]


@dataclass(slots=True)
class Node:
    kind: str  # the node type, e.g. "Compound"
    identifier: str  # e.g. "DB00331" (always a string, gene identifiers included)
    name: str  # e.g. "Metformin"

    @property
    def id(self) -> NodeId:
        return (self.kind, self.identifier)


@dataclass(slots=True)
class Edge:
    source: NodeId
    relation: str  # e.g. "treats"
    target: NodeId
    license: str | None


class Hetionet:
    def __init__(self, path: Path = HETIONET_PATH) -> None:
        if not path.exists():
            print(f"downloading {HETIONET_URL}")
            path.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(HETIONET_URL, path)
        with bz2.open(path, "rt", encoding="utf-8") as f:
            graph = json.load(f)
        self.edges: list[Edge] = [
            Edge(
                source=(edge["source_id"][0], str(edge["source_id"][1])),
                relation=edge["kind"],
                target=(edge["target_id"][0], str(edge["target_id"][1])),
                license=edge["data"].get("license"),
            )
            for edge in graph["edges"]
            if edge["data"].get("license") == LICENSE
        ]
        # Keep only the nodes that some CC0 edge connects.
        connected = {e.source for e in self.edges} | {e.target for e in self.edges}
        nodes = (Node(n["kind"], str(n["identifier"]), n["name"]) for n in graph["nodes"])
        self.nodes: dict[NodeId, Node] = {node.id: node for node in nodes if node.id in connected}

    def summarize(self) -> None:
        """Print the number of nodes per type, and of edges per relation and license."""
        nodes = Counter(kind for kind, _ in self.nodes)
        print(f"\n{len(self.nodes)} nodes")
        for kind, n in nodes.most_common():
            print(f"  {n:>7}  {kind}")

        metaedges = Counter()
        licenses = Counter()
        for edge in self.edges:
            metaedge = (edge.source[0], edge.relation, edge.target[0])
            metaedges[metaedge] += 1
            licenses[metaedge, edge.license or "(none)"] += 1

        print(f"\n{len(self.edges)} edges")
        for (source, relation, target), n in metaedges.most_common():
            by_license = ", ".join(
                f"{license}: {count}"
                for (metaedge, license), count in licenses.most_common()
                if metaedge == (source, relation, target)
            )
            print(f"  {n:>7}  {source} -{relation}-> {target}  [{by_license}]")


if __name__ == "__main__":
    Hetionet().summarize()
