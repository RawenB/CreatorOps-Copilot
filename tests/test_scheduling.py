import sqlite3

import pytest

from creatorops.synthetic_db import create_db
from creatorops.tools.scheduling import decide_approval, list_approvals, propose_schedule_post


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "db.sqlite"
    create_db(path, seed=42)
    return path


def schedule_count(db):
    return sqlite3.connect(db).execute("SELECT COUNT(*) FROM schedule").fetchone()[0]


def test_proposal_does_not_write_to_schedule(db):
    before = schedule_count(db)
    result = propose_schedule_post(1, "instagram", "2030-01-04 18:00", "Hello #ad", db_path=db)
    assert result["status"] == "pending_approval"
    assert result["creator_name"] == "Creator A"
    assert schedule_count(db) == before
    assert result["approval_id"] in [a["approval_id"] for a in list_approvals(db_path=db)]


def test_approved_proposal_is_scheduled(db):
    before = schedule_count(db)
    proposal = propose_schedule_post(2, "TikTok", "2030-01-04 18:00", "Hello", db_path=db)
    result = decide_approval(proposal["approval_id"], approved=True, db_path=db)
    assert result["decision"] == "approved"
    assert schedule_count(db) == before + 1


def test_rejected_proposal_is_not_scheduled(db):
    before = schedule_count(db)
    proposal = propose_schedule_post(2, "TikTok", "2030-01-04 18:00", "Hello", db_path=db)
    decide_approval(proposal["approval_id"], approved=False, db_path=db)
    assert schedule_count(db) == before


def test_cannot_decide_twice(db):
    proposal = propose_schedule_post(2, "TikTok", "2030-01-04 18:00", "Hello", db_path=db)
    decide_approval(proposal["approval_id"], approved=False, db_path=db)
    assert "error" in decide_approval(proposal["approval_id"], approved=True, db_path=db)


@pytest.mark.parametrize(
    "args",
    [
        (99, "Instagram", "2030-01-04 18:00", "x"),  # unknown creator
        (1, "Snapchat", "2030-01-04 18:00", "x"),  # unknown platform
        (1, "Instagram", "2020-01-04 18:00", "x"),  # past date
        (1, "Instagram", "next friday", "x"),  # bad date
        (1, "Instagram", "2030-01-04 18:00", "  "),  # empty caption
    ],
)
def test_invalid_requests_are_refused(db, args):
    assert "error" in propose_schedule_post(*args, db_path=db)
