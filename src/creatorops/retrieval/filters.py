"""Metadata filters applied in Python (used by BM25, same rules as the Qdrant filter)."""


def matches(
    chunk: dict,
    platform: str | None = None,
    doc_type: str | None = None,
    doc_id: str | None = None,
    as_of: str | None = None,
    latest_only: bool = True,
) -> bool:
    if platform and chunk.get("platform") not in (platform, "all"):
        return False
    if doc_type and chunk.get("doc_type") != doc_type:
        return False
    if doc_id and chunk.get("doc_id") != doc_id:
        return False
    if as_of:
        # dates are YYYY-MM-DD strings, so comparing strings works
        valid_from = chunk.get("valid_from") or ""
        valid_to = chunk.get("valid_to")
        if valid_from > as_of:
            return False
        if valid_to and valid_to <= as_of:
            return False
    elif latest_only and not chunk.get("is_latest"):
        return False
    return True
