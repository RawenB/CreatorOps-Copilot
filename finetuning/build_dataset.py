"""Build the clause-type dataset from the CUAD annotations.

CUAD has 41 labels marked as answer spans in 510 contracts. We keep the agency-relevant ones,
map them to 9 classes + "other", and take the sentence around each span (a span alone can be
3 words, a chunk in our RAG index is a few sentences).

Split BY CONTRACT (70 / 15 / 15) so the same contract is never in train and test.

Run: uv run python finetuning/build_dataset.py   ->  data/clauses/{train,val,test}.jsonl
"""

import json
import random
import re
from collections import Counter
from pathlib import Path

CUAD = Path("data/raw/cuad/CUAD_v1.json")
OUT = Path("data/clauses")
SEED = 42

LABEL_MAP = {
    "Exclusivity": "exclusivity",
    "Non-Compete": "non_compete",
    "No-Solicit Of Customers": "non_compete",
    "Competitive Restriction Exception": "non_compete",
    "Renewal Term": "term_renewal",
    "Expiration Date": "term_renewal",
    "Notice Period To Terminate Renewal": "term_renewal",
    "Termination For Convenience": "termination",
    "Post-Termination Services": "termination",
    "License Grant": "ip_license",
    "Non-Transferable License": "ip_license",
    "Irrevocable Or Perpetual License": "ip_license",
    "Ip Ownership Assignment": "ip_license",
    "Joint Ip Ownership": "ip_license",
    "Affiliate License-Licensee": "ip_license",
    "Affiliate License-Licensor": "ip_license",
    "Unlimited/All-You-Can-Eat-License": "ip_license",
    "Revenue/Profit Sharing": "payment",
    "Minimum Commitment": "payment",
    "Price Restrictions": "payment",
    "Most Favored Nation": "payment",
    "Governing Law": "governing_law",
    "Cap On Liability": "liability",
    "Uncapped Liability": "liability",
    "Liquidated Damages": "liability",
    "Anti-Assignment": "other",
    "Audit Rights": "other",
    "Insurance": "other",
    "Change Of Control": "other",
    "Warranty Duration": "other",
    "Covenant Not To Sue": "other",
    "Rofr/Rofo/Rofn": "other",
    "Volume Restriction": "other",
    "Non-Disparagement": "other",
    "Third Party Beneficiary": "other",
    "Source Code Escrow": "other",
    "No-Solicit Of Employees": "other",
}
# "Parties", "Document Name", "Agreement Date", "Effective Date" are not clauses: skipped
LABELS = ["exclusivity", "non_compete", "term_renewal", "termination", "ip_license", "payment",
          "governing_law", "liability", "other"]  # fmt: skip
MIN_CHARS, MAX_CHARS = 40, 800
UNLABELED_PER_CONTRACT = 3  # plain sentences with no annotation -> "other"


def sentence_around(context: str, start: int, end: int) -> str:
    """Extend a span to the sentence (or line) it is in."""
    left = max(context.rfind(". ", 0, start), context.rfind("\n", 0, start)) + 1
    right_candidates = [i for i in (context.find(". ", end), context.find("\n", end)) if i != -1]
    right = min(right_candidates) + 1 if right_candidates else len(context)
    text = re.sub(r"\s+", " ", context[left:right]).strip()
    return text[:MAX_CHARS]


def contract_examples(doc: dict, rng: random.Random) -> list[dict]:
    examples, covered = {}, []
    for paragraph in doc["paragraphs"]:
        context = paragraph["context"]
        for qa in paragraph["qas"]:
            label = LABEL_MAP.get(qa["id"].split("__")[-1])
            for answer in qa["answers"]:
                start = answer["answer_start"]
                end = start + len(answer["text"])
                covered.append((start, end))
                if label is None:
                    continue
                text = sentence_around(context, start, end)
                if len(text) >= MIN_CHARS and text not in examples:
                    examples[text] = label  # same sentence twice: keep the first label
        # a few sentences nobody annotated, as extra "other" examples
        sentences = [m for m in re.finditer(r"[^.\n]{60,600}\.", context)]
        rng.shuffle(sentences)
        added = 0
        for m in sentences:
            if added == UNLABELED_PER_CONTRACT:
                break
            if any(s < m.end() and m.start() < e for s, e in covered):
                continue
            text = re.sub(r"\s+", " ", m.group()).strip()
            if text not in examples:
                examples[text] = "other"
                added += 1
    return [{"text": t, "label": label, "contract": doc["title"]} for t, label in examples.items()]


def main():
    rng = random.Random(SEED)
    docs = json.loads(CUAD.read_text())["data"]
    titles = sorted(d["title"] for d in docs)
    rng.shuffle(titles)
    n = len(titles)
    split_of = {t: "train" for t in titles[: int(0.7 * n)]}
    split_of.update({t: "val" for t in titles[int(0.7 * n) : int(0.85 * n)]})
    split_of.update({t: "test" for t in titles[int(0.85 * n) :]})

    splits = {"train": [], "val": [], "test": []}
    for doc in docs:
        splits[split_of[doc["title"]]] += contract_examples(doc, rng)

    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in splits.items():
        rng.shuffle(rows)
        (OUT / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        counts = Counter(r["label"] for r in rows)
        print(f"{name}: {len(rows)} examples, {len({r['contract'] for r in rows})} contracts")
        print("   ", {label: counts[label] for label in LABELS})


if __name__ == "__main__":
    main()
