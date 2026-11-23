import { useCallback, useRef, useState } from 'react'
import PacketTest from '../components/PacketTest'
import PingTest from '../components/PingTest'
import TopologyCanvas from '../components/TopologyCanvas'
import { MonitoringAPI } from '../services/api'

export default function Topology() {
  const [graph, setGraph] = useState({ nodes: [], edges: [] })

  // interface names on the cables; the choice is remembered in this browser
  const [showInterfaces, setShowInterfaces] = useState(() => {
    try { return localStorage.getItem('showInterfaces') !== 'no' } catch { return true }
  })
  const toggleInterfaces = () => {
    try { localStorage.setItem('showInterfaces', showInterfaces ? 'no' : 'yes') } catch { /* storage blocked */ }
    setShowInterfaces(!showInterfaces)
  }

  // packet (envelope) test
  const [source, setSource] = useState('')
  const [target, setTarget] = useState('')
  const [pick, setPick] = useState(null)         // null | 'source' | 'target'
  const [pickHint, setPickHint] = useState('')
  const [trip, setTrip] = useState(null)         // what the server traced
  const [running, setRunning] = useState(false)
  const [packetErr, setPacketErr] = useState('')
  const map = useRef(null)
  const attempt = useRef(0)      // an answer that arrives after Refresh is dropped

  const send = useCallback(async (from, to) => {
    const mine = ++attempt.current
    setPacketErr(''); setTrip(null); setRunning(true)
    map.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    try {
      const r = await MonitoringAPI.packet(Number(from), Number(to))
      if (mine === attempt.current) setTrip(r.data)
    } catch (e) {
      if (mine !== attempt.current) return
      setPacketErr(e.response?.data?.detail || 'Could not send the packet')
      setRunning(false)
    }
  }, [])

  // clear everything (and stop an envelope on its way) for the next packet
  const reset = () => {
    attempt.current += 1
    setSource(''); setTarget(''); setPick(null); setPickHint('')
    setTrip(null); setRunning(false); setPacketErr('')
  }

  const togglePick = () => {
    setPickHint('')
    if (pick) { setPick(null); return }
    setTrip(null); setPacketErr(''); setPick('source')
    map.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  const onPick = useCallback((device) => {
    if (device.type === 'switch') { setPickHint(`${device.name} is a switch (no IP). `); return }
    const id = String(device.id)
    if (pick === 'source') { setSource(id); setTarget(''); setPickHint(''); setPick('target'); return }
    if (id === source) { setPickHint('That is the source. '); return }
    setTarget(id); setPick(null); setPickHint('')
    send(source, id)
  }, [pick, source, send])

  const notice = pick
    ? `✉️ ${pickHint}Click the ${pick === 'source' ? 'source' : 'destination'} device`
    : trip && !running
      ? <span className={trip.ok ? 'ok' : 'error'}>
          {trip.ok ? '✓ Successful' : '✕ Failed'}: {trip.source} → {trip.target}
        </span>
      : null

  return (
    <div className="grid" style={{ gap: 16 }}>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h2 style={{ margin: 0 }}>Network Topology</h2>
        <div className="muted" style={{ fontSize: 13 }}>
          Drag nodes to move · drag port-to-port to add a cable · <b>double-click a device</b> to edit ·{' '}
          <b>double-click a cable</b> (or its ✕) to delete
        </div>
      </div>
      <div ref={map}>
        <TopologyCanvas onGraphChange={setGraph} picking={!!pick} onPick={onPick}
          trip={trip} onTripDone={() => setRunning(false)} notice={notice}
          showInterfaces={showInterfaces} />
      </div>
      <div className="row muted" style={{ fontSize: 13 }}>
        <span>{graph.nodes.length} devices</span>
        <span>·</span>
        <span>{graph.edges.length} links</span>
        <span>·</span>
        <span style={{ color: 'var(--accent)' }}>— access</span>
        <span style={{ color: 'var(--amber)' }}>— trunk</span>
        <button style={{ marginLeft: 'auto' }} onClick={toggleInterfaces}>
          {showInterfaces ? '🙈 Hide Interfaces' : '👁️ Show Interfaces'}
        </button>
      </div>
      <PacketTest devices={graph.nodes} source={source} target={target}
        onSource={setSource} onTarget={setTarget} onSend={() => send(source, target)}
        picking={!!pick} onPickToggle={togglePick} onReset={reset} running={running} result={trip} error={packetErr} />
      <PingTest />
    </div>
  )
}
