import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import PasswordInput from '../components/PasswordInput'
import { useAuth } from '../context/AuthContext'

export default function Register() {
  const { user, register } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/" replace />
  // only reachable through the "Create one" link on the sign-in page — typing
  // the bare URL (or a browser autocomplete to /register) lands on sign-in.
  if (loc.state?.from !== 'login') return <Navigate to="/login" replace />

  const submit = async (e) => {
    e.preventDefault()
    setErr('')
    if (username.trim().length < 3) { setErr('Username must be at least 3 characters.'); return }
    if (password.length < 6) { setErr('Password must be at least 6 characters.'); return }
    if (password !== confirm) { setErr('The two passwords do not match.'); return }
    setBusy(true)
    try {
      await register(username.trim(), password)
      nav('/')
    } catch (ex) {
      if (ex?.response?.status === 409) {
        setErr('That username is already taken.')
      } else if (ex?.response?.status === 422) {
        setErr('Please check the username and password length.')
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
      <form className="card login-card" onSubmit={submit}>
        <h2 style={{ marginTop: 0 }}>⚡ Create an account</h2>
        <div className="field">
          <label className="muted">Username</label>
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        </div>
        <div className="field">
          <label className="muted">Password</label>
          <PasswordInput value={password} onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password" />
        </div>
        <div className="field">
          <label className="muted">Confirm password</label>
          <PasswordInput value={confirm} onChange={(e) => setConfirm(e.target.value)}
            autoComplete="new-password" />
        </div>
        {err && <div className="error" style={{ marginBottom: 10 }}>{err}</div>}
        <button className="primary" style={{ width: '100%' }} disabled={busy}>
          {busy ? 'Creating…' : 'Create account'}
        </button>
        <p className="muted" style={{ fontSize: 12 }}>
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </div>
  )
}
