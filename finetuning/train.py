"""Fine-tune a small encoder to classify contract clauses (9 classes).

Run locally (Apple GPU or CPU) or on Colab (see finetuning/notebooks/train_colab.ipynb):
    uv run --group finetune python finetuning/train.py
    uv run --group finetune python finetuning/train.py --small      # quick CPU test, 2 min
The best epoch (macro-F1 on val) is saved to models/clause_classifier/.
Runs are logged with MLflow in ./mlruns (see them with: uv run --group finetune mlflow ui).
"""

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

import mlflow
import numpy as np
import torch
from sklearn.metrics import f1_score
from torch.utils.data import DataLoader
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

sys.path.insert(0, str(Path(__file__).parent))
from common import LABEL_ID, LABELS, get_device, load_split  # noqa: E402


def batches(rows, tokenizer, batch_size, max_len, shuffle):
    def collate(items):
        enc = tokenizer([r["text"] for r in items], truncation=True, max_length=max_len,
                        padding=True, return_tensors="pt")  # fmt: skip
        enc["labels"] = torch.tensor([LABEL_ID[r["label"]] for r in items])
        return enc

    return DataLoader(rows, batch_size=batch_size, shuffle=shuffle, collate_fn=collate)


@torch.no_grad()
def predict(model, loader, device) -> tuple[list[int], list[int]]:
    model.eval()
    preds, gold = [], []
    for batch in loader:
        labels = batch.pop("labels")
        logits = model(**{k: v.to(device) for k, v in batch.items()}).logits
        preds += logits.argmax(-1).cpu().tolist()
        gold += labels.tolist()
    return preds, gold


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="answerdotai/ModernBERT-base")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=3e-5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-len", type=int, default=192)  # 95% of the clauses are < 175 tokens
    parser.add_argument("--grad-accum", type=int, default=1, help="batches per optimizer step")
    parser.add_argument("--small", action="store_true", help="500 train / 200 val examples")
    parser.add_argument("--out", default="models/clause_classifier")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = get_device()
    train = load_split("train", 500 if args.small else None)
    val = load_split("val", 200 if args.small else None)

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model, num_labels=len(LABELS), id2label=dict(enumerate(LABELS)), label2id=LABEL_ID
    ).to(device)
    train_loader = batches(train, tokenizer, args.batch_size, args.max_len, shuffle=True)
    val_loader = batches(val, tokenizer, 32, args.max_len, shuffle=False)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    steps = len(train_loader) * args.epochs // args.grad_accum
    scheduler = get_linear_schedule_with_warmup(optimizer, int(0.1 * steps), steps)

    # plain local folder, no database or server needed (mlflow-skinny has no sqlite store)
    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
    mlflow.set_tracking_uri("file:./mlruns")
    mlflow.set_experiment("clause_classifier")
    with mlflow.start_run(run_name=f"{args.model.split('/')[-1]}{'-small' if args.small else ''}"):
        mlflow.log_params(
            {**vars(args), "device": device, "n_train": len(train), "n_val": len(val)}
        )
        best_f1, start = -1.0, time.time()
        for epoch in range(1, args.epochs + 1):
            model.train()
            total = 0.0
            for step, batch in enumerate(train_loader, 1):
                batch = {k: v.to(device) for k, v in batch.items()}
                loss = model(**batch).loss
                (loss / args.grad_accum).backward()
                if step % args.grad_accum == 0:  # small batches use less GPU memory
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optimizer.step()
                    scheduler.step()
                    optimizer.zero_grad()
                total += loss.item()
                if step % 50 == 0:
                    print(
                        f"epoch {epoch} step {step}/{len(train_loader)} loss {total / step:.4f} "
                        f"({(time.time() - start) / 60:.1f} min)",
                        flush=True,
                    )

            preds, gold = predict(model, val_loader, device)
            macro_f1 = f1_score(gold, preds, average="macro")
            mlflow.log_metrics(
                {"train_loss": total / len(train_loader), "val_macro_f1": macro_f1}, step=epoch
            )
            print(
                f"epoch {epoch}: train loss {total / len(train_loader):.4f}, val macro-F1 {macro_f1:.4f}"
            )
            if macro_f1 > best_f1:
                best_f1 = macro_f1
                Path(args.out).mkdir(parents=True, exist_ok=True)
                model.save_pretrained(args.out)
                tokenizer.save_pretrained(args.out)
                Path(args.out, "training.json").write_text(json.dumps(
                    {**vars(args), "best_epoch": epoch, "val_macro_f1": macro_f1, "device": device}, indent=2))  # fmt: skip

        mlflow.log_metrics(
            {"best_val_macro_f1": best_f1, "train_minutes": (time.time() - start) / 60}
        )
        print(f"best val macro-F1 {best_f1:.4f}, saved to {args.out}")


if __name__ == "__main__":
    main()
