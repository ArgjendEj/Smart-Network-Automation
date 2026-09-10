import { useState } from 'react'
import TopologyCanvas from '../components/TopologyCanvas'

export default function Topology() {
  const [graph, setGraph] = useState({ nodes: [], edges: [] })
  return (
    <div className="grid" style={{ gap: 16 }}>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h2 style={{ margin: 0 }}>Network Topology</h2>
        <div className="muted" style={{ fontSize: 13 }}>
          Drag nodes to move · drag port-to-port to add a cable · <b>double-click a cable</b> (or its ✕) to delete
        </div>
      </div>
      <TopologyCanvas onGraphChange={setGraph} />
      <div className="row muted" style={{ fontSize: 13 }}>
        <span>{graph.nodes.length} devices</span>
        <span>·</span>
        <span>{graph.edges.length} links</span>
        <span>·</span>
        <span style={{ color: '#38bdf8' }}>— access</span>
        <span style={{ color: '#f59e0b' }}>— trunk</span>
      </div>
    </div>
  )
}
