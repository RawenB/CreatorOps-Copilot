"""Create data/creatorops.sqlite with synthetic analytics data.

Usage: uv run python scripts/generate_analytics_db.py [--seed 42]
"""

import argparse
import sqlite3

from creatorops.config import settings
from creatorops.synthetic_db import create_db

parser = argparse.ArgumentParser()
parser.add_argument("--seed", type=int, default=settings.seed)
args = parser.parse_args()

create_db(settings.db_path, seed=args.seed)

conn = sqlite3.connect(settings.db_path)
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
for table in tables:
    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"{table:20s} {count}")
print(f"saved to {settings.db_path}")
