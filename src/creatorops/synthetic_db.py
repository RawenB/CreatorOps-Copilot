"""Generate the synthetic analytics database (SQLite).

Everything here is fake: 8 made-up creators, fictional brands, ~1500 posts over 6 months
(May to October 2026) with daily metrics for the first 7 days of each post.

A few anomalies are planted on purpose so analytics questions are interesting:
- one viral Reel (creator 3, around 15x the normal reach)
- a fake-engagement spike: likes but almost no reach (creator 6, 2026-08-12)
- an August slump for creator 5 (reach about 40% lower)
- two paid posts without a disclosure label (compliance problem)
"""

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

START = date(2026, 5, 1)
END = date(2026, 10, 31)
METRIC_DAYS = 7

SCHEMA = """
CREATE TABLE platforms (
    platform_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE creators (
    creator_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    niche TEXT NOT NULL,
    country TEXT NOT NULL,
    joined_agency_at TEXT NOT NULL
);
CREATE TABLE accounts (
    account_id INTEGER PRIMARY KEY,
    creator_id INTEGER NOT NULL REFERENCES creators(creator_id),
    platform_id INTEGER NOT NULL REFERENCES platforms(platform_id),
    handle TEXT NOT NULL,
    followers INTEGER NOT NULL
);
CREATE TABLE brands (
    brand_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL
);
CREATE TABLE campaigns (
    campaign_id INTEGER PRIMARY KEY,
    brand_id INTEGER NOT NULL REFERENCES brands(brand_id),
    creator_id INTEGER NOT NULL REFERENCES creators(creator_id),
    name TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    budget_usd INTEGER NOT NULL
);
CREATE TABLE posts (
    post_id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(account_id),
    campaign_id INTEGER REFERENCES campaigns(campaign_id),
    posted_at TEXT NOT NULL,
    format TEXT NOT NULL,
    caption TEXT NOT NULL,
    is_paid INTEGER NOT NULL,
    has_disclosure INTEGER NOT NULL
);
CREATE TABLE post_metrics_daily (
    post_id INTEGER NOT NULL REFERENCES posts(post_id),
    day TEXT NOT NULL,
    impressions INTEGER NOT NULL,
    reach INTEGER NOT NULL,
    views INTEGER NOT NULL,
    likes INTEGER NOT NULL,
    comments INTEGER NOT NULL,
    shares INTEGER NOT NULL,
    saves INTEGER NOT NULL,
    PRIMARY KEY (post_id, day)
);
CREATE TABLE schedule (
    schedule_id INTEGER PRIMARY KEY,
    creator_id INTEGER NOT NULL REFERENCES creators(creator_id),
    platform_id INTEGER NOT NULL REFERENCES platforms(platform_id),
    scheduled_at TEXT NOT NULL,
    caption TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE approvals (
    approval_id INTEGER PRIMARY KEY,
    schedule_id INTEGER REFERENCES schedule(schedule_id),
    action TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    decision TEXT,
    decided_at TEXT,
    decided_by TEXT
);
CREATE TABLE contracts_index (
    contract_id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    creator_id INTEGER NOT NULL REFERENCES creators(creator_id),
    brand_id INTEGER NOT NULL REFERENCES brands(brand_id),
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    fee_usd INTEGER NOT NULL,
    exclusivity INTEGER NOT NULL,
    exclusivity_category TEXT
);
"""

PLATFORMS = ["Instagram", "TikTok", "YouTube"]

# (name, niche, country, base followers on Instagram)
CREATORS = [
    ("Creator A", "fashion", "FR", 120_000),
    ("Creator B", "beauty", "UK", 85_000),
    ("Creator C", "fitness", "US", 240_000),
    ("Creator D", "food", "TN", 45_000),
    ("Creator E", "travel", "ES", 160_000),
    ("Creator F", "gaming", "US", 310_000),
    ("Creator G", "lifestyle", "DE", 60_000),
    ("Creator H", "tech", "FR", 95_000),
]

# (name, category) - all brand names are invented
BRANDS = [
    ("Lumea Skin", "beauty"),
    ("Northpeak Apparel", "fashion"),
    ("FitFuel Nutrition", "supplements"),
    ("Casa Verde Foods", "food"),
    ("Orbit Audio", "tech"),
    ("Wanderly Travel", "travel"),
    ("PixelForge Games", "gaming"),
    ("Silverline Spirits", "alcohol"),
    ("Glow Theory", "beauty"),
    ("Stride Athletics", "fashion"),
]

FORMATS = {
    "Instagram": ["reel", "photo", "carousel", "story"],
    "TikTok": ["video"],
    "YouTube": ["video", "short"],
}

# how much reach a format gets compared to the account's followers
FORMAT_REACH = {
    "reel": 0.45,
    "photo": 0.18,
    "carousel": 0.25,
    "story": 0.10,
    "video": 0.35,
    "short": 0.40,
}

# how many of the people reached engage (likes + comments + ...)
FORMAT_ENGAGEMENT = {
    "reel": 0.060,
    "photo": 0.045,
    "carousel": 0.055,
    "story": 0.020,
    "video": 0.050,
    "short": 0.045,
}

