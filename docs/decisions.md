# Decisions

Choices I made during the project and why. Changes compared to the original brief are marked.

## 1. Python 3.11 with uv
uv installs Python 3.11 and pins all versions in `uv.lock`, so the project installs the same way on my Mac,
my Windows PC and in GitHub Actions. Tooling is kept small: ruff for style and pytest for tests.

## 2. Local LLM only (Ollama) (changed from the brief)
The brief suggested a hosted API plus a local model. I don't have an API budget, so everything runs with
Ollama. The default model is `qwen3:8b` because it supports tool calling and runs on a laptop.
All LLM calls go through one small client class, so another provider could be added later.
There is also a `fake` provider that returns fixed answers, used in tests and CI.

Downsides: answers are slower and weaker than with a big hosted model, and using a local model as the judge
for generation metrics is less reliable. I will check a sample of the judge's scores by hand and mention it in
the limitations.

## 3. React UI (changed from the brief)
The brief suggested Streamlit or Gradio. I chose React (Vite + TypeScript) because it gives a better demo.
To save time, the FastAPI backend is done first and the UI only calls it.

## 4. Qdrant as vector store
Qdrant supports metadata filters (platform, version, is_latest...) and upserts, which I need for versioned
documents. It can run in local mode (just a folder, no server), which is the default. Docker is available,
so `make qdrant` can also start a real server.

## 5. MLflow for experiments
MLflow with a local folder (`mlruns/`, not committed). No account needed.

## 6. Instagram first
Instagram gets the most policy pages and snapshots and is used in the demo. TikTok and YouTube have fewer pages.

## 7. English
Code, docs, report and presentation are in English.

## 8. One-week deadline (changed from the brief)
The brief planned 4 weeks; I have 1 week. What I keep: everything required by the course (RAG with metadata
and versions, citations, MCP with tools, LangGraph, 120+ eval questions with Recall@k/MRR, one fine-tuning
experiment, web UI). What I reduce:
- corpus around 120 documents (lower end of the 120-250 target)
- fine-tuning: one small encoder model only
- ablations kept cheap (they reuse the same index and eval set)
- stretch goals (multilingual, weekly report, feedback button) are dropped

## 9. Embedding model
Start with `bge-base-en-v1.5` (small, fast on CPU). Compare with `bge-m3` in one ablation if time allows.

## 10. Dependencies
Libraries are added when the code that uses them is added, not all at the start.

## 11. Where policy pages come from (changed from the brief)
Most Instagram / Meta help pages are rendered with JavaScript and return no text when downloaded (even from
the Internet Archive). So for Instagram I use Meta's Transparency Center pages (Community Standards and
Advertising Standards). They apply to Instagram and Facebook and are served as normal HTML.
Old versions come from the Internet Archive (Wayback Machine): `data/sources.csv` says which snapshot
months to download for each page. The FTC Endorsement Guides come from the official eCFR API, which gives the
text at a given date (2016 version and the 2023 revision). The FTC website itself blocks scripts, so its pages
also come from the Wayback Machine.
Pages that come back almost empty (less than 300 characters after parsing) are skipped during ingestion.

## 12. No page numbers
All sources are HTML, XML, markdown or plain text (CUAD contracts are .txt), so `page` is always empty.
Citations use the section path and character offsets instead, which is more precise anyway.

## 13. Versions are decided by content, not by date
The download script can fetch two snapshots of a page that have the same text. Ingestion compares the
sha256 of the parsed text: same hash means "unchanged" and no new version is created. Each version has a
`valid_from` (its snapshot date) and `valid_to` (the date of the next version), so a question like "what
was the rule in 2024?" searches the version that was valid on that date.

## 14. Synthetic contracts from templates
The brief suggested LLM-generated contracts. I generate them from a template filled with the values of
`contracts_index` (dates, fee, exclusivity) and random choices for the other clauses (seeded). This is
reproducible and the contract text always matches the SQL data, which is needed for hybrid questions.

## 15. Hybrid search with Reciprocal Rank Fusion
Dense search is good with paraphrases, BM25 is good with exact words (clause names, "#ad", section numbers).
I take the top 30 of each and merge them with Reciprocal Rank Fusion (k = 60). RRF only uses ranks, so I don't
have to normalize two very different score scales. The BM25 index is rebuilt in memory from the chunk registry
at startup (about 7,500 chunks, a few seconds) instead of being saved to disk.

