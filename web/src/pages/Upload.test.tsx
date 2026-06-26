import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Upload } from './Upload'

vi.mock('../components/Uploader', () => ({
  Uploader: () => <div data-testid="uploader">uploader-stub</div>,
}))

describe('Upload', () => {
  it('renders the heading and the Uploader component', () => {
    render(<Upload />)
    expect(screen.getByText('Upload')).toBeInTheDocument()
    expect(screen.getByTestId('uploader')).toBeInTheDocument()
  })
})
