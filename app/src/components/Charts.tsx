// Two small SVG charts (no chart library): a line chart over months and horizontal bars.
// Specs: 2px line, 10% area wash, 8px markers with a 2px surface ring, hairline grid,
// one series = no legend (the title says what it is), hover tooltip on every point / bar.

import { useState } from 'react'

const COLOR = '#4f46e5' // validated: lightness band, chroma and >= 3:1 contrast on white

// round axis max to a clean number (1, 2, 2.5, 5 x 10^k)
function niceMax(value: number): number {
  if (value <= 0) return 1
  const power = 10 ** Math.floor(Math.log10(value))
  for (const step of [1, 2, 2.5, 5, 10]) if (step * power >= value) return step * power
  return 10 * power
}

export function LineChart({ points, format }: {
  points: { label: string; value: number }[]
  format: (v: number) => string
}) {
  const [hover, setHover] = useState<number | null>(null)
  const width = 640
  const height = 220
  const pad = { left: 52, right: 16, top: 14, bottom: 28 }
  const max = niceMax(Math.max(...points.map((p) => p.value)))
  const x = (i: number) => pad.left + (i * (width - pad.left - pad.right)) / Math.max(points.length - 1, 1)
  const y = (v: number) => pad.top + (1 - v / max) * (height - pad.top - pad.bottom)
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * max)
  const line = points.map((p, i) => `${i ? 'L' : 'M'}${x(i)},${y(p.value)}`).join(' ')
  const area = `${line} L${x(points.length - 1)},${y(0)} L${x(0)},${y(0)} Z`
  const last = points.length - 1

  return (
    <div className="chart" onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="line chart">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.left} x2={width - pad.right} y1={y(t)} y2={y(t)} className="grid" />
            <text x={pad.left - 8} y={y(t) + 4} className="axis" textAnchor="end">
              {format(t)}
            </text>
          </g>
        ))}
        {points.map((p, i) => (
          <text key={p.label} x={x(i)} y={height - 8} className="axis" textAnchor="middle">
            {p.label}
          </text>
        ))}
        <path d={area} fill={COLOR} opacity={0.1} />
        <path d={line} fill="none" stroke={COLOR} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={pad.top} y2={y(0)} className="crosshair" />}
        {points.map((p, i) => (
          <circle key={p.label} cx={x(i)} cy={y(p.value)} r={hover === i ? 5 : 4} fill={COLOR} stroke="#fff" strokeWidth={2} />
        ))}
        {/* direct label on the last point only */}
        <text x={x(last)} y={y(points[last].value) - 12} className="value-label" textAnchor="end">
          {format(points[last].value)}
        </text>
        {/* wide invisible hit areas for the hover */}
        {points.map((p, i) => (
          <rect
            key={p.label}
            x={x(i) - (width - pad.left - pad.right) / (2 * Math.max(last, 1))}
            y={0}
            width={(width - pad.left - pad.right) / Math.max(last, 1)}
            height={height}
            fill="transparent"
            onMouseEnter={() => setHover(i)}
          />
        ))}
      </svg>
      {hover !== null && (
        <div className="tooltip" style={{ left: `${(x(hover) / width) * 100}%`, top: `${(y(points[hover].value) / height) * 100}%` }}>
          <b>{points[hover].label}</b>
          <span>{format(points[hover].value)}</span>
        </div>
      )}
    </div>
  )
}

export function BarList({ items, format }: {
  items: { label: string; value: number; detail?: string }[]
  format: (v: number) => string
}) {
  const max = Math.max(...items.map((i) => i.value), 0) || 1
  return (
    <div className="bar-list">
      {items.map((item) => (
        <div key={item.label} className="bar-row" title={`${item.label}: ${format(item.value)}${item.detail ? ' · ' + item.detail : ''}`}>
          <span className="bar-label">{item.label}</span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${(item.value / max) * 100}%`, background: COLOR }} />
          </div>
          <span className="bar-value">{format(item.value)}</span>
        </div>
      ))}
    </div>
  )
}
