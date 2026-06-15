import { useEffect, useState } from 'react'
import * as api from '../api/client'
import type { Accent, AppSettings, Density, NavLayout, Theme } from '../api/client'
import { ApiError } from '../api/client'
import { ACCENT_PRESETS, useAppearance } from '../api/appearance'

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
          <h1 className="cc-h1">Settings</h1>
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
                value={settings.llm_api_url}
                onChange={(e) => setSettings({ ...settings, llm_api_url: e.target.value })}
              />
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
          </div>
        </section>
      </div>
    </div>
  )
}
