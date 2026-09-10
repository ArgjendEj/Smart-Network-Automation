import { createContext, useContext, useEffect, useState } from 'react'
import { AuthAPI } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) { setReady(true); return }
    AuthAPI.me()
      .then((r) => setUser(r.data))
      .catch(() => localStorage.removeItem('token'))
      .finally(() => setReady(true))
  }, [])

  const login = async (username, password) => {
    const r = await AuthAPI.login(username, password)
    localStorage.setItem('token', r.data.access_token)
    const me = await AuthAPI.me()
    setUser(me.data)
  }

  const register = async (username, password) => {
    const r = await AuthAPI.register(username, password)
    localStorage.setItem('token', r.data.access_token)
    const me = await AuthAPI.me()
    setUser(me.data)
  }

  const logout = async () => {
    try { await AuthAPI.logout() } catch { /* ignore */ }
    localStorage.removeItem('token')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, ready, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