CAPTION_TEMPLATES = [
    "New {niche} look for the week, what do you think?",
    "Behind the scenes of today's {niche} shoot",
    "3 {niche} tips I wish I knew earlier",
    "Q&A time! Ask me anything about {niche}",
    "My honest {niche} routine, no filter",
    "Weekend vibes and a little {niche} inspiration",
]


def season_factor(day: date) -> float:
    """Summer is a bit stronger, September a bit weaker."""
    return {5: 1.0, 6: 1.08, 7: 1.15, 8: 1.05, 9: 0.92, 10: 1.0}[day.month]


def create_db(db_path: Path, seed: int = 42) -> None:
    """Create the database at db_path (overwrites it if it exists)."""
    rng = np.random.default_rng(seed)
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)

    for i, name in enumerate(PLATFORMS, start=1):
        conn.execute("INSERT INTO platforms VALUES (?, ?)", (i, name))

    for i, (name, category) in enumerate(BRANDS, start=1):
        conn.execute("INSERT INTO brands VALUES (?, ?, ?)", (i, name, category))

    # creators and their accounts (every creator has Instagram + TikTok, half have YouTube)
    accounts = []  # (account_id, creator_id, platform name, followers)
    account_id = 1
    for creator_id, (name, niche, country, ig_followers) in enumerate(CREATORS, start=1):
        joined = START - timedelta(days=int(rng.integers(60, 700)))
        conn.execute(
            "INSERT INTO creators VALUES (?, ?, ?, ?, ?)",
            (creator_id, name, niche, country, joined.isoformat()),
        )
        followers_per_platform = {
            "Instagram": ig_followers,
            "TikTok": int(ig_followers * rng.uniform(0.5, 1.6)),
            "YouTube": int(ig_followers * rng.uniform(0.2, 0.6)),
        }
        platforms = ["Instagram", "TikTok"] + (["YouTube"] if creator_id % 2 == 0 else [])
        for platform in platforms:
            handle = "@" + name.lower().replace(" ", "_") + "_" + platform[:2].lower()
            followers = followers_per_platform[platform]
            conn.execute(
                "INSERT INTO accounts VALUES (?, ?, ?, ?, ?)",
                (account_id, creator_id, PLATFORMS.index(platform) + 1, handle, followers),
            )
            accounts.append((account_id, creator_id, platform, followers))
            account_id += 1

    # campaigns: each creator gets 2-3 brand campaigns
    campaigns = []  # (campaign_id, creator_id, start, end)
    campaign_id = 1
    for creator_id in range(1, len(CREATORS) + 1):
        for _ in range(int(rng.integers(2, 4))):
            brand_id = int(rng.integers(1, len(BRANDS) + 1))
            start = START + timedelta(days=int(rng.integers(0, 150)))
            end = min(start + timedelta(days=int(rng.integers(14, 45))), END)
            budget = int(rng.integers(5, 60)) * 500
            name = f"{BRANDS[brand_id - 1][0]} x {CREATORS[creator_id - 1][0]}"
            conn.execute(
                "INSERT INTO campaigns VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    campaign_id,
                    brand_id,
                    creator_id,
                    name,
                    start.isoformat(),
                    end.isoformat(),
                    budget,
                ),
            )
            campaigns.append((campaign_id, creator_id, start, end))
            campaign_id += 1

    # posts: around 1500 over 6 months
    n_days = (END - START).days + 1
    posts_per_week = {"Instagram": 3.7, "TikTok": 2.6, "YouTube": 1.0}
    post_id = 1
    metric_rows = []
    undisclosed_left = 2
    for account_id, creator_id, platform, followers in accounts:
        niche = CREATORS[creator_id - 1][1]
        n_posts = int(rng.poisson(posts_per_week[platform] * n_days / 7))
        offsets = sorted(int(x) for x in rng.integers(0, n_days, size=n_posts))
        for offset in offsets:
            day = START + timedelta(days=offset)
            hour = int(rng.choice([8, 12, 13, 17, 18, 19, 20, 21]))
            posted_at = datetime(day.year, day.month, day.day, hour, int(rng.integers(0, 60)))
            fmt = str(rng.choice(FORMATS[platform]))

            # is it part of a running campaign?
            campaign = None
            for c_id, c_creator, c_start, c_end in campaigns:
                if c_creator == creator_id and c_start <= day <= c_end and rng.random() < 0.35:
                    campaign = c_id
                    break
            is_paid = 1 if campaign else 0
            has_disclosure = 1 if is_paid else 0
            caption = str(rng.choice(CAPTION_TEMPLATES)).format(niche=niche)
            if is_paid:
                caption += " #ad"
                # planted: two paid posts where the disclosure was forgotten
                if undisclosed_left > 0 and platform == "Instagram" and creator_id in (2, 7):
                    has_disclosure = 0
                    caption = caption.replace(" #ad", "")
                    undisclosed_left -= 1

            conn.execute(
                "INSERT INTO posts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    post_id,
                    account_id,
                    campaign,
                    posted_at.isoformat(sep=" "),
                    fmt,
                    caption,
                    is_paid,
                    has_disclosure,
                ),
            )

            # total reach of the post
            reach_total = followers * FORMAT_REACH[fmt] * season_factor(day)
            reach_total *= rng.lognormal(0, 0.35)
            if is_paid:
                reach_total *= 0.85  # sponsored posts usually do a bit worse
            if creator_id == 5 and day.month == 8:
                reach_total *= 0.6  # planted slump
            engagement_rate = FORMAT_ENGAGEMENT[fmt] * rng.lognormal(0, 0.25)

            metric_rows += daily_metrics(post_id, day, reach_total, engagement_rate, fmt, rng)
            post_id += 1

    plant_viral_post(conn, metric_rows, rng)
    plant_fake_engagement(conn, metric_rows)

    conn.executemany(
        "INSERT INTO post_metrics_daily VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", metric_rows
    )

    insert_contracts_index(conn, campaigns, rng)
    insert_schedule(conn, rng)

    conn.commit()
    conn.close()


