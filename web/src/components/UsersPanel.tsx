import { useEffect, useState } from 'react'
import * as api from '../api/client'
import type { Role, User } from '../api/client'
import { ApiError } from '../api/client'

export function UsersPanel() {
  const [users, setUsers] = useState<User[]>([])
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('reader')
  const [error, setError] = useState('')

  const refresh = () => api.listUsers().then(setUsers).catch(() => {})
  useEffect(() => { void refresh() }, [])

  const create = async () => {
    if (!username.trim() || !password) return
    setError('')
    try {
      await api.createUser({ username: username.trim(), password, role })
      setUsername('')
      setPassword('')
      setRole('reader')
      void refresh()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'failed to create user')
    }
  }

  const resetPassword = async (user: User) => {
    const pw = prompt(`New password for "${user.username}":`)
    if (!pw) return
    setError('')
    try {
      await api.updateUser(user.id, { password: pw })
      void refresh()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'failed to update password')
    }
  }

  const changeRole = async (user: User, newRole: Role) => {
    setError('')
    try {
      await api.updateUser(user.id, { role: newRole })
      void refresh()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'failed to change role')
    }
  }

  const remove = async (user: User) => {
    if (!confirm(`Delete user "${user.username}"?`)) return
    setError('')
    try {
      await api.deleteUser(user.id)
      void refresh()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'failed to delete user')
    }
  }

  return (
    <div>
      {users.length > 0 && (
        <div className="cc-list" style={{ marginBottom: 'var(--space-4)' }}>
          {users.map((u) => (
            <div className="cc-row" key={u.id}>
              <div className="cc-row__main">
                <h3 className="cc-row__title">{u.username}</h3>
                <div className="cc-row__meta"><span>{u.role}</span></div>
              </div>
              <div className="cc-row__actions">
                <div className="cc-seg">
                  {(['admin', 'reader'] as Role[]).map((r) => (
                    <button
                      key={r}
                      type="button"
                      aria-pressed={u.role === r}
                      onClick={() => void changeRole(u, r)}
                    >
                      {r === 'admin' ? 'Admin' : 'Reader'}
                    </button>
                  ))}
                </div>
                <button className="cc-btn cc-btn--sm" type="button" onClick={() => void resetPassword(u)}>Reset password</button>
                <button className="cc-btn cc-btn--danger cc-btn--sm" type="button" onClick={() => void remove(u)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}
      <div className="cc-form">
        <div className="cc-field">
          <label className="cc-label" htmlFor="user-username">Username</label>
          <input id="user-username" className="cc-input" value={username} onChange={(e) => { setUsername(e.target.value) }} />
        </div>
        <div className="cc-field">
          <label className="cc-label" htmlFor="user-password">Password</label>
          <input id="user-password" className="cc-input" type="password" value={password} onChange={(e) => { setPassword(e.target.value) }} />
          <p className="cc-hint">Must differ from every other user's password.</p>
        </div>
        <div className="cc-field">
          <label className="cc-label">Role</label>
          <div className="cc-seg">
            {(['admin', 'reader'] as Role[]).map((r) => (
              <button
                key={r}
                type="button"
                aria-pressed={role === r}
                onClick={() => { setRole(r) }}
              >
                {r === 'admin' ? 'Admin' : 'Reader'}
              </button>
            ))}
          </div>
        </div>
        <div className="cc-row-tight">
          <button className="cc-btn cc-btn--primary" type="button" onClick={() => void create()}>Add user</button>
        </div>
        {error && <div className="error-text">{error}</div>}
      </div>
    </div>
  )
}
