import type { ChatResult } from '../api'
import { Markdown } from '../markdown'

const ROUTE_LABEL: Record<string, string> = {
  policy: 'Policy',
  contract: 'Contract',
  sql: 'Analytics',
  hybrid: 'Data + documents',
  action: 'Action',
  out_of_scope: 'Out of scope',
}

// The answer text with every [n] turned into a citation chip, + warnings and a small meta line.
export default function Answer({ result, activeCite, onCite }: {
  result: ChatResult
  activeCite: number | null
  onCite: (n: number) => void
}) {
  const renderText = (text: string, key: string) =>
    text.split(/(\[\d+\])/g).map((part, i) => {
      const match = part.match(/^\[(\d+)\]$/)
      if (!match) return part
      const n = Number(match[1])
      const valid = result.citations.includes(n)
      return (
        <button
          key={`${key}-c${i}`}
          className={'cite' + (valid ? '' : ' invalid') + (n === activeCite ? ' active' : '')}
          title={valid ? 'Show this source' : 'This source does not exist'}
          onClick={() => valid && onCite(n)}
        >
          {n}
        </button>
      )
    })

  const tools = [...new Set(result.tool_calls.map((c) => c.name))]

  return (
    <div className="answer">
      {result.abstained && (
        <div className="notice warn">Not enough information in the sources to answer this.</div>
      )}
      {result.unverified && !result.abstained && (
        <div className="notice warn">This answer cites no source, check it before using it.</div>
      )}
      <Markdown text={result.answer || ''} renderText={renderText} />
      <div className="answer-meta">
        {result.route && <span className={`route route-${result.route}`}>{ROUTE_LABEL[result.route] || result.route}</span>}
        {tools.map((t) => (
          <span key={t} className="tool-chip">
            {t}
          </span>
        ))}
        <span className="muted">{result.latency_s}s</span>
      </div>
    </div>
  )
}
