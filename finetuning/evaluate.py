"""Compare the clause classifiers on the test split (contracts never seen in training).

Methods:
  llm       zero-shot prompt to the local LLM (qwen3:8b), on a fixed random sample of the test set
  probe     un-tuned encoder (frozen, mean pooling) + logistic regression trained on the train split
  finetuned the model saved by train.py

Run: uv run --group finetune python finetuning/evaluate.py --methods probe,finetuned,llm
Results: reports/finetuning/<method>.json (+ a summary table printed at the end)
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support
from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer

sys.path.insert(0, str(Path(__file__).parent))
from common import LABEL_ID, LABELS, get_device, load_split  # noqa: E402

OUT = Path("reports/finetuning")
LLM_SAMPLE = 400

LLM_PROMPT = """Classify this contract clause into exactly one type:
- exclusivity: one party may only work with / buy from / sell through the other (exclusive rights)
- non_compete: a party may not compete, or solicit customers, in a market or for a time
- term_renewal: how long the agreement lasts, when it expires, automatic renewal
- termination: ending the agreement for convenience, notice, what happens after termination
- ip_license: licenses granted, intellectual property ownership or assignment
- payment: fees, revenue or profit sharing, minimum purchase commitments, prices
- governing_law: which law governs the agreement / jurisdiction
- liability: limitation or cap of liability, damages, liquidated damages
- other: anything else (assignment, audit, insurance, warranties, confidentiality...)
Reply with JSON only: {"label": "<type>"}"""


def scores(gold: list[int], preds: list[int], seconds_per_example: float, n_note="") -> dict:
    p, r, f, support = precision_recall_fscore_support(
        gold, preds, labels=range(len(LABELS)), zero_division=0
    )
    return {
        "n": len(gold),
        "note": n_note,
        "macro_f1": round(f1_score(gold, preds, labels=range(len(LABELS)), average="macro"), 4),
        "accuracy": round(float(np.mean(np.array(gold) == np.array(preds))), 4),
        "per_class": {
            LABELS[i]: {
                "precision": round(p[i], 3),
                "recall": round(r[i], 3),
                "f1": round(f[i], 3),
                "support": int(support[i]),
            }
            for i in range(len(LABELS))
        },  # fmt: skip
        "confusion_matrix": confusion_matrix(gold, preds, labels=range(len(LABELS))).tolist(),
        "ms_per_example": round(1000 * seconds_per_example, 1),
    }


# ---------- un-tuned encoder + linear head ----------


@torch.no_grad()
def embed(texts, tokenizer, model, device, batch_size=32, max_len=192):
    vectors = []
    for i in range(0, len(texts), batch_size):
        enc = tokenizer(texts[i : i + batch_size], truncation=True, max_length=max_len,
                        padding=True, return_tensors="pt").to(device)  # fmt: skip
        hidden = model(**enc).last_hidden_state
        mask = enc["attention_mask"].unsqueeze(-1)
        vectors.append(((hidden * mask).sum(1) / mask.sum(1)).float().cpu().numpy())
    return np.concatenate(vectors)


def run_probe(base_model, train, test, device):
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModel.from_pretrained(base_model).to(device).eval()
    x_train = embed([r["text"] for r in train], tokenizer, model, device)
    clf = LogisticRegression(max_iter=3000)
    clf.fit(x_train, [LABEL_ID[r["label"]] for r in train])
    start = time.time()
    x_test = embed([r["text"] for r in test], tokenizer, model, device)
    preds = clf.predict(x_test).tolist()
    return preds, (time.time() - start) / len(test)


# ---------- fine-tuned model ----------


@torch.no_grad()
def run_finetuned(path, test, device, batch_size=32):
    tokenizer = AutoTokenizer.from_pretrained(path)
    model = AutoModelForSequenceClassification.from_pretrained(path).to(device).eval()
    preds, start = [], time.time()
    for i in range(0, len(test), batch_size):
        enc = tokenizer([r["text"] for r in test[i : i + batch_size]], truncation=True,
                        max_length=192, padding=True, return_tensors="pt").to(device)  # fmt: skip
        preds += model(**enc).logits.argmax(-1).cpu().tolist()
    return preds, (time.time() - start) / len(test)


# ---------- LLM zero-shot ----------


def run_llm(test):
    sys.path.insert(0, "src")
    from creatorops.llm.client import get_llm

    llm = get_llm()
    preds, start, invalid = [], time.time(), 0
    for i, row in enumerate(test, 1):
        response = llm.chat([{"role": "system", "content": LLM_PROMPT},
                             {"role": "user", "content": row["text"]}], json_mode=True)  # fmt: skip
        try:
            label = json.loads(response["content"]).get("label")
        except (json.JSONDecodeError, AttributeError):
            label = None
        if label not in LABEL_ID:
            invalid += 1
            label = "other"
        preds.append(LABEL_ID[label])
        if i % 50 == 0:
            print(f"llm {i}/{len(test)}", flush=True)
    return preds, (time.time() - start) / len(test), invalid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--methods", default="probe,finetuned,llm")
    parser.add_argument("--base-model", default="answerdotai/ModernBERT-base")
    parser.add_argument("--model-dir", default="models/clause_classifier")
    parser.add_argument("--small", action="store_true")
    args = parser.parse_args()

    device = get_device()
    train = load_split("train", 500 if args.small else None)
    test = load_split("test", 200 if args.small else None)
    sample = random.Random(42).sample(test, min(LLM_SAMPLE, len(test)))
    sample_ids = {id(r) for r in sample}
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}

    for method in args.methods.split(","):
        print(f"== {method}", flush=True)
        extra = {}
        if method == "probe":
            preds, secs = run_probe(args.base_model, train, test, device)
        elif method == "finetuned":
            preds, secs = run_finetuned(args.model_dir, test, device)
        elif method == "llm":
            preds, secs, invalid = run_llm(sample)
            extra = {"invalid_outputs": invalid}
        else:
            raise SystemExit(f"unknown method {method}")

        rows = sample if method == "llm" else test
        gold = [LABEL_ID[r["label"]] for r in rows]
        result = {"full_test": None, **extra}
        if method != "llm":
            result["full_test"] = scores(gold, preds, secs, "all test examples")
            keep = [i for i, r in enumerate(test) if id(r) in sample_ids]
            result["sample"] = scores([gold[i] for i in keep], [preds[i] for i in keep], secs,
                                      f"same {len(keep)} examples as the LLM")  # fmt: skip
        else:
            result["sample"] = scores(gold, preds, secs, f"random sample of {len(rows)} (seed 42)")
        result["device"] = "ollama" if method == "llm" else device
        results[method] = result
        (OUT / f"{method}{'_small' if args.small else ''}.json").write_text(
            json.dumps(result, indent=2)
        )

    print(f"\n{'method':<10} {'sample macro-F1':>16} {'full macro-F1':>14} {'ms/example':>11}")
    for method, r in results.items():
        full = r["full_test"]["macro_f1"] if r["full_test"] else "-"
        print(
            f"{method:<10} {r['sample']['macro_f1']:>16} {full:>14} {r['sample']['ms_per_example']:>11}"
        )


if __name__ == "__main__":
    main()
