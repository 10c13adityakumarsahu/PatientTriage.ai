/** Centralised API client — all calls go through axios with base URL */
import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'
const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'

export const api = axios.create({ baseURL: BASE, timeout: 10000 })

// ── Patients ──────────────────────────────────────────────────
export const getPatients  = (params) => api.get('/patients/', { params })
export const getPatient   = (id)     => api.get(`/patients/${id}/`)
export const createPatient= (data)   => api.post('/patients/', data)
export const lookupPatient = (identifier) => api.get('/patients/lookup/', { params: { identifier } })
export const addVitals    = (id, d)  => api.post(`/patients/${id}/vitals/`, d)
export const addObservation=(id, d)  => api.post(`/patients/${id}/observations/`, d)
export const getAssessments=(id)     => api.get(`/patients/${id}/assessments/`)

// ── Triage ────────────────────────────────────────────────────
export const assessPatient  = (data) => api.post('/triage/assess/', data)
export const reassessPatient= (data) => api.post('/triage/reassess/', data)
export const aiAnalyze      = (data) => api.post('/triage/ai-analyze/', data)
export const getAiMode      = ()     => api.get('/triage/ai-mode/')
export const toggleAiMode   = (data) => api.post('/triage/ai-mode/', data)

// ── Queue ─────────────────────────────────────────────────────
export const getLiveQueue  = ()  => api.get('/queues/live/')
export const getQueueStats = ()  => api.get('/queues/stats/')
export const recomputeQueue= ()  => api.post('/queues/recompute/')

// ── Routing ───────────────────────────────────────────────────
export const getResources      = ()  => api.get('/routing/resources/')
export const getPatientRouting = (id)=> api.get(`/routing/patients/${id}/routing/`)
export const recommendRouting  = (id)=> api.post(`/routing/patients/${id}/routing/recommend/`)

// ── Alerts ────────────────────────────────────────────────────
export const getAlerts     = (params) => api.get('/alerts/', { params })
export const acknowledgeAlert = (id, data) => api.post(`/alerts/${id}/acknowledge/`, data)

// ── Overrides ─────────────────────────────────────────────────
export const createOverride = (patientId, data) =>
  api.post(`/patients/${patientId}/override/`, data)
export const getOverrides = () => api.get('/overrides/')

// ── Audit ─────────────────────────────────────────────────────
export const getAudit = (params) => api.get('/audit/', { params })

// ── Simulation ───────────────────────────────────────────────
export const seedSimulation  = ()     => api.post('/simulation/seed/')
export const tickSimulation  = (data) => api.post('/simulation/tick/', data)
export const triggerDeterioration = (data) => api.post('/simulation/deteriorate/', data)
export const triggerSurge    = ()     => api.post('/simulation/surge/')
export const resetSimulation = ()     => api.post('/simulation/reset/')
export const getSimStatus    = ()     => api.get('/simulation/status/')
export const intakeNextSimulation = () => api.post('/simulation/intake-next/')
export const getNextPatientData = () => api.get('/simulation/next-patient-data/')

// ── WebSocket ─────────────────────────────────────────────────
export const WS_URL = `${WS_BASE}/ws/ed/live/`
