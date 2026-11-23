import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { TopologyAPI } from '../services/api'
import { PORTS, icon } from './DeviceNode'

const HOVER_MS = 1000
const FETCH_MS = 300      // asked for early, so the box is ready on time

const fullName = (port) => port.replace(/^Gi(?=\d)/, 'GigabitEthernet').replace(/^Fa(?=\d)/, 'FastEthernet')

// what the server knows about, plus the drawn ports nothing uses yet
function allPorts(info) {
  const drawn = PORTS[info.type] || PORTS.pc
  const known = new Set(info.ports.map((p) => p.port))
  const unused = [...new Set([...drawn.top, ...drawn.bottom].map(fullName))]
    .filter((name) => !known.has(name))
    .map((port) => ({
      port, link: 'Down', ip: null,
      vlan: info.type !== 'switch' ? null : port.startsWith('Fast') ? info.spare_vlan : 1,
    }))
  return [...info.ports, ...unused]
    .sort((a, b) => a.port.localeCompare(b.port, undefined, { numeric: true }))
}

/** Packet-Tracer style info box: rest the mouse on a device for 1 second.
 *  Returns the React Flow handlers to spread, and the box to render. */
export function useDeviceTooltip(disabled) {
  const [info, setInfo] = useState(null)
  const hover = useRef({ id: null, timer: null, x: 0, y: 0 })

  const hide = useCallback(() => {
    clearTimeout(hover.current.timer)
    hover.current.id = null
    setInfo(null)
  }, [])
  useEffect(() => hide, [hide])
  useEffect(() => { if (disabled) hide() }, [disabled, hide])

  const onNodeMouseEnter = useCallback((e, node) => {
    hide()
    if (disabled || e.buttons) return
    const h = hover.current
    h.id = node.id; h.x = e.clientX; h.y = e.clientY
    h.timer = setTimeout(() => {
      const request = TopologyAPI.deviceInfo(node.id).catch(() => null)
      h.timer = setTimeout(async () => {
        const r = await request
        if (r && h.id === node.id) setInfo({ ...r.data, x: h.x, y: h.y })
      }, HOVER_MS - FETCH_MS)
    }, FETCH_MS)
  }, [disabled, hide])

  const onNodeMouseMove = useCallback((e) => {
    hover.current.x = e.clientX; hover.current.y = e.clientY
  }, [])

  return {
    handlers: {
      onNodeMouseEnter, onNodeMouseMove, onNodeMouseLeave: hide,
      onNodeDragStart: hide, onMoveStart: hide,
    },
    tooltip: info && <DeviceTooltip info={info} />,
  }
}

function DeviceTooltip({ info }) {
  const box = useRef(null)
  const [pos, setPos] = useState(null)

  // beside the mouse, but always fully inside the window
  useLayoutEffect(() => {
    const { width, height } = box.current.getBoundingClientRect()
    const fit = (at, size, room) => Math.max(8, Math.min(at + 14, room - size - 8))
    setPos({ left: fit(info.x, width, window.innerWidth), top: fit(info.y, height, window.innerHeight) })
  }, [info])

  return (
    <div ref={box} className="device-tooltip" role="tooltip"
      style={{ ...(pos || { left: 0, top: 0 }), visibility: pos ? 'visible' : 'hidden' }}>
      <div className="device-tooltip-head">
        <span style={{ fontSize: 20 }}>{icon[info.type] || '📦'}</span>
        <div>
          <div><span className="muted">Device Name:</span> <b>{info.name}</b></div>
          <div><span className="muted">Hostname:</span> <b>{info.hostname}</b></div>
        </div>
      </div>
      <table>
        <thead><tr><th>Interface</th><th>Link</th><th>VLAN</th><th>IP Address</th></tr></thead>
        <tbody>
          {allPorts(info).map((p) => (
            <tr key={p.port}>
              <td>{p.port}</td>
              <td className={p.link === 'Up' ? 'ok' : 'error'}>{p.link ? `● ${p.link}` : '--'}</td>
              <td>{p.vlan ?? '--'}</td>
              <td>{p.ip ? <b>{p.ip}</b> : <span className="muted">&lt;not set&gt;</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
