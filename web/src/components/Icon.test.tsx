import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { Icon } from './Icon'

describe('Icon', () => {
  it('renders an svg for a known name', () => {
    const { container } = render(<Icon name="items" />)
    const svg = container.querySelector('svg')
    expect(svg).not.toBeNull()
    expect(svg).toHaveAttribute('viewBox', '0 0 24 24')
  })

  it('applies size and extra className', () => {
    const { container } = render(<Icon name="settings" size={32} className="extra" />)
    const svg = container.querySelector('svg')!
    expect(svg).toHaveAttribute('width', '32')
    expect(svg.getAttribute('class')).toContain('extra')
  })

  it('renders nothing for an unknown name', () => {
    const { container } = render(<Icon name="nope" />)
    expect(container.querySelector('svg')).toBeNull()
  })
})
