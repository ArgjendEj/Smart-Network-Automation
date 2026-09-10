const icon = { router: '🔀', switch: '🔗', pc: '💻', ip_phone: '📞', printer: '🖨️', server: '🗄️' }
const roleColor = { lan: 'var(--green)', link: 'var(--amber)', mgmt: 'var(--accent)', iface: 'var(--muted)' }

function IpList({ device }) {
  const ips = device.ip_addresses || []
  if (!ips.length) {
    return device.device_type === 'switch'
      ? <span className="muted">— (Layer 2)</span>
      : <span className="muted">—</span>
  }
  return (
    <div className="grid" style={{ gap: 2 }}>
      {ips.map((x, i) => (
        <div key={i} style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
          <span style={{ color: roleColor[x.role] || 'var(--text)', fontWeight: 600 }}>{x.ip}</span>
          {x.interface !== 'mgmt' && <span className="muted"> · {x.interface}</span>}
          {x.role === 'link' && <span className="muted"> (to peer)</span>}
        </div>
      ))}
    </div>
  )
}

export default function DeviceTable({ devices, onEdit, onDelete, onPing, onConfig, onDhcp, filter }) {
  const rows = devices.filter((d) =>
    !filter || d.name.toLowerCase().includes(filter.toLowerCase()) ||
    d.hostname.toLowerCase().includes(filter.toLowerCase()),
  )
  return (
    <table>
      <thead>
        <tr>
          <th>Device</th><th>Type</th><th>IP addresses</th><th>Status</th><th></th>
        </tr>
      </thead>
      <tbody>
        {rows.map((d) => (
          <tr key={d.id}>
            <td><strong>{d.name}</strong> <span className="muted">/ {d.hostname}</span></td>
            <td>
              {icon[d.device_type]} {d.device_type === 'ip_phone' ? 'ip phone' : d.device_type}
              {d.device_type === 'server' && d.services && (
                <div className="muted" style={{ fontSize: 11 }}>{d.services.split(',').join(' · ')}</div>
              )}
            </td>
            <td><IpList device={d} /></td>
            <td><span className={`pill ${d.status}`}>{d.status}</span></td>
            <td>
              <div className="row">
                <button onClick={() => onPing(d)}>Ping</button>
                {['pc', 'ip_phone', 'printer'].includes(d.device_type)
                  && <button onClick={() => onDhcp(d)}>DHCP</button>}
                {['router', 'switch'].includes(d.device_type)
                  && <button onClick={() => onConfig(d)}>Config</button>}
                <button onClick={() => onEdit(d)}>Edit</button>
                <button onClick={() => onDelete(d)}>Delete</button>
              </div>
            </td>
          </tr>
        ))}
        {!rows.length && <tr><td colSpan={5} className="muted">No devices.</td></tr>}
      </tbody>
    </table>
  )
}
