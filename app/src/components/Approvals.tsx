import { useEffect, useState } from 'react'
import { api, type Approval } from '../api'
import ApprovalCard from './ApprovalCard'

// Queue of write actions waiting for a human (from the chat agent or from MCP clients).
export default function Approvals({ refresh, onChange }: { refresh: number; onChange: () => void }) {
  const [status, setStatus] = useState('pending')
  const [items, setItems] = useState<Approval[]>([])
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.approvals(status).then(setItems)
  }, [status, refresh])

  async function decide(id: number, approved: boolean) {
    setBusy(true)
    try {
      await api.decide(id, approved)
      onChange()
    } catch (e) {
      alert((e as Error).message)
    }
    setBusy(false)
  }

  return (
    <div className="approvals">
      <div className="filters">
        {['pending', 'approved', 'rejected', 'all'].map((s) => (
          <button key={s} className={s === status ? 'on' : ''} onClick={() => setStatus(s)}>
            {s}
          </button>
        ))}
      </div>
      {items.length === 0 && <div className="meta">Nothing here.</div>}
      <div className="grid">
        {items.map((a) => (
          <ApprovalCard key={a.approval_id} approval={a} busy={busy} onDecide={(ok) => decide(a.approval_id, ok)} />
        ))}
      </div>
    </div>
  )
}
