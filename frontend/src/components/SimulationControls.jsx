/** SimulationControls — bottom bar with all demo controls */
import { useState, useEffect } from 'react'
import { seedSimulation, tickSimulation, triggerDeterioration, triggerSurge, resetSimulation, getSimStatus, intakeNextSimulation } from '../api'
import { useStore } from '../store'
import { Play, RefreshCw, Zap, TrendingDown, Clock, UserPlus } from 'lucide-react'

export default function SimulationControls({ onRefresh, selectedPatientId }) {
  const [loading, setLoading] = useState(null)
  const surgeActive = useStore(s => s.surgeActive)
  const [currentStage, setCurrentStage] = useState('wait_reassessment')

  useEffect(() => {
    async function init() {
      try {
        const res = await getSimStatus()
        setCurrentStage(res.data.current_stage || 'wait_reassessment')
      } catch (e) {
        // ignore
      }
    }
    init()
  }, [])

  async function run(key, fn) {
    setLoading(key)
    try {
      const res = await fn()
      if (res && res.data && res.data.next_stage) {
        setCurrentStage(res.data.next_stage)
      } else {
        // reload status
        const statusRes = await getSimStatus()
        setCurrentStage(statusRes.data.current_stage || 'wait_reassessment')
      }
      onRefresh && onRefresh()
    } catch (e) {
      alert(e?.response?.data?.error || e.message || 'Error')
    } finally {
      setLoading(null)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '12px', background: 'var(--bg-hover)', borderRadius: 'var(--r-md)', border: '1px solid var(--border)', marginTop: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)' }}>Simulation Controls</span>
        <span className="badge" style={{ 
          fontSize: '0.66rem', 
          background: 'rgba(124, 58, 237, 0.1)', 
          color: 'var(--accent)', 
          border: '1px solid rgba(124, 58, 237, 0.2)',
          padding: '2px 6px',
          borderRadius: '4px',
          fontWeight: 700
        }}>
          Stage: {
            currentStage === 'wait_reassessment' ? 'Triage Reassess' :
            currentStage === 'io_completion' ? 'Diagnostic I/O' :
            currentStage === 'priority_aging' ? 'Dynamic Aging' :
            'Clinician Allocation'
          }
        </span>
      </div>
      
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
        <button
          id="btn-seed"
          className="btn btn-ghost btn-sm"
          onClick={() => run('seed', seedSimulation)}
          disabled={!!loading}
          style={{ fontSize: '0.72rem', padding: '6px', display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}
          title="Load initial baseline scenario (3 patients)"
        >
          <Play size={12} />
          {loading === 'seed' ? 'Loading…' : 'Start'}
        </button>

        <button
          id="btn-tick-5"
          className="btn btn-ghost btn-sm"
          onClick={() => run('tick5', () => tickSimulation({ minutes: 5, step: false }))}
          disabled={!!loading}
          style={{ fontSize: '0.72rem', padding: '6px', display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}
          title="Advance 5 minutes (Full scheduler tick)"
        >
          <Clock size={12} />
          {loading === 'tick5' ? '…' : '+5 min'}
        </button>

        <button
          id="btn-intake-next"
          className="btn btn-outline-primary btn-sm"
          onClick={() => run('intake_next', intakeNextSimulation)}
          disabled={!!loading}
          style={{ fontSize: '0.72rem', padding: '6px', display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center', gridColumn: 'span 2' }}
          title="Simulate sequential intake walk-in of next synthetic patient"
        >
          <UserPlus size={12} style={{ color: 'var(--accent)' }} />
          {loading === 'intake_next' ? 'Admitting…' : 'Next Patient Intake'}
        </button>

        <button
          id="btn-deteriorate"
          className="btn btn-warning btn-sm"
          onClick={() => {
            if (!selectedPatientId) { alert('Select a patient first from the board.'); return }
            run('det', () => triggerDeterioration({ patient_id: selectedPatientId }))
          }}
          disabled={!!loading || !selectedPatientId}
          style={{ fontSize: '0.72rem', padding: '6px', display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center', gridColumn: 'span 2' }}
          title="Simulate patient deterioration"
        >
          <TrendingDown size={12} />
          {loading === 'det' ? '…' : 'Deteriorate Selected'}
        </button>

        <button
          id="btn-surge"
          className={`btn btn-sm ${surgeActive ? 'btn-danger' : 'btn-warning'}`}
          onClick={() => run('surge', triggerSurge)}
          disabled={!!loading}
          style={{ fontSize: '0.72rem', padding: '6px', display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center', gridColumn: 'span 2' }}
          title="Activate 3× surge"
        >
          <Zap size={12} />
          {loading === 'surge' ? '…' : surgeActive ? 'Surge Active' : '3× Surge'}
        </button>

        <button
          id="btn-reset"
          className="btn btn-ghost btn-sm"
          onClick={() => {
            if (!confirm('Reset all simulation data?')) return
            run('reset', resetSimulation)
          }}
          disabled={!!loading}
          style={{ fontSize: '0.72rem', padding: '6px', display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center', gridColumn: 'span 2', color: 'var(--p1)' }}
          title="Reset simulation"
        >
          <RefreshCw size={12} />
          {loading === 'reset' ? '…' : 'Reset Data'}
        </button>
      </div>
    </div>
  )
}
