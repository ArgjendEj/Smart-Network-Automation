export default function DeploymentStatus({ results }) {
  if (!results?.length) return null
  return (
    <div className="grid" style={{ gap: 12 }}>
      {results.map((r) => (
        <div className="card" key={r.device_id}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <strong>{r.device_name}</strong>
            {r.error
              ? <span className="pill offline">deploy failed</span>
              : r.deployed
                ? <span className="pill online">deployed</span>
                : <span className="pill unknown">generated (not deployed)</span>}
          </div>
          {r.error && <p className="error" style={{ fontSize: 13 }}>{r.error}</p>}
          <pre className="config">{r.config}</pre>
          {r.deploy_output && (
            <details>
              <summary className="muted">device session output</summary>
              <pre className="config">{r.deploy_output}</pre>
            </details>
          )}
        </div>
      ))}
    </div>
  )
}
