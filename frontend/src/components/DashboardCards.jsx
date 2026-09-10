export default function DashboardCards({ data }) {
  const cards = [
    ['Total devices', data.total_devices],
    ['Online', data.online_devices, 'ok'],
    ['Offline', data.offline_devices, 'error'],
    ['VLANs', data.total_vlans],
    ['Routers', data.routers],
    ['Switches', data.switches],
    ['PCs', data.pcs],
    ['Servers', data.servers ?? 0],
    ['IP phones', data.ip_phones ?? 0],
    ['Printers', data.printers ?? 0],
  ]
  return (
    <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))' }}>
      {cards.map(([label, value, cls]) => (
        <div className="card" key={label}>
          <div className="muted" style={{ fontSize: 13 }}>{label}</div>
          <div className={`stat ${cls || ''}`}>{value}</div>
        </div>
      ))}
    </div>
  )
}
