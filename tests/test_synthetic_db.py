import sqlite3

import pytest

from creatorops.synthetic_db import create_db


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "test.sqlite"
    create_db(path, seed=42)
    conn = sqlite3.connect(path)
    yield conn
    conn.close()


def count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_sizes_are_reasonable(db):
    assert count(db, "creators") == 8
    assert 1200 <= count(db, "posts") <= 1800
    assert count(db, "post_metrics_daily") == count(db, "posts") * 7
    assert count(db, "contracts_index") == count(db, "campaigns")


def test_same_seed_gives_same_data(tmp_path):
    a, b = tmp_path / "a.sqlite", tmp_path / "b.sqlite"
    create_db(a, seed=1)
    create_db(b, seed=1)
    query = "SELECT SUM(reach), SUM(likes) FROM post_metrics_daily"
    assert (
        sqlite3.connect(a).execute(query).fetchone() == sqlite3.connect(b).execute(query).fetchone()
    )


def test_planted_undisclosed_paid_posts(db):
    n = db.execute("SELECT COUNT(*) FROM posts WHERE is_paid = 1 AND has_disclosure = 0")
    assert n.fetchone()[0] == 2


def test_planted_viral_post_is_the_top_reel(db):
    top = db.execute(
        """SELECT a.creator_id FROM post_metrics_daily m
           JOIN posts p ON p.post_id = m.post_id
           JOIN accounts a ON a.account_id = p.account_id
           WHERE p.format = 'reel'
           GROUP BY m.post_id ORDER BY SUM(m.reach) DESC LIMIT 1"""
    ).fetchone()[0]
    assert top == 3
