import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Activity, RefreshCw, Plus, Zap } from 'lucide-react'

export default function TopNavbar({ activeTab, surgeActive, loading, onRefresh, onNewIntake }) {
  const navigate = useNavigate()
  const [now, setNow] = useState(new Date())

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  return (
    <header className="app-header" style={{
      display: 'grid',
      gridTemplateColumns: '250px 1fr 320px',
      alignItems: 'center',
      padding: '12px 24px',
      background: 'var(--bg-card)',
      borderBottom: '1px solid var(--border)',
      position: 'sticky',
      top: 0,
      zIndex: 100,
      boxShadow: 'var(--shadow-sm)',
      width: '100%',
      boxSizing: 'border-box'
    }}>
      {/* Left Brand Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }} onClick={() => navigate('/')}>
        <span style={{ fontSize: '1.15rem', fontWeight: 850, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>PatientTriage.ai</span>
      </div>

      {/* Middle Centered Navigation Links */}
      <nav style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
        <button
          onClick={() => navigate('/')}
          style={{
            background: activeTab === 'queue' ? 'rgba(124, 58, 237, 0.06)' : 'none',
            border: 'none',
            color: activeTab === 'queue' ? 'var(--accent)' : 'var(--text-secondary)',
            fontWeight: activeTab === 'queue' ? 700 : 500,
            cursor: 'pointer',
            fontSize: '0.85rem',
            padding: '6px 12px',
            borderRadius: '6px',
            transition: 'all 0.2s'
          }}
        >
          Queue
        </button>
        <button
          onClick={() => navigate('/')}
          style={{
            background: activeTab === 'patients' ? 'rgba(124, 58, 237, 0.06)' : 'none',
            border: 'none',
            color: activeTab === 'patients' ? 'var(--accent)' : 'var(--text-secondary)',
            fontWeight: activeTab === 'patients' ? 700 : 500,
            cursor: 'pointer',
            fontSize: '0.85rem',
            padding: '6px 12px',
            borderRadius: '6px',
            transition: 'all 0.2s'
          }}
        >
          Patients
        </button>
        <button
          onClick={() => navigate('/resources')}
          style={{
            background: activeTab === 'resources' ? 'rgba(124, 58, 237, 0.06)' : 'none',
            border: 'none',
            color: activeTab === 'resources' ? 'var(--accent)' : 'var(--text-secondary)',
            fontWeight: activeTab === 'resources' ? 700 : 500,
            cursor: 'pointer',
            fontSize: '0.85rem',
            padding: '6px 12px',
            borderRadius: '6px',
            transition: 'all 0.2s'
          }}
        >
          Resources
        </button>
        <button
          onClick={() => navigate('/audit')}
          style={{
            background: activeTab === 'audit' ? 'rgba(124, 58, 237, 0.06)' : 'none',
            border: 'none',
            color: activeTab === 'audit' ? 'var(--accent)' : 'var(--text-secondary)',
            fontWeight: activeTab === 'audit' ? 700 : 500,
            cursor: 'pointer',
            fontSize: '0.85rem',
            padding: '6px 12px',
            borderRadius: '6px',
            transition: 'all 0.2s'
          }}
        >
          Audit Log
        </button>
      </nav>

      {/* Right Controls and Metadata */}
      <div className="header-meta" style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '16px' }}>
        {surgeActive && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--surge)', fontSize: '0.78rem', fontWeight: 700 }}>
            <Zap size={13} /> SURGE ACTIVE
          </span>
        )}
        <span className="header-time" style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
        {onNewIntake && (
          <button 
            className="btn btn-primary btn-sm" 
            onClick={onNewIntake} 
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, height: '32px' }}
          >
            <Plus size={14} />
            Add Patient
          </button>
        )}
        {onRefresh && (
          <button className="btn btn-ghost btn-icon btn-sm" onClick={onRefresh} title="Refresh Live Queue">
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
          </button>
        )}
      </div>
    </header>
  )
}
