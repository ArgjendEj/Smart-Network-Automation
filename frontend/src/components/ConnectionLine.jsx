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
          stroke: selected ? 'var(--red)' : trunk ? 'var(--cable-trunk)' : 'var(--cable-access)',
          strokeWidth: selected ? 3 : 2,
        }}
      />
      <EdgeLabelRenderer>
        <div
          className="cable-label"
          style={{
            position: 'absolute',
            transform: `translate(-50%,-50%) translate(${labelX}px,${labelY}px)`,
            background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 6,
            fontSize: 10, padding: '1px 6px', color: 'var(--text)', pointerEvents: 'all',
            display: 'flex', alignItems: 'center', gap: 4,
          }}
        >
          <span>{data?.source_interface || '?'} — {data?.target_interface || '?'}{trunk ? ' (trunk)' : ''}</span>
          <button
            title="Delete cable"
            onClick={(e) => { e.stopPropagation(); data?.onDelete?.(id) }}
            style={{
              padding: '0 4px', fontSize: 11, lineHeight: 1.4, border: '1px solid var(--red)',
              background: 'transparent', color: 'var(--red)', borderRadius: 4, cursor: 'pointer',
            }}
          >
            ✕
          </button>
        </div>
      </EdgeLabelRenderer>
    </>
  )
}
