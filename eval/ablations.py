"""Retrieval ablations (no LLM), all on the questions with gold documents.

1. retriever: dense vs BM25 vs hybrid, each with and without the reranker
2. chunking: structure-aware vs fixed-size chunks (separate index in data/ablation/fixed)
3. context header: "title > section" in front of each chunk before indexing (data/ablation/header),
   question text only (--raw style, no contract id filter)
4. versions: latest-only vs version-aware (as_of) on eval/datasets/version_questions.jsonl

The "with / without routing" ablation needs the LLM: run_agent_eval.py --no-router.
The "fine-tuned classifier vs LLM" ablation is in finetuning/evaluate.py.

Run: uv run python eval/ablations.py                  (builds the 2 extra indexes the first time, ~15 min)
     uv run python eval/ablations.py --only retriever
"""

import argparse
import json
from pathlib import Path

import run_retrieval_eval as retrieval_eval

from creatorops.config import settings
from creatorops.evaluation.dataset import load_questions
from creatorops.indexing.bm25 import BM25Index
from creatorops.indexing.embeddings import Embedder
from creatorops.indexing.vectorstore import VectorStore
from creatorops.ingestion.pipeline import ingest
from creatorops.ingestion.versioning import Registry
from creatorops.retrieval.dense import DenseRetriever
from creatorops.retrieval.hybrid import HybridRetriever
from creatorops.retrieval.rerank import Reranker

RUNS = Path("eval/runs")
ABLATION_DATA = Path("data/ablation")


def build_index(name: str, embedder, chunker="structure", context_header=False):
    """Index the whole corpus again with other settings (only the first time)."""
    folder = ABLATION_DATA / name
    registry = Registry(folder / "registry.sqlite")
    store = VectorStore("chunks", embedder.dim, path=folder / "qdrant")
    if store.count() == 0:
        print(f"building the {name} index...", flush=True)
        ingest(settings.manifest_path, settings.data_dir, registry, store, embedder, chunker=chunker,
               context_header=context_header)  # fmt: skip
    return DenseRetriever(embedder, store), BM25Index(registry.all_chunks())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="retriever, chunking, header or versions")
    args = parser.parse_args()
    parts = [args.only] if args.only else ["retriever", "chunking", "header", "versions"]

    embedder = Embedder(settings.embedding_model)
    reranker = Reranker(settings.reranker_model)
    base = HybridRetriever(reranker=reranker)  # the normal index
    dense, bm25 = base.dense, base.bm25
    items = [i for i in load_questions() if i["gold_doc_ids"]]
    results = {}

    def run(name, retriever, raw=False, run_items=None):
        summary = retrieval_eval.run(retriever=retriever, raw=raw, items=run_items or items,
                                     name=f"ablation_{name}")  # fmt: skip
        results[name] = summary
        print(
            f"{name:<32} recall@10 {summary['all']['recall@10']:.3f}  mrr {summary['all']['mrr']:.3f}",
            flush=True,
        )

    if "retriever" in parts:
        for mode in ["dense", "bm25", "hybrid"]:
            run(f"{mode}_no_rerank", HybridRetriever(dense, bm25, reranker=None, mode=mode))
            run(f"{mode}_rerank", HybridRetriever(dense, bm25, reranker=reranker, mode=mode))

    if "chunking" in parts:
        f_dense, f_bm25 = build_index("fixed", embedder, chunker="fixed")
        run("structure_chunks", base)
        run("fixed_chunks", HybridRetriever(f_dense, f_bm25, reranker=reranker))

    if "header" in parts:
        h_dense, h_bm25 = build_index("header", embedder, context_header=True)
        run("no_header_raw", base, raw=True)
        run("context_header_raw", HybridRetriever(h_dense, h_bm25, reranker=reranker), raw=True)
        run("context_header_tool_filters", HybridRetriever(h_dense, h_bm25, reranker=reranker))

    if "versions" in parts:
        version_items = load_questions("eval/datasets/version_questions.jsonl")
        latest_only = [
            {**i, "as_of": None} for i in version_items
        ]  # same questions, no date filter
        run("version_aware", base, run_items=version_items)
        run("latest_only", base, run_items=latest_only)

    out = RUNS / "ablations_summary.json"
    old = json.loads(out.read_text()) if out.exists() else {}
    out.write_text(json.dumps({**old, **results}, indent=2))


if __name__ == "__main__":
    main()
