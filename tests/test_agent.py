"""Agent graph tests with the fake LLM (no Ollama needed)."""

import sqlite3

import pytest

from creatorops.agent.citations import cited_numbers, verify
from creatorops.agent.graph import Copilot
from creatorops.agent.router import keyword_route
from creatorops.config import settings
from creatorops.llm.client import FakeLLM

pytestmark = pytest.mark.usefixtures("tiny_corpus")


def schedule_count():
    return sqlite3.connect(settings.db_path).execute("SELECT COUNT(*) FROM schedule").fetchone()[0]


def test_policy_question_is_answered_with_a_valid_citation():
    result = Copilot(llm=FakeLLM()).ask("Do I need a paid partnership label on Instagram?")
    assert result["status"] == "done"
    assert result["route"] == "policy"
    assert [c["name"] for c in result["tool_calls"]] == ["search_policies"]
    assert result["citations"] == [1]
    assert not result["abstained"]


def test_out_of_scope_question_is_refused_without_tools():
    result = Copilot(llm=FakeLLM()).ask("What is the capital of Australia?")
    assert result["route"] == "out_of_scope"
    assert result["abstained"] is True
    assert result["tool_calls"] == []


def test_schedule_stops_for_approval_and_writes_only_after_yes():
    copilot = Copilot(llm=FakeLLM())
    before = schedule_count()

    result = copilot.ask("Schedule a post for Creator A on Instagram")
    assert result["status"] == "waiting_approval"
    assert result["pending_approval"]["creator_name"] == "Creator A"
    assert schedule_count() == before  # nothing written yet

    result = copilot.resume(result["thread_id"], approved=True)
    assert result["status"] == "done"
    assert result["approval"]["decision"] == "approved"
    assert schedule_count() == before + 1


def test_rejected_schedule_writes_nothing():
    copilot = Copilot(llm=FakeLLM())
    before = schedule_count()
    result = copilot.ask("Schedule a post for Creator A on Instagram")
    result = copilot.resume(result["thread_id"], approved=False)
    assert result["approval"]["decision"] == "rejected"
    assert schedule_count() == before


def test_without_router_all_tools_are_offered():
    llm = FakeLLM()
    Copilot(llm=llm, use_router=False).ask("Do I need a label?")
    assert len(llm.calls) == 2  # no router call: agent call + final answer


def test_keyword_router():
    assert keyword_route("Schedule this for Friday") == "action"
    assert keyword_route("Is contract C003 exclusive?") == "contract"
    assert keyword_route("Which creator had the best reach?") == "sql"
    assert keyword_route("Best reach creator, and is that allowed by the policy?") == "hybrid"
    assert keyword_route("Tell me a joke") == "out_of_scope"


def test_citation_check_removes_made_up_numbers():
    sources = [{"n": 1}, {"n": 2}]
    check = verify("Label it [1]. Also [7] and [2, 9].", sources, "policy")
    assert check["citations"] == [1, 2]
    assert check["invalid_citations"] == [7, 9]
    assert "[7]" not in check["answer"] and "[2]" in check["answer"]


def test_citation_check_abstention_rules():
    assert verify("I don't know based on the sources.", [{"n": 1}], "policy")["abstained"]
    assert verify("Some answer.", [], "sql")["abstained"]
    check = verify("An answer without citation.", [{"n": 1}], "policy")
    assert check["unverified"] and not check["abstained"]
    assert cited_numbers("a [3] b [1,3]") == [3, 1]


def test_citing_an_empty_sql_result_is_not_valid():
    sources = [{"n": 1, "kind": "sql", "rows": []}]
    check = verify("Creator A had 12.5% [1].", sources, "sql")
    assert check["citations"] == []
    assert check["invalid_citations"] == [1]
    assert check["abstained"] is True


def test_partial_answer_with_citation_is_not_an_abstention():
    answer = "C007 is non-exclusive [1]. The renewal is not mentioned in the clauses."
    assert verify(answer, [{"n": 1}], "contract")["abstained"] is False
