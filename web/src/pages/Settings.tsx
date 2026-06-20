import { useEffect, useRef, useState } from 'react'
import * as api from '../api/client'
import type { Accent, AppSettings, CsvApplyResult, CsvBackup, CsvPreview, Density, Library, NavLayout, Theme } from '../api/client'
import { ApiError, DELETE_BACKUP_CONFIRM } from '../api/client'
import { ACCENT_PRESETS, useAppearance } from '../api/appearance'
import { UsersPanel } from '../components/UsersPanel'

const ACCENT_LABELS: Record<Accent, string> = {
  default: 'Default',
  cobalt: 'Cobalt',
  terracotta: 'Terracotta',
  forest: 'Forest',
  mint: 'Mint',
  ink: 'Ink',
}

export function Settings() {
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const { appearance, setAppearance } = useAppearance()
  const [draft, setDraft] = useState(appearance)
  const [appearanceBusy, setAppearanceBusy] = useState(false)
  const [appearanceError, setAppearanceError] = useState('')
  const [appearanceSaved, setAppearanceSaved] = useState(false)

  useEffect(() => {
    setDraft(appearance)
  }, [appearance])

  const saveAppearance = async () => {
    setAppearanceBusy(true)
    setAppearanceError('')
    setAppearanceSaved(false)
    try {
      await setAppearance(draft)
      setAppearanceSaved(true)
    } catch (err) {
      setAppearanceError(err instanceof ApiError ? err.message : 'save failed')
    } finally {
      setAppearanceBusy(false)
    }
  }

  useEffect(() => {
    api.getSettings().then(setSettings).catch((err) => {
      setError(err instanceof ApiError ? err.message : 'failed to load settings')
    })
  }, [])

  const [libraries, setLibraries] = useState<Library[]>([])
  const [libName, setLibName] = useState('')
  const [libPath, setLibPath] = useState('')
  const [libError, setLibError] = useState('')

  const refreshLibraries = () => api.listLibraries().then(setLibraries).catch(() => {})
  useEffect(() => { refreshLibraries() }, [])

  // --- CSV batch metadata ---
  const csvInputRef = useRef<HTMLInputElement>(null)
  const [csvFile, setCsvFile] = useState<File | null>(null)
  const [csvPreview, setCsvPreview] = useState<CsvPreview | null>(null)
  const [csvResult, setCsvResult] = useState<CsvApplyResult | null>(null)
  const [csvBusy, setCsvBusy] = useState(false)
  const [csvError, setCsvError] = useState('')
  const [backups, setBackups] = useState<CsvBackup[]>([])
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState('')

  const refreshBackups = () => api.listCsvBackups().then((r) => setBackups(r.backups)).catch(() => {})
  useEffect(() => { refreshBackups() }, [])

  const startDelete = (filename: string) => {
    setDeleteTarget(filename)
    setDeleteConfirm('')
  }

  const confirmDelete = async () => {
    if (!deleteTarget || deleteConfirm !== DELETE_BACKUP_CONFIRM) return
    try {
      await api.deleteCsvBackup(deleteTarget, deleteConfirm)
      setDeleteTarget(null)
      setDeleteConfirm('')
      refreshBackups()
    } catch (err) {
      setCsvError(err instanceof ApiError ? err.message : 'delete failed')
    }
  }

  const onCsvSelected = async (file: File | null) => {
    setCsvFile(file)
    setCsvPreview(null)
    setCsvResult(null)
    setCsvError('')
    if (!file) return
    setCsvBusy(true)
    try {
      setCsvPreview(await api.previewCsvImport(file))
    } catch (err) {
      setCsvError(err instanceof ApiError ? err.message : 'preview failed')
    } finally {
      setCsvBusy(false)
    }
  }

  const applyCsv = async () => {
    if (!csvFile) return
    setCsvBusy(true)
    setCsvError('')
    try {
      const result = await api.applyCsvImport(csvFile)
      setCsvResult(result)
      setCsvPreview(null)
      setCsvFile(null)
      if (csvInputRef.current) csvInputRef.current.value = ''
      api.getSettings().then(setSettings).catch(() => {})
      refreshBackups()
    } catch (err) {
      setCsvError(err instanceof ApiError ? err.message : 'import failed')
    } finally {
      setCsvBusy(false)
    }
  }

  const createLib = async () => {
    if (!libName.trim() || !libPath.trim()) return
    setLibError('')
    try {
      await api.createLibrary({ name: libName.trim(), path: libPath.trim() })
      setLibName('')
      setLibPath('')
      refreshLibraries()
    } catch (err) {
      setLibError(err instanceof ApiError ? err.message : 'failed to create library')
    }
  }

  const setLibDefault = async (id: string) => {
    setLibError('')
    try {
      await api.setDefaultLibrary(id)
      refreshLibraries()
    } catch (err) {
      setLibError(err instanceof ApiError ? err.message : 'failed to set default library')
    }
  }

  const removeLib = async (id: string) => {
    if (!confirm('Delete this library?')) return
    setLibError('')
    try {
      await api.deleteLibrary(id)
      refreshLibraries()
    } catch (err) {
      setLibError(err instanceof ApiError ? err.message : 'failed to delete library')
    }
  }

  const setMultiUser = async (value: boolean) => {
    if (!settings) return
    setError('')
    try {
      const updated = await api.updateSettings({ multi_user_enabled: value ? 'true' : 'false' })
      setSettings(updated)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'failed to update multi-user setting')
    }
  }

  if (!settings) return <div className="container"><div className="cc-empty"><p className="cc-empty__title">{error || 'Loading...'}</p></div></div>

  const save = async () => {
    setBusy(true)
    setError('')
    setSaved(false)
    try {
      const updated = await api.updateSettings({
        llm_api_url: settings.llm_api_url,
        llm_model: settings.llm_model,
        llm_item_type: settings.llm_item_type,
        llm_summary_focus: settings.llm_summary_focus,
        llm_bullet_count: settings.llm_bullet_count,
        llm_bullet_max_words: settings.llm_bullet_max_words,
        llm_auto_generate: settings.llm_auto_generate,
        llm_prompt_template: settings.llm_prompt_template,
      })
      setSettings(updated)
      setSaved(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'save failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="container">
      <div className="cc-page-header">
        <div>
          <p className="cc-kicker">Configure</p>
          <h1 className="cc-h1">Settings/Admin</h1>
        </div>
      </div>

      <div className="cc-stack">
        <section className="cc-panel cc-appearance">
          <h2 className="cc-h2" style={{ marginBottom: 'var(--space-4)' }}>Appearance</h2>
          <div className="cc-aprow">
            <div className="cc-aprow__txt">
              <span className="cc-label">Theme</span>
            </div>
            <div className="cc-seg">
              {(['light', 'dark'] as Theme[]).map((t) => (
                <button
                  key={t}
                  type="button"
                  aria-pressed={draft.theme === t}
                  onClick={() => setDraft({ ...draft, theme: t })}
                >
                  {t === 'light' ? 'Light' : 'Dark'}
                </button>
              ))}
            </div>
          </div>
          <div className="cc-aprow">
            <div className="cc-aprow__txt">
              <span className="cc-label">Accent</span>
            </div>
            <div className="cc-swatches">
              {(Object.keys(ACCENT_PRESETS) as Accent[]).map((a) => (
                <button
                  key={a}
                  type="button"
                  className="cc-swatch"
                  aria-pressed={draft.accent === a}
                  title={ACCENT_LABELS[a]}
                  style={{ background: ACCENT_PRESETS[a].accent ?? 'oklch(0.6 0.21 30)' }}
                  onClick={() => setDraft({ ...draft, accent: a })}
                />
              ))}
            </div>
          </div>
          <div className="cc-aprow">
            <div className="cc-aprow__txt">
              <span className="cc-label">Navigation</span>
            </div>
            <div className="cc-seg">
              {(['top', 'side'] as NavLayout[]).map((n) => (
                <button
                  key={n}
                  type="button"
                  aria-pressed={draft.nav === n}
                  onClick={() => setDraft({ ...draft, nav: n })}
                >
                  {n === 'top' ? 'Top bar' : 'Sidebar'}
                </button>
              ))}
            </div>
          </div>
          <div className="cc-aprow">
            <div className="cc-aprow__txt">
              <span className="cc-label">Density</span>
            </div>
            <div className="cc-seg">
              {(['airy', 'balanced', 'dense'] as Density[]).map((d) => (
                <button
                  key={d}
                  type="button"
                  aria-pressed={draft.density === d}
                  onClick={() => setDraft({ ...draft, density: d })}
                >
                  {d[0].toUpperCase() + d.slice(1)}
                </button>
              ))}
            </div>
          </div>
          <div className="cc-aprow">
            <div className="cc-aprow__txt">
              <span className="cc-label">Favorites</span>
            </div>
            <div className="cc-seg">
              {([[true, 'On'], [false, 'Off']] as const).map(([value, label]) => (
                <button
                  key={label}
                  type="button"
                  aria-pressed={draft.favoritesEnabled === value}
                  onClick={() => setDraft({ ...draft, favoritesEnabled: value })}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="cc-row-tight" style={{ marginTop: 'var(--space-4)' }}>
            <button className="cc-btn cc-btn--primary" onClick={saveAppearance} disabled={appearanceBusy} type="button">
              {appearanceBusy ? 'Saving...' : 'Save'}
            </button>
            {appearanceSaved && <span className="cc-saved">Saved</span>}
          </div>
          {appearanceError && <div className="error-text">{appearanceError}</div>}
        </section>

        <section className="cc-panel">
          <h2 className="cc-h2" style={{ marginBottom: 'var(--space-4)' }}>Multi-user access</h2>
          <div className="cc-aprow">
            <div className="cc-aprow__txt">
              <span className="cc-label">Multi-user mode</span>
              <p className="cc-hint">When on, each person logs in with a username and password. Readers can view everything but cannot make changes.</p>
            </div>
            <div className="cc-seg">
              {([[true, 'On'], [false, 'Off']] as const).map(([value, label]) => (
                <button
                  key={label}
                  type="button"
                  aria-pressed={(settings.multi_user_enabled === 'true') === value}
                  onClick={() => setMultiUser(value)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          {settings.multi_user_enabled === 'true' && (
            <div style={{ marginTop: 'var(--space-4)' }}>
              <UsersPanel />
            </div>
          )}
        </section>

        <section className="cc-panel">
          <h2 className="cc-h2" style={{ marginBottom: 'var(--space-4)' }}>LLM defaults</h2>
          <div className="cc-form">
            <div className="cc-field">
              <label className="cc-label">Generate description (LLM)</label>
              <div className="cc-seg">
                {([['true', 'On'], ['false', 'Off']] as const).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={settings.llm_auto_generate === value}
                    onClick={() => setSettings({ ...settings, llm_auto_generate: value })}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <p className="cc-hint">When on, the item editor shows a button to generate a description with the LLM. Notes stay empty until you apply a generated description or write your own.</p>
            </div>
            <div className="cc-field">
              <label className="cc-label" htmlFor="set-llm-api-url">API URL</label>
              <input
                id="set-llm-api-url"
                className="cc-input"
                placeholder="http://host.docker.internal:1234"
                value={settings.llm_api_url}
                onChange={(e) => setSettings({ ...settings, llm_api_url: e.target.value })}
              />
              <p className="cc-hint">Enter just the server host and port — the <code>/v1/chat/completions</code> path is added automatically. A full URL works too.</p>
            </div>
            <div className="cc-field">
              <label className="cc-label" htmlFor="set-llm-model">Model</label>
              <input
                id="set-llm-model"
                className="cc-input"
                value={settings.llm_model}
                onChange={(e) => setSettings({ ...settings, llm_model: e.target.value })}
              />
            </div>
            <div className="cc-field">
              <label className="cc-label" htmlFor="set-llm-item-type">Item type</label>
              <input
                id="set-llm-item-type"
                className="cc-input"
                value={settings.llm_item_type}
                onChange={(e) => setSettings({ ...settings, llm_item_type: e.target.value })}
              />
            </div>
            <div className="cc-field">
              <label className="cc-label" htmlFor="set-llm-summary-focus">Summary focus</label>
              <input
                id="set-llm-summary-focus"
                className="cc-input"
                value={settings.llm_summary_focus}
                onChange={(e) => setSettings({ ...settings, llm_summary_focus: e.target.value })}
              />
            </div>
            <div className="cc-field">
              <label className="cc-label" htmlFor="set-llm-bullet-count">Bullet points</label>
              <input
                id="set-llm-bullet-count"
                className="cc-input"
                type="number"
                min="1"
                value={settings.llm_bullet_count}
                onChange={(e) => setSettings({ ...settings, llm_bullet_count: e.target.value })}
              />
            </div>
            <div className="cc-field">
              <label className="cc-label" htmlFor="set-llm-bullet-max-words">Max words per bullet</label>
              <input
                id="set-llm-bullet-max-words"
                className="cc-input"
                type="number"
                min="1"
                value={settings.llm_bullet_max_words}
                onChange={(e) => setSettings({ ...settings, llm_bullet_max_words: e.target.value })}
              />
            </div>
            <div className="cc-row-tight">
              <button className="cc-btn cc-btn--primary" onClick={save} disabled={busy} type="button">
                {busy ? 'Saving...' : 'Save'}
              </button>
              {saved && <span className="cc-saved">Saved</span>}
            </div>
            {error && <div className="error-text">{error}</div>}
          </div>
        </section>

        <section className="cc-panel">
          <h2 className="cc-h2" style={{ marginBottom: 'var(--space-2)' }}>Prompt template</h2>
          <p className="cc-hint" style={{ marginBottom: 'var(--space-4)' }}>
            Raw TOML used to build the LLM prompt. Placeholders: {'{item_type}'}, {'{summary_focus}'}, {'{bullet_count}'}, {'{bullet_max_words}'}.
          </p>
          <div className="cc-field">
            <textarea
              id="set-llm-prompt-template"
              className="cc-textarea cc-textarea--mono"
              rows={16}
              value={settings.llm_prompt_template}
              onChange={(e) => setSettings({ ...settings, llm_prompt_template: e.target.value })}
            />
          </div>
          <div className="cc-row-tight">
            <button className="cc-btn cc-btn--primary" onClick={save} disabled={busy} type="button">
              {busy ? 'Saving...' : 'Save'}
            </button>
            <button
              className="cc-btn"
              type="button"
              onClick={() => setSettings({ ...settings, llm_prompt_template: settings.llm_prompt_template_default })}
            >
              Reset to default
            </button>
          </div>
        </section>

        <section className="cc-panel">
          <h2 className="cc-h2" style={{ marginBottom: 'var(--space-4)' }}>Libraries</h2>
          <p className="cc-hint" style={{ marginBottom: 'var(--space-4)' }}>
            Storage locations for uploaded items. Paths must already be mounted into the container.
          </p>
          {libraries.length > 0 && (
            <div className="cc-list" style={{ marginBottom: 'var(--space-4)' }}>
              {libraries.map((lib) => (
                <div className="cc-row" key={lib.id}>
                  <div className="cc-row__main">
                    <h3 className="cc-row__title">
                      {lib.name}
                      {lib.is_default && <span className="cc-count">(default)</span>}
                      {!lib.path_ok && <span className="error-text"> path unavailable</span>}
                    </h3>
                    <div className="cc-row__meta">
                      <span>{lib.path}</span>
                      <span>{lib.item_count} items</span>
                    </div>
                  </div>
                  <div className="cc-row__actions">
                    {!lib.is_default && (
                      <button className="cc-btn cc-btn--sm" onClick={() => setLibDefault(lib.id)}>Set default</button>
                    )}
                    {!lib.is_default && lib.item_count === 0 && (
                      <button className="cc-btn cc-btn--danger cc-btn--sm" onClick={() => removeLib(lib.id)}>Delete</button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="cc-form">
            <div className="cc-field">
              <label className="cc-label" htmlFor="lib-name">Name</label>
              <input id="lib-name" className="cc-input" value={libName} onChange={(e) => setLibName(e.target.value)} />
            </div>
            <div className="cc-field">
              <label className="cc-label" htmlFor="lib-path">Path</label>
              <input id="lib-path" className="cc-input" value={libPath} onChange={(e) => setLibPath(e.target.value)} placeholder="/data/storage2" />
              <p className="cc-hint">Must be an existing, writable directory inside the container.</p>
            </div>
            <div className="cc-row-tight">
              <button className="cc-btn cc-btn--primary" type="button" onClick={createLib}>Add library</button>
            </div>
            {libError && <div className="error-text">{libError}</div>}
          </div>
        </section>

        <section className="cc-panel">
          <h2 className="cc-h2" style={{ marginBottom: 'var(--space-4)' }}>Backup &amp; export</h2>
          <div className="cc-stats">
            <div className="cc-stat">
              <div className="cc-stat__n">{settings.stats.total_items}</div>
              <div className="cc-stat__l">Items</div>
            </div>
            <div className="cc-stat">
              <div className="cc-stat__n">{settings.stats.total_collections}</div>
              <div className="cc-stat__l">Collections</div>
            </div>
            <div className="cc-stat">
              <div className="cc-stat__n">{settings.stats.missing_preview}</div>
              <div className="cc-stat__l">Missing preview</div>
            </div>
          </div>
          <div className="cc-row-tight" style={{ marginTop: 'var(--space-4)' }}>
            <a className="cc-btn" href="/api/settings/export/db" download>Download database backup</a>
            <a className="cc-btn" href="/api/settings/export/all" download>Download full backup (db + storage)</a>
            <a className="cc-btn" href="/api/settings/diagnostics" download>Download diagnostic report</a>
          </div>
          <p className="cc-hint">Diagnostic report is a redacted Markdown summary (versions, masked config, database counts) for attaching to a GitHub issue. No secrets are included.</p>
        </section>

        <section className="cc-panel">
          <h2 className="cc-h2" style={{ marginBottom: 'var(--space-2)' }}>Batch metadata (CSV)</h2>
          <p className="cc-hint" style={{ marginBottom: 'var(--space-4)' }}>
            Download a CSV of all item metadata, edit <strong>title</strong>, <strong>note</strong> and <strong>tags</strong> in
            any spreadsheet, then re-upload to apply the changes. Other columns are for reference only and are ignored on import.
            Tags are separated by <code>;</code>. Rows are matched by <code>id</code>; rows with an unknown or blank id are skipped.
          </p>

          <div className="cc-row-tight">
            <a className="cc-btn" href={api.exportItemsCsvUrl()} download>Download metadata CSV</a>
            <label className="cc-btn">
              Choose CSV to import…
              <input
                ref={csvInputRef}
                type="file"
                accept=".csv,text/csv"
                style={{ display: 'none' }}
                onChange={(e) => onCsvSelected(e.target.files?.[0] ?? null)}
                disabled={csvBusy}
              />
            </label>
            {csvFile && <span className="cc-hint">{csvFile.name}</span>}
          </div>

          {csvError && <div className="error-text">{csvError}</div>}

          {csvPreview && (
            <div style={{ marginTop: 'var(--space-4)' }}>
              <p
                style={{
                  margin: '0 0 var(--space-3)',
                  padding: 'var(--space-3)',
                  borderRadius: 'var(--radius-btn)',
                  border: '1px solid color-mix(in oklab, var(--danger) 40%, var(--border))',
                  background: 'color-mix(in oklab, var(--danger) 8%, transparent)',
                  color: 'var(--danger)',
                  fontSize: '0.85rem',
                }}
              >
                ⚠ This will overwrite title/note/tags on {csvPreview.to_update.length} matched item(s).
                A compressed backup of the current values is saved before any changes are applied.
              </p>
              <p className="cc-hint">
                {csvPreview.total_rows} row(s) read — {csvPreview.to_update.length} to update,
                {' '}{csvPreview.unchanged.length} unchanged, {csvPreview.skipped.length} skipped (unknown/blank id).
              </p>
              {csvPreview.to_update.length > 0 && (
                <table style={{ marginTop: 'var(--space-3)', width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                  <thead>
                    <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                      <th>Item</th><th>Field</th><th>Old</th><th>New</th>
                    </tr>
                  </thead>
                  <tbody>
                    {csvPreview.to_update.flatMap((c) =>
                      (['title', 'note', 'tags'] as const)
                        .filter((f) => c[f])
                        .map((f) => {
                          const change = c[f]!
                          const fmt = (v: string | string[]) => (Array.isArray(v) ? v.join(', ') : v) || '—'
                          return (
                            <tr key={`${c.id}-${f}`}>
                              <td>{c.id}</td>
                              <td>{f}</td>
                              <td>{fmt(change.old)}</td>
                              <td>{fmt(change.new)}</td>
                            </tr>
                          )
                        })
                    )}
                  </tbody>
                </table>
              )}
              <div className="cc-row-tight" style={{ marginTop: 'var(--space-4)' }}>
                <button
                  className="cc-btn cc-btn--primary"
                  onClick={applyCsv}
                  disabled={csvBusy || csvPreview.to_update.length === 0}
                >
                  Apply changes
                </button>
                <button className="cc-btn" onClick={() => onCsvSelected(null)} disabled={csvBusy}>Cancel</button>
              </div>
            </div>
          )}

          {csvResult && (
            <p className="cc-hint" style={{ marginTop: 'var(--space-4)' }}>
              Applied: {csvResult.updated.length} updated, {csvResult.skipped.length} skipped.
              {csvResult.backup && <> Backup saved to <code>backups/{csvResult.backup}</code>.</>}
            </p>
          )}

          {backups.length > 0 && (
            <div style={{ marginTop: 'var(--space-5)' }}>
              <span className="cc-label" style={{ display: 'block', marginBottom: 'var(--space-2)' }}>Metadata backups</span>
              <p className="cc-hint" style={{ marginBottom: 'var(--space-3)' }}>
                Compressed snapshots taken before each import (most recent {backups.length}). Keep these until you are sure an import is correct.
              </p>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                    <th>Backup</th><th>Created</th><th>Size</th><th />
                  </tr>
                </thead>
                <tbody>
                  {backups.map((b) => (
                    <tr key={b.filename} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td><code>{b.filename}</code></td>
                      <td>{new Date(b.created_at).toLocaleString()}</td>
                      <td>{(b.size / 1024).toFixed(1)} KB</td>
                      <td style={{ textAlign: 'right' }}>
                        <button className="cc-btn cc-btn--sm cc-btn--danger" onClick={() => startDelete(b.filename)}>Delete</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {deleteTarget && (
            <div
              style={{
                marginTop: 'var(--space-4)',
                padding: 'var(--space-4)',
                borderRadius: 'var(--radius-btn)',
                border: '1px solid color-mix(in oklab, var(--danger) 40%, var(--border))',
                background: 'color-mix(in oklab, var(--danger) 8%, transparent)',
              }}
            >
              <p style={{ margin: '0 0 var(--space-3)', color: 'var(--danger)', fontSize: '0.9rem' }}>
                Permanently delete <code>{deleteTarget}</code>? This cannot be undone.
              </p>
              <p className="cc-hint" style={{ marginBottom: 'var(--space-2)' }}>
                To confirm, type <strong>{DELETE_BACKUP_CONFIRM}</strong> below.
              </p>
              <div className="cc-row-tight">
                <input
                  className="cc-input"
                  value={deleteConfirm}
                  onChange={(e) => setDeleteConfirm(e.target.value)}
                  placeholder={DELETE_BACKUP_CONFIRM}
                  autoFocus
                />
                <button
                  className="cc-btn cc-btn--danger"
                  onClick={confirmDelete}
                  disabled={deleteConfirm !== DELETE_BACKUP_CONFIRM}
                >
                  Delete this backup
                </button>
                <button className="cc-btn" onClick={() => { setDeleteTarget(null); setDeleteConfirm('') }}>Cancel</button>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
