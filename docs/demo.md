# Demo script (about 10 minutes)

## Before

```bash
ollama serve                      # if it is not already running (qwen3:8b pulled)
make api                          # terminal 1, FastAPI on :8000
make ui                           # terminal 2, React on :5173
cp data/creatorops.sqlite /tmp/creatorops_backup.sqlite   # to reset the data after the demo
```

Open http://localhost:5173. The first question takes longer (the models load).

## 1. Policy question with a citation (2 min)

Chat: **"Can I rely only on Instagram's built-in paid partnership tool to disclose a sponsorship?"**

- Show the route (policy) and the tools called under the answer.
- Click the citation number: the sources panel shows the FTC passage, "Open in document" shows the full
  stored snapshot with the passage highlighted, plus its snapshot date and version.

## 2. Version-aware question (1 min)

Chat: **"Under the TikTok branded content policy valid in December 2024, could creators promote alcohol?"**

- The answer is "no": the agent searched with `as_of` = 2024-12-01 and got version 1 of the policy.
- Then: **"Can a creator post branded content for an alcohol brand on TikTok under the current policy?"**
  gives "yes, with age restrictions" from version 2.

## 3. Analytics + documents (2 min)

Chat: **"Creator B has paid posts without a disclosure. Which posts, and how should a sponsored caption be
disclosed according to our SOP?"**

- Sources: the SQL query + rows (posts 166 and 168), and the SOP passage.
- SQL tab: run `SELECT * FROM posts WHERE is_paid = 1 AND has_disclosure = 0`, then try
  `DELETE FROM posts` to show it is rejected.

## 4. Compliance check (1 min)

Chat: **"Is this caption ok for a paid Instagram post: 'New drop! #fashion #ootd #style #ad #streetwear'"**

- `check_post_compliance` says non-compliant (disclosure mixed into hashtags) and cites the FTC rule.

## 5. Human in the loop (2 min)

Chat: **"Schedule an Instagram post for Creator A on 2027-03-05 18:00 with the caption 'Spring looks are
here #ad'."**

- The graph stops: an approval card appears in the chat and in the Approvals tab (badge count).
- Calendar tab: nothing new yet. Approve, the agent finishes its answer, the post appears in the calendar.
- Then: "Schedule a post for Creator Z ..." is refused (unknown creator, nothing is created).

## 6. MCP (1 min)

```bash
uv run python examples/mcp_client_demo.py
```

Shows the tool list and 4 tool calls from an external MCP client; its `schedule_post` request shows up in
the Approvals tab of the UI.

## 7. Results (1 min)

Open `reports/eval_results.md`: v1 vs v2 table, the judge vs manual spot check, the fine-tuning table
(`reports/finetuning.md`), and one or two failures from `docs/error_analysis.md` (router gap for
"look up then schedule", wrong document in the version comparison).

## After

```bash
cp /tmp/creatorops_backup.sqlite data/creatorops.sqlite
```
