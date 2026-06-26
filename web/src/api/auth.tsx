// Context provider component and its hook intentionally live together.
/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import * as api from './client'
import type { Role } from './client'

interface AuthContextValue {
  authenticated: boolean
  role: Role | null
  username: string | null
  multiUser: boolean
  isAdmin: boolean
  loading: boolean
  login: (password: string, username?: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authenticated, setAuthenticated] = useState(false)
  const [role, setRole] = useState<Role | null>(null)
  const [username, setUsername] = useState<string | null>(null)
  const [multiUser, setMultiUser] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void api.me()
      .then((res) => {
        setAuthenticated(res.authenticated)
        setRole(res.role)
        setUsername(res.username)
        setMultiUser(res.multi_user)
      })
      .finally(() => { setLoading(false) })
  }, [])

  const login = async (password: string, username?: string) => {
    const res = await api.login(password, username)
    setAuthenticated(true)
    setRole(res.role)
    setUsername(res.username)
  }

  const logout = async () => {
    await api.logout()
    setAuthenticated(false)
    setRole(null)
    setUsername(null)
  }

  return (
    <AuthContext.Provider
      value={{ authenticated, role, username, multiUser, isAdmin: role === 'admin', loading, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
