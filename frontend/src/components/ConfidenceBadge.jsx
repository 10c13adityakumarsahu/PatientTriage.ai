/**
 * ConfidenceBadge — shows confidence % with an ⓘ icon. Clicking either
 * opens a centered modal detailing the exact calculation breakdown.
 *
 * Props:
 *   confidence       number 0–1
 *   label            'high' | 'medium' | 'low'
 *   breakdown        object  (confidence_breakdown from API)
 *   showOverride     bool    — if true, show Override option in modal
 *   onOverride       fn      — called when Override is clicked from modal
 */
import { useState, useEffect } from 'react'
import { 
  Info, ShieldAlert, AlertTriangle, CheckCircle 
} from 'lucide-react'

export default function ConfidenceBadge({
  confidence,
  label,
  breakdown,
  showOverride = false,
  onOverride,
}) {
  const pct = confidence != null ? Math.round(confidence * 100) : null
  const lvl = label || (pct >= 80 ? 'high' : pct >= 60 ? 'medium' : 'low')
  const [visible, setVisible] = useState(false)

  // Listen for Escape key to close the modal
  useEffect(() => {
    if (!visible) return
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setVisible(false)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [visible])

  if (pct == null) return null

  // Badge color from level
  const badgeColor = lvl === 'high' ? '#15803d' : lvl === 'medium' ? '#ca8a04' : '#b91c1c'

  const components = breakdown?.components || {}
  const compKeys = Object.keys(components)

  const interpretation = breakdown?.interpretation || ''
  const clinicalNote = breakdown?.clinical_note || ''
  const uncertaintyFlags = breakdown?.uncertainty_flags || []

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
      {/* Confidence % badge — clickable to open modal */}
      <span
        className={`confidence-badge ${lvl}`}
        title="Click to view detailed confidence calculation"
        onClick={(e) => {
          e.stopPropagation();
          setVisible(true);
        }}
        style={{
          background: `${badgeColor}18`,
          color: badgeColor,
          border: `1px solid ${badgeColor}40`,
          fontSize: '0.74rem',
          padding: '2px 7px',
          borderRadius: '4px',
          fontWeight: 700,
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          letterSpacing: '0.01em',
          cursor: 'pointer',
        }}
      >
        {pct}%
        {lvl === 'high' && <CheckCircle size={10} />}
        {lvl === 'medium' && <AlertTriangle size={10} />}
        {lvl === 'low' && <ShieldAlert size={10} />}
      </span>

      {/* ⓘ info icon — clickable target for modal */}
      {breakdown && (
        <span
          onClick={(e) => {
            e.stopPropagation();
            setVisible(true);
          }}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            cursor: 'pointer',
            color: 'var(--text-muted)',
            padding: '3px',
            borderRadius: '50%',
            transition: 'color 0.15s',
          }}
          title="Click to view detailed confidence calculation"
        >
          <Info size={11} />
        </span>
      )}

      {/* Detailed Calculation Modal Overlay */}
      {visible && breakdown && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100vw',
            height: '100vh',
            background: 'rgba(0, 0, 0, 0.5)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 99999,
          }}
          onClick={(e) => {
            e.stopPropagation();
            setVisible(false);
          }}
        >
          <div
            style={{
              width: '440px',
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border)',
              borderRadius: '12px',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.25), 0 10px 10px -5px rgba(0, 0, 0, 0.1)',
              padding: '20px',
              color: 'var(--text-primary)',
              display: 'flex',
              flexDirection: 'column',
              maxHeight: '85vh',
              overflowY: 'auto',
              textAlign: 'left',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', borderBottom: '1px solid var(--border)', paddingBottom: '10px' }}>
              <span style={{ fontWeight: 700, fontSize: '0.92rem', color: 'var(--text-primary)' }}>
                Confidence Score Analysis
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{
                  background: 'rgba(255,255,255,0.06)', color: 'var(--text-primary)',
                  border: '1px solid var(--border)',
                  fontWeight: 800, fontSize: '0.9rem',
                  padding: '2px 10px', borderRadius: '4px',
                }}>
                  {pct}%
                </span>
                <button
                  onClick={(e) => { e.stopPropagation(); setVisible(false); }}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    fontSize: '1.4rem',
                    lineHeight: 1,
                    padding: '2px 6px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'color 0.15s',
                  }}
                  title="Close (Esc)"
                  onMouseEnter={(e) => e.target.style.color = 'var(--text-primary)'}
                  onMouseLeave={(e) => e.target.style.color = 'var(--text-muted)'}
                >
                  &times;
                </button>
              </div>
            </div>

            {/* Interpretation */}
            <p style={{
              fontSize: '0.74rem', color: 'var(--text-secondary)',
              margin: '0 0 16px 0', lineHeight: 1.5,
              padding: '8px 10px',
              background: 'rgba(255,255,255,0.04)',
              borderRadius: '6px',
              border: '1px solid var(--border-subtle)',
            }}>
              {interpretation}
            </p>

            {/* Component breakdown table */}
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '0.74rem',
              color: 'var(--text-primary)',
              marginBottom: '16px'
            }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-secondary)', fontWeight: 700 }}>
                  <th style={{ textAlign: 'left', padding: '6px 0', fontSize: '0.7rem', textTransform: 'uppercase' }}>Component</th>
                  <th style={{ textAlign: 'right', padding: '6px 6px', fontSize: '0.7rem', textTransform: 'uppercase' }}>Score</th>
                  <th style={{ textAlign: 'right', padding: '6px 6px', fontSize: '0.7rem', textTransform: 'uppercase' }}>Weight</th>
                  <th style={{ textAlign: 'right', padding: '6px 0', fontSize: '0.7rem', textTransform: 'uppercase' }}>Contrib.</th>
                </tr>
              </thead>
              <tbody>
                {compKeys.map((key) => {
                  const comp = components[key]
                  const contribPct = (comp.contribution * 100).toFixed(1)
                  const scorePct = Math.round(comp.score * 100)
                  const weightPct = Math.round(comp.weight * 100)
                  return (
                    <tr key={key} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                      <td style={{ padding: '8px 0', fontWeight: 500 }}>
                        {comp.label}
                        {comp.flag && <span style={{ color: '#d97706', marginLeft: '4px', cursor: 'help' }} title={comp.flag}>⚠</span>}
                      </td>
                      <td style={{ textAlign: 'right', padding: '8px 6px', color: 'var(--text-primary)', fontWeight: 600 }}>{scorePct}%</td>
                      <td style={{ textAlign: 'right', padding: '8px 6px', color: 'var(--text-secondary)' }}>{weightPct}%</td>
                      <td style={{ textAlign: 'right', padding: '8px 0', fontWeight: 700, color: 'var(--text-primary)' }}>+{contribPct}%</td>
                    </tr>
                  )
                })}
                <tr style={{ borderTop: '1px solid var(--border)', fontWeight: 700 }}>
                  <td style={{ padding: '10px 0', color: 'var(--text-primary)' }}>Total Confidence</td>
                  <td colSpan={2}></td>
                  <td style={{ textAlign: 'right', padding: '10px 0', fontSize: '0.84rem', color: badgeColor }}>{pct}%</td>
                </tr>
              </tbody>
            </table>

            {/* Clinical Deductions Box */}
            {compKeys.some(key => components[key].flag) && (
              <div style={{
                background: 'rgba(217, 119, 6, 0.04)',
                border: '1px solid rgba(217, 119, 6, 0.15)',
                borderRadius: '6px',
                padding: '8px 10px',
                marginBottom: '12px'
              }}>
                <p style={{ fontWeight: 700, fontSize: '0.7rem', color: '#d97706', margin: '0 0 6px 0' }}>
                  Clinical Warnings / Risk Deductions:
                </p>
                {compKeys.filter(key => components[key].flag).map((key) => (
                  <p key={key} style={{ fontSize: '0.68rem', color: 'var(--text-secondary)', margin: '3px 0', lineHeight: 1.35 }}>
                    • <strong>{components[key].label}:</strong> {components[key].flag}
                  </p>
                ))}
              </div>
            )}

            {/* Uncertainty flags */}
            {uncertaintyFlags.length > 0 && (
              <div style={{
                background: 'rgba(234, 179, 8, 0.05)',
                border: '1px solid rgba(234, 179, 8, 0.15)',
                borderRadius: '6px', padding: '8px 10px', marginBottom: '12px'
              }}>
                <p style={{ fontWeight: 700, fontSize: '0.7rem', color: '#d97706', margin: '0 0 6px 0' }}>
                  ⚠ Uncertainty Flags
                </p>
                {uncertaintyFlags.slice(0, 4).map((f, i) => (
                  <p key={i} style={{ fontSize: '0.68rem', color: 'var(--text-secondary)', margin: '3px 0' }}>
                    • {f}
                  </p>
                ))}
              </div>
            )}

            {/* Clinical note */}
            {clinicalNote && (
              <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', margin: '0 0 14px 0', lineHeight: 1.45 }}>
                {clinicalNote}
              </p>
            )}

            {/* Modal Actions */}
            <div style={{ display: 'flex', gap: '10px', marginTop: '14px', paddingTop: '10px', borderTop: '1px solid var(--border)' }}>
              {showOverride && onOverride && (
                <button
                  className="btn btn-outline-danger btn-sm"
                  onClick={(e) => { e.stopPropagation(); setVisible(false); onOverride(); }}
                  style={{ flex: 1, fontSize: '0.74rem', padding: '8px', fontWeight: 700 }}
                >
                  Override AI
                </button>
              )}
              <button
                className="btn btn-ghost btn-sm"
                onClick={(e) => { e.stopPropagation(); setVisible(false); }}
                style={{ flex: 1, fontSize: '0.74rem', padding: '8px', border: '1px solid var(--border)', fontWeight: 700 }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </span>
  )
}