## 16. Reranker
`bge-reranker-v2-m3` reranks the 30 fused candidates. It took about 1.8 s per query on my Mac in a first manual
test, which is fine for the assistant. The ablation will measure if it is worth the extra time.

## 17. SQL safety with the SQLite authorizer
Instead of parsing SQL with regexes, the SQL tool uses SQLite's own authorizer callback: SQLite asks it
before every action, and only SELECT, reading allowlisted tables and calling functions are allowed. The
file is also opened read-only, there is a time limit (progress handler) and a row limit. A small text check
(one statement, starts with SELECT/WITH) gives clearer error messages. Tested with 11 unsafe queries
(DELETE, DROP, multiple statements, PRAGMA, ATTACH, a hidden table, sqlite_master...).

## 18. Tools return sources, not answers
`search_policies`, `find_clause` and `compare_policy_versions` return passages with all citation fields
(source id, title, section, snapshot date, version, URL). The agent writes the answer and must cite these
source ids. `compare_policy_versions` does a section-by-section diff without an LLM; the agent summarizes it.

## 19. Own small Ollama client instead of LangChain's chat model
LangGraph is used for the agent (state, routing, tool loop, interrupt for approvals, checkpointer).
For the LLM itself I call Ollama's `/api/chat` with httpx in ~40 lines (`llm/client.py`). It supports tool
calling and JSON mode, lets me turn off qwen3's "thinking" and returns token counts for the cost metrics.
A `FakeLLM` with the same `chat()` method makes the graph testable in CI without a model.

## 20. Router + tool subsets
A first LLM call classifies the question (policy / contract / sql / hybrid / action / out_of_scope) in JSON
mode, with a keyword router as fallback. Each route only gets the tools it needs (a small model makes fewer
wrong tool calls with fewer tools), and out-of-scope questions are refused without calling any tool. The
`use_router=False` option gives every tool to every question, for the "without routing" ablation.

## 21. Approval with a LangGraph interrupt + the approvals table
`schedule_post` never writes directly. The agent's call creates a pending row in `approvals`, then the
graph stops (`interrupt`). The run is resumed with the human decision; only an approval adds the row to
`schedule`. Rows are also visible in the approvals table, so the UI and the MCP client can show the queue.

## 22. Citation rules
Every tool result gets a number. After the answer, `citations.verify` removes numbers that don't exist,
does not accept citations of an empty SQL result, and marks the answer as:
- abstained: the model says it does not know, or there is no usable source for a question that needs one
  (the answer is then replaced by a standard "not enough information" message)
- unverified: sources exist but the answer cites none of them (shown with a warning)

## 23. Prompt fixes found while testing (before building the eval set)
First manual runs showed the model joining `posts` directly to `creators`, using `format = 'Reels'` and
integer division (engagement rate 0.0), and once inventing "12.5%" from an empty result. Fixes: the schema hint
now includes join keys, allowed values and the engagement-rate formula, one example engagement-rate query is
in the prompt, and empty SQL results are shown as "0 rows". Because the example query is close to some
analytics questions, the eval set must not reuse it word for word (noted in the eval protocol).

## 24. MCP server reuses the same tool functions, without an approve tool
The MCP server is a thin layer (MCPServer from the official `mcp` SDK, stdio) over the functions in
`creatorops.tools`, so the agent, the API and MCP clients always behave the same. `schedule_post` only creates
a pending approval and no MCP tool can approve it: the human-in-the-loop rule also holds when another LLM
(Claude Desktop, Cursor...) is the caller. Tools return plain dicts; the SDK sends them as JSON text.

## 25. Simple React UI with a dev proxy
The UI is plain React state (no router, no state library, no component library), 4 tabs and one CSS file:
it is a demo / evaluation tool, not a product. Vite proxies `/api` to FastAPI so the browser never does
cross-origin calls in dev (CORS is still configured for direct calls). Each chat question starts a new
agent thread: questions are independent, and it keeps the evaluation and the UI behaving the same.
Citations link to the exact passage in the stored version of the document (not the live page), so what
the user checks is what the model read.
