/** CommandCenter — primary ED overview page
 *  Header · Summary Cards · Live Queue · Alerts · Resources
 */
import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { getLiveQueue, getQueueStats, getAlerts, getResources, createPatient, lookupPatient, addVitals, addObservation, assessPatient, reassessPatient, aiAnalyze, api } from '../api'
import { useStore } from '../store'
import { useWebSocket } from '../useWebSocket'
import PriorityBadge from '../components/PriorityBadge'
import ConfidenceBadge from '../components/ConfidenceBadge'
import AlertCard from '../components/AlertCard'
import ResourceCapacityCard from '../components/ResourceCapacityCard'
import SimulationControls from '../components/SimulationControls'
import TopNavbar from '../components/TopNavbar'
import { Activity, Users, AlertTriangle, BarChart2, RefreshCw, Zap, Plus, Search, Brain, FileText, CheckCircle, ChevronRight, X, History, Pencil, User, LayoutGrid, Settings, Sparkles, Hourglass } from 'lucide-react'

const WAIT_WARN = 45   // minutes before yellow
const WAIT_CRIT = 90   // minutes before orange

function formatWait(min) {
  if (min == null) return '—'
  if (min < 60) return `${min}m`
  return `${Math.floor(min / 60)}h ${min % 60}m`
}

function waitClass(min) {
  if (min >= WAIT_CRIT) return 'very-long'
  if (min >= WAIT_WARN) return 'long'
  return ''
}

function shortId(id) {
  return id ? id.slice(0, 8).toUpperCase() : '—'
}

function formatDept(dept) {
  if (!dept) return 'Emergency Room';
  return dept
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());
}

function getAssignedDoc(patient) {
  const overrideBy = patient.latest_assessment?.clinician_override?.overridden_by;
  if (overrideBy) {
    return overrideBy;
  }
  
  const dept = (patient.current_destination || patient.current_queue || '').toLowerCase();
  if (dept.includes('cardiac')) return 'Dr. Kapoor (Cardio)';
  if (dept.includes('pediatr')) return 'Dr. Sharma (Peds)';
  if (dept.includes('ortho') || dept.includes('trauma')) return 'Dr. Roy (Ortho)';
  if (dept.includes('respir')) return 'Dr. Verma (Chest)';
  return 'Dr. Mehta (Duty)';
}

function vitalStatus(key, value, ageGroup) {
  if (value == null) return ''
  if (key === 'spo2' && value < 90) return 'critical'
  if (key === 'spo2' && value < 95) return 'abnormal'
  if (key === 'heart_rate' && (value > 150 || value < 40)) return 'critical'
  if (key === 'heart_rate' && (value > 100 || value < 60)) return 'abnormal'
  if (key === 'respiratory_rate' && (value > 30 || value < 8)) return 'critical'
  if (key === 'respiratory_rate' && (value > 20 || value < 12)) return 'abnormal'
  if (key === 'systolic_bp' && (value < 70 || value > 180)) return 'critical'
  if (key === 'systolic_bp' && (value < 90 || value > 160)) return 'abnormal'
  return ''
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
            name={name}
            className="vital-input-edit"
            defaultValue={defaultValue || ''}
            placeholder={unit || ''}
          />
        )
      ) : (
        <div className="vital-value-group">
          <span className="vital-value">{value != null ? value : '--'}</span>
          <span className="vital-unit">{unit}</span>
          <span className={`vital-status-badge ${badgeClass}`}>{badgeText}</span>
        </div>
      )}
    </div>
  );
}

