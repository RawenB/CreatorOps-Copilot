import { useEffect, useState } from 'react'
import { api, type NewTicket, type Ticket } from '../api'
import { useToast } from '../toast'
import { CloseIcon } from './Icons'

const REFERENCE_HINT: Record<string, string> = {
  contract: 'e.g. C003',
  campaign: 'campaign id, e.g. 6',
  post: 'post id, e.g. 166',
  creator: 'e.g. Creator B',
  policy: 'document id, e.g. ftc_disclosures_101',
}

type Suggestions = Record<string, { value: string; label: string }[]>

// Create a ticket: a task for the team, or a post request (which also goes to the approval queue).
export default function TicketForm({ initial, onClose, onCreated }: {
  initial?: Partial<NewTicket>
  onClose: () => void
  onCreated: (ticket: Ticket) => void
}) {
  const [form, setForm] = useState<NewTicket>({ kind: 'task', priority: 'medium', platform: 'Instagram', ...initial })
  const [suggestions, setSuggestions] = useState<Suggestions>({})
  const [creators, setCreators] = useState<string[]>([])
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const toast = useToast()
  const set = (key: keyof NewTicket, value: string) => setForm((f) => ({ ...f, [key]: value }))

  useEffect(() => {
    // suggestions for the reference field, from the (read-only) SQL endpoint
    const load = async (type: string, query: string) => {
      const result = await api.sql(query)
      return [type, (result.rows || []).map((r) => ({ value: String(r[0]), label: String(r[1]) }))] as const
    }
    Promise.all([
      load('contract', "SELECT ci.contract_id, b.name || ' x ' || c.name FROM contracts_index ci JOIN brands b ON b.brand_id = ci.brand_id JOIN creators c ON c.creator_id = ci.creator_id"),
      load('campaign', 'SELECT campaign_id, name FROM campaigns'),
      load('creator', 'SELECT name, niche FROM creators'),
    ]).then((lists) => setSuggestions(Object.fromEntries(lists)))
    api.creators().then((rows) => setCreators(rows.map((r) => r[1])))
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError('')
    const body = { ...form }
    if (body.post_datetime) body.post_datetime = body.post_datetime.replace('T', ' ')
    if (!body.reference_type) {
      delete body.reference_type
      delete body.reference_id
    }
    try {
      const ticket = await api.createTicket(body)
      toast(`${ticket.code} created` + (ticket.kind === 'post_request' ? ', waiting for approval' : ''))
      onCreated(ticket)
    } catch (err) {
      setError((err as Error).message)
    }
    setSaving(false)
  }

  const isPost = form.kind === 'post_request'

  return (
    <div className="overlay" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <div className="modal-head">
          <h3>New ticket</h3>
          <button type="button" className="icon-button" onClick={onClose}>
            <CloseIcon />
          </button>
        </div>

        <div className="modal-body">
          <div className="segmented full">
            <button type="button" className={!isPost ? 'on' : ''} onClick={() => set('kind', 'task')}>
              Task
            </button>
            <button type="button" className={isPost ? 'on' : ''} onClick={() => set('kind', 'post_request')}>
              Post request
            </button>
          </div>
          <p className="muted small-text">
            {isPost
              ? 'A post request goes to the Approvals queue. Nothing is scheduled until someone approves it.'
              : 'A to-do for the team. It can point to a contract, campaign, post, creator or policy.'}
          </p>

          {!isPost && (
            <>
              <label>
                Title *
                <input required value={form.title || ''} onChange={(e) => set('title', e.target.value)} placeholder="Add a disclosure to post 166" />
              </label>
              <label>
                Description
                <textarea rows={3} value={form.description || ''} onChange={(e) => set('description', e.target.value)} />
              </label>
              <div className="row">
                <label>
                  Priority
                  <select value={form.priority} onChange={(e) => set('priority', e.target.value)}>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </select>
                </label>
                <label>
                  Assignee
                  <input value={form.assignee || ''} onChange={(e) => set('assignee', e.target.value)} placeholder="account manager" />
                </label>
              </div>
            </>
          )}

          {isPost && (
            <>
              <div className="row">
                <label>
                  Creator *
                  <select required value={form.creator || ''} onChange={(e) => set('creator', e.target.value)}>
                    <option value="">Choose...</option>
                    {creators.map((c) => (
                      <option key={c}>{c}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Platform *
                  <select value={form.platform} onChange={(e) => set('platform', e.target.value)}>
                    <option>Instagram</option>
                    <option>TikTok</option>
                    <option>YouTube</option>
                  </select>
                </label>
              </div>
              <label>
                Date and time *
                <input required type="datetime-local" value={form.post_datetime || ''} onChange={(e) => set('post_datetime', e.target.value)} />
              </label>
              <label>
                Caption *
                <textarea required rows={3} value={form.caption || ''} onChange={(e) => set('caption', e.target.value)} placeholder="#ad ..." />
              </label>
            </>
          )}

          <label>
            Link
            <input type="url" value={form.link || ''} onChange={(e) => set('link', e.target.value)} placeholder="https://drive.google.com/... (draft, brief, asset)" />
          </label>
          <div className="row">
            <label>
              Reference
              <select value={form.reference_type || ''} onChange={(e) => set('reference_type', e.target.value)}>
                <option value="">None</option>
                <option value="contract">Contract</option>
                <option value="campaign">Campaign</option>
                <option value="post">Post</option>
                <option value="creator">Creator</option>
                <option value="policy">Policy document</option>
              </select>
            </label>
            <label>
              Reference id
              <input
                list="reference-options"
                disabled={!form.reference_type}
                value={form.reference_id || ''}
                onChange={(e) => set('reference_id', e.target.value)}
                placeholder={REFERENCE_HINT[form.reference_type || ''] || ''}
              />
              <datalist id="reference-options">
                {(suggestions[form.reference_type || ''] || []).map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </datalist>
            </label>
          </div>
          {error && <div className="notice error">{error}</div>}
        </div>

        <div className="modal-foot">
          <button type="button" className="btn ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="btn primary" disabled={saving}>
            {saving ? 'Creating...' : isPost ? 'Create and send for approval' : 'Create ticket'}
          </button>
        </div>
      </form>
    </div>
  )
}
