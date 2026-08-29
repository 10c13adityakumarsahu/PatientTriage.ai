/** ConfidenceBadge — shows confidence % with high/medium/low label */
export default function ConfidenceBadge({ confidence, label }) {
  const pct = confidence != null ? Math.round(confidence * 100) : null
  const lvl = label || (pct >= 80 ? 'high' : pct >= 60 ? 'medium' : 'low')

  if (pct == null) return null
  return (
    <span className={`confidence-badge ${lvl}`} title={`Confidence: ${pct}%`}>
      {pct}%
    </span>
  )
}
