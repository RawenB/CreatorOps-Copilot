import type { Approval } from '../api'
import { formatDateTime, initials, platformClass } from '../format'

export default function ApprovalCard({ approval, onDecide, busy }: {
  approval: Approval
  onDecide?: (approved: boolean) => void
  busy?: boolean
}) {
  const name = approval.creator_name || `Creator #${approval.creator_id}`
  const status = approval.decision || 'pending'

  return (
    <div className={`approval-card status-${status}`}>
      <div className="approval-head">
        <div className={`creator-avatar ${platformClass(approval.platform)}`}>{initials(name)}</div>
        <div className="approval-who">
          <div className="approval-name">{name}</div>
          <div className="muted small-text">
            Schedule a post · request #{approval.approval_id}
          </div>
        </div>
        <span className={`status-pill ${status}`}>{status}</span>
      </div>

      <div className="approval-details">
        <span className={`platform-badge ${platformClass(approval.platform)}`}>{approval.platform}</span>
        <span>{formatDateTime(approval.post_datetime)}</span>
      </div>
      {approval.caption && <blockquote className="caption">{approval.caption}</blockquote>}

      <div className="approval-foot">
        <span className="muted small-text">
          {approval.requested_at ? `requested ${formatDateTime(approval.requested_at)}` : approval.decision ? '' : 'waiting for a decision'}
          {approval.decided_by && ` · ${status} by ${approval.decided_by.replace('_', ' ')}`}
        </span>
        {onDecide && !approval.decision && (
          <div className="buttons">
            <button className="btn danger-outline" disabled={busy} onClick={() => onDecide(false)}>
              Reject
            </button>
            <button className="btn primary" disabled={busy} onClick={() => onDecide(true)}>
              Approve
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
