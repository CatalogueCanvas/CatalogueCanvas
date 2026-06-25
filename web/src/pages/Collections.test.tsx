import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Collections } from './Collections'
import type { Collection } from '../api/client'

vi.mock('../api/client', () => ({
  listCollections: vi.fn(),
  createCollection: vi.fn(),
  deleteCollection: vi.fn(),
}))

vi.mock('../api/appearance', () => ({
  useAppearance: () => ({ appearance: { favoritesEnabled: false } }),
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

function makeCol(over: Partial<Collection> = {}): Collection {
  return { id: 'col-1', title: 'Test Collection', is_system: false, item_count: 0, ...over }
}

function renderPage() {
  return render(<MemoryRouter><Collections /></MemoryRouter>)
}

describe('Collections', () => {
  it('shows empty state when there are no collections', async () => {
    mocked.listCollections.mockResolvedValue([])
    renderPage()
    await waitFor(() => expect(screen.getByText('No collections yet')).toBeInTheDocument())
  })

  it('renders a list of collections', async () => {
    mocked.listCollections.mockResolvedValue([makeCol(), makeCol({ id: 'col-2', title: 'Second' })])
    renderPage()
    await waitFor(() => expect(screen.getByText('Test Collection')).toBeInTheDocument())
    expect(screen.getByText('Second')).toBeInTheDocument()
  })

  it('creates a collection and refreshes the list', async () => {
    mocked.listCollections.mockResolvedValue([])
    mocked.createCollection.mockResolvedValue(makeCol({ id: 'new', title: 'New' }))
    renderPage()
    await waitFor(() => expect(screen.getByText('No collections yet')).toBeInTheDocument())

    mocked.listCollections.mockResolvedValue([makeCol({ id: 'new', title: 'New' })])
    await userEvent.type(screen.getByPlaceholderText('New collection title'), 'New')
    await userEvent.click(screen.getByText('Create'))
    await waitFor(() => expect(mocked.createCollection).toHaveBeenCalledWith({ title: 'New' }))
  })

  it('does not create a collection with blank title', async () => {
    mocked.listCollections.mockResolvedValue([])
    renderPage()
    await waitFor(() => expect(screen.getByText('No collections yet')).toBeInTheDocument())
    await userEvent.click(screen.getByText('Create'))
    expect(mocked.createCollection).not.toHaveBeenCalled()
  })

  it('deletes a collection after confirmation', async () => {
    mocked.listCollections.mockResolvedValue([makeCol()])
    mocked.deleteCollection.mockResolvedValue(undefined)
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderPage()
    await waitFor(() => expect(screen.getByText('Test Collection')).toBeInTheDocument())

    mocked.listCollections.mockResolvedValue([])
    await userEvent.click(screen.getByText('Delete'))
    await waitFor(() => expect(mocked.deleteCollection).toHaveBeenCalledWith('col-1'))
  })
})
