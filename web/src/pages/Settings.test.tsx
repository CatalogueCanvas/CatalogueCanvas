import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Settings } from './Settings'
import type { AppSettings } from '../api/client'

vi.mock('../api/client', () => ({
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  listLibraries: vi.fn(),
  createLibrary: vi.fn(),
  setDefaultLibrary: vi.fn(),
  deleteLibrary: vi.fn(),
  exportDatabase: vi.fn(),
  exportFullBackup: vi.fn(),
  downloadDiagnostics: vi.fn(),
  exportItemsCsv: vi.fn(),
  previewCsvImport: vi.fn(),
  applyCsvImport: vi.fn(),
  listCsvBackups: vi.fn(),
  deleteCsvBackup: vi.fn(),
  ApiError: class extends Error {
    status: number
    constructor(status: number, message: string) { super(message); this.status = status }
  },
  DELETE_BACKUP_CONFIRM: 'DELETE',
}))

vi.mock('../api/appearance', () => ({
  ACCENT_PRESETS: {
    default: { accent: null, dim: null, contrast: null },
    vermilion: { accent: '#e54d2e', dim: '#4a2218', contrast: '#fff' },
  },
  useAppearance: () => ({
    appearance: { theme: 'light', nav: 'side', density: 'balanced', accent: 'default', favoritesEnabled: false },
    setAppearance: vi.fn(),
  }),
}))

vi.mock('../components/UsersPanel', () => ({
  UsersPanel: () => <div data-testid="users-panel">UsersPanel</div>,
}))

import * as api from '../api/client'
const mocked = vi.mocked(api)

afterEach(() => vi.clearAllMocks())

function makeSettings(over: Partial<AppSettings> = {}): AppSettings {
  return {
    llm_api_url: 'http://localhost:1234',
    llm_model: 'test-model',
    llm_item_type: 'artwork',
    llm_summary_focus: 'visual',
    llm_bullet_count: '3',
    llm_bullet_max_words: '50',
    llm_auto_generate: 'false',
    llm_prompt_template: 'template',
    llm_prompt_template_default: 'default-template',
    multi_user_enabled: 'false',
    stats: { total_items: 10, total_collections: 3, missing_preview: 1 },
    ...over,
  } as AppSettings
}

describe('Settings', () => {
  it('shows loading state', async () => {
    // Deferred (not never-resolving) so the worker can tear down — a dangling
    // promise blocks vitest exit / v8 coverage flush when run in isolation.
    let resolve!: (s: AppSettings) => void
    const pending = new Promise<AppSettings>((r) => { resolve = r })
    mocked.getSettings.mockReturnValue(pending)
    mocked.listLibraries.mockResolvedValue([])
    mocked.listCsvBackups.mockResolvedValue({ backups: [] })
    render(<Settings />)
    expect(screen.getByText('Loading...')).toBeInTheDocument()
    resolve(makeSettings())
    await pending
  })

  it('renders settings form after loading', async () => {
    mocked.getSettings.mockResolvedValue(makeSettings())
    mocked.listLibraries.mockResolvedValue([])
    mocked.listCsvBackups.mockResolvedValue({ backups: [] })
    render(<Settings />)
    await waitFor(() => expect(screen.getByText('Settings/Admin')).toBeInTheDocument())
    expect(screen.getByText('Appearance')).toBeInTheDocument()
    expect(screen.getByText('LLM defaults')).toBeInTheDocument()
    expect(screen.getByText('Backup & export')).toBeInTheDocument()
  })

  it('shows stats in backup section', async () => {
    mocked.getSettings.mockResolvedValue(makeSettings())
    mocked.listLibraries.mockResolvedValue([])
    mocked.listCsvBackups.mockResolvedValue({ backups: [] })
    render(<Settings />)
    await waitFor(() => expect(screen.getByText('10')).toBeInTheDocument())
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
  })

  it('saves LLM settings', async () => {
    mocked.getSettings.mockResolvedValue(makeSettings())
    mocked.listLibraries.mockResolvedValue([])
    mocked.listCsvBackups.mockResolvedValue({ backups: [] })
    mocked.updateSettings.mockResolvedValue(makeSettings())
    render(<Settings />)
    await waitFor(() => expect(screen.getByText('Settings/Admin')).toBeInTheDocument())

    const saveButtons = screen.getAllByText('Save')
    await userEvent.click(saveButtons[1])
    await waitFor(() => expect(mocked.updateSettings).toHaveBeenCalled())
  })

  it('shows UsersPanel when multi-user is enabled', async () => {
    mocked.getSettings.mockResolvedValue(makeSettings({ multi_user_enabled: 'true' }))
    mocked.listLibraries.mockResolvedValue([])
    mocked.listCsvBackups.mockResolvedValue({ backups: [] })
    render(<Settings />)
    await waitFor(() => expect(screen.getByTestId('users-panel')).toBeInTheDocument())
  })

  it('renders theme and density toggles', async () => {
    mocked.getSettings.mockResolvedValue(makeSettings())
    mocked.listLibraries.mockResolvedValue([])
    mocked.listCsvBackups.mockResolvedValue({ backups: [] })
    render(<Settings />)
    await waitFor(() => expect(screen.getByText('Light')).toBeInTheDocument())
    expect(screen.getByText('Dark')).toBeInTheDocument()
    expect(screen.getByText('Airy')).toBeInTheDocument()
    expect(screen.getByText('Balanced')).toBeInTheDocument()
    expect(screen.getByText('Dense')).toBeInTheDocument()
  })

  it('renders library section', async () => {
    mocked.getSettings.mockResolvedValue(makeSettings())
    mocked.listLibraries.mockResolvedValue([
      { id: 'lib1', name: 'Default', path: '/data/storage', is_default: true, item_count: 5, path_ok: true },
    ])
    mocked.listCsvBackups.mockResolvedValue({ backups: [] })
    render(<Settings />)
    await waitFor(() => expect(screen.getByText('Default')).toBeInTheDocument())
    expect(screen.getByText('(default)')).toBeInTheDocument()
  })

  it('resets prompt template to default', async () => {
    mocked.getSettings.mockResolvedValue(makeSettings())
    mocked.listLibraries.mockResolvedValue([])
    mocked.listCsvBackups.mockResolvedValue({ backups: [] })
    render(<Settings />)
    await waitFor(() => expect(screen.getByText('Reset to default')).toBeInTheDocument())
  })
})
