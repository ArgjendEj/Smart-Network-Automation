import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import ThemeToggle from './ThemeToggle'

export default function Navbar() {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  return (
    <div className="navbar">
      <div className="muted">Smart Network Automation &amp; Configuration Management</div>
      <div className="row">
        <span className="muted">{user?.username} ({user?.role})</span>
        <ThemeToggle />
        <button onClick={async () => { await logout(); nav('/login') }}>Logout</button>
      </div>
    </div>
  )
}
