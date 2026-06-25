import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

let mockAuth = { authenticated: true, loading: false, isAdmin: true, role: 'admin' as string | null, username: 'admin' as string | null, multiUser: false, login: vi.fn(), logout: vi.fn() }

vi.mock('./api/auth', () => ({
  useAuth: () => mockAuth,
}))

vi.mock('./api/appearance', () => ({
  ACCENT_PRESETS: { vermilion: { accent: '#e54d2e', dim: '#4a2218', contrast: '#fff' } },
  useAppearance: () => ({
    appearance: { theme: 'light', nav: 'side', density: 'default', accent: 'vermilion' },
    setAppearance: vi.fn(),
  }),
}))

vi.mock('./api/selection', () => ({
  SelectionProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useSelection: () => ({ batchMode: false, toggleBatchMode: vi.fn() }),
}))

vi.mock('./api/activity', () => ({
  ActivityProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useActivity: () => ({ tasks: [], removeTask: vi.fn(), clearFinished: vi.fn() }),
}))

vi.mock('./pages/Dashboard', () => ({ Dashboard: () => <div>Dashboard Page</div> }))
vi.mock('./pages/Login', () => ({ Login: () => <div>Login Page</div> }))
vi.mock('./pages/ItemEdit', () => ({ ItemEdit: () => <div>ItemEdit Page</div> }))
vi.mock('./pages/Collections', () => ({ Collections: () => <div>Collections Page</div> }))
vi.mock('./pages/CollectionEdit', () => ({ CollectionEdit: () => <div>CollectionEdit Page</div> }))
vi.mock('./pages/Portfolios', () => ({ Portfolios: () => <div>Portfolios Page</div> }))
vi.mock('./pages/PortfolioEdit', () => ({ PortfolioEdit: () => <div>PortfolioEdit Page</div> }))
vi.mock('./pages/Settings', () => ({ Settings: () => <div>Settings Page</div> }))
vi.mock('./pages/Upload', () => ({ Upload: () => <div>Upload Page</div> }))
vi.mock('./pages/NotFound', () => ({ NotFound: () => <div>NotFound Page</div> }))
vi.mock('./portfolio/Deck', () => ({ Deck: () => <div>Deck Page</div> }))
vi.mock('./components/Nav', () => ({ Nav: () => <nav>Nav</nav> }))
vi.mock('./components/Footer', () => ({ Footer: () => <footer>Footer</footer> }))
vi.mock('./components/ActivityTray', () => ({ ActivityTray: () => null }))

import App from './App'

afterEach(() => {
  vi.clearAllMocks()
  mockAuth = { authenticated: true, loading: false, isAdmin: true, role: 'admin', username: 'admin', multiUser: false, login: vi.fn(), logout: vi.fn() }
})

function renderApp(route = '/') {
  return render(<MemoryRouter initialEntries={[route]}><App /></MemoryRouter>)
}

describe('App', () => {
  it('renders the dashboard for authenticated users at /', async () => {
    renderApp('/')
    await waitFor(() => expect(screen.getByText('Dashboard Page')).toBeInTheDocument())
  })

  it('redirects unauthenticated users to /login', async () => {
    mockAuth = { ...mockAuth, authenticated: false, loading: false }
    renderApp('/')
    await waitFor(() => expect(screen.getByText('Login Page')).toBeInTheDocument())
  })

  it('redirects non-admin users from admin routes to /', async () => {
    mockAuth = { ...mockAuth, isAdmin: false, role: 'reader' }
    renderApp('/settings')
    await waitFor(() => expect(screen.getByText('Dashboard Page')).toBeInTheDocument())
  })

  it('renders the login page at /login', () => {
    renderApp('/login')
    expect(screen.getByText('Login Page')).toBeInTheDocument()
  })

  it('renders NotFound for unknown routes', async () => {
    renderApp('/nonexistent')
    await waitFor(() => expect(screen.getByText('NotFound Page')).toBeInTheDocument())
  })
})
