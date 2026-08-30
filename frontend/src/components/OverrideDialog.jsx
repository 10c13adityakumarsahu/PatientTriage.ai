/** OverrideDialog — 5-step clinician override flow
 *  1. Confirm intent  2. Select priority  3. Choose reason  4. Add note  5. Confirm → logged
 */
import { useState } from 'react'
import { createOverride } from '../api'
import PriorityBadge from './PriorityBadge'
import { CheckCircle, X } from 'lucide-react'

const PRIORITIES = [
  { code: 'P1', label: 'Immediate' },
  { code: 'P2', label: 'Very Urgent' },
  { code: 'P3', label: 'Urgent' },
  { code: 'P4', label: 'Less Urgent' },
  { code: 'P5', label: 'Non-Urgent' },
]

const REASONS = [
  { value: 'clinical_deterioration', label: 'Clinical Deterioration Observed' },
  { value: 'clinical_improvement', label: 'Clinical Improvement Observed' },
  { value: 'additional_history', label: 'Additional History Available' },
  { value: 'resource_constraint', label: 'Resource Constraint' },
  { value: 'patient_preference', label: 'Patient Preference' },
  { value: 'other', label: 'Other Clinical Judgment' },
]

export default function OverrideDialog({ patient, currentAssessment, onClose, onDone }) {
  const [step, setStep] = useState(1)
  const [selectedPriority, setSelectedPriority] = useState(null)
  const [reason, setReason] = useState('')
  const [note, setNote] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleConfirm() {
    if (!selectedPriority || !reason) return
    setLoading(true)
    setError(null)
    try {
      await createOverride(patient.id, {
        override_priority: selectedPriority,
        reason_code: reason,
        note,
        clinician_id: 'clinician-1',
      })
      setStep(5)
      onDone && setTimeout(onDone, 1800)
    } catch (e) {
      setError(e?.response?.data?.error || 'Override failed. Please retry.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="dialog-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="dialog-box" role="dialog" aria-modal="true" aria-label="Clinician Override">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--sp-2)' }}>
          <h2 className="dialog-title">Clinician Override</h2>
          <button className="btn btn-ghost btn-icon" onClick={onClose} aria-label="Close"><X size={16} /></button>
        </div>

        {step < 5 && (
          <>
            <p className="dialog-subtitle">
              AI recommended <strong><PriorityBadge priority={currentAssessment?.priority} /></strong> for&nbsp;
              <strong>{patient?.chief_complaint}</strong>. Override this recommendation.
            </p>
            <div className="step-indicator">
              {[1,2,3,4].map(s => (
                <div key={s} className={`step-dot ${s === step ? 'active' : s < step ? 'done' : ''}`} />
              ))}
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginLeft: 'var(--sp-2)' }}>Step {step} of 4</span>
            </div>
          </>
        )}

        {/* Step 1 — Intent */}
        {step === 1 && (
          <div>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 'var(--sp-6)' }}>
              You are about to override the AI triage recommendation. Your decision will be logged in the audit trail and takes precedence over AI output.
            </p>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: 'var(--sp-6)', padding: 'var(--sp-3)', background: 'var(--bg-elevated)', borderRadius: 'var(--r-md)', border: '1px solid var(--p3-border)' }}>
              AI recommends. You decide. All overrides are auditable.
            </p>
            <div style={{ display: 'flex', gap: 'var(--sp-3)', justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
              <button className="btn btn-warning" onClick={() => setStep(2)}>Continue</button>
            </div>
          </div>
        )}

        {/* Step 2 — Select Priority */}
        {step === 2 && (
          <div>
            <div className="form-group">
              <label className="form-label">Select new priority</label>
              <div className="priority-selector">
                {PRIORITIES.map(p => (
                  <div
                    key={p.code}
                    className={`priority-option ${p.code} ${selectedPriority === p.code ? 'selected' : ''}`}
                    onClick={() => setSelectedPriority(p.code)}
                    role="radio"
                    aria-checked={selectedPriority === p.code}
                    tabIndex={0}
                    onKeyDown={e => e.key === 'Enter' && setSelectedPriority(p.code)}
                  >
                    <span className="prio-code">{p.code}</span>
                    <span className="prio-label">{p.label}</span>
                  </div>
                ))}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 'var(--sp-3)', justifyContent: 'flex-end', marginTop: 'var(--sp-4)' }}>
              <button className="btn btn-ghost" onClick={() => setStep(1)}>Back</button>
              <button className="btn btn-primary" onClick={() => setStep(3)} disabled={!selectedPriority}>Next</button>
            </div>
          </div>
        )}

        {/* Step 3 — Reason */}
        {step === 3 && (
          <div>
            <div className="form-group">
              <label className="form-label" htmlFor="override-reason">Reason for override</label>
              <select
                id="override-reason"
                className="form-select"
                value={reason}
                onChange={e => setReason(e.target.value)}
              >
                <option value="">Select reason…</option>
                {REASONS.map(r => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>
            <div style={{ display: 'flex', gap: 'var(--sp-3)', justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => setStep(2)}>Back</button>
              <button className="btn btn-primary" onClick={() => setStep(4)} disabled={!reason}>Next</button>
            </div>
          </div>
        )}

        {/* Step 4 — Note + Confirm */}
        {step === 4 && (
          <div>
            <div className="form-group">
              <label className="form-label" htmlFor="override-note">Clinical note (optional)</label>
              <textarea
                id="override-note"
                className="form-textarea"
                value={note}
                onChange={e => setNote(e.target.value)}
                placeholder="Add any relevant clinical observations…"
              />
            </div>
            <div style={{ padding: 'var(--sp-3)', background: 'var(--bg-elevated)', borderRadius: 'var(--r-md)', marginBottom: 'var(--sp-4)', fontSize: '0.8rem' }}>
              <div style={{ display: 'flex', gap: 'var(--sp-4)', alignItems: 'center' }}>
                <span style={{ color: 'var(--text-muted)' }}>AI recommendation:</span>
                <PriorityBadge priority={currentAssessment?.priority} />
                <span style={{ color: 'var(--text-muted)' }}>→ Your override:</span>
                <PriorityBadge priority={selectedPriority} />
              </div>
              <div style={{ color: 'var(--text-muted)', marginTop: 'var(--sp-2)', fontSize: '0.75rem' }}>
                Reason: {REASONS.find(r => r.value === reason)?.label}
              </div>
            </div>
            {error && <p style={{ color: 'var(--p1)', fontSize: '0.8rem', marginBottom: 'var(--sp-3)' }}>{error}</p>}
            <div style={{ display: 'flex', gap: 'var(--sp-3)', justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => setStep(3)}>Back</button>
              <button className="btn btn-danger" onClick={handleConfirm} disabled={loading}>
                {loading ? 'Saving…' : 'Confirm Override'}
              </button>
            </div>
          </div>
        )}

        {/* Step 5 — Confirmed */}
        {step === 5 && (
          <div className="success-box">
            <CheckCircle size={20} />
            Override saved. Priority updated to <strong>{selectedPriority}</strong>. Logged in audit trail.
          </div>
        )}
      </div>
    </div>
  )
}
