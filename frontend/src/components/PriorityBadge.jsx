/** PriorityBadge — P1-P5 with colour, text label. Uses explicit text, not colour only. */
const LABELS = {
  P1: 'P1 · Immediate',
  P2: 'P2 · Very Urgent',
  P3: 'P3 · Urgent',
  P4: 'P4 · Less Urgent',
  P5: 'P5 · Non-Urgent',
}

export default function PriorityBadge({ priority, showLabel = false, className = '' }) {
  if (!priority) return <span className={`priority-badge unknown ${className}`}>—</span>
  return (
    <span
      className={`priority-badge ${priority} ${className}`}
      aria-label={LABELS[priority] || priority}
      title={LABELS[priority] || priority}
    >
      {showLabel ? LABELS[priority] : priority}
    </span>
  )
}
