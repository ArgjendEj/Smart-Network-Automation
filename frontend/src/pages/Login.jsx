import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import PasswordInput from '../components/PasswordInput'
import ThemeToggle from '../components/ThemeToggle'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const { user, login } = useAuth()
  const nav = useNavigate()
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('admin123')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/" replace />

  const submit = async (e) => {
    e.preventDefault()
    setErr(''); setBusy(true)
    try {
      await login(username, password)
      nav('/')
    } catch (ex) {
      if (ex?.response?.status === 401) {
        setErr('Wrong username or password.')
      } else if (ex?.response) {
        setErr(`Server error (${ex.response.status}). Try again.`)
      } else {
        setErr('Cannot reach the server. Make sure the "SNA Server" window is open (run start.bat), then retry.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <ThemeToggle style={{ position: 'fixed', top: 16, right: 16 }} />
      <form className="card login-card" onSubmit={submit}>
        <h2 style={{ marginTop: 0 }}>⚡ Sign in</h2>
        <div className="field">
          <label className="muted">Username</label>
          <input value={username} onChange={(e) => setUsername(e.target.value)} />
        </div>
        <div className="field">
          <label className="muted">Password</label>
          <PasswordInput value={password} onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password" />
        </div>
        {err && <div className="error" style={{ marginBottom: 10 }}>{err}</div>}
        <button className="primary" style={{ width: '100%' }} disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
        <p className="muted" style={{ fontSize: 12 }}>
          No account? <Link to="/register" state={{ from: 'login' }}>Create one</Link> &nbsp;·&nbsp; Default: admin / admin123
        </p>
      </form>
    </div>
  )
}
