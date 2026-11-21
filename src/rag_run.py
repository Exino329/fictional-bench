"""Run the RAG methods of configs/rag.yaml with FlashRAG and save one JSONL per run.

Methods (the reader is the same everywhere):
- closed_book: the question alone, no documents.
- oracle: the gold documents of every hop.
- sequential: retrieve once with the question, give the top `retrieval_topk` documents.
- ircot: FlashRAG's IRCoT: one reasoning step, one retrieval with that step, and so on.
sequential and ircot run once per retriever. The reader is one of the config's `generators`,
chosen with --generator; its runs go to runs_dir/<generator>/. Each output line:

    {"id", "question", "golden_answers", "gold_docs", "pred", "retrieved": [doc ids, best first],
     "prompt", "steps"}

FlashRAG's own evaluation is skipped: src/rag_eval.py scores the runs.

    .venv-rag/bin/python src/rag_run.py configs/rag.yaml --generator apertus-fp8 \
        [--methods ircot] [--retrievers bm25]
"""

import argparse
import functools
import json
from pathlib import Path

import yaml
from flashrag.config import Config
from flashrag.dataset import Dataset
from flashrag.generator import VLLMGenerator
from flashrag.pipeline import IRCOTPipeline
from flashrag.prompt import PromptTemplate
from flashrag.utils import get_generator, get_retriever
from huggingface_hub import snapshot_download

ANSWER_RULE = "Give only the answer, in a few words, with no explanation."
USER_PROMPT = "Question: {question}\nAnswer:"
CLOSED_BOOK_SYSTEM = f"Answer the question. {ANSWER_RULE}"
WITH_DOCS_SYSTEM = f"Answer the question using the documents below. {ANSWER_RULE}\n\n{{reference}}"


def flashrag_config(config: dict, generator: str, retriever: str | None = None) -> Config:
    dataset_dir = Path(config["dataset_dir"])
    settings = {
        "data_dir": str(dataset_dir.parent),
        "dataset_name": dataset_dir.name,
        "split": ["test"],
        "save_dir": str(Path(config["runs_dir"]) / generator / "flashrag"),
        "corpus_path": config["corpus"],
        "retrieval_topk": config["retrieval_topk"],
        "retrieval_batch_size": 32,
        "silent_retrieval": True,
        "gpu_id": "0",
        "seed": 0,
        **{k: v for k, v in config["generators"][generator].items() if k != "vllm_args"},
    }
    # FlashRAG reads config.json from generator_model_path: a Hugging Face model id is first
    # downloaded to the Hugging Face cache.
    if not Path(settings["generator_model_path"]).is_dir():
        settings["generator_model_path"] = snapshot_download(settings["generator_model_path"])
    if retriever is not None:
        settings.update(config["retrievers"][retriever])
    return Config(config_dict=settings)


class SafeRetriever:
    """A FlashRAG retriever whose batch search survives queries it cannot handle.

    bm25s raises a ValueError for a query with no token left after stopwords (an IRCoT step can
    be "It is." or empty): such a query gets no documents instead of stopping the whole batch.
    """

    def __init__(self, retriever):
        self.retriever = retriever

    def __getattr__(self, name):
        return getattr(self.retriever, name)

    def batch_search(self, query, num=None, return_score=False):
        try:
            return self.retriever.batch_search(query, num=num, return_score=return_score)
        except ValueError:
            results, scores = [], []
            for q in query:
                try:
                    docs, doc_scores = self.retriever.search(q, num=num, return_score=True)
                except ValueError:
                    docs, doc_scores = [], []
                results.append(docs)
                scores.append(doc_scores)
            return (results, scores) if return_score else results


def template(cfg: Config, system: str, user: str = USER_PROMPT, reference=None) -> PromptTemplate:
    prompt = PromptTemplate(
        cfg, system_prompt=system, user_prompt=user, reference_template=reference
    )
    # FlashRAG applies the model's chat template only to models named "chat" or "instruct".
    prompt.is_chat = True
    # Answer directly: no "thinking" block (Qwen3), which would eat the token budget. Chat
    # templates without this option ignore it.
    tokenizer = prompt._get_tokenizer()
    tokenizer.apply_chat_template = functools.partial(
        tokenizer.apply_chat_template, enable_thinking=False
    )
    return prompt


