# Fine-tuning: contract clause classifier

**Task:** given a contract sentence/clause, predict its type: exclusivity, non_compete, term_renewal,
termination, ip_license, payment, governing_law, liability or other. Used by the `classify_clause` tool
(agent + MCP) to label a clause that a user pastes.

## Data

- Source: CUAD v1 (510 commercial contracts, 41 lawyer-annotated clause labels, CC BY 4.0).
- `finetuning/build_dataset.py` maps the agency-relevant labels to 8 classes (e.g. "Renewal Term",
  "Expiration Date", "Notice Period To Terminate Renewal" -> term_renewal) and the rest (anti-assignment,
  audit, insurance...) to "other". Metadata labels (parties, dates, document name) are dropped.
- The input is the sentence around each annotated span (a span alone can be 3 words), plus 3 random
  un-annotated sentences per contract as extra "other" examples.
- **Split by contract**, 70 / 15 / 15, seed 42, so no contract is in two splits:

| split | examples | contracts |
|---|---|---|
| train | 7,099 | 356 |
| val | 1,544 | 76 |
| test | 1,382 | 77 |

"other" is 47% of the test set, so the main metric is **macro-F1** (every class counts the same).

## Methods

| method | what | where it runs |
|---|---|---|
| LLM zero-shot | qwen3:8b with a prompt listing the classes and a one-line definition of each | Ollama, local |
| frozen encoder + linear head | ModernBERT-base not trained, mean-pooled embeddings, logistic regression trained on the train split | Apple GPU (MPS) |
| **fine-tuned** | ModernBERT-base (149M parameters) fully fine-tuned, 3 epochs, lr 3e-5, batch 8 x 2 accumulation, max 192 tokens, best epoch on val macro-F1 | Apple GPU (MPS), 34 min |

The same training code runs on Colab (`finetuning/notebooks/train_colab.ipynb`). Training runs are
logged with MLflow (`./mlruns`, not committed): parameters, train loss and val macro-F1 per epoch.
Validation macro-F1 per epoch: 0.768, 0.806, 0.808.

## Results

The LLM is slow (0.6 s per clause), so all methods are compared on the same random sample of 400 test
examples (seed 42); the two encoder methods are also scored on the whole test set.

| method | macro-F1 (400 sample) | macro-F1 (full test) | accuracy (full) | ms / clause |
|---|---|---|---|---|
| LLM zero-shot (qwen3:8b) | 0.743 | - | 0.753 (sample) | 576 |
| frozen encoder + logistic regression | 0.717 | 0.735 | 0.798 | 18 |
| **fine-tuned ModernBERT-base** | **0.843** | **0.849** | **0.877** | **17** |

Per class, fine-tuned model (full test set):

| class | precision | recall | F1 | support |
|---|---|---|---|---|
| exclusivity | 0.85 | 0.73 | 0.78 | 62 |
| non_compete | 0.67 | 0.79 | 0.72 | 42 |
| term_renewal | 0.91 | 0.93 | 0.92 | 99 |
| termination | 0.80 | 0.69 | 0.74 | 93 |
| ip_license | 0.88 | 0.84 | 0.86 | 154 |
| payment | 0.86 | 0.80 | 0.83 | 112 |
| governing_law | 1.00 | 0.94 | 0.97 | 69 |
| liability | 0.90 | 0.92 | 0.91 | 105 |
| other | 0.88 | 0.92 | 0.90 | 646 |

Confusion matrix (rows = gold, columns = predicted), fine-tuned, full test:

| gold \ pred | excl | non_c | term_r | termin | ip | pay | law | liab | other |
|---|---|---|---|---|---|---|---|---|---|
| exclusivity | **45** | 9 | 0 | 0 | 4 | 0 | 0 | 0 | 4 |
| non_compete | 0 | **33** | 0 | 0 | 0 | 0 | 0 | 0 | 9 |
| term_renewal | 0 | 0 | **92** | 3 | 0 | 1 | 0 | 0 | 3 |
| termination | 1 | 0 | 5 | **64** | 1 | 1 | 0 | 0 | 21 |
| ip_license | 3 | 2 | 0 | 2 | **129** | 0 | 0 | 0 | 18 |
| payment | 2 | 0 | 1 | 3 | 0 | **90** | 0 | 2 | 14 |
| governing_law | 0 | 0 | 0 | 0 | 0 | 0 | **65** | 1 | 3 |
| liability | 0 | 0 | 0 | 0 | 0 | 2 | 0 | **97** | 6 |
| other | 2 | 5 | 3 | 8 | 12 | 11 | 0 | 8 | **597** |

Full per-method numbers: `reports/finetuning/{llm,probe,finetuned}.json`.

## What the numbers say

- Fine-tuning helps a lot: +11 points macro-F1 over the same encoder frozen, and +10 over the 8B LLM,
  while being ~33x faster than the LLM (17 ms vs 576 ms per clause on the same laptop) and free to run.
- The LLM is good on easy classes (governing law 0.98) but over-predicts termination and non-compete
  (precision 0.42 and 0.50) and puts too little in "other" (recall 0.69).
- Most errors of the fine-tuned model are with "other": termination -> other (21), ip_license -> other (18),
  payment -> other (14). Part of it is label noise: a sentence can contain a termination clause that CUAD
  annotated under another label (e.g. "Post-Termination Services" vs "Termination For Convenience"), and
  the random "other" sentences are not checked by a lawyer.
- exclusivity vs non_compete (9 errors) is a real ambiguity: many CUAD exclusivity clauses are written as
  "shall not sell competing products".

## Limitations

- One run, one seed: with 42-154 examples per class, differences of 1-2 points are noise.
- CUAD is US commercial contracts (licensing, distribution, outsourcing), not influencer contracts. On
  our synthetic influencer contracts the clause headings already give the type, so the classifier is
  mostly useful for real third-party contracts and for clauses pasted by the user.
- Classes are our own mapping of CUAD labels; some mappings are debatable (Minimum Commitment -> payment).
- The "other" sentences sampled from un-annotated text can still contain a relevant clause that the
  annotators did not mark (CUAD is not exhaustive for every sentence).
- The LLM baseline is zero-shot with one prompt; few-shot examples or a bigger model would do better.
- Cost: everything ran locally (no API cost). The fine-tuned model is 574 MB on disk (float32). Training needed batch 8 + gradient
  accumulation to fit next to other apps in 24 GB (batch 16 ran out of GPU memory).

## Reproduce

```bash
uv run python finetuning/build_dataset.py
uv run --group finetune python finetuning/train.py --batch-size 8 --grad-accum 2
uv run --group finetune python finetuning/evaluate.py --methods probe,finetuned,llm
```
