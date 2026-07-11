import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Footer } from './Footer'
import { AuthProvider } from '../api/auth'

// Footer now reads auth state (admin-only update badge). Stub fetch so the
// AuthProvider's me() call resolves to an anonymous user — no update check runs.
beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true,
    status: 200,
    json: async () => ({ authenticated: false, role: null, username: null, multi_user: false }),
  })) as unknown as typeof fetch)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

const renderFooter = () => render(<AuthProvider><Footer /></AuthProvider>)

describe('Footer', () => {
  it('renders attribution and the build version', () => {
    renderFooter()
    expect(screen.getByText(/Designed and built by ToroRojo/)).toBeInTheDocument()
    expect(screen.getByText(/^v/)).toBeInTheDocument()
  })

  it('links to the license, issues and discussions', () => {
    renderFooter()
    expect(screen.getByRole('link', { name: /AGPL-3.0/ })).toHaveAttribute(
      'href',
      expect.stringContaining('/LICENSE'),
    )
    expect(screen.getByRole('link', { name: /Report Problem/ })).toHaveAttribute(
      'href',
      expect.stringContaining('/issues'),
    )
  })
})
