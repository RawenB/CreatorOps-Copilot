"""Policy and contract tools on a tiny corpus (fake embedder, no models)."""

import pytest

from creatorops.tools.contracts import find_clause
from creatorops.tools.policies import compare_policy_versions, search_policies

pytestmark = pytest.mark.usefixtures("tiny_corpus")


def test_search_policies_returns_latest_rules_with_citation_fields():
    result = search_policies("paid partnership label", platform="instagram", top_k=3)
    sources = result["sources"]
    assert sources and all(s["doc_type"] != "contract" for s in sources)
    assert all(s["version"] == 2 for s in sources)
    assert {"source_id", "title", "section", "snapshot_date", "text"} <= sources[0].keys()


def test_search_policies_as_of_returns_old_rules():
    result = search_policies("sponsored post caption", as_of="2025-01-01")
    assert {s["version"] for s in result["sources"]} == {1}


def test_compare_policy_versions_finds_changed_and_added_sections():
    result = compare_policy_versions("disclosure", doc_id="bc")
    assert result["old_version"]["snapshot_date"] == "2024-01-01"
    changes = {c["section"]: c["change"] for c in result["changes"]}
    assert changes["Branded content > Disclosure"] == "modified"
    assert changes["Branded content > Alcohol"] == "added"


def test_compare_with_single_version_says_so():
    assert "error" in compare_policy_versions("exclusivity", doc_id="contract_x")


def test_find_clause_puts_matching_clause_type_first():
    result = find_clause("exclusivity", contract_id="contract_x", top_k=2)
    assert result["sources"][0]["clause_type"] == "exclusivity"


def test_find_clause_rejects_unknown_type():
    assert "error" in find_clause("pizza")
