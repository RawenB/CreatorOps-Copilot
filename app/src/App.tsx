import { useEffect, useState } from 'react'
import { api } from './api'
import Approvals from './components/Approvals'
import Calendar from './components/Calendar'
import Chat from './components/Chat'
import SqlPanel from './components/SqlPanel'

const TABS = ['Chat', 'Approvals', 'Calendar', 'SQL'] as const
type Tab = (typeof TABS)[number]

export default function App() {
  const [tab, setTab] = useState<Tab>('Chat')
  const [model, setModel] = useState('')
  const [pending, setPending] = useState(0)
  const [refresh, setRefresh] = useState(0) // bumped when an approval changes

  useEffect(() => {
    api
      .health()
      .then((h) => setModel(`${h.llm} · ${h.model}`))
      .catch(() => setModel('backend not running (make api)'))
  }, [])

  useEffect(() => {
    api
      .approvals('pending')
      .then((a) => setPending(a.length))
      .catch(() => setPending(0))
  }, [refresh])

  return (
    <div className="app">
      <header>
        <h1>CreatorOps Copilot</h1>
        <nav>
          {TABS.map((t) => (
            <button key={t} className={t === tab ? 'on' : ''} onClick={() => setTab(t)}>
              {t}
              {t === 'Approvals' && pending > 0 && <span className="count">{pending}</span>}
            </button>
          ))}
        </nav>
        <span className="meta">{model}</span>
      </header>
      <main>
        {/* Chat stays mounted so the conversation is kept when switching tabs */}
        <div style={{ display: tab === 'Chat' ? 'block' : 'none' }}>
          <Chat onApprovalChange={() => setRefresh((r) => r + 1)} />
        </div>
        {tab === 'Approvals' && <Approvals refresh={refresh} onChange={() => setRefresh((r) => r + 1)} />}
        {tab === 'Calendar' && <Calendar refresh={refresh} />}
        {tab === 'SQL' && <SqlPanel />}
      </main>
    </div>
  )
}
