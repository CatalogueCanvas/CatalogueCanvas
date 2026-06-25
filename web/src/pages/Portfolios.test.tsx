import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Portfolios } from './Portfolios'
import type { Portfolio } from '../api/client'

vi.mock('../api/client', () => ({
  listPortfolios: vi.fn(),
  createPortfolio: vi.fn(),
  deletePortfolio: vi.fn(),
}))

vi.mock('../api/auth', () => ({
  useAuth: () => ({ isAdmin: true }),
}))

vi.mock('../components/Icon', () => ({
  Icon: ({ name }: { name: string }) => <span data-testid={`icon-${name}`} />,
}))

import * as api from '../api/client'
const mocked = vi.mocked(api)

afterEach(() => vi.clearAllMocks())

function makePortfolio(over: Partial<Portfolio> = {}): Portfolio {
  return { id: 'p-1', title: 'My Portfolio', slug: 'my-portfolio', is_public: false, item_ids: [], ...over }
}

function renderPage() {
  return render(<MemoryRouter><Portfolios /></MemoryRouter>)
}

describe('Portfolios', () => {
  it('shows empty state when there are no portfolios', async () => {
    mocked.listPortfolios.mockResolvedValue([])
    renderPage()
    await waitFor(() => expect(screen.getByText('No portfolios yet')).toBeInTheDocument())
  })

  it('renders portfolios with public/private badges', async () => {
    mocked.listPortfolios.mockResolvedValue([
      makePortfolio({ is_public: true }),
      makePortfolio({ id: 'p-2', title: 'Draft', slug: 'draft', is_public: false }),
    ])
    renderPage()
    await waitFor(() => expect(screen.getByText('My Portfolio')).toBeInTheDocument())
    expect(screen.getByText('Public')).toBeInTheDocument()
    expect(screen.getByText('Private')).toBeInTheDocument()
  })

  it('creates a portfolio and refreshes', async () => {
    mocked.listPortfolios.mockResolvedValue([])
    mocked.createPortfolio.mockResolvedValue(makePortfolio())
    renderPage()
    await waitFor(() => expect(screen.getByText('No portfolios yet')).toBeInTheDocument())

    mocked.listPortfolios.mockResolvedValue([makePortfolio()])
    await userEvent.type(screen.getByPlaceholderText('New portfolio title'), 'My Portfolio')
    await userEvent.click(screen.getByText('Create'))
    await waitFor(() => expect(mocked.createPortfolio).toHaveBeenCalledWith({ title: 'My Portfolio' }))
  })

  it('does not create with blank title', async () => {
    mocked.listPortfolios.mockResolvedValue([])
    renderPage()
    await waitFor(() => expect(screen.getByText('No portfolios yet')).toBeInTheDocument())
    await userEvent.click(screen.getByText('Create'))
    expect(mocked.createPortfolio).not.toHaveBeenCalled()
  })

  it('deletes a portfolio after confirmation', async () => {
    mocked.listPortfolios.mockResolvedValue([makePortfolio()])
    mocked.deletePortfolio.mockResolvedValue(undefined)
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderPage()
    await waitFor(() => expect(screen.getByText('My Portfolio')).toBeInTheDocument())

    mocked.listPortfolios.mockResolvedValue([])
    await userEvent.click(screen.getByText('Delete'))
    await waitFor(() => expect(mocked.deletePortfolio).toHaveBeenCalledWith('p-1'))
  })

  it('shows View link only for public portfolios', async () => {
    mocked.listPortfolios.mockResolvedValue([
      makePortfolio({ is_public: true }),
    ])
    renderPage()
    await waitFor(() => expect(screen.getByText('View')).toBeInTheDocument())
  })
})
