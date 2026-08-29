import { useNavigate } from 'react-router-dom'
import AuditEventList from '../components/AuditEventList'
import TopNavbar from '../components/TopNavbar'

export default function AuditPage() {
  const navigate = useNavigate()
  
  return (
    <div className="app-container" style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: 'var(--bg-base)', width: '100%' }}>
      <TopNavbar activeTab="audit" />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', width: '100%' }}>
        
        <main className="main-content">
          <div className="section-header" style={{ marginBottom: 'var(--sp-6)' }}>
            <h1 className="section-title" style={{ fontSize: '1.1rem' }}>Audit Logs</h1>
          </div>
          <div className="card">
            <AuditEventList limit={200} />
          </div>
        </main>
      </div>
    </div>
  )
}
