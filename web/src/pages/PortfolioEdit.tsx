import { useEffect, useState } from 'react'
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

export function PortfolioEdit() {
  const { id } = useParams<{ id: string }>()
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null)
  const [items, setItems] = useState<Item[]>([])
  const [saved, setSaved] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    if (!id) return
    api.getPortfolio(id).then(setPortfolio)
    api.listItems().then(setItems)
  }, [id])

  if (!portfolio) return <div className="container"><div className="cc-empty"><p className="cc-empty__title">Loading...</p></div></div>

  const toggleItem = (itemId: string) => {
    const item_ids = portfolio.item_ids.includes(itemId)
      ? portfolio.item_ids.filter((i) => i !== itemId)
      : [...portfolio.item_ids, itemId]
    setPortfolio({ ...portfolio, item_ids })
  }

  const save = async () => {
    setSaved(false)
    const updated = await api.updatePortfolio(portfolio.id, {
      title: portfolio.title,
      description: portfolio.description,
      slug: portfolio.slug,
      item_ids: portfolio.item_ids,
      is_public: portfolio.is_public,
      style: portfolio.style,
    })
    setPortfolio(updated)
    setSaved(true)
  }

  const remove = async () => {
    if (!confirm('Delete this portfolio?')) return
    await api.deletePortfolio(portfolio.id)
    navigate('/portfolios')
  }

  const shareUrl = `${window.location.origin}/p/${portfolio.slug}`

  return (
    <div className="container">
      <div className="cc-page-header">
        <div>
          <p className="cc-kicker">Share</p>
          <h1 className="cc-h1">{portfolio.title}</h1>
        </div>
        <button className="cc-btn cc-btn--danger" onClick={remove}><Icon name="delete" size={15} />Delete</button>
      </div>

      <div className="cc-panel cc-stack">
        <div className="cc-field">
          <label className="cc-label" htmlFor="title">Title</label>
          <input id="title" className="cc-input" value={portfolio.title} onChange={(e) => setPortfolio({ ...portfolio, title: e.target.value })} />
        </div>
        <div className="cc-field">
          <label className="cc-label" htmlFor="slug">Slug</label>
          <input id="slug" className="cc-input" value={portfolio.slug} onChange={(e) => setPortfolio({ ...portfolio, slug: e.target.value })} />
        </div>
        <div className="cc-field">
          <label className="cc-label" htmlFor="description">Description (markdown)</label>
          <textarea id="description" className="cc-textarea" rows={4} value={portfolio.description} onChange={(e) => setPortfolio({ ...portfolio, description: e.target.value })} />
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
                  onChange={() => setPortfolio({ ...portfolio, style: s.value })}
                />
                <span className="cc-check__box" />
                {s.label}
              </label>
            ))}
          </div>
        </div>
        <label className="cc-check">
          <input
            id="public"
            type="checkbox"
            checked={portfolio.is_public}
            onChange={(e) => setPortfolio({ ...portfolio, is_public: e.target.checked })}
          />
          <span className="cc-check__box" />
          Public
        </label>
        {portfolio.is_public && (
          <div className="cc-field">
            <label className="cc-label">Share link</label>
            <div className="cc-sharebox">{shareUrl}</div>
            <div className="cc-row-tight">
              <a className="cc-btn" href={`/p/${portfolio.slug}`} target="_blank" rel="noreferrer">Preview deck</a>
              <button className="cc-btn" type="button" onClick={() => api.exportPortfolioStatic(portfolio.id)}>
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
        <button className="cc-btn cc-btn--primary" onClick={save}><Icon name="save" size={15} />Save</button>
        {saved && <span className="cc-saved">Saved.</span>}
      </div>
    </div>
  )
}
