import type { DocSource } from './api'

// Small display helpers.

export function formatDateTime(value?: string | null): string {
  if (!value) return ''
  const date = new Date(value.replace(' ', 'T'))
  if (isNaN(date.getTime())) return value
  return date.toLocaleString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function initials(name?: string): string {
  if (!name) return '?'
  const parts = name.split(' ')
  return parts.length > 1 ? parts[parts.length - 1].slice(0, 1).toUpperCase() : name.slice(0, 2).toUpperCase()
}

export function platformClass(platform?: string): string {
  return (platform || '').toLowerCase()
}

// For short previews: remove markdown symbols (### , **, > ...)
export function plainText(text: string): string {
  return text
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\*\*|__/g, '')
    .replace(/^>\s?/gm, '')
    .replace(/\s+/g, ' ')
    .trim()
}

// "A > B > ### What if a talk show ..." -> "What if a talk show ..."
export function lastSection(path: string | null): string {
  if (!path) return ''
  return plainText(path.split(' > ').pop() || '')
}

// A minimal "source" so a referenced contract / policy can be opened in the document viewer.
export function docRef(docId: string, title: string): DocSource {
  return {
    kind: 'document', n: 0, doc_id: docId, title, doc_type: '', platform: null, section: null,
    snapshot_date: null, version: null, is_latest: true, source_url: null, synthetic: false,
    clause_type: null, char_start: null, char_end: null, score: 0, text: '',
  }
}

export function ticketLink(id: number): string {
  return `${window.location.origin}/#/tickets/${id}`
}

// 1,234 / 12K / 3.4M
export function compact(n: number): string {
  if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(1).replace('.0', '') + 'M'
  if (Math.abs(n) >= 10_000) return Math.round(n / 1000) + 'K'
  return n.toLocaleString('en-US')
}
