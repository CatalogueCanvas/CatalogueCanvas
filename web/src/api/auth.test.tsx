import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { AuthProvider, useAuth } from './auth'
import * as api from './client'

vi.mock('./client', () => ({
  me: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
}))

const mocked = vi.mocked(api)

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <AuthProvider>{children}</AuthProvider>
)

afterEach(() => vi.clearAllMocks())

describe('useAuth', () => {
  it('throws outside the provider', () => {
    expect(() => renderHook(() => useAuth())).toThrow(/within AuthProvider/)
  })

  it('loads the current session on mount', async () => {
    mocked.me.mockResolvedValue({ authenticated: true, role: 'admin', username: 'admin', multi_user: false })
    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.authenticated).toBe(true)
    expect(result.current.isAdmin).toBe(true)
  })

  it('login updates the auth state', async () => {
    mocked.me.mockResolvedValue({ authenticated: false, role: null, username: null, multi_user: false })
    mocked.login.mockResolvedValue({ ok: true, role: 'reader', username: 'bob' })
    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => { await result.current.login('pw', 'bob') })
    expect(result.current.authenticated).toBe(true)
    expect(result.current.role).toBe('reader')
    expect(result.current.isAdmin).toBe(false)
  })

  it('logout clears the auth state', async () => {
    mocked.me.mockResolvedValue({ authenticated: true, role: 'admin', username: 'admin', multi_user: false })
    mocked.logout.mockResolvedValue({ ok: true })
    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.authenticated).toBe(true))

    await act(async () => { await result.current.logout() })
    expect(result.current.authenticated).toBe(false)
    expect(result.current.role).toBeNull()
  })
})