def save(dataset: Dataset, path: Path, steps_of=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as out:
        for item in dataset:
            retrieved = item.output.get("retrieval_result") or []
            row = {
                "id": item.id,
                "question": item.question,
                "golden_answers": item.golden_answers,
                "gold_docs": item.metadata["gold_docs"],
                "pred": item.output.get("pred"),
                "retrieved": [doc["id"] for doc in retrieved],
                "prompt": item.output.get("prompt"),
                "steps": steps_of(item) if steps_of else None,
            }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {path}")


def closed_book(cfg, dataset, generator) -> Dataset:
    prompt = template(cfg, CLOSED_BOOK_SYSTEM)
    prompts = [prompt.get_string(question=q) for q in dataset.question]
    dataset.update_output("prompt", prompts)
    dataset.update_output("pred", generator.generate(prompts))
    return dataset


def oracle(cfg, dataset, generator, corpus: dict) -> Dataset:
    prompt = template(cfg, WITH_DOCS_SYSTEM)
    gold = [[corpus[i] for hop in item.metadata["gold_docs"] for i in hop] for item in dataset]
    prompts = [
        prompt.get_string(question=q, retrieval_result=g)
        for q, g in zip(dataset.question, gold, strict=True)
    ]
    dataset.update_output("retrieval_result", gold)
    dataset.update_output("prompt", prompts)
    dataset.update_output("pred", generator.generate(prompts))
    return dataset


def sequential(cfg, dataset, generator, retriever, keep: int) -> Dataset:
    """Retrieve `keep` documents (for recall@k), give the first `retrieval_topk` to the reader."""
    prompt = template(cfg, WITH_DOCS_SYSTEM)
    results = retriever.batch_search(dataset.question, num=keep)
    top = [docs[: cfg["retrieval_topk"]] for docs in results]
    prompts = [
        prompt.get_string(question=q, retrieval_result=d)
        for q, d in zip(dataset.question, top, strict=True)
    ]
    dataset.update_output("retrieval_result", results)
    dataset.update_output("prompt", prompts)
    dataset.update_output("pred", generator.generate(prompts))
    return dataset


def ircot(cfg, dataset, generator, retriever, max_iter: int) -> Dataset:
    # FlashRAG's IRCoT prompt (instruction + one worked example), sent through the chat template.
    prompt = template(
        cfg,
        f"{IRCOTPipeline.IRCOT_INSTRUCTION}\n\n{IRCOTPipeline.IRCOT_EXAMPLE}",
        user="{reference}Question: {question}\nThought:",
        reference="Wikipedia Title: {title}\n{text}\n\n",
    )
    pipeline = IRCOTPipeline(
        cfg, prompt, max_iter=max_iter, retriever=retriever, generator=generator
    )
    dataset = pipeline.run(dataset, do_eval=False)
    # IRCoT keeps every document it saw, sorted by score in increasing order: put the best first.
    for item in dataset:
        item.update_output("retrieval_result", item.output["retrieval_result"][::-1])
    return dataset


def ircot_steps(item) -> list[str]:
    steps, i = [], 0
    while f"intermediate_output_iter{i}" in item.output:
        steps.append(item.output[f"intermediate_output_iter{i}"]["new_thought"])
        i += 1
    return steps


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", help="YAML config, e.g. configs/rag.yaml")
    parser.add_argument("--methods", nargs="*", help="subset of the config's methods")
    parser.add_argument("--retrievers", nargs="*", help="subset of the config's retrievers")
    parser.add_argument("--generator", help="one of the config's generators (default: the first)")
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    reader = args.generator or next(iter(config["generators"]))
    methods = args.methods or config["methods"]
    retrievers = args.retrievers or list(config["retrievers"])
    runs_dir = Path(config["runs_dir"]) / reader
    test_path = str(Path(config["dataset_dir"]) / "test.jsonl")

    vllm_args = config["generators"][reader].get("vllm_args")
    if vllm_args:  # FlashRAG builds vllm.LLM itself and exposes none of these arguments
        import vllm

        vllm.LLM = functools.partial(vllm.LLM, **vllm_args)
    base = flashrag_config(config, reader)
    # loaded once, shared by every run. get_generator would send any model whose config has a
    # vision part (Qwen3.5, Gemma 3) to FlashRAG's Hugging Face Qwen2-VL generator, not to vLLM.
    generator = VLLMGenerator(base) if base["framework"] == "vllm" else get_generator(base)
    corpus = {}
    with open(config["corpus"], encoding="utf-8") as f:
        for line in f:
            doc = json.loads(line)
            corpus[doc["id"]] = doc

    if "closed_book" in methods:
        save(closed_book(base, Dataset(base, test_path), generator), runs_dir / "closed_book.jsonl")
    if "oracle" in methods:
        save(oracle(base, Dataset(base, test_path), generator, corpus), runs_dir / "oracle.jsonl")
    for name in retrievers:
        if not {"sequential", "ircot"} & set(methods):
            break
        cfg = flashrag_config(config, reader, name)
        retriever = SafeRetriever(get_retriever(cfg))
        if "sequential" in methods:
            dataset = sequential(
                cfg, Dataset(cfg, test_path), generator, retriever, max(config["recall_k"])
            )
            save(dataset, runs_dir / f"sequential__{name}.jsonl")
        if "ircot" in methods:
            dataset = ircot(
                cfg, Dataset(cfg, test_path), generator, retriever, config["ircot_max_iter"]
            )
            save(dataset, runs_dir / f"ircot__{name}.jsonl", steps_of=ircot_steps)
        del retriever
