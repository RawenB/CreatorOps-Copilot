import { useEffect, useState } from 'react'
import { api, type SqlResult } from '../api'
import SqlTable from './SqlTable'

const DEFAULT_QUERY = `SELECT c.name, a.followers
FROM accounts a
JOIN creators c ON c.creator_id = a.creator_id
JOIN platforms p ON p.platform_id = a.platform_id
WHERE p.name = 'Instagram'
ORDER BY a.followers DESC`

type Schema = Record<string, { description: string; columns: Record<string, string> }>

// Read-only SQL console on the analytics database (same checks as the agent's run_sql tool).
export default function SqlPanel() {
  const [query, setQuery] = useState(DEFAULT_QUERY)
  const [result, setResult] = useState<SqlResult | null>(null)
  const [schema, setSchema] = useState<Schema>({})

  useEffect(() => {
    api.schema().then((s) => setSchema(s.tables))
  }, [])

  async function run() {
    try {
      setResult(await api.sql(query))
    } catch (e) {
      setResult({ error: (e as Error).message })
    }
  }

  return (
    <div className="sql-layout">
      <div>
        <textarea value={query} onChange={(e) => setQuery(e.target.value)} rows={8} spellCheck={false} />
        <button onClick={run}>Run (read-only)</button>
        {result?.error && <div className="error">{result.error}</div>}
        {result?.rows && (
          <>
            <div className="meta">
              {result.row_count} rows{result.truncated && ' (truncated)'}
            </div>
            <SqlTable columns={result.columns || []} rows={result.rows} />
          </>
        )}
      </div>
      <aside className="schema">
        <h3>Schema</h3>
        {Object.entries(schema).map(([table, info]) => (
          <details key={table}>
            <summary>{table}</summary>
            <div className="meta">{info.description}</div>
            <ul>
              {Object.entries(info.columns).map(([col, type]) => (
                <li key={col}>
                  {col} <span className="meta">{type}</span>
                </li>
              ))}
            </ul>
          </details>
        ))}
      </aside>
    </div>
  )
}
