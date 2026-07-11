import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { BulkToolbar } from './BulkToolbar'
import type { DescribeResult, Item, Portfolio } from '../api/client'

vi.mock('../api/client', () => ({
  bulkClearNotes: vi.fn(),
  downloadBulkArchive: vi.fn(),
  bulkAddTags: vi.fn(),
  bulkFavorite: vi.fn(),
  bulkUnfavorite: vi.fn(),
  updatePortfolioItems: vi.fn(),
  getSettings: vi.fn(),
  describeItem: vi.fn(),
  updateItem: vi.fn(),
  describeResultToNote: (r: DescribeResult) =>
    [r.summary, '', ...r.descriptions.map((d) => `- ${d}`)].join('\n'),
}))

vi.mock('../api/auth', () => ({
  useAuth: () => ({ isAdmin: true }),
}))

vi.mock('../api/appearance', () => ({
  useAppearance: () => ({ appearance: { favoritesEnabled: true } }),
}))

vi.mock('../api/activity', () => ({
  useActivity: () => ({
    startTask: vi.fn(() => 'task-1'),
    updateItem: vi.fn(),
    finishTask: vi.fn(),
  }),
}))

vi.mock('./Icon', () => ({
  Icon: ({ name }: { name: string }) => <span data-testid={`icon-${name}`} />,
}))

import * as api from '../api/client'
const mocked = vi.mocked(api)

afterEach(() => vi.clearAllMocks())

function makeItem(over: Partial<Item> = {}): Item {
  return {
    id: 'item-1', content_hash: 'h', title: 'Test', note: '',
    mime_type: 'image/png', preview_path: 'p.png', preview_url: '/p.png',
    other_files: [], download_urls: [], tags: [], collection_ids: [],
    raw_meta: {}, ingested_at: '', imported_at: null,
    width: null, height: null, library_id: 'lib1', ...over,
  }
}

function makePortfolio(over: Partial<Portfolio> = {}): Portfolio {
  return { id: 'p-1', title: 'P', slug: 'p', description: '', is_public: false, item_ids: [], style: 'ledger', watermark_enabled: false, watermark_text: '', share_token: '', created_at: '', ...over }
}

const defaultProps = {
  selectedIds: ['item-1'],
  items: [makeItem()],
  portfolios: [makePortfolio()],
  totalCount: 5,
  onDone: vi.fn(),
  onClear: vi.fn(),
  onSelectAll: vi.fn(),
}

function renderToolbar(props = defaultProps) {
  return render(<MemoryRouter><BulkToolbar {...props} /></MemoryRouter>)
}

describe('BulkToolbar', () => {
  it('shows selected count', () => {
    renderToolbar()
    expect(screen.getByText('1 selected')).toBeInTheDocument()
  })

  it('calls onSelectAll when Select all is clicked', async () => {
    renderToolbar()
    await userEvent.click(screen.getByText('Select all (5)'))
    expect(defaultProps.onSelectAll).toHaveBeenCalled()
  })

  it('calls onClear when Clear selection is clicked', async () => {
    renderToolbar()
    await userEvent.click(screen.getByText('Clear selection'))
    expect(defaultProps.onClear).toHaveBeenCalled()
  })

  it('clears notes after confirmation', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    mocked.bulkClearNotes.mockResolvedValue({ updated: [], missing: [] })
    renderToolbar()
    await userEvent.click(screen.getByText('Clear notes'))
    await waitFor(() => expect(mocked.bulkClearNotes).toHaveBeenCalledWith(['item-1']))
    expect(defaultProps.onDone).toHaveBeenCalled()
  })

  it('downloads a zip archive', async () => {
    mocked.downloadBulkArchive.mockResolvedValue(undefined)
    renderToolbar()
    await userEvent.click(screen.getByText('Download zip'))
    await waitFor(() => expect(mocked.downloadBulkArchive).toHaveBeenCalledWith(['item-1']))
  })

  it('adds tags from input', async () => {
    mocked.bulkAddTags.mockResolvedValue({ updated: [], missing: [] })
    renderToolbar()
    await userEvent.type(screen.getByPlaceholderText('tag1, tag2...'), 'red, blue')
    await userEvent.click(screen.getByText('Add tags'))
    await waitFor(() => expect(mocked.bulkAddTags).toHaveBeenCalledWith(['item-1'], ['red', 'blue']))
  })

  it('adds favorites', async () => {
    mocked.bulkFavorite.mockResolvedValue({ updated: [], missing: [] })
    renderToolbar()
    await userEvent.click(screen.getByText('Add to Favorites'))
    await waitFor(() => expect(mocked.bulkFavorite).toHaveBeenCalledWith(['item-1']))
  })

  it('removes favorites', async () => {
    mocked.bulkUnfavorite.mockResolvedValue({ updated: [], missing: [] })
    renderToolbar()
    await userEvent.click(screen.getByText('Remove from Favorites'))
    await waitFor(() => expect(mocked.bulkUnfavorite).toHaveBeenCalledWith(['item-1']))
  })

  it('generates descriptions and stores the full formatted note', async () => {
    mocked.getSettings.mockResolvedValue({
      llm_api_url: '', llm_model: '', llm_item_type: '', llm_summary_focus: '',
      llm_bullet_count: '3', llm_bullet_max_words: '50', llm_prompt_template: '',
    } as unknown as Awaited<ReturnType<typeof api.getSettings>>)
    mocked.describeItem.mockResolvedValue({ summary: 'A cat', descriptions: ['fluffy', 'orange'] })
    mocked.updateItem.mockResolvedValue(makeItem())
    renderToolbar()
    await userEvent.click(screen.getByText('Generate descriptions (LLM)'))
    await waitFor(() =>
      expect(mocked.updateItem).toHaveBeenCalledWith('item-1', { note: 'A cat\n\n- fluffy\n- orange' })
    )
  })

  it('applies portfolio action', async () => {
    mocked.updatePortfolioItems.mockResolvedValue(makePortfolio())
    renderToolbar()
    await userEvent.selectOptions(screen.getAllByRole('combobox')[0], 'p-1')
    await userEvent.click(screen.getByText('Apply'))
    await waitFor(() => expect(mocked.updatePortfolioItems).toHaveBeenCalledWith('p-1', ['item-1'], 'add'))
  })
})
