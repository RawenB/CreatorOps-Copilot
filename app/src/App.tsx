import { useEffect, useState } from 'react'
import { api } from './api'
import Approvals from './components/Approvals'
import Calendar from './components/Calendar'
import Chat from './components/Chat'
import { CalendarIcon, ChatIcon, CheckIcon, DatabaseIcon } from './components/Icons'
import SqlPanel from './components/SqlPanel'
import { ToastProvider } from './toast'

const TABS = [
  { name: 'Chat', icon: ChatIcon, title: 'Assistant', subtitle: 'Policies, contracts and analytics, with sources' },
  { name: 'Approvals', icon: CheckIcon, title: 'Approvals', subtitle: 'Actions waiting for a human decision' },
  { name: 'Calendar', icon: CalendarIcon, title: 'Content calendar', subtitle: 'Scheduled posts' },
  { name: 'SQL', icon: DatabaseIcon, title: 'SQL console', subtitle: 'Read-only queries on the analytics database' },
] as const
type Tab = (typeof TABS)[number]['name']

export default function App() {
  const [tab, setTab] = useState<Tab>('Chat')
  const [model, setModel] = useState<string | null>(null)
  const [online, setOnline] = useState(true)
  const [pending, setPending] = useState(0)
  const [refresh, setRefresh] = useState(0) // bumped when an approval changes

  useEffect(() => {
    api
      .health()
      .then((h) => {
        setModel(h.model)
        setOnline(true)
      })
      .catch(() => setOnline(false))
  }, [])

  useEffect(() => {
    api
      .approvals('pending')
      .then((a) => setPending(a.length))
      .catch(() => setPending(0))
  }, [refresh])

  const current = TABS.find((t) => t.name === tab)!
  const bump = () => setRefresh((r) => r + 1)

  return (
    <ToastProvider>
      <div className="app">
        <aside className="sidebar">
          <div className="brand">
            <div className="logo">CO</div>
            <div>
              <div className="brand-name">CreatorOps</div>
              <div className="brand-sub">Copilot</div>
            </div>
          </div>
          <nav>
            {TABS.map(({ name, icon: Icon }) => (
              <button key={name} className={name === tab ? 'active' : ''} onClick={() => setTab(name)}>
                <Icon />
                <span>{name}</span>
                {name === 'Approvals' && pending > 0 && <span className="count">{pending}</span>}
              </button>
            ))}
          </nav>
          <div className="status">
            <span className={'dot ' + (online ? 'on' : 'off')} />
            {online ? (model ? `${model} · local` : 'connecting...') : 'backend offline (make api)'}
          </div>
        </aside>

        <main>
          <header className="page-header">
            <h1>{current.title}</h1>
            <p>{current.subtitle}</p>
          </header>
          <div className="page">
            {/* Chat stays mounted so the conversation is kept when switching tabs */}
            <div className="page-fill" style={{ display: tab === 'Chat' ? 'flex' : 'none' }}>
              <Chat onApprovalChange={bump} />
            </div>
            {tab === 'Approvals' && <Approvals refresh={refresh} onChange={bump} />}
            {tab === 'Calendar' && <Calendar refresh={refresh} />}
            {tab === 'SQL' && <SqlPanel />}
          </div>
        </main>
      </div>
    </ToastProvider>
  )
}
