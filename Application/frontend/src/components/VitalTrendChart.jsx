/** VitalTrendChart — sparkline for a single vital over time using Recharts */
import { LineChart, Line, ResponsiveContainer, Tooltip, ReferenceLine } from 'recharts'

const VITAL_CONFIG = {
  heart_rate:       { label: 'HR', unit: 'bpm', normalMin: 60, normalMax: 100, color: '#f0883e' },
  spo2:             { label: 'SpO₂', unit: '%', normalMin: 95, normalMax: 100, color: '#58a6ff' },
  respiratory_rate: { label: 'RR', unit: '/min', normalMin: 12, normalMax: 20, color: '#3fb950' },
  systolic_bp:      { label: 'SBP', unit: 'mmHg', normalMin: 90, normalMax: 140, color: '#e3b341' },
  temperature:      { label: 'Temp', unit: '°C', normalMin: 36.1, normalMax: 37.9, color: '#bc8cff' },
}

export default function VitalTrendChart({ readings = [], vitalKey = 'heart_rate' }) {
  const cfg = VITAL_CONFIG[vitalKey] || { label: vitalKey, unit: '', color: '#58a6ff' }

  const data = readings
    .filter(r => r[vitalKey] != null)
    .map(r => ({
      value: r[vitalKey],
      time: new Date(r.recorded_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }))
    .reverse()

  if (data.length < 1) {
    return (
      <div style={{ height: 60, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
        No trend data
      </div>
    )
  }

  return (
    <div>
      <p style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {cfg.label} ({cfg.unit})
      </p>
      <ResponsiveContainer width="100%" height={55}>
        <LineChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <Line
            type="monotone"
            dataKey="value"
            stroke={cfg.color}
            strokeWidth={2}
            dot={data.length <= 5}
            isAnimationActive={false}
          />
          {cfg.normalMax && (
            <ReferenceLine y={cfg.normalMax} stroke="rgba(248,81,73,0.3)" strokeDasharray="3 3" />
          )}
          {cfg.normalMin && (
            <ReferenceLine y={cfg.normalMin} stroke="rgba(248,81,73,0.3)" strokeDasharray="3 3" />
          )}
          <Tooltip
            contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 11 }}
            labelStyle={{ color: 'var(--text-muted)' }}
            itemStyle={{ color: cfg.color }}
            formatter={(v) => [`${v} ${cfg.unit}`, cfg.label]}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
