import { useEffect, useRef, useState } from 'react'
import { api, type ChatResult, type DocSource } from '../api'
import { useToast } from '../toast'
import Answer from './Answer'
import ApprovalCard from './ApprovalCard'
import DocumentViewer from './DocumentViewer'
import { SendIcon, SparkIcon } from './Icons'
import SourceCard from './SourceCard'

type Turn = { question: string; result?: ChatResult; error?: string }

const EXAMPLES = [
  { tag: 'Policy', text: 'Can I rely only on Instagram\'s paid partnership tool to disclose a sponsorship?' },
  { tag: 'Versions', text: 'Under the TikTok branded content policy valid in December 2024, could creators promote alcohol?' },
  { tag: 'Contract', text: 'Is contract C003 exclusive, and what are its payment terms?' },
  { tag: 'Analytics', text: 'Which creator had the highest engagement rate on Instagram Reels in July 2026?' },
  { tag: 'Compliance', text: "Is this caption ok for a paid Instagram post: 'New drop! #fashion #ootd #style #ad #streetwear'" },
  { tag: 'Action', text: "Schedule an Instagram post for Creator A on 2027-03-05 18:00 with the caption 'Spring looks #ad'" },
  { tag: 'Ticket', text: 'Create a high priority ticket to add a disclosure to post 166' },
  { tag: 'Analytics + SOP', text: 'Creator F got a huge number of likes on 2026-08-12. What does our reporting SOP say about it?' },
]

export default function Chat({ onApprovalChange, onOpenTicket }: {
  onApprovalChange: () => void
  onOpenTicket: (id: number) => void
}) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [active, setActive] = useState<number | null>(null) // turn whose sources are shown
  const [cited, setCited] = useState<number | null>(null)
  const [openDoc, setOpenDoc] = useState<DocSource | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const toast = useToast()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [turns])

  // the text box grows with the text (up to a limit)
  useEffect(() => {
    const box = inputRef.current
    if (box) {
      box.style.height = 'auto'
      box.style.height = Math.min(box.scrollHeight, 160) + 'px'
    }
  }, [question])

  async function ask(text: string) {
    if (!text.trim() || loading) return
    const index = turns.length
    setTurns((t) => [...t, { question: text.trim() }])
    setQuestion('')
    setLoading(true)
    try {
      const result = await api.chat(text.trim())
      setTurns((t) => t.map((turn, i) => (i === index ? { ...turn, result } : turn)))
      setActive(index)
      setCited(result.citations[0] ?? null)
      // a new approval request or a new ticket: refresh the badges
      if (result.status === 'waiting_approval' || result.sources.some((s) => s.kind === 'ticket')) onApprovalChange()
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
      toast(approved ? 'Approved: the post is in the calendar' : 'Rejected: nothing was scheduled')
    } catch (e) {
      toast((e as Error).message, 'error')
    }
    setLoading(false)
  }

  function showCitation(index: number, n: number) {
    setActive(index)
    setCited(n)
    setTimeout(() => document.getElementById(`source-${n}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 0)
  }

  const activeResult = active !== null ? turns[active]?.result : undefined
  const sources = activeResult?.sources || []
  // cited sources first, the others after
  const sorted = [...sources].sort(
    (a, b) => Number(!activeResult?.citations.includes(a.n)) - Number(!activeResult?.citations.includes(b.n)),
  )

  return (
    <div className="chat-layout">
      <section className="chat">
        <div className="messages">
          {turns.length === 0 && (
            <div className="welcome">
              <div className="welcome-icon">
                <SparkIcon size={26} />
              </div>
              <h2>What do you need to check today?</h2>
              <p>Every answer comes with its sources: the policy snapshot, the contract clause or the SQL query.</p>
              <div className="examples">
                {EXAMPLES.map((e) => (
                  <button key={e.text} className="example" onClick={() => ask(e.text)}>
                    <span className="example-tag">{e.tag}</span>
                    {e.text}
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((turn, i) => (
            <div key={i} className="turn">
              <div className="bubble user">{turn.question}</div>
              <div
                className={'bubble assistant' + (i === active ? ' selected' : '')}
                onClick={() => turn.result && setActive(i)}
              >
                <div className="avatar">CO</div>
                <div className="bubble-body">
                  {turn.error && <div className="notice error">{turn.error}</div>}
                  {!turn.result && !turn.error && (
                    <div className="typing" data-loading="true">
                      <span />
                      <span />
                      <span />
                      Searching the sources...
                    </div>
                  )}
                  {turn.result?.status === 'waiting_approval' && turn.result.pending_approval && (
                    <>
                      <p className="approval-intro">I prepared this action. A human has to approve it before anything is scheduled:</p>
                      <ApprovalCard
                        approval={turn.result.pending_approval}
                        onOpenTicket={onOpenTicket}
                        busy={loading}
                        onDecide={(ok) => decide(i, turn.result!.pending_approval!.approval_id, ok)}
                      />
                    </>
                  )}
                  {turn.result?.status === 'done' && turn.result.approval?.decision && (
                    <div className="decided">
                      <ApprovalCard approval={turn.result.approval} onOpenTicket={onOpenTicket} />
                    </div>
                  )}
                  {turn.result?.status === 'done' && (
                    <Answer result={turn.result} activeCite={i === active ? cited : null} onCite={(n) => showCitation(i, n)} />
                  )}
                </div>
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault()
            ask(question)
          }}
        >
          <textarea
            ref={inputRef}
            rows={1}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                ask(question)
              }
            }}
            placeholder="Ask about a policy, a contract or a creator's numbers..."
            disabled={loading}
          />
          <button className="send" disabled={loading || !question.trim()} title="Send">
            <SendIcon />
          </button>
        </form>
        <div className="composer-hint">Enter to send · Shift + Enter for a new line · answers run on a local model</div>
      </section>

      <aside className="sources">
        <div className="sources-head">
          <h3>Sources</h3>
          {sources.length > 0 && <span className="muted">{sources.length}</span>}
        </div>
        {sources.length === 0 && (
          <div className="empty small">The sources used for an answer will show here. Click a number in the answer to jump to it.</div>
        )}
        {sorted.map((s) => (
          <SourceCard
            key={s.n}
            source={s}
            cited={s.kind === 'ticket' || Boolean(activeResult?.citations.includes(s.n))}
            selected={s.n === cited}
            onSelect={() => setCited(s.n)}
            onOpen={() => {
              if (s.kind === 'document') setOpenDoc(s)
              if (s.kind === 'ticket') onOpenTicket(s.ticket_id)
            }}
          />
        ))}
      </aside>

      {openDoc && <DocumentViewer source={openDoc} onClose={() => setOpenDoc(null)} />}
    </div>
  )
}
