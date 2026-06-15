import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import * as api from '../api/client'
import type { Collection, Item } from '../api/client'
import { ItemCard } from '../components/ItemCard'
import { Icon } from '../components/Icon'

export function CollectionEdit() {
  const { id } = useParams<{ id: string }>()
  const [collection, setCollection] = useState<Collection | null>(null)
  const [items, setItems] = useState<Item[]>([])
  const navigate = useNavigate()

  useEffect(() => {
    if (!id) return
    api.getCollection(id).then(setCollection)
    api.getCollectionItems(id).then(setItems)
  }, [id])

  if (!collection) return <div className="container"><div className="cc-empty"><p className="cc-empty__title">Loading...</p></div></div>

  const save = async () => {
    const updated = await api.updateCollection(collection.id, {
      title: collection.title,
      description: collection.description,
    })
    setCollection(updated)
  }

  const remove = async () => {
    if (!confirm(`Delete collection "${collection.id}"?`)) return
    await api.deleteCollection(collection.id)
    navigate('/collections')
  }

  return (
    <div className="container">
      <div className="cc-page-header">
        <div>
          <p className="cc-kicker">Organize</p>
          <h1 className="cc-h1">{collection.title}</h1>
        </div>
        {!collection.is_system && (
          <button className="cc-btn cc-btn--danger" onClick={remove}><Icon name="delete" size={15} />Delete</button>
        )}
      </div>
      {!collection.is_system && (
        <div className="cc-panel cc-stack">
          <div className="cc-field">
            <label className="cc-label" htmlFor="title">Title</label>
            <input id="title" className="cc-input" value={collection.title} onChange={(e) => setCollection({ ...collection, title: e.target.value })} />
          </div>
          <div className="cc-field">
            <label className="cc-label" htmlFor="description">Description (markdown)</label>
            <textarea id="description" className="cc-textarea" rows={4} value={collection.description} onChange={(e) => setCollection({ ...collection, description: e.target.value })} />
          </div>
          <div>
            <button className="cc-btn cc-btn--primary" onClick={save}><Icon name="save" size={15} />Save</button>
          </div>
        </div>
      )}

      <div className="cc-section">
        <div className="cc-section__head">
          <h2 className="cc-h2">Items<span className="cc-count">({items.length})</span></h2>
        </div>
        {items.length === 0 ? (
          <div className="cc-empty">
            <p className="cc-empty__title">No items in this collection</p>
            <p className="cc-empty__sub">Assign items from their edit page.</p>
          </div>
        ) : (
          <div className="cc-grid">
            {items.map((item) => <ItemCard key={item.id} item={item} />)}
          </div>
        )}
      </div>
    </div>
  )
}
