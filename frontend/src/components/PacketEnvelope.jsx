import { useEffect, useRef, useState } from 'react'
import { EdgeLabelRenderer, useReactFlow } from 'reactflow'

const CABLE_MS = 650      // along one cable
const DEVICE_MS = 170     // from a device's middle to its port, and back
const PAUSE_MS = 170      // resting on each device
const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - (2 - 2 * t) ** 2 / 2)
const between = (a, b, t) => ({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t })

/** The envelope of the packet test: follows the drawn cables hop by hop and, if
 *  the ping succeeds, comes back to the sender - like Packet Tracer. */
export default function PacketEnvelope({ trip, onDone }) {
  const { getNode, getEdge } = useReactFlow()
  const el = useRef(null)
  const done = useRef(onDone)
  done.current = onDone
  const [mark, setMark] = useState(null)      // null | 'ok' | 'fail'
  const [shown, setShown] = useState(false)

  useEffect(() => {
    if (!trip) { setShown(false); return undefined }
    setMark(null); setShown(true)

    const middle = (id) => {
      const n = getNode(String(id))
      return n ? { x: n.position.x + (n.width || 130) / 2, y: n.position.y + (n.height || 56) / 2 }
        : { x: 0, y: 0 }
    }
    // a point along a cable; the line is re-read every frame so moving a device
    // mid-flight keeps the envelope on its cable
    const onCable = (hop, t) => {
      const id = String(hop.connection_id)
      const line = document.querySelector(`.react-flow__edge-path[id="${id}"]`)
      const edge = getEdge(id)
      if (!line || !edge) return between(middle(hop.from), middle(hop.to), t)
      const forward = edge.source === String(hop.from)
      return line.getPointAtLength(line.getTotalLength() * (forward ? t : 1 - t))
    }

    const back = trip.hops.map((h) => ({ ...h, from: h.to, to: h.from })).reverse()
    const steps = []
    for (const hop of trip.ok ? [...trip.hops, ...back] : trip.hops) {
      steps.push(
        { ms: DEVICE_MS, at: (t) => between(middle(hop.from), onCable(hop, 0), t) },
        { ms: CABLE_MS, at: (t) => onCable(hop, ease(t)) },
        { ms: DEVICE_MS, at: (t) => between(onCable(hop, 1), middle(hop.to), t) },
        { ms: PAUSE_MS, at: () => middle(hop.to) },
      )
    }
    const last = trip.ok || !trip.hops.length ? trip.source_id : trip.hops[trip.hops.length - 1].to

    let frame; let hide
    let i = 0; let began = null
    const place = (p) => {
      if (el.current) el.current.style.transform = `translate(-50%,-50%) translate(${p.x}px,${p.y}px)`
    }
    const tick = (now) => {
      if (began === null) began = now
      while (i < steps.length && now - began >= steps[i].ms) { began += steps[i].ms; i += 1 }
      if (i < steps.length) {
        place(steps[i].at((now - began) / steps[i].ms))
        frame = requestAnimationFrame(tick)
        return
      }
      place(middle(last))
      setMark(trip.ok ? 'ok' : 'fail')
      done.current?.()
      hide = setTimeout(() => setShown(false), 4000)
    }
    frame = requestAnimationFrame(tick)
    return () => { cancelAnimationFrame(frame); clearTimeout(hide) }
  }, [trip, getNode, getEdge])

  if (!trip || !shown) return null
  return (
    <EdgeLabelRenderer>
      <div ref={el} className="packet-envelope" style={{ position: 'absolute', zIndex: 2000, pointerEvents: 'none' }}>
        <svg width="36" height="26" viewBox="0 0 36 26" style={{ display: 'block' }}>
          <rect x="1.5" y="1.5" width="33" height="23" rx="3" fill="#f9a8d4" stroke="#831843" strokeWidth="2" />
          <path d="M2.5 3.5 L18 15 L33.5 3.5" fill="none" stroke="#831843" strokeWidth="2" strokeLinejoin="round" />
        </svg>
        {mark && (
          <div style={{
            position: 'absolute', right: -11, top: -11, width: 22, height: 22, borderRadius: '50%',
            background: mark === 'ok' ? '#15803d' : '#b91c1c', color: '#fff',
            display: 'grid', placeItems: 'center', fontSize: 14, fontWeight: 800,
          }}>
            {mark === 'ok' ? '✓' : '✕'}
          </div>
        )}
      </div>
    </EdgeLabelRenderer>
  )
}
