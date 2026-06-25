import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../api/auth'
import { ApiError } from '../api/client'

export function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const { login, multiUser } = useAuth()
  const navigate = useNavigate()

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login(password, multiUser ? username : undefined)
      navigate('/')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'login failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="cc-login">
      <form className="cc-login__card" onSubmit={(e) => void onSubmit(e)}>
        <div className="cc-login__logo">
          <svg className="cc-mark" viewBox="0 0 48 48" aria-hidden="true">
            <path d="M40 13 A16 16 0 1 0 40 35" fill="none" stroke="var(--text)" strokeWidth="3.4" strokeLinecap="round" />
            <path d="M34 19 A9 9 0 1 0 34 29" fill="none" stroke="var(--accent)" strokeWidth="3.4" strokeLinecap="round" />
          </svg>
          CatalogueCanvas
        </div>
        {multiUser && (
          <div className="cc-field">
            <label className="cc-label" htmlFor="username">Username</label>
            <input
              id="username"
              className="cc-input"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => { setUsername(e.target.value) }}
              autoFocus
            />
          </div>
        )}
        <div className="cc-field">
          <label className="cc-label" htmlFor="password">{multiUser ? 'Password' : 'Admin password'}</label>
          <input
            id="password"
            className="cc-input"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => { setPassword(e.target.value) }}
            autoFocus={!multiUser}
          />
        </div>
        <button className="cc-btn cc-btn--primary" type="submit" disabled={busy} style={{ width: '100%' }}>
          {busy ? 'Logging in...' : 'Log in'}
        </button>
        {error && <div className="error-text">{error}</div>}
      </form>
    </div>
  )
}
