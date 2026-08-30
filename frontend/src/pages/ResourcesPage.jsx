import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '../store'
import { getResources, api } from '../api'
import TopNavbar from '../components/TopNavbar'
import { Plus, Trash, UserCheck, ShieldAlert, Settings, Sparkles, Building, Activity, ShieldCheck, Heart } from 'lucide-react'

const DEFAULT_DEPARTMENTS = [
  { resource_type: 'cardiac_care', name: 'Cardiac Care' },
  { resource_type: 'pediatrics', name: 'Pediatric Resuscitation' },
  { resource_type: 'orthopedics', name: 'Ortho/Trauma Room' },
  { resource_type: 'resuscitation', name: 'Resuscitation Bay' },
  { resource_type: 'general_medicine', name: 'General Medicine' }
];

const DEFAULT_DOCTORS = [
  { id: '1', name: 'Dr. Kapoor', specialty: 'Cardiology', department: 'cardiac_care', status: 'On Duty' },
  { id: '2', name: 'Dr. Sharma', specialty: 'Pediatrics', department: 'pediatrics', status: 'On Duty' },
  { id: '3', name: 'Dr. Roy', specialty: 'Orthopedics', department: 'orthopedics', status: 'On Duty' },
  { id: '4', name: 'Dr. Patel', specialty: 'Trauma Surgery', department: 'resuscitation', status: 'On Call' },
  { id: '5', name: 'Dr. Sen', specialty: 'Neurology', department: 'cardiac_care', status: 'On Duty' },
  { id: '6', name: 'Dr. Joshi', specialty: 'Emergency Medicine', department: 'general_medicine', status: 'On Duty' },
  { id: '7', name: 'Dr. Gupta', specialty: 'OB/GYN', department: 'general_medicine', status: 'Off Duty' },
  { id: '8', name: 'Dr. Iyer', specialty: 'General Practice', department: 'general_medicine', status: 'On Duty' },
]

