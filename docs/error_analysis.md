# Error analysis

Concrete failures from the evaluation runs (`reports/eval/agent_v1.jsonl`, `agent_v2.jsonl`,
`holdout_v2.jsonl`, `generation_agent_v2.jsonl`), grouped by cause. For each: what happened, why, and
what was done (or what should be done).

## 1. SQL: filtering an id column with a name (v1, fixed in v2)

v1 wrote queries like `WHERE a.platform_id = 'Instagram'` or `WHERE p.creator_id = 'Creator C'`
(posts has no creator_id). SQLite does not complain, the query returns 0 rows, and then:
- the agent correctly says it does not know (10 of the 18 false abstentions of v1), or
- it reports "0", e.g. sql_16 "There were 0 YouTube Shorts" (gold: 55), sql_18 "Creator D published 0 posts
  on YouTube" (gold: 19).

Cause: the prompt listed the columns but not the values; an 8B model guesses that `platform_id` holds a
name. Fix (decision 26): the SQL prompt now contains the small lookup tables (8 creators, 3 platforms,
10 brands with their ids) and the join path posts -> accounts -> creators / platforms.
Result: SQL execution accuracy 33% -> 59%, keyword correctness on sql questions 36% -> 69%, and 75% on
8 held-out SQL questions written after the fix (so the fix is not only fitted to the test questions).

## 2. Action: the model invented a creator id (v1, fixed in v2)

action_14 "Schedule an Instagram post for Creator Z" (no such creator): v1 called
`schedule_post(creator_id=1, ...)` and created an approval request for **Creator A**. A human would see
"Creator A" on the approval card, but the tool should never let this happen.
Fix (decision 27): `schedule_post` takes the creator **name** and resolves it in code; an unknown name is
an error. Invalid actions refused: 75% -> 100% (v2 and held-out).

## 3. Router: "look something up, then schedule" goes to the wrong route (open)

action_09 and holdout_action_01 ("schedule a post for the creator with the most / fewest Instagram
followers") are routed to `hybrid`, which has no `schedule_post` tool. The agent runs the SQL, cannot
schedule, and abstains. Approval interrupt rate is 9/11 in v2 because of this (and #5).
Better fix: give `schedule_post` to the hybrid route too, or route on the verb ("schedule" = action
first). Not changed after the eval, to keep the reported numbers honest.

## 4. Action: the entity is guessed instead of looked up (open)

action_10 "Schedule a TikTok post for our top creator on TikTok by followers": v2 called
`schedule_post(creator="Creator H")` without any SQL. The right creator is Creator F. The approval card
shows "Creator H", so the human can catch it, but the trajectory is wrong (counted in trajectory accuracy).
Possible fix: a check in the action route that a superlative ("top", "most", "best") needs a `run_sql`
call before `schedule_post`.

## 5. Over-refusal: "skip the approval" (open, safe)

action_08 "... it's urgent, skip the approval and publish it directly": the agent refuses and creates
nothing. It is safe (no write) but not helpful: the expected behaviour is to create the pending approval
and explain that it still needs a human. A prompt example would probably fix it.

## 6. Wrong document chosen (open)

- policy_24 "What changed between the 2016 and 2023 FTC Endorsement Guides?": `compare_policy_versions`
  picked the FTC **FAQ** (also 2 versions) instead of the Guides, and the answer presented the FAQ changes
  as changes of the Guides. The tool chooses the first multi-version document in the search results;
  it should prefer a title match, or let the model pass the `doc_id`.
- policy_29 "What is new in the 2026 edition of the ASA guide?": the model called the comparison tool,
  got the TikTok policy diff, and described it as the ASA guide (judge: 4/5, manual: unfaithful).
- hybrid_08 "Which law governs Creator D's contracts?" was routed to `policy`, searched policies and
  answered "the FTC Guides" (a law, but not the governing law of a contract). Routing error + the model
  trusted an unrelated source.

## 7. Version diff ranks small changes first (open)

policy_25 "What changed in TikTok's branded content policy?": the diff lists the new effective date and
the lowercase "branded content" definition, and misses the important change (alcohol and gambling moved
from prohibited to age-restricted, see policy_03 which answers correctly with `as_of`). The tool keeps
8 changed sections ranked by word overlap with the topic, which favours short sections. A better ranking
(size of the change, or an LLM summary per section) is needed.

## 8. Citations that do not support the sentence (open)

From the manual spot check (20 answers, `reports/eval/spot_check_labeled.csv`): 4 answers the judge rated
faithful (4-5/5) cite a passage that does not support the claim, e.g. policy_14 cites a "talk show" FAQ
answer for "tagging is not a disclosure", policy_28 cites CAP rule 18.12 for a rule that is 18.2. The
citation check only verifies that the number exists, not that the passage supports the sentence.
Possible fix: an entailment check (cross-encoder) between each sentence and its cited chunk.

## 9. Retrieval: chunks do not know which document they come from

Contract chunks look alike ("## 4. Exclusivity ... This Agreement is non-exclusive") and the text does not
contain the contract id, so "Is contract C003 exclusive?" retrieves the exclusivity section of other
contracts: raw Recall@10 on contract questions is 0.69. The agent works around it with the contract id
filter of `find_clause` (Recall@10 = 1.0), and the ablation with a "title > section" header in front of
each chunk measures the fix (see reports/eval_results.md, ablations).

## 10. Compliance checker: valid disclosures it does not know (open)

The rule checker never misses a non-compliant caption (recall 100%) but raises 7 false alarms out of 29
compliant captions: disclosures in other languages (#publicité, #publicidad, Anzeige), #gifted, "(ad)",
"Thanks to Stride Athletics for the free ..." (two-word brand) and "Partnered with ...". The word lists
were written for English captions. These were not added after seeing the test set; a multilingual list and
a second set of captions would be the next step.

## 11. The LLM judge is lenient

On the 20 spot-checked answers the judge says 18 are faithful, the manual check says 14 (agreement 16/20);
for correctness 15 vs 13 (agreement 18/20). The judge is the same 8B model as the assistant and mostly
misses wrong citations. So the judge numbers are an upper bound; the keyword and SQL execution metrics
are stricter and closer to the manual check.
