import { useEffect, useState } from 'react'
import * as api from '../api/client'
import type { ActivityEntry } from '../api/client'
import { ApiError, DELETE_ACTIVITY_CONFIRM } from '../api/client'

// Turn the free-form detail object into a short, readable cell. Keys are
// server-controlled (field names, counts, flags) and never hold user content,
// so rendering them directly is safe.
function formatDetail(detail: Record<string, unknown>): string {
  return Object.entries(detail)
    .filter(([, v]) => v !== null && v !== undefined && v !== '')
    .map(([k, v]) => `${k}=${Array.isArray(v) ? v.join('/') : String(v)}`)
    .join(' · ')
}

export function ActivityLogPanel() {
  const [entries, setEntries] = useState<ActivityEntry[]>([])
  const [enabled, setEnabled] = useState(true)
  const [error, setError] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [confirmText, setConfirmText] = useState('')

  const refresh = () =>
    api.listActivity()
      .then((r) => {
        setEntries(r.entries)
        setEnabled(r.enabled)
      })
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : 'failed to load activity log')
      })

  useEffect(() => { void refresh() }, [])

  const download = async () => {
    setError('')
    try {
      await api.exportActivityCsv()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'download failed')
    }
  }

  const confirmDelete = async () => {
    if (confirmText !== DELETE_ACTIVITY_CONFIRM) return
    setError('')
    try {
      await api.deleteActivityLog(confirmText)
      setConfirming(false)
      setConfirmText('')
      void refresh()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'delete failed')
    }
  }

  return (
    <div>
      <p className="cc-hint" style={{ marginBottom: 'var(--space-4)' }}>
        Who uploaded, edited or deleted what, and when. Written to{' '}
        <code>logs/audit.log</code> in the data directory as one JSON object per line.
        Passwords, share tokens and setting values are never recorded — only field names.
      </p>

      {!enabled && (
        <p className="cc-hint" style={{ marginBottom: 'var(--space-4)' }}>
          Logging is currently disabled (<code>CC_AUDIT_LOG=0</code>). Existing entries are still shown.
        </p>
      )}

      <div className="cc-row-tight" style={{ marginBottom: 'var(--space-4)' }}>
        <button type="button" className="cc-btn" onClick={() => void download()}>Download log (CSV)</button>
        <button
          type="button"
          className="cc-btn cc-btn--danger"
          onClick={() => { setConfirming(true); setConfirmText('') }}
          disabled={entries.length === 0}
        >
          Delete log
        </button>
      </div>

      {error && <div className="error-text">{error}</div>}

      {confirming && (
        <div
          style={{
            marginBottom: 'var(--space-4)',
            padding: 'var(--space-4)',
            borderRadius: 'var(--radius-btn)',
            border: '1px solid color-mix(in oklab, var(--danger) 40%, var(--border))',
            background: 'color-mix(in oklab, var(--danger) 8%, transparent)',
          }}
        >
          <p style={{ margin: '0 0 var(--space-3)', color: 'var(--danger)', fontSize: '0.9rem' }}>
            Permanently delete the entire activity log? This cannot be undone.
          </p>
          <p className="cc-hint" style={{ marginBottom: 'var(--space-2)' }}>
            To confirm, type <strong>{DELETE_ACTIVITY_CONFIRM}</strong> below.
          </p>
          <div className="cc-row-tight">
            <input
              className="cc-input"
              value={confirmText}
              onChange={(e) => { setConfirmText(e.target.value) }}
              placeholder={DELETE_ACTIVITY_CONFIRM}
              autoFocus
            />
            <button
              className="cc-btn cc-btn--danger"
              onClick={() => void confirmDelete()}
              disabled={confirmText !== DELETE_ACTIVITY_CONFIRM}
            >
              Delete the log
            </button>
            <button className="cc-btn" onClick={() => { setConfirming(false); setConfirmText('') }}>Cancel</button>
          </div>
        </div>
      )}

      {entries.length === 0 ? (
        <p className="cc-hint">No activity recorded yet.</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
          <thead>
            <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
              <th>When</th><th>Who</th><th>Action</th><th>Target</th><th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e, i) => (
              <tr key={`${e.at}-${String(i)}`} style={{ borderBottom: '1px solid var(--border)' }}>
                <td>{new Date(e.at).toLocaleString()}</td>
                <td>{e.actor ?? '—'}</td>
                <td><code>{e.action}</code></td>
                <td>{e.target ?? '—'}</td>
                <td className="cc-hint">{formatDetail(e.detail)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