export default function ResourcesPage() {
  const navigate = useNavigate()
  const { resources, setResources } = useStore()
  const [loading, setLoading] = useState(true)

  const mergedDepts = [...(resources || [])];
  DEFAULT_DEPARTMENTS.forEach(def => {
    if (!mergedDepts.some(r => r.resource_type === def.resource_type)) {
      mergedDepts.push({ id: def.resource_type, resource_type: def.resource_type, name: def.name });
    }
  });
  
  // Clinicians State (persisted via localStorage)
  const [doctors, setDoctors] = useState(() => {
    const saved = localStorage.getItem('ed_doctors')
    return saved ? JSON.parse(saved) : DEFAULT_DOCTORS
  })

  // Form States
  const [showAddDept, setShowAddDept] = useState(false)
  const [newDept, setNewDept] = useState({ name: '', resource_type: 'treatment_room', capacity: 5, status: 'available' })

  const [showAddDoc, setShowAddDoc] = useState(false)
  const [newDoc, setNewDoc] = useState({ name: '', specialty: '', department: 'general_medicine', status: 'On Duty' })

  useEffect(() => {
    localStorage.setItem('ed_doctors', JSON.stringify(doctors))
  }, [doctors])

  const refresh = useCallback(async () => {
    try {
      const res = await getResources()
      setResources(res.data)
    } catch { }
    setLoading(false)
  }, [setResources])

  useEffect(() => {
    refresh()
  }, [refresh])

  // Department actions
  const handleUpdateDeptCapacity = async (id, newCap, newOcc) => {
    try {
      await api.patch(`/routing/resources/${id}/`, { capacity: newCap, occupied: newOcc })
      refresh()
    } catch {
      alert("Failed to update department capacity")
    }
  }

  const handleToggleDeptStatus = async (id, currentStatus) => {
    const nextStatus = currentStatus === 'available' ? 'offline' : 'available'
    try {
      await api.patch(`/routing/resources/${id}/`, { status: nextStatus })
      refresh()
    } catch {
      alert("Failed to update status")
    }
  }

  const handleCreateDept = async (e) => {
    e.preventDefault()
    if (!newDept.name.trim()) return
    try {
      await api.post('/routing/resources/', newDept)
      setShowAddDept(false)
      setNewDept({ name: '', resource_type: 'treatment_room', capacity: 5, status: 'available' })
      refresh()
    } catch {
      alert("Failed to create new department")
    }
  }

  const handleDeleteDept = async (id) => {
    if (!window.confirm("Are you sure you want to delete this department?")) return
    try {
      await api.delete(`/routing/resources/${id}/`)
      refresh()
    } catch {
      alert("Failed to delete department")
    }
  }

  // Doctor actions
  const handleCreateDoc = (e) => {
    e.preventDefault()
    if (!newDoc.name.trim() || !newDoc.specialty.trim()) return
    const created = {
      id: String(Date.now()),
      ...newDoc
    }
    setDoctors(prev => [...prev, created])
    setShowAddDoc(false)
    setNewDoc({ name: '', specialty: '', department: 'general_medicine', status: 'On Duty' })
  }

  const handleDeleteDoc = (id) => {
    if (!window.confirm("Remove this clinician from the registry?")) return
    setDoctors(prev => prev.filter(d => d.id !== id))
  }

  const handleUpdateDocStatus = (id, nextStatus) => {
    setDoctors(prev => prev.map(d => d.id === id ? { ...d, status: nextStatus } : d))
  }

  const handleUpdateDocDept = (id, nextDept) => {
    setDoctors(prev => prev.map(d => d.id === id ? { ...d, department: nextDept } : d))
  }

  const formatDeptName = (key) => {
    return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
  }

  const totalCap = resources.reduce((sum, r) => sum + r.capacity, 0)
  const totalOcc = resources.reduce((sum, r) => sum + r.occupied, 0)
  const avgUtil = totalCap > 0 ? Math.round((totalOcc / totalCap) * 100) : 0

  return (
    <div className="app-container" style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: 'var(--bg-base)', width: '100%' }}>
      <TopNavbar activeTab="resources" loading={loading} onRefresh={refresh} />
      
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', width: '100%', overflowY: 'auto' }}>
        <main className="main-content" style={{ padding: '24px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '24px' }}>
          
          {/* Summary Banner Ribbon */}
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            padding: '16px 20px', 
            background: 'var(--bg-card)', 
            border: '1px solid var(--border)', 
            borderRadius: 'var(--r-md)', 
            boxShadow: 'var(--shadow-sm)'
          }}>
            <div style={{ display: 'flex', gap: '32px' }}>
              <div>
                <span style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Beds & Rooms Capacity</span>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)' }}>{totalCap} total</div>
              </div>
              <div>
                <span style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Occupied Slots</span>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)' }}>{totalOcc} active ({avgUtil}% occupancy)</div>
              </div>
              <div>
                <span style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Active Clinicians</span>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)' }}>{doctors.filter(d => d.status === 'On Duty').length} on-duty</div>
              </div>
            </div>
            
            <div style={{ display: 'flex', gap: '10px' }}>
              <button className="btn btn-outline-primary btn-sm" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }} onClick={() => setShowAddDept(true)}>
                <Building size={14} />
                + Add Department
              </button>
              <button className="btn btn-primary btn-sm" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }} onClick={() => setShowAddDoc(true)}>
                <UserCheck size={14} />
                + Register Doctor
              </button>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr', gap: '24px' }}>
            
            {/* Left Box: Departments & Resource Control */}
            <div className="card" style={{ padding: '20px' }}>
              <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <span className="card-title" style={{ margin: 0 }}>ED Care Departments</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Real-time routing capacities</span>
              </div>

              {loading ? (
                <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading resources...</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {resources.map((res) => (
                    <div 
                      key={res.id} 
                      style={{ 
                        padding: '12px 16px', 
                        border: '1px solid var(--border)', 
                        borderRadius: '6px', 
                        background: res.status === 'offline' ? 'var(--bg-hover)' : 'var(--bg-card)',
                        display: 'flex', 
                        justifyContent: 'space-between', 
                        alignItems: 'center',
                        opacity: res.status === 'offline' ? 0.7 : 1
                      }}
                    >
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <strong style={{ fontSize: '0.92rem', color: 'var(--text-primary)' }}>{res.name}</strong>
                          <span className={`badge ${res.status === 'available' ? 'badge-normal' : 'badge-na'}`} style={{ fontSize: '0.66rem' }}>
                            {res.status === 'available' ? 'Online' : 'Offline'}
                          </span>
                        </div>
                        <span style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
                          Type: {formatDeptName(res.resource_type)}
                        </span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                        
                        {/* Capacity editor */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <div style={{ display: 'flex', flexDirection: 'column', fontStyle: 'normal', alignItems: 'flex-end' }}>
                            <span style={{ fontSize: '0.68rem', color: 'var(--text-secondary)' }}>OCCUPIED / MAX</span>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 2 }}>
                              <input 
                                type="number" 
                                min="0" 
                                max={res.capacity}
                                value={res.occupied} 
                                onChange={(e) => handleUpdateDeptCapacity(res.id, res.capacity, parseInt(e.target.value) || 0)}
                                style={{ width: '45px', padding: '2px 4px', border: '1px solid var(--border)', borderRadius: '4px', textAlign: 'center', fontSize: '0.78rem' }}
                              />
                              <span style={{ color: 'var(--text-muted)' }}>/</span>
                              <input 
                                type="number" 
                                min="1" 
                                value={res.capacity} 
                                onChange={(e) => handleUpdateDeptCapacity(res.id, parseInt(e.target.value) || 1, res.occupied)}
                                style={{ width: '45px', padding: '2px 4px', border: '1px solid var(--border)', borderRadius: '4px', textAlign: 'center', fontSize: '0.78rem' }}
                              />
                            </div>
                          </div>
                        </div>

                        {/* Toggle toggle button */}
                        <button 
                          className={`btn btn-sm ${res.status === 'offline' ? 'btn-ghost' : 'btn-outline-danger'}`} 
                          onClick={() => handleToggleDeptStatus(res.id, res.status)}
                          style={{ fontSize: '0.72rem', padding: '4px 8px' }}
                        >
                          {res.status === 'offline' ? 'Set Online' : 'Set Offline'}
                        </button>

                        <button 
                          className="btn btn-ghost btn-icon" 
                          onClick={() => handleDeleteDept(res.id)}
                          style={{ color: 'var(--p1)' }}
                        >
                          <Trash size={12} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Right Box: Doctors Directory Registry */}
            <div className="card" style={{ padding: '20px' }}>
              <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <span className="card-title" style={{ margin: 0 }}>Clinician Registry</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Active emergency duty roster</span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {doctors.map((doc) => (
                  <div 
                    key={doc.id} 
                    style={{ 
                      padding: '10px 14px', 
                      border: '1px solid var(--border)', 
                      borderRadius: '6px', 
                      background: doc.status === 'Off Duty' ? 'var(--bg-hover)' : 'var(--bg-card)',
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center',
                      opacity: doc.status === 'Off Duty' ? 0.6 : 1
                    }}
                  >
                    <div>
                      <strong style={{ fontSize: '0.9rem', color: 'var(--text-primary)' }}>{doc.name}</strong>
                      <div style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                        {doc.specialty} · <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{formatDeptName(doc.department)}</span>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      {/* Dept assign selector */}
                      <select 
                        value={doc.department} 
                        onChange={(e) => handleUpdateDocDept(doc.id, e.target.value)}
                        style={{ 
                          padding: '2px 4px', 
                          fontSize: '0.72rem', 
                          border: '1px solid var(--border)', 
                          borderRadius: '4px', 
                          background: 'var(--bg-card)',
                          color: 'var(--text-primary)'
                        }}
                      >
                        {mergedDepts.map(r => (
                          <option key={r.id || r.resource_type} value={r.resource_type}>{r.name}</option>
                        ))}
                      </select>

                      {/* Status selector */}
                      <select 
                        value={doc.status} 
                        onChange={(e) => handleUpdateDocStatus(doc.id, e.target.value)}
                        style={{ 
                          padding: '2px 4px', 
                          fontSize: '0.72rem', 
                          border: '1px solid var(--border)', 
                          borderRadius: '4px',
                          color: doc.status === 'On Duty' ? 'var(--p5)' : doc.status === 'On Call' ? 'var(--p2)' : 'var(--text-muted)'
                        }}
                      >
                        <option value="On Duty">On Duty</option>
                        <option value="On Call">On Call</option>
                        <option value="Off Duty">Off Duty</option>
                      </select>

                      <button className="btn btn-ghost btn-icon" onClick={() => handleDeleteDoc(doc.id)} style={{ color: 'var(--p1)' }}>
                        <Trash size={12} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

          </div>

          {/* Department Add Dialog */}
          {showAddDept && (
            <div className="dialog-overlay" onClick={e => e.target === e.currentTarget && setShowAddDept(false)}>
              <div className="dialog-box" style={{ maxWidth: '420px', width: '90vw' }}>
                <div style={{ borderBottom: '1px solid var(--border)', paddingBottom: '10px', marginBottom: '16px' }}>
                  <h3 className="dialog-title" style={{ margin: 0 }}>Add Emergency Department</h3>
                </div>
                <form onSubmit={handleCreateDept}>
                  <div className="form-group" style={{ marginBottom: '12px' }}>
                    <label className="form-label">Department Name</label>
                    <input 
                      type="text" 
                      className="form-input" 
                      value={newDept.name} 
                      onChange={e => setNewDept(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="e.g. cardiac_care, pediatrics, orthopedics..."
                      required 
                    />
                  </div>
                  <div className="form-group" style={{ marginBottom: '12px' }}>
                    <label className="form-label">Resource Type</label>
                    <select 
                      className="form-select" 
                      value={newDept.resource_type} 
                      onChange={e => setNewDept(prev => ({ ...prev, resource_type: e.target.value }))}
                    >
                      <option value="resus_bay">Resuscitation Bay</option>
                      <option value="treatment_room">Treatment Room</option>
                      <option value="fast_track_room">Fast Track Room</option>
                      <option value="observation_bed">Observation Bed</option>
                    </select>
                  </div>
                  <div className="form-group" style={{ marginBottom: '16px' }}>
                    <label className="form-label">Max Bed Capacity</label>
                    <input 
                      type="number" 
                      className="form-input" 
                      min="1" 
                      value={newDept.capacity} 
                      onChange={e => setNewDept(prev => ({ ...prev, capacity: parseInt(e.target.value) || 1 }))}
                      required 
                    />
                  </div>
                  <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                    <button type="button" className="btn btn-ghost" onClick={() => setShowAddDept(false)}>Cancel</button>
                    <button type="submit" className="btn btn-primary">Create Department</button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* Doctor Add Dialog */}
          {showAddDoc && (
            <div className="dialog-overlay" onClick={e => e.target === e.currentTarget && setShowAddDoc(false)}>
              <div className="dialog-box" style={{ maxWidth: '420px', width: '90vw' }}>
                <div style={{ borderBottom: '1px solid var(--border)', paddingBottom: '10px', marginBottom: '16px' }}>
                  <h3 className="dialog-title" style={{ margin: 0 }}>Register Medical Practitioner</h3>
                </div>
                <form onSubmit={handleCreateDoc}>
                  <div className="form-group" style={{ marginBottom: '12px' }}>
                    <label className="form-label">Doctor Name</label>
                    <input 
                      type="text" 
                      className="form-input" 
                      value={newDoc.name} 
                      onChange={e => setNewDoc(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="Dr. Name"
                      required 
                    />
                  </div>
                  <div className="form-group" style={{ marginBottom: '12px' }}>
                    <label className="form-label">Specialization / Specialty</label>
                    <input 
                      type="text" 
                      className="form-input" 
                      value={newDoc.specialty} 
                      onChange={e => setNewDoc(prev => ({ ...prev, specialty: e.target.value }))}
                      placeholder="e.g. Cardiology"
                      required 
                    />
                  </div>
                  <div className="form-group" style={{ marginBottom: '12px' }}>
                    <label className="form-label">Duty Assignment Department</label>
                    <select 
                      className="form-select" 
                      value={newDoc.department} 
                      onChange={e => setNewDoc(prev => ({ ...prev, department: e.target.value }))}
                    >
                      {mergedDepts.map(r => (
                        <option key={r.id || r.resource_type} value={r.resource_type}>{r.name}</option>
                      ))}
                    </select>
                  </div>
                  <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                    <button type="button" className="btn btn-ghost" onClick={() => setShowAddDoc(false)}>Cancel</button>
                    <button type="submit" className="btn btn-primary">Register Physician</button>
                  </div>
                </form>
              </div>
            </div>
          )}

        </main>
      </div>
    </div>
  )
}
