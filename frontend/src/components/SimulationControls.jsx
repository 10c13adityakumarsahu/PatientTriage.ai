/** SimulationControls — bottom bar with all demo controls */
import { useState } from 'react'
import { seedSimulation, tickSimulation, triggerDeterioration, triggerSurge, resetSimulation } from '../api'
import { useStore } from '../store'
import { Play, RefreshCw, Zap, TrendingDown, Clock } from 'lucide-react'

export default function SimulationControls({ onRefresh, selectedPatientId }) {
  const [loading, setLoading] = useState(null)
  const surgeActive = useStore(s => s.surgeActive)

  async function run(key, fn) {
    setLoading(key)
    try {
      await fn()
      onRefresh && onRefresh()
    } catch (e) {
      alert(e?.response?.data?.error || e.message || 'Error')
    } finally {
      setLoading(null)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '12px', background: 'var(--bg-hover)', borderRadius: 'var(--r-md)', border: '1px solid var(--border)', marginTop: '8px' }}>
      <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)' }}>Simulation Controls</span>
      
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
        <button
          id="btn-seed"
          className="btn btn-ghost btn-sm"
          onClick={() => run('seed', seedSimulation)}
          disabled={!!loading}
          style={{ fontSize: '0.72rem', padding: '6px', display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}
          title="Load 20 synthetic patients"
        >
          <Play size={12} />
          {loading === 'seed' ? 'Loading…' : 'Start'}
        </button>

        <button
          id="btn-tick-5"
          className="btn btn-ghost btn-sm"
          onClick={() => run('tick5', () => tickSimulation({ minutes: 5 }))}
          disabled={!!loading}
          style={{ fontSize: '0.72rem', padding: '6px', display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}
          title="Advance 5 minutes"
        >
          <Clock size={12} />
          {loading === 'tick5' ? '…' : '+5 min'}
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
