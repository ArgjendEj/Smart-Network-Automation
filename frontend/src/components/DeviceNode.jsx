import { Handle, Position } from 'reactflow'

const icon = { router: '🔀', switch: '🔗', pc: '💻', ip_phone: '📞', printer: '🖨️', server: '🗄️' }

// how many physical ports each device type shows
export const PORTS = {
  router: { top: ['Gi0/0', 'Gi0/1', 'Gi0/2'], bottom: ['Gi0/3', 'Gi0/4', 'Gi0/5'] },
  switch: {
    top: ['Fa0/1', 'Fa0/2', 'Fa0/3', 'Fa0/4'],
    bottom: ['Fa0/5', 'Fa0/6', 'Fa0/7', 'Gi0/1'],
  },
  // same port top and bottom - lets a cable be dragged from either side
  pc: { top: ['eth0'], bottom: ['eth0'] },
  ip_phone: { top: ['eth0'], bottom: ['eth0'] },
  printer: { top: ['eth0'], bottom: ['eth0'] },
  server: { top: ['eth0'], bottom: ['eth0'] },
}

const dot = {
  width: 9, height: 9, background: '#38bdf8', border: '2px solid #0f172a', borderRadius: '50%',
}

// when the same port name exists on both sides (pc/phone/printer/server -
// one "eth0" dot top, one at the bottom) the bottom one needs a distinct DOM
// id or React Flow always resolves the connection to the first (top) match
function row(list, position, otherList) {
  const n = list.length
  return list.map((port, i) => {
    const id = position === Position.Bottom && otherList.includes(port) ? `${port}__b` : port
    return (
      <Handle
        key={position + port}
        id={id}
        type="source"
        position={position}
        title={port}
        style={{ ...dot, left: `${((i + 1) / (n + 1)) * 100}%` }}
      />
    )
  })
}

export default function DeviceNode({ data }) {
  const ports = PORTS[data.type] || PORTS.pc
  const statusColor = data.status === 'online' ? '#22c55e'
    : data.status === 'offline' ? '#ef4444' : '#94a3b8'

  return (
    <div style={{
      background: '#1e293b', color: '#e2e8f0', border: '1px solid #334155',
      borderRadius: 10, padding: '10px 14px', width: 130, textAlign: 'center', fontSize: 12,
    }}>
      {row(ports.top, Position.Top, ports.bottom)}
      <div style={{ fontWeight: 700 }}>{icon[data.type] || '📦'} {data.name}</div>
      <div style={{ color: statusColor, fontSize: 11 }}>{data.status}</div>
      {row(ports.bottom, Position.Bottom, ports.top)}
    </div>
  )
}
