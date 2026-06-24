import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import * as api from '../api/client'
import type { Item, Portfolio, PortfolioStyle } from '../api/client'
import { Icon } from '../components/Icon'

const STYLES: { value: PortfolioStyle; label: string }[] = [
  { value: 'ledger', label: 'Ledger' },
  { value: 'kinetic', label: 'Kinetic' },
  { value: 'brutalist', label: 'Brutalist' },
  { value: 'riso', label: 'Riso' },
]

type SaveState = 'idle' | 'saving' | 'saved'

export function PortfolioEdit() {
  const { id } = useParams<{ id: string }>()
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null)
  const [items, setItems] = useState<Item[]>([])
  const [saveState, setSaveState] = useState<SaveState>('idle')
  // Transient export options — not persisted, only applied on download.
  const [exportQuality, setExportQuality] = useState(85)
  const [exportResize, setExportResize] = useState(false)
  const [exportMaxEdge, setExportMaxEdge] = useState(1280)
  const navigate = useNavigate()
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)
  const latest = useRef<Portfolio | null>(null)

  useEffect(() => {
    if (!id) return
    void api.getPortfolio(id).then((p) => { latest.current = p; setPortfolio(p) })
    void api.listItems().then(setItems)
  }, [id])

  // Persist the current portfolio. Toggles/items flush now; text debounces.
  const flush = async () => {
    const p = latest.current
    if (!p) return
    setSaveState('saving')
    const updated = await api.updatePortfolio(p.id, {
      title: p.title,
      description: p.description,
      slug: p.slug,
      item_ids: p.item_ids,
      is_public: p.is_public,
      style: p.style,
      watermark_enabled: p.watermark_enabled,
      watermark_text: p.watermark_text,
    })
    latest.current = updated
    setSaveState('saved')
  }

  // Apply a change locally and schedule a save. `immediate` flushes at once
  // (toggles, radios, item picks); text edits debounce to avoid a PATCH/keystroke.
  const update = (patch: Partial<Portfolio>, immediate = false) => {
    if (!portfolio) return
    const next = { ...portfolio, ...patch }
    latest.current = next
    setPortfolio(next)
    setSaveState('saving')
    clearTimeout(timer.current)
    if (immediate) void flush()
    else timer.current = setTimeout(() => void flush(), 500)
  }

  useEffect(() => () => clearTimeout(timer.current), [])

  if (!portfolio) return <div className="container"><div className="cc-empty"><p className="cc-empty__title">Loading...</p></div></div>

  const toggleItem = (itemId: string) => {
    const item_ids = portfolio.item_ids.includes(itemId)
      ? portfolio.item_ids.filter((i) => i !== itemId)
      : [...portfolio.item_ids, itemId]
    update({ item_ids }, true)
  }

  const remove = async () => {
    if (!confirm('Delete this portfolio?')) return
    await api.deletePortfolio(portfolio.id)
    void navigate('/portfolios')
  }

  const shareUrl = `${window.location.origin}/p/${portfolio.slug}`

  return (
    <div className="container">
      <div className="cc-page-header">
        <div>
          <p className="cc-kicker">Share</p>
          <h1 className="cc-h1">{portfolio.title}</h1>
        </div>
        <button className="cc-btn cc-btn--danger" onClick={() => void remove()}><Icon name="delete" size={15} />Delete</button>
      </div>

      <div className="cc-panel cc-stack">
        <div className="cc-field">
          <label className="cc-label" htmlFor="title">Title</label>
          <input id="title" className="cc-input" value={portfolio.title} onChange={(e) => update({ title: e.target.value })} />
        </div>
        <div className="cc-field">
          <label className="cc-label" htmlFor="slug">Slug</label>
          <input id="slug" className="cc-input" value={portfolio.slug} onChange={(e) => update({ slug: e.target.value })} />
        </div>
        <div className="cc-field">
          <label className="cc-label" htmlFor="description">Description (markdown)</label>
          <textarea id="description" className="cc-textarea" rows={4} value={portfolio.description} onChange={(e) => update({ description: e.target.value })} />
        </div>
        <div className="cc-field">
          <label className="cc-label">Theme</label>
          <div className="cc-row-tight">
            {STYLES.map((s) => (
              <label className="cc-check" key={s.value}>
                <input
                  type="radio"
                  name="style"
                  checked={portfolio.style === s.value}
                  onChange={() => update({ style: s.value }, true)}
                />
                <span className="cc-check__box" />
                {s.label}
              </label>
            ))}
          </div>
        </div>
        <div className="cc-field">
          <label className="cc-check">
            <input
              type="checkbox"
              checked={portfolio.watermark_enabled}
              onChange={(e) => update({ watermark_enabled: e.target.checked }, true)}
            />
            <span className="cc-check__box" />
            Watermark exported images
          </label>
          {portfolio.watermark_enabled && (
            <>
              <input
                className="cc-input"
                placeholder="© Your Name"
                value={portfolio.watermark_text}
                onChange={(e) => update({ watermark_text: e.target.value })}
                style={{ marginTop: 'var(--space-2)' }}
              />
              <p className="cc-hint">Burned into the images in the exported zip only. The live deck is unaffected.</p>
            </>
          )}
        </div>
        <label className="cc-check">
          <input
            id="public"
            type="checkbox"
            checked={portfolio.is_public}
            onChange={(e) => update({ is_public: e.target.checked }, true)}
          />
          <span className="cc-check__box" />
          Public
        </label>
        {portfolio.is_public && (
          <div className="cc-field">
            <label className="cc-label">Share link</label>
            <div className="cc-sharebox">{shareUrl}</div>
            <div className="cc-field">
              <label className="cc-label" htmlFor="export-quality">Image quality<span className="cc-count">({exportQuality})</span></label>
              <input
                id="export-quality"
                type="range"
                min={40}
                max={95}
                value={exportQuality}
                onChange={(e) => setExportQuality(Number(e.target.value))}
              />
            </div>
            <label className="cc-check">
              <input type="checkbox" checked={exportResize} onChange={(e) => setExportResize(e.target.checked)} />
              <span className="cc-check__box" />
              Resize images for screen
            </label>
            {exportResize && (
              <div className="cc-field">
                <label className="cc-label" htmlFor="export-maxedge">Max size<span className="cc-count">({exportMaxEdge}px)</span></label>
                <input
                  id="export-maxedge"
                  type="range"
                  min={480}
                  max={4000}
                  step={80}
                  value={exportMaxEdge}
                  onChange={(e) => setExportMaxEdge(Number(e.target.value))}
                />
              </div>
            )}
            <p className="cc-hint">Lower quality or smaller size makes a lighter zip — handy for sharing on screen. Full resolution and quality 85 keep the originals.</p>
            <div className="cc-row-tight">
              <a className="cc-btn" href={`/p/${portfolio.slug}`} target="_blank" rel="noreferrer">Preview deck</a>
              <button className="cc-btn" type="button" onClick={() => void (async () => { clearTimeout(timer.current); await flush(); void api.exportPortfolioStatic(portfolio.id, { quality: exportQuality, max_edge: exportResize ? exportMaxEdge : null }) })()}>
                <Icon name="download" size={15} />Export static site (.zip)
              </button>
            </div>
            <p className="cc-hint">Unzip and host the folder anywhere static — Codeberg Pages, GitHub Pages, Netlify, Cloudflare Pages. No server needed.</p>
          </div>
        )}
      </div>

      <div className="cc-section">
        <div className="cc-section__head">
          <h2 className="cc-h2">Items<span className="cc-count">({portfolio.item_ids.length} selected)</span></h2>
        </div>
        <div className="cc-picker">
          {items.map((item) => (
            <div className="cc-picker__item" key={item.id} data-on={portfolio.item_ids.includes(item.id)} onClick={() => toggleItem(item.id)}>
              <div className="cc-thumb">
                {item.preview_url ? <img src={item.preview_url} alt={item.title} loading="lazy" /> : <span className="cc-thumb__label">no preview</span>}
              </div>
              <div className="cc-picker__bar">
                <label className="cc-check" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={portfolio.item_ids.includes(item.id)}
                    onChange={() => toggleItem(item.id)}
                  />
                  <span className="cc-check__box" />
                </label>
                <h3 className="cc-card__title">{item.title}</h3>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="cc-row-tight" style={{ marginTop: 'var(--space-5)' }}>
        {saveState === 'saving' && <span className="cc-saved">Saving…</span>}
        {saveState === 'saved' && <span className="cc-saved">All changes saved.</span>}
      </div>
    </div>
  )
}
