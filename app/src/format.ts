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
