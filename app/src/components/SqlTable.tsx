export default function SqlTable({ columns, rows }: { columns: string[]; rows: unknown[][] }) {
  if (rows.length === 0) return <div className="empty small">0 rows: the query matched nothing.</div>
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j} className={typeof cell === 'number' ? 'num' : ''}>
                  {cell === null ? <span className="muted">NULL</span> : typeof cell === 'number' ? cell.toLocaleString('en-US', { maximumFractionDigits: 4 }) : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
