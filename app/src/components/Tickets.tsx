import { useEffect, useState } from 'react'
import { api, type DocSource, type Ticket } from '../api'
import { docRef, formatDateTime, ticketLink } from '../format'
import { useToast } from '../toast'
import DocumentViewer from './DocumentViewer'
import { CloseIcon, DocIcon, ExternalIcon } from './Icons'
import TicketForm from './TicketForm'

const STATUS_LABEL: Record<string, string> = {
  open: 'Open',
  in_progress: 'In progress',
  done: 'Done',
  pending: 'Waiting approval',
  approved: 'Approved',
  rejected: 'Rejected',
}

export function StatusPill({ status }: { status: string }) {
  return <span className={`status-pill ${status}`}>{STATUS_LABEL[status] || status}</span>
}

export default function Tickets({ openId, refresh, onChange, onOpen }: {
  openId: number | null
  refresh: number
  onChange: () => void
  onOpen: (id: number | null) => void
}) {
  const [kind, setKind] = useState('')
  const [status, setStatus] = useState('')
  const [items, setItems] = useState<Ticket[] | null>(null)
  const [creating, setCreating] = useState(false)
  const toast = useToast()

  useEffect(() => {
    api.tickets(kind, status).then(setItems).catch((e) => toast(e.message, 'error'))
  }, [kind, status, refresh, toast])

  const open = items?.find((t) => t.ticket_id === openId) || null

  return (
    <div className="content">
      <div className="toolbar">
        <div className="toolbar-left">
          <div className="segmented">
            {[['', 'All'], ['task', 'Tasks'], ['post_request', 'Post requests']].map(([value, label]) => (
              <button key={value} className={kind === value ? 'on' : ''} onClick={() => setKind(value)}>
                {label}
              </button>
            ))}
          </div>
          <select className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Any status</option>
            {Object.entries(STATUS_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <button className="btn primary" onClick={() => setCreating(true)}>
          + New ticket
        </button>
      </div>

      {items === null && <div className="empty">Loading...</div>}
      {items?.length === 0 && (
        <div className="empty">
          No tickets yet. Create one here, from an anomaly on the Analytics page, or ask the assistant
          ("create a ticket to fix the disclosure of post 166").
        </div>
      )}

      <div className={'tickets-layout' + (open ? ' with-detail' : '')}>
      {items && items.length > 0 && (
        <div className="card no-pad">
          <table className="tickets-table">
            <thead>
              <tr>
                <th>Ticket</th>
                <th>Title</th>
                <th>Status</th>
                <th>Priority</th>
                <th>Reference</th>
                <th>From</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {items.map((t) => (
                <tr key={t.ticket_id} className={t.ticket_id === openId ? 'selected' : ''} onClick={() => onOpen(t.ticket_id)}>
                  <td className="mono">{t.code}</td>
                  <td>
                    <div className="ticket-title">
                      {t.title}
                      {t.link && <ExternalIcon size={12} />}
                    </div>
                    <span className="muted small-text">{t.kind === 'task' ? 'Task' : 'Post request'}</span>
                  </td>
                  <td>
                    <StatusPill status={t.status} />
                  </td>
                  <td>
                    <span className={`priority ${t.priority}`}>{t.priority}</span>
                  </td>
                  <td className="small-text">{t.reference_label || <span className="muted">-</span>}</td>
                  <td className="small-text muted">{t.created_by}</td>
                  <td className="small-text muted">{formatDateTime(t.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {open && <TicketDetail key={open.ticket_id} ticket={open} onClose={() => onOpen(null)} onChange={onChange} />}
      </div>
      {creating && (
        <TicketForm
          onClose={() => setCreating(false)}
          onCreated={(t) => {
            setCreating(false)
            onChange()
            onOpen(t.ticket_id)
          }}
        />
      )}
    </div>
  )
}

function TicketDetail({ ticket, onClose, onChange }: { ticket: Ticket; onClose: () => void; onChange: () => void }) {
  const [doc, setDoc] = useState<DocSource | null>(null)
  const [assignee, setAssignee] = useState(ticket.assignee || '')
  const toast = useToast()

  async function update(change: { status?: string; priority?: string; assignee?: string }) {
    try {
      await api.updateTicket(ticket.ticket_id, change)
      onChange()
    } catch (e) {
      toast((e as Error).message, 'error')
    }
  }

  return (
    <div className="drawer">
      <div className="drawer-head">
        <div>
          <span className="mono muted">{ticket.code}</span>
          <h3>{ticket.title}</h3>
        </div>
        <button className="icon-button" onClick={onClose}>
          <CloseIcon />
        </button>
      </div>

      <div className="drawer-body">
        <div className="share">
          <input readOnly value={ticketLink(ticket.ticket_id)} onFocus={(e) => e.target.select()} />
          <button
            className="btn ghost"
            onClick={() => navigator.clipboard.writeText(ticketLink(ticket.ticket_id)).then(() => toast('Link copied'))}
          >
            Copy link
          </button>
        </div>

        <dl className="fields">
          <dt>Status</dt>
          <dd>
            {ticket.kind === 'task' ? (
              <div className="segmented">
                {['open', 'in_progress', 'done'].map((s) => (
                  <button key={s} className={ticket.status === s ? 'on' : ''} onClick={() => update({ status: s })}>
                    {STATUS_LABEL[s]}
                  </button>
                ))}
              </div>
            ) : (
              <>
                <StatusPill status={ticket.status} />
                <div className="muted small-text">Follows approval #{ticket.approval_id} (Approvals page).</div>
              </>
            )}
          </dd>

          <dt>Priority</dt>
          <dd>
            <select className="select" value={ticket.priority} onChange={(e) => update({ priority: e.target.value })}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </dd>

          <dt>Assignee</dt>
          <dd>
            <input
              className="input"
              value={assignee}
              placeholder="nobody"
              onChange={(e) => setAssignee(e.target.value)}
              onBlur={() => assignee !== (ticket.assignee || '') && update({ assignee })}
            />
          </dd>

          <dt>Link</dt>
          <dd>
            {ticket.link ? (
              <a href={ticket.link} target="_blank" rel="noreferrer" className="break">
                {ticket.link} <ExternalIcon size={12} />
              </a>
            ) : (
              <span className="muted">-</span>
            )}
          </dd>

          <dt>Reference</dt>
          <dd>
            {ticket.reference_label ? (
              <div className="reference">
                <span className="tag tag-reference">{ticket.reference_type}</span> {ticket.reference_label}
                {ticket.reference_doc_id && (
                  <button className="link" onClick={() => setDoc(docRef(ticket.reference_doc_id!, ticket.reference_label!))}>
                    <DocIcon size={14} /> Open
                  </button>
                )}
              </div>
            ) : (
              <span className="muted">-</span>
            )}
          </dd>

          <dt>{ticket.kind === 'task' ? 'Description' : 'Caption'}</dt>
          <dd className="pre">{ticket.description || <span className="muted">-</span>}</dd>

          <dt>Created</dt>
          <dd className="muted">
            {formatDateTime(ticket.created_at)} by {ticket.created_by}
          </dd>
        </dl>
      </div>
      {doc && <DocumentViewer source={doc} onClose={() => setDoc(null)} />}
    </div>
  )
}
