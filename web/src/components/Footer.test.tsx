import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Footer } from './Footer'

describe('Footer', () => {
  it('renders attribution and the build version', () => {
    render(<Footer />)
    expect(screen.getByText(/Designed and built by ToroRojo/)).toBeInTheDocument()
    expect(screen.getByText(/^v/)).toBeInTheDocument()
  })

  it('links to the license, issues and discussions', () => {
    render(<Footer />)
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
