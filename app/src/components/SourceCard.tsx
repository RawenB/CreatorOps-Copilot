import type { Source } from '../api'
import SqlTable from './SqlTable'

export default function SourceCard({
  source,
  selected,
  onOpen,
}: {
  source: Source
  selected: boolean
  onOpen: () => void
}) {
  return (
    <div id={`source-${source.n}`} className={'source' + (selected ? ' selected' : '')}>
      <div className="source-head">
        <span className="cite">{source.n}</span>
        {source.kind === 'document' && (
          <span>
            <b>{source.title}</b>
            {source.section && <div className="meta">{source.section}</div>}
          </span>
        )}
        {source.kind === 'sql' && <b>SQL result</b>}
        {source.kind === 'compliance' && <b>Compliance check</b>}
        {source.kind === 'classification' && <b>Clause classifier</b>}
        {source.kind === 'comparison' && (
          <b>
            {source.title}: v{source.old_version.version} ({source.old_version.snapshot_date}) → v
            {source.new_version.version} ({source.new_version.snapshot_date})
          </b>
        )}
      </div>

      {source.kind === 'document' && (
        <>
          <div className="meta">
            {source.doc_type} · {source.platform || 'all platforms'} · snapshot {source.snapshot_date}
            {source.is_latest === false && ' · old version'}
            {source.synthetic && ' · synthetic'}
          </div>
          <div className="excerpt">{source.text.slice(0, 400)}...</div>
          <button onClick={onOpen}>Open in document</button>
        </>
      )}

      {source.kind === 'sql' && (
        <>
          <pre className="sql">{source.query}</pre>
          <SqlTable columns={source.columns} rows={source.rows.slice(0, 20)} />
          {(source.truncated || source.rows.length > 20) && <div className="meta">more rows not shown</div>}
        </>
      )}

      {source.kind === 'compliance' && (
        <div>
          <span className={'badge ' + (source.verdict === 'compliant' ? 'approved' : 'rejected')}>
            {source.verdict.replace('_', ' ')}
          </span>
          <ul>
            {source.problems.map((p) => (
              <li key={p.rule}>{p.message}</li>
            ))}
          </ul>
        </div>
      )}

      {source.kind === 'classification' && (
        <div>
          <b>{source.label}</b>
          <div className="meta">
            {Object.entries(source.scores)
              .map(([label, p]) => `${label} ${(100 * p).toFixed(0)}%`)
              .join(' · ')}
          </div>
        </div>
      )}

      {source.kind === 'comparison' && (
        <div>
          <div className="meta">{source.n_changes} changed sections</div>
          {source.changes.map((c, i) => (
            <div key={i} className="change">
              <b>
                {c.change}: {c.section}
              </b>
              {c.diff && (
                <pre className="diff">
                  {c.diff.map((line, j) => (
                    <div key={j} className={line.startsWith('+') ? 'plus' : 'minus'}>
                      {line}
                    </div>
                  ))}
                </pre>
              )}
              {c.new_text && <div className="excerpt plus">{c.new_text}</div>}
              {c.old_text && <div className="excerpt minus">{c.old_text}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
