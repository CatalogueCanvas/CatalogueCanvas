import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Nav } from './Nav'

const mockLogout = vi.fn()
const mockToggleBatchMode = vi.fn()
const mockSetAppearance = vi.fn()

vi.mock('../api/auth', () => ({
  useAuth: () => ({
    authenticated: true,
    isAdmin: true,
    username: 'admin',
    logout: mockLogout,
  }),
}))

vi.mock('../api/appearance', () => ({
  useAppearance: () => ({
    appearance: { theme: 'light', nav: 'side', density: 'default', accent: 'vermilion' },
    setAppearance: mockSetAppearance,
  }),
}))

vi.mock('../api/selection', () => ({
  useSelection: () => ({
    batchMode: false,
    toggleBatchMode: mockToggleBatchMode,
  }),
}))

vi.mock('./Icon', () => ({
  Icon: ({ name }: { name: string }) => <span data-testid={`icon-${name}`} />,
}))

afterEach(() => vi.clearAllMocks())

describe('Nav', () => {
  it('renders core navigation links', () => {
    render(<MemoryRouter initialEntries={['/']}><Nav /></MemoryRouter>)
    expect(screen.getByText('Items')).toBeInTheDocument()
    expect(screen.getByText('Collections')).toBeInTheDocument()
    expect(screen.getByText('Portfolios')).toBeInTheDocument()
  })

  it('shows admin-only links for admin users', () => {
    render(<MemoryRouter initialEntries={['/']}><Nav /></MemoryRouter>)
    expect(screen.getByText('Upload')).toBeInTheDocument()
    expect(screen.getByText('Settings/Admin')).toBeInTheDocument()
  })

  it('shows batch edit button on items page', () => {
    render(<MemoryRouter initialEntries={['/']}><Nav /></MemoryRouter>)
    expect(screen.getByText('Batch edit')).toBeInTheDocument()
  })

  it('calls logout when Log out is clicked', async () => {
    render(<MemoryRouter initialEntries={['/']}><Nav /></MemoryRouter>)
    await userEvent.click(screen.getByText('Log out'))
    expect(mockLogout).toHaveBeenCalled()
  })

  it('displays the username', () => {
    render(<MemoryRouter initialEntries={['/']}><Nav /></MemoryRouter>)
    expect(screen.getByText('admin')).toBeInTheDocument()
  })
})
