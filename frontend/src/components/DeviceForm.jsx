import { useEffect, useState } from 'react'

const EMPTY = {
  name: '', hostname: '', device_type: 'router',
  mgmt_ip: '', ssh_username: '', ssh_password: '', ssh_secret: '',
  netmiko_driver: 'cisco_ios', services: '',
}

const SERVER_ROLES = ['DHCP', 'DNS', 'Web', 'Syslog', 'NTP', 'Monitoring']

export default function DeviceForm({ initial, onSave, onCancel }) {
  const [form, setForm] = useState(EMPTY)
  const [ips, setIps] = useState([])   // [{interface, address}]

  useEffect(() => {
    setForm({ ...EMPTY, ...(initial || {}) })
    const manual = (initial?.ip_addresses || [])
      .filter((x) => x.role === 'manual')
      .map((x) => ({ interface: x.interface, address: x.ip }))
    setIps(manual)
  }, [initial])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const setIp = (i, k, v) => {
    const next = [...ips]; next[i] = { ...next[i], [k]: v }; setIps(next)
  }
  const submit = (e) => {
    e.preventDefault()
    const payload = { ...form }
    if (form.device_type === 'router') {
      payload.extra_ips = ips.filter((x) => x.interface.trim() && x.address.trim())
    }
    onSave(payload)
  }

  const isRouter = form.device_type === 'router'
  const isServer = form.device_type === 'server'
  const autoIps = (initial?.ip_addresses || []).filter((x) => x.role === 'lan' || x.role === 'link')

  const roleSet = new Set((form.services || '').split(',').map((s) => s.trim()).filter(Boolean))
  const toggleRole = (role) => {
    roleSet.has(role) ? roleSet.delete(role) : roleSet.add(role)
    setForm({ ...form, services: [...roleSet].join(',') })
  }

  return (
    <form className="card" onSubmit={submit} style={{ maxWidth: 560 }}>
      <h3 style={{ marginTop: 0 }}>{initial?.id ? 'Edit device' : 'Add device'}</h3>
      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <div className="field"><label className="muted">Name</label>
          <input required value={form.name} onChange={set('name')} /></div>
        <div className="field"><label className="muted">Hostname</label>
          <input required value={form.hostname} onChange={set('hostname')} /></div>
        <div className="field"><label className="muted">Type</label>
          <select value={form.device_type} onChange={set('device_type')}>
            <option value="router">Router</option>
            <option value="switch">Switch</option>
            <option value="pc">PC</option>
            <option value="ip_phone">IP Phone</option>
            <option value="printer">Printer</option>
            <option value="server">Server</option>
          </select></div>
        {form.device_type !== 'switch' && (
          <div className="field">
            <label className="muted">
              {form.device_type === 'router' ? 'Management IP' : 'IP address'}
            </label>
            <input value={form.mgmt_ip || ''} onChange={set('mgmt_ip')} placeholder="192.168.0.0" />
          </div>
        )}
        {isRouter && (
          <>
            <div className="field"><label className="muted">SSH username</label>
              <input value={form.ssh_username || ''} onChange={set('ssh_username')} /></div>
            <div className="field"><label className="muted">SSH password</label>
              <input type="password" value={form.ssh_password || ''} onChange={set('ssh_password')} /></div>
            <div className="field"><label className="muted">Enable secret</label>
              <input type="password" value={form.ssh_secret || ''} onChange={set('ssh_secret')} /></div>
            <div className="field"><label className="muted">Netmiko driver</label>
              <input value={form.netmiko_driver || 'cisco_ios'} onChange={set('netmiko_driver')} /></div>
          </>
        )}
      </div>

      {form.device_type === 'switch' && (
        <p className="muted" style={{ fontSize: 12, margin: '4px 0 10px' }}>
          Switch = pure Layer 2 — no IP address.
        </p>
      )}

      {isServer && (
        <div style={{ marginTop: 8 }}>
          <label className="muted">Services this server runs</label>
          <div className="row" style={{ flexWrap: 'wrap', gap: 12, marginTop: 6 }}>
            {SERVER_ROLES.map((role) => (
              <label key={role} className="row" style={{ gap: 5, fontSize: 13 }}>
                <input type="checkbox" checked={roleSet.has(role)} onChange={() => toggleRole(role)} />
                {role}
              </label>
            ))}
          </div>
          <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>
            On Auto-configure the routers pick these up: <b>DNS</b> → handed to DHCP clients,
            <b> Syslog</b> → <code>logging host</code>, <b>NTP</b> → <code>ntp server</code>,
            <b> DHCP</b> → routers relay with <code>ip helper-address</code> (no local pool).
            The server keeps a static low address in its subnet.
          </p>
        </div>
      )}

      {isRouter && (
        <div style={{ marginTop: 10 }}>
          <label className="muted">Interface IP addresses (for specific ports)</label>
          {ips.map((x, i) => (
            <div className="row" key={i} style={{ marginTop: 8 }}>
              <input placeholder="GigabitEthernet0/1" style={{ width: 190 }}
                value={x.interface} onChange={(e) => setIp(i, 'interface', e.target.value)} />
              <input placeholder="10.0.1.2/24" style={{ width: 160 }}
                value={x.address} onChange={(e) => setIp(i, 'address', e.target.value)} />
              <button type="button" onClick={() => setIps(ips.filter((_, j) => j !== i))}>✕</button>
            </div>
          ))}
          <button type="button" style={{ marginTop: 8 }}
            onClick={() => setIps([...ips, { interface: '', address: '' }])}>
            + interface IP
          </button>
          {autoIps.length > 0 && (
            <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
              Auto-configured: {autoIps.map((x) => `${x.interface} ${x.ip}`).join(' · ')}
            </p>
          )}
        </div>
      )}

      <div className="row" style={{ marginTop: 14 }}>
        <button className="primary" type="submit">Save</button>
        <button type="button" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  )
}
