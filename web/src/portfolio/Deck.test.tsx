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
    layout: 'slide',
    items: [makeItem()],
    ...over,
  }
}

function renderDeck(entry = '/p/my-deck') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/p/:slug" element={<Deck />} />
        <Route path="/p/:slug/:token" element={<Deck />} />
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

  it('passes the token from a tokened route to the API', async () => {
    mocked.getPublicPortfolio.mockResolvedValue(makePortfolio())
    renderDeck('/p/my-deck/secret-token')
    await waitFor(() => expect(screen.getByText('My Deck')).toBeInTheDocument())
    expect(mocked.getPublicPortfolio).toHaveBeenCalledWith('my-deck', 'secret-token')
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

  it('hides the print button in scroll layout', async () => {
    mocked.getPublicPortfolio.mockResolvedValue(makePortfolio({ layout: 'scroll' }))
    renderDeck()
    await waitFor(() => expect(screen.getByText('My Deck')).toBeInTheDocument())
    expect(screen.queryByText('Print / Export PDF')).not.toBeInTheDocument()
  })

  it.each([
    { style: 'ledger', layout: 'slide' },
    { style: 'ledger', layout: 'scroll' },
    { style: 'kinetic', layout: 'slide' },
    { style: 'kinetic', layout: 'scroll' },
    { style: 'brutalist', layout: 'scroll' },
    { style: 'riso', layout: 'scroll' },
  ] as const)('marks the deck root with $style style and $layout layout independently', async ({ style, layout }) => {
    mocked.getPublicPortfolio.mockResolvedValue(makePortfolio({ style, layout }))
    const { container } = renderDeck()
    await waitFor(() => expect(screen.getByText('My Deck')).toBeInTheDocument())
    const root = container.querySelector('.cc-deck')
    expect(root).toHaveAttribute('data-portfolio-style', style)
    expect(root).toHaveAttribute('data-portfolio-layout', layout)
  })

  it('renders the colophon section', async () => {
    mocked.getPublicPortfolio.mockResolvedValue(makePortfolio())
    renderDeck()
    await waitFor(() => expect(screen.getByText('About this work')).toBeInTheDocument())
    expect(screen.getByText('A portfolio of 1 works shared via CatalogueCanvas.')).toBeInTheDocument()
  })
})
