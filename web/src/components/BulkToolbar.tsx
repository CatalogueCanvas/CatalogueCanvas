import { useRef, useState } from 'react'
import * as api from '../api/client'
import type { Item, Portfolio } from '../api/client'
import { Icon } from './Icon'
import { useAppearance } from '../api/appearance'

interface Props {
  selectedIds: string[]
  items: Item[]
  portfolios: Portfolio[]
  totalCount: number
  onDone: () => void
  onClear: () => void
  onSelectAll: () => void
}

export function BulkToolbar({ selectedIds, items, portfolios, totalCount, onDone, onClear, onSelectAll }: Props) {
  const [tagsInput, setTagsInput] = useState('')
  const [portfolioId, setPortfolioId] = useState('')
  const [portfolioAction, setPortfolioAction] = useState<'add' | 'remove'>('add')
  const [skipExisting, setSkipExisting] = useState(true)
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState('')
  const [errors, setErrors] = useState<string[]>([])
  const cancelRef = useRef(false)
  const { appearance } = useAppearance()

  const selectedItems = items.filter((i) => selectedIds.includes(i.id))

  const clearNotes = async () => {
    if (!confirm(`Clear notes on ${selectedIds.length} item(s)?`)) return
    setBusy(true)
    try {
      await api.bulkClearNotes(selectedIds)
      onDone()
    } finally {
      setBusy(false)
    }
  }

  const download = async () => {
    setBusy(true)
    try {
      await api.downloadBulkArchive(selectedIds)
    } finally {
      setBusy(false)
    }
  }

  const addTags = async () => {
    const tags = tagsInput.split(',').map((t) => t.trim()).filter(Boolean)
    if (tags.length === 0) return
    setBusy(true)
    try {
      await api.bulkAddTags(selectedIds, tags)
      setTagsInput('')
      onDone()
    } finally {
      setBusy(false)
    }
  }

  const addFavorites = async () => {
    setBusy(true)
    try {
      await api.bulkFavorite(selectedIds)
      onDone()
    } finally {
      setBusy(false)
    }
  }

  const removeFavorites = async () => {
    setBusy(true)
    try {
      await api.bulkUnfavorite(selectedIds)
      onDone()
    } finally {
      setBusy(false)
    }
  }

  const applyPortfolio = async () => {
    if (!portfolioId) return
    setBusy(true)
    try {
      await api.updatePortfolioItems(portfolioId, selectedIds, portfolioAction)
      onDone()
    } finally {
      setBusy(false)
    }
  }

  const generateDescriptions = async () => {
    setBusy(true)
    setErrors([])
    cancelRef.current = false
    try {
      const settings = await api.getSettings()
      const targets = skipExisting ? selectedItems.filter((i) => !i.note) : selectedItems
      const newErrors: string[] = []
      for (let i = 0; i < targets.length; i++) {
        if (cancelRef.current) break
        const item = targets[i]
        setProgress(`Processing ${i + 1}/${targets.length}...`)
        try {
          const result = await api.describeItem(item.id, {
            api_url: settings.llm_api_url,
            model: settings.llm_model,
            item_type: settings.llm_item_type,
            summary_focus: settings.llm_summary_focus,
            bullet_count: Number(settings.llm_bullet_count) || 3,
            bullet_max_words: Number(settings.llm_bullet_max_words) || 50,
            prompt_template: settings.llm_prompt_template,
          })
          await api.updateItem(item.id, { note: result.summary })
        } catch (err) {
          newErrors.push(`${item.title}: ${err instanceof Error ? err.message : 'failed'}`)
        }
      }
      setErrors(newErrors)
      onDone()
    } finally {
      setBusy(false)
      setProgress('')
    }
  }

  return (
    <div className="cc-bulk-toolbar">
      <div className="cc-bulk-toolbar__row">
        <span className="cc-bulk-toolbar__count">{selectedIds.length} selected</span>
        <button className="cc-btn" onClick={onSelectAll} disabled={busy}>Select all ({totalCount})</button>
        <button className="cc-btn" onClick={onClear} disabled={busy}>Clear selection</button>
        <button className="cc-btn cc-btn--danger" onClick={clearNotes} disabled={busy}><Icon name="delete" size={15} />Clear notes</button>
        <button className="cc-btn" onClick={download} disabled={busy}><Icon name="download" size={15} />Download zip</button>
        {appearance.favoritesEnabled && (
          <>
            <button className="cc-btn" onClick={addFavorites} disabled={busy}><Icon name="heart" size={15} />Add to Favorites</button>
            <button className="cc-btn" onClick={removeFavorites} disabled={busy}><Icon name="heartFilled" size={15} />Remove from Favorites</button>
          </>
        )}
        <input
          className="cc-input"
          placeholder="tag1, tag2..."
          value={tagsInput}
          onChange={(e) => setTagsInput(e.target.value)}
          disabled={busy}
        />
        <button className="cc-btn" onClick={addTags} disabled={busy || !tagsInput.trim()}>Add tags</button>
        <select className="cc-input" value={portfolioId} onChange={(e) => setPortfolioId(e.target.value)} disabled={busy}>
          <option value="">Portfolio...</option>
          {portfolios.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
        </select>
        <select className="cc-input" value={portfolioAction} onChange={(e) => setPortfolioAction(e.target.value as 'add' | 'remove')} disabled={busy}>
          <option value="add">Add to</option>
          <option value="remove">Remove from</option>
        </select>
        <button className="cc-btn" onClick={applyPortfolio} disabled={busy || !portfolioId}>Apply</button>
      </div>
      <div className="cc-bulk-toolbar__row">
        <label className="cc-check">
          <input type="checkbox" checked={skipExisting} onChange={(e) => setSkipExisting(e.target.checked)} disabled={busy} />
          <span className="cc-check__box" />
          Skip items that already have a note
        </label>
        <button className="cc-btn cc-btn--primary" onClick={generateDescriptions} disabled={busy}>
          {busy && progress ? progress : <><Icon name="generate" size={15} />Generate descriptions (LLM)</>}
        </button>
        {busy && progress && (
          <button className="cc-btn" onClick={() => { cancelRef.current = true }}>Cancel</button>
        )}
      </div>
      {errors.length > 0 && (
        <div className="error-text">
          {errors.map((e) => <div key={e}>{e}</div>)}
        </div>
      )}
    </div>
  )
}
