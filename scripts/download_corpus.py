"""Download / build the document corpus and write data/manifest.csv.

Sources:
1. policy and regulation pages listed in data/sources.csv
   - live: downloaded now
   - wayback: dated snapshots from the Internet Archive (gives us older versions)
   - ecfr: official eCFR API, one file per version date
2. CUAD contracts (Zenodo, CC BY 4.0): a seeded random sample
3. synthetic influencer contracts (generated from the synthetic database)
4. synthetic agency SOPs (data/sops/)

Usage: uv run python scripts/download_corpus.py [--cuad-n 100] [--skip-cuad]
"""

import argparse
import csv
import io
import random
import shutil
import time
import zipfile
from datetime import date
from pathlib import Path

import httpx

from creatorops.config import settings
from creatorops.synthetic_contracts import write_contracts

RAW = settings.data_dir / "raw"
CUAD_URL = "https://zenodo.org/records/4595826/files/CUAD_v1.zip?download=1"
HEADERS = {"User-Agent": "Mozilla/5.0 (student research project; corpus download)"}
TODAY = date.today().isoformat()

MANIFEST_COLUMNS = [
    "doc_id",
    "title",
    "doc_type",
    "platform",
    "publisher",
    "source_url",
    "retrieved_at",
    "doc_date",
    "snapshot_date",
    "version",
    "license",
    "language",
    "synthetic",
    "num_pages",
    "file_path",
]


def wayback_snapshots(client, url):
    """List of (timestamp, original_url) for successful captures, one per month."""
    r = client.get(
        "http://web.archive.org/cdx/search/cdx",
        params={
            "url": url,
            "output": "json",
            "fl": "timestamp,original",
            "filter": "statuscode:200",
            "collapse": "timestamp:6",
            "from": "2023",
        },
    )
    rows = r.json()
    return [(row[0], row[1]) for row in rows[1:]]


def pick_snapshot(snapshots, wanted):
    """'latest' -> newest capture; 'YYYY-MM' -> closest capture to that month."""
    if wanted == "latest":
        return snapshots[-1]
    target = wanted.replace("-", "") + "15"
    return min(snapshots, key=lambda s: abs(int(s[0][:8]) - int(target)))


def stamp_to_date(stamp):
    return f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}"


def download_policies(client):
    rows = []
    with open(settings.data_dir / "sources.csv", encoding="utf-8") as f:
        sources = list(csv.DictReader(f))

    for src in sources:
        out_dir = RAW / "policies" / src["doc_id"]
        out_dir.mkdir(parents=True, exist_ok=True)
        files = []  # (path, snapshot_date)
        try:
            if src["method"] == "live":
                r = client.get(src["url"])
                r.raise_for_status()
                path = out_dir / f"{TODAY}.html"
                path.write_text(r.text, encoding="utf-8")
                files.append((path, TODAY))

            elif src["method"] == "wayback":
                snapshots = wayback_snapshots(client, src["url"])
                chosen = {pick_snapshot(snapshots, w) for w in src["snapshots"].split(";")}
                for stamp, original in sorted(chosen):
                    r = client.get(f"http://web.archive.org/web/{stamp}id_/{original}")
                    r.raise_for_status()
                    path = out_dir / f"{stamp_to_date(stamp)}.html"
                    path.write_text(r.text, encoding="utf-8")
                    files.append((path, stamp_to_date(stamp)))
                    time.sleep(1)  # be nice to the archive

            elif src["method"] == "ecfr":
                for day in src["snapshots"].split(";"):
                    r = client.get(
                        f"https://www.ecfr.gov/api/versioner/v1/full/{day}/title-16.xml",
                        params={"part": "255"},
                        headers={"Accept-Encoding": "gzip"},
                    )
                    r.raise_for_status()
                    path = out_dir / f"{day}.xml"
                    path.write_text(r.text, encoding="utf-8")
                    files.append((path, day))
        except (httpx.HTTPError, ValueError) as e:
            print(f"  FAILED {src['doc_id']}: {e}")
            continue

        for version, (path, snap_date) in enumerate(files, start=1):
            rows.append(
                {
                    "doc_id": src["doc_id"],
                    "title": src["title"],
                    "doc_type": src["doc_type"],
                    "platform": src["platform"],
                    "publisher": src["publisher"],
                    "source_url": src["url"],
                    "retrieved_at": TODAY,
                    "doc_date": snap_date,
                    "snapshot_date": snap_date,
                    "version": version,
                    "license": src["license"],
                    "language": "en",
                    "synthetic": False,
                    "num_pages": "",
                    "file_path": str(path.relative_to(settings.data_dir)),
                }
            )
        print(f"  {src['doc_id']}: {len(files)} snapshot(s)")
    return rows


