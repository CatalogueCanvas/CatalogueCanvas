import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import * as api from '../api/client'
import type { Portfolio } from '../api/client'
import { Icon } from '../components/Icon'
import { useAuth } from '../api/auth'

export function Portfolios() {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([])
  const [title, setTitle] = useState('')
  const { isAdmin } = useAuth()

  const refresh = () => api.listPortfolios().then(setPortfolios)
  useEffect(() => { refresh() }, [])

  const create = async () => {
    if (!title.trim()) return
    await api.createPortfolio({ title: title.trim() })
    setTitle('')
    refresh()
  }

  const remove = async (id: string) => {
    if (!confirm('Delete this portfolio?')) return
    await api.deletePortfolio(id)
    refresh()
  }

  return (
    <div className="container">
      <div className="cc-page-header">
        <div>
          <p className="cc-kicker">Share</p>
          <h1 className="cc-h1">Portfolios<span className="cc-count">({portfolios.length})</span></h1>
        </div>
      </div>
      {isAdmin && (
        <div className="cc-createbar">
          <input className="cc-input" placeholder="New portfolio title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <button className="cc-btn cc-btn--primary" onClick={create}><Icon name="create" size={15} />Create</button>
        </div>
      )}
      {portfolios.length === 0 ? (
        <div className="cc-empty">
          <p className="cc-empty__title">No portfolios yet</p>
        </div>
      ) : (
        <div className="cc-list">
          {portfolios.map((p) => (
            <div className="cc-row" key={p.id}>
              <div className="cc-row__main">
                <h3 className="cc-row__title">{p.title}</h3>
                <div className="cc-row__meta">
                  <span className="cc-mono">/p/{p.slug}</span>
                  <span className="cc-dot" />
                  <span className={`cc-badge${p.is_public ? ' cc-badge--public' : ''}`}>{p.is_public ? 'Public' : 'Private'}</span>
                  <span className="cc-dot" />
                  <span>{p.item_ids.length} items</span>
                </div>
              </div>
              <div className="cc-row__actions">
                {p.is_public && <a className="cc-btn cc-btn--sm" href={`/p/${p.slug}`} target="_blank" rel="noreferrer"><Icon name="view" size={14} />View</a>}
                {isAdmin && <Link className="cc-btn cc-btn--sm" to={`/portfolios/${p.id}`}><Icon name="edit" size={14} />Edit</Link>}
                {isAdmin && <button className="cc-btn cc-btn--danger cc-btn--sm" onClick={() => remove(p.id)}><Icon name="delete" size={14} />Delete</button>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
