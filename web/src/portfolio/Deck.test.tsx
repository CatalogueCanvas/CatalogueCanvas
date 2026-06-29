import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { Deck } from './Deck'
import type { Item, PublicPortfolio } from '../api/client'

vi.mock('../api/client', () => ({
  getPublicPortfolio: vi.fn(),
}))

vi.mock('react-markdown', () => ({
  default: ({ children }: { children: string }) => <div data-testid="markdown">{children}</div>,
}))

import * as api from '../api/client'
const mocked = vi.mocked(api)

afterEach(() => vi.clearAllMocks())

function makeItem(over: Partial<Item> = {}): Item {
  return {
    id: 'item-1', content_hash: 'h', title: 'Work One', note: 'A note',
    mime_type: 'image/png', preview_path: 'p.png', preview_url: '/p.png',
    other_files: [], download_urls: [], tags: ['generative'], collection_ids: [],
    raw_meta: {}, ingested_at: '', imported_at: null,
    width: 800, height: 600, library_id: 'lib1', ...over,
  }
}

function makePortfolio(over: Partial<PublicPortfolio> = {}): PublicPortfolio {
  return {
    title: 'My Deck',
    slug: 'my-deck',
    description: 'A portfolio description',
    style: 'ledger',
    items: [makeItem()],
    ...over,
  }
}

function renderDeck() {
  return render(
    <MemoryRouter initialEntries={['/p/my-deck']}>
      <Routes>
        <Route path="/p/:slug" element={<Deck />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('Deck', () => {
  it('shows error when portfolio not found', async () => {
    mocked.getPublicPortfolio.mockRejectedValue(new Error('not found'))
    renderDeck()
    await waitFor(() => expect(screen.getByText('Portfolio not found.')).toBeInTheDocument())
  })

  it('renders portfolio cover with title', async () => {
    mocked.getPublicPortfolio.mockResolvedValue(makePortfolio())
    renderDeck()
    await waitFor(() => expect(screen.getByText('My Deck')).toBeInTheDocument())
    expect(screen.getByText('Portfolio · 1 works')).toBeInTheDocument()
  })

  it('renders items as work sections', async () => {
    mocked.getPublicPortfolio.mockResolvedValue(makePortfolio())
    renderDeck()
    await waitFor(() => expect(screen.getAllByText('Work One').length).toBeGreaterThan(0))
  })

  it('renders index page for ledger style', async () => {
    mocked.getPublicPortfolio.mockResolvedValue(makePortfolio({ style: 'ledger' }))
    renderDeck()
    await waitFor(() => expect(screen.getByText('Works')).toBeInTheDocument())
  })

  it('renders kinetic-style index with marquee', async () => {
    mocked.getPublicPortfolio.mockResolvedValue(makePortfolio({ style: 'kinetic' }))
    renderDeck()
    await waitFor(() => expect(screen.getByText('Selected')).toBeInTheDocument())
    expect(screen.getAllByText('Archival Systems').length).toBeGreaterThan(0)
  })

  it('shows item tags in work sections', async () => {
    mocked.getPublicPortfolio.mockResolvedValue(makePortfolio())
    renderDeck()
    await waitFor(() => expect(screen.getByText('generative')).toBeInTheDocument())
  })

  it('shows print button', async () => {
    mocked.getPublicPortfolio.mockResolvedValue(makePortfolio())
    renderDeck()
    await waitFor(() => expect(screen.getByText('Print / Export PDF')).toBeInTheDocument())
  })

  it('renders the colophon section', async () => {
    mocked.getPublicPortfolio.mockResolvedValue(makePortfolio())
    renderDeck()
    await waitFor(() => expect(screen.getByText('About this work')).toBeInTheDocument())
    expect(screen.getByText('A portfolio of 1 works shared via CatalogueCanvas.')).toBeInTheDocument()
  })
})
