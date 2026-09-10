import { useState } from 'react'
import DeploymentStatus from '../components/DeploymentStatus'
import { SmartAPI } from '../services/api'

export default function SmartConfiguration() {
  const [results, setResults] = useState([])
  const [err, setErr] = useState('')
  const [autoBusy, setAutoBusy] = useState(false)
  const [autoRes, setAutoRes] = useState(null)
  const [autoRouting, setAutoRouting] = useState('ospf')
  const [autoNat, setAutoNat] = useState(false)

  const doAuto = async (scope) => {
    setErr(''); setAutoBusy(scope); setAutoRes(null)
    try {
      const r = await SmartAPI.auto(scope, autoRouting, autoNat)
      setAutoRes({ ...r.data, scope })
      setResults(r.data.results.map((x) => ({
        device_id: x.device, device_name: x.device, config: x.config, deployed: false,
      })))
    } catch (e) {
      setErr(e.response?.data?.detail || 'Auto configuration failed')
    } finally {
      setAutoBusy(false)
    }
  }

  return (
    <div className="grid" style={{ gap: 16 }}>
      <h2 style={{ margin: 0 }}>Smart Auto Configuration</h2>

      <div className="card" style={{ borderColor: 'var(--accent-2)' }}>
        <h3 style={{ marginTop: 0 }}>⚡ Auto-configure from the topology</h3>
        <p className="muted" style={{ marginTop: -4 }}>
          Place devices, cable them in <b>Topology</b>, then press a button. No forms.
        </p>
        <div className="row" style={{ marginBottom: 10 }}>
          <label className="muted" style={{ fontSize: 13 }}>Routing protocol between routers:</label>
          <select value={autoRouting} onChange={(e) => setAutoRouting(e.target.value)}>
            <option value="ospf">OSPF</option>
            <option value="bgp">BGP (eBGP, one AS per router)</option>
            <option value="both">OSPF + BGP (both at once)</option>
          </select>
          <label className="row" style={{ gap: 6, fontSize: 13 }}>
            <input type="checkbox" checked={autoNat} onChange={(e) => setAutoNat(e.target.checked)} />
            Enable NAT overload (PAT) on routers
          </label>
        </div>
        <div className="row">
          <button className="primary" disabled={!!autoBusy} onClick={() => doAuto('lan')}
            style={{ padding: '10px 20px' }}>
            {autoBusy === 'lan' ? 'Configuring…' : '🏠 Configure local networks + DHCP'}
          </button>
          <button className="primary" disabled={!!autoBusy} onClick={() => doAuto('wan')}
            style={{ padding: '10px 20px' }}>
            {autoBusy === 'wan' ? 'Configuring…' : '🔗 Configure router-to-router links'}
          </button>
          <button disabled={!!autoBusy} onClick={() => doAuto('all')}>
            {autoBusy === 'all' ? '…' : 'Both'}
          </button>
        </div>
        <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          <b>Local networks</b>: each router↔switch/PC link gets a subnet, a DHCP pool, every PC/phone/
          printer gets an address, servers keep a static low address, and each switch gets its own VLAN.
          Server roles (DNS / Syslog / NTP / DHCP relay) are wired into the routers. &nbsp;
          <b>Router-to-router</b>: each router↔router link gets matching IPs + routing.
        </p>

        {autoRes && (
          <div style={{ marginTop: 14 }}>
            <p className="muted" style={{ fontSize: 12 }}>
              Routing: <b>{(autoRes.routing || 'ospf').toUpperCase()}</b>
              {autoRes.nat ? <> · NAT overload: <b>on</b></> : null}
              {autoRes.services && Object.entries(autoRes.services).filter(([, v]) => v).map(([k, v]) => (
                <span key={k}> · {k}: <b>{v}</b></span>
              ))}
            </p>
            {autoRes.segments.map((s) => (
              <div key={s.router} className="ping-result ping-ok" style={{ marginBottom: 8 }}>
                <b>{s.router}</b>{s.asn ? <span className="muted"> · AS {s.asn}</span> : null}
                {s.nat_outside && (
                  <span className="muted"> · NAT outside: {s.nat_outside}</span>
                )}
                {s.lan.map((l, i) => (
                  <div key={i} style={{ fontSize: 13 }}>
                    LAN {l.iface} → {l.network} · gateway {l.gateway}
                    {l.vlan_id ? ` · VLAN ${l.vlan_id}` : ''} · DHCP on
                    {s.nat_outside ? ' · NAT inside' : ''}
                  </div>
                ))}
                {s.links.map((l, i) => (
                  <div key={i} style={{ fontSize: 13 }}>
                    Link {l.iface} → {l.ip} ↔ {l.peer}
                    {l.peer_asn ? <span className="muted"> (BGP neighbor {l.peer_ip}, AS {l.peer_asn})</span> : null}
                  </div>
                ))}
              </div>
            ))}
            {autoRes.dhcp.length > 0 && (
              <table style={{ marginTop: 8 }}>
                <thead><tr><th>PC</th><th>DHCP address</th><th>Network</th><th>Gateway</th></tr></thead>
                <tbody>
                  {autoRes.dhcp.map((d) => (
                    <tr key={d.pc}><td>{d.pc}</td><td>{d.ip}</td><td>{d.network}</td><td>{d.gateway}</td></tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {err && <div className="error">{err}</div>}

      <DeploymentStatus results={results} />
    </div>
  )
}
