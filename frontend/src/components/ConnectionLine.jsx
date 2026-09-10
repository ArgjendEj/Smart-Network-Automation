import { BaseEdge, EdgeLabelRenderer, getBezierPath } from 'reactflow'

/** Custom topology edge: colours trunk vs access links, shows a label,
 *  and offers a ✕ button (also: double-click the line to delete). */
export default function ConnectionLine({
  id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition,
  data, markerEnd, selected,
}) {
  const [path, labelX, labelY] = getBezierPath({
    sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition,
  })
  const trunk = data?.link_type === 'trunk'
  return (
    <>
      <BaseEdge
        id={id} path={path} markerEnd={markerEnd} interactionWidth={24}
        style={{
          stroke: selected ? '#ef4444' : trunk ? '#f59e0b' : '#38bdf8',
          strokeWidth: selected ? 3 : 2,
        }}
      />
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%,-50%) translate(${labelX}px,${labelY}px)`,
            background: '#1e293b', border: '1px solid #334155', borderRadius: 6,
            fontSize: 10, padding: '1px 6px', color: '#e2e8f0', pointerEvents: 'all',
            display: 'flex', alignItems: 'center', gap: 4,
          }}
        >
          <span>{data?.source_interface || '?'} — {data?.target_interface || '?'}{trunk ? ' (trunk)' : ''}</span>
          <button
            title="Delete cable"
            onClick={(e) => { e.stopPropagation(); data?.onDelete?.(id) }}
            style={{
              padding: '0 4px', fontSize: 11, lineHeight: 1.4, border: '1px solid #ef4444',
              background: 'transparent', color: '#ef4444', borderRadius: 4, cursor: 'pointer',
            }}
          >
            ✕
          </button>
        </div>
      </EdgeLabelRenderer>
    </>
  )
}
