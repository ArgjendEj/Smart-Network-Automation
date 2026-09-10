import { Navigate, Route, Routes } from 'react-router-dom'
import Navbar from './components/Navbar'
import Sidebar from './components/Sidebar'
import { useAuth } from './context/AuthContext'
import Dashboard from './pages/Dashboard'
import Devices from './pages/Devices'
import Login from './pages/Login'
import Register from './pages/Register'
import Logs from './pages/Logs'
import ManualConfiguration from './pages/ManualConfiguration'
import SmartConfiguration from './pages/SmartConfiguration'
import Topology from './pages/Topology'

function Protected({ children }) {
  const { user, ready } = useAuth()
  if (!ready) return <div className="content">Loading…</div>
  if (!user) return <Navigate to="/login" replace />
  return (
    <div className="app">
      <Sidebar />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <Navbar />
        <div className="content">{children}</div>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/" element={<Protected><Dashboard /></Protected>} />
      <Route path="/topology" element={<Protected><Topology /></Protected>} />
      <Route path="/devices" element={<Protected><Devices /></Protected>} />
      <Route path="/smart-config" element={<Protected><SmartConfiguration /></Protected>} />
      <Route path="/manual-config" element={<Protected><ManualConfiguration /></Protected>} />
      <Route path="/logs" element={<Protected><Logs /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
