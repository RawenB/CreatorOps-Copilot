// A very small markdown renderer for the answers (the LLM uses **bold**, lists and short headings).
// Supports: headings (#), bullet / numbered lists, **bold**, *italic*, `code`, paragraphs.
// `renderText` is called on plain text parts, so the caller can turn [1] into citation buttons.

import type { ReactNode } from 'react'

type TextRenderer = (text: string, key: string) => ReactNode

function inline(text: string, renderText: TextRenderer, key: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g)
  return parts.map((part, i) => {
    const k = `${key}-${i}`
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={k}>{renderText(part.slice(2, -2), k)}</strong>
    if (part.startsWith('`') && part.endsWith('`')) return <code key={k}>{part.slice(1, -1)}</code>
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) return <em key={k}>{renderText(part.slice(1, -1), k)}</em>
    return <span key={k}>{renderText(part, k)}</span>
  })
}

export function Markdown({ text, renderText }: { text: string; renderText?: TextRenderer }) {
  const render = renderText || ((t: string) => t)
  const blocks: ReactNode[] = []
  let list: { ordered: boolean; items: string[] } | null = null
  let paragraph: string[] = []

  const flushParagraph = () => {
    if (paragraph.length) {
      const key = `p${blocks.length}`
      blocks.push(<p key={key}>{inline(paragraph.join(' '), render, key)}</p>)
      paragraph = []
    }
  }
  const flushList = () => {
    if (list) {
      const key = `l${blocks.length}`
      const items = list.items.map((item, i) => <li key={i}>{inline(item, render, `${key}-${i}`)}</li>)
      blocks.push(list.ordered ? <ol key={key}>{items}</ol> : <ul key={key}>{items}</ul>)
      list = null
    }
  }

  for (const raw of text.split('\n')) {
    const line = raw.trim()
    const bullet = line.match(/^[-*•]\s+(.*)/)
    const numbered = line.match(/^\d+[.)]\s+(.*)/)
    const heading = line.match(/^#{1,6}\s+(.*)/)
    if (!line) {
      flushParagraph()
      flushList()
    } else if (heading) {
      flushParagraph()
      flushList()
      const key = `h${blocks.length}`
      blocks.push(<h4 key={key}>{inline(heading[1], render, key)}</h4>)
    } else if (bullet || numbered) {
      flushParagraph()
      const ordered = Boolean(numbered)
      if (!list || list.ordered !== ordered) {
        flushList()
        list = { ordered, items: [] }
      }
      list.items.push((bullet || numbered)![1])
    } else if (list && raw.startsWith('  ')) {
      list.items[list.items.length - 1] += ' ' + line // continuation of a list item
    } else {
      flushList()
      paragraph.push(line)
    }
  }
  flushParagraph()
  flushList()
  return <div className="markdown">{blocks}</div>
}

// Document text for the viewer: headings in bold, ** removed. Works line by line, so it can be
// applied to the parts before / inside / after the highlighted passage (offsets stay exact).
export function DocText({ text }: { text: string }) {
  return (
    <>
      {text.split('\n').map((line, i, lines) => {
        const heading = line.match(/^\s*#{1,6}\s+(.*)/)
        const clean = (heading ? heading[1] : line).replace(/\*\*/g, '')
        const end = i < lines.length - 1 ? '\n' : ''
        return heading ? (
          <span key={i} className="doc-heading">{clean + end}</span>
        ) : (
          <span key={i}>{clean + end}</span>
        )
      })}
    </>
  )
}
