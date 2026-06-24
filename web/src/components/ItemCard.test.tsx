import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ItemCard } from './ItemCard'
import type { Item } from '../api/client'

function makeItem(over: Partial<Item> = {}): Item {
  return {
    id: 'apple-001',
    content_hash: 'h',
    title: 'My Item',
    note: '',
    mime_type: 'image/webp',
    preview_path: 'p.webp',
    preview_url: '/storage/p.webp',
    other_files: [],
    download_urls: [],
    tags: ['red', 'fruit'],
    collection_ids: [],
    raw_meta: {},
    ingested_at: '',
    imported_at: null,
    width: null,
    height: null,
    library_id: 'lib1',
    ...over,
  }
}

function renderCard(props: Parameters<typeof ItemCard>[0]) {
  return render(<MemoryRouter><ItemCard {...props} /></MemoryRouter>)
}

describe('ItemCard', () => {
  it('renders title, id, and up to three tags', () => {
    renderCard({ item: makeItem({ tags: ['a', 'b', 'c', 'd'] }) })
    expect(screen.getByText('My Item')).toBeInTheDocument()
    expect(screen.getByText('apple-001')).toBeInTheDocument()
    expect(screen.queryByText('d')).not.toBeInTheDocument()
  })

  it('shows a no-preview label when preview_url is missing', () => {
    renderCard({ item: makeItem({ preview_url: null }) })
    expect(screen.getByText('no preview')).toBeInTheDocument()
  })

  it('calls onToggle when the select control is clicked', async () => {
    const onToggle = vi.fn()
    renderCard({ item: makeItem(), onToggle })
    await userEvent.click(screen.getByRole('checkbox'))
    expect(onToggle).toHaveBeenCalledWith('apple-001')
  })

  it('toggles favorite and reflects pressed state', async () => {
    const onToggleFavorite = vi.fn()
    renderCard({
      item: makeItem({ collection_ids: ['favorites'] }),
      favoritesEnabled: true,
      onToggleFavorite,
    })
    const btn = screen.getByRole('button', { name: /Remove from favorites/ })
    expect(btn).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(btn)
    expect(onToggleFavorite).toHaveBeenCalled()
  })
})
