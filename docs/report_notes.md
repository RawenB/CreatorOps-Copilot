# Report notes

Material for the written report and the defense. Numbers come from `reports/eval_results.md`,
`reports/finetuning.md` and `docs/error_analysis.md`.

## 1. Problem

A creator agency answers three kinds of questions every day: platform / advertising rules (they change
often), what a brand contract says, and how creators perform. The assistant answers all three with
citations, mixes them when needed (data + documents), and can prepare actions (scheduling a post) that a
human must approve.

## 2. What was built

- **Corpus with versions:** 158 documents (Meta, TikTok, YouTube policies, FTC Part 255 + FAQ + guide,
  UK CAP / ASA, EU DSA, 100 CUAD contracts, 20 synthetic influencer contracts, 6 SOPs), 170 stored
  snapshots. A new snapshot with a different hash becomes a new version with `valid_from` / `valid_to`,
  so "what were the rules in December 2024?" uses the old text.
- **Retrieval:** structure-aware chunks, bge-base embeddings in Qdrant + BM25, RRF fusion, bge-reranker,
  metadata filters (platform, doc type, contract, date).
- **Synthetic analytics DB:** 8 creators, 1,418 posts, 9,926 daily metric rows, campaigns, contracts
  index, with planted anomalies (viral Reel, fake likes, undisclosed paid posts).
- **Agent (LangGraph):** LLM router -> route-specific tools -> tool loop (max 6 steps) -> citation check;
  `interrupt()` before any write. Local LLM only (qwen3:8b with Ollama).
- **Tools:** policy search, version diff, clause search, clause classifier (fine-tuned), read-only SQL
  (5 safety layers), compliance checker, scheduling with approval.
- **Interfaces:** FastAPI, React UI (chat with highlighted sources, approvals, calendar, SQL), MCP server
  (9 tools, usable from Claude Desktop), CLI.
- **Evaluation:** 137 + 12 held-out + 11 version questions, 28 SQL safety cases, 60 captions, CUAD test split.

## 3. Main results

| what | result |
|---|---|
| retrieval, hybrid + rerank, tool filters (85 q.) | Recall@10 0.824, MRR 0.658 (policy 0.89, contract 1.00, hybrid 0.55 single search) |
| version-aware vs latest-only (11 old-version q.) | Recall@10 1.00 vs 0.00 |
| routing accuracy (v2) | 96.2% |
| SQL execution accuracy, v1 -> v2 (held-out) | 33% -> 59% (75%) |
| keyword correctness, v1 -> v2 | 60% -> 75% |
| LLM judge, v2 (106 answers) | 80% faithful, 76% fully correct (hybrid: 54% / 50%) |
| manual check of the judge (20 answers) | judge 18/20 faithful vs manual 14/20 |
| approval-required actions interrupted | 9/11 (the 2 others: no action at all, never a write) |
| writes without approval | 0 in every run |
| invalid actions refused, v1 -> v2 | 75% -> 100% |
| abstention precision / recall, v2 | 56% / 90% |
| SQL safety | 18/18 unsafe queries rejected, 10/10 injection prompts: database unchanged |
| compliance, rules vs LLM (60 captions) | accuracy 88% vs 73%, recall on non-compliant 100% vs 68% |
| clause classifier, macro-F1 (same 400 test clauses) | fine-tuned 0.843, zero-shot LLM 0.743, frozen encoder 0.717; 17 ms vs 576 ms per clause |

## 4. What I learned (for the defense)

1. **The SQL errors were silent.** Comparing an integer id with a name returns 0 rows without an error, so
   the agent either said "I don't know" or "0". Putting the lookup values in the prompt fixed most of it
   (33% -> 59%, 75% on new questions). Lesson: look at the tool results, not only at the final answer.
2. **Never let the LLM pick ids for write actions.** The model invented `creator_id=1` for "Creator Z".
   Resolving names in code removed the problem completely.
3. **An LLM judge from the same small model is too kind.** It missed 4 of 6 unfaithful answers in the
   sample, mostly wrong citations. Strict metrics (SQL execution, keywords) and a manual check are needed.
4. **The chunk must say where it comes from.** Contract chunks all look alike; adding "title > section"
   to the indexed text raised contract Recall@10 from 0.69 to 1.00 without any filter (MRR 0.51 -> 0.81).
5. **Simple can beat complex:** BM25 alone is close to hybrid on this corpus, the reranker adds almost
   nothing on top of hybrid, fixed-size chunks did slightly better than structure-aware ones, and the
   deterministic compliance rules beat the LLM. Measuring each part was more useful than adding parts.
6. **Fine-tuning a 149M encoder beat an 8B LLM** on a narrow classification task (+10 macro-F1, 33x faster).

## 5. Limitations

- Small evaluation sets (one author, 137 questions); per-type scores move a lot with one question.
- v2 fixes were found on the same test set; the held-out set is only 12 questions.
- The judge is the same model as the assistant; the manual check covers 20 answers.
- Synthetic contracts, SOPs and analytics are cleaner than real ones.
- Policy snapshots come from the Wayback Machine and official pages at given dates, they are not legal
  advice and can be outdated.
- One local 8B model: 7.6 s per answer on average (p95 16 s) on a laptop, and some failures (guessing an entity,
  choosing the wrong document) would likely be rarer with a bigger model.
- The compliance rules only know English disclosure words and do not look at images or videos.
- Every result is from a single run (Ollama is not fully deterministic even at temperature 0).

## 6. Next steps

1. Re-index with the "title > section" header (best ablation result) and re-run the agent eval.
2. Give `schedule_post` to the hybrid route (or route on the verb) for "look up then schedule" requests.
3. Check that each cited passage supports its sentence (entailment model) instead of only checking ids.
4. Better version diff ranking (size of the change), and choose the compared document by title.
5. Multilingual disclosure words (#publicité, #publicidad, Anzeige, #werbung) + a second caption set.
6. A paraphrase set and a second annotator for the evaluation questions.
