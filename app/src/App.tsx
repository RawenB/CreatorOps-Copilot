import { useEffect, useState } from 'react'
import { api } from './api'
import Analytics from './components/Analytics'
import Approvals from './components/Approvals'
import Calendar from './components/Calendar'
import Chat from './components/Chat'
import { CalendarIcon, ChartIcon, ChatIcon, CheckIcon, DatabaseIcon, TicketIcon } from './components/Icons'
import SqlPanel from './components/SqlPanel'
import Tickets from './components/Tickets'
import { ToastProvider } from './toast'

const TABS = [
  { name: 'Chat', path: 'chat', icon: ChatIcon, title: 'Assistant', subtitle: 'Policies, contracts and analytics, with sources' },
  { name: 'Tickets', path: 'tickets', icon: TicketIcon, title: 'Tickets', subtitle: 'Tasks and post requests, with links and references' },
  { name: 'Approvals', path: 'approvals', icon: CheckIcon, title: 'Approvals', subtitle: 'Actions waiting for a human decision' },
  { name: 'Analytics', path: 'analytics', icon: ChartIcon, title: 'Analytics', subtitle: 'Creator performance (synthetic data)' },
  { name: 'Calendar', path: 'calendar', icon: CalendarIcon, title: 'Content calendar', subtitle: 'Scheduled posts' },
  { name: 'SQL', path: 'sql', icon: DatabaseIcon, title: 'SQL console', subtitle: 'Read-only queries on the analytics database' },
] as const
type Tab = (typeof TABS)[number]['name']

// URLs like #/tickets/12 open a ticket directly (so a ticket link can be shared)
function readHash(): { tab: Tab; ticket: number | null } {
  const [, path, id] = window.location.hash.split('/')
  const tab = TABS.find((t) => t.path === path)?.name || 'Chat'
  return { tab, ticket: tab === 'Tickets' && id ? Number(id) : null }
}

export default function App() {
  const [{ tab, ticket }, setRoute] = useState(readHash)
  const [model, setModel] = useState<string | null>(null)
  const [online, setOnline] = useState(true)
  const [pending, setPending] = useState(0)
  const [openTickets, setOpenTickets] = useState(0)
  const [refresh, setRefresh] = useState(0) // bumped when an approval or a ticket changes

  useEffect(() => {
    const onHash = () => setRoute(readHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

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
    api.approvals('pending').then((a) => setPending(a.length)).catch(() => setPending(0))
    api.tickets('task', 'open').then((t) => setOpenTickets(t.length)).catch(() => setOpenTickets(0))
  }, [refresh])

  const go = (name: Tab, ticketId: number | null = null) => {
    const path = TABS.find((t) => t.name === name)!.path
    window.location.hash = `/${path}` + (ticketId ? `/${ticketId}` : '')
  }
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
              <button key={name} className={name === tab ? 'active' : ''} onClick={() => go(name)}>
                <Icon />
                <span>{name}</span>
                {name === 'Approvals' && pending > 0 && <span className="count">{pending}</span>}
                {name === 'Tickets' && openTickets > 0 && <span className="count neutral">{openTickets}</span>}
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
            {/* Chat stays mounted so the conversation is kept when switching pages */}
            <div className="page-fill" style={{ display: tab === 'Chat' ? 'flex' : 'none' }}>
              <Chat onApprovalChange={bump} onOpenTicket={(id) => go('Tickets', id)} />
            </div>
            {tab === 'Tickets' && (
              <Tickets openId={ticket} refresh={refresh} onChange={bump} onOpen={(id) => go('Tickets', id)} />
            )}
            {tab === 'Approvals' && <Approvals refresh={refresh} onChange={bump} onOpenTicket={(id) => go('Tickets', id)} />}
            {tab === 'Analytics' && (
              <Analytics
                onTicketCreated={(t) => {
                  bump()
                  go('Tickets', t.ticket_id)
                }}
              />
            )}
            {tab === 'Calendar' && <Calendar refresh={refresh} />}
            {tab === 'SQL' && <SqlPanel />}
          </div>
        </main>
      </div>
    </ToastProvider>
  )
}
