import { useEffect, useState } from 'react'
import { api, type Approval } from '../api'
import { useToast } from '../toast'
import ApprovalCard from './ApprovalCard'

const FILTERS = ['pending', 'approved', 'rejected', 'all']

// Queue of write actions waiting for a human (from the chat agent or from MCP clients).
export default function Approvals({ refresh, onChange, onOpenTicket }: {
  refresh: number
  onChange: () => void
  onOpenTicket: (id: number) => void
}) {
  const [status, setStatus] = useState('pending')
  const [items, setItems] = useState<Approval[] | null>(null)
  const [busy, setBusy] = useState(false)
  const toast = useToast()

  useEffect(() => {
    api.approvals(status).then(setItems).catch((e) => toast(e.message, 'error'))
  }, [status, refresh, toast])

  async function decide(id: number, approved: boolean) {
    setBusy(true)
    try {
      await api.decide(id, approved)
      toast(approved ? `Request #${id} approved, the post is scheduled` : `Request #${id} rejected`)
      onChange()
    } catch (e) {
      toast((e as Error).message, 'error')
    }
    setBusy(false)
  }

  return (
    <div className="content">
      <div className="toolbar">
        <div className="segmented">
          {FILTERS.map((s) => (
            <button key={s} className={s === status ? 'on' : ''} onClick={() => setStatus(s)}>
              {s}
            </button>
          ))}
        </div>
        <span className="muted">
          The assistant and MCP clients can only ask. Nothing is scheduled until someone approves here.
        </span>
      </div>

      {items === null && <div className="empty">Loading...</div>}
      {items?.length === 0 && (
        <div className="empty">{status === 'pending' ? 'Nothing waiting for approval.' : 'No requests here.'}</div>
      )}
      <div className="card-grid">
        {items?.map((a) => (
          <ApprovalCard
            key={a.approval_id}
            approval={a}
            busy={busy}
            onDecide={(ok) => decide(a.approval_id, ok)}
            onOpenTicket={onOpenTicket}
          />
        ))}
      </div>
    </div>
  )
}
