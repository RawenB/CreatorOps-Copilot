"""Shared code for the clause classifier experiment."""

import json
from pathlib import Path

import torch

DATA = Path("data/clauses")
LABELS = ["exclusivity", "non_compete", "term_renewal", "termination", "ip_license", "payment",
          "governing_law", "liability", "other"]  # fmt: skip
LABEL_ID = {label: i for i, label in enumerate(LABELS)}


def load_split(name: str, limit: int | None = None) -> list[dict]:
    rows = [json.loads(line) for line in (DATA / f"{name}.jsonl").read_text().splitlines()]
    return rows[:limit] if limit else rows


def get_device() -> str:
    if torch.cuda.is_available():
        return "cuda"  # Colab / Kaggle
    if torch.backends.mps.is_available():
        return "mps"  # Apple GPU
    return "cpu"
