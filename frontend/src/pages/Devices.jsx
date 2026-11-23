import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import DeviceForm from '../components/DeviceForm'
import DeviceTable from '../components/DeviceTable'
import PingTest from '../components/PingTest'
import { DeviceAPI } from '../services/api'

export default function Devices() {
  const [devices, setDevices] = useState([])
  const [editing, setEditing] = useState(null)   // device | {} for new | null
  const [filter, setFilter] = useState('')
  const [config, setConfig] = useState(null)
  const [dhcp, setDhcp] = useState(null)   // { pc, scopes, vlanId, result, err }
  const [msg, setMsg] = useState('')

  // Config / DHCP open below the table: bring the panel into view on every click
  const panels = { config: useRef(null), dhcp: useRef(null) }
  const [jump, setJump] = useState(null)   // a new { to } each time
  useEffect(() => {
    if (jump) panels[jump.to].current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [jump])

  const load = () => DeviceAPI.list().then((r) => setDevices(r.data))
  useEffect(() => { load() }, [])

  // /devices?edit=<id> (double-click in the topology) opens that device's form
  const [params, setParams] = useSearchParams()
  const editId = params.get('edit')
  useEffect(() => {
    if (!editId || !devices.length) return
    const d = devices.find((x) => String(x.id) === editId)
    if (d) { setEditing(d); window.scrollTo(0, 0) }
    setParams({}, { replace: true })   // so Cancel / Save / refresh don't reopen it
  }, [editId, devices, setParams])

  const save = async (form) => {
    try {
      if (form.id) await DeviceAPI.update(form.id, form)
      else await DeviceAPI.create(form)
      setEditing(null); await load()
    } catch (e) {
      setMsg(e.response?.data?.detail || 'Save failed')
    }
  }

  const remove = async (d) => {
    if (!confirm(`Delete ${d.name}?`)) return
    await DeviceAPI.remove(d.id); await load()
  }

  const ping = async (d) => {
    setMsg(`Checking ${d.name}…`)
    const r = await DeviceAPI.status(d.id)
    setMsg(`${d.name} is ${r.data.status}`)
    await load()
  }

  const showConfig = async (d) => {
    const r = await DeviceAPI.config(d.id)
    setConfig({ name: d.name, text: r.data.config || '! no configuration generated yet' })
    setJump({ to: 'config' })
  }

  const openDhcp = async (d) => {
    setConfig(null)
    const scopes = (await DeviceAPI.dhcpScopes()).data
    setDhcp({ pc: d, scopes, subnet: '', result: null, err: '' })
    setJump({ to: 'dhcp' })
  }

  const runDhcp = async () => {
    try {
      const r = await DeviceAPI.requestDhcp(dhcp.pc.id, dhcp.subnet || null)
      setDhcp({ ...dhcp, result: r.data, err: '' })
      await load()
    } catch (e) {
      setDhcp({ ...dhcp, err: e.response?.data?.detail || 'DHCP failed', result: null })
    }
  }

  const releaseDhcp = async () => {
    await DeviceAPI.releaseDhcp(dhcp.pc.id)
    setDhcp(null); await load()
  }

  return (
    <div className="grid" style={{ gap: 16 }}>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h2 style={{ margin: 0 }}>Device Management</h2>
        <div className="row">
          <input placeholder="Search…" value={filter} onChange={(e) => setFilter(e.target.value)} />
          <button onClick={async () => {
            setMsg('Checking all devices…')
            await DeviceAPI.refreshAll(); await load(); setMsg('Status refreshed')
          }}>Refresh status</button>
          <button className="primary" onClick={() => setEditing({})}>+ Add device</button>
        </div>
      </div>
      {msg && <div className="muted">{msg}</div>}

      {editing && (
        <DeviceForm initial={editing.id ? editing : null}
          onSave={save} onCancel={() => setEditing(null)} />
      )}

      <div className="card">
        <DeviceTable devices={devices} filter={filter}
          onEdit={setEditing} onDelete={remove} onPing={ping}
          onConfig={showConfig} onDhcp={openDhcp} />
      </div>

      {dhcp && (
        <div className="card" ref={panels.dhcp} style={{ scrollMarginTop: 16 }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <h3 style={{ margin: 0 }}>DHCP — {dhcp.pc.name}</h3>
            <button onClick={() => setDhcp(null)}>Close</button>
          </div>
          {dhcp.scopes.length === 0 ? (
            <p className="muted">
              No DHCP scope yet. Run <b>Smart Auto Config</b> with “Configure DHCP” enabled first.
            </p>
          ) : (
            <>
              <div className="row" style={{ marginTop: 8 }}>
                <div className="field">
                  <label className="muted">Network / pool (auto-detected from topology if left)</label>
                  <select value={dhcp.subnet} onChange={(e) => setDhcp({ ...dhcp, subnet: e.target.value })}>
                    <option value="">Auto-detect</option>
                    {dhcp.scopes.map((s) => (
                      <option key={s.subnet} value={s.subnet}>
                        {s.subnet} · {s.router} · VLAN {s.vlan_id} ({s.free} free)
                      </option>
                    ))}
                  </select>
                </div>
                <button className="primary" onClick={runDhcp}>Request address</button>
                {dhcp.pc.mgmt_ip && <button onClick={releaseDhcp}>Release {dhcp.pc.mgmt_ip}</button>}
              </div>
              {dhcp.err && <p className="error">{dhcp.err}</p>}
              {dhcp.result && (
                <div className="ping-result ping-ok" style={{ marginTop: 12 }}>
                  <div className="ping-verdict">✓ {dhcp.pc.name} got {dhcp.result.ip}</div>
                  <div style={{ fontSize: 13, marginTop: 6 }}>
                    {dhcp.result.subnet} · VLAN {dhcp.result.vlan_id} · gateway {dhcp.result.gateway}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      <PingTest />

      {config && (
        <div className="card" ref={panels.config} style={{ scrollMarginTop: 16 }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <h3 style={{ margin: 0 }}>{config.name} — last configuration</h3>
            <button onClick={() => setConfig(null)}>Close</button>
          </div>
          <pre className="config">{config.text}</pre>
        </div>
      )}
    </div>
  )
}
