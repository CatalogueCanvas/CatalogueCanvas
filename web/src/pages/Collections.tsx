import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import * as api from '../api/client'
import type { Collection } from '../api/client'
import { Icon } from '../components/Icon'
import { useAppearance } from '../api/appearance'
import { useAuth } from '../api/auth'

export function Collections() {
  const [collections, setCollections] = useState<Collection[]>([])
  const [title, setTitle] = useState('')
  const { appearance } = useAppearance()
  const { isAdmin } = useAuth()

  const refresh = useCallback(() => api.listCollections().then((cols) => {
    setCollections(cols.filter((c) => !c.is_system || appearance.favoritesEnabled))
  }), [appearance.favoritesEnabled])
  useEffect(() => { void refresh() }, [refresh])

  const create = async () => {
    if (!title.trim()) return
    await api.createCollection({ title: title.trim() })
    setTitle('')
    void refresh()
  }

  const remove = async (id: string) => {
    if (!confirm(`Delete collection "${id}"? Items will be unassigned.`)) return
    await api.deleteCollection(id)
    void refresh()
  }

  return (
    <div className="container">
      <div className="cc-page-header">
        <div>
          <p className="cc-kicker">Organize</p>
          <h1 className="cc-h1">Collections<span className="cc-count">({collections.length})</span></h1>
        </div>
      </div>
      {isAdmin && (
        <div className="cc-createbar">
          <input className="cc-input" placeholder="New collection title" value={title} onChange={(e) => { setTitle(e.target.value) }} />
          <button className="cc-btn cc-btn--primary" onClick={() => void create()}><Icon name="create" size={15} />Create</button>
        </div>
      )}
      {collections.length === 0 ? (
        <div className="cc-empty">
          <p className="cc-empty__title">No collections yet</p>
        </div>
      ) : (
        <div className="cc-list">
          {collections.map((c) => (
            <div className="cc-row" key={c.id}>
              <div className="cc-row__main">
                <h3 className="cc-row__title">{c.title}</h3>
                <div className="cc-row__meta"><span>{c.id}</span></div>
              </div>
              <div className="cc-row__actions">
                {c.is_system || !isAdmin ? (
                  <Link className="cc-btn cc-btn--sm" to={`/collections/${c.id}`}><Icon name="view" size={14} />Open</Link>
                ) : (
                  <>
                    <Link className="cc-btn cc-btn--sm" to={`/collections/${c.id}`}><Icon name="edit" size={14} />Edit</Link>
                    <button className="cc-btn cc-btn--danger cc-btn--sm" onClick={() => void remove(c.id)}><Icon name="delete" size={14} />Delete</button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
