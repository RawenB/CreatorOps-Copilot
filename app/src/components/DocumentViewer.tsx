import { useEffect, useRef, useState } from 'react'
import { api, type DocSource, type DocumentText } from '../api'

// Full text of the cited document version, with the cited passage highlighted.
export default function DocumentViewer({ source, onClose }: { source: DocSource; onClose: () => void }) {
  const [doc, setDoc] = useState<DocumentText | null>(null)
  const [error, setError] = useState('')
  const markRef = useRef<HTMLElement>(null)

  useEffect(() => {
    api
      .document(source.doc_id, source.version)
      .then(setDoc)
      .catch((e) => setError(e.message))
  }, [source])

  useEffect(() => {
    markRef.current?.scrollIntoView({ block: 'center' })
  }, [doc])

  let body = null
  if (doc) {
    const start = source.char_start ?? -1
    const end = source.char_end ?? -1
    if (start >= 0 && end > start && end <= doc.text.length) {
      body = (
        <>
          {doc.text.slice(0, start)}
          <mark ref={markRef}>{doc.text.slice(start, end)}</mark>
          {doc.text.slice(end)}
        </>
      )
    } else {
      body = doc.text
    }
  }

  return (
    <div className="overlay" onClick={onClose}>
      <div className="viewer" onClick={(e) => e.stopPropagation()}>
        <div className="viewer-head">
          <div>
            <b>{source.title}</b>
            <div className="meta">
              version {source.version} · snapshot {source.snapshot_date}
              {doc && doc.versions.length > 1 && ` · ${doc.versions.length} versions stored`}
              {source.synthetic && ' · synthetic document'}
            </div>
            {source.source_url && (
              <a href={source.source_url} target="_blank" rel="noreferrer">
                original source
              </a>
            )}
          </div>
          <button onClick={onClose}>Close</button>
        </div>
        {error && <div className="error">{error}</div>}
        {!doc && !error && <div className="meta">Loading...</div>}
        <pre className="doc-text">{body}</pre>
      </div>
    </div>
  )
}
