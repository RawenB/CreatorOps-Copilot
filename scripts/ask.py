"""Ask the agent a question from the command line.

Usage: uv run python scripts/ask.py "Do I need to label a paid partnership on Instagram?"
If the agent wants to schedule a post, you are asked to approve it here.
"""

import json
import sys

from creatorops.agent.graph import Copilot


def show(result: dict) -> None:
    print(f"\nroute: {result['route']} | tools: {[c['name'] for c in result['tool_calls']]} "
          f"| {result['latency_s']}s | {result['usage']}")  # fmt: skip
    if result["status"] == "waiting_approval":
        print("\nAPPROVAL NEEDED:\n" + json.dumps(result["pending_approval"], indent=2))
        return
    print("\n" + result["answer"])
    for s in result["sources"]:
        if s["n"] in result["citations"]:
            if s["kind"] == "sql":
                print(f"  [{s['n']}] SQL: {s['query']}")
            elif s["kind"] == "comparison":
                print(f"  [{s['n']}] comparison of {s['title']}")
            else:
                print(f"  [{s['n']}] {s['title']} | {s.get('section')} | {s.get('snapshot_date')}")
    if result["unverified"]:
        print("  (warning: the answer cites no source)")


copilot = Copilot()
result = copilot.ask(sys.argv[1])
show(result)
while result["status"] == "waiting_approval":
    approved = input("\nApprove? [y/N] ").strip().lower() == "y"
    result = copilot.resume(result["thread_id"], approved=approved)
    show(result)
