"""Numbers for the Analytics page (read-only, computed from the analytics database).

Where the data comes from: the database is SYNTHETIC. scripts/generate_analytics_db.py creates
8 creators, their accounts, ~1,400 posts (May-Oct 2026), daily metrics, campaigns and contracts with
a fixed seed. Real Instagram / TikTok data would need the platforms' business APIs (see docs/data_card.md).

Engagement rate = (likes + comments + shares + saves) / reach, like in the reporting SOP.
"""

import sqlite3
import statistics

from creatorops.config import settings

ER = "1.0 * SUM(m.likes + m.comments + m.shares + m.saves) / NULLIF(SUM(m.reach), 0)"
POSTS = ("FROM posts p JOIN accounts a ON a.account_id = p.account_id "
         "JOIN creators c ON c.creator_id = a.creator_id JOIN platforms pl ON pl.platform_id = a.platform_id")  # fmt: skip
METRICS = "JOIN post_metrics_daily m ON m.post_id = p.post_id"


def connect(db_path=None):
    conn = sqlite3.connect(f"file:{db_path or settings.db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def rows(conn, query, params=()) -> list[dict]:
    return [dict(r) for r in conn.execute(query, params).fetchall()]


def where(platform: str | None) -> tuple[str, tuple]:
    return ("WHERE pl.name = ?", (platform,)) if platform else ("", ())


def dashboard(platform: str | None = None, db_path=None) -> dict:
    """Everything the Analytics page shows. platform: Instagram, TikTok, YouTube or None (all)."""
    conn = connect(db_path)
    w, p = where(platform)
    and_w = w.replace("WHERE", "AND") if w else ""

    kpis = rows(conn, f"""
        SELECT COUNT(DISTINCT c.creator_id) AS creators, COUNT(DISTINCT p.post_id) AS posts,
               SUM(m.reach) AS reach, SUM(m.impressions) AS impressions, {ER} AS engagement_rate,
               MIN(p.posted_at) AS first_post, MAX(p.posted_at) AS last_post
        {POSTS} {METRICS} {w}""", p)[0]  # fmt: skip
    kpis.update(rows(conn, f"""
        SELECT SUM(p.is_paid) AS paid_posts, SUM(p.is_paid = 1 AND p.has_disclosure = 0) AS undisclosed_paid
        {POSTS} {w}""", p)[0])  # fmt: skip

    monthly = rows(conn, f"""
        SELECT substr(p.posted_at, 1, 7) AS month, COUNT(DISTINCT p.post_id) AS posts,
               SUM(m.reach) AS reach, {ER} AS engagement_rate
        {POSTS} {METRICS} {w} GROUP BY month ORDER BY month""", p)  # fmt: skip

    creators = rows(conn, f"""
        SELECT c.creator_id, c.name, c.niche, c.country, COUNT(DISTINCT p.post_id) AS posts,
               SUM(m.reach) AS reach, {ER} AS engagement_rate
        {POSTS} {METRICS} {w} GROUP BY c.creator_id ORDER BY reach DESC""", p)  # fmt: skip
    followers = rows(conn, "SELECT a.creator_id, pl.name AS platform, a.followers FROM accounts a "
                           "JOIN platforms pl ON pl.platform_id = a.platform_id")  # fmt: skip
    for c in creators:
        c["followers"] = {
            f["platform"]: f["followers"] for f in followers if f["creator_id"] == c["creator_id"]
        }

    formats = rows(conn, f"""
        SELECT p.format, COUNT(DISTINCT p.post_id) AS posts, SUM(m.reach) * 1.0 / COUNT(DISTINCT p.post_id) AS avg_reach,
               {ER} AS engagement_rate
        {POSTS} {METRICS} {w} GROUP BY p.format ORDER BY engagement_rate DESC""", p)  # fmt: skip

    anomalies = find_anomalies(conn, and_w, p)
    conn.close()
    return {
        "platform": platform,
        "source": {
            "type": "synthetic",
            "generator": "scripts/generate_analytics_db.py",
            "seed": settings.seed,
            "note": "Generated data for the project (fictional creators and brands), not real platform metrics.",
        },
        "kpis": kpis,
        "monthly": monthly,
        "creators": creators,
        "formats": formats,
        "anomalies": anomalies,
    }


def find_anomalies(conn, and_where: str, params: tuple) -> list[dict]:
    """Simple rules a human would check in a report. Each one comes with a suggested ticket."""
    found = []

    # 1. paid posts without a disclosure
    for r in rows(conn, f"""SELECT p.post_id, c.name, pl.name AS platform, p.posted_at {POSTS}
                            WHERE p.is_paid = 1 AND p.has_disclosure = 0 {and_where}""", params):  # fmt: skip
        found.append({
            "kind": "undisclosed_paid_post", "severity": "high", "creator": r["name"], "date": r["posted_at"][:10],
            "text": f"Paid post {r['post_id']} by {r['name']} on {r['platform']} has no disclosure.",
            "ticket": {"title": f"Add a disclosure to post {r['post_id']} ({r['name']})", "priority": "high",
                       "reference_type": "post", "reference_id": str(r["post_id"]),
                       "description": "Paid post without #ad / paid partnership label (FTC, agency SOP section 3)."},
        })  # fmt: skip

    # 2. likes jump much more than reach: likes / reach far above the creator's normal ratio
    #    (sign of bought likes, reporting SOP 3.2)
    daily = rows(conn, f"""SELECT c.name, m.day, SUM(m.likes) AS likes, SUM(m.reach) AS reach {POSTS} {METRICS}
                           WHERE 1 = 1 {and_where} GROUP BY c.name, m.day""", params)  # fmt: skip
    by_creator = {}
    for d in daily:
        by_creator.setdefault(d["name"], []).append(d)
    for name, days in by_creator.items():
        median_likes = statistics.median(d["likes"] for d in days) or 1
        median_ratio = statistics.median(d["likes"] / d["reach"] for d in days if d["reach"]) or 1
        for d in days:
            ratio = d["likes"] / d["reach"] if d["reach"] else 0
            if d["likes"] > 5 * median_likes and ratio > 4 * median_ratio:
                found.append({
                    "kind": "likes_spike", "severity": "high", "creator": name, "date": d["day"],
                    "text": f"{name}: {d['likes']:,} likes on {d['day']} ({d['likes'] / median_likes:.0f}x a normal day) "
                            f"while reach stayed normal (likes/reach {ratio:.2f} vs {median_ratio:.2f} usually). Possible fake likes.",
                    "ticket": {"title": f"Check the likes spike of {name} on {d['day']}", "priority": "high",
                               "reference_type": "creator", "reference_id": name,
                               "description": "Flag it in the campaign report, do not report it as a success (reporting SOP 3.2)."},
                })  # fmt: skip

    # 3. viral posts (reach > 5x the creator's median post reach)
    posts = rows(conn, f"""SELECT p.post_id, c.name, p.format, p.posted_at, SUM(m.reach) AS reach {POSTS} {METRICS}
                           WHERE 1 = 1 {and_where} GROUP BY p.post_id""", params)  # fmt: skip
    by_creator = {}
    for post in posts:
        by_creator.setdefault(post["name"], []).append(post)
    for name, items in by_creator.items():
        median = statistics.median(x["reach"] for x in items) or 1
        for x in items:
            if x["reach"] > 5 * median:
                found.append({
                    "kind": "viral_post", "severity": "info", "creator": name, "date": x["posted_at"][:10],
                    "text": f"{name}'s {x['format']} (post {x['post_id']}) reached {x['reach']:,}, {x['reach'] / median:.0f}x their usual post.",
                    "ticket": {"title": f"Use post {x['post_id']} ({name}) as a case study for brands", "priority": "low",
                               "reference_type": "post", "reference_id": str(x["post_id"]), "description": ""},
                })  # fmt: skip

    # 4. month-to-month reach drop of more than 25%
    monthly = rows(conn, f"""SELECT c.name, substr(p.posted_at, 1, 7) AS month, SUM(m.reach) AS reach {POSTS} {METRICS}
                             WHERE 1 = 1 {and_where} GROUP BY c.name, month ORDER BY c.name, month""", params)  # fmt: skip
    for prev, cur in zip(monthly, monthly[1:]):
        if prev["name"] == cur["name"] and prev["reach"] and cur["reach"] < 0.75 * prev["reach"]:
            drop = 1 - cur["reach"] / prev["reach"]
            found.append({
                "kind": "reach_drop", "severity": "medium", "creator": cur["name"], "date": cur["month"],
                "text": f"{cur['name']}: reach of {cur['month']} posts is {drop:.0%} lower than {prev['month']}.",
                "ticket": {"title": f"Look into the reach drop of {cur['name']} in {cur['month']}", "priority": "medium",
                           "reference_type": "creator", "reference_id": cur["name"], "description": ""},
            })  # fmt: skip

    order = {"high": 0, "medium": 1, "info": 2}
    return sorted(found, key=lambda a: (order[a["severity"]], a["date"]))
