/** App — router with lazy pages */
import { Routes, Route } from 'react-router-dom'
import CommandCenter from './pages/CommandCenter'
import PatientDetail from './pages/PatientDetail'
import AuditPage from './pages/AuditPage'
import ResourcesPage from './pages/ResourcesPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<CommandCenter />} />
      <Route path="/patient/:id" element={<PatientDetail />} />
      <Route path="/audit" element={<AuditPage />} />
      <Route path="/resources" element={<ResourcesPage />} />
      <Route path="*" element={<CommandCenter />} />
    </Routes>
  )
}
