import { useEffect, useState } from 'react'
import LogViewer from '../components/LogViewer'
import { LogAPI } from '../services/api'

export default function Logs() {
  const [logs, setLogs] = useState([])
  const [category, setCategory] = useState('')

  const load = () => {
    LogAPI.list(category ? { category } : {}).then((r) => setLogs(r.data))
  }
  useEffect(load, [category])

  return (
    <div className="grid" style={{ gap: 16 }}>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h2 style={{ margin: 0 }}>Logs</h2>
        <div className="row">
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">All categories</option>
            <option value="config">Configuration</option>
            <option value="deploy">Deployment</option>
            <option value="error">Error</option>
            <option value="auth">Auth</option>
            <option value="system">System</option>
          </select>
          <button onClick={load}>Refresh</button>
        </div>
      </div>
      <div className="card"><LogViewer logs={logs} /></div>
    </div>
  )
}
