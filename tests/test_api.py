import pytest
from fastapi.testclient import TestClient

from creatorops.agent.graph import Copilot
from creatorops.api.main import create_app
from creatorops.llm.client import FakeLLM

pytestmark = pytest.mark.usefixtures("tiny_corpus")


@pytest.fixture
def client():
    return TestClient(create_app(copilot=Copilot(llm=FakeLLM())))


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_chat_returns_answer_with_sources(client):
    data = client.post("/chat", json={"question": "Do I need a paid partnership label?"}).json()
    assert data["status"] == "done"
    assert data["citations"] == [1]
    assert data["sources"][0]["doc_id"] == "bc"


def test_schedule_through_chat_and_approval_endpoint(client):
    data = client.post("/chat", json={"question": "Schedule a post for Creator A"}).json()
    assert data["status"] == "waiting_approval"
    approval_id = data["pending_approval"]["approval_id"]
    assert approval_id in [a["approval_id"] for a in client.get("/approvals").json()]

    before = len(client.get("/schedule").json())
    data = client.post(f"/approvals/{approval_id}/decision", json={"approved": True}).json()
    assert data["status"] == "done"
    assert len(client.get("/schedule").json()) == before + 1
    assert approval_id not in [a["approval_id"] for a in client.get("/approvals").json()]


def test_decide_seeded_approval_without_chat(client):
    pending = client.get("/approvals").json()
    response = client.post(f"/approvals/{pending[0]['approval_id']}/decision",
                           json={"approved": False})  # fmt: skip
    assert response.json()["approval"]["decision"] == "rejected"


def test_sql_endpoint_is_read_only(client):
    assert "rows" in client.post("/sql", json={"query": "SELECT name FROM creators"}).json()
    assert "error" in client.post("/sql", json={"query": "DELETE FROM creators"}).json()


def test_document_endpoint_returns_versions_and_text(client):
    data = client.get("/documents/bc").json()
    assert data["version"] == 2
    assert [v["version"] for v in data["versions"]] == [1, 2]
    assert "paid partnership" in data["text"]
    old = client.get("/documents/bc?version=1").json()
    assert "#ad" in old["text"]
    assert client.get("/documents/nope").status_code == 404
