/** Patient record: vitals, recommendation, override, and care-sequence actions. */
import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getPatient, getAssessments, reassessPatient, addVitals, addObservation, lookupPatient, getLiveQueue, api } from '../api'
import PriorityBadge from '../components/PriorityBadge'
import ConfidenceBadge from '../components/ConfidenceBadge'
import RiskFactorList from '../components/RiskFactorList'
import VitalTrendChart from '../components/VitalTrendChart'
import OverrideDialog from '../components/OverrideDialog'
import AuditEventList from '../components/AuditEventList'
import SimulationControls from '../components/SimulationControls'
import TopNavbar from '../components/TopNavbar'
import { CareSequenceFull } from '../components/CareSequence'
import { getCareSequence, DISPOSITION_LABELS } from '../workflow'
import {
  ArrowLeft, RefreshCw, ShieldAlert, User, Heart, Activity,
  Thermometer, Wind, TrendingDown, X, Search, Brain, Pencil, Plus,
  Menu, Calendar, Hourglass, FileText, Settings, Sparkles, LayoutGrid, ClipboardList, BarChart2
} from 'lucide-react'

function formatTime(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
function formatDate(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleDateString() + ' ' + new Date(dt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function expectedWaitText(priority) {
  if (priority === 'P1') return 'Immediate'
  if (priority === 'P2') return '< 10m'
  if (priority === 'P3') return '< 30m'
  if (priority === 'P4') return '< 60m'
  if (priority === 'P5') return '< 120m'
  return '—'
}
function waitMinutes(arrival) {
  if (!arrival) return 0
  return Math.floor((Date.now() - new Date(arrival)) / 60000)
}

const VITAL_KEYS = ['heart_rate', 'spo2', 'respiratory_rate', 'systolic_bp', 'temperature']
const VITAL_LABELS = {
  heart_rate: 'Heart Rate', spo2: 'SpO₂', respiratory_rate: 'Resp. Rate',
  systolic_bp: 'SBP', diastolic_bp: 'DBP', temperature: 'Temperature'
}
const VITAL_UNITS = {
  heart_rate: 'bpm', spo2: '%', respiratory_rate: '/min',
  systolic_bp: 'mmHg', diastolic_bp: 'mmHg', temperature: '°C'
}

function VitalItem({ label, value, unit, status, name, editing, defaultValue }) {
  let badgeText = 'Normal';
  let badgeClass = 'badge-normal';

  if (value == null || value === '' || value === '--') {
    badgeText = 'N/A';
    badgeClass = 'badge-na';
  } else if (name === 'mental_status') {
    if (value === 'alert') {
      badgeText = 'Normal';
      badgeClass = 'badge-normal';
    } else if (value === 'confused') {
      badgeText = 'Abnormal';
      badgeClass = 'badge-abnormal';
    } else {
      badgeText = 'Critical';
      badgeClass = 'badge-critical';
    }
  } else {
    if (status === 'critical') {
      badgeText = 'Critical';
      badgeClass = 'badge-critical';
    } else if (status === 'abnormal') {
      const numVal = parseFloat(value);
      if (name === 'heart_rate' && numVal > 100) badgeText = 'High';
      else if (name === 'heart_rate' && numVal < 60) badgeText = 'Low';
      else if (name === 'spo2' && numVal < 95) badgeText = 'Low';
      else if (name === 'respiratory_rate' && numVal > 20) badgeText = 'High';
      else if (name === 'respiratory_rate' && numVal < 12) badgeText = 'Low';
      else if (name === 'systolic_bp' && numVal > 140) badgeText = 'High';
      else if (name === 'systolic_bp' && numVal < 90) badgeText = 'Low';
      else if (name === 'temperature' && numVal > 37.9) badgeText = 'High';
      else if (name === 'temperature' && numVal < 36.1) badgeText = 'Low';
      else badgeText = 'Abnormal';
      badgeClass = 'badge-abnormal';
    } else {
      badgeText = 'Normal';
      badgeClass = 'badge-normal';
    }
  }

  return (
    <div className={`vital-item ${editing ? 'editing' : ''}`}>
      <span className="vital-label">{label}</span>
      {editing ? (
        name === 'mental_status' ? (
          <select name={name} className="vital-select-edit" defaultValue={defaultValue || 'alert'}>
            <option value="alert">Alert</option>
            <option value="confused">Confused</option>
            <option value="unresponsive">Unresponsive</option>
          </select>
        ) : (
          <input
            type="number"
            step={name === 'temperature' ? '0.1' : '1'}
            min={name === 'spo2' ? '50' : undefined}
            max={name === 'spo2' ? '100' : undefined}
            name={name}
            className="vital-input-edit"
            defaultValue={defaultValue || ''}
            placeholder={unit || ''}
          />
        )
      ) : (
        <div className="vital-main-row">
          <div className="vital-value-group">
            <span className="vital-value">{value ?? '—'}</span>
            {unit && <span className="vital-unit">{unit}</span>}
          </div>
          <span className={`vital-status-badge ${badgeClass}`}>{badgeText}</span>
        </div>
      )}
    </div>
  )
}

function vitalStatus(key, value, ageGroup) {
  if (value == null) return ''
  // Simplified critical detection
  if (key === 'spo2' && value < 90) return 'critical'
  if (key === 'spo2' && value < 95) return 'abnormal'
  if (key === 'heart_rate' && (value > 150 || value < 40)) return 'critical'
  if (key === 'heart_rate' && (value > 100 || value < 60)) return 'abnormal'
  if (key === 'respiratory_rate' && (value > 30 || value < 8)) return 'critical'
  if (key === 'respiratory_rate' && (value > 20 || value < 12)) return 'abnormal'
  if (key === 'systolic_bp' && (value < 70 || value > 180)) return 'critical'
  if (key === 'systolic_bp' && (value < 90 || value > 160)) return 'abnormal'
  if (key === 'temperature' && (value > 39.0 || value < 35.0 || value < 20.0)) return 'critical'
  if (key === 'temperature' && (value > 37.9 || value < 36.1)) return 'abnormal'
  return ''
}

export default function PatientDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [patient, setPatient] = useState(null)
  const [assessments, setAssessments] = useState([])
  const [loading, setLoading] = useState(true)
  const [overrideOpen, setOverrideOpen] = useState(false)
  const [activeTab, setActiveTab] = useState('overview')
  const [reassessing, setReassessing] = useState(false)
  const [queuePosition, setQueuePosition] = useState(null)

  const [actionModal, setActionModal] = useState({
    isOpen: false,
    type: '' // 'symptoms' or 'identity'
  })
  const [resLocked, setResLocked] = useState(false)
  const [hasAutoOpenedSymptoms, setHasAutoOpenedSymptoms] = useState(false)
  const [editingVitals, setEditingVitals] = useState(false)
  const [editingHistory, setEditingHistory] = useState(false)
  const [historyDraft, setHistoryDraft] = useState('')
  const [savingHistory, setSavingHistory] = useState(false)
  const [editingComplaint, setEditingComplaint] = useState(false)
  const [complaintDraft, setComplaintDraft] = useState('')
  const [savingComplaint, setSavingComplaint] = useState(false)

  const closeActionModal = () => {
    setActionModal({ isOpen: false, type: '' });
    setResLocked(false);
  };

  const load = useCallback(async () => {
    try {
      const [pRes, aRes, qRes] = await Promise.all([
        getPatient(id),
        getAssessments(id),
        getLiveQueue()
      ])
      setPatient(pRes.data)
      setAssessments(aRes.data)
      const qList = qRes.data || [];
      const idx = qList.findIndex(item => item.id === id);
      if (idx !== -1) {
        setQueuePosition(idx + 1);
      } else {
        setQueuePosition(null);
      }
    } catch { }
    setLoading(false)
  }, [id])

  useEffect(() => { load() }, [load])

  async function handleReassess() {
    if (confirm("Update vitals before reassessment? OK to record vitals, Cancel to reassess on current data.")) {
      setEditingVitals(true)
    } else {
      setReassessing(true)
      try {
        await reassessPatient({ patient_id: id, trigger: 'manual_reassessment' })
        await load()
      } catch { }
      setReassessing(false)
    }
  }

  async function handleStatusChange(status) {
    const labels = { in_progress: 'start the visit for', admitted: 'admit', referred: 'refer', discharged: 'discharge' }
    if (!window.confirm(`Confirm: ${labels[status]} this patient?`)) return
    try {
      await api.patch(`/patients/${id}/`, { status })
      await load()
    } catch {
      alert('Failed to update patient status.')
    }
  }

  if (loading) return <div className="loading-wrap" style={{ height: '100vh' }}><RefreshCw size={16} className="spin" /> Loading patient…</div>
  if (!patient) return <div className="loading-wrap" style={{ height: '100vh' }}>Patient not found.</div>

  const latestAssessment = assessments[0]
  const latestVitals = patient.vital_readings?.[0]
  const seq = getCareSequence(patient, latestAssessment)
  const { activeIndex } = seq
  const wait = waitMinutes(patient.arrival_time)
  const confPercent = latestAssessment && latestAssessment.confidence != null
    ? (latestAssessment.confidence > 1 ? Math.round(latestAssessment.confidence) : Math.round(latestAssessment.confidence * 100))
    : 0

  const missingVitalsList = latestAssessment?.missing_fields || []
  const displayMissing = missingVitalsList.map(f => {
    if (f === 'spo2') return 'SpO₂'
    if (f === 'respiratory_rate') return 'respiratory rate'
    if (f === 'systolic_bp' || f === 'diastolic_bp') return 'blood pressure'
    if (f === 'temperature') return 'temperature'
    return f.replace(/_/g, ' ')
  }).filter((v, i, a) => a.indexOf(v) === i)

  let nextStepText = ''
  if (displayMissing.length > 0) {
    if (displayMissing.length === 1) {
      nextStepText = `${displayMissing[0]} will improve accuracy.`
    } else if (displayMissing.length === 2) {
      nextStepText = `${displayMissing[0]} and ${displayMissing[1]} will improve accuracy.`
    } else {
      nextStepText = `${displayMissing.slice(0, -1).join(', ')}, and ${displayMissing[displayMissing.length - 1]} will improve accuracy.`
    }
  } else {
    nextStepText = 'All critical vitals recorded. Monitor patient status continuously.'
  }

  return (
    <div className="app-container" style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: 'var(--bg-base)', width: '100%' }}>
      {/* Reassessing Loader Overlay */}
      {reassessing && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100vw',
          height: '100vh',
          background: 'rgba(0, 0, 0, 0.5)',
          backdropFilter: 'blur(3px)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 999999,
          color: '#fff',
        }}>
          <RefreshCw size={42} className="spin" style={{ marginBottom: '16px', color: 'var(--accent)' }} />
          <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>AI Decision Support Engine</h3>
          <p style={{ margin: '8px 0 0 0', fontSize: '0.8rem', color: 'rgba(255,255,255,0.7)' }}>Running clinical reassessment...</p>
        </div>
      )}
      {/* Top Navbar */}
      <TopNavbar activeTab="patients" />

      {/* Main View Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', width: '100%', overflowY: 'auto' }}>
        <main className="main-content" style={{ padding: '24px', boxSizing: 'border-box' }}>
          {/* Action Toolbar with Breadcrumbs */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
            <nav className="breadcrumb" aria-label="Breadcrumb" style={{ margin: 0 }}>
              <button className="breadcrumb-link" onClick={() => navigate('/')}>ED Queue</button>
              <span className="breadcrumb-sep">›</span>
              <span className="breadcrumb-current">Patient {patient.name || patient.id?.slice(0, 8).toUpperCase()}</span>
            </nav>

            {/* Header Action Buttons */}
            <div style={{ display: 'flex', gap: 'var(--sp-2)', alignItems: 'center' }}>
              <button className="btn btn-ghost btn-sm" onClick={load} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <RefreshCw size={12} />
                Refresh
              </button>

              {activeIndex === 2 && (
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => handleStatusChange('in_progress')}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
                >
                  <Activity size={12} />
                  Start Visit
                </button>
              )}

              {activeIndex === 3 && (
                <>
                  <button
                    className="btn btn-outline-success btn-sm"
                    onClick={() => handleStatusChange('admitted')}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
                  >
                    Admit
                  </button>
                  <button
                    className="btn btn-outline-warning btn-sm"
                    onClick={() => handleStatusChange('referred')}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
                  >
                    Refer
                  </button>
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => handleStatusChange('discharged')}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6, border: '1px solid var(--border)' }}
                  >
                    Discharge
                  </button>
                </>
              )}

              {activeIndex === 4 && (
                <>
                  <button
                    className="btn btn-outline-warning btn-sm"
                    onClick={() => handleStatusChange('referred')}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
                  >
                    Refer
                  </button>
                  <button
                    className="btn btn-outline-success btn-sm"
                    onClick={() => handleStatusChange('discharged')}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
                  >
                    Discharge
                  </button>
                </>
              )}

              <button
                className="btn btn-ghost btn-sm"
                onClick={handleReassess}
                disabled={reassessing}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                <RefreshCw size={12} className={reassessing ? 'spin' : ''} />
                {reassessing ? 'Reassessing…' : 'Reassess'}
              </button>
              <button
                className="btn btn-outline-danger btn-sm"
                onClick={() => setOverrideOpen(true)}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                <ShieldAlert size={12} />
                Override
              </button>
            </div>
          </div>

          {/* Patient Header Card */}
          <div className="patient-header-card">
            <div className="patient-avatar-circle">
              {patient.name ? patient.name.charAt(0).toUpperCase() : 'T'}
            </div>

            <div className="patient-header-main">
              <div className="patient-header-top-row">
                <h1 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0 }}>
                  {patient.name || 'Anonymous Patient'}{' '}
                  <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)', fontWeight: 400 }}>
                    ({patient.patient_identifier || 'No ID'})
                  </span>
                </h1>

                {patient.scenario_tag && (
                  <span className="scenario-tag" style={{ margin: 0 }}>
                    {patient.scenario_tag.replace(/_/g, '-')}
                  </span>
                )}
              </div>

              <h2 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-secondary)', margin: '0 0 10px 0', display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
                <span>{patient.age}y {patient.age_group} · {patient.sex || 'Unknown sex'}</span>
                {queuePosition !== null && (
                  <span style={{
                    fontSize: '0.72rem',
                    background: 'rgba(124, 58, 237, 0.08)',
                    color: 'var(--accent)',
                    padding: '2px 8px',
                    borderRadius: '12px',
                    fontWeight: 700,
                    border: '1px solid rgba(124, 58, 237, 0.2)'
                  }}>
                    Sequence No: #{queuePosition}
                  </span>
                )}
                <span style={{
                  fontSize: '0.72rem',
                  background: 'var(--bg-hover)',
                  color: 'var(--text-muted)',
                  padding: '2px 8px',
                  borderRadius: '12px',
                  fontWeight: 500,
                  border: '1px solid var(--border)'
                }}>
                  Target Wait: {expectedWaitText(patient.current_priority)}
                </span>
              </h2>

              {/* Dynamic Alert Actions Inline */}
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: '10px' }}>
                {(!patient.vital_readings || patient.vital_readings.length === 0) && (
                  <button
                    className="btn btn-warning btn-sm"
                    style={{ padding: '3px 8px', fontSize: '0.72rem', display: 'inline-flex', alignItems: 'center', gap: 3, fontWeight: 700 }}
                    onClick={() => setEditingVitals(true)}
                  >
                    Vitals Pending — Record Vitals
                  </button>
                )}
                {(patient.patient_identifier?.startsWith('TEMP-') || !patient.patient_identifier) && (
                  <button
                    className="btn btn-danger btn-sm"
                    style={{ padding: '3px 8px', fontSize: '0.72rem', display: 'inline-flex', alignItems: 'center', gap: 3, fontWeight: 700 }}
                    onClick={() => setActionModal({ isOpen: true, type: 'identity' })}
                  >
                    ID Pending — Resolve Identity
                  </button>
                )}
              </div>

              <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', margin: '0 0 12px 0' }}>
                <strong>Chief complaint:</strong> {patient.chief_complaint}
              </p>

              <div className="patient-header-meta-row">
                <div className="patient-header-meta-item">
                  <Calendar size={13} style={{ color: 'var(--text-muted)' }} />
                  <span>Arrived: {formatDate(patient.arrival_time)}</span>
                </div>
                <div className="patient-header-meta-item">
                  <Hourglass size={13} style={{ color: 'var(--p2)' }} />
                  <span style={{ color: 'var(--p2)', fontWeight: 600 }}>
                    Waiting: {wait}m
                    {patient.last_attended_time && (
                      <span style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', fontWeight: 400, marginLeft: '6px' }}>
                        (Attended {(() => {
                          const diffMs = new Date() - new Date(patient.last_attended_time);
                          const diffMin = Math.max(0, Math.floor(diffMs / 60000));
                          return `${diffMin}m`;
                        })()} ago)
                      </span>
                    )}
                  </span>
                </div>
                <div className="patient-header-meta-item">
                  <LayoutGrid size={13} style={{ color: 'var(--text-muted)' }} />
                  <span>Queue: {patient.current_queue?.replace(/_/g, ' ') || '—'}</span>
                </div>
                <div className="patient-header-meta-item">
                  <ClipboardList size={13} style={{ color: patient.history_available ? 'var(--p4)' : 'var(--p1)' }} />
                  <span style={{ color: patient.history_available ? 'var(--p4)' : 'var(--p1)' }}>
                    History: {patient.history_available ? 'Available' : 'Not available'}
                  </span>
                </div>
                <div className="patient-header-meta-item" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <User size={13} style={{ color: 'var(--text-muted)' }} />
                  <span style={{ fontWeight: 600 }}>Doctor:</span>
                  <select
                    value={patient.assigned_doctor || ''}
                    onChange={async (e) => {
                      const newDocName = e.target.value;
                      try {
                        await api.patch(`/patients/${patient.id}/`, {
                          assigned_doctor: newDocName
                        });
                        alert("Assigned doctor updated successfully!");
                        load();
                      } catch {
                        alert("Failed to update assigned doctor.");
                      }
                    }}
                    style={{
                      padding: '2px 6px',
                      fontSize: '0.78rem',
                      border: '1px solid var(--border)',
                      borderRadius: '4px',
                      background: 'var(--bg-card)',
                      color: 'var(--text-primary)',
                      fontWeight: 600,
                      cursor: 'pointer'
                    }}
                  >
                    <option value="">Unassigned</option>
                    {(() => {
                      const saved = localStorage.getItem('ed_doctors');
                      const docList = saved ? JSON.parse(saved) : [
                        { name: 'Dr. Kapoor' },
                        { name: 'Dr. Sharma' },
                        { name: 'Dr. Roy' },
                        { name: 'Dr. Patel' },
                        { name: 'Dr. Sen' },
                        { name: 'Dr. Joshi' },
                        { name: 'Dr. Gupta' },
                        { name: 'Dr. Iyer' }
                      ];
                      return docList.map((doc, dIdx) => (
                        <option key={dIdx} value={doc.name}>{doc.name}</option>
                      ));
                    })()}
                  </select>
                </div>
              </div>
            </div>

            <div className="patient-header-badges">
              <PriorityBadge priority={patient.current_priority} showLabel />
              {latestAssessment && (
                <ConfidenceBadge
                  confidence={latestAssessment.confidence}
                  label={latestAssessment.confidence_label}
                  breakdown={latestAssessment.confidence_breakdown}
                  showOverride={true}
                  onOverride={() => setOverrideOpen(true)}
                />
              )}
              {latestAssessment && (
                <span className={`safety-pill ${latestAssessment.requires_human_review ? 'YELLOW' : 'GREEN'}`}>
                  {latestAssessment.requires_human_review ? 'Review Required' : 'AI Assessed'}
                </span>
              )}
            </div>
          </div>

          <CareSequenceFull patient={patient} latestAssessment={latestAssessment} />

          {/* Tab Navigation */}
          <div className="page-tabs" role="tablist">
            {['overview', 'vitals', 'ai-recommendation', 'audit'].map(tab => (
              <button
                key={tab}
                className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
                role="tab"
                aria-selected={activeTab === tab}
                onClick={() => setActiveTab(tab)}
              >
                {tab === 'ai-recommendation' ? 'AI Recommendation' : tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>

          {/* Overview Tab Content */}
          {activeTab === 'overview' && (
            <div className="patient-detail-layout">
              <div>
                {/* Current Vitals Section */}
                <div className="card" style={{ marginBottom: 'var(--sp-4)' }}>
                  <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="card-title" style={{ margin: 0 }}>Current Vitals</span>
                      {latestVitals && !editingVitals && (
                        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                          Recorded {formatTime(latestVitals.recorded_at)}
                        </span>
                      )}
                      {!latestVitals && !editingVitals && (
                        <span className="badge badge-warning" style={{ fontSize: '0.65rem' }}>
                          Vitals Pending
                        </span>
                      )}
                    </div>
                    {!editingVitals && (
                      <button
                        className="btn btn-ghost btn-sm"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
                        onClick={() => setEditingVitals(true)}
                        title={latestVitals ? "Edit Vitals" : "Record Vitals"}
                      >
                        <Plus size={12} />
                        {latestVitals ? 'Edit Vitals' : 'Record Vitals'}
                      </button>
                    )}
                  </div>

                  <form onSubmit={async (e) => {
                    e.preventDefault();
                    const payload = {};
                    ['heart_rate', 'spo2', 'respiratory_rate', 'systolic_bp', 'diastolic_bp', 'temperature'].forEach(f => {
                      const val = e.target[f].value;
                      if (val) {
                        payload[f] = parseFloat(val);
                      } else if (latestVitals && latestVitals[f] != null) {
                        payload[f] = latestVitals[f];
                      }
                    });
                    payload['mental_status'] = e.target['mental_status']?.value || latestVitals?.mental_status || 'alert';
                    try {
                      await addVitals(id, payload);
                      await reassessPatient({ patient_id: id, trigger: 'vitals_update' });
                      alert("Vitals recorded and triage updated!");
                      setEditingVitals(false);
                      load();
                    } catch (err) {
                      alert(err.message || "Failed to save vitals.");
                    }
                  }}>
                    <div className="vitals-grid">
                      <VitalItem
                        label="Heart Rate"
                        value={latestVitals?.heart_rate}
                        unit="bpm"
                        status={vitalStatus('heart_rate', latestVitals?.heart_rate, patient.age_group)}
                        name="heart_rate"
                        editing={editingVitals}
                        defaultValue={latestVitals?.heart_rate}
                      />
                      <VitalItem
                        label="SpO₂"
                        value={latestVitals?.spo2}
                        unit="%"
                        status={vitalStatus('spo2', latestVitals?.spo2, patient.age_group)}
                        name="spo2"
                        editing={editingVitals}
                        defaultValue={latestVitals?.spo2}
                      />
                      <VitalItem
                        label="Resp. Rate"
                        value={latestVitals?.respiratory_rate}
                        unit="/min"
                        status={vitalStatus('respiratory_rate', latestVitals?.respiratory_rate, patient.age_group)}
                        name="respiratory_rate"
                        editing={editingVitals}
                        defaultValue={latestVitals?.respiratory_rate}
                      />

                      {editingVitals ? (
                        <div className="vital-item editing">
                          <span className="vital-label">Systolic / Diastolic BP</span>
                          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: 'auto' }}>
                            <input
                              type="number"
                              name="systolic_bp"
                              className="vital-input-edit"
                              style={{ flex: 1, minWidth: 0 }}
                              defaultValue={latestVitals?.systolic_bp || ''}
                              placeholder="SBP"
                            />
                            <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>/</span>
                            <input
                              type="number"
                              name="diastolic_bp"
                              className="vital-input-edit"
                              style={{ flex: 1, minWidth: 0 }}
                              defaultValue={latestVitals?.diastolic_bp || ''}
                              placeholder="DBP"
                            />
                          </div>
                          <span className="vital-unit" style={{ marginTop: 2 }}>mmHg</span>
                        </div>
                      ) : (
                        <VitalItem
                          label="Systolic / Diastolic BP"
                          value={latestVitals?.systolic_bp ? `${latestVitals.systolic_bp}/${latestVitals.diastolic_bp}` : null}
                          unit="mmHg"
                          status={vitalStatus('systolic_bp', latestVitals?.systolic_bp, patient.age_group)}
                          name="systolic_bp"
                          editing={false}
                        />
                      )}

                      <VitalItem
                        label="Temperature"
                        value={latestVitals?.temperature}
                        unit="°C"
                        status={vitalStatus('temperature', latestVitals?.temperature, patient.age_group)}
                        name="temperature"
                        editing={editingVitals}
                        defaultValue={latestVitals?.temperature}
                      />
                      <VitalItem
                        label="Consciousness"
                        value={latestVitals?.mental_status}
                        unit=""
                        status={latestVitals?.mental_status === 'unresponsive' ? 'critical' : latestVitals?.mental_status === 'confused' ? 'abnormal' : ''}
                        name="mental_status"
                        editing={editingVitals}
                        defaultValue={latestVitals?.mental_status}
                      />
                    </div>

                    {editingVitals && (
                      <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: 'var(--sp-4)' }}>
                        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditingVitals(false)}>Cancel</button>
                        <button type="submit" className="btn btn-primary btn-sm">Save & Triage</button>
                      </div>
                    )}
                  </form>

                  {!editingVitals && (
                    <div className="ai-alert-banner">
                      <Brain size={16} color="var(--accent)" style={{ flexShrink: 0 }} />
                      <span>AI is continuously analyzing incoming data. Reassess to get the latest priority.</span>
                    </div>
                  )}
                </div>

                {/* AI Recommendation Card (BETA) inline */}
                {latestAssessment && !editingVitals && (
                  <div className="card ai-rec-beta-card">
                    <div className="card-header" style={{ marginBottom: 'var(--sp-4)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span className="card-title" style={{ margin: 0 }}>AI Recommendation</span>
                      <span className="badge" style={{ background: 'rgba(234, 88, 12, 0.1)', color: 'var(--p2)', fontSize: '0.65rem', fontWeight: 700, padding: '2px 6px', borderRadius: '4px' }}>BETA</span>
                    </div>

                    <div className="ai-rec-grid">
                      <div className="ai-rec-col">
                        <span className="ai-rec-label">Recommended Priority</span>
                        <div className="ai-rec-value">
                          <PriorityBadge priority={latestAssessment.priority} showLabel />
                        </div>
                      </div>

                      <div className="ai-rec-col" style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <span className="ai-rec-label">Confidence</span>
                        <div style={{ display: 'inline-flex', alignItems: 'center' }}>
                          <ConfidenceBadge
                            confidence={latestAssessment.confidence}
                            label={latestAssessment.confidence_label}
                            breakdown={latestAssessment.confidence_breakdown}
                            showOverride={true}
                            onOverride={() => setOverrideOpen(true)}
                          />
                        </div>
                      </div>

                      <div className="ai-rec-col">
                        <span className="ai-rec-label">Rationale (Top Factors)</span>
                        <ul className="rationale-list">
                          {latestAssessment.risk_factors?.slice(0, 3).map((f, i) => (
                            <li key={i}>{f}</li>
                          ))}
                          {latestAssessment.risk_factors?.length === 0 && (
                            <li>No risk factors identified.</li>
                          )}
                        </ul>
                      </div>
                    </div>
                  </div>
                )}

                {/* Medical History — always shown, editable */}
                {!editingVitals && (
                  <div className="card" style={{ marginTop: 'var(--sp-4)' }}>
                    <div className="card-header" style={{ marginBottom: editingHistory ? 'var(--sp-3)' : 0 }}>
                      <span className="card-title">Medical History</span>
                      {!editingHistory && (
                        <button
                          className="btn btn-ghost btn-sm"
                          style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
                          onClick={() => {
                            setHistoryDraft(patient.relevant_history || '')
                            setEditingHistory(true)
                          }}
                        >
                          <Pencil size={12} />
                          Edit History
                        </button>
                      )}
                    </div>

                    {editingHistory ? (
                      <div>
                        <textarea
                          className="form-textarea"
                          style={{ width: '100%', marginBottom: 'var(--sp-3)', minHeight: 80 }}
                          value={historyDraft}
                          onChange={e => setHistoryDraft(e.target.value)}
                          placeholder="e.g. Hypertension, Diabetes, Past Cardiac Events"
                          autoFocus
                        />
                        <div style={{ display: 'flex', gap: 'var(--sp-2)', justifyContent: 'flex-end' }}>
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => setEditingHistory(false)}
                            disabled={savingHistory}
                          >
                            Cancel
                          </button>
                          <button
                            className="btn btn-primary btn-sm"
                            disabled={savingHistory}
                            onClick={async () => {
                              setSavingHistory(true)
                              try {
                                await api.patch(`/patients/${patient.id}/`, {
                                  relevant_history: historyDraft,
                                  history_available: historyDraft.trim().length > 0,
                                })
                                await reassessPatient({ patient_id: patient.id, trigger: 'history_updated' })
                                setEditingHistory(false)
                                load()
                              } catch {
                                alert('Failed to save history')
                              } finally {
                                setSavingHistory(false)
                              }
                            }}
                          >
                            {savingHistory ? 'Saving…' : 'Save & Re-triage'}
                          </button>
                        </div>
                      </div>
                    ) : (
                      <p style={{ fontSize: '0.85rem', color: patient.relevant_history ? 'var(--text-secondary)' : 'var(--text-muted)', lineHeight: 1.6, margin: 0, fontStyle: patient.relevant_history ? 'normal' : 'italic' }}>
                        {patient.relevant_history || 'No medical history recorded.'}
                      </p>
                    )}
                  </div>
                )}

                {/* Chief Complaint — always shown, editable */}
                {!editingVitals && (
                  <div className="card" style={{ marginTop: 'var(--sp-4)' }}>
                    <div className="card-header" style={{ marginBottom: editingComplaint ? 'var(--sp-3)' : 0 }}>
                      <span className="card-title">Chief Complaint</span>
                      {!editingComplaint && (
                        <button
                          className="btn btn-ghost btn-sm"
                          style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
                          onClick={() => {
                            setComplaintDraft(patient.chief_complaint || '')
                            setEditingComplaint(true)
                          }}
                        >
                          <Pencil size={12} />
                          {patient.chief_complaint ? 'Edit' : 'Add'}
                        </button>
                      )}
                    </div>
                    {editingComplaint ? (
                      <div>
                        <textarea
                          className="form-textarea"
                          style={{ width: '100%', marginBottom: 'var(--sp-3)', minHeight: 60 }}
                          value={complaintDraft}
                          onChange={e => setComplaintDraft(e.target.value)}
                          placeholder="e.g. severe chest pain, shortness of breath"
                          autoFocus
                        />
                        <div style={{ display: 'flex', gap: 'var(--sp-2)', justifyContent: 'flex-end' }}>
                          <button className="btn btn-ghost btn-sm" onClick={() => setEditingComplaint(false)} disabled={savingComplaint}>Cancel</button>
                          <button
                            className="btn btn-primary btn-sm"
                            disabled={savingComplaint}
                            onClick={async () => {
                              setSavingComplaint(true)
                              try {
                                await api.patch(`/patients/${patient.id}/`, { chief_complaint: complaintDraft })
                                await reassessPatient({ patient_id: patient.id, trigger: 'complaint_updated' })
                                setEditingComplaint(false)
                                load()
                              } catch {
                                alert('Failed to save complaint')
                              } finally {
                                setSavingComplaint(false)
                              }
                            }}
                          >
                            {savingComplaint ? 'Saving…' : 'Save & Re-triage'}
                          </button>
                        </div>
                      </div>
                    ) : (
                      <p style={{ fontSize: '0.85rem', color: patient.chief_complaint ? 'var(--text-secondary)' : 'var(--text-muted)', lineHeight: 1.6, margin: 0, fontStyle: patient.chief_complaint ? 'normal' : 'italic' }}>
                        {patient.chief_complaint || 'No chief complaint recorded. Click Edit to add.'}
                      </p>
                    )}
                  </div>
                )}

                {/* Recorded Symptoms */}
                {!editingVitals && (
                  <div className="card" style={{ marginTop: 'var(--sp-4)' }}>
                    <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span className="card-title">Recorded Symptoms</span>
                      <button
                        className="btn btn-ghost btn-sm"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
                        onClick={() => setActionModal({ isOpen: true, type: 'symptoms' })}
                      >
                        <Plus size={12} />
                        Add Symptoms / Issues
                      </button>
                    </div>
                    {patient.notes?.length > 0 ? (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-2)' }}>
                        {patient.notes.flatMap(n => n.normalized_symptoms || []).filter((v, i, a) => a.indexOf(v) === i).map(s => (
                          <span key={s} style={{ fontSize: '0.75rem', padding: '3px 8px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 999, color: 'var(--text-secondary)' }}>
                            {s.replace(/_/g, ' ')}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: 0, fontStyle: 'italic' }}>
                        No symptoms or notes recorded yet. Click Add to log.
                      </p>
                    )}
                  </div>
                )}
              </div>

              {/* Right Column Layout */}
              {latestAssessment && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-4)' }}>
                  {/* Why this priority? */}
                  <div className="card">
                    <div className="card-header" style={{ marginBottom: 'var(--sp-4)' }}>
                      <span className="card-title">Why this priority?</span>
                    </div>
                    {/* Render Risk signals and Uncertainty flags without Missing fields */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-4)' }}>
                      {latestAssessment.risk_factors?.length > 0 && (
                        <div>
                          <p style={{ fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-muted)', marginBottom: 'var(--sp-2)' }}>
                            Key Risk Signals
                          </p>
                          <div className="risk-factor-list">
                            {latestAssessment.risk_factors.slice(0, 4).map((f, i) => (
                              <div key={i} className="risk-factor-item">
                                <span style={{ flexShrink: 0, marginTop: 1 }}>•</span>
                                {f}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {latestAssessment.uncertainty_flags?.length > 0 && (
                        <div>
                          <p style={{ fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-muted)', marginBottom: 'var(--sp-2)' }}>
                            Uncertainty Flags
                          </p>
                          <div className="risk-factor-list">
                            {latestAssessment.uncertainty_flags.slice(0, 3).map((f, i) => (
                              <div key={i} className="risk-factor-item uncertainty-item">
                                <span style={{ flexShrink: 0, marginTop: 1 }}>•</span>
                                {f}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Suggested Next Step CTA Card */}
                  <div className="card">
                    <div className="card-header" style={{ marginBottom: 'var(--sp-4)' }}>
                      <span className="card-title">Suggested Next Step</span>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-3)' }}>
                      <p style={{ fontWeight: 700, fontSize: '0.92rem', margin: 0 }}>
                        {displayMissing.length > 0 ? 'Consider obtaining missing vitals' : 'Continue monitoring'}
                      </p>
                      <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: 0 }}>
                        {nextStepText}
                      </p>
                      <button
                        className="btn-reassess-cta"
                        onClick={handleReassess}
                        disabled={reassessing}
                        style={{ marginTop: 'var(--sp-2)' }}
                      >
                        <RefreshCw size={14} className={reassessing ? 'spin' : ''} />
                        {reassessing ? 'Reassessing...' : 'Reassess Patient'}
                      </button>

                      <button
                        className="btn btn-warning"
                        onClick={async () => {
                          try {
                            await api.post('/simulation/deteriorate/', { patient_id: id });
                            alert("Deterioration simulated! Vitals updated and patient re-triaged.");
                            load();
                          } catch (err) {
                            alert("Failed to simulate deterioration: " + (err.response?.data?.error || err.message));
                          }
                        }}
                        style={{
                          marginTop: 'var(--sp-2)',
                          width: '100%',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '6px',
                          padding: '10px',
                          borderRadius: 'var(--r-md)',
                          fontWeight: 700,
                          fontSize: '0.82rem',
                          background: 'var(--p2)',
                          color: '#fff',
                          border: 'none',
                          cursor: 'pointer'
                        }}
                      >
                        <TrendingDown size={14} />
                        Simulate Deterioration
                      </button>
                    </div>
                  </div>

                  {/* Routing info */}
                  <div className="card">
                    <div className="card-header" style={{ marginBottom: 'var(--sp-4)' }}>
                      <span className="card-title">Routing</span>
                    </div>
                    <div>
                      <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: 4 }}>Recommended destination</p>
                      <p style={{ fontWeight: 600, textTransform: 'capitalize', marginBottom: 'var(--sp-3)', fontSize: '0.9rem' }}>
                        {latestAssessment.recommended_destination?.replace(/_/g, ' ') || '—'}
                      </p>
                      <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: 4 }}>Recommended action</p>
                      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', textTransform: 'capitalize', margin: 0 }}>
                        {latestAssessment.recommended_action?.replace(/_/g, ' ') || '—'}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Vitals tab */}
          {activeTab === 'vitals' && (
            <div className="card">
              <div className="card-header"><span className="card-title">Vital Trends</span></div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--sp-6)' }}>
                {VITAL_KEYS.map(k => (
                  <div key={k} style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', padding: 'var(--sp-3)' }}>
                    <VitalTrendChart readings={patient.vital_readings || []} vitalKey={k} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI Recommendation tab */}
          {activeTab === 'ai-recommendation' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-4)' }}>
              {assessments.length === 0 ? (
                <div className="empty-state"><div className="empty-state-icon">🤖</div>No assessments yet.</div>
              ) : assessments.map((a, i) => (
                <div key={a.id} className="card">
                  <div className="card-header">
                    <div style={{ display: 'flex', gap: 'var(--sp-3)', alignItems: 'center' }}>
                      {i === 0 && <span style={{ fontSize: '0.65rem', color: 'var(--accent)', fontWeight: 700, textTransform: 'uppercase' }}>Latest</span>}
                      <PriorityBadge priority={a.priority} />
                      <ConfidenceBadge confidence={a.confidence} label={a.confidence_label} />
                    </div>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{formatDate(a.created_at)}</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-6)' }}>
                    <div>
                      <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: 'var(--sp-2)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>Trigger</p>
                      <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{a.trigger?.replace(/_/g, ' ')}</p>
                    </div>
                    <div>
                      <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: 'var(--sp-2)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>Destination</p>
                      <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', textTransform: 'capitalize' }}>{a.recommended_destination?.replace(/_/g, ' ')}</p>
                    </div>
                  </div>
                  <div style={{ marginTop: 'var(--sp-4)' }}>
                    <RiskFactorList riskFactors={a.risk_factors} uncertaintyFlags={a.uncertainty_flags} missingFields={a.missing_fields} />
                  </div>
                  {a.requires_human_review && (
                    <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: 'var(--sp-3)', padding: 'var(--sp-3)', background: 'rgba(217,119,6,0.06)', borderRadius: 'var(--r-md)', border: '1px solid var(--p3-border)', display: 'flex', alignItems: 'center', gap: 8 }}>
                      This assessment requires human review
                    </p>
                  )}
                  {a.ai_decision_support && (
                    <div className="ai-support-section" style={{ marginTop: 'var(--sp-4)', borderTop: '1px solid var(--border)', paddingTop: 'var(--sp-4)' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 'var(--sp-6)' }}>
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 'var(--sp-2)' }}>
                            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>AI Recommended Complexity</span>
                            <span style={{
                              fontSize: '0.7rem',
                              fontWeight: 700,
                              padding: '2px 8px',
                              borderRadius: '4px',
                              background: a.ai_decision_support.complexity === 'High' ? 'var(--p1-bg)' : a.ai_decision_support.complexity === 'Medium' ? 'var(--p3-bg)' : 'var(--p4-bg)',
                              color: a.ai_decision_support.complexity === 'High' ? 'var(--p1)' : a.ai_decision_support.complexity === 'Medium' ? 'var(--p3)' : 'var(--p4)',
                              border: '1px solid',
                              borderColor: a.ai_decision_support.complexity === 'High' ? 'var(--p1-border)' : a.ai_decision_support.complexity === 'Medium' ? 'var(--p3-border)' : 'var(--p4-border)'
                            }}>
                              {a.ai_decision_support.complexity}
                            </span>
                          </div>
                          <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 'var(--sp-4)' }}>
                            {a.ai_decision_support.complexity_rationale}
                          </p>

                          <div>
                            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600, display: 'block', marginBottom: 'var(--sp-2)' }}>Suggested Preliminary Tests</span>
                            <ul style={{ listStyleType: 'disc', paddingLeft: 'var(--sp-4)', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                              {a.ai_decision_support.preliminary_tests?.map((t, idx) => (
                                <li key={idx} style={{ marginBottom: 4 }}>{t}</li>
                              ))}
                            </ul>
                          </div>
                        </div>

                        <div>
                          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600, display: 'block', marginBottom: 'var(--sp-2)' }}>Triage Judging & Monitoring Criteria</span>
                          <ul style={{ listStyleType: 'disc', paddingLeft: 'var(--sp-4)', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 'var(--sp-4)' }}>
                            {a.ai_decision_support.criteria?.map((c, idx) => (
                              <li key={idx} style={{ marginBottom: 4 }}>{c}</li>
                            ))}
                          </ul>

                          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600, display: 'block', marginBottom: 'var(--sp-2)' }}>Safety & Medication Protocol (Side)</span>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                            {a.ai_decision_support.medications?.map((m, idx) => (
                              <div key={idx} style={{ padding: '8px 12px', background: 'var(--bg-hover)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                                  <span style={{ fontWeight: 600, fontSize: '0.82rem' }}>{m.name}</span>
                                  <span style={{ fontSize: '0.72rem', background: 'var(--bg-base)', padding: '2px 6px', borderRadius: 4, fontWeight: 600 }}>{m.dosage}</span>
                                </div>
                                <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: 4 }}><strong>Indication:</strong> {m.indication}</p>
                                {m.warning && <p style={{ fontSize: '0.75rem', color: 'var(--p1)', display: 'flex', alignItems: 'flex-start', gap: 4 }}><strong>Warning:</strong> {m.warning}</p>}
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Audit tab */}
          {activeTab === 'audit' && (
            <div className="card">
              <div className="card-header"><span className="card-title">Patient Audit Trail</span></div>
              <AuditEventList patientId={id} />
            </div>
          )}
        </main>


        {overrideOpen && (
          <OverrideDialog
            patient={patient}
            currentAssessment={latestAssessment}
            onClose={() => setOverrideOpen(false)}
            onDone={() => { setOverrideOpen(false); load() }}
          />
        )}

        {actionModal.isOpen && (
          <div className="dialog-overlay" onClick={e => e.target === e.currentTarget && closeActionModal()}>
            <div className="dialog-box" style={{ maxWidth: '520px', width: '90vw' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border)', paddingBottom: 'var(--sp-2)', marginBottom: 'var(--sp-4)' }}>
                <h2 className="dialog-title" style={{ margin: 0 }}>
                  {actionModal.type === 'symptoms' ? 'Record Symptoms' : 'Resolve Patient Identity'}
                </h2>
                <button className="btn btn-ghost btn-icon" onClick={closeActionModal} aria-label="Close">
                  <X size={16} />
                </button>
              </div>

              {actionModal.type === 'symptoms' ? (
                <form onSubmit={async (e) => {
                  e.preventDefault();
                  const symptomsText = e.target.symptoms_text.value;
                  if (!symptomsText.trim()) return;
                  try {
                    await addObservation(patient.id, { raw_text: symptomsText });
                    await reassessPatient({ patient_id: patient.id, trigger: 'symptom_update' });
                    alert("Symptoms recorded and triage updated!");
                    closeActionModal();
                    load();
                  } catch (err) {
                    alert(err.message || "Failed to save symptoms.");
                  }
                }}>
                  <div className="form-group" style={{ marginBottom: '16px' }}>
                    <label className="form-label" htmlFor="detail-popup-symptoms">New Symptoms / Clinical Issues</label>
                    <textarea
                      id="detail-popup-symptoms"
                      name="symptoms_text"
                      className="form-textarea"
                      style={{ height: '120px', width: '100%', padding: '8px' }}
                      placeholder="Describe new symptoms, issues, or changes in clinical presentation (e.g. sudden onset of severe abdominal pain, chest pain radiating to back, or severe breathing difficulties)"
                      required
                    />
                  </div>
                  <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                    <button type="button" className="btn btn-ghost" onClick={closeActionModal}>Cancel</button>
                    <button type="submit" className="btn btn-primary">Save & Triage</button>
                  </div>
                </form>
              ) : (
                <div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 'var(--sp-4)' }}>
                    This patient is registered with temporary ID: <strong>{patient.patient_identifier}</strong>.
                    Provide their standard ABHA/Aadhaar/Phone number to link historic records.
                  </p>
                  <div className="form-group">
                    <label className="form-label" htmlFor="detail-popup-lookup-id">
                      Standard Patient Identifier
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 400, marginLeft: 8 }}>(e.g. ABHA-4221-5582)</span>
                    </label>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <input
                        type="text"
                        id="detail-popup-lookup-id"
                        className="form-input"
                        style={{ flex: 1, backgroundColor: resLocked ? 'var(--bg-hover)' : 'inherit', cursor: resLocked ? 'not-allowed' : 'text' }}
                        disabled={resLocked}
                      />
                      {resLocked ? (
                        <button
                          type="button"
                          className="btn btn-ghost btn-icon"
                          onClick={() => {
                            setResLocked(false);
                            const box = document.getElementById("detail-lookup-resolution-result");
                            if (box) {
                              box.style.display = 'none';
                              box.innerHTML = '';
                              delete box.dataset.resolved;
                            }
                          }}
                          title="Edit Patient Identifier"
                          style={{ padding: '8px' }}
                        >
                          <Pencil size={14} />
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="btn btn-ghost"
                          onClick={async () => {
                            const identifierInput = document.getElementById("detail-popup-lookup-id").value;
                            if (!identifierInput.trim()) return;
                            try {
                              const res = await lookupPatient(identifierInput);
                              const box = document.getElementById("detail-lookup-resolution-result");
                              box.style.display = 'block';
                              if (res.data.exists) {
                                box.innerHTML = `
                                <div style="padding: 10px; border: 1px solid var(--p5-border); background: var(--p5-bg); border-radius: var(--r-md); font-size: 0.8rem; margin-top: 10px;">
                                  <h4 style="margin: 0 0 4px 0; color: var(--p5);">✓ Existing Patient Found</h4>
                                  <p style="margin: 2px 0;"><strong>Name:</strong> ${res.data.demographics.name}</p>
                                  <p style="margin: 2px 0;"><strong>Age/Sex:</strong> ${res.data.demographics.age}y / ${res.data.demographics.sex}</p>
                                  <p style="margin: 2px 0;"><strong>History:</strong> ${res.data.demographics.relevant_history || 'None'}</p>
                                  <p style="margin: 8px 0 0 0; font-size: 0.72rem; color: var(--text-secondary);">Click "Link and Merge Profile" to resolve identity.</p>
                                </div>
                              `;
                                box.dataset.resolved = JSON.stringify({
                                  patient_identifier: identifierInput,
                                  name: res.data.demographics.name,
                                  age: res.data.demographics.age,
                                  sex: res.data.demographics.sex,
                                  relevant_history: res.data.demographics.relevant_history,
                                });
                                setResLocked(true);
                              } else {
                                box.innerHTML = `
                                <div style="padding: 10px; border: 1px solid var(--border); background: var(--bg-hover); border-radius: var(--r-md); font-size: 0.8rem; margin-top: 10px;">
                                  <h4 style="margin: 0 0 4px 0; color: var(--text-secondary);">New Patient Identifier</h4>
                                  <p style="margin: 2px 0;">No past records found for standard ID <strong>${identifierInput}</strong>.</p>
                                  <p style="margin: 4px 0 0 0; font-size: 0.72rem; color: var(--text-secondary);">Click "Link and Merge Profile" to standardise identity with current details.</p>
                                </div>
                              `;
                                box.dataset.resolved = JSON.stringify({
                                  patient_identifier: identifierInput,
                                  name: patient.name,
                                  age: patient.age,
                                  sex: patient.sex,
                                  relevant_history: patient.relevant_history,
                                });
                                setResLocked(true);
                              }
                            } catch (err) {
                              alert("Lookup failed");
                            }
                          }}
                        >
                          Lookup
                        </button>
                      )}
                    </div>
                  </div>

                  <div id="detail-lookup-resolution-result" style={{ display: 'none', marginBottom: '20px' }}></div>

                  <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                    <button type="button" className="btn btn-ghost" onClick={closeActionModal}>Cancel</button>
                    <button type="button" className="btn btn-primary" onClick={async () => {
                      const box = document.getElementById("detail-lookup-resolution-result");
                      let resolved = {};
                      if (!box || !box.dataset.resolved) {
                        const identifierInput = document.getElementById("detail-popup-lookup-id").value;
                        if (!identifierInput.trim()) { alert("Enter a standard ID"); return; }
                        resolved = { patient_identifier: identifierInput };
                      } else {
                        resolved = JSON.parse(box.dataset.resolved);
                      }
                      try {
                        await api.patch(`/patients/${patient.id}/`, resolved);
                        alert("Identity resolved, demographic data updated and triage reassessed!");
                        closeActionModal();
                        load();
                      } catch (err) {
                        alert("Resolution failed");
                      }
                    }}>Link and Merge Profile</button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
