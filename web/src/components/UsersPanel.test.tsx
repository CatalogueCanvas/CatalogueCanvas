import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { UsersPanel } from './UsersPanel'
import type { User } from '../api/client'

vi.mock('../api/client', () => ({
  listUsers: vi.fn(),
  createUser: vi.fn(),
  updateUser: vi.fn(),
  deleteUser: vi.fn(),
  ApiError: class extends Error {
    status: number
    constructor(status: number, message: string) { super(message); this.status = status }
  },
}))

import * as api from '../api/client'
const mocked = vi.mocked(api)

afterEach(() => vi.clearAllMocks())

function makeUser(over: Partial<User> = {}): User {
  return { id: 1, username: 'bob', role: 'reader', created_at: '', ...over }
}

describe('UsersPanel', () => {
  it('renders the create user form', async () => {
    mocked.listUsers.mockResolvedValue([])
    render(<UsersPanel />)
    expect(screen.getByLabelText('Username')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    expect(screen.getByText('Add user')).toBeInTheDocument()
  })

  it('lists existing users', async () => {
    mocked.listUsers.mockResolvedValue([makeUser()])
    render(<UsersPanel />)
    await waitFor(() => expect(screen.getByText('bob')).toBeInTheDocument())
    expect(screen.getByText('reader')).toBeInTheDocument()
  })

  it('creates a user', async () => {
    mocked.listUsers.mockResolvedValue([])
    mocked.createUser.mockResolvedValue(makeUser())
    render(<UsersPanel />)

    await userEvent.type(screen.getByLabelText('Username'), 'alice')
    await userEvent.type(screen.getByLabelText('Password'), 'pass123')
    await userEvent.click(screen.getByText('Add user'))
    await waitFor(() => expect(mocked.createUser).toHaveBeenCalledWith({
      username: 'alice', password: 'pass123', role: 'reader',
    }))
  })

  it('does not create user with blank fields', async () => {
    mocked.listUsers.mockResolvedValue([])
    render(<UsersPanel />)
    await userEvent.click(screen.getByText('Add user'))
    expect(mocked.createUser).not.toHaveBeenCalled()
  })

  it('deletes a user after confirmation', async () => {
    mocked.listUsers.mockResolvedValue([makeUser()])
    mocked.deleteUser.mockResolvedValue({ ok: true })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<UsersPanel />)
    await waitFor(() => expect(screen.getByText('bob')).toBeInTheDocument())

    await userEvent.click(screen.getByText('Delete'))
    await waitFor(() => expect(mocked.deleteUser).toHaveBeenCalledWith(1))
  })

  it('changes user role', async () => {
    mocked.listUsers.mockResolvedValue([makeUser()])
    mocked.updateUser.mockResolvedValue(makeUser())
    render(<UsersPanel />)
    await waitFor(() => expect(screen.getByText('bob')).toBeInTheDocument())

    const adminButtons = screen.getAllByText('Admin')
    await userEvent.click(adminButtons[0])
    await waitFor(() => expect(mocked.updateUser).toHaveBeenCalledWith(1, { role: 'admin' }))
  })

  it('resets password via prompt', async () => {
    mocked.listUsers.mockResolvedValue([makeUser()])
    mocked.updateUser.mockResolvedValue(makeUser())
    vi.spyOn(window, 'prompt').mockReturnValue('newpass')
    render(<UsersPanel />)
    await waitFor(() => expect(screen.getByText('bob')).toBeInTheDocument())

    await userEvent.click(screen.getByText('Reset password'))
    await waitFor(() => expect(mocked.updateUser).toHaveBeenCalledWith(1, { password: 'newpass' }))
  })
})
