import sqlite3

import pytest

from creatorops.synthetic_db import create_db
from creatorops.tools.sql import explain_schema, run_sql


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    path = tmp_path_factory.mktemp("sql") / "test.sqlite"
    create_db(path, seed=42)
    # a table that exists in the file but is NOT in the allowlist
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE secrets (value TEXT)")
    conn.execute("INSERT INTO secrets VALUES ('top secret')")
    conn.commit()
    conn.close()
    return path


def test_simple_select_works(db):
    result = run_sql("SELECT name, niche FROM creators ORDER BY creator_id", db_path=db)
    assert result["columns"] == ["name", "niche"]
    assert result["rows"][0] == ["Creator A", "fashion"]


def test_join_and_cte_work(db):
    query = """
        WITH reach AS (
            SELECT p.account_id, SUM(m.reach) AS total
            FROM posts p JOIN post_metrics_daily m ON m.post_id = p.post_id
            GROUP BY p.account_id
        )
        SELECT a.handle, r.total FROM reach r JOIN accounts a USING (account_id)
        ORDER BY r.total DESC LIMIT 3
    """
    result = run_sql(query, db_path=db)
    assert "error" not in result
    assert result["row_count"] == 3


def test_row_limit(db):
    result = run_sql("SELECT * FROM post_metrics_daily", db_path=db, max_rows=10)
    assert result["row_count"] == 10
    assert result["truncated"] is True


@pytest.mark.parametrize(
    "query",
    [
        "DELETE FROM creators",
        "UPDATE creators SET name = 'x'",
        "INSERT INTO schedule VALUES (99, 1, 1, '2026-12-01', 'x', 'approved', '2026-11-01')",
        "DROP TABLE posts",
        "SELECT * FROM creators; DROP TABLE posts",
        "PRAGMA table_info(creators)",
        "ATTACH DATABASE '/tmp/x.db' AS x",
        "SELECT * FROM secrets",
        "SELECT * FROM sqlite_master",
        "WITH x AS (SELECT 1) DELETE FROM creators",
        "",
    ],
)
def test_unsafe_queries_are_rejected(db, query):
    result = run_sql(query, db_path=db)
    assert "error" in result
    assert sqlite3.connect(db).execute("SELECT COUNT(*) FROM creators").fetchone()[0] == 8


def test_slow_query_times_out(db):
    query = "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n) SELECT COUNT(*) FROM n"
    result = run_sql(query, db_path=db, timeout_s=0.5)
    assert "longer than" in result["error"]


def test_explain_schema_lists_allowed_tables_only(db):
    schema = explain_schema(db_path=db)
    assert "posts" in schema["tables"]
    assert "secrets" not in schema["tables"]
    assert "is_paid" in schema["tables"]["posts"]["columns"]
