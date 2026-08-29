/** AlertCard — shows a single alert with type-appropriate styling */
import { AlertTriangle, Activity, Clock, BarChart2, Info } from 'lucide-react'
import { acknowledgeAlert } from '../api'
import { useStore } from '../store'

const TYPE_ICONS = {
  deterioration:   Activity,
  wait_threshold:  Clock,
  low_confidence:  BarChart2,
  conflicting_data:AlertTriangle,
  capacity_pressure:BarChart2,
  escalation:      AlertTriangle,
}

function timeAgo(dt) {
  if (!dt) return ''
  const diff = Math.floor((Date.now() - new Date(dt)) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`
  return `${Math.floor(diff/3600)}h ago`
}

export default function AlertCard({ alert, onAcknowledge }) {
  const Icon = TYPE_ICONS[alert.alert_type] || Info
  const sev = alert.severity || 'warning'

  async function handleAck() {
    try {
      await acknowledgeAlert(alert.id, { acknowledged_by: 'clinician-1' })
      onAcknowledge && onAcknowledge(alert.id)
    } catch {}
  }

  return (
    <div className={`alert-card ${sev}`} role="alert">
      <div className="alert-card-header">
        <span className={`alert-title ${sev}`} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Icon size={13} />
          {alert.title}
        </span>
        <span className="alert-time">{timeAgo(alert.created_at)}</span>
      </div>
      <p className="alert-message">{alert.message}</p>
      {!alert.acknowledged_at && (
        <button className="btn btn-ghost btn-sm" onClick={handleAck} style={{ alignSelf: 'flex-start', marginTop: 4 }}>
          Acknowledge
        </button>
      )}
    </div>
  )
}
