import { useEffect, useState } from 'react'
import { api, type ScheduledPost } from '../api'
import { platformClass } from '../format'
import { ChevronIcon } from './Icons'

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const pad = (n: number) => String(n).padStart(2, '0')

// Month view of the scheduled posts.
export default function Calendar({ refresh }: { refresh: number }) {
  const [today] = useState(() => new Date()) // computed once
  const [posts, setPosts] = useState<ScheduledPost[]>([])
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth()) // 0-11

  useEffect(() => {
    api.schedule().then(setPosts)
  }, [refresh])

  function move(step: number) {
    const d = new Date(year, month + step, 1)
    setYear(d.getFullYear())
    setMonth(d.getMonth())
  }

  const key = `${year}-${pad(month + 1)}`
  const offset = (new Date(year, month, 1).getDay() + 6) % 7 // monday first
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const cells: (number | null)[] = Array(offset).fill(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)
  while (cells.length % 7) cells.push(null)

  const inMonth = posts.filter((p) => p.scheduled_at.startsWith(key))
  const upcoming = posts.filter((p) => new Date(p.scheduled_at.replace(' ', 'T')) >= today).slice(0, 5)
  const title = new Date(year, month, 1).toLocaleString('en-GB', { month: 'long', year: 'numeric' })

  return (
    <div className="content calendar-page">
      <div className="toolbar">
        <div className="month-nav">
          <button className="icon-button" onClick={() => move(-1)} title="Previous month">
            <ChevronIcon dir="left" />
          </button>
          <h2>{title}</h2>
          <button className="icon-button" onClick={() => move(1)} title="Next month">
            <ChevronIcon />
          </button>
          <button
            className="btn ghost"
            onClick={() => {
              setYear(today.getFullYear())
              setMonth(today.getMonth())
            }}
          >
            Today
          </button>
        </div>
        <div className="legend">
          <span className="platform-badge instagram">Instagram</span>
          <span className="platform-badge tiktok">TikTok</span>
          <span className="platform-badge youtube">YouTube</span>
          <span className="muted">{inMonth.length} posts this month</span>
        </div>
      </div>

      <div className="calendar">
        {DAYS.map((d) => (
          <div key={d} className="day-name">
            {d}
          </div>
        ))}
        {cells.map((day, i) => {
          const date = day ? `${key}-${pad(day)}` : ''
          const dayPosts = day ? posts.filter((p) => p.scheduled_at.startsWith(date)) : []
          const isToday =
            day === today.getDate() && month === today.getMonth() && year === today.getFullYear()
          return (
            <div key={i} className={'day' + (day ? '' : ' empty') + (isToday ? ' today' : '')}>
              {day && <div className="day-number">{day}</div>}
              {dayPosts.map((p) => (
                <div key={p.schedule_id} className={`event ${platformClass(p.platform)}`} title={p.caption}>
                  <b>{p.scheduled_at.slice(11, 16)}</b> {p.creator}
                </div>
              ))}
            </div>
          )
        })}
      </div>

      {upcoming.length > 0 && (
        <div className="upcoming">
          <h3>Next posts</h3>
          {upcoming.map((p) => (
            <div key={p.schedule_id} className="upcoming-row">
              <span className={`platform-badge ${platformClass(p.platform)}`}>{p.platform}</span>
              <span>{p.scheduled_at.slice(0, 16)}</span>
              <b>{p.creator}</b>
              <span className="muted">{p.caption}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
