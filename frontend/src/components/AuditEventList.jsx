/** AuditEventList — append-only audit log table */
import { useEffect, useState } from 'react'
import { getAudit } from '../api'

const EVENT_LABELS = {
  patient_created: 'Patient registered',
  assessment_generated: 'AI assessment generated',
  priority_changed: 'Priority changed',
  vitals_recorded: 'Vitals recorded',
  alert_acknowledged: 'Alert acknowledged',
  recommendation_overridden: 'Clinician override',
  route_changed: 'Route changed',
  reassessment_triggered: 'Reassessment triggered',
  deterioration_triggered: 'Deterioration simulated',
  simulation_patient_created: 'Simulation patient created',
  simulation_reset: 'Simulation reset',
  surge_activated: 'Surge activated',
}

function formatTime(dt) {
  if (!dt) return ''
  return new Date(dt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export default function AuditEventList({ patientId, limit = 50 }) {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    getAudit(patientId ? { patient_id: patientId } : {})
      .then(r => setEvents(r.data.slice(0, limit)))
      .catch(() => { })
      .finally(() => setLoading(false))
  }, [patientId])

  if (loading) return <div className="loading-wrap">Loading Audit Logs…</div>
  if (!events.length) return <div className="empty-state">No audit events yet.</div>

  return (
    <div className="audit-list">
      {events.map(ev => (
        <div key={ev.id} className="audit-item">
          <span className="audit-time">{formatTime(ev.created_at)}</span>
          <div>
            <div className="audit-event">{EVENT_LABELS[ev.event_type] || ev.event_type.replace(/_/g, ' ')}</div>
            <div className="audit-detail">
              {ev.new_state && ev.event_type === 'priority_changed' && (
                <>{ev.old_state?.priority} → {ev.new_state?.priority}
                  {ev.confidence != null && <> · confidence {Math.round(ev.confidence * 100)}%</>}
                </>
              )}
              {ev.new_state && ev.event_type === 'recommendation_overridden' && (
                <>{ev.old_state?.priority} → {ev.new_state?.priority} · {ev.new_state?.reason}</>
              )}
              {ev.trigger && <> · trigger: {ev.trigger}</>}
            </div>
          </div>
          <span className={`audit-actor ${ev.actor_type}`}>{ev.actor_type}</span>
        </div>
      ))}
    </div>
  )
}
