"""classify_clause: clause type of a contract passage, with the fine-tuned encoder.

The model is trained by finetuning/train.py (saved in models/clause_classifier/). If it is not
there (fresh clone, CI), the tool says so instead of guessing.
"""

from pathlib import Path

MODEL_DIR = Path("models/clause_classifier")
_model = None


def load_model():
    global _model
    if _model is None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        device = "mps" if torch.backends.mps.is_available() else "cpu"
        tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
        model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR).to(device).eval()
        _model = (tokenizer, model, device)
    return _model


def classify_clause(text: str, top_n: int = 3) -> dict:
    """Return the most likely clause types with probabilities."""
    if not MODEL_DIR.exists():
        return {"error": "The clause classifier is not trained yet (run finetuning/train.py)."}
    import torch

    tokenizer, model, device = load_model()
    enc = tokenizer(text, truncation=True, max_length=192, return_tensors="pt").to(device)
    with torch.no_grad():
        probs = model(**enc).logits.softmax(-1)[0].cpu().tolist()
    ranked = sorted(zip(model.config.id2label.values(), probs), key=lambda x: -x[1])[:top_n]
    return {"label": ranked[0][0], "scores": {label: round(p, 3) for label, p in ranked}}
