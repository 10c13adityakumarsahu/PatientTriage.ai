import { getCareSequence } from '../workflow'

function stepColor(idx, activeIndex) {
  if (idx < activeIndex) return 'var(--p5)'
  if (idx === activeIndex) {
    if (activeIndex === 0) return 'var(--p1)'
    if (activeIndex === 1) return '#3b82f6'
    if (activeIndex === 2) return 'var(--p2)'
    return 'var(--p5)'
  }
  return 'inherit'
}

/** Compact pathway used on the live queue board. */
export function CareSequenceCompact({ patient, latestAssessment }) {
  const seq = getCareSequence(patient, latestAssessment)
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
        fontSize: '0.7rem',
        color: 'var(--text-muted)',
        marginTop: '6px',
        flexWrap: 'wrap',
      }}
      title={seq.steps.map((s, i) => `${i + 1}. ${s.label}: ${s.desc}`).join(' → ')}
    >
      {seq.steps.map((step, idx) => (
        <span key={step.key} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
          {idx > 0 && <span>→</span>}
          <span
            style={{
              color: stepColor(idx, seq.activeIndex),
              fontWeight: idx === seq.activeIndex ? 700 : 500,
            }}
          >
            {step.label}
          </span>
        </span>
      ))}
    </div>
  )
}

/** Full pathway used on the patient record. */
export function CareSequenceFull({ patient, latestAssessment }) {
  const seq = getCareSequence(patient, latestAssessment)

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '20px 24px',
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--r-md)',
        marginBottom: '24px',
        boxShadow: 'var(--shadow-sm)',
      }}
    >
      {seq.steps.map((step, idx) => {
        const isActive = idx === seq.activeIndex
        const isCompleted = idx < seq.activeIndex
        const color = isCompleted ? 'var(--p5)' : isActive ? 'var(--accent)' : 'var(--text-muted)'
        const lineBg = idx < seq.activeIndex ? 'var(--p5)' : 'var(--border)'

        return (
          <div key={step.key} style={{ display: 'flex', alignItems: 'center', flex: idx < seq.steps.length - 1 ? 1 : 'none' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', position: 'relative', minWidth: '108px' }}>
              <div
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '50%',
                  background: isCompleted ? 'var(--p5)' : isActive ? 'var(--accent)' : 'transparent',
                  border: `2px solid ${isActive ? 'var(--accent)' : isCompleted ? 'var(--p5)' : 'var(--border)'}`,
                  color: isCompleted || isActive ? '#fff' : 'var(--text-muted)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  marginBottom: '6px',
                  boxShadow: isActive ? '0 0 0 4px rgba(124, 58, 237, 0.15)' : 'none',
                }}
              >
                {isCompleted ? '✓' : idx + 1}
              </div>
              <span style={{ fontSize: '0.82rem', fontWeight: isActive || isCompleted ? 700 : 500, color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                {step.label}
              </span>
              <span style={{ fontSize: '0.68rem', color: color, marginTop: '2px' }}>
                {step.desc}
              </span>
            </div>
            {idx < seq.steps.length - 1 && (
              <div style={{ height: '2px', background: lineBg, flex: 1, margin: '0 12px', marginTop: '-24px' }} />
            )}
          </div>
        )
      })}
    </div>
  )
}
