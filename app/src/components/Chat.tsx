import { useState } from 'react'
import { api, type ChatResult, type DocSource } from '../api'
import Answer from './Answer'
import ApprovalCard from './ApprovalCard'
import DocumentViewer from './DocumentViewer'
import SourceCard from './SourceCard'

type Turn = { question: string; result?: ChatResult; error?: string }

const EXAMPLES = [
  'Which creator had the best engagement rate on Instagram Reels in July 2026?',
  'Does contract C003 have an exclusivity clause?',
  'How do I disclose a paid partnership on Instagram?',
  'What changed in the FTC endorsement guides?',
  'Schedule a post for Creator A on Instagram on 2030-01-10 18:00 with caption "New drop #ad"',
]

export default function Chat({ onApprovalChange }: { onApprovalChange: () => void }) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [active, setActive] = useState<number | null>(null) // which turn's sources are shown
  const [cited, setCited] = useState<number | null>(null)
  const [openDoc, setOpenDoc] = useState<DocSource | null>(null)

  async function ask(text: string) {
    if (!text.trim() || loading) return
    const index = turns.length
    setTurns((t) => [...t, { question: text }])
    setQuestion('')
    setLoading(true)
    try {
      const result = await api.chat(text)
      setTurns((t) => t.map((turn, i) => (i === index ? { ...turn, result } : turn)))
      setActive(index)
      setCited(null)
      if (result.status === 'waiting_approval') onApprovalChange()
    } catch (e) {
      const error = (e as Error).message
      setTurns((t) => t.map((turn, i) => (i === index ? { ...turn, error } : turn)))
    }
    setLoading(false)
  }

  async function decide(index: number, approvalId: number, approved: boolean) {
    setLoading(true)
    try {
      const result = (await api.decide(approvalId, approved)) as ChatResult
      setTurns((t) => t.map((turn, i) => (i === index ? { ...turn, result } : turn)))
      onApprovalChange()
    } catch (e) {
      alert((e as Error).message)
    }
    setLoading(false)
  }

  function showCitation(index: number, n: number) {
    setActive(index)
    setCited(n)
    setTimeout(() => document.getElementById(`source-${n}`)?.scrollIntoView({ block: 'nearest' }), 0)
  }

  const sources = active !== null ? turns[active]?.result?.sources || [] : []

  return (
    <div className="chat-layout">
      <div className="chat">
        <div className="messages">
          {turns.length === 0 && (
            <div className="examples">
              <p>Ask about platform policies, contracts or creator analytics. Try:</p>
              {EXAMPLES.map((e) => (
                <button key={e} onClick={() => ask(e)}>
                  {e}
                </button>
              ))}
            </div>
          )}
          {turns.map((turn, i) => (
            <div key={i} className={'turn' + (i === active ? ' active' : '')} onClick={() => setActive(i)}>
              <div className="question">{turn.question}</div>
              {turn.error && <div className="error">{turn.error}</div>}
              {!turn.result && !turn.error && <div className="meta">Thinking...</div>}
              {turn.result?.status === 'waiting_approval' && turn.result.pending_approval && (
                <>
                  <div className="meta">The agent wants to do this, a human has to approve it:</div>
                  <ApprovalCard
                    approval={turn.result.pending_approval}
                    busy={loading}
                    onDecide={(ok) => decide(i, turn.result!.pending_approval!.approval_id, ok)}
                  />
                </>
              )}
              {turn.result?.status === 'done' && (
                <Answer result={turn.result} onCite={(n) => showCitation(i, n)} />
              )}
            </div>
          ))}
        </div>
        <form
          className="ask"
          onSubmit={(e) => {
            e.preventDefault()
            ask(question)
          }}
        >
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question..."
            disabled={loading}
          />
          <button disabled={loading || !question.trim()}>{loading ? '...' : 'Ask'}</button>
        </form>
      </div>

      <aside className="sources">
        <h3>Sources</h3>
        {sources.length === 0 && <div className="meta">The sources of the selected answer show here.</div>}
        {sources.map((s) => (
          <SourceCard
            key={s.n}
            source={s}
            selected={s.n === cited}
            onOpen={() => s.kind === 'document' && setOpenDoc(s)}
          />
        ))}
      </aside>

      {openDoc && <DocumentViewer source={openDoc} onClose={() => setOpenDoc(null)} />}
    </div>
  )
}
