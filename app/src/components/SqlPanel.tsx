import { useEffect, useState } from 'react'
import { api, type SqlResult } from '../api'
import { PlayIcon } from './Icons'
import SqlTable from './SqlTable'

const EXAMPLES = [
  {
    name: 'Followers on Instagram',
    query: `SELECT c.name, a.followers
FROM accounts a
JOIN creators c ON c.creator_id = a.creator_id
JOIN platforms p ON p.platform_id = a.platform_id
WHERE p.name = 'Instagram'
ORDER BY a.followers DESC`,
  },
  {
    name: 'Paid posts without disclosure',
    query: `SELECT p.post_id, c.name, p.posted_at, p.caption
FROM posts p
JOIN accounts a ON a.account_id = p.account_id
JOIN creators c ON c.creator_id = a.creator_id
WHERE p.is_paid = 1 AND p.has_disclosure = 0`,
  },
  {
    name: 'Engagement rate by format',
    query: `SELECT p.format,
       ROUND(1.0 * SUM(m.likes + m.comments + m.shares + m.saves) / SUM(m.reach), 4) AS engagement_rate
FROM posts p
JOIN post_metrics_daily m ON m.post_id = p.post_id
GROUP BY p.format
ORDER BY engagement_rate DESC`,
  },
  {
    name: 'Contracts with exclusivity',
    query: `SELECT ci.contract_id, c.name AS creator, b.name AS brand, ci.end_date, ci.exclusivity_category
FROM contracts_index ci
JOIN creators c ON c.creator_id = ci.creator_id
JOIN brands b ON b.brand_id = ci.brand_id
WHERE ci.exclusivity = 1
ORDER BY ci.end_date`,
  },
]

type Schema = Record<string, { description: string; columns: Record<string, string> }>

// Read-only SQL console on the analytics database (same checks as the agent's run_sql tool).
export default function SqlPanel() {
  const [query, setQuery] = useState(EXAMPLES[0].query)
  const [result, setResult] = useState<SqlResult | null>(null)
  const [schema, setSchema] = useState<Schema>({})
  const [running, setRunning] = useState(false)

  useEffect(() => {
    api.schema().then((s) => setSchema(s.tables))
  }, [])

  async function run() {
    setRunning(true)
    try {
      setResult(await api.sql(query))
    } catch (e) {
      setResult({ error: (e as Error).message })
    }
    setRunning(false)
  }

  return (
    <div className="content sql-layout">
      <div className="sql-main">
        <div className="card">
          <div className="examples-row">
            {EXAMPLES.map((e) => (
              <button key={e.name} className="pill" onClick={() => setQuery(e.query)}>
                {e.name}
              </button>
            ))}
          </div>
          <textarea
            className="editor"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) run()
            }}
            rows={9}
            spellCheck={false}
          />
          <div className="editor-foot">
            <span className="muted small-text">
              Read-only: only one SELECT, allowlisted tables, 5 s timeout, 200 rows max. ⌘ + Enter to run.
            </span>
            <button className="btn primary" onClick={run} disabled={running}>
              <PlayIcon size={14} /> {running ? 'Running...' : 'Run query'}
            </button>
          </div>
        </div>

        {result?.error && <div className="notice error">{result.error}</div>}
        {result?.rows && (
          <div className="card">
            <div className="card-title">
              Result <span className="muted">{result.row_count} rows{result.truncated && ' (truncated)'}</span>
            </div>
            <SqlTable columns={result.columns || []} rows={result.rows} />
          </div>
        )}
      </div>

      <aside className="card schema">
        <div className="card-title">Tables</div>
        {Object.entries(schema).map(([table, info]) => (
          <details key={table}>
            <summary>{table}</summary>
            <p className="muted small-text">{info.description}</p>
            <ul>
              {Object.entries(info.columns).map(([col, type]) => (
                <li key={col}>
                  <code>{col}</code> <span className="muted">{type.toLowerCase()}</span>
                </li>
              ))}
            </ul>
          </details>
        ))}
      </aside>
    </div>
  )
}
