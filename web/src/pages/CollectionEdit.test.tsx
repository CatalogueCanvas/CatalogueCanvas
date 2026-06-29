import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { CollectionEdit } from './CollectionEdit'
import type { Collection, Item } from '../api/client'

vi.mock('../api/client', () => ({
  getCollection: vi.fn(),
  getCollectionItems: vi.fn(),
  updateCollection: vi.fn(),
  deleteCollection: vi.fn(),
}))

vi.mock('../api/auth', () => ({
  useAuth: () => ({ isAdmin: true }),
}))

vi.mock('../components/ItemCard', () => ({
  ItemCard: ({ item }: { item: Item }) => <div data-testid="item-card">{item.title}</div>,
}))

vi.mock('../components/Icon', () => ({
  Icon: ({ name }: { name: string }) => <span data-testid={`icon-${name}`} />,
}))

import * as api from '../api/client'
const mocked = vi.mocked(api)

afterEach(() => vi.clearAllMocks())

function makeCollection(over: Partial<Collection> = {}): Collection {
  return { id: 'col-1', title: 'My Collection', is_system: false, description: '', cover_item_id: null, created_at: '', ...over }
}

function makeItem(over: Partial<Item> = {}): Item {
  return {
    id: 'item-1', content_hash: 'h', title: 'Test Item', note: '',
    mime_type: 'image/png', preview_path: 'p.png', preview_url: '/p.png',
    other_files: [], download_urls: [], tags: [], collection_ids: [],
    raw_meta: {}, ingested_at: '', imported_at: null,
    width: null, height: null, library_id: 'lib1', ...over,
  }
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/collections/col-1']}>
      <Routes>
        <Route path="/collections/:id" element={<CollectionEdit />} />
        <Route path="/collections" element={<div>Collections List</div>} />
      </Routes>
    </MemoryRouter>
  )
}

describe('CollectionEdit', () => {
  it('shows loading state initially', () => {
    mocked.getCollection.mockReturnValue(new Promise(() => {}))
    mocked.getCollectionItems.mockReturnValue(new Promise(() => {}))
    renderPage()
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders collection title and edit form', async () => {
    mocked.getCollection.mockResolvedValue(makeCollection())
    mocked.getCollectionItems.mockResolvedValue([])
    renderPage()
    await waitFor(() => expect(screen.getByText('My Collection')).toBeInTheDocument())
    expect(screen.getByLabelText('Title')).toHaveValue('My Collection')
  })

  it('renders items in the collection', async () => {
    mocked.getCollection.mockResolvedValue(makeCollection())
    mocked.getCollectionItems.mockResolvedValue([makeItem()])
    renderPage()
    await waitFor(() => expect(screen.getByText('Test Item')).toBeInTheDocument())
  })

  it('shows empty state when no items', async () => {
    mocked.getCollection.mockResolvedValue(makeCollection())
    mocked.getCollectionItems.mockResolvedValue([])
    renderPage()
    await waitFor(() => expect(screen.getByText('No items in this collection')).toBeInTheDocument())
  })

  it('saves collection changes', async () => {
    const col = makeCollection()
    mocked.getCollection.mockResolvedValue(col)
    mocked.getCollectionItems.mockResolvedValue([])
    mocked.updateCollection.mockResolvedValue(col)
    renderPage()
    await waitFor(() => expect(screen.getByLabelText('Title')).toBeInTheDocument())

    await userEvent.click(screen.getByText('Save'))
    await waitFor(() => expect(mocked.updateCollection).toHaveBeenCalledWith('col-1', {
      title: 'My Collection', description: '',
    }))
  })

  it('deletes collection after confirmation', async () => {
    mocked.getCollection.mockResolvedValue(makeCollection())
    mocked.getCollectionItems.mockResolvedValue([])
    mocked.deleteCollection.mockResolvedValue({ ok: true })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderPage()
    await waitFor(() => expect(screen.getByText('Delete')).toBeInTheDocument())

    await userEvent.click(screen.getByText('Delete'))
    await waitFor(() => expect(mocked.deleteCollection).toHaveBeenCalledWith('col-1'))
  })
})
