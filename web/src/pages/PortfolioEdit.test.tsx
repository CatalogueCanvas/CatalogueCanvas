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
  mintShareToken: vi.fn(),
  clearShareToken: vi.fn(),
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
    is_public: false, item_ids: [], style: 'ledger', layout: 'slide',
    description: '', watermark_enabled: false, watermark_text: '', share_token: '', created_at: '',
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

  it('shows tokened share link and Require token button', async () => {
    mocked.getPortfolio.mockResolvedValue(makePortfolio({ is_public: true, share_token: 'abc123' }))
    mocked.listItems.mockResolvedValue([])
    mocked.updatePortfolio.mockResolvedValue(makePortfolio({ is_public: true, share_token: 'abc123' }))
    renderPage()
    await waitFor(() => expect(screen.getByText(/\/p\/my-portfolio\/abc123/)).toBeInTheDocument())
    expect(screen.getByText('Regenerate token')).toBeInTheDocument()
    expect(screen.getByText('Disable token')).toBeInTheDocument()
  })

  it('copies the share link to the clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })
    mocked.getPortfolio.mockResolvedValue(makePortfolio({ is_public: true, share_token: 'abc123' }))
    mocked.listItems.mockResolvedValue([])
    mocked.updatePortfolio.mockResolvedValue(makePortfolio({ is_public: true, share_token: 'abc123' }))
    renderPage()
    await waitFor(() => expect(screen.getByText('Copy')).toBeInTheDocument())
    await userEvent.click(screen.getByText('Copy'))
    expect(writeText).toHaveBeenCalledWith('http://localhost:3000/p/my-portfolio/abc123')
    await waitFor(() => expect(screen.getByText('Copied')).toBeInTheDocument())
  })

  it('mints a token when Require token is clicked', async () => {
    mocked.getPortfolio.mockResolvedValue(makePortfolio({ is_public: true }))
    mocked.listItems.mockResolvedValue([])
    mocked.updatePortfolio.mockResolvedValue(makePortfolio({ is_public: true }))
    mocked.mintShareToken.mockResolvedValue({ share_token: 'newtoken' })
    renderPage()
    await waitFor(() => expect(screen.getByText('Require token')).toBeInTheDocument())
    await userEvent.click(screen.getByText('Require token'))
    await waitFor(() => expect(mocked.mintShareToken).toHaveBeenCalledWith('p-1'))
  })

  it('clears the token when Disable token is clicked', async () => {
    mocked.getPortfolio.mockResolvedValue(makePortfolio({ is_public: true, share_token: 'abc123' }))
    mocked.listItems.mockResolvedValue([])
    mocked.updatePortfolio.mockResolvedValue(makePortfolio({ is_public: true, share_token: 'abc123' }))
    mocked.clearShareToken.mockResolvedValue({ ok: true })
    renderPage()
    await waitFor(() => expect(screen.getByText('Disable token')).toBeInTheDocument())
    await userEvent.click(screen.getByText('Disable token'))
    await waitFor(() => expect(mocked.clearShareToken).toHaveBeenCalledWith('p-1'))
  })

  it('deletes portfolio after confirmation', async () => {
    mocked.getPortfolio.mockResolvedValue(makePortfolio())
    mocked.listItems.mockResolvedValue([])
    mocked.deletePortfolio.mockResolvedValue({ ok: true })
    mocked.updatePortfolio.mockResolvedValue(makePortfolio())
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderPage()
    await waitFor(() => expect(screen.getByText('Delete')).toBeInTheDocument())

    await userEvent.click(screen.getByText('Delete'))
    await waitFor(() => expect(mocked.deletePortfolio).toHaveBeenCalledWith('p-1'))
  })

  it('renders layout radio buttons', async () => {
    mocked.getPortfolio.mockResolvedValue(makePortfolio())
    mocked.listItems.mockResolvedValue([])
    mocked.updatePortfolio.mockResolvedValue(makePortfolio())
    renderPage()
    await waitFor(() => expect(screen.getByText('Slides')).toBeInTheDocument())
    expect(screen.getByText('Scrolling page')).toBeInTheDocument()
  })

  it('saves the layout immediately without changing the theme', async () => {
    mocked.getPortfolio.mockResolvedValue(makePortfolio({ style: 'riso' }))
    mocked.listItems.mockResolvedValue([])
    mocked.updatePortfolio.mockResolvedValue(makePortfolio({ style: 'riso', layout: 'scroll' }))
    renderPage()
    await waitFor(() => expect(screen.getByText('Scrolling page')).toBeInTheDocument())
    await userEvent.click(screen.getByText('Scrolling page'))
    await waitFor(() => expect(mocked.updatePortfolio).toHaveBeenCalledWith(
      'p-1',
      expect.objectContaining({ layout: 'scroll', style: 'riso' }),
    ))
  })

  it('saves the theme without changing the layout', async () => {
    mocked.getPortfolio.mockResolvedValue(makePortfolio({ layout: 'scroll' }))
    mocked.listItems.mockResolvedValue([])
    mocked.updatePortfolio.mockResolvedValue(makePortfolio({ style: 'brutalist', layout: 'scroll' }))
    renderPage()
    await waitFor(() => expect(screen.getByText('Brutalist')).toBeInTheDocument())
    await userEvent.click(screen.getByText('Brutalist'))
    await waitFor(() => expect(mocked.updatePortfolio).toHaveBeenCalledWith(
      'p-1',
      expect.objectContaining({ style: 'brutalist', layout: 'scroll' }),
    ))
  })

  it('shows watermark input when watermark is enabled', async () => {
    mocked.getPortfolio.mockResolvedValue(makePortfolio({ watermark_enabled: true }))
    mocked.listItems.mockResolvedValue([])
    mocked.updatePortfolio.mockResolvedValue(makePortfolio({ watermark_enabled: true }))
    renderPage()
    await waitFor(() => expect(screen.getByPlaceholderText('© Your Name')).toBeInTheDocument())
  })
})
