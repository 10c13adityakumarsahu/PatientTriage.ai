/** ResourceCapacityCard — shows bed/room utilisation bars */
export default function ResourceCapacityCard({ resources = [] }) {
  if (!resources.length) return (
    <div className="empty-state" style={{ padding: 'var(--sp-4)' }}>No resource data</div>
  )

  function getFillClass(pct) {
    if (pct >= 100) return 'full'
    if (pct >= 80) return 'high'
    if (pct >= 60) return 'medium'
    return ''
  }

  const TYPE_LABEL = {
    resus_bay: 'Resus',
    treatment_room: 'Treatment',
    fast_track_room: 'Fast Track',
    observation_bed: 'Observation',
  }

  // Group by type
  const grouped = {}
  for (const r of resources) {
    const t = r.resource_type
    if (!grouped[t]) grouped[t] = { cap: 0, occ: 0, name: TYPE_LABEL[t] || t }
    grouped[t].cap += r.capacity
    grouped[t].occ += r.occupied
  }

  return (
    <div className="resource-grid">
      {Object.entries(grouped).map(([type, g]) => {
        const pct = g.cap > 0 ? Math.round(g.occ / g.cap * 100) : 0
        return (
          <div key={type} className="resource-card">
            <div className="resource-name">{g.name}</div>
            <div className="capacity-bar">
              <div
                className={`capacity-fill ${getFillClass(pct)}`}
                style={{ width: `${Math.min(pct, 100)}%` }}
              />
            </div>
            <div className="capacity-text">
              <span>{g.occ}/{g.cap} occupied</span>
              <span style={{ color: pct >= 80 ? 'var(--p2)' : 'var(--text-muted)' }}>{pct}%</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
