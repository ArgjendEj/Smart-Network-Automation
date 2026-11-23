// controls + outcome of the packet (envelope) test; the envelope itself travels
// on the map above (PacketEnvelope.jsx)
export default function PacketTest({
  devices, source, target, onSource, onTarget, onSend, picking, onPickToggle, onReset, running, result, error,
}) {
  // a switch has no IP, so it can be crossed but not pinged
  const options = devices.filter((d) => d.type !== 'switch')
    .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }))
  const list = options.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h3 style={{ margin: 0 }}>✉️ Packet test</h3>
        <div className="row">
          <button onClick={onReset} title="Clear for the next packet">🔄 Refresh</button>
          <button disabled={running} onClick={onPickToggle}>
            {picking ? 'Cancel' : '🖱️ Pick on the map'}
          </button>
        </div>
      </div>

      <div className="row" style={{ gap: 10, alignItems: 'flex-end', marginTop: 10 }}>
        <div className="field">
          <label className="muted">Source</label>
          <select aria-label="Packet source" value={source} disabled={running}
            onChange={(e) => onSource(e.target.value)} style={{ width: 180 }}>
            <option value="">Choose…</option>{list}
          </select>
        </div>
        <div className="field">
          <label className="muted">Destination</label>
          <select aria-label="Packet destination" value={target} disabled={running}
            onChange={(e) => onTarget(e.target.value)} style={{ width: 180 }}>
            <option value="">Choose…</option>{list}
          </select>
        </div>
        <div className="field">
          <button className="primary" style={{ padding: '9px 22px' }} onClick={onSend}
            disabled={running || !source || !target || source === target}>
            {running ? 'Sending…' : 'Send ✉'}
          </button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {result && !running && (
        <div className={`ping-result ${result.ok ? 'ping-ok' : 'ping-fail'}`} style={{ marginTop: 0 }}>
          <div className="ping-verdict">{result.ok ? '✓  Successful' : '✕  Failed'}</div>
          <div className="ping-path" style={{ flexWrap: 'wrap' }}>
            <span className="ping-node">{result.source}</span>
            <span className="ping-arrow">──▶</span>
            <span className="ping-node">{result.target}</span>
          </div>
          {result.hops.length > 0 && (
            <div className="muted" style={{ fontSize: 12 }}>
              {result.ok ? 'Path' : 'Got as far as'}: {result.path.join(' → ')}
            </div>
          )}
          <div style={{ fontSize: 13, marginTop: 6 }}>{result.reason}</div>
        </div>
      )}
    </div>
  )
}
