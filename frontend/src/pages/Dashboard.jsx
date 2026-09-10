import { useEffect, useState } from 'react'
import DashboardCards from '../components/DashboardCards'
import LogViewer from '../components/LogViewer'
import { DashboardAPI, DeviceAPI } from '../services/api'

const roleColor = { lan: 'var(--green)', link: 'var(--amber)', mgmt: 'var(--accent)', iface: 'var(--muted)' }

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [devices, setDevices] = useState([])
  const [err, setErr] = useState('')

  useEffect(() => {
    DashboardAPI.get().then((r) => setData(r.data)).catch(() => setErr('Failed to load dashboard'))
    DeviceAPI.list().then((r) => setDevices(r.data)).catch(() => {})
  }, [])

  if (err) return <p className="error">{err}</p>
  if (!data) return <p className="muted">Loading…</p>

  const withIps = devices.filter((d) => (d.ip_addresses || []).length > 0)

  return (
    <div className="grid" style={{ gap: 24 }}>
      <h2 style={{ margin: 0 }}>Dashboard</h2>
      <DashboardCards data={data} />

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Network addressing</h3>
        {withIps.length === 0
          ? <p className="muted">No IP addresses yet — run Smart Auto Config.</p>
          : (
            <table>
              <thead><tr><th>Device</th><th>Interface</th><th>IP address</th><th>Role</th></tr></thead>
              <tbody>
                {withIps.flatMap((d) =>
                  d.ip_addresses.map((x, i) => (
                    <tr key={d.id + '-' + i}>
                      <td>{i === 0 ? <strong>{d.hostname}</strong> : ''}</td>
                      <td className="muted">{x.interface}</td>
                      <td style={{ color: roleColor[x.role], fontWeight: 600 }}>{x.ip}</td>
                      <td className="muted">
                        {x.role === 'lan' ? 'LAN gateway'
                          : x.role === 'link' ? 'router-to-router link'
                          : x.role === 'mgmt' ? 'management' : 'interface'}
                      </td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Deploy history &amp; recent config activity</h3>
        <LogViewer logs={data.recent_deploys} />
      </div>
    </div>
  )
}
