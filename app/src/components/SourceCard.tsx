import { useState } from 'react'
import type { Source } from '../api'
import { lastSection, plainText } from '../format'
import { DocIcon } from './Icons'
import SqlTable from './SqlTable'

const DOC_TYPE: Record<string, string> = {
  platform_policy: 'Policy',
  regulation: 'Regulation',
  sop: 'Agency SOP',
  contract: 'Contract',
}

function tagOf(source: Source): { label: string; className: string } {
  if (source.kind === 'document') return { label: DOC_TYPE[source.doc_type] || source.doc_type, className: source.doc_type }
  if (source.kind === 'sql') return { label: 'SQL', className: 'sql' }
  if (source.kind === 'comparison') return { label: 'Version diff', className: 'diff' }
  if (source.kind === 'compliance') return { label: 'Compliance', className: 'compliance' }
  return { label: 'Classifier', className: 'classifier' }
}

export default function SourceCard({ source, cited, selected, onSelect, onOpen }: {
  source: Source
  cited: boolean
  selected: boolean
  onSelect: () => void
  onOpen: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const tag = tagOf(source)
  // the section title is often also the first line of the text: don't show it twice
  let excerpt = source.kind === 'document' ? plainText(source.text) : ''
  const section = source.kind === 'document' ? lastSection(source.section) : ''
  if (section && excerpt.startsWith(section)) excerpt = excerpt.slice(section.length).trim()

  return (
    <div
      id={`source-${source.n}`}
      className={'source' + (selected ? ' selected' : '') + (cited ? '' : ' not-cited')}
      onClick={onSelect}
    >
      <div className="source-top">
        <span className="source-n">{source.n}</span>
        <span className={`tag tag-${tag.className}`}>{tag.label}</span>
        {!cited && <span className="muted small-text">not cited</span>}
      </div>

      {source.kind === 'document' && (
        <>
          <div className="source-title">{source.title}</div>
          {section && <div className="source-section">{section}</div>}
          <div className="source-meta">
            {source.platform && source.platform !== 'all' && <span>{source.platform}</span>}
            {source.version && <span>v{source.version}</span>}
            {source.snapshot_date && <span>snapshot {source.snapshot_date}</span>}
            {source.is_latest === false && <span className="old">old version</span>}
            {source.synthetic && <span>synthetic</span>}
          </div>
          {excerpt && <p className={'excerpt' + (expanded ? ' expanded' : '')}>{excerpt}</p>}
          <div className="source-actions">
            <button className="link" onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }}>
              {expanded ? 'Show less' : 'Show more'}
            </button>
            <button className="link" onClick={(e) => { e.stopPropagation(); onOpen() }}>
              <DocIcon size={14} /> Open document
            </button>
          </div>
        </>
      )}

      {source.kind === 'sql' && (
        <>
          <pre className="code small">{source.query.trim()}</pre>
          <SqlTable columns={source.columns} rows={source.rows.slice(0, 10)} />
          {source.rows.length > 10 && <div className="muted small-text">{source.rows.length - 10} more rows</div>}
        </>
      )}

      {source.kind === 'comparison' && (
        <>
          <div className="source-title">{source.title}</div>
          <div className="source-meta">
            <span>v{source.old_version.version} ({source.old_version.snapshot_date})</span>
            <span>→ v{source.new_version.version} ({source.new_version.snapshot_date})</span>
            <span>{source.n_changes} changed sections</span>
          </div>
          {source.changes.slice(0, expanded ? undefined : 3).map((c, i) => (
            <div key={i} className="change">
              <div className="change-title">
                <span className={`change-kind ${c.change}`}>{c.change}</span> {lastSection(c.section)}
              </div>
              {c.diff && (
                <pre className="diff">
                  {c.diff.slice(0, 6).map((line, j) => (
                    <div key={j} className={line.startsWith('+') ? 'plus' : 'minus'}>
                      {plainText(line).slice(0, 160)}
                    </div>
                  ))}
                </pre>
              )}
              {c.new_text && <p className="excerpt plus">{plainText(c.new_text)}</p>}
              {c.old_text && <p className="excerpt minus">{plainText(c.old_text)}</p>}
            </div>
          ))}
          {source.changes.length > 3 && (
            <button className="link" onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }}>
              {expanded ? 'Show less' : `Show all ${source.changes.length} changes`}
            </button>
          )}
        </>
      )}

      {source.kind === 'compliance' && (
        <>
          <div className={'verdict ' + source.verdict}>
            {source.verdict === 'compliant' ? 'Compliant' : 'Not compliant'}
          </div>
          {source.problems.length > 0 && (
            <ul className="problems">
              {source.problems.map((p) => (
                <li key={p.rule}>{p.message}</li>
              ))}
            </ul>
          )}
        </>
      )}

      {source.kind === 'classification' && (
        <div className="scores">
          {Object.entries(source.scores).map(([label, p]) => (
            <div key={label} className="score-row">
              <span>{label.replace('_', ' ')}</span>
              <div className="bar">
                <div style={{ width: `${Math.round(100 * p)}%` }} />
              </div>
              <span className="muted">{Math.round(100 * p)}%</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
