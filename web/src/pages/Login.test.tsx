import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Login } from './Login'
import { ApiError } from '../api/client'

const mockLogin = vi.fn()
const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../api/auth', () => ({
  useAuth: () => ({
    login: mockLogin,
    multiUser: false,
  }),
}))

afterEach(() => vi.clearAllMocks())

function renderLogin() {
  return render(<MemoryRouter><Login /></MemoryRouter>)
}

describe('Login', () => {
  it('renders the password field and submit button', () => {
    renderLogin()
    expect(screen.getByLabelText('Admin password')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Log in' })).toBeInTheDocument()
  })

  it('does not show the username field in single-user mode', () => {
    renderLogin()
    expect(screen.queryByLabelText('Username')).not.toBeInTheDocument()
  })

  it('submits the password and navigates on success', async () => {
    mockLogin.mockResolvedValue(undefined)
    renderLogin()
    await userEvent.type(screen.getByLabelText('Admin password'), 'secret')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
    await waitFor(() => expect(mockLogin).toHaveBeenCalledWith('secret', undefined))
    expect(mockNavigate).toHaveBeenCalledWith('/')
  })

  it('shows an error message on ApiError', async () => {
    mockLogin.mockRejectedValue(new ApiError(401, 'bad password'))
    renderLogin()
    await userEvent.type(screen.getByLabelText('Admin password'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
    await waitFor(() => expect(screen.getByText('bad password')).toBeInTheDocument())
  })

  it('shows generic error for non-ApiError', async () => {
    mockLogin.mockRejectedValue(new Error('network'))
    renderLogin()
    await userEvent.type(screen.getByLabelText('Admin password'), 'x')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
    await waitFor(() => expect(screen.getByText('login failed')).toBeInTheDocument())
  })
})
