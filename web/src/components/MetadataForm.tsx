import { useEffect, useRef, useState } from 'react'
import * as api from '../api/client'
import type { Collection, Item } from '../api/client'

export function MetadataForm({ item, onSaved, readOnly = false }: { item: Item; onSaved: (item: Item) => void; readOnly?: boolean }) {
  const [title, setTitle] = useState(item.title)
  const [tags, setTags] = useState(item.tags.join(', '))
  const [collectionIds, setCollectionIds] = useState<string[]>(item.collection_ids.filter((id) => id !== 'favorites'))
  const [collections, setCollections] = useState<Collection[]>([])
  const [editingCollections, setEditingCollections] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const savedTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => () => { if (savedTimer.current) clearTimeout(savedTimer.current) }, [])

  useEffect(() => {
    api.listCollections().then((cols) => { setCollections(cols.filter((c) => !c.is_system)) }).catch(() => {})
  }, [])

  useEffect(() => {
    // Resync the editable draft when a different item is loaded.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTitle(item.title)
    setTags(item.tags.join(', '))
    setCollectionIds(item.collection_ids.filter((id) => id !== 'favorites'))
    setEditingCollections(false)
  }, [item])

  const toggleCollection = (id: string) => {
    setCollectionIds((prev) => (prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]))
  }

  const save = async () => {
    setSaving(true)
    try {
      const isFavorite = item.collection_ids.includes('favorites')
      const updated = await api.updateItem(item.id, {
        title,
        tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
        collection_ids: isFavorite ? [...collectionIds, 'favorites'] : collectionIds,
      })
      onSaved(updated)
      setEditingCollections(false)
      setSaved(true)
      if (savedTimer.current) clearTimeout(savedTimer.current)
      savedTimer.current = setTimeout(() => { setSaved(false) }, 1800)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="cc-form">
      <div className="cc-field">
        <label className="cc-label" htmlFor="title">Title</label>
        <input id="title" className="cc-input" value={title} onChange={(e) => { setTitle(e.target.value) }} disabled={readOnly} />
      </div>
      <div className="cc-field">
        <label className="cc-label" htmlFor="tags">Tags (comma separated)</label>
        <input id="tags" className="cc-input" value={tags} onChange={(e) => { setTags(e.target.value) }} disabled={readOnly} />
        {item.tags.length > 0 ? (
          <div className="cc-card__tags cc-form__tags">
            {item.tags.map((t) => <span className="cc-tag" key={t}>{t}</span>)}
          </div>
        ) : (
          <p className="cc-empty__sub">No tags yet.</p>
        )}
      </div>
      <div className="cc-field">
        <label className="cc-label">Collections</label>
        {collections.length === 0 ? (
          <p className="cc-empty__sub">No collections yet.</p>
        ) : editingCollections ? (
          <div className="cc-checklist">
            {collections.map((c) => (
              <label className="cc-check" key={c.id}>
                <input
                  type="checkbox"
                  checked={collectionIds.includes(c.id)}
                  onChange={() => { toggleCollection(c.id) }}
                  disabled={readOnly}
                />
                <span className="cc-check__box" />
                {c.title}
              </label>
            ))}
          </div>
        ) : (
          <>
            {collectionIds.length > 0 ? (
              <div className="cc-card__tags cc-form__tags">
                {collections
                  .filter((c) => collectionIds.includes(c.id))
                  .map((c) => <span className="cc-tag" key={c.id}>{c.title}</span>)}
              </div>
            ) : (
              <p className="cc-empty__sub">None.</p>
            )}
            {!readOnly && (
              <button
                type="button"
                className="cc-btn cc-btn--sm"
                onClick={() => { setEditingCollections(true) }}
              >
                Edit
              </button>
            )}
          </>
        )}
      </div>
      {!readOnly && (
        <button className="cc-btn cc-btn--primary" onClick={() => void save()} disabled={saving}>
          {saving ? 'Saving...' : saved ? 'Saved ✓' : 'Save'}
        </button>
      )}
    </div>
  )
}
