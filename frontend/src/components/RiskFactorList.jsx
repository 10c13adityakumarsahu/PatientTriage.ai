/** RiskFactorList — top 2-4 clinical risk drivers + uncertainty flags */
import { AlertTriangle, Info, AlertCircle } from 'lucide-react'

export default function RiskFactorList({ riskFactors = [], uncertaintyFlags = [], missingFields = [] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-4)' }}>
      {riskFactors.length > 0 && (
        <div>
          <p style={{ fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-muted)', marginBottom: 'var(--sp-2)' }}>
            Key Risk Signals
          </p>
          <div className="risk-factor-list">
            {riskFactors.slice(0, 4).map((f, i) => (
              <div key={i} className="risk-factor-item">
                <AlertCircle size={12} style={{ flexShrink: 0, marginTop: 1 }} />
                {f}
              </div>
            ))}
          </div>
        </div>
      )}

      {uncertaintyFlags.length > 0 && (
        <div>
          <p style={{ fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-muted)', marginBottom: 'var(--sp-2)' }}>
            Uncertainty Flags
          </p>
          <div className="risk-factor-list">
            {uncertaintyFlags.slice(0, 3).map((f, i) => (
              <div key={i} className="risk-factor-item uncertainty-item">
                <AlertTriangle size={12} style={{ flexShrink: 0, marginTop: 1 }} />
                {f}
              </div>
            ))}
          </div>
        </div>
      )}

      {missingFields.length > 0 && (
        <div>
          <p style={{ fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-muted)', marginBottom: 'var(--sp-2)' }}>
            Missing Information
          </p>
          <div className="risk-factor-list">
            {missingFields.slice(0, 3).map((f, i) => (
              <div key={i} className="risk-factor-item missing-item">
                <Info size={12} style={{ flexShrink: 0, marginTop: 1 }} />
                {f.replace(/_/g, ' ')}
              </div>
            ))}
          </div>
        </div>
      )}

      {riskFactors.length === 0 && uncertaintyFlags.length === 0 && (
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>No risk factors recorded yet.</p>
      )}
    </div>
  )
}
