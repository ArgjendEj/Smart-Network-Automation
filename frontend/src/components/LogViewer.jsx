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
              {new Date(l.timestamp).toLocaleString()}
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
