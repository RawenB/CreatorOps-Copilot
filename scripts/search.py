"""Search the corpus from the command line.

Examples:
  uv run python scripts/search.py "do I need to label a paid partnership?"
  uv run python scripts/search.py "branded content rules" --platform tiktok --as-of 2024-01-01
  uv run python scripts/search.py "exclusivity competitor" --doc-type contract -k 3
"""

import argparse

from creatorops.retrieval.dense import DenseRetriever, format_citation

parser = argparse.ArgumentParser()
parser.add_argument("query")
parser.add_argument("-k", "--top-k", type=int, default=5)
parser.add_argument("--platform", help="instagram, tiktok or youtube")
parser.add_argument("--doc-type", help="platform_policy, regulation, contract or sop")
parser.add_argument("--as-of", help="YYYY-MM-DD: search the versions valid on that date")
parser.add_argument("--all-versions", action="store_true")
args = parser.parse_args()

retriever = DenseRetriever()
results = retriever.search(
    args.query,
    top_k=args.top_k,
    platform=args.platform,
    doc_type=args.doc_type,
    as_of=args.as_of,
    latest_only=not args.all_versions,
)

for i, r in enumerate(results, start=1):
    print(f"\n[{i}] score={r['score']:.3f}  {format_citation(r)}")
    print("    " + r["text"][:300].replace("\n", " ") + "...")
