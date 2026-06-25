import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Dashboard } from './Dashboard'
import type { Item } from '../api/client'

vi.mock('../api/client', () => ({
  listItems: vi.fn(),
  searchItems: vi.fn(),
  listPortfolios: vi.fn(),
  favoriteItem: vi.fn(),
  unfavoriteItem: vi.fn(),
}))

vi.mock('../api/selection', () => ({
  useSelection: () => ({
    batchMode: false,
    selected: new Set(),
    toggleSelect: vi.fn(),
    selectAll: vi.fn(),
    clear: vi.fn(),
  }),
}))

vi.mock('../api/appearance', () => ({
  useAppearance: () => ({ appearance: { favoritesEnabled: false } }),
}))

vi.mock('../api/auth', () => ({
  useAuth: () => ({ isAdmin: true }),
}))

vi.mock('../components/ItemCard', () => ({
  ItemCard: ({ item }: { item: Item }) => <div data-testid="item-card">{item.title}</div>,
}))

vi.mock('../components/BulkToolbar', () => ({
  BulkToolbar: () => <div data-testid="bulk-toolbar">BulkToolbar</div>,
}))

vi.mock('../components/Icon', () => ({
  Icon: ({ name }: { name: string }) => <span data-testid={`icon-${name}`} />,
}))

import * as api from '../api/client'
const mocked = vi.mocked(api)

afterEach(() => vi.clearAllMocks())

function makeItem(over: Partial<Item> = {}): Item {
  return {
    id: 'item-1', content_hash: 'h', title: 'Test Item', note: '',
    mime_type: 'image/png', preview_path: 'p.png', preview_url: '/p.png',
    other_files: [], download_urls: [], tags: ['art'], collection_ids: [],
    raw_meta: {}, ingested_at: '2024-01-01', imported_at: null,
    width: null, height: null, library_id: 'lib1', ...over,
  }
}

function renderPage() {
  return render(<MemoryRouter><Dashboard /></MemoryRouter>)
}

describe('Dashboard', () => {
  it('shows loading state initially', () => {
    mocked.listItems.mockReturnValue(new Promise(() => {}))
    mocked.listPortfolios.mockReturnValue(new Promise(() => {}))
    renderPage()
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('shows empty state when no items', async () => {
    mocked.listItems.mockResolvedValue([])
    mocked.listPortfolios.mockResolvedValue([])
    renderPage()
    await waitFor(() => expect(screen.getByText('No items yet')).toBeInTheDocument())
  })

  it('renders items', async () => {
    mocked.listItems.mockResolvedValue([makeItem()])
    mocked.listPortfolios.mockResolvedValue([])
    renderPage()
    await waitFor(() => expect(screen.getByText('Test Item')).toBeInTheDocument())
  })

  it('shows search input', async () => {
    mocked.listItems.mockResolvedValue([])
    mocked.listPortfolios.mockResolvedValue([])
    renderPage()
    expect(screen.getByPlaceholderText('Search items...')).toBeInTheDocument()
  })

  it('opens filter panel when clicked', async () => {
    mocked.listItems.mockResolvedValue([makeItem()])
    mocked.listPortfolios.mockResolvedValue([])
    renderPage()
    await waitFor(() => expect(screen.getByText('Test Item')).toBeInTheDocument())

    await userEvent.click(screen.getByText(/Filter/))
    expect(screen.getByText('Newest first')).toBeInTheDocument()
  })

  it('shows item count', async () => {
    mocked.listItems.mockResolvedValue([makeItem(), makeItem({ id: 'item-2', title: 'Second' })])
    mocked.listPortfolios.mockResolvedValue([])
    renderPage()
    await waitFor(() => expect(screen.getByText('(2)')).toBeInTheDocument())
  })
})
