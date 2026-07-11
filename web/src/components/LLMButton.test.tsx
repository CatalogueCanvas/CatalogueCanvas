import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { LLMButton } from './LLMButton'
import type { AppSettings } from '../api/client'

vi.mock('../api/client', () => ({
  getSettings: vi.fn(),
  describeItem: vi.fn(),
  ApiError: class extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.status = status
    }
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

const defaultSettings: AppSettings = {
  llm_api_url: 'http://localhost:1234',
  llm_model: 'test-model',
  llm_item_type: 'artwork',
  llm_summary_focus: 'visual',
  llm_bullet_count: '3',
  llm_bullet_max_words: '50',
  llm_auto_generate: 'true',
  llm_prompt_template: '',
  llm_prompt_template_default: '',
  theme: 'light',
  accent: 'default',
  nav: 'top',
  density: 'balanced',
  favorites_enabled: 'false',
  multi_user_enabled: 'false',
  update_check_enabled: 'false',
  stats: { total_items: 0, total_collections: 0, missing_preview: 0 },
}

function renderButton(onResult = vi.fn()) {
  return render(<MemoryRouter><LLMButton itemId="item-1" itemTitle="Test Item" onResult={onResult} /></MemoryRouter>)
}

describe('LLMButton', () => {
  it('renders the initial button', () => {
    mocked.getSettings.mockResolvedValue(defaultSettings)
    renderButton()
    expect(screen.getByText('Generate description (LLM)')).toBeInTheDocument()
  })

  it('opens the form when clicked', async () => {
    mocked.getSettings.mockResolvedValue(defaultSettings)
    renderButton()
    await userEvent.click(screen.getByText('Generate description (LLM)'))
    expect(screen.getByText('Generate')).toBeInTheDocument()
    expect(screen.getByLabelText('API key (optional, never stored)')).toBeInTheDocument()
  })

  it('closes the form when Cancel is clicked', async () => {
    mocked.getSettings.mockResolvedValue(defaultSettings)
    renderButton()
    await userEvent.click(screen.getByText('Generate description (LLM)'))
    await userEvent.click(screen.getByText('Cancel'))
    expect(screen.getByText('Generate description (LLM)')).toBeInTheDocument()
  })

  it('calls describeItem and passes result on success', async () => {
    const result = { summary: 'A test summary', descriptions: ['desc1'] }
    mocked.getSettings.mockResolvedValue(defaultSettings)
    mocked.describeItem.mockResolvedValue(result)
    const onResult = vi.fn()
    renderButton(onResult)
    await waitFor(() => expect(mocked.getSettings).toHaveBeenCalled())

    await userEvent.click(screen.getByText('Generate description (LLM)'))
    await userEvent.click(screen.getByText('Generate'))
    await waitFor(() => expect(onResult).toHaveBeenCalledWith(result))
  })

  it('shows error on failure', async () => {
    mocked.getSettings.mockResolvedValue(defaultSettings)
    mocked.describeItem.mockRejectedValue(new Error('network error'))
    renderButton()
    await waitFor(() => expect(mocked.getSettings).toHaveBeenCalled())

    await userEvent.click(screen.getByText('Generate description (LLM)'))
    await userEvent.click(screen.getByText('Generate'))
    await waitFor(() => expect(screen.getByText('request failed')).toBeInTheDocument())
  })
})
