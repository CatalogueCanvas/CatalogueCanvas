import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ItemEdit } from './ItemEdit'
import type { AppSettings, DescribeResult, Item } from '../api/client'

vi.mock('../api/client', () => ({
  getItem: vi.fn(),
  getSettings: vi.fn(),
  listItems: vi.fn(),
  updateItem: vi.fn(),
  deleteItem: vi.fn(),
  favoriteItem: vi.fn(),
  unfavoriteItem: vi.fn(),
  itemMetadataUrl: vi.fn(() => '/api/items/item-1/metadata'),
  itemArchiveUrl: vi.fn(() => '/api/items/item-1/archive'),
  describeResultToNote: (r: DescribeResult) =>
    [r.summary, '', ...r.descriptions.map((d) => `- ${d}`)].join('\n'),
}))

vi.mock('../api/appearance', () => ({
  useAppearance: () => ({ appearance: { favoritesEnabled: false } }),
}))

vi.mock('../api/auth', () => ({
  useAuth: () => ({ isAdmin: true }),
}))

vi.mock('../components/MetadataForm', () => ({
  MetadataForm: () => <div data-testid="metadata-form">MetadataForm</div>,
}))

vi.mock('../components/NotesPanel', () => ({
  NotesPanel: () => <div data-testid="notes-panel">NotesPanel</div>,
}))

vi.mock('../components/LLMButton', () => ({
  LLMButton: ({ onResult }: { onResult: (r: DescribeResult) => void }) => (
    <button
      data-testid="llm-button"
      onClick={() => onResult({ summary: 'A cat', descriptions: ['fluffy', 'orange'] })}
    >
      LLMButton
    </button>
  ),
}))

vi.mock('../components/Icon', () => ({
  Icon: ({ name }: { name: string }) => <span data-testid={`icon-${name}`} />,
}))

import * as api from '../api/client'
const mocked = vi.mocked(api)

afterEach(() => vi.clearAllMocks())

function makeSettings(over: Partial<AppSettings> = {}): AppSettings {
  return {
    llm_api_url: '', llm_model: '', llm_item_type: '', llm_summary_focus: '',
    llm_bullet_count: '3', llm_bullet_max_words: '50', llm_auto_generate: 'false',
    llm_prompt_template: '', llm_prompt_template_default: '',
    theme: 'light', accent: 'default', nav: 'top', density: 'balanced', favorites_enabled: 'false',
    multi_user_enabled: 'false',
    update_check_enabled: 'false',
    stats: { total_items: 0, total_collections: 0, missing_preview: 0 }, ...over,
  }
}

function makeItem(over: Partial<Item> = {}): Item {
  return {
    id: 'item-1', content_hash: 'h', title: 'Test Item', note: '',
    mime_type: 'image/png', preview_path: 'p.png', preview_url: '/p.png',
    other_files: [], download_urls: [], tags: ['art'], collection_ids: [],
    raw_meta: {}, ingested_at: '2024-01-01', imported_at: null,
    width: null, height: null, library_id: 'lib1', ...over,
  }
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/items/item-1']}>
      <Routes>
        <Route path="/items/:id" element={<ItemEdit />} />
        <Route path="/" element={<div>Home</div>} />
      </Routes>
    </MemoryRouter>
  )
}

describe('ItemEdit', () => {
  it('shows loading state initially', () => {
    mocked.getItem.mockReturnValue(new Promise(() => {}))
    mocked.getSettings.mockReturnValue(new Promise(() => {}))
    mocked.listItems.mockReturnValue(new Promise(() => {}))
    renderPage()
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders item title and components', async () => {
    mocked.getItem.mockResolvedValue(makeItem())
    mocked.getSettings.mockResolvedValue(makeSettings())
    mocked.listItems.mockResolvedValue([makeItem()])
    renderPage()
    await waitFor(() => expect(screen.getByText('Test Item')).toBeInTheDocument())
    expect(screen.getByTestId('metadata-form')).toBeInTheDocument()
    expect(screen.getByTestId('notes-panel')).toBeInTheDocument()
  })

  it('shows the preview image', async () => {
    mocked.getItem.mockResolvedValue(makeItem())
    mocked.getSettings.mockResolvedValue(makeSettings())
    mocked.listItems.mockResolvedValue([makeItem()])
    renderPage()
    await waitFor(() => expect(screen.getByAltText('Test Item')).toBeInTheDocument())
  })

  it('shows "no preview" when preview_url is null', async () => {
    mocked.getItem.mockResolvedValue(makeItem({ preview_url: null }))
    mocked.getSettings.mockResolvedValue(makeSettings())
    mocked.listItems.mockResolvedValue([makeItem({ preview_url: null })])
    renderPage()
    await waitFor(() => expect(screen.getByText('no preview')).toBeInTheDocument())
  })

  it('shows delete button for admin', async () => {
    mocked.getItem.mockResolvedValue(makeItem())
    mocked.getSettings.mockResolvedValue(makeSettings())
    mocked.listItems.mockResolvedValue([makeItem()])
    renderPage()
    await waitFor(() => expect(screen.getByText('Delete')).toBeInTheDocument())
  })

  it('deletes item after confirmation', async () => {
    mocked.getItem.mockResolvedValue(makeItem())
    mocked.getSettings.mockResolvedValue(makeSettings())
    mocked.listItems.mockResolvedValue([makeItem()])
    mocked.deleteItem.mockResolvedValue({ ok: true })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderPage()
    await waitFor(() => expect(screen.getByText('Delete')).toBeInTheDocument())

    await userEvent.click(screen.getByText('Delete'))
    await waitFor(() => expect(mocked.deleteItem).toHaveBeenCalledWith('item-1'))
  })

  it('shows LLMButton when auto-generate is enabled', async () => {
    mocked.getItem.mockResolvedValue(makeItem())
    mocked.getSettings.mockResolvedValue(makeSettings({ llm_auto_generate: 'true' }))
    mocked.listItems.mockResolvedValue([makeItem()])
    renderPage()
    await waitFor(() => expect(screen.getByTestId('llm-button')).toBeInTheDocument())
  })

  it('applies the LLM result to the note as a formatted string', async () => {
    mocked.getItem.mockResolvedValue(makeItem())
    mocked.getSettings.mockResolvedValue(makeSettings({ llm_auto_generate: 'true' }))
    mocked.listItems.mockResolvedValue([makeItem()])
    mocked.updateItem.mockResolvedValue(makeItem({ note: 'A cat\n\n- fluffy\n- orange' }))
    renderPage()
    await waitFor(() => expect(screen.getByTestId('llm-button')).toBeInTheDocument())

    await userEvent.click(screen.getByTestId('llm-button'))
    await userEvent.click(await screen.findByText('Apply to note'))

    await waitFor(() =>
      expect(mocked.updateItem).toHaveBeenCalledWith('item-1', { note: 'A cat\n\n- fluffy\n- orange' })
    )
  })

  it('shows navigation links when there are adjacent items', async () => {
    mocked.getItem.mockResolvedValue(makeItem())
    mocked.getSettings.mockResolvedValue(makeSettings())
    mocked.listItems.mockResolvedValue([
      makeItem({ id: 'item-0', title: 'First' }),
      makeItem(),
      makeItem({ id: 'item-2', title: 'Third' }),
    ])
    renderPage()
    await waitFor(() => expect(screen.getByLabelText('Previous item')).toBeInTheDocument())
    expect(screen.getByLabelText('Next item')).toBeInTheDocument()
  })
})
