import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MetadataForm } from './MetadataForm'
import type { Item } from '../api/client'

vi.mock('../api/client', () => ({
  listCollections: vi.fn(),
  updateItem: vi.fn(),
}))

import * as api from '../api/client'
const mocked = vi.mocked(api)

afterEach(() => vi.clearAllMocks())

function makeItem(over: Partial<Item> = {}): Item {
  return {
    id: 'item-1', content_hash: 'h', title: 'Test Item', note: '',
    mime_type: 'image/png', preview_path: 'p.png', preview_url: '/p.png',
    other_files: [], download_urls: [], tags: ['red', 'blue'], collection_ids: [],
    raw_meta: {}, ingested_at: '', imported_at: null,
    width: null, height: null, library_id: 'lib1', ...over,
  }
}

describe('MetadataForm', () => {
  it('renders title and tags inputs', () => {
    mocked.listCollections.mockResolvedValue([])
    render(<MetadataForm item={makeItem()} onSaved={vi.fn()} />)
    expect(screen.getByLabelText('Title')).toHaveValue('Test Item')
    expect(screen.getByLabelText('Tags (comma separated)')).toHaveValue('red, blue')
  })

  it('renders tag chips', () => {
    mocked.listCollections.mockResolvedValue([])
    render(<MetadataForm item={makeItem()} onSaved={vi.fn()} />)
    expect(screen.getByText('red')).toBeInTheDocument()
    expect(screen.getByText('blue')).toBeInTheDocument()
  })

  it('shows "No tags yet" when tags are empty', () => {
    mocked.listCollections.mockResolvedValue([])
    render(<MetadataForm item={makeItem({ tags: [] })} onSaved={vi.fn()} />)
    expect(screen.getByText('No tags yet.')).toBeInTheDocument()
  })

  it('renders collection checkboxes', async () => {
    mocked.listCollections.mockResolvedValue([
      { id: 'col-1', title: 'Art', is_system: false, item_count: 3 },
    ])
    render(<MetadataForm item={makeItem()} onSaved={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('Art')).toBeInTheDocument())
  })

  it('shows "No collections yet" when none exist', async () => {
    mocked.listCollections.mockResolvedValue([])
    render(<MetadataForm item={makeItem()} onSaved={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('No collections yet.')).toBeInTheDocument())
  })

  it('saves metadata on click', async () => {
    mocked.listCollections.mockResolvedValue([])
    const updated = makeItem({ title: 'Updated' })
    mocked.updateItem.mockResolvedValue(updated)
    const onSaved = vi.fn()
    render(<MetadataForm item={makeItem()} onSaved={onSaved} />)

    await userEvent.click(screen.getByText('Save'))
    await waitFor(() => expect(mocked.updateItem).toHaveBeenCalledWith('item-1', {
      title: 'Test Item',
      tags: ['red', 'blue'],
      collection_ids: [],
    }))
    expect(onSaved).toHaveBeenCalledWith(updated)
  })

  it('hides save button in readOnly mode', () => {
    mocked.listCollections.mockResolvedValue([])
    render(<MetadataForm item={makeItem()} onSaved={vi.fn()} readOnly />)
    expect(screen.queryByText('Save')).not.toBeInTheDocument()
  })

  it('toggles collection selection', async () => {
    mocked.listCollections.mockResolvedValue([
      { id: 'col-1', title: 'Art', is_system: false, item_count: 3 },
    ])
    mocked.updateItem.mockResolvedValue(makeItem())
    const onSaved = vi.fn()
    render(<MetadataForm item={makeItem()} onSaved={onSaved} />)
    await waitFor(() => expect(screen.getByText('Art')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('checkbox', { name: 'Art' }))
    await userEvent.click(screen.getByText('Save'))
    await waitFor(() => expect(mocked.updateItem).toHaveBeenCalledWith('item-1', expect.objectContaining({
      collection_ids: ['col-1'],
    })))
  })
})
