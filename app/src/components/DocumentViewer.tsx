import { useEffect, useRef, useState } from 'react'
import { api, type DocSource, type DocumentText } from '../api'
import { DocText } from '../markdown'
import { CloseIcon, ExternalIcon } from './Icons'

// Full text of the cited document version, with the cited passage highlighted.
// The other stored versions can be opened too (no highlight there).
export default function DocumentViewer({ source, onClose }: { source: DocSource; onClose: () => void }) {
  const [version, setVersion] = useState<number | null>(source.version)
  const [doc, setDoc] = useState<DocumentText | null>(null)
  const [error, setError] = useState('')
  const markRef = useRef<HTMLElement>(null)

  useEffect(() => {
    api
      .document(source.doc_id, version)
      .then(setDoc)
      .catch((e) => setError(e.message))
  }, [source, version])

  useEffect(() => {
    markRef.current?.scrollIntoView({ block: 'center' })
  }, [doc])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  let body: React.ReactNode = null
  if (doc) {
    const start = source.char_start ?? -1
    const end = source.char_end ?? -1
    const sameVersion = doc.version === source.version
    if (sameVersion && start >= 0 && end > start && end <= doc.text.length) {
      body = (
        <>
          <DocText text={doc.text.slice(0, start)} />
          <mark ref={markRef}>
            <DocText text={doc.text.slice(start, end)} />
          </mark>
          <DocText text={doc.text.slice(end)} />
        </>
      )
    } else {
      body = <DocText text={doc.text} />
    }
  }

  return (
    <div className="overlay" onClick={onClose}>
      <div className="viewer" onClick={(e) => e.stopPropagation()}>
        <div className="viewer-head">
          <div>
            <h3>{source.title}</h3>
            <div className="source-meta">
              {doc?.synthetic && <span>synthetic document</span>}
              {source.source_url && (
                <a href={source.source_url} target="_blank" rel="noreferrer">
                  original page <ExternalIcon size={12} />
                </a>
              )}
            </div>
          </div>
          <button className="icon-button" onClick={onClose} title="Close (Esc)">
            <CloseIcon />
          </button>
        </div>

        {doc && doc.versions.length > 1 && (
          <div className="versions">
            <span className="muted">Stored versions:</span>
            {doc.versions.map((v) => (
              <button key={v.version} className={'pill' + (v.version === doc.version ? ' on' : '')} onClick={() => setVersion(v.version)}>
                v{v.version} · {v.snapshot_date}
                {v.is_latest && ' (latest)'}
                {v.version === source.version && ' · cited'}
              </button>
            ))}
          </div>
        )}

        {error && <div className="notice error">{error}</div>}
        {(!doc || (version !== null && doc.version !== version)) && !error && <div className="empty">Loading the document...</div>}
        {doc && (version === null || doc.version === version) && <pre className="doc-text">{body}</pre>}
      </div>
    </div>
  )
}
