// Small wrapper around the FastAPI backend + the types it returns.

export type DocSource = {
  kind: 'document'
  n: number
  doc_id: string
  title: string
  doc_type: string
  platform: string | null
  section: string | null
  snapshot_date: string | null
  version: number | null
  is_latest: boolean | null
  source_url: string | null
  synthetic: boolean
  clause_type: string | null
  char_start: number | null
  char_end: number | null
  score: number
  text: string
}

export type SqlSource = {
  kind: 'sql'
  n: number
  query: string
  columns: string[]
  rows: unknown[][]
  truncated: boolean
}

export type Change = {
  section: string
  change: 'added' | 'removed' | 'modified'
  new_text?: string
  old_text?: string
  diff?: string[]
}

export type ComparisonSource = {
  kind: 'comparison'
  n: number
  doc_id: string
  title: string
  old_version: { version: number; snapshot_date: string }
  new_version: { version: number; snapshot_date: string }
  n_changes: number
  changes: Change[]
}

export type ComplianceSource = {
  kind: 'compliance'
  n: number
  verdict: 'compliant' | 'non_compliant'
  problems: { rule: string; message: string }[]
}

export type ClassificationSource = {
  kind: 'classification'
  n: number
  label: string
  scores: Record<string, number>
}

export type Ticket = {
  ticket_id: number
  code: string
  kind: 'task' | 'post_request'
  title: string
  description: string | null
  status: string
  priority: 'low' | 'medium' | 'high'
  assignee: string | null
  link: string | null
  reference_type: string | null
  reference_id: string | null
  reference_label: string | null
  reference_doc_id?: string | null
  approval_id: number | null
  decided_by?: string | null
  created_by: string
  created_at: string
  updated_at: string
}

export type TicketSource = Ticket & { kind: 'task'; n: number } // a ticket the assistant created

export type Source =
  | DocSource
  | SqlSource
  | ComparisonSource
  | ComplianceSource
  | ClassificationSource
  | (Omit<TicketSource, 'kind'> & { kind: 'ticket' })

export type NewTicket = {
  kind: 'task' | 'post_request'
  title?: string
  description?: string
  priority?: string
  assignee?: string
  link?: string
  reference_type?: string
  reference_id?: string
  creator?: string
  platform?: string
  post_datetime?: string
  caption?: string
}

export type Anomaly = {
  kind: string
  severity: 'high' | 'medium' | 'info'
  creator: string
  date: string
  text: string
  ticket: { title: string; priority: string; reference_type: string; reference_id: string; description: string }
}

export type AnalyticsData = {
  platform: string | null
  source: { type: string; generator: string; seed: number; note: string }
  kpis: {
    creators: number
    posts: number
    reach: number
    impressions: number
    engagement_rate: number
    first_post: string
    last_post: string
    paid_posts: number
    undisclosed_paid: number
  }
  monthly: { month: string; posts: number; reach: number; engagement_rate: number }[]
  creators: {
    creator_id: number
    name: string
    niche: string
    country: string
    posts: number
    reach: number
    engagement_rate: number
    followers: Record<string, number>
  }[]
  formats: { format: string; posts: number; avg_reach: number; engagement_rate: number }[]
  anomalies: Anomaly[]
}

export type Approval = {
  approval_id: number
  action: string
  requested_at: string
  decision: string | null
  decided_at: string | null
  decided_by: string | null
  creator_id?: number
  creator_name?: string
  platform?: string
  post_datetime?: string
  caption?: string
  link?: string | null
  reference?: string | null
  ticket?: string
  ticket_id?: number
}

export type ChatResult = {
  thread_id: string
  status: 'done' | 'waiting_approval'
  question: string
  route: string
  answer: string | null
  pending_approval: Approval | null
  approval: Approval | null
  citations: number[]
  invalid_citations: number[]
  abstained: boolean
  unverified: boolean
  sources: Source[]
  tool_calls: { name: string; arguments: Record<string, unknown> }[]
  usage: Record<string, number>
  latency_s: number
}

export type SqlResult = {
  query?: string
  columns?: string[]
  rows?: unknown[][]
  row_count?: number
  truncated?: boolean
  error?: string
}

export type ScheduledPost = {
  schedule_id: number
  scheduled_at: string
  caption: string
  status: string
  creator: string
  platform: string
}

export type DocumentText = {
  doc_id: string
  title: string
  version: number
  versions: { version: number; snapshot_date: string; is_latest: boolean }[]
  source_url: string | null
  synthetic: boolean
  text: string
}

async function request<T>(path: string, body?: unknown, method?: string): Promise<T> {
  const response = await fetch('/api' + path, {
    method: method ?? (body === undefined ? 'GET' : 'POST'),
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || `Error ${response.status}`)
  }
  return response.json()
}

export const api = {
  health: () => request<{ status: string; llm: string; model: string }>('/health'),
  chat: (question: string, thread_id?: string) =>
    request<ChatResult>('/chat', { question, thread_id }),
  approvals: (status = 'pending') => request<Approval[]>(`/approvals?status=${status}`),
  decide: (id: number, approved: boolean) =>
    request<ChatResult | { status: string; approval: Approval }>(`/approvals/${id}/decision`, {
      approved,
      decided_by: 'account_manager',
    }),
  schedule: () => request<ScheduledPost[]>('/schedule'),
  sql: (query: string) => request<SqlResult>('/sql', { query }),
  schema: () =>
    request<{ tables: Record<string, { description: string; columns: Record<string, string> }> }>(
      '/schema',
    ),
  tickets: (kind = '', status = '') => {
    const params = new URLSearchParams()
    if (kind) params.set('kind', kind)
    if (status) params.set('status', status)
    return request<Ticket[]>('/tickets?' + params)
  },
  ticket: (id: number) => request<Ticket>(`/tickets/${id}`),
  createTicket: (ticket: NewTicket) => request<Ticket>('/tickets', ticket),
  updateTicket: (id: number, change: { status?: string; priority?: string; assignee?: string }) =>
    request<Ticket>(`/tickets/${id}`, change, 'PATCH'),
  analytics: (platform = '') => request<AnalyticsData>('/analytics' + (platform ? `?platform=${platform}` : '')),
  creators: () => request<[number, string, string, string][]>('/creators'),
  document: (docId: string, version?: number | null) =>
    request<DocumentText>(`/documents/${docId}` + (version ? `?version=${version}` : '')),
}
