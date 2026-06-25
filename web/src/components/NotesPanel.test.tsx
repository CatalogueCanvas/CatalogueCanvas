import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { NotesPanel } from './NotesPanel'
import type { Item } from '../api/client'

vi.mock('../api/client', () => ({
  updateItem: vi.fn(),
}))

vi.mock('react-markdown', () => ({
  default: ({ children }: { children: string }) => <div data-testid="markdown">{children}</div>,
}))

import * as api from '../api/client'
const mocked = vi.mocked(api)

afterEach(() => vi.clearAllMocks())

function makeItem(over: Partial<Item> = {}): Item {
  return {
    id: 'item-1', content_hash: 'h', title: 'Test', note: 'hello **world**',
    mime_type: 'image/png', preview_path: 'p.png', preview_url: '/p.png',
    other_files: [], download_urls: [], tags: [], collection_ids: [],
    raw_meta: {}, ingested_at: '', imported_at: null,
    width: null, height: null, library_id: 'lib1', ...over,
  }
}

describe('NotesPanel', () => {
  it('renders the note content in read mode', () => {
    render(<NotesPanel item={makeItem()} onSaved={vi.fn()} />)
    expect(screen.getByTestId('markdown')).toHaveTextContent('hello **world**')
    expect(screen.getByText('Edit')).toBeInTheDocument()
  })

  it('shows "No notes yet" when note is empty', () => {
    render(<NotesPanel item={makeItem({ note: '' })} onSaved={vi.fn()} />)
    expect(screen.getByText('No notes yet.')).toBeInTheDocument()
  })

  it('hides the edit button in readOnly mode', () => {
    render(<NotesPanel item={makeItem()} onSaved={vi.fn()} readOnly />)
    expect(screen.queryByText('Edit')).not.toBeInTheDocument()
  })

  it('edits and saves a note', async () => {
    const onSaved = vi.fn()
    const updated = makeItem({ note: 'updated' })
    mocked.updateItem.mockResolvedValue(updated)
    render(<NotesPanel item={makeItem()} onSaved={onSaved} />)

    await userEvent.click(screen.getByText('Edit'))
    const textarea = screen.getByRole('textbox')
    await userEvent.clear(textarea)
    await userEvent.type(textarea, 'updated')
    await userEvent.click(screen.getByText('Save'))

    await waitFor(() => expect(mocked.updateItem).toHaveBeenCalledWith('item-1', { note: 'updated' }))
    expect(onSaved).toHaveBeenCalledWith(updated)
  })

  it('cancels editing and restores original note', async () => {
    render(<NotesPanel item={makeItem()} onSaved={vi.fn()} />)
    await userEvent.click(screen.getByText('Edit'))
    const textarea = screen.getByRole('textbox')
    await userEvent.clear(textarea)
    await userEvent.type(textarea, 'changed')
    await userEvent.click(screen.getByText('Cancel'))
    expect(screen.getByTestId('markdown')).toHaveTextContent('hello **world**')
  })
})
