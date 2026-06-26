import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Uploader } from './Uploader'

vi.mock('../api/client', () => ({
  listLibraries: vi.fn(),
  uploadItem: vi.fn(),
  ApiError: class extends Error {
    status: number
    constructor(status: number, message: string) { super(message); this.status = status }
  },
}))

vi.mock('../api/activity', () => ({
  useActivity: () => ({
    startTask: vi.fn(() => 'task-1'),
    updateItem: vi.fn(),
    finishTask: vi.fn(),
  }),
}))

import * as api from '../api/client'
const mocked = vi.mocked(api)

afterEach(() => vi.clearAllMocks())

describe('Uploader', () => {
  it('renders the dropzone text', async () => {
    mocked.listLibraries.mockResolvedValue([])
    render(<Uploader onUploaded={vi.fn()} />)
    expect(screen.getByText('Drop ZIP files here or click to upload')).toBeInTheDocument()
  })

  it('shows library selector when multiple libraries exist', async () => {
    mocked.listLibraries.mockResolvedValue([
      { id: 'lib1', name: 'Default', path: '/data', is_default: true, item_count: 0, path_ok: true },
      { id: 'lib2', name: 'Extra', path: '/extra', is_default: false, item_count: 0, path_ok: true },
    ])
    render(<Uploader onUploaded={vi.fn()} />)
    await waitFor(() => expect(screen.getByLabelText('Library')).toBeInTheDocument())
  })

  it('does not show library selector with single library', async () => {
    mocked.listLibraries.mockResolvedValue([
      { id: 'lib1', name: 'Default', path: '/data', is_default: true, item_count: 0, path_ok: true },
    ])
    render(<Uploader onUploaded={vi.fn()} />)
    await waitFor(() => expect(mocked.listLibraries).toHaveBeenCalled())
    expect(screen.queryByLabelText('Library')).not.toBeInTheDocument()
  })

  it('uploads a zip file and calls onUploaded', async () => {
    mocked.listLibraries.mockResolvedValue([])
    mocked.uploadItem.mockResolvedValue({ created: true, item: { id: 'new-item' }, note: null })
    const onUploaded = vi.fn()
    render(<Uploader onUploaded={onUploaded} />)

    const file = new File(['zip content'], 'test.zip', { type: 'application/zip' })
    const fileInput = screen.getByTestId('upload-input') as HTMLInputElement
    await userEvent.upload(fileInput, file)
    await waitFor(() => expect(mocked.uploadItem).toHaveBeenCalledWith(file, undefined))
    expect(onUploaded).toHaveBeenCalled()
  })

  it('ignores non-zip files', async () => {
    mocked.listLibraries.mockResolvedValue([])
    const onUploaded = vi.fn()
    render(<Uploader onUploaded={onUploaded} />)

    const file = new File(['content'], 'test.txt', { type: 'text/plain' })
    const fileInput = screen.getByTestId('upload-input') as HTMLInputElement
    await userEvent.upload(fileInput, file)
    expect(mocked.uploadItem).not.toHaveBeenCalled()
  })
})
