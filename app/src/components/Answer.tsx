import type { ChatResult } from '../api'

// Shows the answer text and turns every [n] into a clickable citation chip.
export default function Answer({
  result,
  onCite,
}: {
  result: ChatResult
  onCite: (n: number) => void
}) {
  const text = result.answer || ''
  const parts = text.split(/(\[\d+\])/g)

  return (
    <div className="answer">
      {result.abstained && <div className="badge warn">Not enough information in the sources</div>}
      {result.unverified && <div className="badge warn">No source cited, check this answer</div>}
      <p>
        {parts.map((part, i) => {
          const match = part.match(/^\[(\d+)\]$/)
          if (!match) return <span key={i}>{part}</span>
          const n = Number(match[1])
          const valid = result.citations.includes(n)
          return (
            <button
              key={i}
              className={valid ? 'cite' : 'cite invalid'}
              title={valid ? 'Show source' : 'This source does not exist'}
              onClick={() => valid && onCite(n)}
            >
              {n}
            </button>
          )
        })}
      </p>
      <div className="meta">
        route: {result.route} · tools: {result.tool_calls.map((c) => c.name).join(', ') || 'none'} ·{' '}
        {result.latency_s}s
      </div>
    </div>
  )
}