export default function CommandCenter() {
  const navigate = useNavigate()
  const { queue, setQueue, alerts, setAlerts, setQueueStats, queueStats, resources, setResources, surgeActive, setSurge, wsConnected } = useStore()
  const [loading, setLoading] = useState(true)

  const [now, setNow] = useState(new Date())

  // Intake State
  const [showIntake, setShowIntake] = useState(false)
  const [searchId, setSearchId] = useState('')
  const [searchLoading, setSearchLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [lookupResult, setLookupResult] = useState(null)

  const [idType, setIdType] = useState('abha') // 'abha', 'aadhaar', 'mobile'
  const [isEmergency, setIsEmergency] = useState(false)
  const [validationError, setValidationError] = useState('')
  const [isLocked, setIsLocked] = useState(false)
  const [resLocked, setResLocked] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [filterTab, setFilterTab] = useState('all')
  const [sortBy, setSortBy] = useState('priority')

  // Pending Actions Modal State
  const [actionModal, setActionModal] = useState({
    isOpen: false,
    type: '', // 'vitals' or 'identity' or 'symptoms'
    patient: null
  })

  const [expandedSections, setExpandedSections] = useState({
    critical: true,
    deteriorating: true,
    vitalsPending: true,
    testsSuggested: true,
    surges: true,
    inVisit: false,
    completed: false,
    general: false
  })

  const closeActionModal = () => {
    setActionModal({ isOpen: false, type: '', patient: null });
    setResLocked(false);
  };

  function validateIdInput(value, type) {
    if (!value.trim()) return '';
    if (type === 'aadhaar') {
      const cleaned = value.replace(/\s+/g, '');
      if (!/^\d{12}$/.test(cleaned)) {
        return 'Aadhaar must be exactly 12 digits (e.g. 1234 5678 9012)';
      }
    } else if (type === 'abha') {
      // Accept: 14-digit number, XX-XXXX-XXXX-XXXX, ABHA address (name@abdm)
      const stripped = value.replace(/-/g, '');
      const isAbhaNum = /^\d{14}$/.test(stripped);
      const isAbhaAddr = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+$/.test(value);
      if (!isAbhaNum && !isAbhaAddr) {
        return 'ABHA must be 14 digits (e.g. 91-4221-5582-0001) or address (name@abdm)';
      }
    } else if (type === 'mobile') {
      const cleaned = value.replace(/\D/g, '');
      if (!/^[6-9]\d{9}$/.test(cleaned)) {
        return 'Mobile number must be a valid 10-digit Indian number';
      }
    }
    return '';
  }

  const handleIdChange = (val) => {
    setSearchId(val);
    setIntakeData(prev => ({ ...prev, patient_identifier: val }));
    const err = validateIdInput(val, idType);
    setValidationError(err);
  };

  const handleTypeChange = (type) => {
    setIdType(type);
    const err = validateIdInput(searchId, type);
    setValidationError(err);
  };

  const handleEmergencyToggle = (checked) => {
    setIsEmergency(checked);
    setIsLocked(false);
    if (checked) {
      const tempId = `TEMP-EMERGENCY-${Math.floor(1000 + Math.random() * 9000)}`;
      setSearchId(tempId);
      setIntakeData({
        name: 'Emergency Patient (Temp)',
        patient_identifier: tempId,
        age: '40',
        sex: 'U',
        chief_complaint: intakeData.chief_complaint,
        history_available: false,
        relevant_history: '',
      });
      setLookupResult({ exists: false, isTemp: true });
      setValidationError('');
    } else {
      setSearchId('');
      setIntakeData(prev => ({
        ...prev,
        name: '',
        patient_identifier: '',
        age: '',
        sex: 'M',
        relevant_history: '',
      }));
      setLookupResult(null);
    }
  };

  function handleQuickEmergencyIntake() {
    const tempId = `TEMP-EMERGENCY-${Math.floor(1000 + Math.random() * 9000)}`
    setIntakeData({
      name: 'Emergency Patient (Temp)',
      patient_identifier: tempId,
      sex: 'U',
      chief_complaint: '',
      history_available: false,
      relevant_history: '',
    })
    setLookupResult({ exists: false, isTemp: true })
    setSearchId(tempId)
    setIsEmergency(true)
    setIsLocked(false)
    setIdType('abha')
    setValidationError('')
    setShowIntake(true)
  }

  function handleNewIntakeClick() {
    setSearchId('')
    setIntakeData({
      name: '',
      patient_identifier: '',
      age: '',
      sex: 'M',
      chief_complaint: '',
      history_available: true,
      relevant_history: '',
    })
    setLookupResult(null)
    setIsEmergency(false)
    setIsLocked(false)
    setIdType('abha')
    setValidationError('')
    setShowIntake(true)
  }

  function handleRegisterWithoutId() {
    const tempId = `TEMP-${Math.floor(10000 + Math.random() * 90000)}`
    setIsEmergency(true)
    setIsLocked(false)
    setIdType('abha')
    setValidationError('')
    setSearchId(tempId)
    setIntakeData({
      name: '',
      patient_identifier: tempId,
      age: '',
      sex: 'M',
      chief_complaint: '',
      history_available: false,
      relevant_history: '',
    })
    setLookupResult({ exists: false, isTemp: true })
    setShowIntake(true)
  }

  const [intakeData, setIntakeData] = useState({
    name: '',
    patient_identifier: '',
    age: '',
    sex: 'M',
    chief_complaint: '',
    history_available: true,
    relevant_history: '',
  })

  async function handleSearch() {
    if (!searchId.trim()) return
    setSearchLoading(true)
    try {
      const res = await lookupPatient(searchId)
      if (res.data.exists) {
        setIntakeData(prev => ({
          ...prev,
          name: res.data.demographics.name || '',
          patient_identifier: searchId,
          age: res.data.demographics.age || '',
          sex: res.data.demographics.sex || 'M',
          relevant_history: res.data.demographics.relevant_history || '',
        }))
        setLookupResult({ exists: true })
        setIsLocked(false)
      } else {
        setIntakeData(prev => ({
          ...prev,
          name: '',
          patient_identifier: searchId,
          age: '',
          sex: 'M',
          relevant_history: '',
        }))
        setLookupResult({ exists: false, isTemp: false })
        setIsLocked(true)
      }
    } catch (e) {
      alert("Error looking up patient ID");
    } finally {
      setSearchLoading(false)
    }
  }

  async function handleSubmitIntake(e) {
    e.preventDefault();

    if (!isEmergency) {
      const err = validateIdInput(searchId, idType);
      if (err) {
        alert(`Validation Error: ${err}`);
        return;
      }
    }

    const finalData = { ...intakeData };
    finalData.arrival_time = new Date().toISOString();

    if (!finalData.patient_identifier) {
      alert("Patient ID is required.");
      return;
    }

    // Assign fallbacks if demographic info is empty
    if (!finalData.name) {
      finalData.name = finalData.patient_identifier.startsWith('TEMP-')
        ? 'Emergency Patient (Temp)'
        : `Patient (${finalData.patient_identifier})`;
    }
    if (!finalData.age) {
      finalData.age = 30; // fallback age
    }

    setSubmitting(true);
    try {
      // 1. Create Patient
      const patRes = await createPatient(finalData);
      const pId = patRes.data.id;

      // 2. Assess Patient
      await assessPatient({ patient_id: pId });

      // Clean up and navigate directly to the patient
      setShowIntake(false);
      navigate(`/patient/${pId}`);
    } catch (err) {
      alert(err?.response?.data?.error || err.message || "Error submitting patient intake.");
    } finally {
      setSubmitting(false);
    }
  }

  // Clock
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  const refresh = useCallback(async () => {
    try {
      const [qRes, sRes, aRes, rRes] = await Promise.all([
        getLiveQueue(), getQueueStats(), getAlerts({ active: 'true' }), getResources()
      ])
      setQueue(qRes.data)
      setQueueStats(sRes.data)
      setAlerts(aRes.data)
      setResources(rRes.data)
    } catch { }
    setLoading(false)
  }, [])

  const handleEscalate = async (e, patient) => {
    e.stopPropagation()
    const prioMap = { 'P5': 'P4', 'P4': 'P3', 'P3': 'P2', 'P2': 'P1', 'P1': 'P1' }
    const nextPrio = prioMap[patient.current_priority] || 'P1'
    try {
      await api.post(`/overrides/`, {
        patient_id: patient.id,
        override_priority: nextPrio,
        override_destination: patient.current_destination || 'general_medicine',
        override_rationale: "Clinician manual priority escalation.",
        overridden_by: "Dr. Admin"
      })
      alert(`Patient priority escalated to ${nextPrio}!`);
      refresh()
    } catch {
      alert("Failed to escalate priority");
    }
  }

  const handleDrop = async (e, patient) => {
    e.stopPropagation()
    if (!window.confirm("Are you sure you want to discharge/drop this patient from the queue?")) return
    try {
      await api.patch(`/patients/${patient.id}/`, {
        status: 'discharged'
      })
      alert("Patient discharged and dropped from queue!");
      refresh()
    } catch {
      alert("Failed to drop patient");
    }
  }

  const handleStartVisit = async (e, patient) => {
    e.stopPropagation()
    try {
      await api.patch(`/patients/${patient.id}/`, {
        status: 'in_progress'
      })
      alert("Patient visit started!");
      refresh()
    } catch {
      alert("Failed to start visit");
    }
  }

  useEffect(() => { refresh() }, [])
  // Poll every 15s as backup
  useEffect(() => {
    const t = setInterval(refresh, 15000)
    return () => clearInterval(t)
  }, [refresh])

  // WebSocket real-time updates
  useWebSocket((msg) => {
    if (msg.type === 'priority.changed' || msg.type === 'patient.created' || msg.type === 'patient.updated') {
      refresh()
    }
    if (msg.type === 'alert.created') {
      setAlerts(prev => [msg.payload, ...prev])
    }
    if (msg.type === 'surge.started') {
      setSurge(true)
      refresh()
    }
    if (msg.type === 'simulation.reset') {
      refresh()
    }
  })

  const activeAlerts = alerts.filter(a => !a.acknowledged_at)
  const p1p2 = queueStats?.p1_p2_count ?? queue.filter(p => p.current_priority === 'P1' || p.current_priority === 'P2').length

  const criticalPts = queue.filter(p => (p.current_priority === 'P1' || p.current_priority === 'P2') && p.status === 'waiting')
  
  const deterioratingPts = queue.filter(p => 
    (p.scenario_tag === 'deteriorating' || activeAlerts.some(a => a.patient_id === p.id && a.alert_type === 'deterioration')) && 
    p.status === 'waiting' && 
    p.current_priority !== 'P1' && 
    p.current_priority !== 'P2'
  )
  
  const vitalsPendingPts = queue.filter(p => !p.latest_vitals && p.status === 'waiting')
  
  const testsSuggestedPts = queue.filter(p => 
    p.latest_vitals && 
    p.latest_assessment?.ai_decision_support?.preliminary_tests?.length > 0 && 
    p.status === 'waiting' && 
    p.current_priority !== 'P1' && 
    p.current_priority !== 'P2'
  )
  
  const surgePts = queue.filter(p => p.scenario_tag === 'surge' && p.status === 'waiting')
  
  const inVisitPts = queue.filter(p => p.status === 'in_progress')
  
  const completedPts = queue.filter(p => p.status === 'discharged' || p.status === 'admitted')
  
  const generalPts = queue.filter(p => 
    p.status === 'waiting' && 
    p.latest_vitals && 
    (!p.latest_assessment?.ai_decision_support?.preliminary_tests || p.latest_assessment?.ai_decision_support?.preliminary_tests?.length === 0) && 
    p.current_priority !== 'P1' && 
    p.current_priority !== 'P2' && 
    p.scenario_tag !== 'deteriorating' && 
    p.scenario_tag !== 'surge'
  )

  function renderQueueCard(title, patients, bgHex, textHex, description) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', minHeight: '180px' }}>
        {/* Title Outside */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.88rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--text-primary)' }}>{title}</span>
            <span className="badge" style={{ background: bgHex, color: textHex, fontSize: '0.78rem', padding: '2px 8px', borderRadius: '4px', fontWeight: 700 }}>
              {patients.length}
            </span>
          </div>
        </div>
        {description && (
          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: '0 0 12px 0', lineHeight: 1.4 }}>{description}</p>
        )}

        {/* Subtable Container (Borderless) */}
        <div 
          style={{ 
            background: 'transparent', 
            display: 'flex',
            flexDirection: 'column'
          }}
        >
          {/* Subtable Header */}
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: '1fr 180px 80px', 
            gap: '12px', 
            padding: '8px 0', 
            borderBottom: '2px solid var(--border)',
            fontSize: '0.72rem',
            fontWeight: 700,
            textTransform: 'uppercase',
            color: 'var(--text-muted)',
            letterSpacing: '0.05em'
          }}>
            <span>Patient Info</span>
            <span>Suggested Tests</span>
            <span style={{ textAlign: 'right', paddingRight: '14px' }}>Wait</span>
          </div>

          {/* Subtable Body (Scrollable) */}
          <div 
            style={{ 
              overflowY: 'auto', 
              display: 'flex', 
              flexDirection: 'column', 
              maxHeight: 'calc(100vh - 350px)' 
            }}
            className="left-pane" // Custom scrollbar
          >
            {patients.length === 0 ? (
              <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                No patients in queue
              </div>
            ) : (
              patients.map((p, idx) => {
                const waitTime = Math.floor((now - new Date(p.arrival_time)) / 60000)
                const latestAss = p.latest_assessment
                const isLast = idx === patients.length - 1

                return (
                  <div
                    key={p.id}
                    onClick={() => navigate(`/patient/${p.id}`)}
                    className="queue-table-row"
                    title="Click to see full details"
                    style={{ 
                      display: 'grid', 
                      gridTemplateColumns: '1fr 180px 80px', 
                      gap: '12px', 
                      alignItems: 'center', 
                      padding: '12px 0',
                      borderBottom: '1px solid var(--border)',
                      cursor: 'pointer',
                      background: 'transparent'
                    }}
                  >
                    {/* Col 1: Core Patient Info */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', overflow: 'hidden' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                        <span className="patient-card-name" style={{ fontSize: '0.92rem', fontWeight: 700, margin: 0 }}>
                          {p.name || 'Anonymous Patient'}
                        </span>
                        <PriorityBadge priority={p.current_priority} />
                        {latestAss?.confidence != null && (
                          <span 
                            className="badge" 
                            style={{ 
                              background: 'rgba(124, 58, 237, 0.05)', 
                              color: 'var(--accent)', 
                              border: '1px solid rgba(124, 58, 237, 0.15)', 
                              fontSize: '0.7rem', 
                              padding: '1px 5px', 
                              borderRadius: '4px',
                              fontWeight: 700,
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '3px'
                            }}
                          >
                            <Brain size={10} />
                            {Math.round(latestAss.confidence * 100)}% AI Conf
                          </span>
                        )}
                      </div>
                      
                      {/* Dept & Assigned Doctor Info */}
                      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', fontSize: '0.78rem', marginTop: '2px' }}>
                        <span>
                          <strong style={{ color: 'var(--text-secondary)' }}>Dept:</strong>{' '}
                          <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                            {formatDept(p.current_destination || p.current_queue || 'Triage')}
                          </span>
                        </span>
                        <span>
                          <strong style={{ color: 'var(--text-secondary)' }}>Doc:</strong>{' '}
                          <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                            {getAssignedDoc(p)}
                          </span>
                        </span>
                      </div>

                      <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                        <span>{p.age}y {p.age_group} · {p.sex}</span>
                      </div>
                      <div className="patient-card-complaint" style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: 0 }}>
                        {p.chief_complaint || 'No chief complaint recorded.'}
                      </div>
                    </div>

                    {/* Col 2: Suggested Tests/Scans (Aligned Column) */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', overflow: 'hidden', minWidth: '170px' }}>
                      {latestAss?.ai_decision_support?.preliminary_tests?.length > 0 ? (
                        latestAss.ai_decision_support.preliminary_tests.slice(0, 2).map((test, i) => (
                          <span 
                            key={i} 
                            className="badge" 
                            style={{ 
                              background: 'rgba(59, 130, 246, 0.06)', 
                              color: '#3b82f6', 
                              border: '1px solid rgba(59, 130, 246, 0.15)', 
                              fontSize: '0.65rem', 
                              padding: '2px 6px', 
                              borderRadius: '3px',
                              textOverflow: 'ellipsis',
                              overflow: 'hidden',
                              whiteSpace: 'nowrap',
                              display: 'block',
                              textAlign: 'center',
                              fontWeight: 600
                            }}
                            title={test}
                          >
                            {test}
                          </span>
                        ))
                      ) : (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontStyle: 'italic', textAlign: 'center', display: 'block' }}>—</span>
                      )}
                    </div>

                    {/* Col 3: Wait Time & Action Arrow */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'flex-end' }}>
                      <span className={`patient-card-wait ${waitClass(waitTime)}`} style={{ fontSize: '0.78rem', fontWeight: 700 }}>
                        {formatWait(waitTime)}
                      </span>
                      <ChevronRight size={14} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>
      </div>
    );
  }

  // 1. Filtering
  let filteredPatients = [...queue]

  if (searchTerm) {
    const term = searchTerm.toLowerCase()
    filteredPatients = filteredPatients.filter(p => 
      p.name?.toLowerCase().includes(term) ||
      p.patient_identifier?.toLowerCase().includes(term) ||
      p.chief_complaint?.toLowerCase().includes(term)
    )
  }

  if (filterTab === 'critical') {
    filteredPatients = filteredPatients.filter(p => p.current_priority === 'P1' || p.current_priority === 'P2')
  } else if (filterTab === 'vitals_pending') {
    filteredPatients = filteredPatients.filter(p => {
      const ass = p.latest_assessment
      return !ass || !ass.vitals || Object.keys(ass.vitals).length === 0
    })
  } else if (filterTab === 'tests_suggested') {
    filteredPatients = filteredPatients.filter(p => p.latest_assessment?.ai_decision_support?.preliminary_tests?.length > 0)
  } else if (filterTab === 'active_visits') {
    filteredPatients = filteredPatients.filter(p => p.status === 'in_progress')
  }

  // 2. Sorting
  filteredPatients.sort((a, b) => {
    if (sortBy === 'priority') {
      const prioMap = { 'P1': 1, 'P2': 2, 'P3': 3, 'P4': 4, 'P5': 5 }
      const aVal = prioMap[a.current_priority] || 99
      const bVal = prioMap[b.current_priority] || 99
      if (aVal !== bVal) return aVal - bVal
      return new Date(a.arrival_time) - new Date(b.arrival_time)
    } else if (sortBy === 'wait_time') {
      return new Date(a.arrival_time) - new Date(b.arrival_time)
    } else if (sortBy === 'name') {
      return (a.name || '').localeCompare(b.name || '')
    }
    return 0
  })

  return (
    <div className="app-container" style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: 'var(--bg-base)', width: '100%' }}>
      {/* Top Navbar */}
      <TopNavbar 
        activeTab="queue" 
        surgeActive={surgeActive} 
        loading={loading} 
        onRefresh={refresh} 
        onNewIntake={handleNewIntakeClick} 
      />

      {/* Main View Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', width: '100%', overflow: 'hidden' }}>
        <main className="main-content" style={{ padding: '24px', flex: 1, display: 'flex', gap: '24px', boxSizing: 'border-box', width: '100%', overflow: 'hidden' }}>
          {/* Left Column: Filter & Controls Panel (width: 240px) */}
          <div style={{ 
            width: '240px', 
            flexShrink: 0, 
            display: 'flex', 
            flexDirection: 'column', 
            gap: '20px',
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--r-md)',
            padding: '16px',
            boxShadow: 'var(--shadow-sm)',
            height: 'fit-content'
          }}>
            
            {/* Search Input */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)' }}>Search Patient</label>
              <div style={{ position: 'relative' }}>
                <input 
                  type="text" 
                  placeholder="Search..." 
                  value={searchTerm} 
                  onChange={e => setSearchTerm(e.target.value)} 
                  style={{ 
                    width: '100%', 
                    padding: '8px 12px 8px 32px', 
                    borderRadius: '6px', 
                    border: '1px solid var(--border)', 
                    background: 'var(--bg-card)', 
                    color: 'var(--text-primary)',
                    fontSize: '0.85rem'
                  }} 
                />
                <Search size={14} style={{ position: 'absolute', left: '10px', top: '11px', color: 'var(--text-muted)' }} />
              </div>
            </div>


            {/* Sorting Controls */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)' }}>Sort By</label>
              <select 
                value={sortBy} 
                onChange={e => setSortBy(e.target.value)} 
                style={{ 
                  width: '100%', 
                  padding: '8px 12px', 
                  borderRadius: '6px', 
                  border: '1px solid var(--border)', 
                  background: 'var(--bg-card)', 
                  color: 'var(--text-primary)',
                  fontSize: '0.85rem',
                  cursor: 'pointer'
                }}
              >
                <option value="priority">Priority (High-Low)</option>
                <option value="wait_time">Wait Time (Longest)</option>
                <option value="name">Patient Name</option>
              </select>
            </div>

            {/* Filter Tabs list */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)' }}>Filter Board</label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <button 
                  onClick={() => setFilterTab('all')} 
                  style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center', 
                    padding: '10px 12px', 
                    borderRadius: '6px', 
                    border: 'none', 
                    background: filterTab === 'all' ? 'rgba(124, 58, 237, 0.08)' : 'transparent', 
                    color: filterTab === 'all' ? 'var(--accent)' : 'var(--text-secondary)',
                    fontWeight: filterTab === 'all' ? 700 : 500,
                    fontSize: '0.85rem', 
                    textAlign: 'left',
                    cursor: 'pointer'
                  }}
                >
                  <span>All Queue</span>
                  <span className="badge" style={{ background: filterTab === 'all' ? 'var(--accent)' : 'var(--border)', color: filterTab === 'all' ? '#fff' : 'var(--text-secondary)' }}>
                    {queue.length}
                  </span>
                </button>
                
                <button 
                  onClick={() => setFilterTab('critical')} 
                  style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center', 
                    padding: '10px 12px', 
                    borderRadius: '6px', 
                    border: 'none', 
                    background: filterTab === 'critical' ? 'rgba(220, 38, 38, 0.08)' : 'transparent', 
                    color: filterTab === 'critical' ? 'var(--p1)' : 'var(--text-secondary)',
                    fontWeight: filterTab === 'critical' ? 700 : 500,
                    fontSize: '0.85rem', 
                    textAlign: 'left',
                    cursor: 'pointer'
                  }}
                >
                  <span>Critical (P1/P2)</span>
                  <span className="badge" style={{ background: filterTab === 'critical' ? 'var(--p1)' : 'var(--border)', color: filterTab === 'critical' ? '#fff' : 'var(--text-secondary)' }}>
                    {queue.filter(p => p.current_priority === 'P1' || p.current_priority === 'P2').length}
                  </span>
                </button>

                <button 
                  onClick={() => setFilterTab('vitals_pending')} 
                  style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center', 
                    padding: '10px 12px', 
                    borderRadius: '6px', 
                    border: 'none', 
                    background: filterTab === 'vitals_pending' ? 'rgba(234, 179, 8, 0.08)' : 'transparent', 
                    color: filterTab === 'vitals_pending' ? 'var(--p3)' : 'var(--text-secondary)',
                    fontWeight: filterTab === 'vitals_pending' ? 700 : 500,
                    fontSize: '0.85rem', 
                    textAlign: 'left',
                    cursor: 'pointer'
                  }}
                >
                  <span>Vitals Pending</span>
                  <span className="badge" style={{ background: filterTab === 'vitals_pending' ? 'var(--p3)' : 'var(--border)', color: filterTab === 'vitals_pending' ? '#fff' : 'var(--text-secondary)' }}>
                    {queue.filter(p => !p.latest_assessment || !p.latest_assessment.vitals || Object.keys(p.latest_assessment.vitals).length === 0).length}
                  </span>
                </button>

                <button 
                  onClick={() => setFilterTab('tests_suggested')} 
                  style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center', 
                    padding: '10px 12px', 
                    borderRadius: '6px', 
                    border: 'none', 
                    background: filterTab === 'tests_suggested' ? 'rgba(59, 130, 246, 0.08)' : 'transparent', 
                    color: filterTab === 'tests_suggested' ? '#3b82f6' : 'var(--text-secondary)',
                    fontWeight: filterTab === 'tests_suggested' ? 700 : 500,
                    fontSize: '0.85rem', 
                    textAlign: 'left',
                    cursor: 'pointer'
                  }}
                >
                  <span>Tests Suggested</span>
                  <span className="badge" style={{ background: filterTab === 'tests_suggested' ? '#3b82f6' : 'var(--border)', color: filterTab === 'tests_suggested' ? '#fff' : 'var(--text-secondary)' }}>
                    {queue.filter(p => p.latest_assessment?.ai_decision_support?.preliminary_tests?.length > 0).length}
                  </span>
                </button>

                <button 
                  onClick={() => setFilterTab('active_visits')} 
                  style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center', 
                    padding: '10px 12px', 
                    borderRadius: '6px', 
                    border: 'none', 
                    background: filterTab === 'active_visits' ? 'rgba(16, 185, 129, 0.08)' : 'transparent', 
                    color: filterTab === 'active_visits' ? 'var(--p5)' : 'var(--text-secondary)',
                    fontWeight: filterTab === 'active_visits' ? 700 : 500,
                    fontSize: '0.85rem', 
                    textAlign: 'left',
                    cursor: 'pointer'
                  }}
                >
                  <span>Active Visits</span>
                  <span className="badge" style={{ background: filterTab === 'active_visits' ? 'var(--p5)' : 'var(--border)', color: filterTab === 'active_visits' ? '#fff' : 'var(--text-secondary)' }}>
                    {queue.filter(p => p.status === 'in_progress').length}
                  </span>
                </button>
              </div>
            </div>


            <SimulationControls onRefresh={refresh} selectedPatientId={queue[0]?.id} />
            <div style={{ flex: 1 }} />
          </div>

          {/* Right Column: Unified Patient Board Table (fills remaining space) */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '16px', overflow: 'hidden' }}>
            
            {/* ED Status Ribbon */}
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '24px', 
              padding: '12px 18px', 
              background: 'var(--bg-card)', 
              border: '1px solid var(--border)', 
              borderRadius: 'var(--r-md)', 
              fontSize: '0.82rem',
              color: 'var(--text-secondary)',
              flexWrap: 'wrap',
              boxShadow: 'var(--shadow-sm)'
            }}>
              <span style={{ fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.04em', fontSize: '0.78rem' }}>ED Status Ribbon:</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--p1)' }}></span>
                <strong>{p1p2}</strong> Urgent (P1/P2)
              </span>
              <span style={{ color: 'var(--border)' }}>|</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--p3)' }}></span>
                <strong>{queueStats?.total_waiting ?? queue.length}</strong> Waiting
              </span>
              <span style={{ color: 'var(--border)' }}>|</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--p2)' }}></span>
                <strong>{activeAlerts.length}</strong> Alerts ({activeAlerts.filter(a => a.severity === 'CRITICAL').length} Crit)
              </span>
              <span style={{ color: 'var(--border)' }}>|</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#3b82f6' }}></span>
                <strong>{queueStats?.average_resource_utilisation != null ? `${Math.round(queueStats.average_resource_utilisation)}%` : '—'}</strong> Bed Occupancy
              </span>
            </div>

            {surgeActive && (
              <div className="surge-banner" style={{ borderRadius: 'var(--r-md)', margin: 0 }}>
                <AlertTriangle size={14} />
                <span>ED is experiencing surge behavior (3x arrivals). Triage thresholds adjusted.</span>
              </div>
            )}

            {/* Main Board Table */}
            <div 
              style={{ 
                background: 'var(--bg-card)', 
                border: '1px solid var(--border)',
                borderRadius: 'var(--r-md)', 
                display: 'flex', 
                flexDirection: 'column', 
                flex: 1, 
                overflow: 'hidden' 
              }}
            >
              {/* Table Header */}
              <div style={{ 
                display: 'grid', 
                gridTemplateColumns: '1.2fr 80px 1.2fr 1.2fr 75px 110px 240px', 
                gap: '12px', 
                padding: '12px 20px', 
                background: 'var(--bg-hover)', 
                borderBottom: '1px solid var(--border)', 
                fontSize: '0.72rem', 
                fontWeight: 700, 
                textTransform: 'uppercase', 
                color: 'var(--text-muted)',
                letterSpacing: '0.04em'
              }}>
                <span>Patient Info</span>
                <span>Triage</span>
                <span>Dept & Clinician</span>
                <span>Suggested Scans/Tests</span>
                <span style={{ textAlign: 'right' }}>Wait</span>
                <span style={{ textAlign: 'center' }}>AI Confidence</span>
                <span style={{ textAlign: 'right' }}>Actions</span>
              </div>

              {/* Table Body (Scrollable) */}
              <div 
                className="left-pane" 
                style={{ 
                  overflowY: 'auto', 
                  flex: 1, 
                  maxHeight: 'calc(100vh - 240px)',
                  display: 'flex',
                  flexDirection: 'column',
                  background: 'var(--bg-hover)'
                }}
              >
                {filteredPatients.length === 0 ? (
                  <div style={{ padding: '48px', textAlign: 'center', color: 'var(--text-muted)' }}>
                    No patients found matching the selected filter/criteria.
                  </div>
                ) : (
                  filteredPatients.map((p, idx) => {
                    const waitTime = Math.floor((now - new Date(p.arrival_time)) / 60000)
                    const latestAss = p.latest_assessment
                    const isLast = idx === filteredPatients.length - 1

                    const hasVitals = latestAss?.vitals && Object.keys(latestAss.vitals).length > 0
                    const hasTests = latestAss?.ai_decision_support?.preliminary_tests?.length > 0
                    const isWaiting = p.status === 'waiting'
                    const isInProgress = p.status === 'in_progress'
                    const isDone = p.status === 'discharged' || p.status === 'admitted'

                    // Stage computation:
                    // 0: Vitals Pending (if no vitals)
                    // 1: Tests Suggested/Ordered (if vitals exist, and tests suggested)
                    // 2: In Queue / Waiting (if vitals exist, no tests suggested or tests approved/ordered, status is waiting)
                    // 3: Being Checked (if status is in_progress)
                    // 4: Done (if discharged or admitted)
                    let activeIndex = 0
                    if (isDone) {
                      activeIndex = 4
                    } else if (isInProgress) {
                      activeIndex = 3
                    } else if (isWaiting) {
                      if (hasTests) {
                        activeIndex = 1
                      } else {
                        activeIndex = 2
                      }
                    } else if (hasVitals) {
                      if (hasTests) {
                        activeIndex = 1
                      } else {
                        activeIndex = 2
                      }
                    }

                    return (
                      <div
                        key={p.id}
                        onClick={() => navigate(`/patient/${p.id}`)}
                        className="queue-table-row"
                        style={{
                          display: 'grid',
                          gridTemplateColumns: '1.2fr 80px 1.2fr 1.2fr 75px 110px 240px',
                          gap: '12px',
                          padding: '14px 20px',
                          alignItems: 'center',
                          borderBottom: isLast ? 'none' : '1px solid var(--border)',
                          cursor: 'pointer',
                          background: idx % 2 === 0 ? 'var(--bg-card)' : 'var(--bg-hover)'
                        }}
                      >
                        {/* Col 1: Patient Details */}
                        <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                          <span style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {p.name || 'Anonymous Patient'}
                          </span>
                          <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                            {p.age}y · {p.sex} · {p.age_group}
                          </span>
                          <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginTop: '2px' }}>
                            {p.chief_complaint || 'No chief complaint.'}
                          </span>

                          {/* Stepper Pipeline: Vital -> Test -> In Queue -> Checked -> Done */}
                          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '6px', flexWrap: 'wrap' }}>
                            <span style={{ color: activeIndex >= 1 ? 'var(--p5)' : 'var(--p1)', fontWeight: activeIndex === 0 ? 'bold' : 'normal' }}>Vitals</span>
                            <span>→</span>
                            <span style={{ color: activeIndex >= 2 ? 'var(--p5)' : activeIndex === 1 ? '#3b82f6' : 'inherit', fontWeight: activeIndex === 1 ? 'bold' : 'normal' }}>Tests</span>
                            <span>→</span>
                            <span style={{ color: activeIndex >= 3 ? 'var(--p5)' : activeIndex === 2 ? 'var(--p2)' : 'inherit', fontWeight: activeIndex === 2 ? 'bold' : 'normal' }}>InQueue</span>
                            <span>→</span>
                            <span style={{ color: activeIndex >= 4 ? 'var(--p5)' : activeIndex === 3 ? 'var(--p5)' : 'inherit', fontWeight: activeIndex === 3 ? 'bold' : 'normal' }}>Checked</span>
                            <span>→</span>
                            <span style={{ color: activeIndex === 4 ? 'var(--p5)' : 'inherit', fontWeight: activeIndex === 4 ? 'bold' : 'normal' }}>Done</span>
                          </div>
                        </div>

                        {/* Col 2: Triage Priority */}
                        <div>
                          <PriorityBadge priority={p.current_priority} />
                        </div>

                        {/* Col 3: Department and Doctor */}
                        <div style={{ display: 'flex', flexDirection: 'column', fontSize: '0.8rem', color: 'var(--text-primary)' }}>
                          <span>
                            <strong style={{ color: 'var(--text-secondary)', fontSize: '0.72rem' }}>DEPT:</strong>{' '}
                            <strong>{formatDept(p.current_destination || p.current_queue)}</strong>
                          </span>
                          <span style={{ marginTop: '2px' }}>
                            <strong style={{ color: 'var(--text-secondary)', fontSize: '0.72rem' }}>DOC:</strong>{' '}
                            <span style={{ fontWeight: 600 }}>{getAssignedDoc(p)}</span>
                          </span>
                        </div>

                        {/* Col 4: Suggested Diagnostic Tests */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', overflow: 'hidden' }}>
                          {latestAss?.ai_decision_support?.preliminary_tests?.length > 0 ? (
                            latestAss.ai_decision_support.preliminary_tests.slice(0, 2).map((test, i) => (
                              <span 
                                key={i} 
                                className="badge" 
                                style={{ 
                                  background: 'rgba(59, 130, 246, 0.05)', 
                                  color: '#3b82f6', 
                                  border: '1px solid rgba(59, 130, 246, 0.15)', 
                                  fontSize: '0.68rem', 
                                  padding: '1px 6px', 
                                  borderRadius: '3px',
                                  whiteSpace: 'nowrap',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  display: 'block',
                                  width: 'fit-content'
                                }}
                                title={test}
                              >
                                {test}
                              </span>
                            ))
                          ) : (
                            <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>None recommended</span>
                          )}
                        </div>

                        {/* Col 5: Wait Time */}
                        <div style={{ textAlign: 'right' }}>
                          <span className={`patient-card-wait ${waitClass(waitTime)}`} style={{ fontSize: '0.82rem', fontWeight: 700 }}>
                            {formatWait(waitTime)}
                          </span>
                        </div>

                        {/* Col 6: AI Confidence */}
                        <div style={{ textAlign: 'center' }}>
                          {latestAss?.confidence != null ? (
                            <span 
                              className="badge" 
                              style={{ 
                                background: 'rgba(124, 58, 237, 0.05)', 
                                color: 'var(--accent)', 
                                border: '1px solid rgba(124, 58, 237, 0.15)', 
                                fontSize: '0.74rem', 
                                padding: '3px 8px', 
                                borderRadius: '4px',
                                fontWeight: 700,
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '3px'
                              }}
                            >
                              <Brain size={10} />
                              {Math.round(latestAss.confidence * 100)}%
                            </span>
                          ) : (
                            <span style={{ color: 'var(--text-muted)', fontSize: '0.76rem' }}>—</span>
                          )}
                        </div>

                        {/* Col 7: Context-aware CTA button */}
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '6px' }}>
                          {activeIndex === 0 ? (
                            <button 
                              className="btn btn-outline-warning btn-sm" 
                              onClick={(e) => { e.stopPropagation(); navigate(`/patient/${p.id}`) }}
                              style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', padding: '4px 8px', minWidth: '110px', justifyContent: 'center' }}
                            >
                              <Activity size={12} />
                              Record Vitals
                            </button>
                          ) : activeIndex === 1 ? (
                            <button 
                              className="btn btn-primary btn-sm" 
                              onClick={async (e) => { 
                                e.stopPropagation(); 
                                try {
                                  await api.post(`/overrides/`, {
                                    patient_id: p.id,
                                    override_priority: p.current_priority,
                                    override_destination: p.current_destination || 'general_medicine',
                                    override_rationale: "Approved AI suggested diagnostics.",
                                    overridden_by: "Dr. Admin"
                                  });
                                  alert("Suggested preliminary scans approved!");
                                  refresh();
                                } catch {
                                  alert("Failed to approve scans");
                                }
                              }}
                              style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', padding: '4px 8px', minWidth: '110px', justifyContent: 'center' }}
                            >
                              <CheckCircle size={12} />
                              Approve Scans
                            </button>
                          ) : activeIndex === 2 ? (
                            <button 
                              className="btn btn-outline-danger btn-sm" 
                              onClick={async (e) => {
                                e.stopPropagation();
                                try {
                                  await reassessPatient({ patient_id: p.id, trigger: 'manual_reassessment' });
                                  alert("Triage reassessment computed successfully!");
                                  refresh();
                                } catch {
                                  alert("Failed to reassess patient");
                                }
                              }}
                              style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', padding: '4px 8px', minWidth: '110px', justifyContent: 'center' }}
                            >
                              <RefreshCw size={12} />
                              Reassess
                            </button>
                          ) : activeIndex === 3 ? (
                            <button 
                              className="btn btn-outline-success btn-sm" 
                              onClick={(e) => { e.stopPropagation(); navigate(`/patient/${p.id}`) }}
                              style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', padding: '4px 8px', minWidth: '110px', justifyContent: 'center' }}
                            >
                              Done & History
                            </button>
                          ) : (
                            <button 
                              className="btn btn-ghost btn-sm" 
                              onClick={(e) => { e.stopPropagation(); navigate(`/patient/${p.id}`) }}
                              style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', padding: '4px 8px', border: '1px solid var(--border)', minWidth: '110px', justifyContent: 'center' }}
                            >
                              Details
                            </button>
                          )}
                          <ChevronRight size={14} className="hover-arrow" style={{ color: 'var(--text-muted)', marginLeft: '4px', transition: 'all 0.2s' }} />
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          </div>
        </main>


        {/* Intake Drawer Modal */}
        {showIntake && (
          <div className="dialog-overlay" onClick={e => e.target === e.currentTarget && setShowIntake(false)}>
            <div className="dialog-box" style={{ maxWidth: '540px', width: '90vw' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border)', paddingBottom: 'var(--sp-2)', marginBottom: 'var(--sp-4)' }}>
                <h2 className="dialog-title" style={{ margin: 0 }}>
                  {isEmergency ? 'Register Without ID' : 'Patient Intake'}
                </h2>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {!isEmergency && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textDecoration: 'underline' }}
                      onClick={handleRegisterWithoutId}
                    >
                      Register without ID
                    </button>
                  )}
                  {isEmergency && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}
                      onClick={() => {
                        setIsEmergency(false)
                        setSearchId('')
                        setIntakeData(prev => ({ ...prev, patient_identifier: '', name: '', age: '', sex: 'M' }))
                        setLookupResult(null)
                      }}
                    >
                      Back to Lookup
                    </button>
                  )}
                  <button className="btn btn-ghost btn-icon" onClick={() => setShowIntake(false)} aria-label="Close">
                    <X size={16} />
                  </button>
                </div>
              </div>

              {isEmergency && (
                <div style={{ background: 'rgba(220,38,38,0.06)', border: '1px solid rgba(220,38,38,0.2)', padding: '10px 12px', borderRadius: 'var(--r-md)', marginBottom: '16px' }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--p1)', fontWeight: 600 }}>Registering without ID</span>
                  <p style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', margin: '2px 0 0 0' }}>
                    Temporary ID assigned: <strong>{intakeData.patient_identifier}</strong>. Resolve identity later from the patient record.
                  </p>
                </div>
              )}

              {!isEmergency && (
                <div style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)', padding: '12px', borderRadius: 'var(--r-md)', marginBottom: '16px' }}>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 600, display: 'block', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Search Existing Registry
                  </span>

                  <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
                    {['abha', 'aadhaar', 'mobile'].map(t => (
                      <button
                        key={t}
                        type="button"
                        className={`btn btn-sm ${idType === t ? 'btn-primary' : 'btn-ghost'}`}
                        style={{ textTransform: 'uppercase', fontSize: '0.65rem' }}
                        onClick={() => handleTypeChange(t)}
                      >
                        {t}
                      </button>
                    ))}
                  </div>

                  <div style={{ display: 'flex', gap: '8px' }}>
                    <input
                      type="text"
                      className="form-input"
                      placeholder={idType === 'abha' ? 'e.g. 91-4221-5582-0001 or name@abdm' : idType === 'aadhaar' ? '12-digit Aadhaar number' : '10-digit mobile number'}
                      value={searchId}
                      style={{ flex: 1, backgroundColor: isLocked ? 'var(--bg-hover)' : 'inherit', cursor: isLocked ? 'not-allowed' : 'text' }}
                      disabled={isLocked}
                      onChange={e => handleIdChange(e.target.value)}
                    />
                    {isLocked ? (
                      <button
                        type="button"
                        className="btn btn-ghost btn-icon"
                        onClick={() => {
                          setIsLocked(false);
                          setLookupResult(null);
                        }}
                        title="Edit Identifier"
                      >
                        <Pencil size={14} />
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="btn btn-ghost"
                        onClick={handleSearch}
                        disabled={searchLoading || !!validationError || !searchId.trim()}
                      >
                        {searchLoading ? 'Searching…' : 'Lookup'}
                      </button>
                    )}
                  </div>

                  {validationError && (
                    <p style={{ color: 'var(--p1)', fontSize: '0.72rem', margin: '4px 0 0 0' }}>{validationError}</p>
                  )}

                  {lookupResult && (
                    <div style={{ marginTop: '10px' }}>
                      {lookupResult.exists ? (
                        <div style={{ padding: '12px 14px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                            <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'var(--accent)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '1rem', flexShrink: 0 }}>
                              {intakeData.name ? intakeData.name.charAt(0).toUpperCase() : '?'}
                            </div>
                            <div>
                              <p style={{ fontWeight: 700, fontSize: '0.9rem', margin: 0 }}>{intakeData.name || '—'}</p>
                              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0 }}>
                                {intakeData.age ? `${intakeData.age}y` : ''}{intakeData.sex ? ` · ${intakeData.sex === 'M' ? 'Male' : intakeData.sex === 'F' ? 'Female' : 'Other'}` : ''}
                              </p>
                            </div>
                          </div>
                          <button
                            type="button"
                            className="btn btn-primary"
                            style={{ width: '100%', justifyContent: 'center' }}
                            disabled={submitting}
                            onClick={e => handleSubmitIntake({ preventDefault: () => {} })}
                          >
                            {submitting ? 'Registering…' : 'Continue with this patient →'}
                          </button>
                        </div>
                      ) : (
                        <div style={{ padding: '8px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', color: 'var(--text-secondary)', fontSize: '0.78rem' }}>
                          No record found. Complete registration details below to create a new profile.
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              <form onSubmit={handleSubmitIntake}>
                {(!lookupResult?.exists) && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 120px 100px', gap: '12px', marginBottom: '12px' }}>
                    <div className="form-group">
                      <label className="form-label" htmlFor="intake-name">Patient Name {isEmergency && <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(optional)</span>}</label>
                      <input
                        type="text"
                        id="intake-name"
                        className="form-input"
                        value={intakeData.name}
                        onChange={e => setIntakeData(prev => ({ ...prev, name: e.target.value }))}
                        placeholder={isEmergency ? 'Leave blank to assign temporary name' : 'e.g. John Doe'}
                        required={!isEmergency}
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label" htmlFor="intake-age">Age (years) {isEmergency && <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(optional)</span>}</label>
                      <input
                        type="number"
                        id="intake-age"
                        className="form-input"
                        value={intakeData.age}
                        onChange={e => setIntakeData(prev => ({ ...prev, age: e.target.value }))}
                        placeholder="e.g. 45"
                        required={!isEmergency}
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label" htmlFor="intake-sex">Sex</label>
                      <select
                        id="intake-sex"
                        className="form-select"
                        value={intakeData.sex}
                        onChange={e => setIntakeData(prev => ({ ...prev, sex: e.target.value }))}
                      >
                        <option value="M">Male</option>
                        <option value="F">Female</option>
                        <option value="U">Other</option>
                      </select>
                    </div>
                  </div>
                )}

                {(!lookupResult?.exists) && (
                  <>
                    <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', margin: '0 0 12px 0', padding: '6px 10px', background: 'var(--bg-elevated)', borderRadius: 'var(--r-md)' }}>
                      Chief complaint, medical history, symptoms and vitals can be added inside the patient record after registration.
                    </p>
                    <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                      <button type="button" className="btn btn-ghost" onClick={() => setShowIntake(false)}>Cancel</button>
                      <button type="submit" className="btn btn-primary" disabled={submitting}>
                        {submitting ? 'Registering…' : 'Register Patient'}
                      </button>
                    </div>
                  </>
                )}
              </form>
            </div>
          </div>
        )}

        {/* Action Modal (Vitals & Identity lookup resolved from queues) */}
        {actionModal.isOpen && (
          <div className="dialog-overlay" onClick={e => e.target === e.currentTarget && closeActionModal()}>
            <div className="dialog-box" style={{ maxWidth: '520px', width: '90vw' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border)', paddingBottom: 'var(--sp-2)', marginBottom: 'var(--sp-4)' }}>
                <h2 className="dialog-title" style={{ margin: 0 }}>
                  {actionModal.type === 'vitals' ? 'Record Vitals' : actionModal.type === 'symptoms' ? 'Record Symptoms / Issues' : 'Resolve Patient Identity'}
                </h2>
                <button className="btn btn-ghost btn-icon" onClick={closeActionModal} aria-label="Close">
                  <X size={16} />
                </button>
              </div>

              {actionModal.type === 'vitals' ? (
                <form onSubmit={async (e) => {
                  e.preventDefault();
                  const payload = {};
                  ['heart_rate', 'spo2', 'respiratory_rate', 'systolic_bp', 'diastolic_bp', 'temperature'].forEach(f => {
                    const val = e.target[f].value;
                    if (val) payload[f] = parseFloat(val);
                  });
                  payload['mental_status'] = e.target.mental_status.value;
                  try {
                    await addVitals(actionModal.patient.id, payload);
                    await assessPatient({ patient_id: actionModal.patient.id, trigger: 'vitals_update' });
                    alert("Vitals recorded and triage updated!");
                    closeActionModal();
                    refresh();
                  } catch (err) {
                    alert(err.message || "Failed to save vitals.");
                  }
                }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                    <div className="form-group">
                      <label className="form-label" htmlFor="popup-hr">Heart Rate (bpm) <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 400, marginLeft: 4 }}>(e.g. 75)</span></label>
                      <input type="number" id="popup-hr" name="heart_rate" className="form-input" required />
                    </div>
                    <div className="form-group">
                      <label className="form-label" htmlFor="popup-spo2">SpO₂ (%) <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 400, marginLeft: 4 }}>(e.g. 98)</span></label>
                      <input type="number" id="popup-spo2" name="spo2" className="form-input" required />
                    </div>
                    <div className="form-group">
                      <label className="form-label" htmlFor="popup-rr">Respiratory Rate (/min) <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 400, marginLeft: 4 }}>(e.g. 16)</span></label>
                      <input type="number" id="popup-rr" name="respiratory_rate" className="form-input" required />
                    </div>
                    <div className="form-group">
                      <label className="form-label" htmlFor="popup-sbp">Systolic BP (mmHg) <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 400, marginLeft: 4 }}>(e.g. 120)</span></label>
                      <input type="number" id="popup-sbp" name="systolic_bp" className="form-input" required />
                    </div>
                    <div className="form-group">
                      <label className="form-label" htmlFor="popup-dbp">Diastolic BP (mmHg) <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 400, marginLeft: 4 }}>(e.g. 80)</span></label>
                      <input type="number" id="popup-dbp" name="diastolic_bp" className="form-input" required />
                    </div>
                    <div className="form-group">
                      <label className="form-label" htmlFor="popup-temp">Temperature (°C) <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 400, marginLeft: 4 }}>(e.g. 36.8)</span></label>
                      <input type="number" step="0.1" id="popup-temp" name="temperature" className="form-input" required />
                    </div>
                  </div>

                  <div className="form-group" style={{ marginBottom: '20px' }}>
                    <label className="form-label" htmlFor="popup-mental">Mental Status</label>
                    <select id="popup-mental" name="mental_status" className="form-select">
                      <option value="alert">Alert</option>
                      <option value="confused">Confused</option>
                      <option value="unresponsive">Unresponsive</option>
                    </select>
                  </div>

                  <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                    <button type="button" className="btn btn-ghost" onClick={closeActionModal}>Cancel</button>
                    <button type="submit" className="btn btn-primary">Save & Triage</button>
                  </div>
                </form>
              ) : actionModal.type === 'symptoms' ? (
                <form onSubmit={async (e) => {
                  e.preventDefault();
                  const symptomsText = e.target.symptoms_text.value;
                  if (!symptomsText.trim()) return;
                  try {
                    await addObservation(actionModal.patient.id, { raw_text: symptomsText });
                    await reassessPatient({ patient_id: actionModal.patient.id, trigger: 'symptom_update' });
                    alert("Symptoms recorded and triage updated!");
                    closeActionModal();
                    refresh();
                  } catch (err) {
                    alert(err.message || "Failed to save symptoms.");
                  }
                }}>
                  <div className="form-group" style={{ marginBottom: '16px' }}>
                    <label className="form-label" htmlFor="popup-symptoms">New Symptoms / Clinical Issues</label>
                    <textarea
                      id="popup-symptoms"
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
                    This patient is registered with temporary ID: <strong>{actionModal.patient.patient_identifier}</strong>.
                    Provide their standard ABHA/Aadhaar/Phone number to link historic records.
                  </p>

                  <div className="form-group">
                    <label className="form-label" htmlFor="popup-lookup-id">
                      Standard Patient Identifier
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 400, marginLeft: 8 }}>(e.g. ABHA-4221-5582)</span>
                    </label>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <input
                        type="text"
                        id="popup-lookup-id"
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
                            const box = document.getElementById("lookup-resolution-result");
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
                            const identifierInput = document.getElementById("popup-lookup-id").value;
                            if (!identifierInput.trim()) return;
                            try {
                              const res = await lookupPatient(identifierInput);
                              const box = document.getElementById("lookup-resolution-result");
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
                                  name: actionModal.patient.name,
                                  age: actionModal.patient.age,
                                  sex: actionModal.patient.sex,
                                  relevant_history: actionModal.patient.relevant_history,
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

                  <div id="lookup-resolution-result" style={{ display: 'none', marginBottom: '20px' }}></div>

                  <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                    <button type="button" className="btn btn-ghost" onClick={closeActionModal}>Cancel</button>
                    <button type="button" className="btn btn-primary" onClick={async () => {
                      const box = document.getElementById("lookup-resolution-result");
                      let resolved = {};
                      if (!box || !box.dataset.resolved) {
                        const identifierInput = document.getElementById("popup-lookup-id").value;
                        if (!identifierInput.trim()) { alert("Enter a standard ID"); return; }
                        resolved = { patient_identifier: identifierInput };
                      } else {
                        resolved = JSON.parse(box.dataset.resolved);
                      }
                      try {
                        await api.patch(`/patients/${actionModal.patient.id}/`, resolved);
                        alert("Identity resolved, demographic data updated and triage reassessed!");
                        closeActionModal();
                        refresh();
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
    </div >
  )
}
