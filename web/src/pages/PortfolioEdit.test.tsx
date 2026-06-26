import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { PortfolioEdit } from './PortfolioEdit'
import type { Item, Portfolio } from '../api/client'

vi.mock('../api/client', () => ({
  getPortfolio: vi.fn(),
  listItems: vi.fn(),
  updatePortfolio: vi.fn(),
  deletePortfolio: vi.fn(),
  exportPortfolioStatic: vi.fn(),
}))

vi.mock('../components/Icon', () => ({
  Icon: ({ name }: { name: string }) => <span data-testid={`icon-${name}`} />,
}))

import * as api from '../api/client'
const mocked = vi.mocked(api)

afterEach(() => vi.clearAllMocks())

function makePortfolio(over: Partial<Portfolio> = {}): Portfolio {
  return {
    id: 'p-1', title: 'My Portfolio', slug: 'my-portfolio',
    is_public: false, item_ids: [], style: 'ledger',
    description: '', watermark_enabled: false, watermark_text: '',
    ...over,
  }
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
    <MemoryRouter initialEntries={['/portfolios/p-1']}>
      <Routes>
        <Route path="/portfolios/:id" element={<PortfolioEdit />} />
        <Route path="/portfolios" element={<div>Portfolios List</div>} />
      </Routes>
    </MemoryRouter>
  )
}

describe('PortfolioEdit', () => {
  it('shows loading state', () => {
    mocked.getPortfolio.mockReturnValue(new Promise(() => {}))
    mocked.listItems.mockReturnValue(new Promise(() => {}))
    renderPage()
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders portfolio title and form', async () => {
    mocked.getPortfolio.mockResolvedValue(makePortfolio())
    mocked.listItems.mockResolvedValue([])
    mocked.updatePortfolio.mockResolvedValue(makePortfolio())
    renderPage()
    await waitFor(() => expect(screen.getByText('My Portfolio')).toBeInTheDocument())
    expect(screen.getByLabelText('Title')).toHaveValue('My Portfolio')
    expect(screen.getByLabelText('Slug')).toHaveValue('my-portfolio')
  })

  it('renders theme radio buttons', async () => {
    mocked.getPortfolio.mockResolvedValue(makePortfolio())
    mocked.listItems.mockResolvedValue([])
    mocked.updatePortfolio.mockResolvedValue(makePortfolio())
    renderPage()
    await waitFor(() => expect(screen.getByText('Ledger')).toBeInTheDocument())
    expect(screen.getByText('Kinetic')).toBeInTheDocument()
    expect(screen.getByText('Brutalist')).toBeInTheDocument()
    expect(screen.getByText('Riso')).toBeInTheDocument()
  })

  it('renders item picker', async () => {
    mocked.getPortfolio.mockResolvedValue(makePortfolio())
    mocked.listItems.mockResolvedValue([makeItem()])
    mocked.updatePortfolio.mockResolvedValue(makePortfolio())
    renderPage()
    await waitFor(() => expect(screen.getByText('Test Item')).toBeInTheDocument())
  })

  it('shows public toggle and share link when public', async () => {
    mocked.getPortfolio.mockResolvedValue(makePortfolio({ is_public: true }))
    mocked.listItems.mockResolvedValue([])
    mocked.updatePortfolio.mockResolvedValue(makePortfolio({ is_public: true }))
    renderPage()
    await waitFor(() => expect(screen.getByText(/\/p\/my-portfolio/)).toBeInTheDocument())
  })

  it('deletes portfolio after confirmation', async () => {
    mocked.getPortfolio.mockResolvedValue(makePortfolio())
    mocked.listItems.mockResolvedValue([])
    mocked.deletePortfolio.mockResolvedValue(undefined)
    mocked.updatePortfolio.mockResolvedValue(makePortfolio())
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderPage()
    await waitFor(() => expect(screen.getByText('Delete')).toBeInTheDocument())

    await userEvent.click(screen.getByText('Delete'))
    await waitFor(() => expect(mocked.deletePortfolio).toHaveBeenCalledWith('p-1'))
  })

  it('shows watermark input when watermark is enabled', async () => {
    mocked.getPortfolio.mockResolvedValue(makePortfolio({ watermark_enabled: true }))
    mocked.listItems.mockResolvedValue([])
    mocked.updatePortfolio.mockResolvedValue(makePortfolio({ watermark_enabled: true }))
    renderPage()
    await waitFor(() => expect(screen.getByPlaceholderText('© Your Name')).toBeInTheDocument())
  })
})
