import { useEffect, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import * as api from '../api/client'
import type { Item, DescribeResult, AppSettings } from '../api/client'
import { LLMButton } from '../components/LLMButton'
import { MetadataForm } from '../components/MetadataForm'
import { NotesPanel } from '../components/NotesPanel'
import { Icon } from '../components/Icon'
import { useAppearance } from '../api/appearance'
import { useAuth } from '../api/auth'

export function ItemEdit() {
  const { id } = useParams<{ id: string }>()
  const [item, setItem] = useState<Item | null>(null)
  const [llmResult, setLlmResult] = useState<DescribeResult | null>(null)
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [itemIds, setItemIds] = useState<string[]>([])
  const navigate = useNavigate()
  const { appearance } = useAppearance()
  const { isAdmin } = useAuth()

  useEffect(() => {
    if (id) void api.getItem(id).then(setItem)
  }, [id])

  useEffect(() => {
    if (isAdmin) void api.getSettings().then(setSettings)
  }, [isAdmin])

  useEffect(() => {
    void api.listItems().then((items) => { setItemIds(items.map((i) => i.id)) })
  }, [])

  const currentIndex = item ? itemIds.indexOf(item.id) : -1
  const prevId = currentIndex > 0 ? itemIds[currentIndex - 1] : null
  const nextId = currentIndex >= 0 && currentIndex < itemIds.length - 1 ? itemIds[currentIndex + 1] : null

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      // eslint-disable-next-line xss/no-mixed-html
      const el = e.target as HTMLElement
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable) return
      if (e.key === 'ArrowLeft' && prevId) { void navigate(`/items/${prevId}`) }
      else if (e.key === 'ArrowRight' && nextId) { void navigate(`/items/${nextId}`) }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => { window.removeEventListener('keydown', onKeyDown) }
  }, [prevId, nextId, navigate])

  if (!item) return <div className="container"><div className="cc-empty"><p className="cc-empty__title">Loading...</p></div></div>

  const applyDescription = async () => {
    if (!llmResult) return
    const note = [llmResult.summary, '', ...llmResult.descriptions.map((d) => `- ${d}`)].join('\n')
    const updated = await api.updateItem(item.id, { note })
    setItem(updated)
    setLlmResult(null)
  }

  const remove = async () => {
    if (!confirm(`Delete item ${item.id}? This cannot be undone.`)) return
    await api.deleteItem(item.id)
    navigate('/')
  }

  const toggleFavorite = async () => {
    const isFavorite = item.collection_ids.includes('favorites')
    const updated = isFavorite ? await api.unfavoriteItem(item.id) : await api.favoriteItem(item.id)
    setItem(updated)
  }

  return (
    <div className="container">
      {prevId && (
        <Link to={`/items/${prevId}`} className="cc-item-nav cc-item-nav--prev" aria-label="Previous item">‹</Link>
      )}
      {nextId && (
        <Link to={`/items/${nextId}`} className="cc-item-nav cc-item-nav--next" aria-label="Next item">›</Link>
      )}
      <div className="cc-page-header">
        <div>
          <p className="cc-kicker">Catalogue</p>
          <h1 className="cc-h1">{item.title}</h1>
        </div>
        {isAdmin && appearance.favoritesEnabled && (
          <button
            className="cc-btn"
            onClick={() => void toggleFavorite()}
            aria-pressed={item.collection_ids.includes('favorites')}
          >
            <Icon name={item.collection_ids.includes('favorites') ? 'heartFilled' : 'heart'} size={15} />
            {item.collection_ids.includes('favorites') ? 'Favorited' : 'Favorite'}
          </button>
        )}
        {isAdmin && (
          <button className="cc-btn cc-btn--danger" onClick={() => void remove()}><Icon name="delete" size={15} />Delete</button>
        )}
      </div>
      <div className="cc-itemedit">
        <div className="cc-itemedit__media">
          <div className="cc-thumb cc-thumb--lg">
            {item.preview_url ? <img src={item.preview_url} alt={item.title} /> : <span className="cc-thumb__label">no preview</span>}
          </div>
          {item.download_urls.filter((d) => d.type === 'image').length > 0 && (
            <div className="cc-thumbrow">
              {item.download_urls.filter((d) => d.type === 'image').map((d) => (
                <a key={d.url} href={d.url} target="_blank" rel="noreferrer">
                  <img src={d.url} alt={d.name} />
                </a>
              ))}
            </div>
          )}
        </div>
        <div className="cc-stack">
          <div className="cc-row__meta">
            <span className="cc-mono">ID: {item.id}</span>
            <a className="cc-mono" href={api.itemMetadataUrl(item.id)} target="_blank" rel="noreferrer">Metadata (JSON-LD)</a>
          </div>
          {item.download_urls.length > 0 && (
            <div className="cc-field">
              <label className="cc-label">Files</label>
              <div className="cc-files">
                {item.download_urls.map((d) => (
                  d.type === 'other'
                    ? (
                      <a key={d.url} className="cc-pill" href={d.url} download>
                        {d.name} <span className="cc-pill-type">{d.type}</span>
                      </a>
                    )
                    : (
                      <a key={d.url} className="cc-pill" href={d.url} target="_blank" rel="noreferrer">
                        {d.name} <span className="cc-pill-type">{d.type}</span>
                      </a>
                    )
                ))}
              </div>
            </div>
          )}
          <div>
            <a className="cc-btn" href={api.itemArchiveUrl(item.id)} download><Icon name="download" size={15} />Download all as ZIP</a>
          </div>
          <div className="cc-panel">
            <MetadataForm item={item} onSaved={setItem} readOnly={!isAdmin} />
          </div>
          {isAdmin && settings?.llm_auto_generate === 'true' && <LLMButton itemId={item.id} itemTitle={item.title} onResult={setLlmResult} />}
          {llmResult && (
            <div className="cc-llm__result">
              <strong>Summary:</strong> {llmResult.summary}
              <ul>
                {llmResult.descriptions.map((d, i) => <li key={i}>{d}</li>)}
              </ul>
              <button className="cc-btn cc-btn--primary" onClick={() => void applyDescription()} type="button">Apply to note</button>
            </div>
          )}
        </div>
      </div>
      <NotesPanel item={item} onSaved={setItem} readOnly={!isAdmin} />
    </div>
  )
}
