import { useCallback, useEffect, useMemo, useState } from 'react'
import * as api from '../api/client'
import type { Item, Portfolio } from '../api/client'
import { ItemCard } from '../components/ItemCard'
import { BulkToolbar } from '../components/BulkToolbar'
import { Icon } from '../components/Icon'
import { useSelection } from '../api/selection'

type SortBy = 'date-new' | 'date-old' | 'title-asc' | 'title-desc' | 'note' | 'no-note'

export function Dashboard() {
  const [items, setItems] = useState<Item[]>([])
  const [portfolios, setPortfolios] = useState<Portfolio[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [sortBy, setSortBy] = useState<SortBy>('date-new')
  const [tagFilter, setTagFilter] = useState('')
  const [filtersOpen, setFiltersOpen] = useState(false)
  const { batchMode, selected, toggleSelect, selectAll, clear } = useSelection()

  const refresh = useCallback(() => {
    api.listItems().then(setItems).finally(() => setLoading(false))
    api.listPortfolios().then(setPortfolios)
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const allTags = useMemo(() => {
    const tags = new Set<string>()
    items.forEach((i) => i.tags.forEach((t) => tags.add(t)))
    return [...tags].sort((a, b) => a.localeCompare(b))
  }, [items])

  const filtered = useMemo(() => {
    const q = query.toLowerCase()
    let result = items.filter((i) => {
      return !q || i.title.toLowerCase().includes(q) || i.id.includes(q) || i.tags.some((t) => t.toLowerCase().includes(q))
    })
    if (tagFilter) {
      result = result.filter((i) => i.tags.includes(tagFilter))
    }
    result = [...result]
    switch (sortBy) {
      case 'title-asc':
        result.sort((a, b) => a.title.localeCompare(b.title))
        break
      case 'title-desc':
        result.sort((a, b) => b.title.localeCompare(a.title))
        break
      case 'date-new':
        result.sort((a, b) => (b.imported_at ?? b.ingested_at).localeCompare(a.imported_at ?? a.ingested_at))
        break
      case 'date-old':
        result.sort((a, b) => (a.imported_at ?? a.ingested_at).localeCompare(b.imported_at ?? b.ingested_at))
        break
      case 'note':
        result.sort((a, b) => Number(!!b.note) - Number(!!a.note))
        break
      case 'no-note':
        result.sort((a, b) => Number(!!a.note) - Number(!!b.note))
        break
    }
    return result
  }, [items, query, tagFilter, sortBy])

  const onBulkDone = () => {
    clear()
    refresh()
  }

  return (
    <div className="container">
      <div className="cc-page-header">
        <div>
          <p className="cc-kicker">Catalogue</p>
          <h1 className="cc-h1">Items<span className="cc-count">({items.length})</span></h1>
        </div>
        <div className="cc-search">
          <span className="cc-search__icon" />
          <input className="cc-input" placeholder="Search items..." value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
      </div>
      <div className="cc-filterbar">
        <button
          type="button"
          className="cc-btn cc-btn--sm cc-btn--ghost cc-filterbar__toggle"
          onClick={() => setFiltersOpen((o) => !o)}
          aria-expanded={filtersOpen}
        >
          <Icon name="filter" size={14} />
          Filter &amp; sort
          {tagFilter && <span className="cc-filterbar__badge">{tagFilter}</span>}
          <Icon name="chevronDown" size={14} className={filtersOpen ? 'cc-filterbar__chevron--open' : ''} />
        </button>
        {filtersOpen && (
          <div className="cc-row-tight cc-filterbar__panel">
            <select className="cc-input cc-select" value={sortBy} onChange={(e) => setSortBy(e.target.value as SortBy)}>
              <option value="date-new">Newest first</option>
              <option value="date-old">Oldest first</option>
              <option value="title-asc">Title A-Z</option>
              <option value="title-desc">Title Z-A</option>
              <option value="note">Has note first</option>
              <option value="no-note">No note first</option>
            </select>
            <select className="cc-input cc-select" value={tagFilter} onChange={(e) => setTagFilter(e.target.value)}>
              <option value="">All tags</option>
              {allTags.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        )}
      </div>
      {batchMode && (
        <BulkToolbar
          selectedIds={[...selected]}
          items={items}
          portfolios={portfolios}
          totalCount={filtered.length}
          onDone={onBulkDone}
          onClear={clear}
          onSelectAll={() => selectAll(filtered.map((i) => i.id))}
        />
      )}
      {loading ? (
        <div className="cc-empty">
          <p className="cc-empty__title">Loading...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="cc-empty">
          <p className="cc-empty__title">No items yet</p>
          <p className="cc-empty__sub">Add items from the Upload page.</p>
        </div>
      ) : (
        <div className="cc-grid">
          {filtered.map((item) => (
            <ItemCard
              key={item.id}
              item={item}
              selected={batchMode ? selected.has(item.id) : undefined}
              onToggle={batchMode ? toggleSelect : undefined}
            />
          ))}
        </div>
      )}
    </div>
  )
}
