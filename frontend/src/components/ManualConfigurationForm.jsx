import { useState } from 'react'

const emptyIface = { name: '', ip_address: '', subnet_mask: '', mode: '', vlan_id: '', description: '', enabled: true }
const emptyVlan = { vlan_id: '', name: '' }
const emptyDhcp = { pool_name: '', network: '', netmask: '255.255.255.0', default_gateway: '', dns: '8.8.8.8' }
const emptyOspfNet = { network: '', wildcard: '0.0.0.255', area: '0' }
const emptyBgpNet = { network: '', mask: '255.255.255.0' }
const emptyBgpNeighbor = { ip: '', remote_as: '' }

export default function ManualConfigurationForm({ devices, onSubmit }) {
  const [deviceId, setDeviceId] = useState('')
  const [hostname, setHostname] = useState('')
  const [interfaces, setInterfaces] = useState([{ ...emptyIface }])
  const [vlans, setVlans] = useState([])
  const [dhcp, setDhcp] = useState([])
  const [ospf, setOspf] = useState({ on: false, process_id: '1', router_id: '', networks: [] })
  const [bgp, setBgp] = useState({ on: false, asn: '', router_id: '', networks: [], neighbors: [] })
  const [deploy, setDeploy] = useState(false)

  const dev = devices.find((d) => String(d.id) === deviceId)
  const isSwitch = dev?.device_type === 'switch'
  const isRouter = dev?.device_type === 'router'

  const updOspfNet = (i, k, v) => setOspf((o) => {
    const networks = [...o.networks]; networks[i] = { ...networks[i], [k]: v }; return { ...o, networks }
  })
  const updBgpNet = (i, k, v) => setBgp((b) => {
    const networks = [...b.networks]; networks[i] = { ...networks[i], [k]: v }; return { ...b, networks }
  })
  const updBgpNeighbor = (i, k, v) => setBgp((b) => {
    const neighbors = [...b.neighbors]; neighbors[i] = { ...neighbors[i], [k]: v }; return { ...b, neighbors }
  })

  const upd = (setter, list) => (i, k, v) => {
    const next = [...list]; next[i] = { ...next[i], [k]: v }; setter(next)
  }
  const updIface = upd(setInterfaces, interfaces)
  const updVlan = upd(setVlans, vlans)
  const updDhcp = upd(setDhcp, dhcp)

  const submit = (e) => {
    e.preventDefault()
    onSubmit({
      device_id: Number(deviceId),
      hostname: hostname || null,
      interfaces: interfaces.filter((x) => x.name).map((x) => ({
        ...x,
        vlan_id: isSwitch && x.vlan_id ? Number(x.vlan_id) : null,
        mode: isSwitch ? (x.mode || null) : null,
        ip_address: isSwitch ? null : (x.ip_address || null),
        subnet_mask: isSwitch ? null : (x.subnet_mask || null),
        description: x.description || null,
      })),
      vlans: isSwitch ? vlans.filter((x) => x.vlan_id).map((x) => ({ vlan_id: Number(x.vlan_id), name: x.name || null })) : [],
      dhcp: isSwitch ? [] : dhcp.filter((x) => x.pool_name && x.network).map((x) => ({ ...x })),
      ospf: (isRouter && ospf.on && ospf.networks.some((n) => n.network)) ? {
        process_id: Number(ospf.process_id) || 1,
        router_id: ospf.router_id || null,
        networks: ospf.networks.filter((n) => n.network).map((n) => ({
          network: n.network, wildcard: n.wildcard || '0.0.0.255', area: n.area || '0',
        })),
        passive_interfaces: [],
      } : null,
      bgp: (isRouter && bgp.on && bgp.asn && (bgp.networks.some((n) => n.network) || bgp.neighbors.some((n) => n.ip))) ? {
        asn: Number(bgp.asn),
        router_id: bgp.router_id || null,
        networks: bgp.networks.filter((n) => n.network).map((n) => ({
          network: n.network, mask: n.mask || '255.255.255.0',
        })),
        neighbors: bgp.neighbors.filter((n) => n.ip).map((n) => ({
          ip: n.ip, remote_as: Number(n.remote_as),
        })),
      } : null,
      deploy,
    })
  }

  return (
    <form className="card grid" style={{ gap: 16 }} onSubmit={submit}>
      <div className="row">
        <div className="field">
          <label className="muted">Device</label>
          <select required value={deviceId} onChange={(e) => setDeviceId(e.target.value)}>
            <option value="">— select —</option>
            {devices
              .filter((d) => d.device_type === 'router' || d.device_type === 'switch')
              .map((d) => <option key={d.id} value={d.id}>{d.name} ({d.device_type})</option>)}
          </select>
        </div>
        <div className="field">
          <label className="muted">Hostname (optional)</label>
          <input value={hostname} onChange={(e) => setHostname(e.target.value)} />
        </div>
      </div>

      <section>
        <label className="muted">
          Interfaces{isSwitch && <span className="muted"> — switch ports are Layer 2 only (no IP)</span>}
        </label>
        {interfaces.map((x, i) => (
          <div className="row" key={i} style={{ marginTop: 8 }}>
            <input placeholder="GigabitEthernet0/1" value={x.name} onChange={(e) => updIface(i, 'name', e.target.value)} />
            {!isSwitch && (
              <>
                <input placeholder="IP" style={{ width: 120 }} value={x.ip_address} onChange={(e) => updIface(i, 'ip_address', e.target.value)} />
                <input placeholder="Mask" style={{ width: 130 }} value={x.subnet_mask} onChange={(e) => updIface(i, 'subnet_mask', e.target.value)} />
              </>
            )}
            {isSwitch && (
              <>
                <select value={x.mode} onChange={(e) => updIface(i, 'mode', e.target.value)}>
                  <option value="">mode…</option>
                  <option value="access">access</option>
                  <option value="trunk">trunk</option>
                </select>
                <input placeholder="VLAN" style={{ width: 80 }} value={x.vlan_id} onChange={(e) => updIface(i, 'vlan_id', e.target.value)} />
              </>
            )}
            <label className="row" style={{ gap: 4 }}>
              <input type="checkbox" checked={x.enabled} onChange={(e) => updIface(i, 'enabled', e.target.checked)} /> up
            </label>
            <button type="button" onClick={() => setInterfaces(interfaces.filter((_, j) => j !== i))}>✕</button>
          </div>
        ))}
        <button type="button" style={{ marginTop: 8 }} onClick={() => setInterfaces([...interfaces, { ...emptyIface }])}>+ interface</button>
      </section>

      <section hidden={!isSwitch}>
        <label className="muted">VLANs</label>
        {vlans.map((x, i) => (
          <div className="row" key={i} style={{ marginTop: 8 }}>
            <input placeholder="VLAN id" style={{ width: 90 }} value={x.vlan_id} onChange={(e) => updVlan(i, 'vlan_id', e.target.value)} />
            <input placeholder="name" value={x.name} onChange={(e) => updVlan(i, 'name', e.target.value)} />
            <button type="button" onClick={() => setVlans(vlans.filter((_, j) => j !== i))}>✕</button>
          </div>
        ))}
        <button type="button" style={{ marginTop: 8 }} onClick={() => setVlans([...vlans, { ...emptyVlan }])}>+ VLAN</button>
      </section>

      <section hidden={isSwitch}>
        <label className="muted">DHCP pools</label>
        {dhcp.map((x, i) => (
          <div className="row" key={i} style={{ marginTop: 8 }}>
            <input placeholder="pool name" value={x.pool_name} onChange={(e) => updDhcp(i, 'pool_name', e.target.value)} />
            <input placeholder="network 10.10.1.0" value={x.network} onChange={(e) => updDhcp(i, 'network', e.target.value)} />
            <input placeholder="netmask" style={{ width: 130 }} value={x.netmask} onChange={(e) => updDhcp(i, 'netmask', e.target.value)} />
            <input placeholder="gateway" style={{ width: 120 }} value={x.default_gateway} onChange={(e) => updDhcp(i, 'default_gateway', e.target.value)} />
            <input placeholder="dns" style={{ width: 110 }} value={x.dns} onChange={(e) => updDhcp(i, 'dns', e.target.value)} />
            <button type="button" onClick={() => setDhcp(dhcp.filter((_, j) => j !== i))}>✕</button>
          </div>
        ))}
        <button type="button" style={{ marginTop: 8 }} onClick={() => setDhcp([...dhcp, { ...emptyDhcp }])}>+ DHCP pool</button>
      </section>

      <section hidden={!isRouter}>
        <label className="row" style={{ gap: 6 }}>
          <input type="checkbox" checked={ospf.on} onChange={(e) => setOspf({ ...ospf, on: e.target.checked })} />
          <b>OSPF</b>
        </label>
        {ospf.on && (
          <div className="grid" style={{ gap: 8, marginTop: 8 }}>
            <div className="row">
              <input placeholder="process id" style={{ width: 100 }} value={ospf.process_id}
                onChange={(e) => setOspf({ ...ospf, process_id: e.target.value })} />
              <input placeholder="router-id (optional)" style={{ width: 170 }} value={ospf.router_id}
                onChange={(e) => setOspf({ ...ospf, router_id: e.target.value })} />
            </div>
            {ospf.networks.map((n, i) => (
              <div className="row" key={i}>
                <input placeholder="network 192.168.1.0" value={n.network} onChange={(e) => updOspfNet(i, 'network', e.target.value)} />
                <input placeholder="wildcard" style={{ width: 120 }} value={n.wildcard} onChange={(e) => updOspfNet(i, 'wildcard', e.target.value)} />
                <input placeholder="area" style={{ width: 70 }} value={n.area} onChange={(e) => updOspfNet(i, 'area', e.target.value)} />
                <button type="button" onClick={() => setOspf({ ...ospf, networks: ospf.networks.filter((_, j) => j !== i) })}>✕</button>
              </div>
            ))}
            <button type="button" onClick={() => setOspf({ ...ospf, networks: [...ospf.networks, { ...emptyOspfNet }] })}>+ network</button>
          </div>
        )}
      </section>

      <section hidden={!isRouter}>
        <label className="row" style={{ gap: 6 }}>
          <input type="checkbox" checked={bgp.on} onChange={(e) => setBgp({ ...bgp, on: e.target.checked })} />
          <b>BGP</b>
        </label>
        {bgp.on && (
          <div className="grid" style={{ gap: 8, marginTop: 8 }}>
            <div className="row">
              <input placeholder="AS number" style={{ width: 110 }} value={bgp.asn}
                onChange={(e) => setBgp({ ...bgp, asn: e.target.value })} />
              <input placeholder="router-id (optional)" style={{ width: 170 }} value={bgp.router_id}
                onChange={(e) => setBgp({ ...bgp, router_id: e.target.value })} />
            </div>
            <label className="muted" style={{ fontSize: 12 }}>Advertised networks</label>
            {bgp.networks.map((n, i) => (
              <div className="row" key={i}>
                <input placeholder="network 192.168.1.0" value={n.network} onChange={(e) => updBgpNet(i, 'network', e.target.value)} />
                <input placeholder="mask" style={{ width: 140 }} value={n.mask} onChange={(e) => updBgpNet(i, 'mask', e.target.value)} />
                <button type="button" onClick={() => setBgp({ ...bgp, networks: bgp.networks.filter((_, j) => j !== i) })}>✕</button>
              </div>
            ))}
            <button type="button" onClick={() => setBgp({ ...bgp, networks: [...bgp.networks, { ...emptyBgpNet }] })}>+ network</button>
            <label className="muted" style={{ fontSize: 12 }}>Neighbors</label>
            {bgp.neighbors.map((n, i) => (
              <div className="row" key={i}>
                <input placeholder="neighbor IP 10.0.0.2" value={n.ip} onChange={(e) => updBgpNeighbor(i, 'ip', e.target.value)} />
                <input placeholder="remote-as" style={{ width: 110 }} value={n.remote_as} onChange={(e) => updBgpNeighbor(i, 'remote_as', e.target.value)} />
                <button type="button" onClick={() => setBgp({ ...bgp, neighbors: bgp.neighbors.filter((_, j) => j !== i) })}>✕</button>
              </div>
            ))}
            <button type="button" onClick={() => setBgp({ ...bgp, neighbors: [...bgp.neighbors, { ...emptyBgpNeighbor }] })}>+ neighbor</button>
          </div>
        )}
      </section>

      <div className="row">
        <label className="row" style={{ gap: 6 }}>
          <input type="checkbox" checked={deploy} onChange={(e) => setDeploy(e.target.checked)} /> Deploy over SSH
        </label>
        <button className="primary" type="submit" disabled={!deviceId}>Generate configuration</button>
      </div>
    </form>
  )
}
