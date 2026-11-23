import { useEffect, useRef, useState } from 'react'
import { MonitoringAPI } from '../services/api'
import TerminalIcon from './TerminalIcon'

export default function PingTest() {
  const [endpoints, setEndpoints] = useState([])
  const [source, setSource] = useState('')
  const [target, setTarget] = useState('')
  const [busy, setBusy] = useState(false)
  const [res, setRes] = useState(null)
  const [err, setErr] = useState('')

  const load = () => MonitoringAPI.endpoints().then((r) => setEndpoints(r.data)).catch(() => {})
  useEffect(() => { load() }, [])

  const attempt = useRef(0)      // an answer that arrives after Refresh is dropped
  const run = async () => {
    const mine = ++attempt.current
    setBusy(true); setErr(''); setRes(null)
    try {
      const r = await MonitoringAPI.ping({ mode: 'design', source_ip: source, target, count: 5 })
      if (mine === attempt.current) setRes(r.data)
    } catch (e) {
      if (mine === attempt.current) setErr(e.response?.data?.detail || 'Ping failed')
    } finally {
      if (mine === attempt.current) setBusy(false)
    }
  }

  // clear everything for the next ping
  const reset = () => {
    attempt.current += 1
    setSource(''); setTarget(''); setRes(null); setErr(''); setBusy(false)
    load()
  }

  const swap = () => { setSource(target); setTarget(source); setRes(null) }
  const labelFor = (ip) => endpoints.find((e) => e.ip === ip)?.label

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h3 className="row" style={{ margin: 0, gap: 10 }}><TerminalIcon /> Ping test</h3>
        <div className="row">
          <button style={{ padding: '2px 8px', fontSize: 12 }} onClick={reset}
            title="Clear for the next ping">🔄 Refresh</button>
          <button style={{ padding: '2px 8px', fontSize: 12 }} onClick={load}>↻ reload IPs</button>
        </div>
      </div>

      <datalist id="ping-endpoints">
        {endpoints.map((e) => <option key={e.ip + e.label} value={e.ip}>{e.label}</option>)}
      </datalist>

      <div className="row" style={{ gap: 10, alignItems: 'flex-end', marginTop: 10, flexWrap: 'wrap' }}>
        <div className="field">
          <label className="muted">Source IP</label>
          <input list="ping-endpoints" value={source} onChange={(e) => setSource(e.target.value)}
            style={{ width: 180 }} />
        </div>
        <button title="swap" onClick={swap} style={{ padding: '8px 10px' }}>⇄</button>
        <div className="field">
          <label className="muted">Destination IP</label>
          <input list="ping-endpoints" value={target} onChange={(e) => setTarget(e.target.value)}
            style={{ width: 180 }} />
        </div>
        <button className="primary" disabled={busy || !source || !target} onClick={run}
          style={{ padding: '9px 22px' }}>
          {busy ? 'Pinging…' : 'Ping ▶'}
        </button>
      </div>
      {(labelFor(source) || labelFor(target)) && (
        <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
          {labelFor(source) || source} → {labelFor(target) || target}
        </div>
      )}

      {err && <p className="error" style={{ marginTop: 12 }}>{err}</p>}

      {res && (
        <div className={`ping-result ${res.ok ? 'ping-ok' : 'ping-fail'}`}>
          <div className="ping-verdict">{res.ok ? '✓  Ping successful' : '✕  No ping'}</div>
          <div className="ping-path">
            <span className="ping-node">{res.source}</span>
            <span className="ping-arrow">──▶</span>
            {res.via?.length > 0 && (
              <>
                <span className="ping-node">{res.via.join(' · ')}</span>
                <span className="ping-arrow">──▶</span>
              </>
            )}
            <span className="ping-node">{res.target}</span>
          </div>
          {res.source_net && (
            <div className="muted" style={{ fontSize: 12 }}>
              {res.source_net} → {res.target_net}
            </div>
          )}
          <div style={{ fontSize: 13, marginTop: 6 }}>{res.reason || res.output}</div>
        </div>
      )}

      <p className="muted" style={{ fontSize: 12, marginTop: 12 }}>
        Checks your topology + IP plan (subnets, gateways, OSPF, BGP) to tell you whether the ping
        would succeed on a real network — no simulator, no devices touched.
      </p>
    </div>
  )
}