def daily_metrics(post_id, day, reach_total, engagement_rate, fmt, rng):
    """Split the total reach over 7 days (most of it on the first days)."""
    weights = np.array([0.45, 0.22, 0.12, 0.08, 0.06, 0.04, 0.03])
    rows = []
    for i in range(METRIC_DAYS):
        reach = int(reach_total * weights[i] * rng.uniform(0.85, 1.15))
        impressions = int(reach * rng.uniform(1.1, 1.5))
        views = impressions if fmt in ("reel", "video", "short", "story") else 0
        engaged = reach * engagement_rate
        likes = int(engaged * 0.80)
        comments = int(engaged * 0.05)
        shares = int(engaged * 0.07)
        saves = int(engaged * 0.08)
        day_i = (day + timedelta(days=i)).isoformat()
        rows.append([post_id, day_i, impressions, reach, views, likes, comments, shares, saves])
    return rows


def plant_viral_post(conn, metric_rows, rng):
    """Make one Reel of creator 3 (Creator C) go viral: about 15x the reach."""
    post_id = conn.execute(
        """SELECT p.post_id FROM posts p JOIN accounts a ON a.account_id = p.account_id
           WHERE a.creator_id = 3 AND p.format = 'reel' AND p.posted_at LIKE '2026-07%'
           ORDER BY p.posted_at LIMIT 1"""
    ).fetchone()[0]
    for row in metric_rows:
        if row[0] == post_id:
            for col in range(2, 9):
                row[col] = int(row[col] * 15)


def plant_fake_engagement(conn, metric_rows):
    """Creator 6 (Creator F): on 2026-08-12 likes jump but reach stays flat (bot-like)."""
    post_ids = {
        r[0]
        for r in conn.execute(
            """SELECT p.post_id FROM posts p JOIN accounts a ON a.account_id = p.account_id
               WHERE a.creator_id = 6"""
        )
    }
    for row in metric_rows:
        if row[0] in post_ids and row[1] == "2026-08-12":
            row[5] = row[5] * 20 + 5000  # likes


def insert_contracts_index(conn, campaigns, rng):
    """One contract per campaign. doc_id points to the synthetic contract documents."""
    for i, (campaign_id, creator_id, start, end) in enumerate(campaigns, start=1):
        brand_id, budget = conn.execute(
            "SELECT brand_id, budget_usd FROM campaigns WHERE campaign_id = ?", (campaign_id,)
        ).fetchone()
        exclusive = 1 if rng.random() < 0.5 else 0
        category = BRANDS[brand_id - 1][1] if exclusive else None
        contract_end = end + timedelta(days=int(rng.choice([30, 90, 180])))
        conn.execute(
            "INSERT INTO contracts_index VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"C{i:03d}",
                f"synthetic_contract_{i:03d}",
                creator_id,
                brand_id,
                (start - timedelta(days=14)).isoformat(),
                contract_end.isoformat(),
                budget,
                exclusive,
                category,
            ),
        )


def insert_schedule(conn, rng):
    """A few upcoming posts in the schedule (some already approved)."""
    for i in range(1, 11):
        creator_id = int(rng.integers(1, len(CREATORS) + 1))
        platform_id = int(rng.integers(1, 3))
        when = datetime(2026, 11, 1, 18, 0) + timedelta(days=i * 2)
        status = "approved" if i <= 6 else "pending"
        created = when - timedelta(days=5)
        conn.execute(
            "INSERT INTO schedule VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                i,
                creator_id,
                platform_id,
                when.isoformat(sep=" "),
                f"Upcoming post #{i}",
                status,
                created.isoformat(sep=" "),
            ),
        )
        decision = "approved" if status == "approved" else None
        decided_at = (created + timedelta(hours=3)).isoformat(sep=" ") if decision else None
        conn.execute(
            "INSERT INTO approvals VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                i,
                i,
                "schedule_post",
                created.isoformat(sep=" "),
                decision,
                decided_at,
                "account_manager" if decision else None,
            ),
        )
