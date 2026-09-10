import { useCallback, useEffect, useMemo, useRef } from 'react'
import ReactFlow, {
  Background, Controls, MiniMap, addEdge, useEdgesState, useNodesState,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { TopologyAPI } from '../services/api'
import ConnectionLine from './ConnectionLine'
import DeviceNode from './DeviceNode'

function toNode(n) {
  return {
    id: String(n.id),
    type: 'device',
    position: { x: n.x, y: n.y },
    data: { name: n.name, type: n.type, status: n.status, hostname: n.hostname },
  }
}

const shortHandle = (iface) => (iface || '')
  .replace('GigabitEthernet', 'Gi').replace('FastEthernet', 'Fa') || null

function toEdge(e) {
  return {
    id: String(e.id),
    source: String(e.source),
    target: String(e.target),
    sourceHandle: shortHandle(e.source_interface),
    targetHandle: shortHandle(e.target_interface),
    type: 'connection',
    data: {
      link_type: e.link_type,
      source_interface: e.source_interface,
      target_interface: e.target_interface,
    },
  }
}

export default function TopologyCanvas({ onGraphChange }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const edgeTypes = useMemo(() => ({ connection: ConnectionLine }), [])
  const nodeTypes = useMemo(() => ({ device: DeviceNode }), [])

  const reloadRef = useRef(null)

  const removeById = useCallback(async (edgeId, meta = {}) => {
    const a = meta.a || '?'
    const b = meta.b || '?'
    if (!confirm(`Delete this cable?\n${a}  —  ${b}`)) return
    try {
      await TopologyAPI.removeLink(Number(edgeId))
      setEdges((eds) => eds.filter((x) => x.id !== String(edgeId)))
      reloadRef.current?.()
    } catch (e) {
      alert(e.response?.data?.detail || 'Could not delete the cable')
    }
  }, [setEdges])

  const reload = useCallback(() => {
    TopologyAPI.graph().then((r) => {
      setNodes(r.data.nodes.map(toNode))
      setEdges(r.data.edges.map((e) => {
        const edge = toEdge(e)
        edge.data.onDelete = () =>
          removeById(edge.id, { a: e.source_interface, b: e.target_interface })
        return edge
      }))
      onGraphChange?.(r.data)
    })
  }, [setNodes, setEdges, onGraphChange, removeById])

  reloadRef.current = reload
  useEffect(() => { reload() }, [reload])

  const expand = (h) => {
    if (!h) return ''
    if (h.startsWith('Gi')) return 'GigabitEthernet' + h.slice(2)
    if (h.startsWith('Fa')) return 'FastEthernet' + h.slice(2)
    return h
  }

  const onConnect = useCallback(async (params) => {
    // the port you dragged from / to is taken from the handle you used
    const a_interface = expand(params.sourceHandle) ||
      prompt('Source interface', 'GigabitEthernet0/0') || ''
    if (a_interface === null) return
    const b_interface = expand(params.targetHandle) ||
      prompt('Target interface', 'GigabitEthernet0/1') || ''
    const link_type = confirm('Trunk link? (OK = trunk, Cancel = access)') ? 'trunk' : 'access'
    try {
      await TopologyAPI.addLink({
        a_device_id: Number(params.source), b_device_id: Number(params.target),
        a_interface, b_interface, link_type,
      })
      setEdges((eds) => addEdge(
        { ...params, type: 'connection',
          data: { link_type, source_interface: a_interface, target_interface: b_interface } },
        eds,
      ))
      reload()
    } catch (e) {
      alert(e.response?.data?.detail || 'Could not create link')
    }
  }, [setEdges, reload])

  const onNodeDragStop = useCallback((_, node) => {
    TopologyAPI.move(Number(node.id), node.position.x, node.position.y)
  }, [])

  const onEdgesDelete = useCallback((deleted) => {
    deleted.forEach((e) => TopologyAPI.removeLink(Number(e.id)).catch(() => {}))
  }, [])

  const onEdgeDoubleClick = useCallback((_, edge) => {
    removeById(edge.id, {
      a: edge.data?.source_interface, b: edge.data?.target_interface,
    })
  }, [removeById])

  return (
    <div style={{ height: '70vh', border: '1px solid #334155', borderRadius: 12 }}>
      <ReactFlow
        nodes={nodes} edges={edges}
        onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
        onConnect={onConnect} onNodeDragStop={onNodeDragStop} onEdgesDelete={onEdgesDelete}
        onEdgeDoubleClick={onEdgeDoubleClick}
        edgeTypes={edgeTypes} nodeTypes={nodeTypes} connectionMode="loose"
        fitView deleteKeyCode={['Backspace', 'Delete']}
      >
        <Background color="#334155" gap={18} />
        <MiniMap pannable zoomable style={{ background: '#0f172a' }} />
        <Controls />
      </ReactFlow>
    </div>
  )
}