def download_cuad(client, n):
    """Download the CUAD zip once, keep the label files and a random sample of contracts."""
    cuad_dir = RAW / "cuad"
    zip_path = cuad_dir / "CUAD_v1.zip"
    cuad_dir.mkdir(parents=True, exist_ok=True)
    if not zip_path.exists():
        print("  downloading CUAD (~100 MB)...")
        with client.stream("GET", CUAD_URL) as r:
            r.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)

    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        # keep the annotations for the fine-tuning experiment
        for name in names:
            if name.endswith(("master_clauses.csv", "CUAD_v1.json")):
                (cuad_dir / Path(name).name).write_bytes(z.read(name))
        txt_files = sorted(n for n in names if "full_contract_txt/" in n and n.endswith(".txt"))
        sample = random.Random(settings.seed).sample(txt_files, n)
        rows = []
        for name in sample:
            stem = Path(name).stem
            doc_id = "cuad_" + "".join(c if c.isalnum() else "_" for c in stem)[:60].lower()
            path = cuad_dir / "contracts" / f"{doc_id}.txt"
            path.parent.mkdir(exist_ok=True)
            text = io.TextIOWrapper(z.open(name), encoding="utf-8", errors="ignore").read()
            path.write_text(text, encoding="utf-8")
            rows.append(
                {
                    "doc_id": doc_id,
                    "title": stem,
                    "doc_type": "contract",
                    "platform": "",
                    "publisher": "CUAD (The Atticus Project)",
                    "source_url": "https://zenodo.org/records/4595826",
                    "retrieved_at": TODAY,
                    "doc_date": "",
                    "snapshot_date": "",
                    "version": 1,
                    "license": "CC BY 4.0",
                    "language": "en",
                    "synthetic": False,
                    "num_pages": "",
                    "file_path": str(path.relative_to(settings.data_dir)),
                }
            )
    print(f"  CUAD: {len(rows)} contracts")
    return rows


def build_synthetic_contracts():
    if not settings.db_path.exists():
        raise SystemExit("Run scripts/generate_analytics_db.py first.")
    docs = write_contracts(settings.db_path, RAW / "synthetic_contracts", seed=settings.seed)
    rows = [
        {
            "doc_id": d["doc_id"],
            "title": d["title"],
            "doc_type": "contract",
            "platform": "",
            "publisher": "CreatorOps (synthetic)",
            "source_url": "",
            "retrieved_at": TODAY,
            "doc_date": d["doc_date"],
            "snapshot_date": "",
            "version": 1,
            "license": "CC BY 4.0 (project-generated)",
            "language": "en",
            "synthetic": True,
            "num_pages": "",
            "file_path": str(d["path"].relative_to(settings.data_dir)),
        }
        for d in docs
    ]
    print(f"  synthetic contracts: {len(rows)}")
    return rows


def copy_sops():
    rows = []
    out_dir = RAW / "sops"
    out_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted((settings.data_dir / "sops").glob("*.md")):
        target = out_dir / path.name
        shutil.copy(path, target)
        title = path.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
        rows.append(
            {
                "doc_id": path.stem,
                "title": title,
                "doc_type": "sop",
                "platform": "",
                "publisher": "CreatorOps (synthetic)",
                "source_url": "",
                "retrieved_at": TODAY,
                "doc_date": "2026-01-15",
                "snapshot_date": "",
                "version": 1,
                "license": "CC BY 4.0 (project-generated)",
                "language": "en",
                "synthetic": True,
                "num_pages": "",
                "file_path": str(target.relative_to(settings.data_dir)),
            }
        )
    print(f"  SOPs: {len(rows)}")
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cuad-n", type=int, default=100)
    parser.add_argument("--skip-cuad", action="store_true")
    args = parser.parse_args()

    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=120)
    rows = []
    print("policies and regulations:")
    rows += download_policies(client)
    if not args.skip_cuad:
        print("CUAD:")
        rows += download_cuad(client, args.cuad_n)
    print("synthetic documents:")
    rows += build_synthetic_contracts()
    rows += copy_sops()

    with open(settings.manifest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(
        f"{len(rows)} files, {len({r['doc_id'] for r in rows})} documents -> "
        f"{settings.manifest_path}"
    )


if __name__ == "__main__":
    main()
