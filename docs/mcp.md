# MCP server

The tools of the agent are also exposed as an [MCP](https://modelcontextprotocol.io) server
(`src/creatorops/mcp_server/server.py`, official Python SDK). Any MCP client can use them,
for example Claude Desktop, Cursor or the small demo client in `examples/`.

## Tools

| Tool | What it does | Writes? |
|---|---|---|
| `search_policies` | hybrid search over platform policies, regulations and SOPs (`platform`, `as_of` filters) | no |
| `compare_policy_versions` | section-by-section diff of the two latest versions of a policy | no |
| `find_clause` | find a clause type (exclusivity, payment, ...) in the contracts | no |
| `run_sql` | one read-only SELECT on the analytics database | no |
| `explain_schema` | tables, columns and join keys | no |
| `schedule_post` | creates a **pending approval**, nothing is scheduled yet | approvals table only |
| `list_approvals` | list pending / approved / rejected requests | no |

There is also one resource, `creatorops://schema`, with the schema as plain text.

There is on purpose **no tool to approve a request**. An MCP client (so an LLM) can only ask;
a human decides in the React UI or with `POST /approvals/{id}/decision`.

## Run it

```bash
make mcp                               # stdio server
uv run python examples/mcp_client_demo.py   # starts the server and calls 4 tools
```

The database and the index must exist first (`make db corpus ingest`).

## Claude Desktop config

Add this to `claude_desktop_config.json`
(macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`) and restart the app.
Change the path to where you cloned the repo.

```json
{
  "mcpServers": {
    "creatorops": {
      "command": "uv",
      "args": ["--directory", "/path/to/CreatorOps-Copilot", "run", "python", "-m",
               "creatorops.mcp_server.server"],
      "env": { "HF_HUB_OFFLINE": "1" }
    }
  }
}
```

`HF_HUB_OFFLINE=1` stops the embedding / reranker models from checking Hugging Face at every
start (they must have been downloaded once before, e.g. by `make ingest`).
