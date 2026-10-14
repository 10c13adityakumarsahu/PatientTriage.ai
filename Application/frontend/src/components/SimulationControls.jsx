/** SimulationControls — bottom bar with all demo controls */
import { useState, useEffect } from 'react'
import { seedSimulation, tickSimulation, triggerDeterioration, triggerSurge, resetSimulation, getSimStatus, intakeNextSimulation, getNextPatientData } from '../api'
import { useStore } from '../store'
import { Play, RefreshCw, Zap, TrendingDown, Clock, UserPlus } from 'lucide-react'

export default function SimulationControls({ 
  onRefresh, 
  selectedPatientId, 
  onSimulateIntake, 
  onSeedSuccess,
  currentStage,
  setCurrentStage,
  isPlaying,
  setIsPlaying,
  onStepStage
}) {
  const [loading, setLoading] = useState(null)
  const surgeActive = useStore(s => s.surgeActive)

  async function run(key, fn) {
    setLoading(key)
    try {
      const res = await fn()
      if (res && res.data && res.data.next_stage) {
        setCurrentStage && setCurrentStage(res.data.next_stage)
      } else {
        // reload status
        const statusRes = await getSimStatus()
        setCurrentStage && setCurrentStage(statusRes.data.current_stage || 'wait_reassessment')
      }
      if (key === 'seed' && onSeedSuccess) {
        onSeedSuccess()
      }
      if (key === 'reset' && setIsPlaying) {
        setIsPlaying(false)
      }
      onRefresh && onRefresh()
    } catch (e) {
      alert(e?.response?.data?.error || e.message || 'Error')
    } finally {
      setLoading(null)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '12px', background: 'var(--bg-card)', borderRadius: 'var(--r-md)', border: '1px solid var(--border)', marginTop: '8px', boxShadow: 'var(--shadow-sm)' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', borderBottom: '1px solid var(--border)', paddingBottom: '8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)' }}>Simulation</span>
          <span className="badge" style={{
            fontSize: '0.62rem',
            background: isPlaying ? 'rgba(16, 185, 129, 0.1)' : 'rgba(124, 58, 237, 0.1)',
            color: isPlaying ? 'var(--p5)' : 'var(--accent)',
            border: '1px solid rgba(124, 58, 237, 0.2)',
            padding: '2px 6px',
            borderRadius: '4px',
            fontWeight: 700,
            whiteSpace: 'nowrap'
          }}>
            {isPlaying ? 'Auto-Play Active' : 'Normal Workspace'}
          </span>
        </div>
      </div>

      {/* Mode Switcher Toggle Button */}
      <button
        id="btn-mode-toggle"
        className={`btn btn-sm ${isPlaying ? 'btn-danger' : 'btn-success'}`}
        onClick={() => setIsPlaying(!isPlaying)}
        disabled={!!loading}
        style={{ width: '100%', fontSize: '0.76rem', padding: '8px', display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'center', fontWeight: 700 }}
      >
        <Zap size={14} />
        {isPlaying ? 'Stop Auto-Play' : 'Start Auto-Play'}
      </button>

      {/* Visual Pipeline Cursor Stepper (Vertical Stepper) */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '4px' }}>
        <label style={{ fontSize: '0.64rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)', letterSpacing: '0.04em' }}>Scheduler Stage Pipeline</label>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', background: 'rgba(0,0,0,0.06)', padding: '8px', borderRadius: '6px', border: '1px solid var(--border)' }}>
          {[
            { key: 'wait_reassessment', label: '1. Triage Reassess', color: 'var(--p1)' },
            { key: 'io_completion', label: '2. Scan Completion', color: '#3b82f6' },
            { key: 'priority_aging', label: '3. Priority Aging', color: 'var(--p2)' },
            { key: 'core_allocation', label: '4. Doctor Allocation', color: 'var(--p5)' }
          ].map((stg) => {
            const isActive = currentStage === stg.key;
            return (
              <div
                key={stg.key}
                id={`step-${stg.key}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '4px 6px',
                  fontSize: '0.72rem',
                  fontWeight: isActive ? 700 : 500,
                  borderRadius: '4px',
                  background: isActive ? 'var(--bg-hover)' : 'transparent',
                  color: isActive ? 'var(--text-primary)' : 'var(--text-muted)',
                  borderLeft: isActive ? `3px solid ${stg.color}` : '3px solid transparent',
                  paddingLeft: isActive ? '6px' : '9px',
                  transition: 'all 0.2s ease'
                }}
              >
                <span style={{ 
                  width: '6px', 
                  height: '6px', 
                  borderRadius: '50%', 
                  background: isActive ? stg.color : 'var(--text-muted)',
                  boxShadow: isActive ? `0 0 8px ${stg.color}` : 'none',
                  display: 'inline-block',
                  flexShrink: 0
                }} />
                <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{stg.label}</span>
              </div>
            );
          })}
        </div>
      </div>

      {!isPlaying && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
          <button
            id="btn-seed"
            className="btn btn-outline-primary btn-sm"
            onClick={() => run('seed', seedSimulation)}
            disabled={!!loading}
            style={{ width: '100%', fontSize: '0.75rem', padding: '8px', display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'center' }}
            title="Load initial baseline scenario (15 patients in Vitals Pending)"
          >
            <Play size={12} />
            Start (15 Patients)
          </button>

          <button
            id="btn-intake-next"
            className="btn btn-outline-primary btn-sm"
            onClick={async () => {
              if (onSimulateIntake) {
                setLoading('intake_next')
                try {
                  const res = await getNextPatientData()
                  if (res.data) {
                    onSimulateIntake(res.data)
                  } else {
                    alert("All synthetic patients have been registered.")
                  }
                } catch (e) {
                  alert("Failed to get next patient data: " + (e?.response?.data?.error || e.message))
                } finally {
                  setLoading(null)
                }
              } else {
                run('intake_next', intakeNextSimulation)
              }
            }}
            disabled={!!loading}
            style={{ width: '100%', fontSize: '0.75rem', padding: '8px', display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'center' }}
          >
            Manual Intake
          </button>

           <button
            id="btn-surge"
            className={`btn btn-sm ${surgeActive ? 'btn-danger' : 'btn-warning'}`}
            onClick={() => run('surge', triggerSurge)}
            disabled={!!loading || surgeActive}
            style={{ width: '100%', fontSize: '0.75rem', padding: '8px', display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'center', cursor: surgeActive ? 'not-allowed' : 'pointer' }}
          >
            {surgeActive ? 'Surge Active' : '3× Surge'}
          </button>

          <button
            id="btn-reset"
            className="btn btn-ghost btn-sm"
            onClick={() => {
              if (!confirm('Reset all simulation data?')) return
              run('reset', resetSimulation)
            }}
            disabled={!!loading}
            style={{ width: '100%', fontSize: '0.72rem', padding: '6px', display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center', color: 'var(--p1)' }}
            title="Reset simulation"
          >
            Reset Data
          </button>
        </div>
      )}
    </div>
  )
}
