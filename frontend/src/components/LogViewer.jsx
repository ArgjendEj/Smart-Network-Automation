// the server stores UTC without a zone suffix: mark it as UTC so the browser
// shows local time, as 23/11/2026 18:58
const formatTime = (ts) => new Date(/Z|[+-]\d\d:\d\d$/.test(ts) ? ts : `${ts}Z`)
  .toLocaleString('en-GB', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
  .replace(',', '')

const levelClass = { error: 'error', warning: '', info: 'muted' }

export default function LogViewer({ logs }) {
  if (!logs?.length) return <p className="muted">No log entries.</p>
  return (
    <table>
      <thead>
        <tr><th>Time</th><th>Level</th><th>Category</th><th>Message</th></tr>
      </thead>
      <tbody>
        {logs.map((l) => (
          <tr key={l.id}>
            <td className="muted" style={{ whiteSpace: 'nowrap' }}>
              {formatTime(l.timestamp)}
            </td>
            <td className={levelClass[l.level] || ''}>{l.level}</td>
            <td>{l.category}</td>
            <td>{l.message}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
