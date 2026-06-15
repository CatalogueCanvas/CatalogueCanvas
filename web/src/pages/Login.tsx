import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../api/auth'
import { ApiError } from '../api/client'

export function Login() {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login(password)
      navigate('/')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'login failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="cc-login">
      <form className="cc-login__card" onSubmit={onSubmit}>
        <div className="cc-login__logo">
          <svg className="cc-mark" viewBox="0 0 48 48" aria-hidden="true">
            <path d="M40 13 A16 16 0 1 0 40 35" fill="none" stroke="var(--text)" strokeWidth="3.4" strokeLinecap="round" />
            <path d="M34 19 A9 9 0 1 0 34 29" fill="none" stroke="var(--accent)" strokeWidth="3.4" strokeLinecap="round" />
          </svg>
          CatalogueCanvas
        </div>
        <div className="cc-field">
          <label className="cc-label" htmlFor="password">Admin password</label>
          <input
            id="password"
            className="cc-input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoFocus
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
