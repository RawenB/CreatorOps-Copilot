"""Policy tools: search platform rules / regulations, and compare two versions of a policy."""

import difflib

from creatorops.config import settings
from creatorops.ingestion.chunking import find_sections
from creatorops.ingestion.parsers import parse_file
from creatorops.tools.common import get_registry, get_retriever, to_source

POLICY_TYPES = ["platform_policy", "regulation", "sop"]


def search_policies(
    query: str,
    platform: str | None = None,
    as_of: str | None = None,
    top_k: int = 5,
) -> dict:
    """Search platform policies, advertising regulations and agency SOPs.

    platform: "instagram", "tiktok" or "youtube" (regulations that apply everywhere are included).
    as_of: "YYYY-MM-DD" to get the rules that were valid on that date (default: latest rules).
    """
    results = get_retriever().search(
        query, top_k=top_k, doc_type=POLICY_TYPES, platform=platform, as_of=as_of
    )
    return {
        "query": query,
        "platform": platform,
        "as_of": as_of,
        "sources": [to_source(r) for r in results],
    }


def section_texts(file_path: str) -> dict[str, str]:
    text = parse_file(settings.data_dir / file_path)
    return {path or "(intro)": text[start:end].strip() for path, start, end in find_sections(text)}


def compare_policy_versions(
    topic: str,
    platform: str | None = None,
    doc_id: str | None = None,
    max_changes: int = 8,
) -> dict:
    """Compare the two most recent versions of a policy document, section by section.

    If doc_id is not given, the policy is chosen by searching `topic` among documents that
    have more than one version.
    """
    registry = get_registry()

    if doc_id is None:
        candidates = get_retriever().search(
            topic, top_k=20, doc_type=POLICY_TYPES, platform=platform, latest_only=False
        )
        for c in candidates:
            if len(registry.versions(c["doc_id"])) > 1:
                doc_id = c["doc_id"]
                break
        if doc_id is None:
            return {"error": "No policy with several versions matches this topic.", "topic": topic}

    versions = registry.versions(doc_id)
    if len(versions) < 2:
        return {"doc_id": doc_id, "error": "Only one version of this document is stored."}

    old_v, new_v = versions[-2][0], versions[-1][0]
    old_chunk = registry.first_chunk(doc_id, old_v)
    new_chunk = registry.first_chunk(doc_id, new_v)
    old_sections = section_texts(old_chunk["file_path"])
    new_sections = section_texts(new_chunk["file_path"])

    changes = []
    for name in new_sections.keys() - old_sections.keys():
        changes.append({"section": name, "change": "added", "new_text": new_sections[name][:600]})
    for name in old_sections.keys() - new_sections.keys():
        changes.append({"section": name, "change": "removed", "old_text": old_sections[name][:600]})
    for name in new_sections.keys() & old_sections.keys():
        old, new = old_sections[name], new_sections[name]
        if old != new:
            diff = difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=0)
            lines = [d for d in diff if d[:1] in "+-" and d[:3] not in ("+++", "---")]
            changes.append({"section": name, "change": "modified", "diff": lines[:20]})

    # sections that talk about the topic first
    topic_words = [w for w in topic.lower().split() if len(w) > 3]

    def relevance(change):
        text = " ".join(str(v) for v in change.values()).lower()
        return sum(text.count(w) for w in topic_words)

    changes.sort(key=relevance, reverse=True)
    return {
        "doc_id": doc_id,
        "title": new_chunk["title"],
        "old_version": {"version": old_v, "snapshot_date": old_chunk["snapshot_date"]},
        "new_version": {"version": new_v, "snapshot_date": new_chunk["snapshot_date"]},
        "n_changes": len(changes),
        "changes": changes[:max_changes],
    }
