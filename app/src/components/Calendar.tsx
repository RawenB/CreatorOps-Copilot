import { useEffect, useState } from 'react'
import { api, type ScheduledPost } from '../api'

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function monthKey(date: string) {
  return date.slice(0, 7) // "YYYY-MM"
}

// Month view of the scheduled posts.
export default function Calendar({ refresh }: { refresh: number }) {
  const [posts, setPosts] = useState<ScheduledPost[]>([])
  const [month, setMonth] = useState('')

  useEffect(() => {
    api.schedule().then((p) => {
      setPosts(p)
      if (p.length > 0) setMonth((m) => m || monthKey(p[0].scheduled_at))
    })
  }, [refresh])

  const months = [...new Set(posts.map((p) => monthKey(p.scheduled_at)))]
  if (!month) return <div className="meta">No scheduled posts.</div>

  const [year, m] = month.split('-').map(Number)
  const first = new Date(year, m - 1, 1)
  const daysInMonth = new Date(year, m, 0).getDate()
  const offset = (first.getDay() + 6) % 7 // monday first
  const cells: (number | null)[] = [...Array(offset).fill(null)]
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)

  return (
    <div>
      <div className="filters">
        {months.map((key) => (
          <button key={key} className={key === month ? 'on' : ''} onClick={() => setMonth(key)}>
            {key}
          </button>
        ))}
      </div>
      <div className="calendar">
        {DAYS.map((d) => (
          <div key={d} className="day-name">
            {d}
          </div>
        ))}
        {cells.map((day, i) => {
          const date = day ? `${month}-${String(day).padStart(2, '0')}` : ''
          const today = posts.filter((p) => day && p.scheduled_at.startsWith(date))
          return (
            <div key={i} className={'day' + (day ? '' : ' empty')}>
              {day && <div className="day-number">{day}</div>}
              {today.map((p) => (
                <div key={p.schedule_id} className={'post ' + p.platform.toLowerCase()} title={p.caption}>
                  {p.scheduled_at.slice(11, 16)} {p.creator} · {p.platform}
                </div>
              ))}
            </div>
          )
        })}
      </div>
    </div>
  )
}
