import type { Approval } from '../api'

export default function ApprovalCard({
  approval,
  onDecide,
  busy,
}: {
  approval: Approval
  onDecide?: (approved: boolean) => void
  busy?: boolean
}) {
  return (
    <div className="approval-card">
      <div className="approval-title">
        #{approval.approval_id} · {approval.action}
        {approval.decision && <span className={'badge ' + approval.decision}>{approval.decision}</span>}
      </div>
      <div>
        <b>{approval.creator_name || `creator ${approval.creator_id}`}</b> on {approval.platform} at {approval.post_datetime}
      </div>
      {approval.caption && <div className="caption">"{approval.caption}"</div>}
      <div className="meta">requested {approval.requested_at}</div>
      {onDecide && !approval.decision && (
        <div className="buttons">
          <button className="ok" disabled={busy} onClick={() => onDecide(true)}>
            Approve
          </button>
          <button className="no" disabled={busy} onClick={() => onDecide(false)}>
            Reject
          </button>
        </div>
      )}
    </div>
  )
}
