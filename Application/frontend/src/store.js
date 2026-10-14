/** Zustand global store — queue, alerts, simulation state, surge */
import { create } from 'zustand'

export const useStore = create((set, get) => ({
  // ── Queue ──────────────────────────────────────────────────
  queue: [],
  queueStats: null,
  setQueue: (queue) => set({ queue }),
  setQueueStats: (stats) => set({ queueStats: stats }),

  updatePatientInQueue: (updated) => set(state => ({
    queue: state.queue.map(p =>
      p.id === updated.patient_id || p.id === updated.id ? { ...p, ...updated } : p
    )
  })),

  // ── Alerts ─────────────────────────────────────────────────
  alerts: [],
  setAlerts: (alerts) => set({ alerts }),
  addAlert: (alert) => set(state => ({ alerts: [alert, ...state.alerts] })),
  removeAlert: (id) => set(state => ({ alerts: state.alerts.filter(a => a.id !== id) })),

  // ── Simulation ─────────────────────────────────────────────
  simStatus: null,
  surgeActive: false,
  isRunning: false,
  setSimStatus: (s) => set({ simStatus: s, surgeActive: s?.surge_active || false, isRunning: s?.is_running || false }),
  setSurge: (v) => set({ surgeActive: v }),

  // ── WebSocket ──────────────────────────────────────────────
  wsConnected: false,
  setWsConnected: (v) => set({ wsConnected: v }),

  // ── Resources ──────────────────────────────────────────────
  resources: [],
  setResources: (r) => set({ resources: r }),

  // ── Selected patient (detail view) ────────────────────────
  selectedPatient: null,
  setSelectedPatient: (p) => set({ selectedPatient: p }),
}))
