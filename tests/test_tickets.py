import pytest
from fastapi.testclient import TestClient

from creatorops.agent.graph import Copilot
from creatorops.api.main import create_app
from creatorops.llm.client import FakeLLM
from creatorops.tools import tickets
from creatorops.tools.analytics import dashboard
from creatorops.tools.scheduling import decide_approval, propose_schedule_post

pytestmark = pytest.mark.usefixtures("tiny_corpus")


def test_task_with_reference_and_link():
    t = tickets.create_task("Fix the disclosure", priority="high", link="https://drive.example.com/x",
                            reference_type="contract", reference_id="c003")  # fmt: skip
    assert t["code"] == f"TCK-{t['ticket_id']:04d}"
    assert t["status"] == "open"
    assert t["reference_id"] == "C003"
    assert t["reference_label"].startswith("Contract C003")
    assert t["reference_doc_id"] == "synthetic_contract_003"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"title": " "},
        {"title": "x", "link": "drive.example.com/no-scheme"},
        {"title": "x", "reference_type": "contract", "reference_id": "C999"},
        {"title": "x", "reference_type": "post", "reference_id": "999999"},
        {"title": "x", "reference_type": "planet", "reference_id": "Mars"},
        {"title": "x", "priority": "urgent"},
    ],
)
def test_invalid_tasks_are_refused(kwargs):
    assert "error" in tickets.create_task(**kwargs)


def test_every_schedule_request_opens_a_ticket_that_follows_the_approval():
    result = propose_schedule_post("Creator A", "Instagram", "2030-01-04 18:00", "Hi #ad",
                                   link="https://example.com/video", reference_type="campaign",
                                   reference_id="1")  # fmt: skip
    ticket = tickets.get_ticket(result["ticket_id"])
    assert ticket["kind"] == "post_request" and ticket["status"] == "pending"
    assert ticket["link"] == "https://example.com/video"
    assert "error" in tickets.update_ticket(ticket["ticket_id"], status="done")  # only via approval
    decide_approval(result["approval_id"], approved=True)
    assert tickets.get_ticket(result["ticket_id"])["status"] == "approved"


def test_task_status_can_change():
    t = tickets.create_task(
        "Check the likes spike", reference_type="creator", reference_id="creator f"
    )
    assert t["reference_label"] == "Creator F"
    assert tickets.update_ticket(t["ticket_id"], status="in_progress")["status"] == "in_progress"
    assert "error" in tickets.update_ticket(t["ticket_id"], status="closed")


def test_analytics_dashboard_finds_the_planted_anomalies():
    data = dashboard()
    assert data["source"]["type"] == "synthetic"
    assert data["kpis"]["creators"] == 8
    kinds = {a["kind"] for a in data["anomalies"]}
    assert {"undisclosed_paid_post", "likes_spike", "viral_post"} <= kinds
    spike = next(a for a in data["anomalies"] if a["kind"] == "likes_spike")
    assert spike["creator"] == "Creator F" and spike["date"] == "2026-08-12"
    assert dashboard("TikTok")["kpis"]["posts"] < data["kpis"]["posts"]


def test_ticket_api():
    client = TestClient(create_app(copilot=Copilot(llm=FakeLLM())))
    task = client.post("/tickets", json={"title": "Review C003", "reference_type": "contract",
                                         "reference_id": "C003"}).json()  # fmt: skip
    assert task["code"].startswith("TCK-")
    assert (
        client.patch(f"/tickets/{task['ticket_id']}", json={"status": "done"}).json()["status"]
        == "done"
    )
    assert client.post("/tickets", json={"title": "x", "link": "not a url"}).status_code == 400

    post = client.post("/tickets", json={"kind": "post_request", "creator": "Creator B", "platform": "TikTok",
                                         "post_datetime": "2030-02-01 18:00", "caption": "#ad hi"}).json()  # fmt: skip
    assert post["status"] == "pending"
    assert post["approval_id"] in [a["approval_id"] for a in client.get("/approvals").json()]
    assert len(client.get("/tickets?kind=task").json()) >= 1
    assert client.get("/analytics").json()["kpis"]["posts"] > 0


def test_ticket_created_by_the_agent_is_a_ticket_source():
    from creatorops.agent.tools import call_read_tool, format_for_llm, result_to_sources

    result = call_read_tool("create_ticket", {"title": "Check post 166", "reference_type": "post",
                                              "reference_id": "166"})  # fmt: skip
    sources = result_to_sources("create_ticket", result, 1)
    assert sources[0]["kind"] == "ticket" and sources[0]["created_by"] == "assistant"
    assert result["code"] in format_for_llm("create_ticket", result, sources)
